"""
E2E test configuration.

All e2e tests require a running Dovecot IMAP server:
    docker-compose -f docker-compose.test.yml up -d

Tests are skipped automatically when the server is not reachable so that
the regular pytest run (no Docker) stays unaffected.
"""

import imaplib

import pytest

E2E_HOST = "localhost"
E2E_PORT = 143
E2E_USER = "testuser"
E2E_PASS = "testpass"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end test — requires Dovecot running via docker-compose.test.yml",
    )


def _server_reachable() -> bool:
    try:
        conn = imaplib.IMAP4(E2E_HOST, E2E_PORT)
        conn.logout()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def e2e_host():
    if not _server_reachable():
        pytest.skip(
            "IMAP test server not reachable — start with: "
            "docker-compose -f docker-compose.test.yml up -d"
        )
    return E2E_HOST


@pytest.fixture(scope="session")
def e2e_creds(e2e_host):
    return e2e_host, E2E_PORT, E2E_USER, E2E_PASS


@pytest.fixture
def imap_conn(e2e_creds):
    """Authenticated, plain-IMAP4 connection to the test server."""
    host, port, user, pw = e2e_creds
    conn = imaplib.IMAP4(host, port)
    conn.login(user, pw)
    yield conn
    try:
        conn.logout()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clear_inbox(imap_conn):
    """Wipe INBOX before every e2e test for isolation."""
    imap_conn.select("INBOX")
    status, data = imap_conn.uid("SEARCH", None, "ALL")
    if status == "OK" and data[0]:
        for uid in data[0].split():
            imap_conn.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
        imap_conn.expunge()
    yield
