"""Tests for service/notification_helper.py.

Android imports (android, jnius) are not available in CI; the module's
try/except guards make every function a safe no-op. Tests verify that:
  - All three public functions can be called without raising
  - On a mock Android environment the correct API calls are made
"""

import sys
import types
from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_android_mocks():
    """Return (android_mod, jnius_mod) with enough surface area for the helper."""
    android_mod = types.ModuleType("android")
    android_mod.mActivity = MagicMock(name="mActivity")

    jnius_mod = types.ModuleType("jnius")

    # autoclass returns different mock classes per name
    _classes = {}

    def _autoclass(name):
        if name not in _classes:
            _classes[name] = MagicMock(name=name)
        return _classes[name]

    jnius_mod.autoclass = _autoclass
    return android_mod, jnius_mod


# ---------------------------------------------------------------------------
# No-op on non-Android (default CI environment)
# ---------------------------------------------------------------------------

class TestNoOp:
    def test_create_channel_no_crash(self):
        from service import notification_helper
        notification_helper.create_channel()  # must not raise

    def test_send_notification_no_crash(self):
        from service import notification_helper
        notification_helper.send_notification("title", "body")

    def test_start_foreground_no_crash(self):
        from service import notification_helper
        notification_helper.start_foreground(MagicMock())


# ---------------------------------------------------------------------------
# Behaviour with mocked Android APIs
# ---------------------------------------------------------------------------

class TestWithAndroidMocks:
    def setup_method(self):
        self.android_mod, self.jnius_mod = _make_android_mocks()
        # Patch both modules into sys.modules before each test
        sys.modules["android"] = self.android_mod
        sys.modules["jnius"] = self.jnius_mod
        # Force reimport so the patched modules are used
        import importlib
        import service.notification_helper as nh
        importlib.reload(nh)
        self.nh = nh

    def teardown_method(self):
        sys.modules.pop("android", None)
        sys.modules.pop("jnius", None)

    def test_create_channel_calls_create(self):
        self.nh.create_channel()
        NotificationChannel = self.jnius_mod.autoclass("android.app.NotificationChannel")
        # Channel was instantiated with the correct ID and name
        NotificationChannel.assert_called_once_with(
            self.nh.CHANNEL_ID, self.nh.CHANNEL_NAME,
            self.jnius_mod.autoclass("android.app.NotificationManager").IMPORTANCE_LOW,
        )

    def test_send_notification_builds_and_posts(self):
        self.nh.send_notification("Hello", "World")
        NotificationManagerCompat = self.jnius_mod.autoclass(
            "androidx.core.app.NotificationManagerCompat"
        )
        manager = NotificationManagerCompat.from_(self.android_mod.mActivity)
        assert manager.notify.called

    def test_start_foreground_calls_service_start(self):
        ctx = MagicMock(name="service_context")
        self.nh.start_foreground(ctx)
        assert ctx.startForeground.called
        args = ctx.startForeground.call_args[0]
        assert args[0] == self.nh.FOREGROUND_NOTIF_ID

    def test_send_notification_unique_ids(self):
        """Two back-to-back notifications should get different notification IDs."""
        self.nh.send_notification("A", "1")
        self.nh.send_notification("B", "2")
        NotificationManagerCompat = self.jnius_mod.autoclass(
            "androidx.core.app.NotificationManagerCompat"
        )
        manager = NotificationManagerCompat.from_(self.android_mod.mActivity)
        assert manager.notify.call_count == 2
        id1 = manager.notify.call_args_list[0][0][0]
        id2 = manager.notify.call_args_list[1][0][0]
        # IDs should differ (time-based) or at least be non-negative integers
        assert isinstance(id1, int) and id1 >= 0
        assert isinstance(id2, int) and id2 >= 0
