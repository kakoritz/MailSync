"""
Auth module tests — all network calls are mocked.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from core import database
from auth import token_store
from auth.yahoo_auth import validate_credentials, YahooAuthError
from auth.microsoft_auth import initiate_device_flow, get_access_token


# --- token_store ---

def test_save_and_load_yahoo_credentials():
    database.init()
    token_store.save_yahoo_credentials("user@yahoo.com", "app-password-xyz")
    loaded = token_store.load_yahoo_credentials("user@yahoo.com")
    assert loaded == "app-password-xyz"


def test_load_missing_yahoo_credentials_raises():
    database.init()
    with pytest.raises(KeyError):
        token_store.load_yahoo_credentials("nobody@yahoo.com")


def test_save_and_load_microsoft_token():
    database.init()
    token = json.dumps({"access_token": "abc", "refresh_token": "xyz"})
    token_store.save_microsoft_token("user@outlook.com", token)
    loaded = token_store.load_microsoft_token("user@outlook.com")
    assert json.loads(loaded)["access_token"] == "abc"


def test_delete_credentials_removes_entry():
    database.init()
    token_store.save_yahoo_credentials("user@yahoo.com", "pw")
    token_store.delete_credentials("user@yahoo.com")
    with pytest.raises(KeyError):
        token_store.load_yahoo_credentials("user@yahoo.com")


# --- yahoo_auth ---

def test_validate_credentials_success():
    mock_conn = MagicMock()
    with patch("auth.yahoo_auth.imaplib.IMAP4_SSL", return_value=mock_conn):
        validate_credentials("user@yahoo.com", "password")
        mock_conn.login.assert_called_once_with("user@yahoo.com", "password")
        mock_conn.logout.assert_called_once()


def test_validate_credentials_wrong_password():
    import imaplib
    mock_conn = MagicMock()
    mock_conn.login.side_effect = imaplib.IMAP4.error("Invalid credentials")
    with patch("auth.yahoo_auth.imaplib.IMAP4_SSL", return_value=mock_conn):
        with pytest.raises(YahooAuthError, match="Login failed"):
            validate_credentials("user@yahoo.com", "wrong")


def test_validate_credentials_connection_failure():
    with patch("auth.yahoo_auth.imaplib.IMAP4_SSL", side_effect=OSError("timeout")):
        with pytest.raises(YahooAuthError, match="Cannot reach"):
            validate_credentials("user@yahoo.com", "pw")


# --- microsoft_auth: get_access_token with SerializableTokenCache ---

def _fake_token_json():
    return json.dumps({"access_token": "old", "refresh_token": "rtoken"})


def test_get_access_token_uses_silent_flow():
    database.init()
    token_store.save_microsoft_token("user@outlook.com", _fake_token_json())

    mock_cache = MagicMock()
    mock_cache.has_state_changed = False
    mock_app = MagicMock()
    mock_app.get_accounts.return_value = [MagicMock()]
    mock_app.acquire_token_silent.return_value = {"access_token": "silent_token"}

    with patch("auth.microsoft_auth.msal.SerializableTokenCache", return_value=mock_cache), \
         patch("auth.microsoft_auth.msal.PublicClientApplication", return_value=mock_app):
        token = get_access_token("user@outlook.com")

    assert token == "silent_token"


def test_get_access_token_falls_back_to_refresh():
    database.init()
    token_store.save_microsoft_token("user@outlook.com", _fake_token_json())

    mock_cache = MagicMock()
    mock_cache.has_state_changed = False
    mock_app = MagicMock()
    mock_app.get_accounts.return_value = []
    mock_app.acquire_token_by_refresh_token.return_value = {"access_token": "refreshed"}

    with patch("auth.microsoft_auth.msal.SerializableTokenCache", return_value=mock_cache), \
         patch("auth.microsoft_auth.msal.PublicClientApplication", return_value=mock_app):
        token = get_access_token("user@outlook.com")

    assert token == "refreshed"


def test_get_access_token_raises_when_all_fail():
    database.init()
    token_store.save_microsoft_token("user@outlook.com", _fake_token_json())

    mock_cache = MagicMock()
    mock_cache.has_state_changed = False
    mock_app = MagicMock()
    mock_app.get_accounts.return_value = []
    mock_app.acquire_token_by_refresh_token.return_value = {"error": "invalid_grant"}

    with patch("auth.microsoft_auth.msal.SerializableTokenCache", return_value=mock_cache), \
         patch("auth.microsoft_auth.msal.PublicClientApplication", return_value=mock_app):
        with pytest.raises(RuntimeError, match="Re-authentication"):
            get_access_token("user@outlook.com")


def test_get_access_token_saves_cache_on_state_change():
    database.init()
    token_store.save_microsoft_token("user@outlook.com", _fake_token_json())

    mock_cache = MagicMock()
    mock_cache.has_state_changed = True
    mock_cache.serialize.return_value = '{"tokens": "fresh"}'
    mock_app = MagicMock()
    mock_app.get_accounts.return_value = [MagicMock()]
    mock_app.acquire_token_silent.return_value = {"access_token": "new_token"}

    with patch("auth.microsoft_auth.msal.SerializableTokenCache", return_value=mock_cache), \
         patch("auth.microsoft_auth.msal.PublicClientApplication", return_value=mock_app):
        get_access_token("user@outlook.com")

    mock_cache.serialize.assert_called()


def test_initiate_device_flow_raises_on_error():
    mock_app = MagicMock()
    mock_app.initiate_device_flow.return_value = {
        "error": "bad_request",
        "error_description": "Client not found",
    }
    with patch("auth.microsoft_auth.msal.PublicClientApplication", return_value=mock_app):
        with pytest.raises(RuntimeError, match="Device flow error"):
            initiate_device_flow()
