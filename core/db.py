from __future__ import annotations

import importlib
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = ROOT / "db" / "app.sqlite"


def database_url() -> str:
    return os.getenv("DATABASE_URL") or f"sqlite:///{DEFAULT_SQLITE_PATH}"


def is_postgres_url(url: str | None = None) -> bool:
    value = (url or database_url()).lower()
    return value.startswith("postgres://") or value.startswith("postgresql://")


def placeholder() -> str:
    return "%s" if is_postgres_url() else "?"


@contextmanager
def connect() -> Iterator[Any]:
    url = database_url()
    if is_postgres_url(url):
        psycopg = importlib.import_module("psycopg")
        rows = importlib.import_module("psycopg.rows")
        conn = psycopg.connect(url, row_factory=rows.dict_row)
    else:
        path = _sqlite_path(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_app_schema() -> None:
    initialize_auth_schema()
    initialize_feedback_schema()


def initialize_auth_schema() -> None:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL DEFAULT 'google',
                provider_sub TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                picture TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'student',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL,
                last_seen_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT,
                revoked_at TEXT,
                user_agent TEXT,
                ip_address TEXT
            )
            """
        )
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_last_login_at ON users(last_login_at)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_sessions_token_hash ON auth_sessions(token_hash)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at)")


def initialize_feedback_schema() -> None:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_tickets (
                ticket_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                user_sub TEXT NOT NULL DEFAULT '',
                user_email TEXT NOT NULL DEFAULT '',
                user_name TEXT NOT NULL DEFAULT '',
                user_picture TEXT NOT NULL DEFAULT '',
                question_text TEXT NOT NULL,
                debug_report_id TEXT,
                latest_request TEXT NOT NULL,
                latest_response TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                resolved_at TEXT,
                resolved_response TEXT,
                notification_sent INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_notifications (
                notification_id TEXT PRIMARY KEY,
                ticket_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                read_at TEXT,
                user_sub TEXT NOT NULL DEFAULT '',
                user_email TEXT NOT NULL DEFAULT '',
                user_name TEXT NOT NULL DEFAULT '',
                user_picture TEXT NOT NULL DEFAULT '',
                question_text TEXT,
                engine_case TEXT,
                answer TEXT,
                debug_report_id TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_tickets_user_email ON feedback_tickets(user_email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_tickets_status ON feedback_tickets(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_notifications_user_email ON feedback_notifications(user_email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_notifications_read_at ON feedback_notifications(read_at)")


def _sqlite_path(url: str) -> Path:
    if url.startswith("sqlite:///"):
        return Path(url.removeprefix("sqlite:///")).expanduser().resolve()
    if url.startswith("sqlite://"):
        return Path(url.removeprefix("sqlite://")).expanduser().resolve()
    return DEFAULT_SQLITE_PATH
