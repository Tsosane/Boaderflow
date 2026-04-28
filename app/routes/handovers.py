from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_roles
from app.enums import EventOperation, UserRole
from app.models import AppUser, Container, Handover, Site, Trip
from app.routes.helpers import parse_datetime_input
from app.services.audit import log_event, serialize_model
from app.services.projections import refresh_projection_cache
from app.services.rules import BusinessRuleError, ensure_distinct_sites
from app.web import redirect_to, render_template


router = APIRouter(prefix="/handovers", tags=["handovers"])


@router.get("")
def list_handovers(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.BORDER_AGENT.value, UserRole.PORT_AGENT.value, UserRole.HUB_OPERATOR.value)),
):
    handovers = db.scalars(
        select(Handover)
        .options(joinedload(Handover.container), joinedload(Handover.trip), joinedload(Handover.from_site), joinedload(Handover.to_site))
        .where(Handover.origin_site_code == current_user.site.code)
        .order_by(Handover.handover_time.desc())
    ).all()
    return render_template(
        request,
        "handovers/index.html",
        {"handovers": handovers, "page_title": "Handovers", "current_user": current_user},
    )


@router.get("/new")
def new_handover_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.BORDER_AGENT.value, UserRole.PORT_AGENT.value, UserRole.HUB_OPERATOR.value)),
):
    trips = db.scalars(select(Trip).order_by(Trip.created_at.desc())).all()
    containers = db.scalars(select(Container).order_by(Container.container_no)).all()
    sites = db.scalars(select(Site).where(Site.code != request.app.state.settings.control_tower_site_code)).all()
    users = db.scalars(
        select(AppUser)
        .options(joinedload(AppUser.site))
        .where(AppUser.is_active.is_(True))
        .order_by(AppUser.full_name)
    ).all()
    return render_template(
        request,
        "handovers/new.html",
        {"trips": trips, "containers": containers, "sites": sites, "users": users, "page_title": "Record Handover", "current_user": current_user},
    )


@router.post("")
def create_handover(
    request: Request,
    trip_id: str = Form(...),
    container_id: str = Form(...),
    from_site_id: str = Form(...),
    to_site_id: str = Form(...),
    sender_user_id: str = Form(...),
    receiver_user_id: str = Form(...),
    seal_verified: bool = Form(False),
    seal_no: str = Form(""),
    handover_time: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.BORDER_AGENT.value, UserRole.PORT_AGENT.value, UserRole.HUB_OPERATOR.value)),
):
    try:
        ensure_distinct_sites(from_site_id, to_site_id)
    except BusinessRuleError as exc:
        db.rollback()
        return redirect_to("/handovers/new", error=str(exc))

    if str(current_user.id) not in {sender_user_id, receiver_user_id}:
        return redirect_to("/handovers/new", error="The logged-in user must be one side of the handover.")

    handover = Handover(
        trip_id=trip_id,
        container_id=container_id,
        from_site_id=from_site_id,
        to_site_id=to_site_id,
        sender_user_id=sender_user_id,
        receiver_user_id=receiver_user_id,
        origin_site_code=current_user.site.code,
        seal_verified=seal_verified,
        seal_no=seal_no.strip() or None,
        handover_time=parse_datetime_input(handover_time),
        notes=notes.strip() or None,
    )
    db.add(handover)
    db.flush()
    log_event(
        db,
        actor=current_user,
        entity_name="handover",
        record_id=handover.id,
        operation=EventOperation.INSERT,
        payload=serialize_model(handover),
    )
    refresh_projection_cache(db)
    db.commit()
    return redirect_to("/handovers", message="Handover recorded.")
