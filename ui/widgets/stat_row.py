from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.properties import StringProperty

Builder.load_string("""
<StatRow>:
    orientation: "horizontal"
    size_hint_y: None
    height: "28dp"
    Label:
        text: root.label
        color: (0.60, 0.60, 0.66, 1)
        font_size: "13sp"
        halign: "left"
        text_size: self.size
    Label:
        text: root.value
        color: (0.95, 0.95, 0.97, 1)
        font_size: "13sp"
        bold: True
        halign: "right"
        text_size: self.size
""")


class StatRow(BoxLayout):
    label = StringProperty("")
    value = StringProperty("")
