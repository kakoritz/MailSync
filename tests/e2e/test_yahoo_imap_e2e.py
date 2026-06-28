"""
E2E tests for yahoo_reader.py against a real Dovecot IMAP server.

These tests verify that the actual IMAP stack (imaplib UID commands,
SEARCH, FETCH, EXPUNGE handling) works against a real server — not mocks.

Start the server before running:
    docker-compose -f docker-compose.test.yml up -d
    pytest tests/e2e/ -m e2e -q
"""

import email
import imaplib
import textwrap
import time

import pytest

from tests.e2e.conftest import E2E_HOST, E2E_PORT, E2E_USER, E2E_PASS


pytestmark = pytest.mark.e2e


def _make_message(subject: str, msg_id: str) -> bytes:
    return textwrap.dedent(f"""\
        From: sender@test.com
        To: {E2E_USER}@localhost
        Subject: {subject}
        Message-ID: <{msg_id}>
        MIME-Version: 1.0
        Content-Type: text/plain

        E2E test message body.
    """).encode()


def _append(conn: imaplib.IMAP4, raw: bytes) -> None:
    conn.append("INBOX", None, imaplib.Time2Internaldate(time.time()), raw)


def _plain_connect(email_addr: str) -> imaplib.IMAP4:
    """Test-only connect: plain IMAP4 to localhost instead of Yahoo SSL."""
    conn = imaplib.IMAP4(E2E_HOST, E2E_PORT)
    conn.login(E2E_USER, E2E_PASS)
    return conn


# ---------------------------------------------------------------------------
# fetch_uids_since
# ---------------------------------------------------------------------------

class TestFetchUidsSince:
    def test_empty_inbox_returns_empty(self, imap_conn, monkeypatch):
        import sync.yahoo_reader as yr
        monkeypatch.setattr("auth.yahoo_auth.connect", _plain_connect)
        uids = yr.fetch_uids_since(E2E_USER, last_uid=0)
        assert uids == []

    def test_returns_uids_after_last(self, imap_conn, monkeypatch):
        import sync.yahoo_reader as yr
        monkeypatch.setattr("auth.yahoo_auth.connect", _plain_connect)

        _append(imap_conn, _make_message("Msg 1", "e2e-001@test"))
        _append(imap_conn, _make_message("Msg 2", "e2e-002@test"))

        uids = yr.fetch_uids_since(E2E_USER, last_uid=0)
        assert len(uids) == 2
        assert uids == sorted(uids)

    def test_respects_last_uid_filter(self, imap_conn, monkeypatch):
        import sync.yahoo_reader as yr
        monkeypatch.setattr("auth.yahoo_auth.connect", _plain_connect)

        _append(imap_conn, _make_message("Old msg", "e2e-old@test"))
        uids_all = yr.fetch_uids_since(E2E_USER, last_uid=0)
        assert len(uids_all) == 1

        _append(imap_conn, _make_message("New msg", "e2e-new@test"))
        uids_after = yr.fetch_uids_since(E2E_USER, last_uid=uids_all[0])
        assert len(uids_after) == 1
        assert uids_after[0] > uids_all[0]


# ---------------------------------------------------------------------------
# iter_new_messages
# ---------------------------------------------------------------------------

class TestIterNewMessages:
    def test_yields_rfc822_bytes(self, imap_conn, monkeypatch):
        import sync.yahoo_reader as yr
        monkeypatch.setattr("auth.yahoo_auth.connect", _plain_connect)

        raw = _make_message("Test subject", "e2e-iter-001@test")
        _append(imap_conn, raw)

        messages = list(yr.iter_new_messages(E2E_USER, last_uid=0))
        assert len(messages) == 1
        uid, msg_bytes = messages[0]
        assert isinstance(uid, int)
        assert isinstance(msg_bytes, bytes)

        parsed = email.message_from_bytes(msg_bytes)
        assert parsed["Subject"] == "Test subject"
        assert parsed["Message-ID"] == "<e2e-iter-001@test>"

    def test_multiple_messages_in_order(self, imap_conn, monkeypatch):
        import sync.yahoo_reader as yr
        monkeypatch.setattr("auth.yahoo_auth.connect", _plain_connect)

        for i in range(3):
            _append(imap_conn, _make_message(f"Msg {i}", f"e2e-order-{i:03d}@test"))

        messages = list(yr.iter_new_messages(E2E_USER, last_uid=0))
        assert len(messages) == 3

        uids = [uid for uid, _ in messages]
        assert uids == sorted(uids)

        subjects = [email.message_from_bytes(b)["Subject"] for _, b in messages]
        assert subjects == ["Msg 0", "Msg 1", "Msg 2"]

    def test_empty_inbox_yields_nothing(self, imap_conn, monkeypatch):
        import sync.yahoo_reader as yr
        monkeypatch.setattr("auth.yahoo_auth.connect", _plain_connect)

        messages = list(yr.iter_new_messages(E2E_USER, last_uid=0))
        assert messages == []
