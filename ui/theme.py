"""
Visual constants for MailSync UI.

One place for all colors, font sizes, and spacing. Never define these inline
in screen or widget files.
"""

# Background
BG_DARK = (0.08, 0.08, 0.12, 1)
BG_CARD = (0.13, 0.13, 0.18, 1)
BG_CARD_HOVER = (0.17, 0.17, 0.22, 1)

# Brand accent
ACCENT = (0.18, 0.52, 0.96, 1)        # blue
ACCENT_PRESS = (0.12, 0.38, 0.78, 1)

# Status colors
STATUS_OK = (0.18, 0.80, 0.44, 1)     # green
STATUS_ERROR = (0.92, 0.29, 0.29, 1)  # red
STATUS_WARN = (0.95, 0.70, 0.15, 1)   # amber
STATUS_IDLE = (0.50, 0.50, 0.55, 1)   # grey

# Text
TEXT_PRIMARY = (0.95, 0.95, 0.97, 1)
TEXT_SECONDARY = (0.60, 0.60, 0.66, 1)
TEXT_MUTED = (0.38, 0.38, 0.42, 1)
TEXT_ON_ACCENT = (1, 1, 1, 1)

# Typography (sp units — Kivy scales these for display density)
FONT_XL = "36sp"
FONT_LG = "22sp"
FONT_MD = "16sp"
FONT_SM = "13sp"
FONT_XS = "11sp"

# Spacing / padding
PAD_LG = "24dp"
PAD_MD = "16dp"
PAD_SM = "8dp"
PAD_XS = "4dp"

# Card radius
RADIUS = [12]

# Sync button
SYNC_BTN_HEIGHT = "72dp"
SYNC_BTN_COLOR = ACCENT
SYNC_BTN_COLOR_ACTIVE = ACCENT_PRESS
SYNC_BTN_COLOR_ERROR = STATUS_ERROR

# Health gauge full / empty bar colors
HEALTH_FULL = STATUS_OK
HEALTH_EMPTY = (0.20, 0.20, 0.24, 1)
