"""
Outlook writer tests — requests calls fully mocked.
"""

import pytest
from unittest.mock import patch, MagicMock

from sync.outlook_writer import import_message, message_exists, OutlookWriteError


@pytest.fixture
def mock_token():
    with patch("sync.outlook_writer.get_access_token", return_value="fake-token"):
        yield


def _mock_response(status_code: int, json_data: dict = None, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def test_import_message_success(mock_token):
    rfc822 = b"From: a@b.com\r\nSubject: Hello\r\n\r\nBody"
    mock_resp = _mock_response(201, {"id": "msg-id-123"})

    with patch("sync.outlook_writer.requests.post", return_value=mock_resp) as mock_post:
        msg_id = import_message("user@outlook.com", rfc822)

    assert msg_id == "msg-id-123"
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["data"] == rfc822
    assert kwargs["headers"]["Content-Type"] == "message/rfc822"


def test_import_message_401_retries(mock_token):
    rfc822 = b"From: a@b.com\r\n\r\nBody"
    fail_resp = _mock_response(401, text="Unauthorized")
    ok_resp = _mock_response(201, {"id": "retry-id"})

    with patch("sync.outlook_writer.requests.post", side_effect=[fail_resp, ok_resp]):
        msg_id = import_message("user@outlook.com", rfc822)

    assert msg_id == "retry-id"


def test_import_message_persistent_failure(mock_token):
    rfc822 = b"From: a@b.com\r\n\r\nBody"
    fail_resp = _mock_response(500, text="Server Error")

    with patch("sync.outlook_writer.requests.post", return_value=fail_resp):
        with pytest.raises(OutlookWriteError, match="500"):
            import_message("user@outlook.com", rfc822)


def test_message_exists_true(mock_token):
    mock_resp = _mock_response(200, {"value": [{"id": "existing"}]})
    with patch("sync.outlook_writer.requests.get", return_value=mock_resp):
        assert message_exists("user@outlook.com", "<msg@example.com>") is True


def test_message_exists_false(mock_token):
    mock_resp = _mock_response(200, {"value": []})
    with patch("sync.outlook_writer.requests.get", return_value=mock_resp):
        assert message_exists("user@outlook.com", "<msg@example.com>") is False


def test_message_exists_api_error_returns_false(mock_token):
    mock_resp = _mock_response(403)
    with patch("sync.outlook_writer.requests.get", return_value=mock_resp):
        assert message_exists("user@outlook.com", "<msg@example.com>") is False
