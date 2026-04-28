from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import ContainerStateProjection


VIEW_NAME = "container_current_state_v"


VIEW_SQL = f"""
CREATE VIEW {VIEW_NAME} AS
WITH latest_milestone AS (
    SELECT
        m.*,
        ROW_NUMBER() OVER (
            PARTITION BY m.container_id
            ORDER BY m.milestone_time DESC, m.created_at DESC
        ) AS rn
    FROM milestone AS m
),
latest_handover AS (
    SELECT
        h.*,
        ROW_NUMBER() OVER (
            PARTITION BY h.container_id
            ORDER BY h.handover_time DESC, h.created_at DESC
        ) AS rn
    FROM handover AS h
),
active_assignment AS (
    SELECT
        tc.container_id,
        tc.trip_id
    FROM trip_container AS tc
    WHERE tc.active_assignment IS TRUE
)
SELECT
    c.id AS container_id,
    c.consignment_id AS consignment_id,
    c.container_no AS container_no,
    cons.reference_no AS consignment_ref,
    COALESCE(lm.milestone_type, 'REGISTERED') AS current_status,
    current_site.code AS current_site_code,
    current_site.name AS current_site_name,
    lm.milestone_type AS latest_milestone_type,
    lm.milestone_time AS latest_milestone_time,
    lh.handover_time AS last_handover_time,
    aa.trip_id AS trip_id,
    CASE
        WHEN lm.milestone_type = 'DELIVERED' THEN 'COMPLETED'
        WHEN lm.milestone_type = 'DEPARTED' THEN 'DEPARTED'
        WHEN lm.milestone_type IS NOT NULL THEN 'IN_TRANSIT'
        ELSE t.status
    END AS trip_status
FROM container AS c
JOIN consignment AS cons ON cons.id = c.consignment_id
LEFT JOIN latest_milestone AS lm ON lm.container_id = c.id AND lm.rn = 1
LEFT JOIN latest_handover AS lh ON lh.container_id = c.id AND lh.rn = 1
LEFT JOIN active_assignment AS aa ON aa.container_id = c.id
LEFT JOIN trip AS t ON t.id = aa.trip_id
LEFT JOIN site AS current_site
    ON current_site.id = COALESCE(
        lh.to_site_id,
        lm.site_id,
        cons.origin_site_id
    );
"""


def ensure_projection_view(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text(f"DROP VIEW IF EXISTS {VIEW_NAME}"))
        connection.execute(text(VIEW_SQL))


def refresh_projection_cache(session: Session) -> None:
    rows = session.execute(text(f"SELECT * FROM {VIEW_NAME} ORDER BY container_no")).mappings().all()
    session.execute(delete(ContainerStateProjection))

    refreshed_at = datetime.now(timezone.utc)
    for row in rows:
        projection = ContainerStateProjection(
            container_id=_as_uuid(row["container_id"]),
            consignment_id=_as_uuid(row["consignment_id"]),
            container_no=row["container_no"],
            consignment_ref=row["consignment_ref"],
            current_status=row["current_status"],
            current_site_code=row["current_site_code"],
            current_site_name=row["current_site_name"],
            latest_milestone_type=row["latest_milestone_type"],
            latest_milestone_time=_as_datetime(row["latest_milestone_time"]),
            last_handover_time=_as_datetime(row["last_handover_time"]),
            trip_id=_as_uuid(row["trip_id"]),
            trip_status=row["trip_status"],
            refreshed_at=refreshed_at,
        )
        session.add(projection)


def load_container_states(session: Session) -> list[dict[str, Any]]:
    rows = (
        session.query(ContainerStateProjection)
        .order_by(ContainerStateProjection.latest_milestone_time.desc().nullslast(), ContainerStateProjection.container_no)
        .all()
    )
    return [
        {
            "container_id": row.container_id,
            "consignment_id": row.consignment_id,
            "container_no": row.container_no,
            "consignment_ref": row.consignment_ref,
            "current_status": row.current_status,
            "current_site_code": row.current_site_code,
            "current_site_name": row.current_site_name,
            "latest_milestone_type": row.latest_milestone_type,
            "latest_milestone_time": row.latest_milestone_time,
            "last_handover_time": row.last_handover_time,
            "trip_id": row.trip_id,
            "trip_status": row.trip_status,
            "refreshed_at": row.refreshed_at,
        }
        for row in rows
    ]


def _as_uuid(value: Any):
    if value in (None, ""):
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _as_datetime(value: Any):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
