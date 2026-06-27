"""
Writes RFC822 messages to Microsoft Outlook via the Graph API.

Endpoint: POST /users/{email}/messages (MIME import)
Docs: https://learn.microsoft.com/en-us/graph/api/user-sendmail

Each message is uploaded as a raw MIME blob. Graph API preserves all
headers, attachments, and body parts. Messages land in the Inbox.
"""

import base64

import requests

from auth.microsoft_auth import get_access_token
from core.constants import GRAPH_API_BASE


class OutlookWriteError(Exception):
    pass


def _headers(outlook_email: str) -> dict:
    token = get_access_token(outlook_email)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain",
    }


def import_message(outlook_email: str, rfc822_bytes: bytes) -> str:
    """Import a raw RFC822 message into the Outlook Inbox.

    Returns the Graph API message ID on success.
    """
    url = f"{GRAPH_API_BASE}/users/{outlook_email}/messages"
    headers = {
        **_headers(outlook_email),
        "Content-Type": "application/json",
    }

    import json
    payload = {
        "message": {},
        "saveToSentItems": False,
    }

    # Use the createUploadSession / direct MIME import path
    # Graph supports raw MIME via the $value endpoint after message creation,
    # but the simpler path is: POST /messages with body as base64 MIME.
    mime_b64 = base64.b64encode(rfc822_bytes).decode()
    payload = {
        "message": {
            "body": {
                "contentType": "html",
                "content": "",
            }
        }
    }

    # Preferred: directly POST MIME to /messages/$value (Graph MIME import)
    mime_url = f"{GRAPH_API_BASE}/users/{outlook_email}/messages"
    mime_headers = {
        "Authorization": f"Bearer {get_access_token(outlook_email)}",
        "Content-Type": "message/rfc822",
    }
    resp = requests.post(mime_url, headers=mime_headers, data=rfc822_bytes, timeout=30)

    if resp.status_code == 401:
        # Token may have just expired mid-batch; retry once with a fresh token
        mime_headers["Authorization"] = f"Bearer {get_access_token(outlook_email)}"
        resp = requests.post(mime_url, headers=mime_headers, data=rfc822_bytes, timeout=30)

    if resp.status_code not in (200, 201):
        raise OutlookWriteError(
            f"Graph API error {resp.status_code}: {resp.text[:200]}"
        )

    return resp.json().get("id", "")


def message_exists(outlook_email: str, internet_message_id: str) -> bool:
    """Check if a message with the given Message-ID header already exists.

    Used for idempotency — prevents duplicates if a sync run is interrupted
    and restarted at the same UID.
    """
    url = (
        f"{GRAPH_API_BASE}/users/{outlook_email}/messages"
        f"?$filter=internetMessageId eq '{internet_message_id}'"
        f"&$select=id&$top=1"
    )
    headers = _headers(outlook_email)
    headers["Content-Type"] = "application/json"
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        return False
    return len(resp.json().get("value", [])) > 0
