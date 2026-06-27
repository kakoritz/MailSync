"""
Settings screen — disconnect accounts, view sync interval, view version.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.lang import Builder

from core import database, config
from core.constants import APP_VERSION
from auth.token_store import delete_credentials
from ui import theme

Builder.load_string("""
<SettingsScreen>:
    name: "settings"
    canvas.before:
        Color:
            rgba: (0.08, 0.08, 0.12, 1)
        Rectangle:
            pos: self.pos
            size: self.size
""")


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical", padding="16dp", spacing="12dp")

        back_btn = Button(
            text="← Back",
            size_hint_y=None, height="40dp",
            background_color=(0, 0, 0, 0),
            color=theme.ACCENT,
        )
        back_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        root.add_widget(back_btn)

        root.add_widget(Label(
            text="Settings",
            font_size="22sp", bold=True,
            color=theme.TEXT_PRIMARY,
            size_hint_y=None, height="40dp",
        ))

        # Account management
        root.add_widget(self._section("Accounts"))

        self.yahoo_status_lbl = Label(
            text="Yahoo: not connected",
            color=theme.TEXT_SECONDARY,
            font_size="14sp",
            size_hint_y=None, height="28dp",
            halign="left",
        )
        root.add_widget(self.yahoo_status_lbl)

        disconnect_yahoo_btn = Button(
            text="Disconnect Yahoo Account",
            size_hint_y=None, height="44dp",
            background_color=theme.STATUS_ERROR,
        )
        disconnect_yahoo_btn.bind(on_release=self._disconnect_yahoo)
        root.add_widget(disconnect_yahoo_btn)

        self.ms_status_lbl = Label(
            text="Microsoft: not connected",
            color=theme.TEXT_SECONDARY,
            font_size="14sp",
            size_hint_y=None, height="28dp",
            halign="left",
        )
        root.add_widget(self.ms_status_lbl)

        disconnect_ms_btn = Button(
            text="Disconnect Microsoft Account",
            size_hint_y=None, height="44dp",
            background_color=theme.STATUS_ERROR,
        )
        disconnect_ms_btn.bind(on_release=self._disconnect_microsoft)
        root.add_widget(disconnect_ms_btn)

        # Add account button
        add_btn = Button(
            text="+ Connect Accounts",
            size_hint_y=None, height="44dp",
            background_color=theme.ACCENT,
        )
        add_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "connect"))
        root.add_widget(add_btn)

        root.add_widget(self._section("Sync History"))
        history_btn = Button(
            text="View Sync Log",
            size_hint_y=None, height="44dp",
            background_color=theme.BG_CARD,
        )
        history_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "history"))
        root.add_widget(history_btn)

        # Version
        root.add_widget(Label(
            text=f"MailSync v{APP_VERSION}",
            color=theme.TEXT_MUTED,
            font_size="12sp",
            size_hint_y=None, height="28dp",
        ))

        self.add_widget(root)

    @staticmethod
    def _section(text: str) -> Label:
        return Label(
            text=text,
            font_size="16sp", bold=True,
            color=theme.TEXT_PRIMARY,
            size_hint_y=None, height="36dp",
            halign="left",
        )

    def on_enter(self) -> None:
        self._refresh_status()

    def _refresh_status(self) -> None:
        yahoo = database.get_accounts_by_service("yahoo")
        ms = database.get_accounts_by_service("microsoft")
        self.yahoo_status_lbl.text = (
            f"Yahoo: {yahoo[0]['email']}" if yahoo else "Yahoo: not connected"
        )
        self.ms_status_lbl.text = (
            f"Microsoft: {ms[0]['email']}" if ms else "Microsoft: not connected"
        )

    def _disconnect_yahoo(self, *_) -> None:
        rows = database.get_accounts_by_service("yahoo")
        if rows:
            email = rows[0]["email"]
            delete_credentials(email)
            database.delete_sync_state(email)
        self._refresh_status()

    def _disconnect_microsoft(self, *_) -> None:
        rows = database.get_accounts_by_service("microsoft")
        if rows:
            delete_credentials(rows[0]["email"])
        self._refresh_status()
