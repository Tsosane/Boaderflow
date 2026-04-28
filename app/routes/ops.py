from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text


router = APIRouter(tags=["ops"])


@router.get("/health")
def health(request: Request):
    settings = request.app.state.settings
    return {"status": "ok", "site_code": settings.site_code, "site_name": settings.site_name}


@router.get("/ready")
def ready(request: Request):
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ready"}
