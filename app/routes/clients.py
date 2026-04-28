from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_roles
from app.enums import EventOperation, UserRole
from app.models import AppUser, Client
from app.services.audit import log_event, serialize_model
from app.web import redirect_to, render_template


router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("")
def list_clients(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    clients = db.scalars(
        select(Client)
        .where(Client.origin_site_code == current_user.site.code)
        .order_by(Client.company_name)
    ).all()
    return render_template(
        request,
        "clients/index.html",
        {"clients": clients, "page_title": "Clients", "current_user": current_user},
    )


@router.get("/new")
def new_client_form(
    request: Request,
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    return render_template(
        request,
        "clients/new.html",
        {"page_title": "Register Client", "current_user": current_user},
    )


@router.post("")
def create_client(
    request: Request,
    company_name: str = Form(...),
    contact_name: str = Form(...),
    contact_email: str = Form(...),
    contact_phone: str = Form(""),
    country: str = Form(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    if db.scalar(select(Client.id).where(Client.contact_email == contact_email.strip().lower())):
        return redirect_to("/clients/new", error="A client with that contact email already exists.")

    client = Client(
        origin_site_code=current_user.origin_site_code,
        company_name=company_name.strip(),
        contact_name=contact_name.strip(),
        contact_email=contact_email.strip().lower(),
        contact_phone=contact_phone.strip() or None,
        country=country.strip(),
    )
    db.add(client)
    db.flush()
    log_event(
        db,
        actor=current_user,
        entity_name="client",
        record_id=client.id,
        operation=EventOperation.INSERT,
        payload=serialize_model(client),
    )
    db.commit()
    return redirect_to("/clients", message=f"Client {client.company_name} registered.")
