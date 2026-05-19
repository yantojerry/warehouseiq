import json
import os
from pathlib import Path

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.auth.roles import ROLE_SUPER_ADMIN, canonical_role
from ui.styles import APP_THEME, LIGHT_MODE_OVERRIDES, make_badge, repolish, set_button_kind
from ui.theme import COLORS


CONFIG_DIR = Path(os.getenv("WAREHOUSEIQ_CONFIG_DIR", Path.home() / ".warehouseiq"))
CONFIG_PATH = CONFIG_DIR / "user_settings.json"
SUPER_ADMIN_CONFIG_PATH = CONFIG_DIR / "super_admin_settings.json"

DEFAULT_USER_PREFERENCES = {
    "mode": "Dark",
    "text_size": "Medium",
    "language": "English",
    "theme_color": COLORS["teal"],
}

DEFAULT_SUPER_ADMIN_PREFERENCES = {
    "mode": "Dark",
    "profile": "super_admin",
    "text_size": "Medium",
    "language": "English",
    "theme_color": COLORS["super_accent"],
}

TEXT_SIZE_PIXELS = {
    "Small": 12,
    "Medium": 13,
    "Large": 15,
}


def load_user_preferences():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        payload = {}
    preferences = dict(DEFAULT_USER_PREFERENCES)
    preferences.update(payload if isinstance(payload, dict) else {})
    preferences["theme_color"] = _valid_color(preferences.get("theme_color"), DEFAULT_USER_PREFERENCES["theme_color"])
    if preferences.get("mode") not in {"Light", "Dark"}:
        preferences["mode"] = DEFAULT_USER_PREFERENCES["mode"]
    if preferences.get("text_size") not in TEXT_SIZE_PIXELS:
        preferences["text_size"] = DEFAULT_USER_PREFERENCES["text_size"]
    return preferences


def load_super_admin_preferences():
    try:
        with SUPER_ADMIN_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        payload = {}
    preferences = dict(DEFAULT_SUPER_ADMIN_PREFERENCES)
    preferences.update(payload if isinstance(payload, dict) else {})
    if preferences.get("mode") not in {"Light", "Dark"}:
        preferences["mode"] = DEFAULT_SUPER_ADMIN_PREFERENCES["mode"]
    preferences["theme_color"] = _valid_color(
        preferences.get("theme_color"),
        DEFAULT_SUPER_ADMIN_PREFERENCES["theme_color"],
    )
    if preferences.get("text_size") not in TEXT_SIZE_PIXELS:
        preferences["text_size"] = DEFAULT_SUPER_ADMIN_PREFERENCES["text_size"]
    return preferences


def save_user_preferences(preferences):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(preferences, handle, indent=2)


def save_super_admin_preferences(preferences):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with SUPER_ADMIN_CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(preferences, handle, indent=2)


def reset_application_theme():
    app = QApplication.instance()
    if app:
        app.setStyleSheet(APP_THEME)


def apply_saved_user_preferences():
    apply_user_preferences(load_user_preferences())


def apply_saved_super_admin_preferences():
    apply_user_preferences(load_super_admin_preferences())


def apply_user_preferences(preferences):
    app = QApplication.instance()
    if not app:
        return
    accent = _valid_color(preferences.get("theme_color"), COLORS["teal"])
    mode = preferences.get("mode") if preferences.get("mode") in {"Light", "Dark"} else "Dark"
    text_size = TEXT_SIZE_PIXELS.get(preferences.get("text_size"), TEXT_SIZE_PIXELS["Medium"])
    is_light = mode == "Light"
    background = "#f6f7fb" if is_light else COLORS["background"]
    page_text = COLORS["text"] if is_light else COLORS["white"]
    hover = _mix(accent, "#ffffff", 0.18)
    pale = _mix(accent, "#ffffff", 0.84)
    is_super_admin_theme = preferences.get("profile") == "super_admin"

    mode_overrides = LIGHT_MODE_OVERRIDES if is_light else ""
    app.setStyleSheet(
        APP_THEME
        + mode_overrides
        + (_super_admin_theme_overrides(is_light, accent, pale, hover) if is_super_admin_theme else "")
        + f"""
QWidget {{
    font-size: {text_size}px;
}}

QMainWindow, #content_area, #page_content {{
    background-color: {background};
}}

#page_title {{
    color: {page_text};
}}

#brand_logo {{
    background-color: {accent};
}}

#brand_accent {{
    color: {hover};
}}

QToolButton#nav_button_active {{
    background-color: {accent};
    color: {COLORS["white"]};
}}

QPushButton, QPushButton#btn_primary, QPushButton#btn_teal, QPushButton#btn_success {{
    background-color: {accent};
    color: {COLORS["white"]};
}}

QPushButton:hover, QPushButton#btn_primary:hover {{
    background-color: {hover};
}}

QPushButton#btn_outline:hover, QPushButton#btn_ghost:hover {{
    background-color: {pale};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
    border: 1px solid {accent};
}}

QComboBox QAbstractItemView {{
    selection-background-color: {pale};
    selection-color: {accent};
}}

QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}

QLabel#badge_teal {{
    background-color: {pale};
    color: {accent};
}}
"""
    )


class SettingsPage(QWidget):
    def __init__(self, current_role=None, display_name=None, permissions=None):
        super().__init__()
        self.current_role = canonical_role(current_role) or "User"
        self.display_name = display_name or "User"
        self.permissions = set(permissions or ())
        if self.current_role == ROLE_SUPER_ADMIN:
            self.preferences = load_super_admin_preferences()
        else:
            self.preferences = load_user_preferences()
        self._loading = False
        self.color_swatch = None
        self.setObjectName("content_area")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Super Admin Settings" if self.current_role == ROLE_SUPER_ADMIN else "Settings")
        title.setObjectName("page_title")
        subtitle = QLabel(
            "System authority controls"
            if self.current_role == ROLE_SUPER_ADMIN
            else "Personal workspace preferences"
        )
        subtitle.setObjectName("page_subtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        if self.current_role == ROLE_SUPER_ADMIN:
            self._build_super_admin_settings(root)
        else:
            self._build_user_settings(root)
        root.addStretch()

    def _build_user_settings(self, root):
        account = QFrame()
        account.setObjectName("card")
        account_layout = QVBoxLayout(account)
        account_layout.setContentsMargins(18, 16, 18, 16)
        account_layout.setSpacing(10)
        account_layout.addWidget(self._row("Signed in as", self.display_name))
        account_layout.addWidget(self._separator())
        account_layout.addWidget(self._row("Role", self.current_role))
        root.addWidget(account)

        controls = QFrame()
        controls.setObjectName("card")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 16, 18, 16)
        controls_layout.setSpacing(12)

        self.mode_toggle = QCheckBox("Dark mode")
        self.mode_toggle.setChecked(self.preferences.get("mode") == "Dark")
        self.mode_toggle.stateChanged.connect(self._save_from_controls)
        controls_layout.addWidget(self._control_row("Mode", self.mode_toggle))

        self.text_size_combo = QComboBox()
        self.text_size_combo.addItems(["Small", "Medium", "Large"])
        self.text_size_combo.setCurrentText(self.preferences.get("text_size", "Medium"))
        self.text_size_combo.currentTextChanged.connect(self._save_from_controls)
        controls_layout.addWidget(self._control_row("Text Size", self.text_size_combo))

        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Filipino", "Spanish", "Chinese"])
        language = self.preferences.get("language", "English")
        if self.language_combo.findText(language) == -1:
            self.language_combo.addItem(language)
        self.language_combo.setCurrentText(language)
        self.language_combo.currentTextChanged.connect(self._save_from_controls)
        controls_layout.addWidget(self._control_row("Language", self.language_combo))

        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(10)
        self.color_swatch = QFrame()
        self.color_swatch.setFixedSize(28, 28)
        self._update_color_swatch()
        pick_color = QPushButton("Choose Color")
        set_button_kind(pick_color, "outline")
        pick_color.clicked.connect(self._pick_color)
        color_layout.addWidget(self.color_swatch)
        color_layout.addWidget(pick_color)
        color_layout.addStretch()
        controls_layout.addWidget(self._control_row("Theme Color", color_row))

        root.addWidget(controls)

    def _build_super_admin_settings(self, root):
        account = QFrame()
        account.setObjectName("card")
        account_layout = QVBoxLayout(account)
        account_layout.setContentsMargins(18, 16, 18, 16)
        account_layout.setSpacing(10)
        account_layout.addWidget(self._row("Signed in as", self.display_name, compact=True))
        account_layout.addWidget(self._separator())
        account_layout.addWidget(self._row("Role", self.current_role, compact=True))
        account_layout.addWidget(self._separator())
        account_layout.addWidget(self._row("Authority", "All permissions enforced", compact=True))
        root.addWidget(account)

        system = QFrame()
        system.setObjectName("card")
        system_layout = QVBoxLayout(system)
        system_layout.setContentsMargins(18, 16, 18, 16)
        system_layout.setSpacing(10)
        system_layout.addWidget(self._row("Permission Mode", "Super Admin locked", compact=True))
        system_layout.addWidget(self._separator())
        system_layout.addWidget(self._row("Audit Visibility", "Full system activity", compact=True))
        system_layout.addWidget(self._separator())
        system_layout.addWidget(self._row("Enabled Task Count", str(len(self.permissions)), compact=True))
        system_layout.addWidget(self._separator())
        self.super_admin_mode_toggle = QCheckBox("Dark mode")
        self.super_admin_mode_toggle.setChecked(self.preferences.get("mode") == "Dark")
        self.super_admin_mode_toggle.stateChanged.connect(self._save_super_admin_mode)
        system_layout.addWidget(self._control_row("Theme Mode", self.super_admin_mode_toggle))
        system_layout.addWidget(make_badge("Super Admin Only", "super_admin"))
        root.addWidget(system)

    def _save_super_admin_mode(self):
        if self._loading:
            return
        self.preferences = dict(DEFAULT_SUPER_ADMIN_PREFERENCES)
        self.preferences["mode"] = "Dark" if self.super_admin_mode_toggle.isChecked() else "Light"
        save_super_admin_preferences(self.preferences)
        apply_user_preferences(self.preferences)

    def _save_from_controls(self):
        if self._loading:
            return
        self.preferences = {
            "mode": "Dark" if self.mode_toggle.isChecked() else "Light",
            "text_size": self.text_size_combo.currentText(),
            "language": self.language_combo.currentText(),
            "theme_color": self.preferences.get("theme_color", COLORS["teal"]),
        }
        save_user_preferences(self.preferences)
        apply_user_preferences(self.preferences)

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.preferences.get("theme_color", COLORS["teal"])), self, "Theme Color")
        if not color.isValid():
            return
        self.preferences["theme_color"] = color.name()
        self._update_color_swatch()
        self._save_from_controls()

    def _update_color_swatch(self):
        if not self.color_swatch:
            return
        color = _valid_color(self.preferences.get("theme_color"), COLORS["teal"])
        self.color_swatch.setStyleSheet(f"background-color: {color}; border: 1px solid {COLORS['border_2']}; border-radius: 6px;")
        repolish(self.color_swatch)

    def _row(self, label, value, compact=False):
        row = QFrame()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        left = QLabel(label)
        left.setObjectName("form_label")
        left.setMinimumWidth(150 if compact else 0)
        right = QLabel(value or "-")
        right.setObjectName("card_title")
        right.setWordWrap(True)
        layout.addWidget(left)
        if compact:
            layout.addWidget(right, 1)
        else:
            layout.addStretch()
            layout.addWidget(right)
        return row

    def _control_row(self, label, control):
        row = QFrame()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        left = QLabel(label)
        left.setObjectName("form_label")
        left.setMinimumWidth(120)
        layout.addWidget(left)
        layout.addWidget(control, 1)
        return row

    @staticmethod
    def _separator():
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setFixedHeight(1)
        return line


def _valid_color(value, fallback):
    color = QColor(str(value or ""))
    return color.name() if color.isValid() else fallback


def _mix(color, target, amount):
    source = QColor(color)
    dest = QColor(target)
    amount = max(0.0, min(1.0, amount))
    red = int(source.red() + (dest.red() - source.red()) * amount)
    green = int(source.green() + (dest.green() - source.green()) * amount)
    blue = int(source.blue() + (dest.blue() - source.blue()) * amount)
    return QColor(red, green, blue).name()


def _super_admin_theme_overrides(is_light, accent, pale, hover):
    if not is_light:
        return f"""
#sidebar_super_admin, #sidebar_brand_super_admin {{
    background-color: {COLORS["super_sidebar"]};
    border-color: {COLORS["super_sidebar_3"]};
}}

#sidebar_profile_super_admin {{
    background-color: {COLORS["super_sidebar_2"]};
}}

#brand_label, #profile_name {{
    color: {COLORS["white"]};
}}

#brand_accent_super_admin {{
    color: {COLORS["super_accent"]};
}}

#brand_logo_super_admin {{
    background-color: {COLORS["super_accent"]};
    color: {COLORS["super_sidebar"]};
}}

#user_avatar_super_admin {{
    background-color: {COLORS["super_sidebar_3"]};
    color: {COLORS["super_accent_pale"]};
    border-color: {COLORS["super_accent"]};
}}

QToolButton#nav_parent_super, QToolButton#nav_button_super {{
    color: {COLORS["muted"]};
    background-color: transparent;
}}

QToolButton#nav_parent_super:hover, QToolButton#nav_button_super:hover,
QToolButton#nav_parent_super_expanded {{
    background-color: {COLORS["super_sidebar_2"]};
    color: {COLORS["super_accent_pale"]};
}}

QToolButton#nav_parent_super_active, QToolButton#nav_button_super_active {{
    background-color: {COLORS["super_accent"]};
    color: {COLORS["super_sidebar"]};
}}
"""
    return f"""
#sidebar_super_admin, #sidebar_brand_super_admin, #sidebar_profile_super_admin {{
    background-color: {COLORS["white"]};
    border-color: {COLORS["border"]};
}}

#sidebar_super_admin {{
    border-right: 1px solid {COLORS["border"]};
}}

#sidebar_divider {{
    background-color: {COLORS["border"]};
}}

#brand_label, #profile_name {{
    color: {COLORS["text"]};
}}

#brand_accent_super_admin {{
    color: {accent};
}}

#brand_logo_super_admin {{
    background-color: {accent};
    color: {COLORS["super_sidebar"]};
}}

#user_avatar_super_admin {{
    background-color: {pale};
    color: {COLORS["super_sidebar"]};
    border-color: {accent};
}}

QToolButton#nav_parent_super, QToolButton#nav_button_super {{
    background-color: transparent;
    color: {COLORS["text_2"]};
}}

QToolButton#nav_parent_super:hover, QToolButton#nav_button_super:hover {{
    background-color: {pale};
    color: {COLORS["super_sidebar"]};
}}

QToolButton#nav_parent_super_expanded {{
    background-color: {pale};
    color: {COLORS["super_sidebar"]};
}}

QToolButton#nav_parent_super_active, QToolButton#nav_button_super_active {{
    background-color: {accent};
    color: {COLORS["super_sidebar"]};
}}

QPushButton#sidebar_logout {{
    color: {COLORS["text_3"]};
}}

QPushButton#sidebar_logout:hover {{
    background-color: {COLORS["red_pale"]};
    color: {COLORS["red"]};
}}

QLabel#badge_super_admin {{
    background-color: {pale};
    color: {COLORS["super_sidebar"]};
}}
"""
