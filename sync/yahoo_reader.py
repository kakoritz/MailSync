"""
Reads email from Yahoo IMAP using UIDs for stable, gap-free iteration.

A new IMAP connection is opened per sync run (stateless). Idle/push is not
used — the background scheduler handles polling cadence.
"""

import imaplib
import email as email_lib
from typing import Generator

from auth.yahoo_auth import connect, YahooAuthError


class YahooReadError(Exception):
    pass


def fetch_uids_since(yahoo_email: str, last_uid: int) -> list[int]:
    """Return all INBOX UIDs greater than last_uid, in ascending order."""
    conn = connect(yahoo_email)
    try:
        conn.select("INBOX", readonly=True)
        search_criterion = f"UID {last_uid + 1}:*"
        status, data = conn.uid("SEARCH", None, search_criterion)
        if status != "OK":
            raise YahooReadError(f"SEARCH failed: {status}")
        raw = data[0].decode() if data[0] else ""
        if not raw.strip():
            return []
        uids = [int(u) for u in raw.split()]
        return sorted(uids)
    except imaplib.IMAP4.error as exc:
        raise YahooReadError(f"IMAP error: {exc}") from exc
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def fetch_message_rfc822(yahoo_email: str, uid: int) -> bytes:
    """Fetch the full RFC822 bytes for a single UID."""
    conn = connect(yahoo_email)
    try:
        conn.select("INBOX", readonly=True)
        status, data = conn.uid("FETCH", str(uid), "(RFC822)")
        if status != "OK" or not data or data[0] is None:
            raise YahooReadError(f"FETCH failed for UID {uid}: {status}")
        return data[0][1]
    except imaplib.IMAP4.error as exc:
        raise YahooReadError(f"IMAP error fetching UID {uid}: {exc}") from exc
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def iter_new_messages(
    yahoo_email: str, last_uid: int
) -> Generator[tuple[int, bytes], None, None]:
    """Yield (uid, rfc822_bytes) for every message newer than last_uid.

    Opens one IMAP connection for the full batch (more efficient than one
    connection per message).
    """
    conn = connect(yahoo_email)
    try:
        conn.select("INBOX", readonly=True)
        search_criterion = f"UID {last_uid + 1}:*"
        status, data = conn.uid("SEARCH", None, search_criterion)
        if status != "OK":
            raise YahooReadError(f"SEARCH failed: {status}")

        raw = data[0].decode() if data[0] else ""
        if not raw.strip():
            return

        uids = sorted(int(u) for u in raw.split())
        for uid in uids:
            status, msg_data = conn.uid("FETCH", str(uid), "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                raise YahooReadError(f"FETCH failed for UID {uid}")
            yield uid, msg_data[0][1]
    except imaplib.IMAP4.error as exc:
        raise YahooReadError(f"IMAP error: {exc}") from exc
    finally:
        try:
            conn.logout()
        except Exception:
            pass
