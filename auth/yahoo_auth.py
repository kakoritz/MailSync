import imaplib
import socket

from core.constants import YAHOO_IMAP_HOST, YAHOO_IMAP_PORT
from auth import token_store


class YahooAuthError(Exception):
    pass


def validate_credentials(email: str, app_password: str) -> None:
    """Open an IMAP connection to verify the credentials are valid.

    Raises YahooAuthError if the connection or login fails.
    """
    try:
        conn = imaplib.IMAP4_SSL(YAHOO_IMAP_HOST, YAHOO_IMAP_PORT)
    except (OSError, socket.timeout) as exc:
        raise YahooAuthError(f"Cannot reach Yahoo IMAP: {exc}") from exc

    try:
        conn.login(email, app_password)
        conn.logout()
    except imaplib.IMAP4.error as exc:
        raise YahooAuthError(f"Login failed: {exc}") from exc


def connect(email: str) -> imaplib.IMAP4_SSL:
    """Return an authenticated, connected IMAP4_SSL instance.

    Caller is responsible for calling .logout() when done.
    """
    app_password = token_store.load_yahoo_credentials(email)
    try:
        conn = imaplib.IMAP4_SSL(YAHOO_IMAP_HOST, YAHOO_IMAP_PORT)
        conn.login(email, app_password)
    except imaplib.IMAP4.error as exc:
        raise YahooAuthError(f"IMAP login failed for {email}: {exc}") from exc
    finally:
        del app_password
    return conn
