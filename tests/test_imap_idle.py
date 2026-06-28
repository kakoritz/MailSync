"""
IMAP IDLE monitor tests.

All tests mock `auth.yahoo_auth.connect` to return a fake IMAP connection
whose readline() returns scripted byte sequences. This avoids any network
calls and keeps tests deterministic.
"""

import socket
import threading
import time

import pytest
from unittest.mock import MagicMock, patch

from sync.imap_idle import IdleMonitor, _IDLE_TAG


YAHOO = "user@yahoo.com"


def _make_conn(*readline_responses):
    """Return a mock IMAP connection with scripted readline() responses."""
    conn = MagicMock()
    conn.readline.side_effect = list(readline_responses)
    mock_socket = MagicMock()
    conn.socket.return_value = mock_socket
    return conn


def _monitor_with_conn(conn, callback=None):
    """Convenience: return an IdleMonitor patched to use `conn`."""
    cb = callback or (lambda: None)
    monitor = IdleMonitor(YAHOO, on_new_mail=cb)
    return monitor, patch("sync.imap_idle.connect", return_value=conn)


# ---------------------------------------------------------------------------
# Callback firing
# ---------------------------------------------------------------------------

def test_exists_fires_callback():
    """Server sending EXISTS triggers on_new_mail and monitor exits."""
    fired = threading.Event()

    conn = _make_conn(
        b"+ idling\r\n",           # IDLE continuation
        b"* 5 EXISTS\r\n",         # new mail notification
        _IDLE_TAG + b" OK IDLE terminated\r\n",  # DONE response
    )

    monitor = IdleMonitor(YAHOO, on_new_mail=lambda: (fired.set(), monitor.stop()))

    with patch("auth.yahoo_auth.connect", return_value=conn):
        monitor.start()
        assert fired.wait(timeout=2), "on_new_mail was not called within 2s"
        if monitor._thread:
            monitor._thread.join(timeout=2)

    assert not monitor.is_running


def test_recent_fires_callback():
    """RECENT notification (some servers send this) also triggers callback."""
    fired = threading.Event()

    conn = _make_conn(
        b"+ idling\r\n",
        b"* 2 RECENT\r\n",
        _IDLE_TAG + b" OK IDLE terminated\r\n",
    )

    monitor = IdleMonitor(YAHOO, on_new_mail=lambda: (fired.set(), monitor.stop()))

    with patch("auth.yahoo_auth.connect", return_value=conn):
        monitor.start()
        assert fired.wait(timeout=2)


def test_unrelated_server_response_does_not_fire():
    """FLAGS updates and other unrelated responses don't trigger callback."""
    fired = threading.Event()

    conn = _make_conn(
        b"+ idling\r\n",
        b"* 1 FETCH (FLAGS (\\Seen))\r\n",  # unrelated — ignored
        b"* 3 EXISTS\r\n",                   # this should fire
        _IDLE_TAG + b" OK IDLE terminated\r\n",
    )

    monitor = IdleMonitor(YAHOO, on_new_mail=lambda: (fired.set(), monitor.stop()))

    with patch("auth.yahoo_auth.connect", return_value=conn):
        monitor.start()
        assert fired.wait(timeout=2)

    assert fired.is_set()


# ---------------------------------------------------------------------------
# Timeout / keepalive
# ---------------------------------------------------------------------------

def test_socket_timeout_triggers_reidle():
    """On socket.timeout (25-min keepalive), monitor sends DONE, re-enters IDLE,
    and does NOT fire the callback until EXISTS arrives."""
    fired = threading.Event()

    # Readline sequence:
    # 1. b"+ idling"          — first IDLE continuation
    # 2. socket.timeout       — 25-min keepalive fires in _wait_for_notification
    # 3. A001 OK terminated   — _exit_idle reads the DONE response
    # 4. b"+ idling"          — second IDLE continuation
    # 5. b"* 7 EXISTS"        — new mail on second IDLE
    # 6. A001 OK terminated   — _exit_idle before callback
    conn = _make_conn(
        b"+ idling\r\n",
        socket.timeout("keepalive"),
        _IDLE_TAG + b" OK IDLE terminated\r\n",
        b"+ idling\r\n",
        b"* 7 EXISTS\r\n",
        _IDLE_TAG + b" OK IDLE terminated\r\n",
    )

    monitor = IdleMonitor(YAHOO, on_new_mail=lambda: (fired.set(), monitor.stop()))

    with patch("auth.yahoo_auth.connect", return_value=conn):
        monitor.start()
        assert fired.wait(timeout=3), "on_new_mail not called after re-IDLE"

    assert fired.is_set()


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

def test_stop_exits_cleanly():
    """stop() causes the monitor thread to exit without waiting for new mail."""
    conn = _make_conn(
        b"+ idling\r\n",
        OSError("socket closed by stop()"),  # simulate stop() closing socket
    )

    monitor = IdleMonitor(YAHOO, on_new_mail=lambda: None)

    with patch("auth.yahoo_auth.connect", return_value=conn):
        monitor.start()
        time.sleep(0.05)  # let it enter IDLE
        monitor.stop()
        if monitor._thread:
            monitor._thread.join(timeout=2)

    assert not monitor.is_running


def test_start_idempotent():
    """Calling start() twice does not spawn a second thread."""
    conn = _make_conn(
        b"+ idling\r\n",
        OSError("closed"),
    )

    monitor = IdleMonitor(YAHOO, on_new_mail=lambda: None)

    with patch("auth.yahoo_auth.connect", return_value=conn):
        monitor.start()
        t1 = monitor._thread
        monitor.start()
        t2 = monitor._thread
        monitor.stop()

    assert t1 is t2


# ---------------------------------------------------------------------------
# Reconnect
# ---------------------------------------------------------------------------

def test_reconnects_on_bye():
    """* BYE from the server causes reconnect; second connection delivers mail."""
    fired = threading.Event()
    connect_calls = [0]
    conns = []

    def make_conn(_email):
        connect_calls[0] += 1
        if connect_calls[0] == 1:
            c = _make_conn(
                b"+ idling\r\n",
                b"* BYE Server shutting down\r\n",
            )
        else:
            c = _make_conn(
                b"+ idling\r\n",
                b"* 3 EXISTS\r\n",
                _IDLE_TAG + b" OK IDLE terminated\r\n",
            )
        conns.append(c)
        return c

    monitor = IdleMonitor(YAHOO, on_new_mail=lambda: (fired.set(), monitor.stop()))

    # Patch reconnect delays to 0 so the test doesn't wait 5 real seconds
    with patch("sync.imap_idle._RECONNECT_DELAYS", (0, 0, 0, 0)), \
         patch("auth.yahoo_auth.connect", side_effect=make_conn):
        monitor.start()
        assert fired.wait(timeout=3), "reconnect + callback not called within 3s"

    assert connect_calls[0] == 2
