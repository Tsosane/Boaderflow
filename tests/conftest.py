from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import bootstrap_database
from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    db_path = tmp_path / "borderflow-test.db"
    return Settings(
        database_url=f"sqlite:///{db_path}",
        api_secret_key="test-secret",
        seed_scope="all",
        bootstrap_database=True,
        site_code="DEPOT-MSU",
        site_name="Maseru Depot",
        repl_subscriptions="sub_demo_from_depot",
    )


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session(app):
    bootstrap_database(app.state.engine, app.state.session_factory, app.state.settings)
    session_factory = app.state.session_factory
    with session_factory() as db:
        yield db
