"""
Yahoo reader tests — IMAP calls fully mocked.
"""

import imaplib
import pytest
from unittest.mock import patch, MagicMock

from sync.yahoo_reader import fetch_uids_since, iter_new_messages, YahooReadError


@pytest.fixture
def mock_connect():
    with patch("sync.yahoo_reader.connect") as mock:
        yield mock


# --- fetch_uids_since ---

def test_fetch_uids_since_empty_inbox(mock_connect):
    conn = MagicMock()
    conn.uid.return_value = ("OK", [b""])
    mock_connect.return_value = conn
    assert fetch_uids_since("user@yahoo.com", 0) == []


def test_fetch_uids_since_returns_sorted_uids(mock_connect):
    conn = MagicMock()
    conn.uid.return_value = ("OK", [b"15 12 18 10"])
    mock_connect.return_value = conn
    assert fetch_uids_since("user@yahoo.com", 9) == [10, 12, 15, 18]


def test_fetch_uids_since_search_failure(mock_connect):
    conn = MagicMock()
    conn.uid.return_value = ("NO", [b""])
    mock_connect.return_value = conn
    with pytest.raises(YahooReadError, match="SEARCH failed"):
        fetch_uids_since("user@yahoo.com", 0)


# --- iter_new_messages ---

def test_iter_new_messages_yields_in_order(mock_connect):
    msg1 = b"From: a@b.com\r\nSubject: Test1\r\n\r\nBody1"
    msg2 = b"From: c@d.com\r\nSubject: Test2\r\n\r\nBody2"
    conn = MagicMock()
    fetch_count = [0]

    def uid_side(command, *args):
        if command == "SEARCH":
            return ("OK", [b"10 11"])
        fetch_count[0] += 1
        return ("OK", [(None, msg1 if fetch_count[0] == 1 else msg2)])

    conn.uid.side_effect = uid_side
    mock_connect.return_value = conn

    results = list(iter_new_messages("user@yahoo.com", 9))
    assert results == [(10, msg1), (11, msg2)]


def test_iter_new_messages_skips_expunged_uid(mock_connect):
    """A NIL FETCH response (deleted message) is skipped; iteration continues."""
    msg2 = b"From: c@d.com\r\nSubject: Alive\r\n\r\nBody"
    conn = MagicMock()
    fetch_count = [0]

    def uid_side(command, *args):
        if command == "SEARCH":
            return ("OK", [b"10 11"])
        fetch_count[0] += 1
        if fetch_count[0] == 1:
            return ("OK", [None])  # UID 10 was expunged
        return ("OK", [(None, msg2)])

    conn.uid.side_effect = uid_side
    mock_connect.return_value = conn

    results = list(iter_new_messages("user@yahoo.com", 9))
    assert results == [(11, msg2)]


def test_iter_new_messages_fetch_status_failure_raises(mock_connect):
    conn = MagicMock()

    def uid_side(command, *args):
        if command == "SEARCH":
            return ("OK", [b"10 11"])
        return ("NO", [None])

    conn.uid.side_effect = uid_side
    mock_connect.return_value = conn

    with pytest.raises(YahooReadError, match="FETCH failed"):
        list(iter_new_messages("user@yahoo.com", 9))


def test_iter_new_messages_empty(mock_connect):
    conn = MagicMock()
    conn.uid.return_value = ("OK", [b""])
    mock_connect.return_value = conn
    assert list(iter_new_messages("user@yahoo.com", 100)) == []


def test_iter_new_messages_imap_error_raises(mock_connect):
    conn = MagicMock()
    conn.uid.side_effect = imaplib.IMAP4.error("connection reset")
    mock_connect.return_value = conn

    with pytest.raises(YahooReadError, match="IMAP error"):
        list(iter_new_messages("user@yahoo.com", 0))
