import sqlite3
from datetime import datetime, timezone

DB_PATH = "authorized_users.db"

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH)
    return _conn


def init_db() -> None:
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS authorized_users (
            user_id   INTEGER PRIMARY KEY,
            username  TEXT,
            authorized_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def is_authorized(user_id: int) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM authorized_users WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row is not None


def authorize_user(user_id: int, username: str | None) -> None:
    conn = _get_conn()
    conn.execute(
        """
        INSERT OR IGNORE INTO authorized_users (user_id, username, authorized_at)
        VALUES (?, ?, ?)
        """,
        (user_id, username, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
