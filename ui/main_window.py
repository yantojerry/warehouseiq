import inspect

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, pyqtSignal
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
from ui.modules import MODULE_BY_KEY, allowed_modules, can_access, first_accessible_module
from ui.settings import apply_saved_user_preferences, reset_application_theme
from utils.styles import canonical_role, display_role, make_badge, repolish
from utils.roles import is_super_admin
from utils.theme import COLORS


class MainWindow(QMainWindow):
    logout_requested = pyqtSignal()

    def __init__(self, username=None, role=None, display_name=None, permissions=None):
        super().__init__()
        self.username = username or "User"
        self.display_name = display_name or self.username
        self.role = canonical_role(role) or "Admin"
        self.permissions = permissions or []
        self.permission_keys = {
            item.get("key") if isinstance(item, dict) else str(item)
            for item in self.permissions
        }
        self._is_super_admin = is_super_admin(self.role)
        self.setWindowTitle("WarehouseIQ Warehouse Management System")
        self.setMinimumSize(1200, 720)

        self._nav_buttons = {}
        self._nav_group_buttons = {}
        self._nav_group_containers = {}
        self._nav_group_modules = {}
        self._pages = {}
        self._module_indexes = {}
        self._current_key = None
        self._collapsed = False
        self._sidebar_width = 232
        self._sidebar_collapsed_width = 68
        self.toast = ToastManager(self)

        self._stack = QStackedWidget()
        self._build_ui()
        if self._is_super_admin:
            reset_application_theme()
        else:
            apply_saved_user_preferences()
        self.navigate_to(first_accessible_module(self.role, self.permission_keys))

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
        sidebar.setObjectName("sidebar_super_admin" if self._is_super_admin else "sidebar")
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
        frame.setObjectName("sidebar_brand_super_admin" if self._is_super_admin else "sidebar_brand")
        frame.setFixedHeight(68)
        row = QHBoxLayout(frame)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(8)

        self.brand_logo = QLabel("W")
        self.brand_logo.setObjectName("brand_logo_super_admin" if self._is_super_admin else "brand_logo")
        self.brand_logo.setFixedSize(32, 32)
        self.brand_logo.setAlignment(Qt.AlignCenter)
        row.addWidget(self.brand_logo)

        self.brand_text = QWidget()
        col = QVBoxLayout(self.brand_text)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        label = QLabel("WarehouseIQ")
        label.setObjectName("brand_label")
        accent = QLabel("Command Center" if self._is_super_admin else "Management")
        accent.setObjectName("brand_accent_super_admin" if self._is_super_admin else "brand_accent")
        col.addWidget(label)
        col.addWidget(accent)
        row.addWidget(self.brand_text, 1)

        toggle = QToolButton()
        toggle.setObjectName("nav_button_super" if self._is_super_admin else "nav_button")
        toggle.setIcon(icon("fa5s.bars", COLORS["white"]))
        toggle.setCursor(Qt.PointingHandCursor)
        toggle.clicked.connect(self.toggle_sidebar)
        row.addWidget(toggle)
        return frame

    def _profile_card(self):
        frame = QFrame()
        frame.setObjectName("sidebar_profile_super_admin" if self._is_super_admin else "sidebar_profile")
        row = QHBoxLayout(frame)
        row.setContentsMargins(16, 16, 16, 16)
        row.setSpacing(10)

        avatar = QLabel(self._initials(self.display_name))
        avatar.setObjectName("user_avatar_super_admin" if self._is_super_admin else "user_avatar")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(40, 40)
        row.addWidget(avatar)

        self.profile_text = QWidget()
        col = QVBoxLayout(self.profile_text)
        col.setSpacing(3)
        col.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(self.display_name)
        name_lbl.setObjectName("profile_name")
        tone = {"Super Admin": "super_admin", "Admin": "navy", "Cashier": "blue", "Warehouseman": "amber", "Bookkeeper": "teal"}.get(self.role, "gray")
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
        modules = allowed_modules(self.role, self.permission_keys)
        if self._is_super_admin:
            self._populate_super_admin_nav(modules)
            return

        last_group = None
        settings_module = MODULE_BY_KEY.get("settings")
        settings_accessible = settings_module and can_access(self.role, "settings", self.permission_keys)
        visible_modules = [module for module in modules if module.key != "settings"]
        for index, module in enumerate(visible_modules):
            if module.group != last_group:
                if last_group is not None and settings_accessible:
                    self._nav_vbox.addWidget(self._nav_button(settings_module))
                label = QLabel(module.group.upper())
                label.setObjectName("nav_section_label")
                label.setContentsMargins(10, 8 if last_group else 4, 0, 2)
                self._nav_vbox.addWidget(label)
                last_group = module.group
            self._nav_vbox.addWidget(self._nav_button(module))
            if index == len(visible_modules) - 1 and settings_accessible:
                self._nav_vbox.addWidget(self._nav_button(settings_module))

        if not visible_modules and settings_accessible:
            label = QLabel("SYSTEM")
            label.setObjectName("nav_section_label")
            label.setContentsMargins(10, 4, 0, 2)
            self._nav_vbox.addWidget(label)
            self._nav_vbox.addWidget(self._nav_button(settings_module))

    def _populate_super_admin_nav(self, modules):
        grouped = {}
        for module in modules:
            grouped.setdefault(module.group, []).append(module)

        for group, rows in grouped.items():
            parent = QToolButton()
            parent.setObjectName("nav_parent_super")
            parent.setMinimumHeight(38)
            parent.setArrowType(Qt.RightArrow)
            parent.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            parent.setText(group)
            parent.setToolTip(group)
            parent.setCursor(Qt.PointingHandCursor)
            parent.clicked.connect(lambda checked=False, name=group: self._toggle_nav_group(name))
            self._nav_vbox.addWidget(parent)
            self._nav_group_buttons[group] = parent
            self._nav_group_modules[group] = {module.key for module in rows}

            container = QWidget()
            container.setObjectName("sidebar_nav_group")
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(14, 0, 0, 4)
            container_layout.setSpacing(4)
            for module in rows:
                container_layout.addWidget(self._nav_button(module, super_admin=True))
            container.setVisible(False)
            self._nav_vbox.addWidget(container)
            self._nav_group_containers[group] = container

    def _nav_button(self, module, super_admin=False):
        btn = QToolButton()
        btn.setObjectName("nav_button_super" if super_admin else "nav_button")
        btn.setMinimumHeight(36)
        btn.setIconSize(QSize(16, 16))
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setIcon(icon(module.icon, COLORS["muted"]))
        btn.setText(module.label)
        btn.setToolTip(module.label)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, key=module.key: self.navigate_to(key))
        self._nav_buttons.setdefault(module.key, []).append(btn)
        return btn

    def _toggle_nav_group(self, group):
        container = self._nav_group_containers.get(group)
        button = self._nav_group_buttons.get(group)
        if not container or not button:
            return
        is_expanded = not container.isVisible()
        container.setVisible(is_expanded)
        button.setArrowType(Qt.DownArrow if is_expanded else Qt.RightArrow)
        self._update_active_nav()

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
        if not can_access(self.role, module_key, self.permission_keys):
            module = MODULE_BY_KEY.get(module_key)
            label = module.label if module else module_key
            error_dialog(self, "Access Denied", f"Your role cannot access {label}.")
            return False

        if module_key not in self._module_indexes:
            module = MODULE_BY_KEY[module_key]
            page = self._create_page(module)
            self._pages[module_key] = page
            self._module_indexes[module_key] = self._stack.addWidget(page)

        self._stack.setCurrentIndex(self._module_indexes[module_key])
        self._current_key = module_key
        self._update_active_nav()
        return True

    def _create_page(self, module):
        kwargs = {}
        try:
            parameters = inspect.signature(module.page_class.__init__).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "username" in parameters:
            kwargs["username"] = self.display_name
        if "permissions" in parameters:
            kwargs["permissions"] = self.permission_keys
        if "current_role" in parameters:
            kwargs["current_role"] = self.role
        if "current_user" in parameters:
            kwargs["current_user"] = self.username
        if "display_name" in parameters:
            kwargs["display_name"] = self.display_name
        if "navigate_callback" in parameters:
            kwargs["navigate_callback"] = self.navigate_to
        page = module.page_class(**kwargs)
        if hasattr(page, "set_permissions"):
            page.set_permissions(self.permission_keys)
        return page

    def _update_active_nav(self):
        for key, buttons in self._nav_buttons.items():
            is_active = key == self._current_key
            module = MODULE_BY_KEY[key]
            color = COLORS["white"] if is_active else COLORS["muted"]
            object_name = "nav_button_active" if is_active else "nav_button"
            if self._is_super_admin:
                object_name = "nav_button_super_active" if is_active else "nav_button_super"
            for button in buttons:
                button.setObjectName(object_name)
                button.setIcon(icon(module.icon, color))
                repolish(button)

        for group, button in self._nav_group_buttons.items():
            container = self._nav_group_containers.get(group)
            group_is_active = self._current_key in self._nav_group_modules.get(group, set())
            if group_is_active:
                button.setObjectName("nav_parent_super_active")
            elif container and container.isVisible():
                button.setObjectName("nav_parent_super_expanded")
            else:
                button.setObjectName("nav_parent_super")
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
        for buttons in self._nav_buttons.values():
            for btn in buttons:
                btn.setToolButtonStyle(Qt.ToolButtonIconOnly if self._collapsed else Qt.ToolButtonTextBesideIcon)
        for btn in self._nav_group_buttons.values():
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly if self._collapsed else Qt.ToolButtonTextBesideIcon)

    @staticmethod
    def _initials(username):
        parts = [p for p in str(username or "User").replace("_", " ").split() if p]
        if not parts:
            return "U"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()
