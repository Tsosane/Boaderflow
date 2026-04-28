from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_roles
from app.enums import EventOperation, UserRole
from app.models import AppUser, Consignment, Container
from app.routes.helpers import parse_decimal_input
from app.services.audit import log_event, serialize_model
from app.services.projections import refresh_projection_cache
from app.web import redirect_to, render_template


router = APIRouter(prefix="/containers", tags=["containers"])


@router.get("")
def list_containers(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    containers = db.scalars(
        select(Container)
        .options(joinedload(Container.consignment))
        .order_by(Container.created_at.desc())
    ).all()
    return render_template(
        request,
        "containers/index.html",
        {"containers": containers, "page_title": "Containers", "current_user": current_user},
    )


@router.get("/new")
def new_container_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    consignments = db.scalars(select(Consignment).order_by(Consignment.created_at.desc())).all()
    return render_template(
        request,
        "containers/new.html",
        {"consignments": consignments, "page_title": "Register Container", "current_user": current_user},
    )


@router.post("")
def create_container(
    request: Request,
    consignment_id: str = Form(...),
    container_no: str = Form(...),
    container_type: str = Form(...),
    seal_no: str = Form(""),
    gross_weight_kg: str = Form(""),
    cargo_description: str = Form(""),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    container = Container(
        consignment_id=consignment_id,
        origin_site_code=current_user.origin_site_code,
        container_no=container_no.strip().upper(),
        container_type=container_type.strip().upper(),
        seal_no=seal_no.strip() or None,
        gross_weight_kg=parse_decimal_input(gross_weight_kg),
        cargo_description=cargo_description.strip() or None,
        created_by_id=current_user.id,
    )
    db.add(container)
    db.flush()
    log_event(
        db,
        actor=current_user,
        entity_name="container",
        record_id=container.id,
        operation=EventOperation.INSERT,
        payload=serialize_model(container),
    )
    refresh_projection_cache(db)
    db.commit()
    return redirect_to("/containers", message=f"Container {container.container_no} registered.")

