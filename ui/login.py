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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components import error_dialog, info_dialog, warning_dialog
from backend.infrastructure.api_client import ApiError, list_inventory, register, login as api_login
from ui.styles import APP_THEME, canonical_role, set_button_kind
from ui.theme import COLORS


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
        self.low_stock_count = 0
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

    def _show_low_stock_alert(self):
        try:
            items = list_inventory() or []
            low_items = [
                item for item in items
                if item.get("is_active", 1)
                and item.get("quantity", 0) <= item.get("low_stock_threshold", 0)
            ]
            self.low_stock_count = len(low_items)
            if not low_items:
                return
            dlg = LowStockAlertDialog(low_items, parent=None)
            dlg.exec_()
        except Exception:
            self.low_stock_count = 0

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
        if role == "Warehouseman":
            self._show_low_stock_alert()

class LowStockAlertDialog(QDialog):
    def __init__(self, low_stock_items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Low Stock Alert")
        self.setFixedSize(480, 420)
        self.setAttribute(Qt.WA_StyledBackground)
        self._build_ui(low_stock_items)
        self.setStyleSheet(APP_THEME)

    def _build_ui(self, items):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        warning_icon = QLabel("⚠")
        warning_icon.setStyleSheet("font-size: 22px; color: #E8A020;")
        header_row.addWidget(warning_icon)
        title = QLabel("Low Stock Warning")
        title.setObjectName("login_title")
        title.setStyleSheet("font-size: 17px; font-weight: 600; margin-left: 6px;")
        header_row.addWidget(title)
        header_row.addStretch()
        layout.addLayout(header_row)

        subtitle = QLabel(f"{len(items)} item(s) are low or critical and need restocking.")
        subtitle.setObjectName("login_subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #E0E0E0;")
        layout.addWidget(divider)

        # Items list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        items_widget = QWidget()
        items_widget.setStyleSheet("background: transparent;")
        items_layout = QVBoxLayout(items_widget)
        items_layout.setContentsMargins(0, 4, 0, 4)
        items_layout.setSpacing(6)

        for item in items:
            row = QFrame()
            qty = item.get("quantity", 0)
            threshold = item.get("low_stock_threshold", 0)
            is_critical = qty == 0
            is_low = qty <= threshold

            if is_critical:
                row.setStyleSheet(
                    f"QFrame {{ background: #3b1218; border: 1px solid {COLORS['red']}; "
                    "border-radius: 8px; padding: 2px; }"
                )
            else:
                row.setStyleSheet(
                    f"QFrame {{ background: #3d2a0b; border: 1px solid {COLORS['amber']}; "
                    "border-radius: 8px; padding: 2px; }"
                )

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(8)

            name_col = QVBoxLayout()
            name_col.setSpacing(2)
            name_lbl = QLabel(item.get("item_name", "Unknown"))
            name_lbl.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {COLORS['white']};")
            floor_lbl = QLabel(f"Floor {item.get('floor', '?')}  ·  {item.get('category', '')}")
            floor_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['muted']};")
            name_col.addWidget(name_lbl)
            name_col.addWidget(floor_lbl)
            row_layout.addLayout(name_col, 1)

            status_col = QVBoxLayout()
            status_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            qty_lbl = QLabel(f"{'Out of stock' if is_critical else f'{qty} left'}")
            qty_lbl.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {'#DC2626' if is_critical else '#D97706'};")
            min_lbl = QLabel(f"Min: {threshold}")
            min_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['muted']};")
            qty_lbl.setAlignment(Qt.AlignRight)
            min_lbl.setAlignment(Qt.AlignRight)
            status_col.addWidget(qty_lbl)
            status_col.addWidget(min_lbl)
            row_layout.addLayout(status_col)

            items_layout.addWidget(row)

        scroll.setWidget(items_widget)
        layout.addWidget(scroll, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setFixedHeight(40)
        set_button_kind(dismiss_btn, "ghost")
        dismiss_btn.clicked.connect(self.reject)

        view_btn = QPushButton("View Items →")
        view_btn.setFixedHeight(40)
        set_button_kind(view_btn, "teal")
        view_btn.clicked.connect(self.accept)

        btn_row.addWidget(dismiss_btn)
        btn_row.addWidget(view_btn)
        layout.addLayout(btn_row)

__all__ = ["LoginPage", "CreateAccountDialog", "ForgotPasswordDialog"]
