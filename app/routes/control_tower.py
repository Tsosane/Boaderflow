from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_roles
from app.enums import UserRole
from app.models import AppUser, EventLog, ReplicationIssue
from app.services.projections import load_container_states
from app.services.replication import fetch_replication_snapshot
from app.web import render_template


router = APIRouter(prefix="/control-tower", tags=["control-tower"])


@router.get("/containers")
def control_tower_containers(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.MANAGER.value)),
):
    container_states = load_container_states(db)
    recent_events = db.scalars(select(EventLog).order_by(EventLog.event_time.desc()).limit(12)).all()
    return render_template(
        request,
        "control_tower/containers.html",
        {
            "container_states": container_states,
            "recent_events": recent_events,
            "page_title": "Control Tower Containers",
            "current_user": current_user,
        },
    )


@router.get("/conflicts")
def control_tower_conflicts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.MANAGER.value)),
):
    issues = db.scalars(select(ReplicationIssue).order_by(ReplicationIssue.last_seen_at.desc())).all()
    return render_template(
        request,
        "control_tower/conflicts.html",
        {"issues": issues, "page_title": "Replication Conflicts & Issues", "current_user": current_user},
    )


@router.get("/replication")
def control_tower_replication(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.MANAGER.value)),
):
    snapshot = fetch_replication_snapshot(db, request.app.state.settings)
    return render_template(
        request,
        "control_tower/replication.html",
        {"snapshot": snapshot, "page_title": "Replication Health", "current_user": current_user},
    )
