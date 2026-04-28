from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


TABLES = (
    "site",
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
    "replication_issue",
    "container_state_projection",
)


def load_topology(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_counts(dsn: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            for table in TABLES:
                cursor.execute(f"SELECT COUNT(*) AS total FROM {table}")
                counts[table] = cursor.fetchone()["total"]
    return counts


def fetch_projection_rows(dsn: str) -> list[dict]:
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    container_no,
                    current_status,
                    current_site_code,
                    consignment_ref,
                    trip_status
                FROM container_state_projection
                ORDER BY container_no
                """
            )
            return list(cursor.fetchall())


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect BorderFlow site convergence across the replication topology.")
    parser.add_argument(
        "--topology",
        default="infra/replication_topology.json",
        help="Path to the replication topology JSON file.",
    )
    args = parser.parse_args()

    topology = load_topology(Path(args.topology))
    print("BorderFlow convergence snapshot")
    print("=" * 80)

    for key, site in topology["sites"].items():
        print(f"\n[{key}] {site['site_code']}")
        counts = fetch_counts(site["admin_dsn"])
        for table_name, total in counts.items():
            print(f"  {table_name:<24} {total}")

        projection_rows = fetch_projection_rows(site["admin_dsn"])
        if projection_rows:
            print("  projection rows:")
            for row in projection_rows:
                print(
                    "   "
                    f"{row['container_no']} -> {row['current_status']} "
                    f"at {row['current_site_code']} ({row['consignment_ref']}, trip={row['trip_status']})"
                )
        else:
            print("  projection rows: none")


if __name__ == "__main__":
    main()
