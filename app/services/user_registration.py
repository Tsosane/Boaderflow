from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import EventOperation, SiteCode, UserRole
from app.models import AppUser, Driver, Site
from app.security import hash_password
from app.services.audit import log_event, serialize_model


SITE_ROLE_OPTIONS: dict[str, tuple[UserRole, ...]] = {
    SiteCode.DEPOT_MSU.value: (UserRole.DEPOT_CONTROLLER, UserRole.YARD_CLERK, UserRole.DRIVER),
    SiteCode.BORDER_MB.value: (UserRole.BORDER_AGENT,),
    SiteCode.PORT_DBN.value: (UserRole.PORT_AGENT,),
    SiteCode.HUB_JHB.value: (UserRole.HUB_OPERATOR,),
    SiteCode.CTRL_TOWER.value: (UserRole.MANAGER,),
}


class RegistrationError(ValueError):
    """Raised when a user registration request is invalid."""


def allowed_roles_for_site(site_code: str, *, include_driver: bool = True) -> tuple[str, ...]:
    roles = SITE_ROLE_OPTIONS.get(site_code, ())
    if include_driver:
        return tuple(role.value for role in roles)
    return tuple(role.value for role in roles if role != UserRole.DRIVER)


def parse_licence_expiry(value: str) -> date:
    normalized = value.strip()
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return datetime.fromisoformat(normalized).date()


def register_site_user(
    db: Session,
    *,
    site: Site,
    actor: AppUser | None,
    full_name: str,
    email: str,
    password: str,
    role: str,
    licence_no: str = "",
    licence_expiry: str = "",
) -> AppUser:
    normalized_email = email.strip().lower()
    chosen_role = role.strip().upper()
    allowed_roles = allowed_roles_for_site(site.code, include_driver=True)

    if chosen_role not in allowed_roles:
        raise RegistrationError("That role is not valid for this site.")
    if db.scalar(select(AppUser.id).where(AppUser.email == normalized_email)):
        raise RegistrationError("A user with that email already exists.")

    user = AppUser(
        site_id=site.id,
        origin_site_code=site.code,
        full_name=full_name.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
        role=chosen_role,
    )
    db.add(user)
    db.flush()
    audit_actor = actor or user
    log_event(
        db,
        actor=audit_actor,
        entity_name="app_user",
        record_id=user.id,
        operation=EventOperation.INSERT,
        payload=serialize_model(user),
    )

    if chosen_role == UserRole.DRIVER.value:
        normalized_licence = licence_no.strip().upper()
        if not normalized_licence or not licence_expiry.strip():
            raise RegistrationError("Driver sign-up requires a licence number and licence expiry.")
        if db.scalar(select(Driver.id).where(Driver.licence_no == normalized_licence)):
            raise RegistrationError("A driver with that licence number already exists.")
        driver = Driver(
            user_id=user.id,
            origin_site_code=site.code,
            licence_no=normalized_licence,
            licence_expiry=parse_licence_expiry(licence_expiry),
        )
        db.add(driver)
        db.flush()
        log_event(
            db,
            actor=audit_actor,
            entity_name="driver",
            record_id=driver.id,
            operation=EventOperation.INSERT,
            payload=serialize_model(driver),
        )

    return user
