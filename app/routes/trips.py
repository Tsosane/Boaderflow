from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_roles
from app.enums import EventOperation, MilestoneType, TripStatus, UserRole
from app.models import AppUser, Container, Driver, Milestone, Site, Trip, TripContainer, Vehicle
from app.routes.helpers import parse_datetime_input
from app.services.audit import log_event, serialize_model
from app.services.projections import refresh_projection_cache
from app.services.rules import (
    BusinessRuleError,
    ensure_container_not_on_active_trip,
    ensure_driver_not_on_active_trip,
    ensure_vehicle_not_on_active_trip,
)
from app.web import redirect_to, render_template


router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("")
def list_trips(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    trips = db.scalars(
        select(Trip)
        .options(
            joinedload(Trip.origin_site),
            joinedload(Trip.destination_site),
            joinedload(Trip.vehicle),
            joinedload(Trip.driver).joinedload(Driver.user),
        )
        .order_by(Trip.created_at.desc())
    ).all()
    assignments = db.scalars(select(TripContainer).options(joinedload(TripContainer.container))).all()
    assignment_map: dict[object, list[TripContainer]] = {}
    for assignment in assignments:
        assignment_map.setdefault(assignment.trip_id, []).append(assignment)
    return render_template(
        request,
        "trips/index.html",
        {"trips": trips, "assignment_map": assignment_map, "page_title": "Trips", "current_user": current_user},
    )


@router.get("/new")
def new_trip_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    vehicles = db.scalars(select(Vehicle).where(Vehicle.is_active.is_(True)).order_by(Vehicle.registration_no)).all()
    drivers = db.scalars(select(Driver).options(joinedload(Driver.user)).where(Driver.is_active.is_(True))).all()
    destinations = db.scalars(
        select(Site).where(Site.code.not_in([current_user.site.code, request.app.state.settings.control_tower_site_code]))
    ).all()
    assigned_container_ids = db.scalars(
        select(TripContainer.container_id).where(TripContainer.active_assignment.is_(True))
    ).all()
    container_query = select(Container).order_by(Container.container_no)
    if assigned_container_ids:
        container_query = container_query.where(Container.id.not_in(assigned_container_ids))
    containers = db.scalars(container_query).all()
    return render_template(
        request,
        "trips/new.html",
        {
            "vehicles": vehicles,
            "drivers": drivers,
            "destinations": destinations,
            "containers": containers,
            "page_title": "Plan Trip",
            "current_user": current_user,
        },
    )


@router.post("")
def create_trip(
    request: Request,
    destination_site_id: str = Form(...),
    vehicle_id: str = Form(...),
    driver_id: str = Form(...),
    container_id: str = Form(...),
    planned_departure: str = Form(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    try:
        ensure_container_not_on_active_trip(db, container_id)
        ensure_vehicle_not_on_active_trip(db, vehicle_id)
        ensure_driver_not_on_active_trip(db, driver_id)
    except BusinessRuleError as exc:
        db.rollback()
        return redirect_to("/trips/new", error=str(exc))

    trip = Trip(
        origin_site_id=current_user.site_id,
        destination_site_id=destination_site_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        origin_site_code=current_user.origin_site_code,
        status=TripStatus.PLANNED.value,
        planned_departure=parse_datetime_input(planned_departure),
        created_by_id=current_user.id,
    )
    db.add(trip)
    db.flush()

    assignment = TripContainer(
        trip_id=trip.id,
        container_id=container_id,
        origin_site_code=current_user.origin_site_code,
        assigned_by_id=current_user.id,
        active_assignment=True,
    )
    db.add(assignment)
    db.flush()

    log_event(db, actor=current_user, entity_name="trip", record_id=trip.id, operation=EventOperation.INSERT, payload=serialize_model(trip))
    log_event(
        db,
        actor=current_user,
        entity_name="trip_container",
        record_id=assignment.id,
        operation=EventOperation.INSERT,
        payload=serialize_model(assignment),
    )
    refresh_projection_cache(db)
    db.commit()
    return redirect_to("/trips", message="Trip created and container assigned.")


@router.post("/{trip_id}/depart")
def depart_trip(
    request: Request,
    trip_id: str,
    departure_time: str = Form(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    _ = request
    trip = db.get(Trip, trip_id)
    if trip is None:
        return redirect_to("/trips", error="Trip not found.")
    if trip.status != TripStatus.PLANNED.value:
        return redirect_to("/trips", error="Only planned trips can be departed.")

    trip.status = TripStatus.DEPARTED.value
    trip.actual_departure = parse_datetime_input(departure_time)
    assignments = db.scalars(select(TripContainer).where(TripContainer.trip_id == trip.id, TripContainer.active_assignment.is_(True))).all()
    for assignment in assignments:
        milestone = Milestone(
            trip_id=trip.id,
            container_id=assignment.container_id,
            site_id=trip.origin_site_id,
            recorded_by_id=current_user.id,
            origin_site_code=current_user.origin_site_code,
            milestone_type=MilestoneType.DEPARTED.value,
            milestone_time=trip.actual_departure,
            notes="Trip departed from depot.",
        )
        db.add(milestone)
        db.flush()
        log_event(
            db,
            actor=current_user,
            entity_name="milestone",
            record_id=milestone.id,
            operation=EventOperation.INSERT,
            payload=serialize_model(milestone),
        )

    log_event(db, actor=current_user, entity_name="trip", record_id=trip.id, operation=EventOperation.UPDATE, payload=serialize_model(trip))
    refresh_projection_cache(db)
    db.commit()
    return redirect_to("/trips", message="Trip departed and departure milestones recorded.")
