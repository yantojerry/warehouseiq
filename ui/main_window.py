from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.components import ToastManager, error_dialog
from ui.components.icons import icon
from ui.modules import MODULE_BY_KEY, ROLE_START_PAGE, allowed_modules, can_access
from utils.styles import canonical_role, display_role, make_badge, repolish
from utils.theme import COLORS


class MainWindow(QMainWindow):
    logout_requested = pyqtSignal()

    def __init__(self, username=None, role=None, display_name=None):
        super().__init__()
        self.username = username or "User"
        self.display_name = display_name or self.username
        self.role = canonical_role(role) or "Admin"
        self.setWindowTitle("MIHS General Merchandise Management System")
        self.setMinimumSize(1200, 720)

        self._nav_buttons = {}
        self._pages = {}
        self._module_indexes = {}
        self._current_key = None
        self._collapsed = False
        self._sidebar_width = 232
        self._sidebar_collapsed_width = 68
        self.toast = ToastManager(self)

        self._stack = QStackedWidget()
        self._build_ui()
        self.navigate_to(ROLE_START_PAGE.get(self.role, "dashboard"))

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("content_area")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar)
        root.addWidget(self._stack, 1)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(self._sidebar_width)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._brand_header())
        layout.addWidget(self._h_divider())
        layout.addWidget(self._nav_scroll(), 1)
        layout.addWidget(self._h_divider())
        layout.addWidget(self._profile_card())
        layout.addWidget(self._logout_btn())
        return sidebar

    def _brand_header(self):
        frame = QFrame()
        frame.setObjectName("sidebar_brand")
        frame.setFixedHeight(64)
        row = QHBoxLayout(frame)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(8)

        self.brand_logo = QLabel("M")
        self.brand_logo.setObjectName("brand_logo")
        self.brand_logo.setFixedSize(32, 32)
        self.brand_logo.setAlignment(Qt.AlignCenter)
        row.addWidget(self.brand_logo)

        self.brand_text = QWidget()
        col = QVBoxLayout(self.brand_text)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        label = QLabel("MIHS General")
        label.setObjectName("brand_label")
        accent = QLabel("Merchandise")
        accent.setObjectName("brand_accent")
        col.addWidget(label)
        col.addWidget(accent)
        row.addWidget(self.brand_text, 1)

        toggle = QToolButton()
        toggle.setObjectName("nav_button")
        toggle.setIcon(icon("fa5s.bars", COLORS["white"]))
        toggle.setCursor(Qt.PointingHandCursor)
        toggle.clicked.connect(self.toggle_sidebar)
        row.addWidget(toggle)
        return frame

    def _profile_card(self):
        frame = QFrame()
        frame.setObjectName("sidebar_profile")
        row = QHBoxLayout(frame)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(10)

        avatar = QLabel(self._initials(self.display_name))
        avatar.setObjectName("user_avatar")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(40, 40)
        row.addWidget(avatar)

        self.profile_text = QWidget()
        col = QVBoxLayout(self.profile_text)
        col.setSpacing(3)
        col.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(self.display_name)
        name_lbl.setObjectName("profile_name")
        tone = {"Admin": "navy", "Sales Staff": "blue", "Warehouse Staff": "amber", "Bookkeeper": "teal"}.get(self.role, "gray")
        col.addWidget(name_lbl)
        col.addWidget(make_badge(display_role(self.role), tone))
        row.addWidget(self.profile_text, 1)
        return frame

    def _nav_scroll(self):
        scroll = QScrollArea()
        scroll.setObjectName("sidebar_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("sidebar_nav")
        self._nav_vbox = QVBoxLayout(container)
        self._nav_vbox.setContentsMargins(10, 10, 10, 10)
        self._nav_vbox.setSpacing(4)
        self._populate_nav()
        self._nav_vbox.addStretch()
        scroll.setWidget(container)
        return scroll

    def _populate_nav(self):
        last_group = None
        for module in allowed_modules(self.role):
            if module.group != last_group:
                label = QLabel(module.group.upper())
                label.setObjectName("nav_section_label")
                label.setContentsMargins(10, 8 if last_group else 4, 0, 2)
                self._nav_vbox.addWidget(label)
                last_group = module.group
            btn = QToolButton()
            btn.setObjectName("nav_button")
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setIcon(icon(module.icon, COLORS["muted"]))
            btn.setText(module.label)
            btn.setToolTip(module.label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, key=module.key: self.navigate_to(key))
            self._nav_vbox.addWidget(btn)
            self._nav_buttons[module.key] = btn

    def _logout_btn(self):
        btn = QPushButton("Sign Out")
        btn.setObjectName("sidebar_logout")
        btn.setFixedHeight(44)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.logout_requested.emit)
        return btn

    def _h_divider(self):
        line = QFrame()
        line.setObjectName("sidebar_divider")
        line.setFixedHeight(1)
        return line

    def navigate_to(self, module_key):
        if not can_access(self.role, module_key):
            module = MODULE_BY_KEY.get(module_key)
            label = module.label if module else module_key
            error_dialog(self, "Access Denied", f"Your role cannot access {label}.")
            return False

        if module_key not in self._module_indexes:
            module = MODULE_BY_KEY[module_key]
            page = module.page_class(username=self.display_name) if module.key == "dashboard" else module.page_class()
            self._pages[module_key] = page
            self._module_indexes[module_key] = self._stack.addWidget(page)

        self._stack.setCurrentIndex(self._module_indexes[module_key])
        self._current_key = module_key
        self._update_active_nav()
        return True

    def _update_active_nav(self):
        for key, button in self._nav_buttons.items():
            is_active = key == self._current_key
            button.setObjectName("nav_button_active" if is_active else "nav_button")
            module = MODULE_BY_KEY[key]
            color = COLORS["white"] if is_active else COLORS["muted"]
            button.setIcon(icon(module.icon, color))
            repolish(button)

    def toggle_sidebar(self):
        self._collapsed = not self._collapsed
        target = self._sidebar_collapsed_width if self._collapsed else self._sidebar_width
        animation = QPropertyAnimation(self.sidebar, b"minimumWidth", self)
        animation.setDuration(200)
        animation.setStartValue(self.sidebar.width())
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start(QPropertyAnimation.DeleteWhenStopped)
        self.sidebar.setMaximumWidth(target)
        self.brand_text.setVisible(not self._collapsed)
        self.profile_text.setVisible(not self._collapsed)
        for btn in self._nav_buttons.values():
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly if self._collapsed else Qt.ToolButtonTextBesideIcon)

    @staticmethod
    def _initials(username):
        parts = [p for p in str(username or "User").replace("_", " ").split() if p]
        if not parts:
            return "U"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()
