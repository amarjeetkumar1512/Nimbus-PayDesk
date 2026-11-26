import os
import re
import sqlite3
import uuid
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "nimbus.db"


def get_database_url():
    return os.getenv("DATABASE_URL", "").strip()


class PostgresConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, query, params=None):
        query = query.strip()

        if query.upper() == "BEGIN IMMEDIATE":
            query = "BEGIN"
        else:
            query = re.sub(r"\?", "%s", query)

        if params is None:
            return self._connection.execute(query)

        return self._connection.execute(query, params)

    def commit(self):
        from psycopg.pq import TransactionStatus

        if self._connection.info.transaction_status != TransactionStatus.IDLE:
            self._connection.execute("COMMIT")

    def rollback(self):
        from psycopg.pq import TransactionStatus

        if self._connection.info.transaction_status != TransactionStatus.IDLE:
            self._connection.execute("ROLLBACK")

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()

        return False


def get_connection():
    database_url = get_database_url()

    if database_url:
        import psycopg
        from psycopg.rows import dict_row

        if database_url.startswith("postgres://"):
            database_url = database_url.replace(
                "postgres://",
                "postgresql://",
                1
            )

        connection = psycopg.connect(
            database_url,
            row_factory=dict_row,
            autocommit=True,
            connect_timeout=15
        )

        return PostgresConnection(connection)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def migrate_tickets_table(conn):
    columns = conn.execute(
        "PRAGMA table_info(tickets)"
    ).fetchall()

    column_info = {
        column["name"]: dict(column)
        for column in columns
    }

    required = {
        "ticket_id",
        "invoice_id",
        "cid",
        "status",
        "reason",
        "amount",
        "created_at",
    }

    migration_needed = (
        not required.issubset(column_info)
        or column_info.get("ticket_id", {}).get("pk") != 1
        or column_info.get("invoice_id", {}).get("notnull") != 0
        or column_info.get("amount", {}).get("notnull") != 0
    )

    if not migration_needed:
        print("Tickets table migration already completed.")
        return

    print("Migrating tickets table...")

    conn.execute("DROP TABLE IF EXISTS tickets_new")

    conn.execute("""
        CREATE TABLE tickets_new (
            ticket_id TEXT PRIMARY KEY,
            invoice_id TEXT,
            cid TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL,
            reason TEXT,
            amount REAL,
            created_at TEXT NOT NULL
        )
    """)

    old_tickets = conn.execute(
        "SELECT * FROM tickets"
    ).fetchall()

    for ticket in old_tickets:
        ticket_id = (
            ticket["ticket_id"]
            if "ticket_id" in column_info
            else str(uuid.uuid4())
        )

        conn.execute("""
            INSERT INTO tickets_new (
                ticket_id,
                invoice_id,
                cid,
                status,
                reason,
                amount,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id,
            ticket["invoice_id"],
            ticket["cid"],
            ticket["status"],
            ticket["reason"],
            ticket["amount"],
            ticket["created_at"],
        ))

    conn.execute("DROP TABLE tickets")
    conn.execute("ALTER TABLE tickets_new RENAME TO tickets")

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tickets_invoice_id
        ON tickets(invoice_id)
    """)

    print("Tickets table migration completed.")


def migrate_events_table(conn):
    columns = conn.execute(
        "PRAGMA table_info(events)"
    ).fetchall()

    column_info = {
        column["name"]: dict(column)
        for column in columns
    }

    if not column_info.get("invoice_id", {}).get("notnull", 0):
        print("Events table migration already completed.")
        return

    print("Migrating events table...")

    conn.execute("DROP TABLE IF EXISTS events_new")

    conn.execute("""
        CREATE TABLE events_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cid TEXT NOT NULL,
            invoice_id TEXT,
            stage TEXT NOT NULL,
            event TEXT NOT NULL,
            detail TEXT,
            ts TEXT NOT NULL
        )
    """)

    old_events = conn.execute("""
        SELECT id, cid, invoice_id, stage, event, detail, ts
        FROM events
    """).fetchall()

    for event in old_events:
        conn.execute("""
            INSERT INTO events_new (
                id,
                cid,
                invoice_id,
                stage,
                event,
                detail,
                ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            event["id"],
            event["cid"],
            event["invoice_id"],
            event["stage"],
            event["event"],
            event["detail"],
            event["ts"],
        ))

    conn.execute("DROP TABLE events")
    conn.execute("ALTER TABLE events_new RENAME TO events")

    print("Events table migration completed.")


def init_sqlite_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vendors (
                gstin TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                po_id TEXT PRIMARY KEY,
                vendor TEXT NOT NULL,
                amount REAL NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                invoice_id TEXT,
                cid TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL,
                reason TEXT,
                amount REAL,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cid TEXT NOT NULL,
                invoice_id TEXT,
                stage TEXT NOT NULL,
                event TEXT NOT NULL,
                detail TEXT,
                ts TEXT NOT NULL
            )
        """)

        migrate_tickets_table(conn)
        migrate_events_table(conn)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_invoice_id
            ON tickets(invoice_id)
        """)

        conn.commit()


def init_postgres_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vendors (
                gstin TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                po_id TEXT PRIMARY KEY,
                vendor TEXT NOT NULL,
                amount DOUBLE PRECISION NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                invoice_id TEXT,
                cid TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL,
                reason TEXT,
                amount DOUBLE PRECISION,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id BIGSERIAL PRIMARY KEY,
                cid TEXT NOT NULL,
                invoice_id TEXT,
                stage TEXT NOT NULL,
                event TEXT NOT NULL,
                detail TEXT,
                ts TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_invoice_id
            ON tickets(invoice_id)
        """)


def init_db():
    if get_database_url():
        print("Initializing Nimbus PayDesk PostgreSQL database...")
        init_postgres_db()
        print("PostgreSQL database initialized successfully.")
    else:
        print("Initializing Nimbus PayDesk SQLite database...")
        init_sqlite_db()
        print("SQLite database initialized successfully.")


if __name__ == "__main__":
    init_db()

    if get_database_url():
        print("Database: PostgreSQL")
    else:
        print(f"Database location: {DB_PATH}")