"""
Home / dashboard screen.

Layout (top to bottom):
  - Yahoo account card
  - Outlook account card
  - SYNC NOW button
  - Stats panel (since date, total, today, last sync, health gauge)
  - Open Outlook button
"""

import threading
from datetime import datetime, timezone

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.lang import Builder

from core import database
from sync.sync_engine import run_sync
from ui.widgets.account_card import AccountCard
from ui.widgets.sync_button import SyncButton
from ui.widgets.stat_row import StatRow
from ui.widgets.health_gauge import HealthGauge
from ui.widgets.open_outlook_btn import OpenOutlookButton
from ui import theme

Builder.load_string("""
<HomeScreen>:
    name: "home"
    canvas.before:
        Color:
            rgba: (0.08, 0.08, 0.12, 1)
        Rectangle:
            pos: self.pos
            size: self.size
""")


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._yahoo_email: str | None = None
        self._outlook_email: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical", padding="16dp", spacing="12dp")

        # Header
        header = Label(
            text="MailSync",
            font_size="28sp",
            bold=True,
            color=theme.TEXT_PRIMARY,
            size_hint_y=None,
            height="48dp",
        )
        root.add_widget(header)

        # Account cards
        self.yahoo_card = AccountCard(service_name="Yahoo Mail")
        self.yahoo_card.set_disconnected()
        root.add_widget(self.yahoo_card)

        self.outlook_card = AccountCard(service_name="Outlook 365")
        self.outlook_card.set_disconnected()
        root.add_widget(self.outlook_card)

        # Sync button
        self.sync_btn = SyncButton()
        self.sync_btn.bind(on_release=self._on_sync_pressed)
        root.add_widget(self.sync_btn)

        # Stats panel
        stats_box = BoxLayout(
            orientation="vertical",
            spacing="6dp",
            size_hint_y=None,
            height="180dp",
            padding=("0dp", "8dp"),
        )
        self.stat_since = StatRow(label="Syncing since")
        self.stat_total = StatRow(label="Total emails synced")
        self.stat_today = StatRow(label="Synced today")
        self.stat_last = StatRow(label="Last sync")
        self.health_gauge = HealthGauge()

        for w in (self.stat_since, self.stat_total, self.stat_today,
                  self.stat_last, self.health_gauge):
            stats_box.add_widget(w)
        root.add_widget(stats_box)

        # Open Outlook button
        self.outlook_btn = OpenOutlookButton()
        root.add_widget(self.outlook_btn)

        # Nav to settings
        from kivy.uix.button import Button
        settings_btn = Button(
            text="Settings / Accounts",
            font_size="14sp",
            background_color=(0.13, 0.13, 0.18, 1),
            color=theme.TEXT_SECONDARY,
            size_hint_y=None,
            height="44dp",
        )
        settings_btn.bind(on_release=lambda *_: self._go("settings"))
        root.add_widget(settings_btn)

        self.add_widget(root)

    def on_enter(self) -> None:
        self._refresh_accounts()
        self._refresh_stats()

    def _refresh_accounts(self) -> None:
        yahoo_rows = database.get_accounts_by_service("yahoo")
        ms_rows = database.get_accounts_by_service("microsoft")

        if yahoo_rows:
            self._yahoo_email = yahoo_rows[0]["email"]
            self.yahoo_card.set_connected(self._yahoo_email)
        else:
            self._yahoo_email = None
            self.yahoo_card.set_disconnected()

        if ms_rows:
            self._outlook_email = ms_rows[0]["email"]
            self.outlook_card.set_connected(self._outlook_email)
        else:
            self._outlook_email = None
            self.outlook_card.set_disconnected()

    def _refresh_stats(self) -> None:
        if not (self._yahoo_email and self._outlook_email):
            self.stat_since.value = "—"
            self.stat_total.value = "—"
            self.stat_today.value = "—"
            self.stat_last.value = "—"
            self.health_gauge.update(100)
            return

        state = database.get_sync_state(self._yahoo_email)
        if not state:
            return

        stats = database.get_sync_stats(state["id"])

        first = state["first_sync_at"]
        self.stat_since.value = first[:10] if first else "Not yet synced"

        self.stat_total.value = f"{stats['total_synced']:,}"
        self.stat_today.value = str(stats["today_synced"])

        last = state["last_sync_at"]
        if last:
            try:
                dt = datetime.fromisoformat(last)
                delta = datetime.now(timezone.utc) - dt
                mins = int(delta.total_seconds() / 60)
                if mins < 1:
                    self.stat_last.value = "Just now"
                elif mins < 60:
                    self.stat_last.value = f"{mins} min ago"
                else:
                    self.stat_last.value = f"{mins // 60}h ago"
            except Exception:
                self.stat_last.value = last[:16]
        else:
            self.stat_last.value = "Never"

        self.health_gauge.update(stats["health_pct"])

    def _on_sync_pressed(self, *_) -> None:
        if not (self._yahoo_email and self._outlook_email):
            self._go("connect")
            return
        self.sync_btn.set_syncing(True)
        threading.Thread(target=self._run_sync, daemon=True).start()

    def _run_sync(self) -> None:
        try:
            result = run_sync(self._yahoo_email, self._outlook_email)
            Clock.schedule_once(lambda dt: self._on_sync_done(result))
        except Exception as exc:
            Clock.schedule_once(lambda dt: self._on_sync_error(str(exc)))

    def _on_sync_done(self, result) -> None:
        self.sync_btn.set_syncing(False)
        if result.status == "error":
            self.sync_btn.set_error()
        self._refresh_stats()

    def _on_sync_error(self, msg: str) -> None:
        self.sync_btn.set_error()

    def _go(self, screen_name: str) -> None:
        self.manager.current = screen_name
