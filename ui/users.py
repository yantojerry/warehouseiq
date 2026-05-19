from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components import error_dialog, warning_dialog
from backend.infrastructure.api_client import ApiError, create_user, get_user_tasks, list_roles, list_users, reset_user_password, update_user, update_user_tasks
from ui.styles import configure_table, make_badge, set_button_kind, table_item, tone_for_status
from backend.auth.roles import ROLE_ADMIN, ROLE_BOOKKEEPER, ROLE_CASHIER, ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN


class UserManagementPage(QWidget):
    def __init__(self, permissions=None, current_role=None):
        super().__init__()
        self.permissions = set(permissions or ())
        self.current_role = current_role
        self.can_view_users = self._can("users.view")
        self.can_edit_users = self._can("users.edit")
        self.can_reset_users = self._can("users.reset")
        self.can_assign_tasks = self._can("tasks.assign")
        self.can_add_users = self._can("users.add") or self._can("users.add_admin")
        self.setObjectName("content_area")
        self._build_ui()
        self.load_users()

    def _can(self, permission):
        return permission in self.permissions or self.current_role == ROLE_SUPER_ADMIN

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)
        header = QHBoxLayout()
        block = QVBoxLayout()
        title = QLabel("User Management")
        title.setObjectName("page_title")
        sub = QLabel("Manage account roles and access status")
        sub.setObjectName("page_subtitle")
        block.addWidget(title)
        block.addWidget(sub)
        header.addLayout(block)
        header.addStretch()
        if self.can_add_users:
            add = QPushButton("Add User")
            set_button_kind(add, "teal")
            add.clicked.connect(self.add_user)
            header.addWidget(add)
        root.addLayout(header)

        if not self.can_view_users:
            card = QLabel("User creation is available from the Add User button.")
            card.setObjectName("page_subtitle")
            root.addWidget(card)
            root.addStretch()
            return

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["USERNAME", "NAME", "ROLE", "STATUS", "LAST LOGIN", "ACTION"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 250)
        configure_table(self.table)
        root.addWidget(self.table)

    def load_users(self):
        if not self.can_view_users or not hasattr(self, "table"):
            return
        try:
            rows = list_users()
        except ApiError as exc:
            error_dialog(self, "Users", str(exc))
            return
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, table_item(row.get("username") or "-", bold=True))
            self.table.setItem(r, 1, table_item(row.get("display_name") or "-"))
            self.table.setItem(r, 2, table_item(row.get("role") or "-"))
            self.table.setCellWidget(r, 3, make_badge(row.get("status") or "Active", tone_for_status(row.get("status"))))
            self.table.setItem(r, 4, table_item(row.get("last_login_at") or "-"))
            self.table.setCellWidget(r, 5, self._actions(row))
            self.table.setRowHeight(r, 54)

    def _actions(self, row):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(4, 2, 4, 2)
        if self.can_edit_users:
            edit = QPushButton("Edit")
            edit.setFixedHeight(32)
            set_button_kind(edit, "outline")
            edit.clicked.connect(lambda: self.edit_user(row))
            layout.addWidget(edit)
        if self.can_reset_users:
            reset = QPushButton("Reset")
            reset.setFixedHeight(32)
            set_button_kind(reset, "ghost")
            reset.clicked.connect(lambda: self.reset_password(row))
            layout.addWidget(reset)
        if self.can_assign_tasks:
            tasks = QPushButton("Tasks")
            tasks.setFixedHeight(32)
            set_button_kind(tasks, "teal")
            tasks.clicked.connect(lambda: self.assign_tasks(row))
            layout.addWidget(tasks)
        return box

    def add_user(self):
        dialog = UserDialog(self, roles=self._available_roles())
        if dialog.exec_():
            self.load_users()

    def edit_user(self, row):
        dialog = UserDialog(self, row, roles=self._available_roles())
        if dialog.exec_():
            self.load_users()

    def reset_password(self, row):
        dialog = ResetPasswordDialog(self, row)
        if dialog.exec_():
            self.load_users()

    def assign_tasks(self, row):
        dialog = UserTaskDialog(self, row)
        dialog.exec_()

    def _available_roles(self):
        if self._can("roles.manage"):
            try:
                return [role.get("name") for role in list_roles() if role.get("name")]
            except ApiError:
                pass
        roles = [ROLE_CASHIER, ROLE_WAREHOUSEMAN, ROLE_BOOKKEEPER]
        if self._can("users.add_admin"):
            roles.append(ROLE_ADMIN)
        return roles


class UserDialog(QDialog):
    def __init__(self, parent, user=None, roles=None):
        super().__init__(parent)
        self.user = user or {}
        self.roles = roles or [ROLE_CASHIER, ROLE_WAREHOUSEMAN, ROLE_BOOKKEEPER]
        self.setWindowTitle("User")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        self.username = QLineEdit(self.user.get("username", ""))
        self.username.setFixedHeight(36)
        self.username.setEnabled(not self.user)
        self.display_name = QLineEdit(self.user.get("display_name", ""))
        self.display_name.setFixedHeight(36)
        self.password = QLineEdit()
        self.password.setFixedHeight(36)
        self.password.setEchoMode(QLineEdit.Password)
        self.role = QComboBox()
        self.role.setFixedHeight(36)
        self.role.addItems(self.roles)
        current_role = self.user.get("role", ROLE_CASHIER)
        if current_role and self.role.findText(current_role) == -1:
            self.role.addItem(current_role)
        self.role.setCurrentText(current_role)
        self.status = QComboBox()
        self.status.setFixedHeight(36)
        self.status.addItems(["Active", "Inactive"])
        self.status.setCurrentText(self.user.get("status", "Active"))
        self._add_field(layout, "Username", self.username)
        self._add_field(layout, "Display Name", self.display_name)
        if not self.user:
            self._add_field(layout, "Password", self.password)
        self._add_field(layout, "Role", self.role)
        self._add_field(layout, "Status", self.status)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        cancel = QPushButton("Cancel")
        set_button_kind(cancel, "outline")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        set_button_kind(save, "teal")
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    @staticmethod
    def _add_field(layout, label_text, widget):
        label = QLabel(label_text.upper())
        label.setObjectName("form_label")
        layout.addWidget(label)
        layout.addWidget(widget)

    def save(self):
        if not self.username.text().strip():
            warning_dialog(self, "Validation", "Username is required.")
            return
        try:
            if self.user:
                update_user(self.user["id"], {
                    "display_name": self.display_name.text().strip(),
                    "role": self.role.currentText(),
                    "status": self.status.currentText(),
                })
            else:
                if not self.password.text().strip():
                    warning_dialog(self, "Validation", "Password is required.")
                    return
                create_user({
                    "username": self.username.text().strip(),
                    "password": self.password.text().strip(),
                    "display_name": self.display_name.text().strip() or self.username.text().strip(),
                    "role": self.role.currentText(),
                    "status": self.status.currentText(),
                })
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Users", str(exc))


class ResetPasswordDialog(QDialog):
    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("Reset Password")
        self.setMinimumWidth(360)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        self.password = QLineEdit()
        self.password.setFixedHeight(36)
        self.password.setEchoMode(QLineEdit.Password)
        user_label = QLabel(f"New password for {self.user.get('username')}")
        user_label.setObjectName("form_label")
        layout.addWidget(user_label)
        password_label = QLabel("NEW PASSWORD")
        password_label.setObjectName("form_label")
        layout.addWidget(password_label)
        layout.addWidget(self.password)
        save = QPushButton("Reset Password")
        set_button_kind(save, "teal")
        save.clicked.connect(self.save)
        layout.addWidget(save)

    def save(self):
        if not self.password.text().strip():
            warning_dialog(self, "Validation", "Password is required.")
            return
        try:
            reset_user_password(self.user["id"], self.password.text().strip())
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Users", str(exc))


class UserTaskDialog(QDialog):
    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.checks = {}
        self.setWindowTitle("User Tasks")
        self.setMinimumSize(520, 620)
        self._build_ui()
        self.load_tasks()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel(f"Tasks for {self.user.get('username')}")
        title.setObjectName("login_title")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.container = QWidget()
        self.task_layout = QVBoxLayout(self.container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(8)
        scroll.setWidget(self.container)
        layout.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        cancel = QPushButton("Cancel")
        set_button_kind(cancel, "outline")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save Tasks")
        set_button_kind(save, "teal")
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def load_tasks(self):
        try:
            payload = get_user_tasks(self.user["id"])
        except ApiError as exc:
            error_dialog(self, "User Tasks", str(exc))
            return
        grouped = {}
        for permission in payload.get("permissions") or []:
            grouped.setdefault(permission.get("category") or "General", []).append(permission)
        self._clear_layout(self.task_layout)
        self.checks.clear()
        is_super_admin_user = (payload.get("user") or {}).get("role") == ROLE_SUPER_ADMIN
        for category, rows in grouped.items():
            heading = QLabel(category.upper())
            heading.setObjectName("section_label")
            self.task_layout.addWidget(heading)
            for permission in rows:
                row = QFrame()
                row.setObjectName("card_body")
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(10, 6, 10, 6)
                row_layout.setSpacing(8)
                check = QCheckBox(permission.get("label") or permission.get("permission_key"))
                check.setStyleSheet("QCheckBox { color: palette(text); spacing: 6px; }")
                check.setChecked(bool(permission.get("is_enabled")))
                check.setEnabled(not is_super_admin_user)
                row_layout.addWidget(check)
                self.task_layout.addWidget(row)
                self.checks[permission["id"]] = check
        self.task_layout.addStretch()

    def save(self):
        permissions = [
            {"permission_id": permission_id, "is_enabled": check.isChecked()}
            for permission_id, check in self.checks.items()
        ]
        try:
            update_user_tasks(self.user["id"], permissions)
            self.accept()
        except ApiError as exc:
            error_dialog(self, "User Tasks", str(exc))

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                UserTaskDialog._clear_layout(child_layout)
