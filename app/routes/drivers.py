from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_roles
from app.enums import UserRole
from app.models import AppUser, Driver
from app.services.user_registration import RegistrationError, register_site_user
from app.web import redirect_to, render_template


router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("")
def list_drivers(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    drivers = db.scalars(
        select(Driver)
        .options(joinedload(Driver.user))
        .where(Driver.origin_site_code == current_user.site.code)
        .order_by(Driver.created_at.desc())
    ).all()
    return render_template(
        request,
        "drivers/index.html",
        {"drivers": drivers, "page_title": "Drivers", "current_user": current_user},
    )


@router.get("/new")
def new_driver_form(
    request: Request,
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    return render_template(
        request,
        "drivers/new.html",
        {"page_title": "Register Driver", "current_user": current_user, "default_password": request.app.state.settings.seed_password},
    )


@router.post("")
def create_driver(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    licence_no: str = Form(...),
    licence_expiry: str = Form(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(UserRole.DEPOT_CONTROLLER.value)),
):
    try:
        driver_user = register_site_user(
            db,
            site=current_user.site,
            actor=current_user,
            full_name=full_name,
            email=email,
            password=password,
            role=UserRole.DRIVER.value,
            licence_no=licence_no,
            licence_expiry=licence_expiry,
        )
        db.commit()
    except RegistrationError as exc:
        db.rollback()
        return redirect_to("/drivers/new", error=str(exc))
    return redirect_to("/drivers", message=f"Driver {driver_user.full_name} registered.")
