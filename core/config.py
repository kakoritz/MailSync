import json
import os
from pathlib import Path

from core.constants import CONFIG_FILENAME

_DEFAULTS = {
    "sync_interval_seconds": 3600,
    "notifications_enabled": True,
    "theme": "dark",
}


def _config_path() -> Path:
    return Path(os.getenv("MAILSYNC_DATA_DIR", ".")) / CONFIG_FILENAME


def load() -> dict:
    path = _config_path()
    if not path.exists():
        return dict(_DEFAULTS)
    with open(path) as f:
        data = json.load(f)
    return {**_DEFAULTS, **data}


def save(config: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


def get(key: str):
    return load().get(key, _DEFAULTS.get(key))


def set(key: str, value) -> None:
    config = load()
    config[key] = value
    save(config)
