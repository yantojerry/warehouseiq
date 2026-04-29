from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components import error_dialog, warning_dialog
from utils.api_client import ApiError, create_user, list_users, reset_user_password, update_user
from utils.styles import configure_table, make_badge, set_button_kind, table_item, tone_for_status


class UserManagementPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("content_area")
        self._build_ui()
        self.load_users()

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
        add = QPushButton("Add User")
        set_button_kind(add, "teal")
        add.clicked.connect(self.add_user)
        header.addWidget(add)
        root.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["USERNAME", "NAME", "ROLE", "STATUS", "LAST LOGIN", "ACTION"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 220)
        configure_table(self.table)
        root.addWidget(self.table)

    def load_users(self):
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
            self.table.setRowHeight(r, 46)

    def _actions(self, row):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(4, 2, 4, 2)
        edit = QPushButton("Edit")
        set_button_kind(edit, "outline")
        edit.clicked.connect(lambda: self.edit_user(row))
        reset = QPushButton("Reset")
        set_button_kind(reset, "ghost")
        reset.clicked.connect(lambda: self.reset_password(row))
        layout.addWidget(edit)
        layout.addWidget(reset)
        return box

    def add_user(self):
        dialog = UserDialog(self)
        if dialog.exec_():
            self.load_users()

    def edit_user(self, row):
        dialog = UserDialog(self, row)
        if dialog.exec_():
            self.load_users()

    def reset_password(self, row):
        dialog = ResetPasswordDialog(self, row)
        if dialog.exec_():
            self.load_users()


class UserDialog(QDialog):
    def __init__(self, parent, user=None):
        super().__init__(parent)
        self.user = user or {}
        self.setWindowTitle("User")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        form = QFormLayout()
        self.username = QLineEdit(self.user.get("username", ""))
        self.username.setEnabled(not self.user)
        self.display_name = QLineEdit(self.user.get("display_name", ""))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.role = QComboBox()
        self.role.addItems(["Admin", "Sales Staff", "Warehouse Staff", "Bookkeeper"])
        self.role.setCurrentText(self.user.get("role", "Sales Staff"))
        self.status = QComboBox()
        self.status.addItems(["Active", "Inactive"])
        self.status.setCurrentText(self.user.get("status", "Active"))
        form.addRow("Username", self.username)
        form.addRow("Display Name", self.display_name)
        if not self.user:
            form.addRow("Password", self.password)
        form.addRow("Role", self.role)
        form.addRow("Status", self.status)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        set_button_kind(cancel, "outline")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        set_button_kind(save, "teal")
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        layout.addWidget(QLabel(f"New password for {user.get('username')}"))
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
