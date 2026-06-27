"""
Reads email from Yahoo IMAP using UIDs for stable, gap-free iteration.

A new IMAP connection is opened per sync run (stateless). Idle/push is not
used — the background scheduler handles polling cadence.

EXPUNGE safety: if a message is deleted from Yahoo between the SEARCH and
FETCH, the FETCH returns a NIL response. We skip those UIDs with a warning
rather than raising, so the sync run continues and the UID is still advanced
(the message is gone; there's nothing to migrate).
"""

import imaplib
import logging
from typing import Generator

from auth.yahoo_auth import connect, YahooAuthError

logger = logging.getLogger(__name__)


class YahooReadError(Exception):
    pass


def fetch_uids_since(yahoo_email: str, last_uid: int) -> list[int]:
    """Return all INBOX UIDs greater than last_uid, in ascending order."""
    conn = connect(yahoo_email)
    try:
        conn.select("INBOX", readonly=True)
        status, data = conn.uid("SEARCH", None, f"UID {last_uid + 1}:*")
        if status != "OK":
            raise YahooReadError(f"SEARCH failed: {status}")
        raw = data[0].decode() if data[0] else ""
        return sorted(int(u) for u in raw.split()) if raw.strip() else []
    except imaplib.IMAP4.error as exc:
        raise YahooReadError(f"IMAP error: {exc}") from exc
    finally:
        _safe_logout(conn)


def iter_new_messages(
    yahoo_email: str, last_uid: int
) -> Generator[tuple[int, bytes], None, None]:
    """Yield (uid, rfc822_bytes) for every message newer than last_uid.

    Opens one IMAP connection for the full batch. UIDs that no longer exist
    (deleted between SEARCH and FETCH) are skipped with a log warning; the
    UID is still yielded with a sentinel so the caller can advance last_uid.

    Actually: expunged UIDs return NIL data — we skip them silently (they
    can't be migrated and there's nothing meaningful to do with them).
    """
    conn = connect(yahoo_email)
    try:
        conn.select("INBOX", readonly=True)
        status, data = conn.uid("SEARCH", None, f"UID {last_uid + 1}:*")
        if status != "OK":
            raise YahooReadError(f"SEARCH failed: {status}")

        raw = data[0].decode() if data[0] else ""
        if not raw.strip():
            return

        uids = sorted(int(u) for u in raw.split())
        for uid in uids:
            status, msg_data = conn.uid("FETCH", str(uid), "(RFC822)")
            if status != "OK":
                raise YahooReadError(f"FETCH failed for UID {uid}: status={status}")

            # NIL response means the message was expunged after SEARCH
            if not msg_data or msg_data[0] is None:
                logger.warning("YahooReader: UID %d returned NIL (expunged) — skipping", uid)
                continue

            yield uid, msg_data[0][1]

    except imaplib.IMAP4.error as exc:
        raise YahooReadError(f"IMAP error: {exc}") from exc
    finally:
        _safe_logout(conn)


def _safe_logout(conn: imaplib.IMAP4_SSL) -> None:
    try:
        conn.logout()
    except Exception:
        pass
