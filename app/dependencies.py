from __future__ import annotations

from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import AppUser
from app.services.rules import user_can_access_site


def get_db(request: Request):
    session_factory = request.app.state.session_factory
    session: Session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> AppUser:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )
    statement = select(AppUser).options(joinedload(AppUser.site)).where(
        AppUser.id == UUID(user_id), AppUser.is_active.is_(True)
    )
    user = db.scalars(statement).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )
    return user


def require_roles(*roles: str) -> Callable:
    def dependency(request: Request, current_user: AppUser = Depends(get_current_user)) -> AppUser:
        settings = request.app.state.settings
        if not user_can_access_site(current_user, settings.site_code, settings.control_tower_site_code):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this site.")
        if roles and current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action is not allowed.")
        return current_user

    return dependency
