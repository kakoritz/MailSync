from kivy.uix.button import Button
from kivy.animation import Animation
from kivy.properties import BooleanProperty, StringProperty, ColorProperty
from kivy.lang import Builder

from ui import theme

Builder.load_string("""
<SyncButton>:
    text: root.label_text
    font_size: "20sp"
    bold: True
    background_normal: ""
    background_color: root.btn_color
    color: (1, 1, 1, 1)
    size_hint_y: None
    height: "72dp"
    disabled: root.syncing
""")


class SyncButton(Button):
    syncing = BooleanProperty(False)
    label_text = StringProperty("SYNC NOW")
    btn_color = ColorProperty(theme.SYNC_BTN_COLOR)

    def set_syncing(self, active: bool) -> None:
        self.syncing = active
        if active:
            self.label_text = "SYNCING..."
            self.btn_color = theme.SYNC_BTN_COLOR_ACTIVE
            self._pulse()
        else:
            self.label_text = "SYNC NOW"
            self.btn_color = theme.SYNC_BTN_COLOR
            Animation.cancel_all(self)
            self.opacity = 1.0

    def set_error(self) -> None:
        self.syncing = False
        self.label_text = "SYNC FAILED — TAP TO RETRY"
        self.btn_color = theme.SYNC_BTN_COLOR_ERROR

    def _pulse(self) -> None:
        anim = (
            Animation(opacity=0.6, duration=0.5)
            + Animation(opacity=1.0, duration=0.5)
        )
        anim.repeat = True
        anim.start(self)
