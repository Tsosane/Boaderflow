from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.enums import MilestoneType, SiteCode, TripStatus, UserRole
from app.models import AppUser, Incident, Milestone, Trip, TripContainer


class BusinessRuleError(ValueError):
    """Raised when a business invariant would be broken."""


MILESTONE_ORDER: dict[MilestoneType, int] = {
    MilestoneType.DEPARTED: 10,
    MilestoneType.ARRIVED: 20,
    MilestoneType.QUEUED: 30,
    MilestoneType.CLEARED: 40,
    MilestoneType.GATE_IN: 50,
    MilestoneType.PORT_CLEARED: 60,
    MilestoneType.RELEASED: 70,
    MilestoneType.DELIVERED: 80,
}

SITE_MILESTONES: dict[SiteCode, tuple[MilestoneType, ...]] = {
    SiteCode.DEPOT_MSU: (),
    SiteCode.BORDER_MB: (MilestoneType.ARRIVED, MilestoneType.QUEUED, MilestoneType.CLEARED),
    SiteCode.PORT_DBN: (MilestoneType.GATE_IN, MilestoneType.PORT_CLEARED, MilestoneType.RELEASED),
    SiteCode.HUB_JHB: (MilestoneType.DELIVERED,),
    SiteCode.CTRL_TOWER: (),
}


def ensure_aware_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def ensure_distinct_sites(from_site_id: object, to_site_id: object) -> None:
    if from_site_id == to_site_id:
        raise BusinessRuleError("A handover must move between two different sites.")


def ensure_container_not_on_active_trip(session: Session, container_id: object) -> None:
    statement: Select[tuple[TripContainer]] = (
        select(TripContainer)
        .join(Trip, Trip.id == TripContainer.trip_id)
        .where(
            TripContainer.container_id == container_id,
            TripContainer.active_assignment.is_(True),
            Trip.status.in_(active_trip_statuses()),
        )
    )
    if session.scalars(statement).first():
        raise BusinessRuleError("This container is already assigned to an active trip.")


def ensure_vehicle_not_on_active_trip(session: Session, vehicle_id: object) -> None:
    statement = select(Trip.id).where(Trip.vehicle_id == vehicle_id, Trip.status.in_(active_trip_statuses()))
    if session.scalar(statement) is not None:
        raise BusinessRuleError("This vehicle is already assigned to an active trip.")


def ensure_driver_not_on_active_trip(session: Session, driver_id: object) -> None:
    statement = select(Trip.id).where(Trip.driver_id == driver_id, Trip.status.in_(active_trip_statuses()))
    if session.scalar(statement) is not None:
        raise BusinessRuleError("This driver is already assigned to an active trip.")


def active_trip_statuses() -> tuple[str, ...]:
    return (
        TripStatus.PLANNED.value,
        TripStatus.DEPARTED.value,
        TripStatus.IN_TRANSIT.value,
        TripStatus.ARRIVED.value,
    )


def allowed_milestones_for_site(site_code: str) -> tuple[MilestoneType, ...]:
    try:
        return SITE_MILESTONES[SiteCode(site_code)]
    except Exception as exc:  # pragma: no cover - defensive
        raise BusinessRuleError(f"Unknown site code {site_code!r}.") from exc


def latest_milestone(session: Session, trip_id: object, container_id: object) -> Milestone | None:
    statement = (
        select(Milestone)
        .where(Milestone.trip_id == trip_id, Milestone.container_id == container_id)
        .order_by(Milestone.milestone_time.desc(), Milestone.created_at.desc())
    )
    return session.scalars(statement).first()


def ensure_milestone_allowed(
    session: Session,
    *,
    trip_id: object,
    container_id: object,
    milestone_type: MilestoneType,
    site_code: str,
) -> None:
    allowed = allowed_milestones_for_site(site_code)
    if milestone_type not in allowed:
        allowed_labels = ", ".join(item.value for item in allowed) or "none"
        raise BusinessRuleError(f"{site_code} can only record these milestones: {allowed_labels}.")

    previous = latest_milestone(session, trip_id, container_id)
    if previous is None:
        raise BusinessRuleError("A container must be departed from the depot before site milestones can be recorded.")

    previous_type = MilestoneType(previous.milestone_type)
    if MILESTONE_ORDER[milestone_type] != MILESTONE_ORDER[previous_type] + 10:
        raise BusinessRuleError(
            f"Milestones must move in order. Latest milestone is {previous_type.value}, so "
            f"{milestone_type.value} is not the next valid step."
        )


def user_can_access_site(user: AppUser, current_site_code: str, control_tower_site_code: str) -> bool:
    if current_site_code == control_tower_site_code:
        return user.role == UserRole.MANAGER.value
    return user.site.code == current_site_code or user.role == UserRole.MANAGER.value


def user_has_role(user: AppUser, roles: Iterable[str]) -> bool:
    return user.role in set(roles)


def ensure_incident_can_be_resolved(user: AppUser, incident: Incident) -> None:
    if incident.origin_site_code != user.site.code:
        raise BusinessRuleError("Incidents can only be resolved by the site that created them in this MVP.")
