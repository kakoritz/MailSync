"""
MailSync — entry point.

Initialises the database, builds the ScreenManager, and starts the
background sync service on Android.
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.utils import platform

from core import database
from ui.screens.home_screen import HomeScreen
from ui.screens.connect_screen import ConnectScreen
from ui.screens.history_screen import HistoryScreen
from ui.screens.settings_screen import SettingsScreen


class MailSyncApp(App):
    def build(self):
        database.init()

        sm = ScreenManager(transition=FadeTransition(duration=0.15))
        sm.add_widget(HomeScreen())
        sm.add_widget(ConnectScreen())
        sm.add_widget(HistoryScreen())
        sm.add_widget(SettingsScreen())

        if platform == "android":
            self._start_background_service()

        return sm

    def _start_background_service(self) -> None:
        try:
            from android import mActivity
            from android.broadcast import BroadcastReceiver
            from jnius import autoclass

            Service = autoclass("org.kivy.android.PythonService")
            Service.start(mActivity, "MailSync background sync")
        except Exception as exc:
            from kivy.logger import Logger
            Logger.warning(f"MailSync: Could not start background service: {exc}")


if __name__ == "__main__":
    MailSyncApp().run()
