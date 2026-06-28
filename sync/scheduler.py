"""
Platform-aware sync scheduler.

On Android: the background service (service/sync_service.py) owns the timer.
On desktop (dev/test): this module provides a threading-based scheduler.

Fires the sync function immediately on start(), then every interval seconds.
This ensures the first sync doesn't wait a full interval after launch.
"""

import threading
from typing import Callable

from core.constants import SYNC_INTERVAL_SECONDS


class SyncScheduler:
    def __init__(self, sync_fn: Callable, interval: int = SYNC_INTERVAL_SECONDS):
        self._sync_fn = sync_fn
        self._interval = interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _loop(self) -> None:
        # Fire immediately on first run, then every interval
        while True:
            try:
                self._sync_fn()
            except Exception:
                pass
            if self._stop_event.wait(self._interval):
                break

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())
