"""
IMAP IDLE push monitor (RFC 2177).

Replaces the polling model: instead of waking up every N minutes to check for
new mail, the IDLE connection stays open and the Yahoo server pushes an EXISTS
notification the moment a new message arrives. Sync fires immediately.

Architecture:
  IdleMonitor runs in a daemon thread. When the server sends EXISTS or RECENT,
  it calls on_new_mail() and then re-enters IDLE for the next message.

  25-minute keepalive: most IMAP servers drop idle connections after 30 minutes.
  At 25 minutes we send DONE + IDLE to reset the timer.

  Reconnect with exponential backoff on any connection error.

Protocol (raw bytes, bypassing imaplib's normal command/response machinery):
  C: A001 IDLE\r\n
  S: + idling\r\n
  ... server may push: * 5 EXISTS\r\n ...
  C: DONE\r\n
  S: A001 OK IDLE terminated\r\n
"""

import logging
import socket
import threading
from typing import Callable

logger = logging.getLogger(__name__)

_IDLE_TIMEOUT = 25 * 60        # re-IDLE before most servers' 30-min cutoff
_IDLE_TAG = b"A001"            # fixed tag — one IDLE command at a time per connection
_RECONNECT_DELAYS = (5, 15, 60, 300)  # seconds between reconnect attempts


class IdleMonitor:
    """Holds a persistent IMAP IDLE connection and fires on_new_mail on EXISTS."""

    def __init__(self, yahoo_email: str, on_new_mail: Callable[[], None]):
        self._email = yahoo_email
        self._on_new_mail = on_new_mail
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._conn = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        # Interrupt any blocking readline() by closing the socket
        if self._conn is not None:
            try:
                self._conn.socket().close()
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # --- internal ---

    def _run(self) -> None:
        delay_idx = 0
        while not self._stop_event.is_set():
            try:
                self._connect_and_idle()
                delay_idx = 0
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                delay = _RECONNECT_DELAYS[min(delay_idx, len(_RECONNECT_DELAYS) - 1)]
                logger.warning("IdleMonitor: reconnecting in %ds after: %s", delay, exc)
                delay_idx += 1
                self._stop_event.wait(delay)

    def _connect_and_idle(self) -> None:
        from auth.yahoo_auth import connect
        self._conn = connect(self._email)
        try:
            self._conn.select("INBOX")
            while not self._stop_event.is_set():
                self._enter_idle()
                fired = self._wait_for_notification()
                if not self._stop_event.is_set():
                    self._exit_idle()
                if fired and not self._stop_event.is_set():
                    try:
                        self._on_new_mail()
                    except Exception as exc:
                        logger.warning("IdleMonitor: on_new_mail error: %s", exc)
        finally:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None

    def _enter_idle(self) -> None:
        """Send IDLE and consume the server's continuation response."""
        self._conn.send(_IDLE_TAG + b" IDLE\r\n")
        resp = self._conn.readline()
        if not resp.startswith(b"+"):
            raise RuntimeError(f"IDLE rejected by server: {resp!r}")
        self._conn.socket().settimeout(_IDLE_TIMEOUT)

    def _wait_for_notification(self) -> bool:
        """Block until EXISTS/RECENT, server 25-min timeout, or stop().

        Returns True if new mail was signalled, False on timeout/stop.
        """
        fired = False
        try:
            while not self._stop_event.is_set():
                line = self._conn.readline()
                if not line:
                    raise ConnectionResetError("Server closed IDLE connection")
                if b"* BYE" in line:
                    raise ConnectionResetError(f"Server sent BYE: {line!r}")
                if b"EXISTS" in line or b"RECENT" in line:
                    fired = True
                    break
        except OSError:
            # Socket closed — either stop() was called or a network error
            pass
        except socket.timeout:
            # 25 minutes elapsed; re-IDLE to reset the server timer
            pass
        return fired

    def _exit_idle(self) -> None:
        """Send DONE and drain the tagged completion response."""
        try:
            self._conn.socket().settimeout(10)
            self._conn.send(b"DONE\r\n")
            for _ in range(20):
                line = self._conn.readline()
                if not line or _IDLE_TAG in line:
                    break
        except Exception:
            pass
        finally:
            try:
                self._conn.socket().settimeout(None)
            except Exception:
                pass
