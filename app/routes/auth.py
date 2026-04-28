from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings
from app.dependencies import get_current_user, get_db
from app.enums import SiteCode
from app.models import AppUser, Site
from app.security import verify_password
from app.services.user_registration import RegistrationError, allowed_roles_for_site, register_site_user
from app.web import redirect_to, render_template


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
def login_form(request: Request):
    if request.session.get("user_id"):
        return redirect_to("/dashboard")
    settings: Settings = request.app.state.settings
    return render_template(
        request,
        "auth/login.html",
        {"allowed_roles": allowed_roles_for_site(settings.site_code, include_driver=True)},
    )


@router.get("/register")
def register_form(request: Request):
    if request.session.get("user_id"):
        return redirect_to("/dashboard")
    settings: Settings = request.app.state.settings
    return render_template(
        request,
        "auth/register.html",
        {
            "page_title": "Register Account",
            "allowed_roles": allowed_roles_for_site(settings.site_code, include_driver=True),
            "show_driver_fields": settings.site_code == SiteCode.DEPOT_MSU.value,
        },
    )


@router.post("/register")
def register_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    licence_no: str = Form(""),
    licence_expiry: str = Form(""),
    db: Session = Depends(get_db),
):
    settings: Settings = request.app.state.settings
    site = db.scalars(select(Site).where(Site.code == settings.site_code, Site.is_active.is_(True))).first()
    if site is None:
        return redirect_to("/auth/register", error="This site is not ready for user registration.")

    try:
        user = register_site_user(
            db,
            site=site,
            actor=None,
            full_name=full_name,
            email=email,
            password=password,
            role=role,
            licence_no=licence_no,
            licence_expiry=licence_expiry,
        )
        db.commit()
    except RegistrationError as exc:
        db.rollback()
        return redirect_to("/auth/register", error=str(exc))

    request.session["user_id"] = str(user.id)
    return redirect_to("/dashboard", message=f"Welcome to BorderFlow, {user.full_name}.")


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    settings: Settings = request.app.state.settings
    statement = select(AppUser).options(joinedload(AppUser.site)).where(
        AppUser.email == email.strip().lower(),
        AppUser.is_active.is_(True),
    )
    user = db.scalars(statement).first()
    if user is None or not verify_password(password, user.password_hash):
        return redirect_to("/auth/login", error="Invalid email or password.")

    if settings.site_code == settings.control_tower_site_code:
        if user.role != "MANAGER":
            return redirect_to("/auth/login", error="Only the manager can log into the Control Tower.")
    elif user.site.code != settings.site_code:
        return redirect_to("/auth/login", error="This user belongs to a different site.")

    request.session["user_id"] = str(user.id)
    return redirect_to("/dashboard", message=f"Welcome back, {user.full_name}.")


@router.post("/logout")
def logout(request: Request, current_user: AppUser = Depends(get_current_user)):
    request.session.clear()
    return redirect_to("/auth/login", message=f"Signed out {current_user.full_name}.")
