from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Site(TimestampMixin, Base):
    __tablename__ = "site"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    site_type: Mapped[str] = mapped_column(String(30), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AppUser(TimestampMixin, Base):
    __tablename__ = "app_user"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    site_id: Mapped[Any] = mapped_column(ForeignKey("site.id"), nullable=False, index=True)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    site: Mapped["Site"] = relationship()


class Client(TimestampMixin, Base):
    __tablename__ = "client"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(30))
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicle"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    site_id: Mapped[Any] = mapped_column(ForeignKey("site.id"), nullable=False)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    registration_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity_teu: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    site: Mapped["Site"] = relationship()


class Driver(Base):
    __tablename__ = "driver"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    user_id: Mapped[Any] = mapped_column(ForeignKey("app_user.id"), unique=True, nullable=False)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    licence_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    licence_expiry: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["AppUser"] = relationship()


class Consignment(TimestampMixin, Base):
    __tablename__ = "consignment"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    client_id: Mapped[Any] = mapped_column(ForeignKey("client.id"), nullable=False)
    origin_site_id: Mapped[Any] = mapped_column(ForeignKey("site.id"), nullable=False)
    destination_site_id: Mapped[Any] = mapped_column(ForeignKey("site.id"), nullable=False)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    reference_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[Any] = mapped_column(ForeignKey("app_user.id"), nullable=False)

    client: Mapped["Client"] = relationship()
    origin_site: Mapped["Site"] = relationship(foreign_keys=[origin_site_id])
    destination_site: Mapped["Site"] = relationship(foreign_keys=[destination_site_id])
    created_by: Mapped["AppUser"] = relationship(foreign_keys=[created_by_id])


class Container(TimestampMixin, Base):
    __tablename__ = "container"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    consignment_id: Mapped[Any] = mapped_column(ForeignKey("consignment.id"), nullable=False)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    container_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    container_type: Mapped[str] = mapped_column(String(30), nullable=False)
    seal_no: Mapped[str | None] = mapped_column(String(50))
    gross_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cargo_description: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[Any] = mapped_column(ForeignKey("app_user.id"), nullable=False)

    consignment: Mapped["Consignment"] = relationship()
    created_by: Mapped["AppUser"] = relationship()


class Trip(TimestampMixin, Base):
    __tablename__ = "trip"
    __table_args__ = (
        Index(
            "ux_trip_vehicle_active",
            "vehicle_id",
            unique=True,
            sqlite_where=text("status IN ('PLANNED', 'DEPARTED', 'IN_TRANSIT', 'ARRIVED')"),
            postgresql_where=text("status IN ('PLANNED', 'DEPARTED', 'IN_TRANSIT', 'ARRIVED')"),
        ),
        Index(
            "ux_trip_driver_active",
            "driver_id",
            unique=True,
            sqlite_where=text("status IN ('PLANNED', 'DEPARTED', 'IN_TRANSIT', 'ARRIVED')"),
            postgresql_where=text("status IN ('PLANNED', 'DEPARTED', 'IN_TRANSIT', 'ARRIVED')"),
        ),
    )

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    origin_site_id: Mapped[Any] = mapped_column(ForeignKey("site.id"), nullable=False)
    destination_site_id: Mapped[Any] = mapped_column(ForeignKey("site.id"), nullable=False)
    vehicle_id: Mapped[Any] = mapped_column(ForeignKey("vehicle.id"), nullable=False)
    driver_id: Mapped[Any] = mapped_column(ForeignKey("driver.id"), nullable=False)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    planned_departure: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[Any] = mapped_column(ForeignKey("app_user.id"), nullable=False)

    origin_site: Mapped["Site"] = relationship(foreign_keys=[origin_site_id])
    destination_site: Mapped["Site"] = relationship(foreign_keys=[destination_site_id])
    vehicle: Mapped["Vehicle"] = relationship()
    driver: Mapped["Driver"] = relationship()
    created_by: Mapped["AppUser"] = relationship()


class TripContainer(Base):
    __tablename__ = "trip_container"
    __table_args__ = (
        UniqueConstraint("trip_id", "container_id", name="uq_trip_container_pair"),
        Index(
            "ux_trip_container_active",
            "container_id",
            unique=True,
            sqlite_where=text("active_assignment = 1"),
            postgresql_where=text("active_assignment IS TRUE"),
        ),
    )

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    trip_id: Mapped[Any] = mapped_column(ForeignKey("trip.id"), nullable=False)
    container_id: Mapped[Any] = mapped_column(ForeignKey("container.id"), nullable=False)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by_id: Mapped[Any] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    active_assignment: Mapped[bool | None] = mapped_column(Boolean, default=True)

    trip: Mapped["Trip"] = relationship()
    container: Mapped["Container"] = relationship()
    assigned_by: Mapped["AppUser"] = relationship()


class Handover(Base):
    __tablename__ = "handover"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    trip_id: Mapped[Any] = mapped_column(ForeignKey("trip.id"), nullable=False)
    container_id: Mapped[Any] = mapped_column(ForeignKey("container.id"), nullable=False)
    from_site_id: Mapped[Any] = mapped_column(ForeignKey("site.id"), nullable=False)
    to_site_id: Mapped[Any] = mapped_column(ForeignKey("site.id"), nullable=False)
    sender_user_id: Mapped[Any] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    receiver_user_id: Mapped[Any] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    seal_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    seal_no: Mapped[str | None] = mapped_column(String(50))
    handover_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    trip: Mapped["Trip"] = relationship()
    container: Mapped["Container"] = relationship()
    from_site: Mapped["Site"] = relationship(foreign_keys=[from_site_id])
    to_site: Mapped["Site"] = relationship(foreign_keys=[to_site_id])
    sender_user: Mapped["AppUser"] = relationship(foreign_keys=[sender_user_id])
    receiver_user: Mapped["AppUser"] = relationship(foreign_keys=[receiver_user_id])


class Milestone(Base):
    __tablename__ = "milestone"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    trip_id: Mapped[Any] = mapped_column(ForeignKey("trip.id"), nullable=False)
    container_id: Mapped[Any] = mapped_column(ForeignKey("container.id"), nullable=False)
    site_id: Mapped[Any] = mapped_column(ForeignKey("site.id"), nullable=False)
    recorded_by_id: Mapped[Any] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    milestone_type: Mapped[str] = mapped_column(String(50), nullable=False)
    milestone_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    trip: Mapped["Trip"] = relationship()
    container: Mapped["Container"] = relationship()
    site: Mapped["Site"] = relationship()
    recorded_by: Mapped["AppUser"] = relationship()


class Incident(TimestampMixin, Base):
    __tablename__ = "incident"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    trip_id: Mapped[Any] = mapped_column(ForeignKey("trip.id"), nullable=False)
    container_id: Mapped[Any | None] = mapped_column(ForeignKey("container.id"))
    site_id: Mapped[Any] = mapped_column(ForeignKey("site.id"), nullable=False)
    reported_by_id: Mapped[Any] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    resolved_by_id: Mapped[Any | None] = mapped_column(ForeignKey("app_user.id"))
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    incident_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    incident_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    trip: Mapped["Trip"] = relationship()
    container: Mapped["Container"] = relationship()
    site: Mapped["Site"] = relationship()
    reported_by: Mapped["AppUser"] = relationship(foreign_keys=[reported_by_id])
    resolved_by: Mapped["AppUser"] = relationship(foreign_keys=[resolved_by_id])


class EventLog(Base):
    __tablename__ = "event_log"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    origin_site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(50), nullable=False)
    record_id: Mapped[Any] = mapped_column(SAUuid, nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(10), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    performed_by_id: Mapped[Any] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    performed_by: Mapped["AppUser"] = relationship()


class ReplicationIssue(TimestampMixin, Base):
    __tablename__ = "replication_issue"

    id: Mapped[Any] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    site_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    subscription_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BootstrapState(Base):
    __tablename__ = "bootstrap_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ContainerStateProjection(Base):
    __tablename__ = "container_state_projection"

    container_id: Mapped[Any] = mapped_column(SAUuid, primary_key=True)
    consignment_id: Mapped[Any] = mapped_column(SAUuid, nullable=False, index=True)
    container_no: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    consignment_ref: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    current_status: Mapped[str] = mapped_column(String(50), nullable=False)
    current_site_name: Mapped[str | None] = mapped_column(String(100))
    current_site_code: Mapped[str | None] = mapped_column(String(20), index=True)
    latest_milestone_type: Mapped[str | None] = mapped_column(String(50))
    latest_milestone_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_handover_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trip_id: Mapped[Any | None] = mapped_column(SAUuid, index=True)
    trip_status: Mapped[str | None] = mapped_column(String(30))
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
