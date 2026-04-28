from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_roles
from app.enums import EventOperation, IncidentSeverity, IncidentType, UserRole
from app.models import AppUser, Container, Incident, Trip
from app.routes.helpers import parse_datetime_input
from app.services.audit import log_event, serialize_model
from app.services.rules import BusinessRuleError, ensure_incident_can_be_resolved
from app.web import redirect_to, render_template


router = APIRouter(prefix="/incidents", tags=["incidents"])


INCIDENT_ROLES = (
    UserRole.DEPOT_CONTROLLER.value,
    UserRole.BORDER_AGENT.value,
    UserRole.PORT_AGENT.value,
    UserRole.HUB_OPERATOR.value,
)


@router.get("")
def list_incidents(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(*INCIDENT_ROLES)),
):
    incidents = db.scalars(
        select(Incident)
        .options(joinedload(Incident.trip), joinedload(Incident.container), joinedload(Incident.reported_by))
        .where(Incident.origin_site_code == current_user.site.code)
        .order_by(Incident.incident_time.desc())
    ).all()
    return render_template(
        request,
        "incidents/index.html",
        {
            "incidents": incidents,
            "page_title": "Incidents",
            "current_user": current_user,
            "incident_types": IncidentType,
            "incident_severities": IncidentSeverity,
        },
    )


@router.get("/new")
def new_incident_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(*INCIDENT_ROLES)),
):
    trips = db.scalars(select(Trip).order_by(Trip.created_at.desc())).all()
    containers = db.scalars(select(Container).order_by(Container.container_no)).all()
    return render_template(
        request,
        "incidents/new.html",
        {
            "trips": trips,
            "containers": containers,
            "incident_types": IncidentType,
            "incident_severities": IncidentSeverity,
            "page_title": "Report Incident",
            "current_user": current_user,
        },
    )


@router.post("")
def create_incident(
    request: Request,
    trip_id: str = Form(...),
    container_id: str = Form(""),
    incident_type: str = Form(...),
    severity: str = Form(...),
    incident_time: str = Form(...),
    description: str = Form(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(*INCIDENT_ROLES)),
):
    incident = Incident(
        trip_id=trip_id,
        container_id=container_id or None,
        site_id=current_user.site_id,
        reported_by_id=current_user.id,
        origin_site_code=current_user.site.code,
        incident_type=incident_type,
        severity=severity,
        description=description.strip(),
        incident_time=parse_datetime_input(incident_time),
    )
    db.add(incident)
    db.flush()
    log_event(
        db,
        actor=current_user,
        entity_name="incident",
        record_id=incident.id,
        operation=EventOperation.INSERT,
        payload=serialize_model(incident),
    )
    db.commit()
    return redirect_to("/incidents", message="Incident logged.")


@router.post("/{incident_id}/resolve")
def resolve_incident(
    request: Request,
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(*INCIDENT_ROLES)),
):
    incident = db.get(Incident, incident_id)
    if incident is None:
        return redirect_to("/incidents", error="Incident not found.")
    try:
        ensure_incident_can_be_resolved(current_user, incident)
    except BusinessRuleError as exc:
        db.rollback()
        return redirect_to("/incidents", error=str(exc))

    incident.resolved = True
    incident.resolved_at = datetime.now(timezone.utc)
    incident.resolved_by_id = current_user.id
    log_event(
        db,
        actor=current_user,
        entity_name="incident",
        record_id=incident.id,
        operation=EventOperation.UPDATE,
        payload=serialize_model(incident),
    )
    db.commit()
    return redirect_to("/incidents", message="Incident resolved.")
