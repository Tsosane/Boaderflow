from __future__ import annotations

import argparse
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.bootstrap import bootstrap_database
from app.config import get_settings
from app.database import build_engine, build_session_factory, session_scope
from app.services.projections import refresh_projection_cache
from app.services.replication import upsert_replication_issues
from app.services.replication_topology import configure_replication, load_topology


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="borderflow-cli", description="BorderFlow operations CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_site = subparsers.add_parser("init-site", help="Create schema, seed data, and refresh projections for one site.")
    init_site.add_argument("--skip-seed", action="store_true")
    init_site.add_argument("--skip-schema", action="store_true")

    subparsers.add_parser("refresh-projections", help="Refresh the container projection cache.")
    subparsers.add_parser("poll-replication", help="Read replication stats and update replication issues.")

    setup_replication = subparsers.add_parser("setup-replication", help="Create publications and subscriptions for the full topology.")
    setup_replication.add_argument("--topology", default=None)
    setup_replication.add_argument("--reset", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    wait_for_database(engine, settings.database_wait_timeout_seconds, settings.database_wait_interval_seconds)

    if args.command == "init-site":
        bootstrap_database(
            engine,
            session_factory,
            settings,
            apply_schema=not args.skip_schema,
            apply_seed=not args.skip_seed,
        )
        print(f"Initialized {settings.site_code} at {settings.database_url}")
        return

    if args.command == "refresh-projections":
        with session_scope(session_factory) as session:
            refresh_projection_cache(session)
        print(f"Refreshed projections for {settings.site_code}")
        return

    if args.command == "poll-replication":
        with session_scope(session_factory) as session:
            issues = upsert_replication_issues(session, settings)
        print(f"Recorded {len(issues)} replication issue(s) for {settings.site_code}")
        return

    if args.command == "setup-replication":
        topology = load_topology(args.topology or settings.topology_path)
        configure_replication(topology, reset=args.reset)
        print(f"Configured replication from topology {args.topology or settings.topology_path}")
        return


def wait_for_database(engine, timeout_seconds: int, interval_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
