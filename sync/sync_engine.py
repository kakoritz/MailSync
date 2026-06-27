"""
Orchestrates a full sync pass from Yahoo → Outlook.

The engine is stateless and idempotent: it reads the last synced UID from the
database, fetches only newer messages, and updates the UID after each
successful write. A failed write does not advance the UID, so the message
will be retried on the next run.
"""

import email as email_lib
from datetime import datetime, timezone
from typing import Callable

from core import database
from sync.yahoo_reader import iter_new_messages, YahooReadError
from sync.outlook_writer import import_message, message_exists, OutlookWriteError


class SyncResult:
    def __init__(self):
        self.emails_synced = 0
        self.errors: list[str] = []
        self.status = "success"


def run_sync(
    yahoo_email: str,
    outlook_email: str,
    progress_cb: Callable[[int], None] | None = None,
) -> SyncResult:
    """Execute one full sync pass.

    progress_cb(n) is called after each successful message write, where n is
    the running total for this run. Pass None to skip callbacks.
    """
    result = SyncResult()
    state = database.get_or_create_sync_state(yahoo_email, outlook_email)
    log_id = database.start_sync_log(state["id"])
    last_uid = state["last_yahoo_uid"]

    try:
        for uid, rfc822_bytes in iter_new_messages(yahoo_email, last_uid):
            try:
                msg = email_lib.message_from_bytes(rfc822_bytes)
                internet_id = msg.get("Message-ID", "").strip()

                if internet_id and message_exists(outlook_email, internet_id):
                    database.update_last_uid(yahoo_email, uid)
                    last_uid = uid
                    continue

                import_message(outlook_email, rfc822_bytes)
                database.update_last_uid(yahoo_email, uid)
                last_uid = uid
                result.emails_synced += 1

                if progress_cb:
                    progress_cb(result.emails_synced)

            except OutlookWriteError as exc:
                result.errors.append(f"UID {uid}: {exc}")
                result.status = "partial"
                break

    except YahooReadError as exc:
        result.errors.append(str(exc))
        result.status = "error"

    if result.status == "success" and not result.errors:
        database.finish_sync_log(log_id, result.emails_synced, "success")
    elif result.status == "partial":
        database.finish_sync_log(
            log_id, result.emails_synced, "partial",
            error_msg="; ".join(result.errors)
        )
    else:
        database.finish_sync_log(
            log_id, result.emails_synced, "error",
            error_msg="; ".join(result.errors)
        )

    return result
