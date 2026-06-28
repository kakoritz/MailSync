"""
Microsoft OAuth2 via MSAL Device Code Flow.

No redirect URI or web server needed. The user visits aka.ms/devicelogin,
enters the code shown by the app, and signs in. The app polls until the
token is acquired.

Token cache is serialized via MSAL's SerializableTokenCache and stored in the
encrypted credential store. This means silent token refresh survives process
restarts and the background service doesn't need to re-authenticate.

Azure App Registration requirements:
  - Platform: Mobile and desktop applications
  - Scopes: Mail.ReadWrite, offline_access
  - Client ID set via MAILSYNC_CLIENT_ID environment variable
"""

import json
import os

import msal

from auth import token_store
from core.constants import GRAPH_SCOPES

_CLIENT_ID_PLACEHOLDER = "YOUR_AZURE_CLIENT_ID"
_AUTHORITY = "https://login.microsoftonline.com/common"
_CACHE_SUFFIX = ":msal_cache"


def _client_id() -> str:
    return os.getenv("MAILSYNC_CLIENT_ID", _CLIENT_ID_PLACEHOLDER)


def _load_cache(email: str) -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    try:
        raw = token_store.load_microsoft_token(email + _CACHE_SUFFIX)
        cache.deserialize(raw)
    except (KeyError, Exception):
        pass
    return cache


def _save_cache(email: str, cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        token_store.save_microsoft_token(email + _CACHE_SUFFIX, cache.serialize())


def _build_app(client_id: str, cache: msal.SerializableTokenCache | None = None):
    return msal.PublicClientApplication(
        client_id,
        authority=_AUTHORITY,
        token_cache=cache,
    )


def initiate_device_flow() -> dict:
    """Start the Device Code Flow.

    Returns a dict with 'message', 'user_code', and 'verification_uri'.
    Pass the returned dict to poll_device_flow() to wait for completion.
    """
    app = _build_app(_client_id())
    flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
    if "error" in flow:
        raise RuntimeError(f"Device flow error: {flow.get('error_description', flow)}")
    return flow


def poll_device_flow(flow: dict) -> tuple[str, dict]:
    """Block until the user completes sign-in or the flow expires.

    Returns (email, result_dict) on success. Raises RuntimeError on failure.
    """
    cache = msal.SerializableTokenCache()
    app = _build_app(_client_id(), cache)
    result = app.acquire_token_by_device_flow(flow)

    if "error" in result:
        raise RuntimeError(
            f"Auth failed: {result.get('error_description', result['error'])}"
        )

    claims = result.get("id_token_claims", {})
    email = claims.get("preferred_username") or claims.get("email") or "unknown@outlook.com"

    token_store.save_microsoft_token(email, json.dumps(result))
    _save_cache(email, cache)

    return email, result


def get_access_token(email: str) -> str:
    """Return a valid access token, refreshing silently if needed.

    Uses the serialized MSAL token cache so refresh survives process restarts.
    Raises RuntimeError if re-authentication is required.
    """
    cache = _load_cache(email)
    app = _build_app(_client_id(), cache)

    accounts = app.get_accounts(username=email)
    if accounts:
        result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_cache(email, cache)
            return result["access_token"]

    # Fall back to the raw refresh token stored from the last successful auth
    try:
        raw = token_store.load_microsoft_token(email)
        cached = json.loads(raw)
        del raw
        if "refresh_token" in cached:
            result = app.acquire_token_by_refresh_token(
                cached["refresh_token"], scopes=GRAPH_SCOPES
            )
            if result and "access_token" in result:
                token_store.save_microsoft_token(email, json.dumps(result))
                _save_cache(email, cache)
                return result["access_token"]
    except KeyError:
        pass

    raise RuntimeError(
        f"Cannot refresh token for {email}. Re-authentication required."
    )
