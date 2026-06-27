"""
Platform-aware sync scheduler.

On Android: the background service (service/sync_service.py) owns the timer.
On desktop (dev/test): this module provides a threading-based scheduler.
"""

import threading
import time
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
        while not self._stop_event.is_set():
            self._stop_event.wait(self._interval)
            if not self._stop_event.is_set():
                try:
                    self._sync_fn()
                except Exception:
                    pass

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())
