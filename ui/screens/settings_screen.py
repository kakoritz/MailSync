"""
Settings screen — accounts, sync interval, history, version.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.slider import Slider
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

_INTERVAL_OPTIONS = [
    (900,  "15 minutes"),
    (1800, "30 minutes"),
    (3600, "1 hour"),
    (7200, "2 hours"),
    (21600, "6 hours"),
]


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()

    def _build_ui(self) -> None:
        from kivy.uix.scrollview import ScrollView
        scroll = ScrollView()
        root = BoxLayout(
            orientation="vertical",
            padding="16dp",
            spacing="12dp",
            size_hint_y=None,
        )
        root.bind(minimum_height=root.setter("height"))
        scroll.add_widget(root)

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

        # --- Accounts ---
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
        disconnect_yahoo_btn.bind(on_release=self._confirm_disconnect_yahoo)
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
        disconnect_ms_btn.bind(on_release=self._confirm_disconnect_microsoft)
        root.add_widget(disconnect_ms_btn)

        add_btn = Button(
            text="+ Connect Accounts",
            size_hint_y=None, height="44dp",
            background_color=theme.ACCENT,
        )
        add_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "connect"))
        root.add_widget(add_btn)

        # --- Sync interval ---
        root.add_widget(self._section("Sync Interval"))

        self.interval_lbl = Label(
            text="Background sync: 1 hour",
            color=theme.TEXT_SECONDARY,
            font_size="14sp",
            size_hint_y=None, height="28dp",
            halign="left",
        )
        root.add_widget(self.interval_lbl)

        for seconds, label in _INTERVAL_OPTIONS:
            btn = Button(
                text=label,
                size_hint_y=None, height="40dp",
                background_color=theme.BG_CARD,
                color=theme.TEXT_PRIMARY,
            )
            btn.bind(on_release=lambda _, s=seconds, l=label: self._set_interval(s, l))
            root.add_widget(btn)

        # --- History ---
        root.add_widget(self._section("Sync History"))
        history_btn = Button(
            text="View Sync Log",
            size_hint_y=None, height="44dp",
            background_color=theme.BG_CARD,
        )
        history_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "history"))
        root.add_widget(history_btn)

        root.add_widget(Label(
            text=f"MailSync v{APP_VERSION}",
            color=theme.TEXT_MUTED,
            font_size="12sp",
            size_hint_y=None, height="32dp",
        ))

        self.add_widget(scroll)

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
        self._refresh_interval_label()

    def _refresh_status(self) -> None:
        yahoo = database.get_accounts_by_service("yahoo")
        ms = database.get_accounts_by_service("microsoft")
        self.yahoo_status_lbl.text = (
            f"Yahoo: {yahoo[0]['email']}" if yahoo else "Yahoo: not connected"
        )
        self.ms_status_lbl.text = (
            f"Microsoft: {ms[0]['email']}" if ms else "Microsoft: not connected"
        )

    def _refresh_interval_label(self) -> None:
        seconds = config.get("sync_interval_seconds")
        label = next(
            (l for s, l in _INTERVAL_OPTIONS if s == seconds),
            f"{seconds // 60} minutes",
        )
        self.interval_lbl.text = f"Background sync: {label}"

    def _set_interval(self, seconds: int, label: str) -> None:
        config.set("sync_interval_seconds", seconds)
        self.interval_lbl.text = f"Background sync: {label}"

    # --- Disconnect with confirmation ---

    def _confirm_disconnect_yahoo(self, *_) -> None:
        rows = database.get_accounts_by_service("yahoo")
        if not rows:
            return
        email = rows[0]["email"]
        self._confirm_popup(
            title="Disconnect Yahoo?",
            message=(
                f"Remove {email}?\n\n"
                "Sync history and last-synced position will be deleted.\n"
                "This cannot be undone."
            ),
            on_confirm=self._disconnect_yahoo,
        )

    def _confirm_disconnect_microsoft(self, *_) -> None:
        rows = database.get_accounts_by_service("microsoft")
        if not rows:
            return
        email = rows[0]["email"]
        self._confirm_popup(
            title="Disconnect Microsoft?",
            message=f"Remove {email}?\nYou will need to re-authenticate.",
            on_confirm=self._disconnect_microsoft,
        )

    def _confirm_popup(self, title: str, message: str, on_confirm) -> None:
        content = BoxLayout(orientation="vertical", padding="16dp", spacing="12dp")
        content.add_widget(Label(
            text=message,
            color=theme.TEXT_PRIMARY,
            font_size="14sp",
            halign="center",
            text_size=(None, None),
        ))
        btn_row = BoxLayout(orientation="horizontal", spacing="8dp",
                            size_hint_y=None, height="48dp")

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.85, 0.45),
            background_color=theme.BG_CARD,
        )

        cancel_btn = Button(
            text="Cancel",
            background_color=theme.BG_CARD,
            color=theme.TEXT_PRIMARY,
        )
        cancel_btn.bind(on_release=popup.dismiss)

        confirm_btn = Button(
            text="Disconnect",
            background_color=theme.STATUS_ERROR,
            color=theme.TEXT_ON_ACCENT,
        )

        def _do_confirm(*_):
            popup.dismiss()
            on_confirm()

        confirm_btn.bind(on_release=_do_confirm)
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)
        content.add_widget(btn_row)

        popup.open()

    def _disconnect_yahoo(self) -> None:
        rows = database.get_accounts_by_service("yahoo")
        if rows:
            email = rows[0]["email"]
            delete_credentials(email)
            database.delete_sync_state(email)
        self._refresh_status()

    def _disconnect_microsoft(self) -> None:
        rows = database.get_accounts_by_service("microsoft")
        if rows:
            email = rows[0]["email"]
            delete_credentials(email)
            # Also remove the MSAL cache entry
            try:
                from auth.microsoft_auth import _CACHE_SUFFIX
                delete_credentials(email + _CACHE_SUFFIX)
            except Exception:
                pass
        self._refresh_status()
