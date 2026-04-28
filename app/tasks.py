from __future__ import annotations

from app.bootstrap import bootstrap_database
from app.celery_app import celery_app
from app.config import get_settings
from app.database import build_engine, build_session_factory, session_scope
from app.services.projections import refresh_projection_cache
from app.services.replication import upsert_replication_issues


settings = get_settings()
engine = build_engine(settings.database_url)
session_factory = build_session_factory(engine)


@celery_app.task(name="app.tasks.bootstrap_site_task")
def bootstrap_site_task() -> str:
    bootstrap_database(engine, session_factory, settings)
    return f"Bootstrapped {settings.site_code}"


@celery_app.task(name="app.tasks.refresh_projection_cache_task")
def refresh_projection_cache_task() -> str:
    with session_scope(session_factory) as session:
        refresh_projection_cache(session)
    return "Projection cache refreshed"


@celery_app.task(name="app.tasks.poll_replication_health_task")
def poll_replication_health_task() -> str:
    with session_scope(session_factory) as session:
        upsert_replication_issues(session, settings)
    return "Replication health polled"

