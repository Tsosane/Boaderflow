from __future__ import annotations

from celery import Celery

from app.config import get_settings


settings = get_settings()

celery_app = Celery(
    "borderflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "refresh-projection-cache": {
            "task": "app.tasks.refresh_projection_cache_task",
            "schedule": settings.worker_refresh_interval_seconds,
        },
        "poll-replication-health": {
            "task": "app.tasks.poll_replication_health_task",
            "schedule": settings.worker_health_interval_seconds,
        },
    },
)
