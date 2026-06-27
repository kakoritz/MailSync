"""
Encrypted credential persistence. All writes go through crypto.encrypt();
plaintext never touches the database.
"""

from core import database
from security import crypto


def save_yahoo_credentials(email: str, app_password: str) -> None:
    blob = crypto.encrypt(app_password)
    database.upsert_account("yahoo", email, blob)
    del app_password


def load_yahoo_credentials(email: str) -> str:
    row = database.get_account(email)
    if row is None:
        raise KeyError(f"No credentials stored for {email}")
    return crypto.decrypt(bytes(row["cred_blob"]))


def save_microsoft_token(email: str, token_json: str) -> None:
    blob = crypto.encrypt(token_json)
    database.upsert_account("microsoft", email, blob)
    del token_json


def load_microsoft_token(email: str) -> str:
    row = database.get_account(email)
    if row is None:
        raise KeyError(f"No token stored for {email}")
    return crypto.decrypt(bytes(row["cred_blob"]))


def delete_credentials(email: str) -> None:
    database.delete_account(email)
