"""
Sync engine tests — verifies last-UID tracking, idempotency, and error recovery.
"""

import email
import pytest
from unittest.mock import patch, MagicMock, call

from core import database
from sync.sync_engine import run_sync
from sync.yahoo_reader import YahooReadError
from sync.outlook_writer import OutlookWriteError

YAHOO = "user@yahoo.com"
OUTLOOK = "user@outlook.com"

_MSG_TEMPLATE = "From: sender@example.com\r\nMessage-ID: <{id}@test>\r\nSubject: Test {id}\r\n\r\nBody {id}"


def _rfc822(msg_id: str) -> bytes:
    return _MSG_TEMPLATE.format(id=msg_id).encode()


@pytest.fixture(autouse=True)
def setup_db():
    database.init()
    yield


def test_sync_advances_last_uid():
    database.get_or_create_sync_state(YAHOO, OUTLOOK)

    messages = [(10, _rfc822("10")), (11, _rfc822("11")), (12, _rfc822("12"))]

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists", return_value=False), \
         patch("sync.sync_engine.import_message", return_value="graph-id"):
        result = run_sync(YAHOO, OUTLOOK)

    assert result.emails_synced == 3
    assert result.status == "success"
    state = database.get_sync_state(YAHOO)
    assert state["last_yahoo_uid"] == 12


def test_sync_skips_existing_messages():
    # Seed a non-zero UID so is_initial_sync=False and message_exists is consulted
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
    database.update_last_uid(YAHOO, 9)

    messages = [(10, _rfc822("10")), (11, _rfc822("11"))]

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists", return_value=True), \
         patch("sync.sync_engine.import_message") as mock_import:
        result = run_sync(YAHOO, OUTLOOK)

    mock_import.assert_not_called()
    assert result.emails_synced == 0
    assert result.status == "success"
    state = database.get_sync_state(YAHOO)
    assert state["last_yahoo_uid"] == 11


def test_sync_partial_failure_preserves_last_good_uid():
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
    messages = [(10, _rfc822("10")), (11, _rfc822("11")), (12, _rfc822("12"))]

    import_calls = [0]
    def mock_import(email_addr, rfc):
        import_calls[0] += 1
        if import_calls[0] == 2:
            raise OutlookWriteError("Graph API 503")
        return "ok"

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists", return_value=False), \
         patch("sync.sync_engine.import_message", side_effect=mock_import):
        result = run_sync(YAHOO, OUTLOOK)

    assert result.status == "partial"
    assert result.emails_synced == 1
    state = database.get_sync_state(YAHOO)
    assert state["last_yahoo_uid"] == 10


def test_sync_yahoo_error_sets_error_status():
    database.get_or_create_sync_state(YAHOO, OUTLOOK)

    with patch("sync.sync_engine.iter_new_messages",
               side_effect=YahooReadError("IMAP connection refused")):
        result = run_sync(YAHOO, OUTLOOK)

    assert result.status == "error"
    assert "IMAP connection refused" in result.errors[0]
    state = database.get_sync_state(YAHOO)
    assert state["last_yahoo_uid"] == 0


def test_sync_empty_inbox_succeeds_with_zero_emails():
    database.get_or_create_sync_state(YAHOO, OUTLOOK)

    with patch("sync.sync_engine.iter_new_messages", return_value=iter([])):
        result = run_sync(YAHOO, OUTLOOK)

    assert result.emails_synced == 0
    assert result.status == "success"


def test_sync_calls_progress_callback():
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
    messages = [(10, _rfc822("10")), (11, _rfc822("11"))]
    progress_values = []

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists", return_value=False), \
         patch("sync.sync_engine.import_message", return_value="id"):
        run_sync(YAHOO, OUTLOOK, progress_cb=progress_values.append)

    assert progress_values == [1, 2]


def test_sync_writes_log_entry():
    state = database.get_or_create_sync_state(YAHOO, OUTLOOK)
    messages = [(10, _rfc822("10"))]

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists", return_value=False), \
         patch("sync.sync_engine.import_message", return_value="id"):
        run_sync(YAHOO, OUTLOOK)

    stats = database.get_sync_stats(state["id"])
    assert stats["total_synced"] == 1


def test_sync_is_idempotent_on_rerun():
    database.get_or_create_sync_state(YAHOO, OUTLOOK)

    messages = [(10, _rfc822("10"))]
    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists", return_value=False), \
         patch("sync.sync_engine.import_message", return_value="id"):
        run_sync(YAHOO, OUTLOOK)

    # Second run: same UID range but message_exists returns True
    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists", return_value=True), \
         patch("sync.sync_engine.import_message") as mock_import:
        result = run_sync(YAHOO, OUTLOOK)

    mock_import.assert_not_called()
    assert result.emails_synced == 0


# --- dry_run ---

def test_dry_run_does_not_write_or_update_db():
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
    messages = [(10, _rfc822("10")), (11, _rfc822("11"))]

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.import_message") as mock_import:
        result = run_sync(YAHOO, OUTLOOK, dry_run=True)

    mock_import.assert_not_called()
    assert result.dry_run is True
    assert result.emails_would_sync == 2
    assert result.emails_synced == 0

    state = database.get_sync_state(YAHOO)
    assert state["last_yahoo_uid"] == 0


def test_dry_run_does_not_write_log_entry():
    state = database.get_or_create_sync_state(YAHOO, OUTLOOK)
    messages = [(10, _rfc822("10"))]

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)):
        run_sync(YAHOO, OUTLOOK, dry_run=True)

    stats = database.get_sync_stats(state["id"])
    assert stats["total_synced"] == 0


def test_dry_run_calls_progress_callback():
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
    messages = [(10, _rfc822("10")), (11, _rfc822("11")), (12, _rfc822("12"))]
    progress = []

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)):
        run_sync(YAHOO, OUTLOOK, progress_cb=progress.append, dry_run=True)

    assert progress == [1, 2, 3]


# --- initial sync optimization ---

def test_initial_sync_skips_message_exists_check():
    """When last_yahoo_uid is 0, message_exists must never be called."""
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
    messages = [(1, _rfc822("1")), (2, _rfc822("2"))]

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists") as mock_exists, \
         patch("sync.sync_engine.import_message", return_value="id"):
        result = run_sync(YAHOO, OUTLOOK)

    mock_exists.assert_not_called()
    assert result.emails_synced == 2


def test_subsequent_sync_calls_message_exists():
    """After at least one prior sync, message_exists is called for each message."""
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
    database.update_last_uid(YAHOO, 5)  # non-zero → is_initial_sync=False

    messages = [(6, _rfc822("6")), (7, _rfc822("7"))]

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists", return_value=False) as mock_exists, \
         patch("sync.sync_engine.import_message", return_value="id"):
        run_sync(YAHOO, OUTLOOK)

    assert mock_exists.call_count == 2


def test_sync_counts_skipped_dedup_messages():
    """Deduped messages are counted in emails_skipped, not emails_synced."""
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
    database.update_last_uid(YAHOO, 5)  # non-zero → is_initial_sync=False

    messages = [(6, _rfc822("6")), (7, _rfc822("7"))]

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists", return_value=True), \
         patch("sync.sync_engine.import_message") as mock_import:
        result = run_sync(YAHOO, OUTLOOK)

    mock_import.assert_not_called()
    assert result.emails_skipped == 2
    assert result.emails_synced == 0


def test_per_run_cache_avoids_api_call_for_duplicate_message_id():
    """Two UIDs with the same Message-ID: second one hits the cache, not the API."""
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
    database.update_last_uid(YAHOO, 5)

    # Both messages have same Message-ID (can happen in some IMAP edge cases)
    same_rfc = _rfc822("same-id")
    messages = [(6, same_rfc), (7, same_rfc)]

    exists_calls = [0]
    def mock_exists(*_):
        exists_calls[0] += 1
        return False

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)), \
         patch("sync.sync_engine.message_exists", side_effect=mock_exists), \
         patch("sync.sync_engine.import_message", return_value="id"):
        result = run_sync(YAHOO, OUTLOOK)

    # First UID: message_exists called once, written, cached
    # Second UID: cache hit — message_exists NOT called again
    assert exists_calls[0] == 1
    assert result.emails_synced == 1
    assert result.emails_cache_hit == 1


def test_dry_run_persists_pending_count_in_db():
    """After a dry-run, pending_emails is written to sync_state."""
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
    messages = [(1, _rfc822("1")), (2, _rfc822("2"))]

    with patch("sync.sync_engine.iter_new_messages", return_value=iter(messages)):
        result = run_sync(YAHOO, OUTLOOK, dry_run=True)

    assert result.emails_would_sync == 2
    state = database.get_sync_state(YAHOO)
    assert state["pending_emails"] == 2
