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
    database.get_or_create_sync_state(YAHOO, OUTLOOK)
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
