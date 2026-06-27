"""
Yahoo reader tests — IMAP calls fully mocked.
"""

import imaplib
import pytest
from unittest.mock import patch, MagicMock, call

from sync.yahoo_reader import fetch_uids_since, iter_new_messages, YahooReadError


def _mock_imap(search_response=None, fetch_responses=None):
    conn = MagicMock()
    conn.uid.side_effect = _make_uid_side_effect(search_response, fetch_responses)
    return conn


def _make_uid_side_effect(search_response, fetch_responses):
    fetch_iter = iter(fetch_responses or [])

    def side_effect(command, *args):
        if command == "SEARCH":
            return search_response or ("OK", [b""])
        if command == "FETCH":
            return next(fetch_iter)
        raise ValueError(f"Unexpected command: {command}")

    return side_effect


@pytest.fixture
def mock_connect():
    with patch("sync.yahoo_reader.connect") as mock:
        yield mock


def test_fetch_uids_since_empty_inbox(mock_connect):
    conn = MagicMock()
    conn.uid.return_value = ("OK", [b""])
    mock_connect.return_value = conn

    uids = fetch_uids_since("user@yahoo.com", 0)
    assert uids == []


def test_fetch_uids_since_returns_sorted_uids(mock_connect):
    conn = MagicMock()
    conn.uid.return_value = ("OK", [b"15 12 18 10"])
    mock_connect.return_value = conn

    uids = fetch_uids_since("user@yahoo.com", 9)
    assert uids == [10, 12, 15, 18]


def test_fetch_uids_since_search_failure(mock_connect):
    conn = MagicMock()
    conn.uid.return_value = ("NO", [b""])
    mock_connect.return_value = conn

    with pytest.raises(YahooReadError, match="SEARCH failed"):
        fetch_uids_since("user@yahoo.com", 0)


def test_iter_new_messages_yields_in_order(mock_connect):
    msg1 = b"From: a@b.com\r\nSubject: Test1\r\n\r\nBody1"
    msg2 = b"From: c@d.com\r\nSubject: Test2\r\n\r\nBody2"

    conn = MagicMock()
    call_count = [0]

    def uid_side(command, *args):
        if command == "SEARCH":
            return ("OK", [b"10 11"])
        if command == "FETCH":
            call_count[0] += 1
            if call_count[0] == 1:
                return ("OK", [(None, msg1)])
            return ("OK", [(None, msg2)])

    conn.uid.side_effect = uid_side
    mock_connect.return_value = conn

    results = list(iter_new_messages("user@yahoo.com", 9))
    assert len(results) == 2
    assert results[0] == (10, msg1)
    assert results[1] == (11, msg2)


def test_iter_new_messages_stops_on_fetch_failure(mock_connect):
    conn = MagicMock()

    def uid_side(command, *args):
        if command == "SEARCH":
            return ("OK", [b"10 11"])
        return ("NO", [None])

    conn.uid.side_effect = uid_side
    mock_connect.return_value = conn

    with pytest.raises(YahooReadError):
        list(iter_new_messages("user@yahoo.com", 9))


def test_iter_new_messages_empty(mock_connect):
    conn = MagicMock()
    conn.uid.return_value = ("OK", [b""])
    mock_connect.return_value = conn

    results = list(iter_new_messages("user@yahoo.com", 100))
    assert results == []
