import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import os

from core.constants import DB_FILENAME

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    service     TEXT NOT NULL CHECK(service IN ('yahoo','microsoft')),
    email       TEXT NOT NULL UNIQUE,
    cred_blob   BLOB NOT NULL,
    added_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_state (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    yahoo_email     TEXT NOT NULL UNIQUE,
    outlook_email   TEXT NOT NULL,
    last_yahoo_uid  INTEGER NOT NULL DEFAULT 0,
    pending_emails  INTEGER,
    idle_last_seen  TEXT,
    first_sync_at   TEXT,
    last_sync_at    TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_state_id   INTEGER NOT NULL REFERENCES sync_state(id),
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    emails_synced   INTEGER NOT NULL DEFAULT 0,
    status          TEXT CHECK(status IN ('success','partial','error')),
    error_msg       TEXT
);
"""

_MIGRATIONS = [
    "ALTER TABLE sync_state ADD COLUMN pending_emails INTEGER",
    "ALTER TABLE sync_state ADD COLUMN idle_last_seen TEXT",
]


def _db_path() -> Path:
    return Path(os.getenv("MAILSYNC_DATA_DIR", ".")) / DB_FILENAME


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init() -> None:
    _db_path().parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
        # Run migrations; silently skip if the column already exists
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- accounts ---

def upsert_account(service: str, email: str, cred_blob: bytes) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO accounts (service, email, cred_blob, added_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(email) DO UPDATE SET cred_blob=excluded.cred_blob""",
            (service, email, cred_blob, _now()),
        )


def get_account(email: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM accounts WHERE email = ?", (email,)
        ).fetchone()


def get_accounts_by_service(service: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM accounts WHERE service = ?", (service,)
        ).fetchall()


def delete_account(email: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM accounts WHERE email = ?", (email,))


# --- sync_state ---

def get_or_create_sync_state(yahoo_email: str, outlook_email: str) -> sqlite3.Row:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sync_state WHERE yahoo_email = ?", (yahoo_email,)
        ).fetchone()
        if row is None:
            conn.execute(
                """INSERT INTO sync_state
                   (yahoo_email, outlook_email, last_yahoo_uid, created_at)
                   VALUES (?, ?, 0, ?)""",
                (yahoo_email, outlook_email, _now()),
            )
            row = conn.execute(
                "SELECT * FROM sync_state WHERE yahoo_email = ?", (yahoo_email,)
            ).fetchone()
        return row


def update_last_uid(yahoo_email: str, uid: int) -> None:
    with get_conn() as conn:
        now = _now()
        conn.execute(
            """UPDATE sync_state
               SET last_yahoo_uid = ?,
                   last_sync_at = ?,
                   first_sync_at = COALESCE(first_sync_at, ?)
               WHERE yahoo_email = ?""",
            (uid, now, now, yahoo_email),
        )


def update_pending_emails(yahoo_email: str, count: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sync_state SET pending_emails = ? WHERE yahoo_email = ?",
            (count, yahoo_email),
        )


def update_idle_last_seen(yahoo_email: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sync_state SET idle_last_seen = ? WHERE yahoo_email = ?",
            (_now(), yahoo_email),
        )


def get_sync_stats_by_day(sync_state_id: int, days: int = 7) -> list[dict]:
    """Return emails_synced grouped by date for the last N days."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DATE(started_at) AS date, COALESCE(SUM(emails_synced), 0) AS emails_synced
               FROM sync_log
               WHERE sync_state_id = ?
                 AND started_at >= DATE('now', ? || ' days')
                 AND status = 'success'
               GROUP BY DATE(started_at)
               ORDER BY date""",
            (sync_state_id, f"-{days}"),
        ).fetchall()
        return [{"date": r["date"], "emails_synced": r["emails_synced"]} for r in rows]


def get_sync_state(yahoo_email: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sync_state WHERE yahoo_email = ?", (yahoo_email,)
        ).fetchone()


def delete_sync_state(yahoo_email: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM sync_state WHERE yahoo_email = ?", (yahoo_email,)
        )


# --- sync_log ---

def start_sync_log(sync_state_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sync_log (sync_state_id, started_at) VALUES (?, ?)",
            (sync_state_id, _now()),
        )
        return cur.lastrowid


def finish_sync_log(
    log_id: int, emails_synced: int, status: str, error_msg: str = None
) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE sync_log
               SET completed_at = ?, emails_synced = ?, status = ?, error_msg = ?
               WHERE id = ?""",
            (_now(), emails_synced, status, error_msg, log_id),
        )


def get_sync_stats(sync_state_id: int) -> dict:
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COALESCE(SUM(emails_synced), 0) FROM sync_log WHERE sync_state_id = ?",
            (sync_state_id,),
        ).fetchone()[0]

        today_start = datetime.now(timezone.utc).date().isoformat()
        today = conn.execute(
            """SELECT COALESCE(SUM(emails_synced), 0) FROM sync_log
               WHERE sync_state_id = ? AND started_at >= ?""",
            (sync_state_id, today_start),
        ).fetchone()[0]

        last_30 = conn.execute(
            """SELECT COUNT(*), SUM(CASE WHEN status='success' THEN 1 ELSE 0 END)
               FROM sync_log
               WHERE sync_state_id = ?
                 AND started_at >= datetime('now', '-30 days')""",
            (sync_state_id,),
        ).fetchone()
        total_runs, successful_runs = last_30
        health_pct = int((successful_runs / total_runs) * 100) if total_runs else 100

        return {
            "total_synced": total,
            "today_synced": today,
            "health_pct": health_pct,
        }
