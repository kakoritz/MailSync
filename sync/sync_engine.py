"""
Orchestrates a full sync pass from Yahoo → Outlook.

The engine is stateless and idempotent: it reads the last synced UID from the
database, fetches only newer messages, and updates the UID after each
successful write. A failed write does not advance the UID — the message will
be retried on the next run.

Optimisation — initial sync fast path:
  When last_yahoo_uid is 0 at the start of a run, the Outlook mailbox is
  guaranteed empty (we've never written anything). The message_exists() check
  is skipped entirely, saving one Graph API call per message — which matters
  on a first sync of a large inbox.

dry_run=True fetches and inspects messages but does not write to Outlook and
does not update any database state. Useful for verifying credentials and
counting pending messages without side effects.
"""

import email as email_lib
from typing import Callable

from core import database
from sync.yahoo_reader import iter_new_messages, YahooReadError
from sync.outlook_writer import import_message, message_exists, OutlookWriteError


class SyncResult:
    def __init__(self, dry_run: bool = False):
        self.emails_synced = 0
        self.emails_skipped = 0   # already existed in Outlook (dedup)
        self.emails_would_sync = 0  # dry_run only
        self.errors: list[str] = []
        self.status = "success"
        self.dry_run = dry_run


def run_sync(
    yahoo_email: str,
    outlook_email: str,
    progress_cb: Callable[[int], None] | None = None,
    dry_run: bool = False,
) -> SyncResult:
    """Execute one full sync pass.

    progress_cb(n) is called after each successful message write (or would-be
    write in dry_run mode), where n is the running total for this run.

    In dry_run mode: no messages are written to Outlook, no database state is
    updated, and the result reports emails_would_sync instead of emails_synced.
    """
    result = SyncResult(dry_run=dry_run)
    state = database.get_or_create_sync_state(yahoo_email, outlook_email)
    initial_last_uid = state["last_yahoo_uid"]
    last_uid = initial_last_uid

    # When initial_last_uid is 0 this is the first ever sync — Outlook is empty
    # so we can skip the per-message existence check entirely.
    is_initial_sync = (initial_last_uid == 0)

    log_id = None if dry_run else database.start_sync_log(state["id"])

    try:
        for uid, rfc822_bytes in iter_new_messages(yahoo_email, last_uid):
            try:
                if dry_run:
                    result.emails_would_sync += 1
                    if progress_cb:
                        progress_cb(result.emails_would_sync)
                    continue

                if not is_initial_sync:
                    msg = email_lib.message_from_bytes(rfc822_bytes)
                    internet_id = msg.get("Message-ID", "").strip()
                    if internet_id and message_exists(outlook_email, internet_id):
                        database.update_last_uid(yahoo_email, uid)
                        last_uid = uid
                        result.emails_skipped += 1
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

    if not dry_run:
        if result.status == "success":
            database.finish_sync_log(log_id, result.emails_synced, "success")
        elif result.status == "partial":
            database.finish_sync_log(
                log_id, result.emails_synced, "partial",
                error_msg="; ".join(result.errors),
            )
        else:
            database.finish_sync_log(
                log_id, 0, "error",
                error_msg="; ".join(result.errors),
            )

    return result
