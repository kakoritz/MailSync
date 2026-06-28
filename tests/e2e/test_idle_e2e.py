"""
E2E tests for IdleMonitor against a real Dovecot IMAP server.

Verifies that:
  - The IDLE connection is established and the server pushes EXISTS
  - The on_new_mail callback fires within a few seconds of APPEND
  - stop() cleanly terminates the monitor without hanging

Start the server before running:
    docker-compose -f docker-compose.test.yml up -d
    pytest tests/e2e/ -m e2e -q
"""

import imaplib
import threading
import time

import pytest

from sync.imap_idle import IdleMonitor
from tests.e2e.conftest import E2E_HOST, E2E_PORT, E2E_USER, E2E_PASS


pytestmark = pytest.mark.e2e

_CALLBACK_TIMEOUT = 10  # seconds to wait for the on_new_mail callback


def _plain_connect(email_addr: str) -> imaplib.IMAP4:
    conn = imaplib.IMAP4(E2E_HOST, E2E_PORT)
    conn.login(E2E_USER, E2E_PASS)
    return conn


def _append_message(subject: str) -> None:
    """Append a message to INBOX using a separate connection."""
    conn = imaplib.IMAP4(E2E_HOST, E2E_PORT)
    conn.login(E2E_USER, E2E_PASS)
    raw = (
        f"From: test@test.com\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: <idle-e2e-{time.time()}@test>\r\n"
        f"\r\nBody\r\n"
    ).encode()
    conn.append("INBOX", None, imaplib.Time2Internaldate(time.time()), raw)
    conn.logout()


class TestIdleMonitorE2E:
    def test_callback_fires_on_append(self, imap_conn, monkeypatch):
        """IDLE monitor receives EXISTS push when a message is APPENDed."""
        monkeypatch.setattr("auth.yahoo_auth.connect", _plain_connect)

        fired = threading.Event()
        monitor = IdleMonitor(E2E_USER, on_new_mail=fired.set)
        monitor.start()

        # Give IDLE time to establish before appending
        time.sleep(1)

        _append_message("IDLE trigger test")

        assert fired.wait(timeout=_CALLBACK_TIMEOUT), (
            f"on_new_mail was not called within {_CALLBACK_TIMEOUT}s of APPEND"
        )
        monitor.stop()

    def test_stop_terminates_cleanly(self, imap_conn, monkeypatch):
        """stop() returns promptly without hanging."""
        monkeypatch.setattr("auth.yahoo_auth.connect", _plain_connect)

        monitor = IdleMonitor(E2E_USER, on_new_mail=lambda: None)
        monitor.start()
        time.sleep(1)

        t0 = time.monotonic()
        monitor.stop()
        if monitor._thread:
            monitor._thread.join(timeout=5)
        elapsed = time.monotonic() - t0

        assert elapsed < 5, f"stop() took too long: {elapsed:.1f}s"
        assert not monitor.is_running

    def test_callback_fires_multiple_times(self, imap_conn, monkeypatch):
        """Each appended message triggers a separate callback."""
        monkeypatch.setattr("auth.yahoo_auth.connect", _plain_connect)

        call_count = 0
        lock = threading.Lock()

        def on_mail():
            nonlocal call_count
            with lock:
                call_count += 1

        monitor = IdleMonitor(E2E_USER, on_new_mail=on_mail)
        monitor.start()

        time.sleep(1)
        _append_message("First message")
        time.sleep(_CALLBACK_TIMEOUT / 2)
        _append_message("Second message")
        time.sleep(_CALLBACK_TIMEOUT / 2)

        monitor.stop()

        with lock:
            assert call_count >= 2, f"Expected at least 2 callbacks, got {call_count}"
