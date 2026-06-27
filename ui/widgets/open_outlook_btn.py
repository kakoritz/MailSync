"""
Button that opens the Outlook Android app (or its Play Store listing if not installed).
On non-Android platforms the button is rendered but disabled.
"""

from kivy.uix.button import Button
from kivy.lang import Builder
from kivy.properties import BooleanProperty
from kivy.utils import platform

Builder.load_string("""
<OpenOutlookButton>:
    text: "Open Outlook ↗"
    font_size: "15sp"
    background_normal: ""
    background_color: (0.18, 0.52, 0.96, 0.18)
    color: (0.18, 0.52, 0.96, 1)
    size_hint_y: None
    height: "48dp"
    disabled: not root.android_available
""")

_OUTLOOK_PKG = "com.microsoft.office.outlook"


class OpenOutlookButton(Button):
    android_available = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.android_available = (platform == "android")
        self.bind(on_release=self._launch)

    def _launch(self, *_) -> None:
        if platform != "android":
            return
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity

            intent = activity.getPackageManager().getLaunchIntentForPackage(_OUTLOOK_PKG)
            if intent:
                activity.startActivity(intent)
            else:
                fallback = Intent(
                    Intent.ACTION_VIEW,
                    Uri.parse(f"market://details?id={_OUTLOOK_PKG}"),
                )
                activity.startActivity(fallback)
        except Exception as exc:
            from kivy.logger import Logger
            Logger.warning(f"OpenOutlookButton: {exc}")
