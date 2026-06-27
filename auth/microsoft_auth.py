"""
Microsoft OAuth2 via MSAL Device Code Flow.

No redirect URI or web server needed. The user visits aka.ms/devicelogin,
enters the code shown by the app, and signs in. The app polls until the
token is acquired.

The Azure App Registration must have:
  - "Mobile and desktop applications" platform enabled
  - The device code flow enabled (no client secret needed for public client)
  - Scopes: Mail.ReadWrite, offline_access
"""

import json
import time

import msal

from auth import token_store
from core.constants import GRAPH_SCOPES

_CLIENT_ID = "YOUR_AZURE_CLIENT_ID"  # set via MAILSYNC_CLIENT_ID env var or config
_AUTHORITY = "https://login.microsoftonline.com/common"


def _build_app(client_id: str) -> msal.PublicClientApplication:
    return msal.PublicClientApplication(client_id, authority=_AUTHORITY)


def _client_id() -> str:
    import os
    return os.getenv("MAILSYNC_CLIENT_ID", _CLIENT_ID)


def initiate_device_flow() -> dict:
    """Start the Device Code Flow.

    Returns a dict with 'message' (display to user), 'user_code', and
    'verification_uri'. Call poll_device_flow() to wait for completion.
    """
    app = _build_app(_client_id())
    flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
    if "error" in flow:
        raise RuntimeError(f"Device flow error: {flow.get('error_description', flow)}")
    return flow


def poll_device_flow(flow: dict, timeout_seconds: int = 300) -> tuple[str, str]:
    """Block until the user completes sign-in or timeout expires.

    Returns (email, token_json) on success. Raises RuntimeError on failure.
    """
    app = _build_app(_client_id())
    result = app.acquire_token_by_device_flow(flow)

    if "error" in result:
        raise RuntimeError(
            f"Auth failed: {result.get('error_description', result['error'])}"
        )

    email = result.get("id_token_claims", {}).get("preferred_username", "")
    if not email:
        email = result.get("id_token_claims", {}).get("email", "unknown@outlook.com")

    token_json = json.dumps(result)
    token_store.save_microsoft_token(email, token_json)
    del token_json

    return email, result


def get_access_token(email: str) -> str:
    """Return a valid access token, refreshing silently if needed."""
    raw = token_store.load_microsoft_token(email)
    cached = json.loads(raw)
    del raw

    app = _build_app(_client_id())

    accounts = app.get_accounts(username=email)
    if accounts:
        result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])
        if result and "access_token" in result:
            return result["access_token"]

    if "refresh_token" in cached:
        result = app.acquire_token_by_refresh_token(
            cached["refresh_token"], scopes=GRAPH_SCOPES
        )
        if result and "access_token" in result:
            token_store.save_microsoft_token(email, json.dumps(result))
            return result["access_token"]

    raise RuntimeError(
        f"Cannot refresh token for {email}. Re-authentication required."
    )
