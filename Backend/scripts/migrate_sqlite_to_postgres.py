from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from psycopg import connect
from psycopg.rows import dict_row

from backend_app.config import DEFAULT_DB_PATH
from backend_app.db import configure_database, init_db


TABLES = [
    "card_products",
    "user_price_configs",
    "cabinets",
    "users",
    "user_balance_transactions",
    "user_sessions",
    "rentals",
    "rental_allocations",
]


def load_sqlite_rows(db_path: Path, table_name: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(f"SELECT * FROM {table_name} ORDER BY id ASC").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def migrate() -> None:
    sqlite_path = Path(os.getenv("SOURCE_SQLITE_PATH", DEFAULT_DB_PATH))
    database_url = os.getenv("DATABASE_URL")

    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    configure_database(database_url=database_url)
    init_db()

    with connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE rental_allocations, rentals, user_sessions, user_balance_transactions, users, cabinets, user_price_configs, card_products RESTART IDENTITY CASCADE")

            for table_name in TABLES:
                rows = load_sqlite_rows(sqlite_path, table_name)
                if not rows:
                    continue

                columns = list(rows[0].keys())
                quoted_columns = ", ".join(columns)
                placeholders = ", ".join(["%s"] * len(columns))
                cur.executemany(
                    f"INSERT INTO {table_name} ({quoted_columns}) VALUES ({placeholders})",
                    [tuple(row[column] for column in columns) for row in rows],
                )

                cur.execute(
                    """
                    SELECT setval(
                        pg_get_serial_sequence(%s, 'id'),
                        COALESCE((SELECT MAX(id) FROM """ + table_name + """), 1),
                        COALESCE((SELECT MAX(id) FROM """ + table_name + """), 0) > 0
                    )
                    """,
                    (table_name,),
                )

        conn.commit()

    print(f"Migrated SQLite data from {sqlite_path} to Postgres successfully.")


if __name__ == "__main__":
    migrate()
