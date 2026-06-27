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


# --- microsoft_auth ---

def test_get_access_token_uses_silent_flow():
    fake_token = {"access_token": "fresh_token", "refresh_token": "rtoken"}
    token_json = json.dumps(fake_token)
    database.init()
    token_store.save_microsoft_token("user@outlook.com", token_json)

    mock_app = MagicMock()
    mock_app.get_accounts.return_value = [MagicMock()]
    mock_app.acquire_token_silent.return_value = {"access_token": "silent_token"}

    with patch("auth.microsoft_auth.msal.PublicClientApplication", return_value=mock_app):
        token = get_access_token("user@outlook.com")
    assert token == "silent_token"


def test_get_access_token_falls_back_to_refresh():
    fake_token = {"access_token": "old", "refresh_token": "rtoken"}
    database.init()
    token_store.save_microsoft_token("user@outlook.com", json.dumps(fake_token))

    mock_app = MagicMock()
    mock_app.get_accounts.return_value = []
    mock_app.acquire_token_by_refresh_token.return_value = {"access_token": "refreshed"}

    with patch("auth.microsoft_auth.msal.PublicClientApplication", return_value=mock_app):
        token = get_access_token("user@outlook.com")
    assert token == "refreshed"


def test_get_access_token_raises_when_all_fail():
    database.init()
    token_store.save_microsoft_token("user@outlook.com", json.dumps({"access_token": "x"}))

    mock_app = MagicMock()
    mock_app.get_accounts.return_value = []
    mock_app.acquire_token_by_refresh_token.return_value = {"error": "invalid_grant"}

    with patch("auth.microsoft_auth.msal.PublicClientApplication", return_value=mock_app):
        with pytest.raises(RuntimeError, match="Re-authentication"):
            get_access_token("user@outlook.com")
