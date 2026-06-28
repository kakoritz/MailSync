"""
Credential validator tests — verifies ping_yahoo and ping_microsoft behaviors.

The validator uses lazy imports inside each function to avoid circular imports
at module load time, so we patch the symbols at their source modules rather
than on the credential_validator namespace.
"""

import imaplib
import pytest
from unittest.mock import patch, MagicMock

from auth.credential_validator import ping_yahoo, ping_microsoft

YAHOO_EMAIL = "user@yahoo.com"
MS_EMAIL = "user@outlook.com"


# --- ping_yahoo ---

def test_ping_yahoo_success():
    mock_conn = MagicMock()

    with patch("auth.token_store.load_yahoo_credentials", return_value="app-password"), \
         patch("auth.credential_validator.imaplib.IMAP4_SSL", return_value=mock_conn):
        result = ping_yahoo(YAHOO_EMAIL)

    assert result.valid is True
    assert result.error == ""
    mock_conn.login.assert_called_once_with(YAHOO_EMAIL, "app-password")
    mock_conn.logout.assert_called_once()


def test_ping_yahoo_no_credentials():
    with patch("auth.token_store.load_yahoo_credentials", side_effect=KeyError):
        result = ping_yahoo(YAHOO_EMAIL)

    assert result.valid is False
    assert "No credentials" in result.error


def test_ping_yahoo_bad_password():
    mock_conn = MagicMock()
    mock_conn.login.side_effect = imaplib.IMAP4.error("LOGIN failed")

    with patch("auth.token_store.load_yahoo_credentials", return_value="wrong"), \
         patch("auth.credential_validator.imaplib.IMAP4_SSL", return_value=mock_conn):
        result = ping_yahoo(YAHOO_EMAIL)

    assert result.valid is False
    assert "Login failed" in result.error


def test_ping_yahoo_network_error():
    with patch("auth.token_store.load_yahoo_credentials", return_value="pw"), \
         patch("auth.credential_validator.imaplib.IMAP4_SSL", side_effect=OSError("refused")):
        result = ping_yahoo(YAHOO_EMAIL)

    assert result.valid is False
    assert "Network error" in result.error


# --- ping_microsoft ---

def test_ping_microsoft_success():
    with patch("auth.microsoft_auth.get_access_token", return_value="valid-token"):
        result = ping_microsoft(MS_EMAIL)

    assert result.valid is True
    assert result.error == ""


def test_ping_microsoft_token_refresh_fails():
    with patch("auth.microsoft_auth.get_access_token",
               side_effect=RuntimeError("No valid token")):
        result = ping_microsoft(MS_EMAIL)

    assert result.valid is False
    assert "No valid token" in result.error


def test_ping_microsoft_empty_token():
    with patch("auth.microsoft_auth.get_access_token", return_value=""):
        result = ping_microsoft(MS_EMAIL)

    assert result.valid is False
    assert "Empty token" in result.error


def test_ping_microsoft_unexpected_exception():
    with patch("auth.microsoft_auth.get_access_token",
               side_effect=Exception("connection reset")):
        result = ping_microsoft(MS_EMAIL)

    assert result.valid is False
    assert "Unexpected error" in result.error
