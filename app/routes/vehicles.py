from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_roles
from app.enums import EventOperation, UserRole
from app.models import AppUser, Vehicle
from app.services.audit import log_event, serialize_model
from app.web import redirect_to, render_template


router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("")
def list_vehicles(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    vehicles = db.scalars(
        select(Vehicle)
        .where(Vehicle.origin_site_code == current_user.site.code)
        .order_by(Vehicle.registration_no)
    ).all()
    return render_template(
        request,
        "vehicles/index.html",
        {"vehicles": vehicles, "page_title": "Vehicles", "current_user": current_user},
    )


@router.get("/new")
def new_vehicle_form(
    request: Request,
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    return render_template(
        request,
        "vehicles/new.html",
        {"page_title": "Register Vehicle", "current_user": current_user},
    )


@router.post("")
def create_vehicle(
    request: Request,
    registration_no: str = Form(...),
    vehicle_type: str = Form(...),
    capacity_teu: int = Form(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    normalized_registration = registration_no.strip().upper()
    if db.scalar(select(Vehicle.id).where(Vehicle.registration_no == normalized_registration)):
        return redirect_to("/vehicles/new", error="A vehicle with that registration number already exists.")

    vehicle = Vehicle(
        site_id=current_user.site_id,
        origin_site_code=current_user.origin_site_code,
        registration_no=normalized_registration,
        vehicle_type=vehicle_type.strip().upper(),
        capacity_teu=capacity_teu,
    )
    db.add(vehicle)
    db.flush()
    log_event(
        db,
        actor=current_user,
        entity_name="vehicle",
        record_id=vehicle.id,
        operation=EventOperation.INSERT,
        payload=serialize_model(vehicle),
    )
    db.commit()
    return redirect_to("/vehicles", message=f"Vehicle {vehicle.registration_no} registered.")
