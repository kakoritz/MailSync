"""
Key derivation and symmetric encryption for all stored credentials and tokens.

Key material is derived from a device fingerprint (android_id on Android,
machine-id on Linux/Mac) combined with a per-install random salt stored in the
database. This means the encrypted blobs are device-bound — they cannot be
decrypted if the database file is moved to a different machine.
"""

import base64
import os
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

_SALT_FILE = Path(os.getenv("MAILSYNC_DATA_DIR", ".")) / ".salt"
_ITERATIONS = 260_000


def _get_or_create_salt() -> bytes:
    if _SALT_FILE.exists():
        return _SALT_FILE.read_bytes()
    salt = os.urandom(32)
    _SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SALT_FILE.write_bytes(salt)
    _SALT_FILE.chmod(0o600)
    return salt


def _device_fingerprint() -> bytes:
    try:
        from jnius import autoclass
        Settings = autoclass("android.provider.Settings$Secure")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        android_id = Settings.getString(
            PythonActivity.mActivity.getContentResolver(),
            Settings.ANDROID_ID,
        )
        return android_id.encode()
    except Exception:
        pass

    for candidate in [Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")]:
        if candidate.exists():
            return candidate.read_text().strip().encode()

    import uuid
    return str(uuid.getnode()).encode()


def _derive_key() -> bytes:
    salt = _get_or_create_salt()
    fingerprint = _device_fingerprint()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    raw = kdf.derive(fingerprint)
    return base64.urlsafe_b64encode(raw)


def _fernet() -> Fernet:
    return Fernet(_derive_key())


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    return _fernet().decrypt(ciphertext).decode()


def verify(ciphertext: bytes) -> bool:
    try:
        _fernet().decrypt(ciphertext)
        return True
    except InvalidToken:
        return False
