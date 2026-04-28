from __future__ import annotations

from app.services.replication_topology import build_subscription_dsn, publication_statement_for_site
from app.services.replication import fetch_replication_snapshot


def test_replication_snapshot_falls_back_on_sqlite(session, settings):
    snapshot = fetch_replication_snapshot(session, settings)
    assert snapshot
    assert snapshot[0]["subname"] == "sub_demo_from_depot"
    assert snapshot[0]["worker_type"] == "unavailable"


def test_depot_publication_includes_full_site_catalog():
    publication_sql = publication_statement_for_site("DEPOT-MSU")
    assert publication_sql is not None
    assert "site," in publication_sql
    assert "CTRL-TOWER" not in publication_sql


def test_subscription_dsn_is_derived_from_sqlalchemy_url():
    dsn = build_subscription_dsn(
        "postgresql+psycopg://borderflow:borderflow@depot-db:5432/borderflow",
        "repl_user",
        "repl_pass",
    )
    assert "host=depot-db" in dsn
    assert "port=5432" in dsn
    assert "dbname=borderflow" in dsn
    assert "user=repl_user" in dsn
