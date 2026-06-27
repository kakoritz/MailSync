"""
Android background service entry point.

Declared in buildozer.spec as:
  android.services = sync:service/sync_service.py

Runs as a separate process from the UI. Wakes every sync_interval_seconds
(read from config, default 3600), executes a sync pass, and posts an Android
notification with the result.

The UI refreshes its stats by reading the database on screen entry (on_enter).
No IPC is needed — both processes share the same SQLite file.

Signal handling: SIGTERM triggers a clean stop after the current sync finishes.
"""

import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import database, config
from core.constants import SYNC_INTERVAL_SECONDS
from sync.sync_engine import run_sync

_running = True


def _handle_sigterm(_signum, _frame) -> None:
    global _running
    _running = False


signal.signal(signal.SIGTERM, _handle_sigterm)


def _notify(title: str, message: str) -> None:
    try:
        from android.notifications import notify
        notify(title, message)
    except Exception:
        pass


def _get_interval() -> int:
    return config.get("sync_interval_seconds") or SYNC_INTERVAL_SECONDS


def main() -> None:
    database.init()

    while _running:
        yahoo_rows = database.get_accounts_by_service("yahoo")
        ms_rows = database.get_accounts_by_service("microsoft")

        if yahoo_rows and ms_rows:
            yahoo_email = yahoo_rows[0]["email"]
            outlook_email = ms_rows[0]["email"]

            try:
                result = run_sync(yahoo_email, outlook_email)

                if result.emails_synced > 0:
                    _notify(
                        "MailSync",
                        f"Synced {result.emails_synced} new email(s) from Yahoo.",
                    )

                if result.status == "error" and result.errors:
                    _notify("MailSync — Sync Error", result.errors[0])

            except Exception as exc:
                _notify("MailSync — Error", str(exc)[:120])

        interval = _get_interval()
        # Sleep in 10-second slices so SIGTERM is handled promptly
        elapsed = 0
        while _running and elapsed < interval:
            time.sleep(min(10, interval - elapsed))
            elapsed += 10


if __name__ == "__main__":
    main()
