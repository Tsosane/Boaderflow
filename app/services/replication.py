from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.config import Settings
from app.enums import ReplicationIssueType
from app.models import ReplicationIssue


def fetch_replication_snapshot(session: Session, settings: Settings) -> list[dict[str, Any]]:
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return [
            {
                "subname": subname,
                "worker_type": "unavailable",
                "pid": None,
                "received_lsn": None,
                "last_msg_receipt_time": None,
                "latest_end_lsn": None,
                "latest_end_time": None,
                "apply_error_count": 0,
                "sync_error_count": 0,
                "conflict_total": 0,
            }
            for subname in settings.subscription_names
        ]

    subscription_rows = session.execute(
        text(
            """
            SELECT DISTINCT ON (subname)
                subname,
                'subscription-worker' AS worker_type,
                pid,
                received_lsn::text AS received_lsn,
                last_msg_receipt_time,
                latest_end_lsn::text AS latest_end_lsn,
                latest_end_time
            FROM pg_stat_subscription
            ORDER BY subname, latest_end_time DESC NULLS LAST, pid DESC NULLS LAST
            """
        )
    ).mappings()

    stats_rows = session.execute(
        text(
            """
            SELECT
                subname,
                apply_error_count,
                sync_error_count,
                0 AS conflict_total
            FROM pg_stat_subscription_stats
            """
        )
    ).mappings()

    stats_by_name = {row["subname"]: dict(row) for row in stats_rows}
    snapshot: list[dict[str, Any]] = []
    for row in subscription_rows:
        merged = dict(row)
        merged.update(stats_by_name.get(row["subname"], {}))
        snapshot.append(merged)
    return snapshot


def upsert_replication_issues(session: Session, settings: Settings) -> list[ReplicationIssue]:
    try:
        snapshot = fetch_replication_snapshot(session, settings)
    except ProgrammingError:
        snapshot = []

    now = datetime.now(timezone.utc)
    issues: list[ReplicationIssue] = []

    for subname in settings.subscription_names:
        if not any(item["subname"] == subname for item in snapshot):
            issues.append(
                _record_issue(
                    session,
                    site_code=settings.site_code,
                    subscription_name=subname,
                    issue_type=ReplicationIssueType.SUBSCRIPTION_MISSING.value,
                    detail="Subscription not visible from pg_stat_subscription.",
                    seen_at=now,
                )
            )

    for item in snapshot:
        stale_cutoff = now - timedelta(seconds=settings.replication_stale_after_seconds)
        last_seen = item.get("last_msg_receipt_time")
        if last_seen and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        if item.get("apply_error_count", 0):
            issues.append(
                _record_issue(
                    session,
                    site_code=settings.site_code,
                    subscription_name=item["subname"],
                    issue_type=ReplicationIssueType.APPLY_ERROR.value,
                    detail=f"Apply errors recorded: {item['apply_error_count']}.",
                    seen_at=now,
                )
            )
        if item.get("sync_error_count", 0):
            issues.append(
                _record_issue(
                    session,
                    site_code=settings.site_code,
                    subscription_name=item["subname"],
                    issue_type=ReplicationIssueType.SYNC_ERROR.value,
                    detail=f"Initial sync errors recorded: {item['sync_error_count']}.",
                    seen_at=now,
                )
            )
        if item.get("conflict_total", 0):
            issues.append(
                _record_issue(
                    session,
                    site_code=settings.site_code,
                    subscription_name=item["subname"],
                    issue_type=ReplicationIssueType.CONFLICT.value,
                    detail=f"Logical replication conflicts recorded: {item['conflict_total']}.",
                    seen_at=now,
                )
            )
        if last_seen and last_seen < stale_cutoff:
            issues.append(
                _record_issue(
                    session,
                    site_code=settings.site_code,
                    subscription_name=item["subname"],
                    issue_type=ReplicationIssueType.STALE_SUBSCRIPTION.value,
                    detail=f"Last message was received at {last_seen.isoformat()}.",
                    seen_at=now,
                )
            )

    return issues


def unresolved_replication_issue_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(ReplicationIssue).where(ReplicationIssue.is_resolved.is_(False))) or 0


def _record_issue(
    session: Session,
    *,
    site_code: str,
    subscription_name: str,
    issue_type: str,
    detail: str,
    seen_at: datetime,
) -> ReplicationIssue:
    issue = session.scalar(
        select(ReplicationIssue).where(
            ReplicationIssue.site_code == site_code,
            ReplicationIssue.subscription_name == subscription_name,
            ReplicationIssue.issue_type == issue_type,
            ReplicationIssue.is_resolved.is_(False),
        )
    )
    if issue is None:
        issue = ReplicationIssue(
            site_code=site_code,
            subscription_name=subscription_name,
            issue_type=issue_type,
            detail=detail,
            last_seen_at=seen_at,
        )
        session.add(issue)
    else:
        issue.detail = detail
        issue.last_seen_at = seen_at
    return issue
