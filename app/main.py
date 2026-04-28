from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.bootstrap import bootstrap_database
from app.config import Settings, get_settings
from app.database import build_engine, build_session_factory
from app.routes import (
    auth,
    clients,
    consignments,
    containers,
    control_tower,
    dashboard,
    drivers,
    handovers,
    incidents,
    milestones,
    ops,
    trips,
    users,
    vehicles,
)


def _session_cookie_name(settings: Settings) -> str:
    if settings.session_cookie_name != "borderflow_session":
        return settings.session_cookie_name
    site_slug = settings.site_code.lower().replace("-", "_")
    return f"{settings.session_cookie_name}_{site_slug}"


def create_app(app_settings: Settings | None = None) -> FastAPI:
    settings = app_settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.bootstrap_database:
            bootstrap_database(app.state.engine, app.state.session_factory, settings)
        yield

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = build_engine(settings.database_url)
    app.state.session_factory = build_session_factory(app.state.engine)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.api_secret_key,
        session_cookie=_session_cookie_name(settings),
    )

    app.include_router(auth.router)
    app.include_router(ops.router)
    app.include_router(dashboard.router)
    app.include_router(clients.router)
    app.include_router(consignments.router)
    app.include_router(containers.router)
    app.include_router(drivers.router)
    app.include_router(users.router)
    app.include_router(trips.router)
    app.include_router(vehicles.router)
    app.include_router(milestones.router)
    app.include_router(handovers.router)
    app.include_router(incidents.router)
    app.include_router(control_tower.router)

    return app


app = create_app()
