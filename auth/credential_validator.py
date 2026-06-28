"""
Lightweight credential validation for both services.

Used on app startup to show live connection status without running a full sync.
Each ping opens and closes a connection as quickly as possible — no mailbox
data is read or written.
"""

import imaplib
import socket
from dataclasses import dataclass

from core.constants import YAHOO_IMAP_HOST, YAHOO_IMAP_PORT


@dataclass
class ValidationResult:
    valid: bool
    error: str = ""


def ping_yahoo(email: str) -> ValidationResult:
    """Verify Yahoo IMAP credentials are still accepted.

    Opens an IMAP connection, logs in, and logs out. No messages are accessed.
    """
    from auth.token_store import load_yahoo_credentials
    try:
        password = load_yahoo_credentials(email)
    except KeyError:
        return ValidationResult(valid=False, error="No credentials stored")

    try:
        conn = imaplib.IMAP4_SSL(YAHOO_IMAP_HOST, YAHOO_IMAP_PORT)
        conn.login(email, password)
        conn.logout()
        del password
        return ValidationResult(valid=True)
    except imaplib.IMAP4.error as exc:
        del password
        return ValidationResult(valid=False, error=f"Login failed: {exc}")
    except (OSError, socket.timeout) as exc:
        return ValidationResult(valid=False, error=f"Network error: {exc}")


def ping_microsoft(email: str) -> ValidationResult:
    """Verify a Microsoft access token can be obtained.

    Calls get_access_token() which uses the MSAL token cache. No Graph API
    calls are made — we're only verifying the token refresh path works.
    """
    from auth.microsoft_auth import get_access_token
    try:
        token = get_access_token(email)
        if token:
            return ValidationResult(valid=True)
        return ValidationResult(valid=False, error="Empty token returned")
    except RuntimeError as exc:
        return ValidationResult(valid=False, error=str(exc))
    except Exception as exc:
        return ValidationResult(valid=False, error=f"Unexpected error: {exc}")
