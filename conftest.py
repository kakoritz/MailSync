import os
import tempfile
import pytest

# Point all file I/O at a temp dir so tests never touch real data
@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path):
    os.environ["MAILSYNC_DATA_DIR"] = str(tmp_path)
    yield
    os.environ.pop("MAILSYNC_DATA_DIR", None)
