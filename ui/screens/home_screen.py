"""
Home / dashboard screen.

Layout (top to bottom):
  - Yahoo account card  (shows live validity on enter)
  - Outlook account card
  - SYNC NOW button
  - Check Pending button (dry-run — counts emails without writing)
  - Error detail label (shows last error message)
  - Stats panel (since date, total, today, last sync, health gauge)
  - Open Outlook button
  - Settings nav button
"""

import threading
from datetime import datetime, timezone

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.lang import Builder

from core import database
from auth.credential_validator import ping_yahoo, ping_microsoft
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
        self._active = False
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = ScrollView()
        root = BoxLayout(
            orientation="vertical",
            padding="16dp",
            spacing="10dp",
            size_hint_y=None,
        )
        root.bind(minimum_height=root.setter("height"))
        scroll.add_widget(root)

        root.add_widget(Label(
            text="MailSync",
            font_size="28sp",
            bold=True,
            color=theme.TEXT_PRIMARY,
            size_hint_y=None,
            height="48dp",
        ))

        # Account cards
        self.yahoo_card = AccountCard(service_name="Yahoo Mail")
        self.yahoo_card.set_disconnected()
        root.add_widget(self.yahoo_card)

        self.outlook_card = AccountCard(service_name="Outlook 365")
        self.outlook_card.set_disconnected()
        root.add_widget(self.outlook_card)

        # Primary sync button
        self.sync_btn = SyncButton()
        self.sync_btn.bind(on_release=self._on_sync_pressed)
        root.add_widget(self.sync_btn)

        # Dry-run / pending check button
        self.check_btn = Button(
            text="Check Pending Emails",
            font_size="14sp",
            background_color=theme.BG_CARD,
            color=theme.ACCENT,
            size_hint_y=None,
            height="44dp",
        )
        self.check_btn.bind(on_release=self._on_check_pressed)
        root.add_widget(self.check_btn)

        # Error / info detail label
        self.detail_lbl = Label(
            text="",
            color=theme.STATUS_ERROR,
            font_size="12sp",
            size_hint_y=None,
            height="0dp",
            halign="center",
            text_size=(None, None),
        )
        root.add_widget(self.detail_lbl)

        # Stats panel
        stats_box = BoxLayout(
            orientation="vertical",
            spacing="6dp",
            size_hint_y=None,
            height="200dp",
            padding=("0dp", "8dp"),
        )
        self.stat_since = StatRow(label="Syncing since")
        self.stat_total = StatRow(label="Total synced")
        self.stat_today = StatRow(label="Synced today")
        self.stat_last = StatRow(label="Last sync")
        self.stat_pending = StatRow(label="Pending (est.)")
        self.health_gauge = HealthGauge()

        for w in (self.stat_since, self.stat_total, self.stat_today,
                  self.stat_last, self.stat_pending, self.health_gauge):
            stats_box.add_widget(w)
        root.add_widget(stats_box)

        self.outlook_btn = OpenOutlookButton()
        root.add_widget(self.outlook_btn)

        settings_btn = Button(
            text="Settings / Accounts",
            font_size="14sp",
            background_color=theme.BG_CARD,
            color=theme.TEXT_SECONDARY,
            size_hint_y=None,
            height="44dp",
        )
        settings_btn.bind(on_release=lambda *_: self._go("settings"))
        root.add_widget(settings_btn)

        self.add_widget(scroll)

    def on_enter(self) -> None:
        self._active = True
        self._refresh_accounts()
        self._refresh_stats()
        if self._yahoo_email or self._outlook_email:
            threading.Thread(target=self._validate_credentials, daemon=True).start()

    def on_leave(self) -> None:
        self._active = False

    # --- account loading ---

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

    # --- credential validation (background) ---

    def _validate_credentials(self) -> None:
        if self._yahoo_email:
            result = ping_yahoo(self._yahoo_email)
            if self._active:
                Clock.schedule_once(
                    lambda dt: self._apply_yahoo_validity(result)
                )

        if self._outlook_email:
            result = ping_microsoft(self._outlook_email)
            if self._active:
                Clock.schedule_once(
                    lambda dt: self._apply_ms_validity(result)
                )

    def _apply_yahoo_validity(self, result) -> None:
        if not result.valid:
            self.yahoo_card.set_error("Auth failed")
            self._show_detail(f"Yahoo: {result.error}")

    def _apply_ms_validity(self, result) -> None:
        if not result.valid:
            self.outlook_card.set_error("Auth failed")
            self._show_detail(f"Microsoft: {result.error}")

    # --- stats ---

    def _refresh_stats(self) -> None:
        if not (self._yahoo_email and self._outlook_email):
            for stat in (self.stat_since, self.stat_total, self.stat_today,
                         self.stat_last, self.stat_pending):
                stat.value = "—"
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

    # --- sync ---

    def _on_sync_pressed(self, *_) -> None:
        if not (self._yahoo_email and self._outlook_email):
            self._go("connect")
            return
        self._clear_detail()
        self.sync_btn.set_syncing(True)
        threading.Thread(target=self._run_sync_worker, daemon=True).start()

    def _run_sync_worker(self) -> None:
        try:
            result = run_sync(
                self._yahoo_email,
                self._outlook_email,
                progress_cb=lambda n: Clock.schedule_once(
                    lambda dt: self._on_sync_progress(n)
                ),
            )
            if self._active:
                Clock.schedule_once(lambda dt: self._on_sync_done(result))
        except Exception as exc:
            if self._active:
                Clock.schedule_once(lambda dt: self._on_sync_error(str(exc)))

    def _on_sync_progress(self, count: int) -> None:
        self.sync_btn.label_text = f"SYNCING... ({count})"

    def _on_sync_done(self, result) -> None:
        self.sync_btn.set_syncing(False)
        if result.status == "error":
            self.sync_btn.set_error()
            if result.errors:
                self._show_detail(result.errors[0])
        elif result.status == "partial":
            self._show_detail(
                f"Partial sync: {result.emails_synced} written. "
                + (result.errors[0] if result.errors else ""),
                color=theme.STATUS_WARN,
            )
        self._refresh_stats()

    def _on_sync_error(self, msg: str) -> None:
        self.sync_btn.set_error()
        self._show_detail(msg)

    # --- dry-run / check pending ---

    def _on_check_pressed(self, *_) -> None:
        if not (self._yahoo_email and self._outlook_email):
            self._show_detail("Connect both accounts first.", color=theme.STATUS_WARN)
            return
        self.check_btn.text = "Checking..."
        self.check_btn.disabled = True
        self._clear_detail()
        threading.Thread(target=self._run_check_worker, daemon=True).start()

    def _run_check_worker(self) -> None:
        try:
            result = run_sync(
                self._yahoo_email,
                self._outlook_email,
                dry_run=True,
            )
            if self._active:
                Clock.schedule_once(lambda dt: self._on_check_done(result))
        except Exception as exc:
            if self._active:
                Clock.schedule_once(lambda dt: self._on_check_error(str(exc)))

    def _on_check_done(self, result) -> None:
        self.check_btn.text = "Check Pending Emails"
        self.check_btn.disabled = False
        n = result.emails_would_sync
        self.stat_pending.value = str(n) if n > 0 else "Up to date"
        if n > 0:
            self._show_detail(
                f"{n} email(s) pending — tap SYNC NOW to migrate.",
                color=theme.STATUS_WARN,
            )
        else:
            self._show_detail("Mailbox is up to date.", color=theme.STATUS_OK)

    def _on_check_error(self, msg: str) -> None:
        self.check_btn.text = "Check Pending Emails"
        self.check_btn.disabled = False
        self._show_detail(msg)

    # --- helpers ---

    def _show_detail(self, msg: str, color=None) -> None:
        self.detail_lbl.color = color or theme.STATUS_ERROR
        self.detail_lbl.text = msg
        self.detail_lbl.height = "40dp"

    def _clear_detail(self) -> None:
        self.detail_lbl.text = ""
        self.detail_lbl.height = "0dp"

    def _go(self, screen_name: str) -> None:
        self.manager.current = screen_name
