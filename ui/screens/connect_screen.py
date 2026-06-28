"""
Account connection screen.

Two flows:
  1. Yahoo — enter email + App Password → validate IMAP → save
  2. Microsoft — tap Connect → show device code → poll for token → save
"""

import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.lang import Builder

from auth.yahoo_auth import validate_credentials, YahooAuthError
from auth.microsoft_auth import initiate_device_flow, poll_device_flow
from auth.token_store import save_yahoo_credentials
from core import database
from ui import theme

Builder.load_string("""
<ConnectScreen>:
    name: "connect"
    canvas.before:
        Color:
            rgba: (0.08, 0.08, 0.12, 1)
        Rectangle:
            pos: self.pos
            size: self.size
""")


class ConnectScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._device_flow = None
        self._build_ui()

    def on_enter(self) -> None:
        yahoo_rows = database.get_accounts_by_service("yahoo")
        ms_rows = database.get_accounts_by_service("microsoft")

        has_yahoo = bool(yahoo_rows)
        has_ms = bool(ms_rows)

        if has_yahoo or has_ms:
            self._header_lbl.text = "Re-authenticate"
        else:
            self._header_lbl.text = "Connect Accounts"

        if has_yahoo:
            self.yahoo_email_input.text = yahoo_rows[0]["email"]
            self._yahoo_btn.text = "Update credentials"
        else:
            self.yahoo_email_input.text = ""
            self._yahoo_btn.text = "Connect Yahoo"
        self.yahoo_pw_input.text = ""

        if has_ms:
            self._ms_btn.text = "Re-authenticate Microsoft"
        else:
            self._ms_btn.text = "Connect Microsoft Account"

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical", padding="20dp", spacing="16dp")

        back_btn = Button(
            text="← Back",
            size_hint_y=None, height="40dp",
            background_color=(0, 0, 0, 0),
            color=theme.ACCENT,
        )
        back_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        root.add_widget(back_btn)

        self._header_lbl = Label(
            text="Connect Accounts",
            font_size="22sp", bold=True,
            color=theme.TEXT_PRIMARY,
            size_hint_y=None, height="40dp",
        )
        root.add_widget(self._header_lbl)

        # --- Yahoo section ---
        root.add_widget(self._section_label("Yahoo Mail"))

        self.yahoo_email_input = TextInput(
            hint_text="Yahoo email address",
            multiline=False,
            size_hint_y=None, height="44dp",
        )
        self.yahoo_pw_input = TextInput(
            hint_text="App Password (from Yahoo Account Security)",
            password=True,
            multiline=False,
            size_hint_y=None, height="44dp",
        )
        self._yahoo_btn = Button(
            text="Connect Yahoo",
            size_hint_y=None, height="48dp",
            background_color=theme.ACCENT,
        )
        self._yahoo_btn.bind(on_release=self._on_yahoo_connect)
        yahoo_btn = self._yahoo_btn

        self.yahoo_status = Label(
            text="",
            color=theme.TEXT_SECONDARY,
            font_size="13sp",
            size_hint_y=None, height="24dp",
        )
        for w in (self.yahoo_email_input, self.yahoo_pw_input,
                  yahoo_btn, self.yahoo_status):
            root.add_widget(w)

        # --- Microsoft section ---
        root.add_widget(self._section_label("Microsoft Outlook 365"))

        self._ms_btn = Button(
            text="Connect Microsoft Account",
            size_hint_y=None, height="48dp",
            background_color=(0.0, 0.47, 0.83, 1),
        )
        self._ms_btn.bind(on_release=self._on_ms_connect)
        root.add_widget(self._ms_btn)

        self.ms_code_label = Label(
            text="",
            markup=True,
            color=theme.TEXT_PRIMARY,
            font_size="14sp",
            size_hint_y=None, height="80dp",
            halign="center",
            text_size=(None, None),
        )
        root.add_widget(self.ms_code_label)

        self.ms_status = Label(
            text="",
            color=theme.TEXT_SECONDARY,
            font_size="13sp",
            size_hint_y=None, height="24dp",
        )
        root.add_widget(self.ms_status)

        self.add_widget(root)

    @staticmethod
    def _section_label(text: str) -> Label:
        return Label(
            text=text,
            font_size="16sp",
            bold=True,
            color=theme.TEXT_PRIMARY,
            size_hint_y=None, height="32dp",
            halign="left",
        )

    # --- Yahoo connect ---

    def _on_yahoo_connect(self, *_) -> None:
        email = self.yahoo_email_input.text.strip()
        pw = self.yahoo_pw_input.text.strip()
        if not email or not pw:
            self.yahoo_status.color = theme.STATUS_ERROR
            self.yahoo_status.text = "Email and App Password are required."
            return
        self.yahoo_status.color = theme.TEXT_SECONDARY
        self.yahoo_status.text = "Connecting..."
        threading.Thread(
            target=self._yahoo_connect_worker, args=(email, pw), daemon=True
        ).start()

    def _yahoo_connect_worker(self, email: str, pw: str) -> None:
        try:
            validate_credentials(email, pw)
            save_yahoo_credentials(email, pw)
            del pw
            Clock.schedule_once(lambda dt: self._yahoo_done(email))
        except YahooAuthError as exc:
            del pw
            Clock.schedule_once(lambda dt: self._yahoo_error(str(exc)))

    def _yahoo_done(self, email: str) -> None:
        self.yahoo_status.color = theme.STATUS_OK
        self.yahoo_status.text = f"Connected: {email}"
        self.yahoo_pw_input.text = ""

    def _yahoo_error(self, msg: str) -> None:
        self.yahoo_status.color = theme.STATUS_ERROR
        self.yahoo_status.text = f"Failed: {msg}"

    # --- Microsoft connect ---

    def _on_ms_connect(self, *_) -> None:
        self.ms_status.color = theme.TEXT_SECONDARY
        self.ms_status.text = "Starting device flow..."
        threading.Thread(target=self._ms_flow_worker, daemon=True).start()

    def _ms_flow_worker(self) -> None:
        try:
            flow = initiate_device_flow()
            self._device_flow = flow
            Clock.schedule_once(lambda dt: self._show_device_code(flow))
            email, _ = poll_device_flow(flow)
            Clock.schedule_once(lambda dt: self._ms_done(email))
        except Exception as exc:
            Clock.schedule_once(lambda dt: self._ms_error(str(exc)))

    def _show_device_code(self, flow: dict) -> None:
        code = flow.get("user_code", "")
        url = flow.get("verification_uri", "aka.ms/devicelogin")
        # markup=True is set at widget creation; assign text after so [b] tags render
        self.ms_code_label.text = f"Visit: [b]{url}[/b]\nEnter code: [b]{code}[/b]"
        self.ms_status.text = "Waiting for sign-in..."

    def _ms_done(self, email: str) -> None:
        self.ms_code_label.text = ""
        self.ms_status.color = theme.STATUS_OK
        self.ms_status.text = f"Connected: {email}"

    def _ms_error(self, msg: str) -> None:
        self.ms_code_label.text = ""
        self.ms_status.color = theme.STATUS_ERROR
        self.ms_status.text = f"Failed: {msg}"
