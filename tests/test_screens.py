"""
Headless UI smoke tests.

These tests verify that each screen can be instantiated and that key widgets
exist without crashing. They do NOT test interaction logic — that lives in
the business-logic tests. These run in CI with SDL_VIDEODRIVER=offscreen.

Skipped automatically when KIVY_NO_ENV_CONFIG is not set and Kivy is not
importable (e.g. dev environments without display libs).
"""

import os
import pytest

os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("MAILSYNC_CLIENT_ID", "test-client-id")

kivy = pytest.importorskip("kivy", reason="Kivy not installed")


from kivy.config import Config
Config.set("graphics", "headless", "fake")
Config.set("graphics", "width", "480")
Config.set("graphics", "height", "800")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    """Start a minimal Kivy app context for widget instantiation."""
    data_dir = tmp_path_factory.mktemp("data")
    os.environ["MAILSYNC_DATA_DIR"] = str(data_dir)

    from core import database
    database.init()

    _app = App()
    _app.build = lambda: ScreenManager()
    _app._run_prepare()
    yield _app


def test_home_screen_builds(app):
    from ui.screens.home_screen import HomeScreen
    screen = HomeScreen()
    assert hasattr(screen, "sync_btn")
    assert hasattr(screen, "yahoo_card")
    assert hasattr(screen, "outlook_card")
    assert hasattr(screen, "check_btn")
    assert hasattr(screen, "detail_lbl")
    assert hasattr(screen, "health_gauge")


def test_connect_screen_builds(app):
    from ui.screens.connect_screen import ConnectScreen
    screen = ConnectScreen()
    assert hasattr(screen, "yahoo_email_input")
    assert hasattr(screen, "ms_code_label")
    assert screen.ms_code_label.markup is True


def test_settings_screen_builds(app):
    from ui.screens.settings_screen import SettingsScreen
    screen = SettingsScreen()
    assert hasattr(screen, "yahoo_status_lbl")
    assert hasattr(screen, "ms_status_lbl")
    assert hasattr(screen, "interval_lbl")


def test_history_screen_builds(app):
    from ui.screens.history_screen import HistoryScreen
    screen = HistoryScreen()
    assert screen is not None


def test_account_card_states(app):
    from ui.widgets.account_card import AccountCard
    card = AccountCard(service_name="Yahoo Mail")
    card.set_disconnected()
    assert card.connected is False
    card.set_connected("user@yahoo.com")
    assert card.connected is True
    assert card.email == "user@yahoo.com"
    card.set_error("Login failed")
    assert "Login failed" in card.status_text


def test_health_gauge_update(app):
    from ui.widgets.health_gauge import HealthGauge
    from ui import theme
    gauge = HealthGauge()
    gauge.update(100)
    assert gauge.health_pct == 100
    gauge.update(50)
    assert tuple(gauge.gauge_color) == theme.STATUS_ERROR
    gauge.update(75)
    assert tuple(gauge.gauge_color) == theme.STATUS_WARN
    gauge.update(95)
    assert tuple(gauge.gauge_color) == theme.STATUS_OK


def test_open_outlook_btn_non_android(app):
    from ui.widgets.open_outlook_btn import OpenOutlookButton
    btn = OpenOutlookButton()
    assert btn.android_available is False
    assert btn.disabled is True
