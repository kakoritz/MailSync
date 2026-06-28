"""
Android background service entry point.

Declared in buildozer.spec as:
  android.services = sync:service/sync_service.py

Runs as a separate process from the UI. On each iteration:
  1. Run a sync pass immediately.
  2. Open an IMAP IDLE connection — wait for the server to push an EXISTS
     notification or for the configured max-interval fallback timer to fire.
  3. Repeat.

This means new mail triggers a sync within seconds rather than up to an hour.
The configured interval acts only as a fallback in case IDLE is disrupted.

SIGTERM triggers a clean stop after the current sync finishes.
"""

import os
import signal
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import database, config
from core.constants import SYNC_INTERVAL_SECONDS
from service import notification_helper
from sync.sync_engine import run_sync

_stop_event = threading.Event()


def _handle_sigterm(_signum, _frame) -> None:
    _stop_event.set()


signal.signal(signal.SIGTERM, _handle_sigterm)


def _get_interval() -> int:
    return config.get("sync_interval_seconds") or SYNC_INTERVAL_SECONDS


def _do_sync(yahoo_email: str, outlook_email: str) -> None:
    try:
        result = run_sync(yahoo_email, outlook_email)
        if result.emails_synced > 0:
            notification_helper.send_notification(
                "MailSync", f"Synced {result.emails_synced} new email(s) from Yahoo."
            )
        if result.status == "error" and result.errors:
            notification_helper.send_notification("MailSync — Sync Error", result.errors[0])
    except Exception as exc:
        notification_helper.send_notification("MailSync — Error", str(exc)[:120])


def _wait_for_new_mail(yahoo_email: str) -> None:
    """Use IMAP IDLE push; fall back to polling at max interval."""
    from sync.imap_idle import IdleMonitor

    new_mail_event = threading.Event()

    def on_new_mail():
        database.update_idle_last_seen(yahoo_email)
        new_mail_event.set()

    monitor = IdleMonitor(yahoo_email, on_new_mail=on_new_mail)
    monitor.start()

    # Wait until: (a) new mail arrives, (b) max interval elapsed, (c) SIGTERM
    new_mail_event.wait(timeout=_get_interval())
    _stop_event.wait(timeout=0)  # check stop without blocking

    monitor.stop()
    if monitor._thread:
        monitor._thread.join(timeout=5)


def main() -> None:
    notification_helper.create_channel()
    database.init()

    while not _stop_event.is_set():
        yahoo_rows = database.get_accounts_by_service("yahoo")
        ms_rows = database.get_accounts_by_service("microsoft")

        if yahoo_rows and ms_rows:
            yahoo_email = yahoo_rows[0]["email"]
            outlook_email = ms_rows[0]["email"]

            _do_sync(yahoo_email, outlook_email)

            if not _stop_event.is_set():
                _wait_for_new_mail(yahoo_email)
        else:
            # No accounts configured yet — check again in 60 s
            _stop_event.wait(60)


if __name__ == "__main__":
    main()
