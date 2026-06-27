import pytest
from cryptography.fernet import InvalidToken
from security import crypto


def test_encrypt_decrypt_round_trip():
    plaintext = "super-secret-app-password-123"
    blob = crypto.encrypt(plaintext)
    assert crypto.decrypt(blob) == plaintext


def test_encrypted_blob_is_bytes():
    blob = crypto.encrypt("test")
    assert isinstance(blob, bytes)


def test_different_plaintexts_produce_different_blobs():
    blob1 = crypto.encrypt("password1")
    blob2 = crypto.encrypt("password2")
    assert blob1 != blob2


def test_tampered_blob_raises():
    blob = crypto.encrypt("secret")
    tampered = blob[:-4] + b"XXXX"
    with pytest.raises(Exception):
        crypto.decrypt(tampered)


def test_verify_valid_blob():
    blob = crypto.encrypt("valid")
    assert crypto.verify(blob) is True


def test_verify_invalid_blob():
    assert crypto.verify(b"not-a-valid-fernet-token") is False


def test_key_derivation_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setenv("MAILSYNC_DATA_DIR", str(tmp_path))
    key1 = crypto._derive_key()
    key2 = crypto._derive_key()
    assert key1 == key2


def test_encrypt_non_ascii():
    text = "パスワード🔑"
    assert crypto.decrypt(crypto.encrypt(text)) == text
