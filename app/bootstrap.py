from __future__ import annotations

import time

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base, session_scope
from app.models import BootstrapState
from app.services.projections import ensure_projection_view, refresh_projection_cache
from app.services.seed import seed_demo_data


def bootstrap_database(
    engine: Engine,
    session_factory: sessionmaker,
    settings: Settings,
    *,
    apply_schema: bool = True,
    apply_seed: bool = True,
) -> None:
    if apply_schema:
        Base.metadata.create_all(engine)
    _apply_postgres_runtime_guards(engine)
    ensure_projection_view(engine)

    with session_scope(session_factory) as session:
        if apply_schema:
            _set_bootstrap_state(session, "schema", "applied")
        if apply_seed:
            seed_demo_data(session, settings)
            _set_bootstrap_state(session, f"seed:{settings.site_code}", settings.seed_scope)
        refresh_projection_cache(session)
        _set_bootstrap_state(session, "projection_cache", "refreshed")


def _set_bootstrap_state(session, key: str, value: str) -> None:
    state = session.get(BootstrapState, key)
    if state is None:
        session.add(BootstrapState(key=key, value=value))
    else:
        state.value = value


def _apply_postgres_runtime_guards(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.connect() as connection:
        _execute_postgres_guard_statement(
            connection,
            text(
                """
                CREATE OR REPLACE FUNCTION prevent_event_mutation()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION '% rows are append-only in BorderFlow.', TG_TABLE_NAME;
                END;
                $$ LANGUAGE plpgsql
                """
            ),
        )
        _execute_postgres_guard_statement(connection, text("DROP TRIGGER IF EXISTS trg_milestone_immutable ON milestone"))
        _execute_postgres_guard_statement(
            connection,
            text(
                """
                CREATE TRIGGER trg_milestone_immutable
                    BEFORE UPDATE OR DELETE ON milestone
                    FOR EACH ROW
                    EXECUTE FUNCTION prevent_event_mutation()
                """
            ),
        )
        _execute_postgres_guard_statement(connection, text("DROP TRIGGER IF EXISTS trg_handover_immutable ON handover"))
        _execute_postgres_guard_statement(
            connection,
            text(
                """
                CREATE TRIGGER trg_handover_immutable
                    BEFORE UPDATE OR DELETE ON handover
                    FOR EACH ROW
                    EXECUTE FUNCTION prevent_event_mutation()
                """
            ),
        )

        # Row-filtered logical replication needs the filter column available in the
        # replica identity for UPDATE/DELETE traffic. FULL keeps the publications
        # simple and avoids per-table custom identity indexes in this MVP.
        for table_name in (
            "app_user",
            "client",
            "vehicle",
            "driver",
            "consignment",
            "container",
            "trip",
            "trip_container",
            "milestone",
            "handover",
            "incident",
            "event_log",
        ):
            _execute_postgres_guard_statement(connection, text(f"ALTER TABLE {table_name} REPLICA IDENTITY FULL"))


def _execute_postgres_guard_statement(connection, statement, retries: int = 6, delay_seconds: float = 0.5) -> None:
    for attempt in range(retries):
        transaction = connection.begin()
        try:
            connection.execute(statement)
            transaction.commit()
            return
        except OperationalError as exc:
            transaction.rollback()
            sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
            if sqlstate != "40P01" or attempt == retries - 1:
                raise
            time.sleep(delay_seconds * (attempt + 1))
        except Exception:
            transaction.rollback()
            raise
