"""
Writes RFC822 messages to Microsoft Outlook via the Microsoft Graph API.

Uses the raw MIME import endpoint (Content-Type: message/rfc822), which
preserves all headers, attachments, and body parts exactly as received
from Yahoo IMAP.
"""

import time

import requests

from auth.microsoft_auth import get_access_token
from core.constants import GRAPH_API_BASE


class OutlookWriteError(Exception):
    pass


_RETRY_DELAYS = (2, 4, 8)  # seconds between retries on 429 / 5xx


def import_message(outlook_email: str, rfc822_bytes: bytes) -> str:
    """Import a raw RFC822 message into the Outlook Inbox.

    Retries with exponential backoff on 429 (rate limit) and 5xx responses.
    Retries once with a fresh token on 401.
    Returns the Graph API message ID on success.
    """
    url = f"{GRAPH_API_BASE}/users/{outlook_email}/messages"

    def _post(token: str) -> requests.Response:
        return requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "message/rfc822",
            },
            data=rfc822_bytes,
            timeout=30,
        )

    token = get_access_token(outlook_email)
    resp = _post(token)

    if resp.status_code == 401:
        token = get_access_token(outlook_email)
        resp = _post(token)

    for delay in _RETRY_DELAYS:
        if resp.status_code == 429 or resp.status_code >= 500:
            retry_after = int(resp.headers.get("Retry-After", delay))
            time.sleep(retry_after)
            resp = _post(get_access_token(outlook_email))
        else:
            break

    if resp.status_code not in (200, 201):
        raise OutlookWriteError(
            f"Graph API error {resp.status_code}: {resp.text[:200]}"
        )

    return resp.json().get("id", "")


def message_exists(outlook_email: str, internet_message_id: str) -> bool:
    """Return True if a message with this Message-ID already exists in Outlook.

    Used for idempotency — prevents duplicates when a sync run is retried.
    """
    url = (
        f"{GRAPH_API_BASE}/users/{outlook_email}/messages"
        f"?$filter=internetMessageId eq '{internet_message_id}'"
        f"&$select=id&$top=1"
    )
    try:
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {get_access_token(outlook_email)}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return False
        return len(resp.json().get("value", [])) > 0
    except requests.RequestException:
        return False
