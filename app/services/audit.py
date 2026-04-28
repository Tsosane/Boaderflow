from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.enums import EventOperation
from app.models import AppUser, EventLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date, UUID, Decimal)):
        return str(value)
    return value


def serialize_model(instance: Any) -> dict[str, Any]:
    mapper = inspect(instance.__class__)
    payload: dict[str, Any] = {}
    for attr in mapper.columns:
        payload[attr.key] = _jsonable(getattr(instance, attr.key))
    return payload


def log_event(
    session: Session,
    *,
    actor: AppUser,
    entity_name: str,
    record_id: Any,
    operation: EventOperation,
    payload: dict[str, Any],
) -> EventLog:
    event = EventLog(
        origin_site_code=actor.origin_site_code,
        entity_name=entity_name,
        record_id=record_id,
        operation=operation.value,
        payload=payload,
        performed_by_id=actor.id,
    )
    session.add(event)
    return event

