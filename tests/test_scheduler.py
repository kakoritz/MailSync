"""
SyncScheduler tests — immediate first-run, interval firing, start/stop.
"""

import threading
import time

import pytest

from sync.scheduler import SyncScheduler


def test_scheduler_fires_immediately_on_start():
    """sync_fn must be called within 0.5 s of start() — no initial wait."""
    called = threading.Event()

    def sync_fn():
        called.set()

    s = SyncScheduler(sync_fn, interval=3600)
    s.start()
    fired = called.wait(timeout=0.5)
    s.stop()
    assert fired, "sync_fn was not called immediately on start()"


def test_scheduler_fires_again_after_interval():
    """sync_fn is called twice: once immediately and once after the interval."""
    call_times: list[float] = []

    def sync_fn():
        call_times.append(time.monotonic())

    s = SyncScheduler(sync_fn, interval=0.1)
    s.start()
    time.sleep(0.35)
    s.stop()

    assert len(call_times) >= 2, f"Expected ≥2 calls, got {len(call_times)}"
    gap = call_times[1] - call_times[0]
    assert gap >= 0.08, f"Gap between first and second call too short: {gap:.3f}s"


def test_scheduler_stops_cleanly():
    """After stop(), no further calls to sync_fn occur."""
    count = [0]

    def sync_fn():
        count[0] += 1

    s = SyncScheduler(sync_fn, interval=0.05)
    s.start()
    time.sleep(0.08)
    s.stop()
    snapshot = count[0]
    time.sleep(0.15)
    assert count[0] == snapshot, "sync_fn called after stop()"


def test_scheduler_not_started_twice():
    """Calling start() twice does not spawn a second thread."""
    s = SyncScheduler(lambda: None, interval=3600)
    s.start()
    thread1 = s._thread
    s.start()
    thread2 = s._thread
    s.stop()
    assert thread1 is thread2


def test_scheduler_exception_in_sync_fn_does_not_crash():
    """Exceptions in sync_fn are silently swallowed; scheduler keeps running."""
    call_count = [0]

    def sync_fn():
        call_count[0] += 1
        raise RuntimeError("deliberate error")

    s = SyncScheduler(sync_fn, interval=0.05)
    s.start()
    time.sleep(0.12)
    s.stop()

    # Give the thread a moment to notice the stop event and exit
    if s._thread:
        s._thread.join(timeout=1.0)

    assert call_count[0] >= 1
    assert not s.is_running
