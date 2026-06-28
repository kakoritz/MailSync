import pytest
from core import database


def test_init_creates_tables():
    # fresh_db fixture already called init(); just verify tables exist
    with database.get_conn() as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert {"accounts", "sync_state", "sync_log"}.issubset(tables)


# --- accounts ---

def test_upsert_and_get_account():
    database.upsert_account("yahoo", "user@yahoo.com", b"encrypted-blob")
    row = database.get_account("user@yahoo.com")
    assert row is not None
    assert row["service"] == "yahoo"
    assert bytes(row["cred_blob"]) == b"encrypted-blob"


def test_upsert_updates_existing():
    database.upsert_account("yahoo", "user@yahoo.com", b"old-blob")
    database.upsert_account("yahoo", "user@yahoo.com", b"new-blob")
    row = database.get_account("user@yahoo.com")
    assert bytes(row["cred_blob"]) == b"new-blob"


def test_get_accounts_by_service():
    database.upsert_account("yahoo", "a@yahoo.com", b"x")
    database.upsert_account("microsoft", "b@outlook.com", b"y")
    yahoo = database.get_accounts_by_service("yahoo")
    assert len(yahoo) == 1
    assert yahoo[0]["email"] == "a@yahoo.com"


def test_delete_account():
    database.upsert_account("yahoo", "user@yahoo.com", b"blob")
    database.delete_account("user@yahoo.com")
    assert database.get_account("user@yahoo.com") is None


# --- sync_state ---

def test_get_or_create_sync_state_creates_on_first_call():
    state = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    assert state["yahoo_email"] == "a@yahoo.com"
    assert state["last_yahoo_uid"] == 0


def test_get_or_create_sync_state_returns_existing():
    state1 = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    database.update_last_uid("a@yahoo.com", 42)
    state2 = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    assert state2["last_yahoo_uid"] == 42


def test_update_last_uid():
    database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    database.update_last_uid("a@yahoo.com", 100)
    state = database.get_sync_state("a@yahoo.com")
    assert state["last_yahoo_uid"] == 100


def test_first_sync_at_set_only_once():
    database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    database.update_last_uid("a@yahoo.com", 1)
    state_after_first = database.get_sync_state("a@yahoo.com")
    first_sync = state_after_first["first_sync_at"]

    database.update_last_uid("a@yahoo.com", 2)
    state_after_second = database.get_sync_state("a@yahoo.com")
    assert state_after_second["first_sync_at"] == first_sync


def test_delete_sync_state():
    database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    database.delete_sync_state("a@yahoo.com")
    assert database.get_sync_state("a@yahoo.com") is None


# --- sync_log ---

def test_sync_log_lifecycle():
    state = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    log_id = database.start_sync_log(state["id"])
    assert isinstance(log_id, int)
    database.finish_sync_log(log_id, 5, "success")


def test_sync_stats_empty():
    state = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    stats = database.get_sync_stats(state["id"])
    assert stats["total_synced"] == 0
    assert stats["today_synced"] == 0
    assert stats["health_pct"] == 100


def test_sync_stats_accumulate():
    state = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    for _ in range(3):
        log_id = database.start_sync_log(state["id"])
        database.finish_sync_log(log_id, 10, "success")

    stats = database.get_sync_stats(state["id"])
    assert stats["total_synced"] == 30
    assert stats["health_pct"] == 100


def test_health_pct_with_errors():
    state = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    log_id = database.start_sync_log(state["id"])
    database.finish_sync_log(log_id, 5, "success")
    log_id = database.start_sync_log(state["id"])
    database.finish_sync_log(log_id, 0, "error", "IMAP timeout")

    stats = database.get_sync_stats(state["id"])
    assert stats["health_pct"] == 50


def test_pending_emails_default_is_none():
    state = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    assert state["pending_emails"] is None


def test_update_pending_emails():
    database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    database.update_pending_emails("a@yahoo.com", 42)
    state = database.get_sync_state("a@yahoo.com")
    assert state["pending_emails"] == 42


def test_update_pending_emails_to_zero():
    database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    database.update_pending_emails("a@yahoo.com", 10)
    database.update_pending_emails("a@yahoo.com", 0)
    state = database.get_sync_state("a@yahoo.com")
    assert state["pending_emails"] == 0


def test_idle_last_seen_default_is_none():
    state = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    assert state["idle_last_seen"] is None


def test_update_idle_last_seen():
    database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    database.update_idle_last_seen("a@yahoo.com")
    state = database.get_sync_state("a@yahoo.com")
    assert state["idle_last_seen"] is not None
    # Should be a valid ISO timestamp
    from datetime import datetime
    dt = datetime.fromisoformat(state["idle_last_seen"])
    assert dt is not None


def test_get_sync_stats_by_day_empty():
    state = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    rows = database.get_sync_stats_by_day(state["id"])
    assert isinstance(rows, list)
    assert rows == []


def test_get_sync_stats_by_day_accumulates():
    state = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    log_id = database.start_sync_log(state["id"])
    database.finish_sync_log(log_id, 7, "success")
    log_id = database.start_sync_log(state["id"])
    database.finish_sync_log(log_id, 3, "success")

    rows = database.get_sync_stats_by_day(state["id"])
    assert len(rows) == 1
    assert rows[0]["emails_synced"] == 10


def test_get_sync_stats_by_day_excludes_errors():
    state = database.get_or_create_sync_state("a@yahoo.com", "b@outlook.com")
    log_id = database.start_sync_log(state["id"])
    database.finish_sync_log(log_id, 5, "success")
    log_id = database.start_sync_log(state["id"])
    database.finish_sync_log(log_id, 0, "error", "timeout")

    rows = database.get_sync_stats_by_day(state["id"])
    assert len(rows) == 1
    assert rows[0]["emails_synced"] == 5
