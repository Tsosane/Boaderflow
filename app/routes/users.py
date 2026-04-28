from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_roles
from app.enums import UserRole
from app.models import AppUser
from app.services.user_registration import RegistrationError, allowed_roles_for_site, register_site_user
from app.web import redirect_to, render_template


router = APIRouter(prefix="/users", tags=["users"])


USER_MANAGEMENT_ROLES = (
    UserRole.DEPOT_CONTROLLER.value,
    UserRole.BORDER_AGENT.value,
    UserRole.PORT_AGENT.value,
    UserRole.HUB_OPERATOR.value,
    UserRole.MANAGER.value,
)


@router.get("")
def list_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(*USER_MANAGEMENT_ROLES)),
):
    users = db.scalars(
        select(AppUser)
        .where(AppUser.site_id == current_user.site_id)
        .order_by(AppUser.created_at.desc())
    ).all()
    return render_template(
        request,
        "users/index.html",
        {
            "users": users,
            "allowed_roles": allowed_roles_for_site(current_user.site.code, include_driver=False),
            "page_title": "Site Users",
            "current_user": current_user,
        },
    )


@router.get("/new")
def new_user_form(
    request: Request,
    current_user: AppUser = Depends(require_roles(*USER_MANAGEMENT_ROLES)),
):
    return render_template(
        request,
        "users/new.html",
        {
            "allowed_roles": allowed_roles_for_site(current_user.site.code, include_driver=False),
            "page_title": "Register Site User",
            "current_user": current_user,
        },
    )


@router.post("")
def create_user(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_roles(*USER_MANAGEMENT_ROLES)),
):
    try:
        user = register_site_user(
            db,
            site=current_user.site,
            actor=current_user,
            full_name=full_name,
            email=email,
            password=password,
            role=role,
        )
        db.commit()
    except RegistrationError as exc:
        db.rollback()
        return redirect_to("/users/new", error=str(exc))
    return redirect_to("/users", message=f"User {user.full_name} registered.")
