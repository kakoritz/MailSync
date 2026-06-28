from kivy.uix.boxlayout import BoxLayout
from kivy.uix.progressbar import ProgressBar
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.properties import NumericProperty, ColorProperty

from ui import theme

Builder.load_string("""
<HealthGauge>:
    orientation: "vertical"
    size_hint_y: None
    height: "48dp"
    spacing: "4dp"

    BoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: "18dp"
        Label:
            text: "Health"
            color: (0.60, 0.60, 0.66, 1)
            font_size: "13sp"
            halign: "left"
            text_size: self.size
        Label:
            text: f"{root.health_pct}%"
            color: root.gauge_color
            font_size: "13sp"
            bold: True
            halign: "right"
            text_size: self.size

    ProgressBar:
        id: bar
        max: 100
        value: root.health_pct
        size_hint_y: None
        height: "10dp"
""")


class HealthGauge(BoxLayout):
    health_pct = NumericProperty(100)
    gauge_color = ColorProperty(theme.STATUS_OK)

    def on_health_pct(self, _instance, value: float) -> None:
        if value >= 90:
            self.gauge_color = theme.STATUS_OK
        elif value >= 60:
            self.gauge_color = theme.STATUS_WARN
        else:
            self.gauge_color = theme.STATUS_ERROR

    def update(self, pct: int) -> None:
        self.health_pct = max(0, min(100, pct))
