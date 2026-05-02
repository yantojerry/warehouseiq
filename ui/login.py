from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ui.components import error_dialog, info_dialog, warning_dialog
from utils.api_client import ApiError, register, login as api_login
from utils.styles import APP_THEME, canonical_role, set_button_kind


SUPPORTED_ROLES = {"Super Admin", "Admin", "Warehouseman", "Bookkeeper", "Cashier"}


class CreateAccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WarehouseIQ - Create Account")
        self.setFixedSize(460, 600)
        self.setAttribute(Qt.WA_StyledBackground)
        self._build_ui()
        self.setStyleSheet(APP_THEME)

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(24, 24, 24, 24)
        main.setAlignment(Qt.AlignCenter)
        card = QFrame()
        card.setObjectName("login_card")
        card.setFixedWidth(380)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)
        title = QLabel("Create Account")
        title.setObjectName("login_title")
        layout.addWidget(title)
        subtitle = QLabel("Super Admin or Admin can manage users later from User Management.")
        subtitle.setObjectName("login_subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        self.display_name_input = self._add_input(layout, "Display Name", "Enter full name")
        self.username_input = self._add_input(layout, "Username", "Enter username")
        self.role_combo = QComboBox()
        self.role_combo.setFixedHeight(36)
        self.role_combo.addItems(["Cashier", "Warehouseman", "Bookkeeper"])
        role_label = self._label("Role")
        role_label.setObjectName("form_label")
        layout.addWidget(role_label)
        layout.addWidget(self.role_combo)
        self.password_input = self._add_input(layout, "Password", "Enter password", password=True)
        self.confirm_password_input = self._add_input(layout, "Confirm Password", "Confirm password", password=True)
        submit = QPushButton("Submit")
        set_button_kind(submit, "teal")
        submit.clicked.connect(self.submit)
        layout.addWidget(submit)

        back_btn = QPushButton("Back to Login")
        set_button_kind(back_btn, "ghost")
        back_btn.clicked.connect(self.reject)
        layout.addWidget(back_btn)
        main.addWidget(card, alignment=Qt.AlignCenter)

    def _label(self, text):
        label = QLabel(text.upper())
        label.setObjectName("form_label")
        return label

    def _add_input(self, layout, label_text, placeholder, password=False):
        layout.addWidget(self._label(label_text))
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setFixedHeight(40)
        if password:
            line_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(line_edit)
        return line_edit

    def submit(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        confirm = self.confirm_password_input.text().strip()
        if not username or not password or not confirm:
            warning_dialog(self, "Input Error", "Please fill in all fields.")
            return
        if password != confirm:
            warning_dialog(self, "Input Error", "Password and confirm password do not match.")
            self.confirm_password_input.clear()
            return
        try:
            register(username, password, self.role_combo.currentText(), self.display_name_input.text().strip() or username)
        except ApiError as exc:
            error_dialog(self, "Create Account Failed", str(exc))
            return
        info_dialog(self, "Create Account", "Account created successfully. You can now sign in.")
        self.accept()


class ForgotPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WarehouseIQ - Reset Password")
        self.setFixedSize(420, 220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        title = QLabel("Reset Password")
        title.setObjectName("login_title")
        message = QLabel("Password resets are handled by an Admin in User Management.")
        message.setObjectName("login_subtitle")
        message.setWordWrap(True)
        close = QPushButton("OK")
        set_button_kind(close, "teal")
        close.clicked.connect(self.accept)
        layout.addWidget(title)
        layout.addWidget(message)
        layout.addWidget(close)
        self.setStyleSheet(APP_THEME)


class LoginPage(QDialog):
    login_success = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WarehouseIQ - Login")
        self.setFixedSize(500, 600)
        self.setObjectName("login_page")
        self.setAttribute(Qt.WA_StyledBackground)
        self.authenticated_username = None
        self.authenticated_display_name = None
        self.authenticated_role = None
        self.authenticated_permissions = []
        self.authenticated_user_id = None
        self._has_centered_on_show = False
        self._build_ui()
        self.setStyleSheet(APP_THEME)

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 20, 20, 20)
        main.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("login_card")
        card.setFixedWidth(380)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(14)

        logo = QLabel("M")
        logo.setObjectName("login_logo")
        logo.setFixedSize(52, 52)
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo, alignment=Qt.AlignLeft)

        title = QLabel("WarehouseIQ")
        title.setObjectName("login_title")
        layout.addWidget(title)
        subtitle = QLabel("Sign in to warehouse operations.")
        subtitle.setObjectName("login_subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(12)

        self.username_input = self._add_input(layout, "Username", "Enter username")
        self.password_input = self._add_password(layout)

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setFixedHeight(44)
        self.login_btn.clicked.connect(self.login)
        set_button_kind(self.login_btn, "navy")
        layout.addWidget(self.login_btn)

        links = QHBoxLayout()
        forgot = QPushButton("Forgot Password?")
        forgot.clicked.connect(self._open_forgot_password_dialog)
        set_button_kind(forgot, "link")
        create = QPushButton("Create Account")
        create.clicked.connect(self._open_create_account_dialog)
        set_button_kind(create, "link")
        links.addWidget(forgot)
        links.addStretch()
        links.addWidget(create)
        layout.addLayout(links)
        main.addWidget(card, alignment=Qt.AlignCenter)
        self._center_on_screen()

    def _add_input(self, layout, label_text, placeholder):
        label = QLabel(label_text.upper())
        label.setObjectName("form_label")
        layout.addWidget(label)
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setFixedHeight(40)
        line_edit.returnPressed.connect(self.login)
        layout.addWidget(line_edit)
        return line_edit

    def _add_password(self, layout):
        label = QLabel("PASSWORD")
        label.setObjectName("form_label")
        layout.addWidget(label)
        row = QFrame()
        row.setObjectName("password_row")
        row.setFixedHeight(40)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        line_edit = QLineEdit()
        line_edit.setObjectName("password_inside")
        line_edit.setPlaceholderText("Enter password")
        line_edit.setFixedHeight(36)
        line_edit.setEchoMode(QLineEdit.Password)
        line_edit.returnPressed.connect(self.login)
        row_layout.addWidget(line_edit, 1)
        toggle = QPushButton("Show")
        toggle.setObjectName("password_toggle")
        toggle.setFixedWidth(56)
        toggle.clicked.connect(lambda: self._toggle_password(line_edit, toggle))
        row_layout.addWidget(toggle)
        layout.addWidget(row)
        return line_edit

    def showEvent(self, event):
        super().showEvent(event)
        if not self._has_centered_on_show:
            self._center_on_screen()
            self._has_centered_on_show = True

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            frame_geometry = self.frameGeometry()
            frame_geometry.moveCenter(screen.availableGeometry().center())
            self.move(frame_geometry.topLeft())

    def _toggle_password(self, field, button):
        showing = field.echoMode() == QLineEdit.Password
        field.setEchoMode(QLineEdit.Normal if showing else QLineEdit.Password)
        button.setText("Hide" if showing else "Show")

    def _open_create_account_dialog(self):
        CreateAccountDialog(self).exec_()

    def _open_forgot_password_dialog(self):
        ForgotPasswordDialog(self).exec_()

    def closeEvent(self, event):
        event.accept()
        QApplication.quit()

    def login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            warning_dialog(self, "Input Error", "Please enter both username and password.")
            return
        try:
            user = api_login(username, password)
        except ApiError as exc:
            error_dialog(self, "Login Failed", str(exc))
            self.password_input.clear()
            return
        role = canonical_role(user.get("role"))
        if role not in SUPPORTED_ROLES:
            error_dialog(self, "Login Failed", f"Unsupported account role: {role}")
            return
        self.authenticated_user_id = user.get("id")
        self.authenticated_username = user.get("username") or username
        self.authenticated_display_name = user.get("display_name") or self.authenticated_username
        self.authenticated_role = role
        self.authenticated_permissions = user.get("permissions") or []
        self.login_success.emit()
        self.accept()


__all__ = ["LoginPage", "CreateAccountDialog", "ForgotPasswordDialog"]
