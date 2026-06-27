import os
import pytest
from core import database


@pytest.fixture(autouse=True)
def fresh_db():
    """Each test gets a clean, initialised database."""
    database.init()
    yield
