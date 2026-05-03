NAVY = "#0f1f4b"
NAVY_2 = "#1a3070"
NAVY_3 = "#243d8f"
TEAL = "#0d7d62"
TEAL_LIGHT = "#12a882"
AMBER = "#b97a0f"
RED = "#b91c1c"
GREEN = "#15803d"
SURFACE = "#f5f6f9"
BORDER = "#dde1eb"
TEXT = "#0f172a"
TEXT_2 = "#3d4a63"
TEXT_3 = "#64748b"

WHITE = "#ffffff"
BACKGROUND = "#0c1024"
SURFACE_2 = "#eef0f5"
BORDER_2 = "#c8cdd9"
TEAL_PALE = "#e1f5ee"
AMBER_PALE = "#fdf3dc"
RED_PALE = "#fef2f2"
GREEN_PALE = "#f0fdf4"
NAVY_PALE = "#e8ecf8"
BLUE = "#1d4ed8"
BLUE_PALE = "#eff6ff"
MUTED = "#94a3b8"
PAPER_WARNING = "#fff8f8"
SUPER_SIDEBAR = "#21131b"
SUPER_SIDEBAR_2 = "#3a2030"
SUPER_SIDEBAR_3 = "#573049"
SUPER_ACCENT = "#d6a84f"
SUPER_ACCENT_PALE = "#fff4d8"

FONT_UI = "Plus Jakarta Sans"
FONT_MONO = "DM Mono"
FONT_FALLBACK = "Segoe UI"
MONO_FALLBACK = "Consolas"

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 20,
    "xxl": 24,
    "xxxl": 32,
}

COLORS = {
    "background": BACKGROUND,
    "navy": NAVY,
    "navy_2": NAVY_2,
    "navy_3": NAVY_3,
    "teal": TEAL,
    "teal_light": TEAL_LIGHT,
    "teal_pale": TEAL_PALE,
    "white": WHITE,
    "surface": SURFACE,
    "surface_2": SURFACE_2,
    "border": BORDER,
    "border_2": BORDER_2,
    "text": TEXT,
    "text_2": TEXT_2,
    "text_3": TEXT_3,
    "red": RED,
    "red_pale": RED_PALE,
    "amber": AMBER,
    "amber_pale": AMBER_PALE,
    "green": GREEN,
    "green_pale": GREEN_PALE,
    "blue": BLUE,
    "blue_pale": BLUE_PALE,
    "navy_pale": NAVY_PALE,
    "muted": MUTED,
    "paper_warning": PAPER_WARNING,
    "super_sidebar": SUPER_SIDEBAR,
    "super_sidebar_2": SUPER_SIDEBAR_2,
    "super_sidebar_3": SUPER_SIDEBAR_3,
    "super_accent": SUPER_ACCENT,
    "super_accent_pale": SUPER_ACCENT_PALE,
}

STATUS_TONES = {
    "Paid": "teal",
    "Partial": "amber",
    "Pending": "amber",
    "Unpaid": "red",
    "Active": "teal",
    "Inactive": "red",
    "Low": "amber",
    "Critical": "red",
    "Completed": "green",
    "Cancelled": "red",
    "Processing": "blue",
    "Preparing": "blue",
    "Ready": "teal",
    "OK": "teal",
    "Done": "teal",
    "Walk-in": "gray",
    "Wholesale": "blue",
    "Reseller": "teal",
}


def color(name):
    return COLORS[name]
