"""
Orchestrates a full sync pass from Yahoo → Outlook.

The engine is stateless and idempotent: it reads the last synced UID from the
database, fetches only newer messages, and updates the UID after each
successful write. A failed write does not advance the UID — the message will
be retried on the next run.

Optimisation 1 — initial sync fast path:
  When last_yahoo_uid is 0 at the start of a run, the Outlook mailbox is
  guaranteed empty (we've never written anything). The message_exists() check
  is skipped entirely, saving one Graph API call per message.

Optimisation 2 — per-run Message-ID cache:
  Within a single run, Message-IDs written to Outlook are tracked in a set.
  If the same Message-ID appears again in the UID sequence (e.g. after a
  partial failure where the DB was updated but the run restarted), the cache
  hit avoids a redundant Graph API call. The cache is local to the run and
  never persisted.

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
        self.emails_skipped = 0    # already existed in Outlook (dedup)
        self.emails_cache_hit = 0  # short-circuited by per-run Message-ID cache
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

    # Opt 1: first-ever sync — Outlook is guaranteed empty
    is_initial_sync = (initial_last_uid == 0)

    # Opt 2: per-run cache of Message-IDs we've written this run
    written_ids: set[str] = set()

    log_id = None if dry_run else database.start_sync_log(state["id"])

    try:
        for uid, rfc822_bytes in iter_new_messages(yahoo_email, last_uid):
            try:
                if dry_run:
                    result.emails_would_sync += 1
                    if progress_cb:
                        progress_cb(result.emails_would_sync)
                    continue

                msg = email_lib.message_from_bytes(rfc822_bytes)
                internet_id = msg.get("Message-ID", "").strip()

                if not is_initial_sync and internet_id:
                    # Check per-run cache first (free)
                    if internet_id in written_ids:
                        database.update_last_uid(yahoo_email, uid)
                        last_uid = uid
                        result.emails_cache_hit += 1
                        continue

                    # Fall back to Graph API existence check
                    if message_exists(outlook_email, internet_id):
                        database.update_last_uid(yahoo_email, uid)
                        last_uid = uid
                        result.emails_skipped += 1
                        continue

                import_message(outlook_email, rfc822_bytes)
                database.update_last_uid(yahoo_email, uid)
                last_uid = uid
                result.emails_synced += 1

                if internet_id:
                    written_ids.add(internet_id)

                if progress_cb:
                    progress_cb(result.emails_synced)

            except OutlookWriteError as exc:
                result.errors.append(f"UID {uid}: {exc}")
                result.status = "partial"
                break

    except YahooReadError as exc:
        result.errors.append(str(exc))
        result.status = "error"

    if dry_run:
        database.update_pending_emails(yahoo_email, result.emails_would_sync)
    else:
        if result.status == "success":
            database.finish_sync_log(log_id, result.emails_synced, "success")
            database.update_pending_emails(yahoo_email, 0)
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
