from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.services.rules import BusinessRuleError


def parse_datetime_input(value: str) -> datetime:
    if not value:
        raise BusinessRuleError("A date and time value is required.")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_decimal_input(value: str | None) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(value)

