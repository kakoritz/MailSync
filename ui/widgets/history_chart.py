"""
7-day sync history bar chart widget.

Displays one bar per day (Mon–Sun covering the last 7 days).
Bar height is proportional to emails_synced that day.
Bars with > 0 emails use STATUS_OK; empty days use STATUS_IDLE.
"""

from datetime import date, timedelta

from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from ui import theme

_DAYS_SHORT = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


class HistoryChart(BoxLayout):
    """Horizontal bar chart of emails synced per day for the last 7 days."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = "80dp"
        self.spacing = "4dp"

        self._chart = Widget(size_hint_y=1)
        self._chart.bind(size=self._redraw, pos=self._redraw)
        self.add_widget(self._chart)

        label_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height="14dp",
        )
        self._day_labels = []
        for _ in range(7):
            lbl = Label(
                text="",
                font_size="10sp",
                color=theme.TEXT_MUTED,
                halign="center",
            )
            label_row.add_widget(lbl)
            self._day_labels.append(lbl)
        self.add_widget(label_row)

        self._data: list[dict] = []
        self._populate_day_labels()

    def _populate_day_labels(self) -> None:
        today = date.today()
        for i, lbl in enumerate(self._day_labels):
            d = today - timedelta(days=6 - i)
            lbl.text = _DAYS_SHORT[d.weekday()]

    def update(self, data: list[dict]) -> None:
        """Accept output of database.get_sync_stats_by_day() and redraw."""
        self._data = data
        self._redraw()

    def _redraw(self, *_args) -> None:
        canvas = self._chart.canvas
        canvas.clear()

        today = date.today()
        # Build a date → count lookup from data
        by_date: dict[str, int] = {r["date"]: r["emails_synced"] for r in self._data}

        dates = [today - timedelta(days=6 - i) for i in range(7)]
        counts = [by_date.get(d.isoformat(), 0) for d in dates]
        max_count = max(counts) if any(counts) else 1

        w = self._chart.width
        h = self._chart.height
        bar_w = w / 7
        gap = bar_w * 0.2

        with canvas:
            for i, count in enumerate(counts):
                bar_h = max(2, (count / max_count) * h) if max_count > 0 else 2
                x = self._chart.x + i * bar_w + gap / 2
                y = self._chart.y

                color = theme.STATUS_OK if count > 0 else theme.STATUS_IDLE
                Color(*color)
                Rectangle(pos=(x, y), size=(bar_w - gap, bar_h))
