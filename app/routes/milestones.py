from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_roles
from app.enums import EventOperation, MilestoneType, SiteCode, UserRole
from app.models import AppUser, Milestone, TripContainer
from app.routes.helpers import parse_datetime_input
from app.services.audit import log_event, serialize_model
from app.services.projections import refresh_projection_cache
from app.services.rules import BusinessRuleError, allowed_milestones_for_site, ensure_milestone_allowed
from app.web import redirect_to, render_template


router = APIRouter(prefix="/milestones", tags=["milestones"])


SITE_ROLE_MAP = {
    SiteCode.BORDER_MB.value: (UserRole.BORDER_AGENT.value,),
    SiteCode.PORT_DBN.value: (UserRole.PORT_AGENT.value,),
    SiteCode.HUB_JHB.value: (UserRole.HUB_OPERATOR.value,),
}


def _site_roles_for_request(request: Request) -> tuple[str, ...]:
    return SITE_ROLE_MAP.get(request.app.state.settings.site_code, ())


@router.get("")
def list_milestones(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.BORDER_AGENT.value, UserRole.PORT_AGENT.value, UserRole.HUB_OPERATOR.value)),
):
    milestones = db.scalars(
        select(Milestone)
        .options(joinedload(Milestone.container), joinedload(Milestone.trip), joinedload(Milestone.site))
        .where(Milestone.origin_site_code == current_user.site.code)
        .order_by(Milestone.milestone_time.desc())
    ).all()
    return render_template(
        request,
        "milestones/index.html",
        {"milestones": milestones, "page_title": "Milestones", "current_user": current_user},
    )


@router.get("/new")
def new_milestone_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.BORDER_AGENT.value, UserRole.PORT_AGENT.value, UserRole.HUB_OPERATOR.value)),
):
    assignments = db.scalars(
        select(TripContainer)
        .options(joinedload(TripContainer.trip), joinedload(TripContainer.container))
        .where(TripContainer.active_assignment.is_(True))
        .order_by(TripContainer.assigned_at.desc())
    ).all()
    allowed = allowed_milestones_for_site(request.app.state.settings.site_code)
    return render_template(
        request,
        "milestones/new.html",
        {"assignments": assignments, "allowed_milestones": allowed, "page_title": "Record Milestone", "current_user": current_user},
    )


@router.post("")
def create_milestone(
    request: Request,
    trip_id: str = Form(...),
    container_id: str = Form(...),
    milestone_type: str = Form(...),
    milestone_time: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.BORDER_AGENT.value, UserRole.PORT_AGENT.value, UserRole.HUB_OPERATOR.value)),
):
    chosen_type = MilestoneType(milestone_type)
    try:
        ensure_milestone_allowed(
            db,
            trip_id=trip_id,
            container_id=container_id,
            milestone_type=chosen_type,
            site_code=request.app.state.settings.site_code,
        )
    except BusinessRuleError as exc:
        db.rollback()
        return redirect_to("/milestones/new", error=str(exc))

    milestone = Milestone(
        trip_id=trip_id,
        container_id=container_id,
        site_id=current_user.site_id,
        recorded_by_id=current_user.id,
        origin_site_code=current_user.site.code,
        milestone_type=chosen_type.value,
        milestone_time=parse_datetime_input(milestone_time),
        notes=notes.strip() or None,
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

    refresh_projection_cache(db)
    db.commit()
    return redirect_to("/milestones", message=f"{chosen_type.value} recorded.")
