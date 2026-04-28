from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_roles
from app.enums import EventOperation, UserRole
from app.models import AppUser, Client, Consignment, Site
from app.services.audit import log_event, serialize_model
from app.web import redirect_to, render_template


router = APIRouter(prefix="/consignments", tags=["consignments"])


@router.get("")
def list_consignments(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    consignments = db.scalars(
        select(Consignment)
        .options(
            joinedload(Consignment.client),
            joinedload(Consignment.origin_site),
            joinedload(Consignment.destination_site),
        )
        .order_by(Consignment.created_at.desc())
    ).all()
    return render_template(
        request,
        "consignments/index.html",
        {"consignments": consignments, "page_title": "Consignments", "current_user": current_user},
    )


@router.get("/new")
def new_consignment_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    clients = db.scalars(select(Client).where(Client.is_active.is_(True)).order_by(Client.company_name)).all()
    destinations = db.scalars(
        select(Site).where(Site.code.not_in([current_user.site.code, request.app.state.settings.control_tower_site_code]))
    ).all()
    return render_template(
        request,
        "consignments/new.html",
        {"clients": clients, "destinations": destinations, "page_title": "New Consignment", "current_user": current_user},
    )


@router.post("")
def create_consignment(
    request: Request,
    client_id: str = Form(...),
    destination_site_id: str = Form(...),
    reference_no: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    consignment = Consignment(
        client_id=client_id,
        origin_site_id=current_user.site_id,
        destination_site_id=destination_site_id,
        origin_site_code=current_user.origin_site_code,
        reference_no=reference_no.strip().upper(),
        notes=notes.strip() or None,
        created_by_id=current_user.id,
    )
    db.add(consignment)
    db.flush()
    log_event(
        db,
        actor=current_user,
        entity_name="consignment",
        record_id=consignment.id,
        operation=EventOperation.INSERT,
        payload=serialize_model(consignment),
    )
    db.commit()
    return redirect_to("/consignments", message=f"Consignment {consignment.reference_no} created.")

