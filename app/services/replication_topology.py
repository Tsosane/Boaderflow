from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg import sql


ACTIVE_TRIP_STATUSES = ("PLANNED", "DEPARTED", "IN_TRANSIT", "ARRIVED")


@dataclass(slots=True)
class SiteRecord:
    key: str
    site_code: str
    admin_dsn: str


@dataclass(slots=True)
class SubscriptionRecord:
    name: str
    subscriber: str
    publisher: str
    publication: str


@dataclass(slots=True)
class ReplicationTopology:
    replication_user: str
    replication_password: str
    sites: dict[str, SiteRecord]
    subscriptions: list[SubscriptionRecord]


def load_topology(path: str) -> ReplicationTopology:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sites = {
        key: SiteRecord(key=key, site_code=value["site_code"], admin_dsn=value["admin_dsn"])
        for key, value in payload["sites"].items()
    }
    subscriptions = [SubscriptionRecord(**item) for item in payload["subscriptions"]]
    return ReplicationTopology(
        replication_user=payload["replication_user"],
        replication_password=payload["replication_password"],
        sites=sites,
        subscriptions=subscriptions,
    )


def configure_replication(topology: ReplicationTopology, *, reset: bool = False) -> None:
    for site in topology.sites.values():
        with connect_with_retry(site.admin_dsn, autocommit=True) as connection:
            ensure_replication_user(connection, topology.replication_user, topology.replication_password)
            publication_sql = publication_statement_for_site(site.site_code)
            if publication_sql is not None:
                if reset:
                    drop_publication_if_exists(connection, publication_name_for_site(site.site_code))
                ensure_publication(connection, publication_name_for_site(site.site_code), publication_sql)

    for subscription in topology.subscriptions:
        subscriber = topology.sites[subscription.subscriber]
        publisher = topology.sites[subscription.publisher]
        publisher_dsn = build_subscription_dsn(publisher.admin_dsn, topology.replication_user, topology.replication_password)
        with connect_with_retry(subscriber.admin_dsn, autocommit=True) as connection:
            if reset:
                drop_subscription_if_exists(connection, subscription.name)
            ensure_subscription(connection, subscription.name, publisher_dsn, subscription.publication)


def connect_with_retry(dsn: str, *, autocommit: bool, timeout_seconds: int = 120, interval_seconds: int = 3) -> psycopg.Connection:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            return psycopg.connect(dsn, autocommit=autocommit)
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(interval_seconds)


def ensure_replication_user(connection: psycopg.Connection, username: str, password: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (username,))
        if cursor.fetchone() is None:
            cursor.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN REPLICATION PASSWORD {}").format(
                    sql.Identifier(username),
                    sql.Literal(password),
                )
            )
        else:
            cursor.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN REPLICATION PASSWORD {}").format(
                    sql.Identifier(username),
                    sql.Literal(password),
                )
            )

        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(connection.info.dbname),
                sql.Identifier(username),
            )
        )
        cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(username)))
        cursor.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(username)))
        cursor.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {}").format(
                sql.Identifier(username)
            )
        )


def publication_name_for_site(site_code: str) -> str | None:
    return {
        "DEPOT-MSU": "pub_depot_master",
        "BORDER-MB": "pub_border_events",
        "PORT-DBN": "pub_port_events",
        "HUB-JHB": "pub_hub_events",
    }.get(site_code)


def publication_statement_for_site(site_code: str) -> str | None:
    statements = {
        "DEPOT-MSU": """
        CREATE PUBLICATION pub_depot_master
            FOR TABLE
                site,
                app_user WHERE (origin_site_code = 'DEPOT-MSU'),
                client WHERE (origin_site_code = 'DEPOT-MSU'),
                vehicle WHERE (origin_site_code = 'DEPOT-MSU'),
                driver WHERE (origin_site_code = 'DEPOT-MSU'),
                consignment WHERE (origin_site_code = 'DEPOT-MSU'),
                container WHERE (origin_site_code = 'DEPOT-MSU'),
                trip WHERE (origin_site_code = 'DEPOT-MSU'),
                trip_container WHERE (origin_site_code = 'DEPOT-MSU'),
                milestone WHERE (origin_site_code = 'DEPOT-MSU'),
                event_log WHERE (origin_site_code = 'DEPOT-MSU')
        """,
        "BORDER-MB": """
        CREATE PUBLICATION pub_border_events
            FOR TABLE
                milestone WHERE (origin_site_code = 'BORDER-MB'),
                handover WHERE (origin_site_code = 'BORDER-MB'),
                incident WHERE (origin_site_code = 'BORDER-MB'),
                event_log WHERE (origin_site_code = 'BORDER-MB')
        """,
        "PORT-DBN": """
        CREATE PUBLICATION pub_port_events
            FOR TABLE
                milestone WHERE (origin_site_code = 'PORT-DBN'),
                handover WHERE (origin_site_code = 'PORT-DBN'),
                incident WHERE (origin_site_code = 'PORT-DBN'),
                event_log WHERE (origin_site_code = 'PORT-DBN')
        """,
        "HUB-JHB": """
        CREATE PUBLICATION pub_hub_events
            FOR TABLE
                milestone WHERE (origin_site_code = 'HUB-JHB'),
                handover WHERE (origin_site_code = 'HUB-JHB'),
                incident WHERE (origin_site_code = 'HUB-JHB'),
                event_log WHERE (origin_site_code = 'HUB-JHB')
        """,
    }
    return statements.get(site_code)


def ensure_publication(connection: psycopg.Connection, publication_name: str, create_sql: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_publication WHERE pubname = %s", (publication_name,))
        if cursor.fetchone() is None:
            cursor.execute(create_sql)


def drop_publication_if_exists(connection: psycopg.Connection, publication_name: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("DROP PUBLICATION IF EXISTS {}").format(sql.Identifier(publication_name)))


def ensure_subscription(connection: psycopg.Connection, name: str, publisher_dsn: str, publication: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_subscription WHERE subname = %s", (name,))
        if cursor.fetchone() is None:
            cursor.execute(
                sql.SQL(
                    "CREATE SUBSCRIPTION {} CONNECTION {} PUBLICATION {} "
                    "WITH (copy_data = true, create_slot = true, enabled = true)"
                ).format(
                    sql.Identifier(name),
                    sql.Literal(publisher_dsn),
                    sql.Identifier(publication),
                )
            )
        else:
            cursor.execute(sql.SQL("ALTER SUBSCRIPTION {} ENABLE").format(sql.Identifier(name)))
            cursor.execute(sql.SQL("ALTER SUBSCRIPTION {} REFRESH PUBLICATION").format(sql.Identifier(name)))


def drop_subscription_if_exists(connection: psycopg.Connection, name: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_subscription WHERE subname = %s", (name,))
        if cursor.fetchone() is None:
            return
        cursor.execute(sql.SQL("ALTER SUBSCRIPTION {} DISABLE").format(sql.Identifier(name)))
        cursor.execute(sql.SQL("DROP SUBSCRIPTION {}").format(sql.Identifier(name)))


def build_subscription_dsn(admin_dsn: str, replication_user: str, replication_password: str) -> str:
    parsed = urlparse(admin_dsn.replace("+psycopg", ""))
    database = parsed.path.lstrip("/")
    return (
        f"host={parsed.hostname} port={parsed.port or 5432} dbname={database} "
        f"user={replication_user} password={replication_password}"
    )
