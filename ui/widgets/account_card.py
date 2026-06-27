from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty, ColorProperty

from ui import theme

Builder.load_string("""
<AccountCard>:
    orientation: "horizontal"
    size_hint_y: None
    height: "72dp"
    padding: "16dp"
    spacing: "12dp"
    canvas.before:
        Color:
            rgba: root.card_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12]

    Label:
        id: status_dot
        text: "●"
        color: root.dot_color
        size_hint: None, None
        size: "16dp", "16dp"
        font_size: "16sp"

    BoxLayout:
        orientation: "vertical"
        spacing: "2dp"
        Label:
            text: root.service_name
            color: app.theme_cls.text_color if hasattr(app, 'theme_cls') else (0.95, 0.95, 0.97, 1)
            font_size: "14sp"
            bold: True
            halign: "left"
            text_size: self.size
        Label:
            text: root.email
            color: (0.60, 0.60, 0.66, 1)
            font_size: "12sp"
            halign: "left"
            text_size: self.size

    Label:
        text: root.status_text
        color: root.dot_color
        font_size: "12sp"
        size_hint_x: None
        width: "60dp"
        halign: "right"
        text_size: self.size
""")


class AccountCard(BoxLayout):
    service_name = StringProperty("")
    email = StringProperty("")
    connected = BooleanProperty(False)
    status_text = StringProperty("Disconnected")
    card_color = ColorProperty((0.13, 0.13, 0.18, 1))
    dot_color = ColorProperty((0.50, 0.50, 0.55, 1))

    def set_connected(self, email: str) -> None:
        self.email = email
        self.connected = True
        self.status_text = "Connected"
        self.dot_color = theme.STATUS_OK

    def set_disconnected(self) -> None:
        self.email = "Not connected"
        self.connected = False
        self.status_text = "Disconnected"
        self.dot_color = theme.STATUS_IDLE

    def set_error(self, message: str = "Error") -> None:
        self.status_text = message
        self.dot_color = theme.STATUS_ERROR
