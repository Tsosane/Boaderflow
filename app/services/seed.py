from __future__ import annotations

from datetime import date
from uuid import NAMESPACE_DNS, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.enums import SiteCode, SiteType, UserRole
from app.models import AppUser, Client, Driver, Site, Vehicle
from app.security import hash_password


def _fixed_uuid(label: str):
    return uuid5(NAMESPACE_DNS, f"borderflow::{label}")


def seed_demo_data(session: Session, settings: Settings) -> None:
    sites = {item.code: item for item in session.scalars(select(Site)).all()}
    for spec in _site_specs():
        site = sites.get(spec["code"])
        if site is None:
            site = Site(id=spec["id"], **{key: value for key, value in spec.items() if key != "id"})
            session.add(site)
            session.flush()
            sites[site.code] = site
        else:
            site.name = spec["name"]
            site.site_type = spec["site_type"]
            site.location = spec["location"]
            site.country = spec["country"]
            site.is_active = True

    if settings.seed_scope == "none":
        return

    password_hash = hash_password(settings.seed_password)
    for spec in _user_specs(password_hash):
        user = session.scalar(select(AppUser).where(AppUser.email == spec["email"]))
        if user is None:
            user = AppUser(id=spec["id"], **{key: value for key, value in spec.items() if key != "id"})
            session.add(user)
        else:
            user.site_id = spec["site_id"]
            user.origin_site_code = spec["origin_site_code"]
            user.full_name = spec["full_name"]
            user.role = spec["role"]
            user.is_active = True
        if settings.seed_scope == "all":
            user.password_hash = password_hash
    session.flush()

    if settings.seed_scope in {"all", "depot_only"}:
        _ensure_driver(session)
        _ensure_vehicle(session, sites[SiteCode.DEPOT_MSU.value].id)
        _ensure_client(session)


def _site_specs() -> list[dict[str, object]]:
    return [
        {
            "id": _fixed_uuid("site-depot"),
            "code": SiteCode.DEPOT_MSU.value,
            "name": "Maseru Depot",
            "site_type": SiteType.DEPOT.value,
            "location": "Maseru, Lesotho",
            "country": "Lesotho",
        },
        {
            "id": _fixed_uuid("site-border"),
            "code": SiteCode.BORDER_MB.value,
            "name": "Maseru Bridge Border Post",
            "site_type": SiteType.BORDER_POST.value,
            "location": "Maseru Bridge",
            "country": "Lesotho / South Africa",
        },
        {
            "id": _fixed_uuid("site-port"),
            "code": SiteCode.PORT_DBN.value,
            "name": "Durban Port Agent",
            "site_type": SiteType.PORT_AGENT.value,
            "location": "Durban",
            "country": "South Africa",
        },
        {
            "id": _fixed_uuid("site-hub"),
            "code": SiteCode.HUB_JHB.value,
            "name": "Johannesburg Destination Hub",
            "site_type": SiteType.DESTINATION_HUB.value,
            "location": "Johannesburg",
            "country": "South Africa",
        },
        {
            "id": _fixed_uuid("site-control"),
            "code": SiteCode.CTRL_TOWER.value,
            "name": "Control Tower",
            "site_type": SiteType.CONTROL_TOWER.value,
            "location": "Remote",
            "country": "Lesotho",
        },
    ]


def _user_specs(password_hash: str) -> list[dict[str, object]]:
    return [
        {
            "id": _fixed_uuid("user-depot-controller"),
            "site_id": _fixed_uuid("site-depot"),
            "origin_site_code": SiteCode.DEPOT_MSU.value,
            "full_name": "Mpho Tsosane",
            "email": "depot.controller@borderflow.local",
            "password_hash": password_hash,
            "role": UserRole.DEPOT_CONTROLLER.value,
        },
        {
            "id": _fixed_uuid("user-border-agent"),
            "site_id": _fixed_uuid("site-border"),
            "origin_site_code": SiteCode.DEPOT_MSU.value,
            "full_name": "Palesa Border Agent",
            "email": "border.agent@borderflow.local",
            "password_hash": password_hash,
            "role": UserRole.BORDER_AGENT.value,
        },
        {
            "id": _fixed_uuid("user-port-agent"),
            "site_id": _fixed_uuid("site-port"),
            "origin_site_code": SiteCode.DEPOT_MSU.value,
            "full_name": "Thabo Port Agent",
            "email": "port.agent@borderflow.local",
            "password_hash": password_hash,
            "role": UserRole.PORT_AGENT.value,
        },
        {
            "id": _fixed_uuid("user-hub-operator"),
            "site_id": _fixed_uuid("site-hub"),
            "origin_site_code": SiteCode.DEPOT_MSU.value,
            "full_name": "Naledi Hub Operator",
            "email": "hub.operator@borderflow.local",
            "password_hash": password_hash,
            "role": UserRole.HUB_OPERATOR.value,
        },
        {
            "id": _fixed_uuid("user-manager"),
            "site_id": _fixed_uuid("site-control"),
            "origin_site_code": SiteCode.DEPOT_MSU.value,
            "full_name": "Kopano Compliance Manager",
            "email": "manager@borderflow.local",
            "password_hash": password_hash,
            "role": UserRole.MANAGER.value,
        },
        {
            "id": _fixed_uuid("user-driver"),
            "site_id": _fixed_uuid("site-depot"),
            "origin_site_code": SiteCode.DEPOT_MSU.value,
            "full_name": "Neo Driver",
            "email": "driver@borderflow.local",
            "password_hash": password_hash,
            "role": UserRole.DRIVER.value,
        },
    ]


def _ensure_driver(session: Session) -> None:
    driver = session.scalar(select(Driver).where(Driver.licence_no == "LS-CDL-22001"))
    if driver is None:
        session.add(
            Driver(
                id=_fixed_uuid("driver-record"),
                user_id=_fixed_uuid("user-driver"),
                origin_site_code=SiteCode.DEPOT_MSU.value,
                licence_no="LS-CDL-22001",
                licence_expiry=date(2028, 12, 31),
            )
        )
    else:
        driver.user_id = _fixed_uuid("user-driver")
        driver.origin_site_code = SiteCode.DEPOT_MSU.value
        driver.licence_expiry = date(2028, 12, 31)
        driver.is_active = True


def _ensure_vehicle(session: Session, site_id) -> None:
    vehicle = session.scalar(select(Vehicle).where(Vehicle.registration_no == "BFL-401-LS"))
    if vehicle is None:
        session.add(
            Vehicle(
                id=_fixed_uuid("vehicle-demo"),
                site_id=site_id,
                origin_site_code=SiteCode.DEPOT_MSU.value,
                registration_no="BFL-401-LS",
                vehicle_type="FLATBED",
                capacity_teu=2,
            )
        )
    else:
        vehicle.site_id = site_id
        vehicle.origin_site_code = SiteCode.DEPOT_MSU.value
        vehicle.vehicle_type = "FLATBED"
        vehicle.capacity_teu = 2
        vehicle.is_active = True


def _ensure_client(session: Session) -> None:
    client = session.scalar(select(Client).where(Client.contact_email == "client@acmetextiles.example"))
    if client is None:
        session.add(
            Client(
                id=_fixed_uuid("client-demo"),
                origin_site_code=SiteCode.DEPOT_MSU.value,
                company_name="Acme Textiles",
                contact_name="Lerato Khau",
                contact_email="client@acmetextiles.example",
                contact_phone="+266-5000-1000",
                country="Lesotho",
            )
        )
    else:
        client.origin_site_code = SiteCode.DEPOT_MSU.value
        client.company_name = "Acme Textiles"
        client.contact_name = "Lerato Khau"
        client.contact_phone = "+266-5000-1000"
        client.country = "Lesotho"
        client.is_active = True
