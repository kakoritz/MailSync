"""
Android background service entry point.

Declared in buildozer.spec as:
  android.services = sync:service/sync_service.py

Runs independently of the UI process. Wakes every SYNC_INTERVAL_SECONDS,
runs a sync pass, and posts a notification with the result.

Communication back to the UI is via OSC on localhost.
"""

import time
import os
import sys

# Ensure the project root is on the path so core/sync/auth imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import database
from core.constants import SYNC_INTERVAL_SECONDS, OSC_HOST, OSC_PORT_UI
from sync.sync_engine import run_sync


def _post_notification(title: str, message: str) -> None:
    try:
        from android.notifications import notify
        notify(title, message)
    except Exception:
        pass


def _notify_ui(emails_synced: int) -> None:
    try:
        from kivy.lib.osc import oscAPI
        oscAPI.sendMsg("/sync_done", [emails_synced], host=OSC_HOST, port=OSC_PORT_UI)
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
                    _post_notification(
                        "MailSync",
                        f"Synced {result.emails_synced} new email(s) from Yahoo.",
                    )
                    _notify_ui(result.emails_synced)

                if result.status == "error":
                    _post_notification(
                        "MailSync — Sync Error",
                        result.errors[0] if result.errors else "Unknown error",
                    )

            except Exception as exc:
                _post_notification("MailSync — Error", str(exc))

        time.sleep(SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
