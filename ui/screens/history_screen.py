"""
Sync history screen — shows the sync_log table in reverse-chronological order.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.lang import Builder

from core import database
from ui import theme

Builder.load_string("""
<HistoryScreen>:
    name: "history"
    canvas.before:
        Color:
            rgba: (0.08, 0.08, 0.12, 1)
        Rectangle:
            pos: self.pos
            size: self.size
""")

_STATUS_COLORS = {
    "success": theme.STATUS_OK,
    "partial": theme.STATUS_WARN,
    "error": theme.STATUS_ERROR,
}


class HistoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical", padding="16dp", spacing="8dp")

        back_btn = Button(
            text="← Back",
            size_hint_y=None, height="40dp",
            background_color=(0, 0, 0, 0),
            color=theme.ACCENT,
        )
        back_btn.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        root.add_widget(back_btn)

        root.add_widget(Label(
            text="Sync History",
            font_size="22sp", bold=True,
            color=theme.TEXT_PRIMARY,
            size_hint_y=None, height="40dp",
        ))

        self._log_box = BoxLayout(
            orientation="vertical", spacing="4dp", size_hint_y=None
        )
        self._log_box.bind(minimum_height=self._log_box.setter("height"))

        scroll = ScrollView()
        scroll.add_widget(self._log_box)
        root.add_widget(scroll)

        self.add_widget(root)

    def on_enter(self) -> None:
        self._load_log()

    def _load_log(self) -> None:
        self._log_box.clear_widgets()
        yahoo_rows = database.get_accounts_by_service("yahoo")
        if not yahoo_rows:
            self._log_box.add_widget(Label(
                text="No accounts connected.",
                color=theme.TEXT_MUTED,
                size_hint_y=None, height="40dp",
            ))
            return

        yahoo_email = yahoo_rows[0]["email"]
        state = database.get_sync_state(yahoo_email)
        if not state:
            return

        from core.database import get_conn
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM sync_log WHERE sync_state_id = ?
                   ORDER BY started_at DESC LIMIT 50""",
                (state["id"],),
            ).fetchall()

        if not rows:
            self._log_box.add_widget(Label(
                text="No sync history yet.",
                color=theme.TEXT_MUTED,
                size_hint_y=None, height="40dp",
            ))
            return

        for row in rows:
            row_widget = self._make_row(row)
            self._log_box.add_widget(row_widget)

    def _make_row(self, row) -> BoxLayout:
        color = _STATUS_COLORS.get(row["status"], theme.TEXT_MUTED)
        box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None, height="40dp",
            spacing="8dp",
        )
        started = (row["started_at"] or "")[:16].replace("T", " ")
        box.add_widget(Label(
            text=started,
            color=theme.TEXT_SECONDARY,
            font_size="12sp",
            size_hint_x=0.45,
            halign="left", text_size=(None, None),
        ))
        box.add_widget(Label(
            text=f"+{row['emails_synced']} emails",
            color=theme.TEXT_PRIMARY,
            font_size="12sp",
            size_hint_x=0.30,
            halign="right", text_size=(None, None),
        ))
        box.add_widget(Label(
            text=(row["status"] or "").upper(),
            color=color,
            font_size="11sp",
            bold=True,
            size_hint_x=0.25,
            halign="right", text_size=(None, None),
        ))
        return box
