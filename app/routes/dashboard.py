from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import AppUser, Consignment, Container, EventLog, ReplicationIssue, Trip
from app.services.projections import load_container_states
from app.web import redirect_to, render_template


router = APIRouter(tags=["dashboard"])


@router.get("/")
def index(request: Request):
    if request.session.get("user_id"):
        return redirect_to("/dashboard")
    return redirect_to("/auth/login")


@router.get("/dashboard")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    container_states = load_container_states(db)[:8]
    metrics = {
        "consignments": db.scalar(select(func.count()).select_from(Consignment)) or 0,
        "containers": db.scalar(select(func.count()).select_from(Container)) or 0,
        "trips": db.scalar(select(func.count()).select_from(Trip)) or 0,
        "issues": db.scalar(select(func.count()).select_from(ReplicationIssue).where(ReplicationIssue.is_resolved.is_(False))) or 0,
    }
    recent_events = db.scalars(select(EventLog).order_by(EventLog.event_time.desc()).limit(8)).all()
    return render_template(
        request,
        "dashboard.html",
        {
            "metrics": metrics,
            "container_states": container_states,
            "recent_events": recent_events,
            "page_title": "Site Dashboard",
            "current_user": current_user,
        },
    )
