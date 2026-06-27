"""
Android background service entry point.

Declared in buildozer.spec as:
  android.services = sync:service/sync_service.py

Runs as a separate process from the UI. Wakes every SYNC_INTERVAL_SECONDS,
executes a sync pass, and posts an Android notification with the result.

The UI refreshes its stats by reading the database on screen entry (on_enter).
No IPC is needed — both processes share the same SQLite file.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import database
from core.constants import SYNC_INTERVAL_SECONDS
from sync.sync_engine import run_sync


def _notify(title: str, message: str) -> None:
    try:
        from android.notifications import notify
        notify(title, message)
    except Exception:
        pass


def main() -> None:
    database.init()

    while True:
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

        time.sleep(SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
