from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
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

from ui.components import error_dialog, info_dialog, warning_dialog
from backend.infrastructure.api_client import (
    ApiError,
    create_customer,
    list_customers,
    update_customer,
    update_customer_balance,
)
from backend.core.helpers import format_currency
from ui.styles import COLORS, configure_table, make_badge, set_button_kind, table_item


class CustomersPage(QWidget):
    def __init__(self, permissions=None):
        super().__init__()
        self.permissions = set(permissions or ())
        self.setObjectName("content_area")
        self.customers = []
        self._load_error_shown = False
        self._build_ui()
        self.load_customers()

    def _can(self, permission):
        return permission in self.permissions

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll)

        content = QWidget()
        content.setObjectName("page_content")
        page = QVBoxLayout(content)
        page.setContentsMargins(20, 20, 20, 20)
        page.setSpacing(14)
        scroll.setWidget(content)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Customers")
        title.setObjectName("page_title")
        sub = QLabel("Customer purchase and balance overview")
        sub.setObjectName("page_subtitle")
        title_block.addWidget(title)
        title_block.addWidget(sub)
        header.addLayout(title_block)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search customers...")
        self.search_input.textChanged.connect(self.load_customers)
        self.search_input.setFixedWidth(260)
        self.search_input.setFixedHeight(36)
        header.addWidget(self.search_input)

        if self._can("customers.manage"):
            add = QPushButton("Add Customer")
            set_button_kind(add, "teal")
            add.clicked.connect(self.open_add_dialog)
            header.addWidget(add)
        page.addLayout(header)

        badges = QHBoxLayout()
        badges.setSpacing(8)
        self.total_badge = make_badge("0 total", "gray")
        self.balance_badge = make_badge("0 with balance", "red")
        badges.addWidget(self.total_badge)
        badges.addWidget(self.balance_badge)
        badges.addStretch()
        page.addLayout(badges)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        card_header = QFrame()
        card_header.setObjectName("card_header")
        card_header_layout = QHBoxLayout(card_header)
        card_header_layout.setContentsMargins(18, 13, 18, 13)
        card_title = QLabel("Customer Accounts")
        card_title.setObjectName("card_title")
        card_header_layout.addWidget(card_title)
        card_header_layout.addStretch()
        card_layout.addWidget(card_header)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "NAME",
            "TYPE",
            "CONTACT",
            "TOTAL PURCHASES",
            "BALANCE",
            "ACTION",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 210)
        configure_table(self.table)
        self.table.setMinimumHeight(470)
        card_layout.addWidget(self.table)
        page.addWidget(card)
        page.addStretch()

    def load_customers(self):
        if not self._can("customers.view"):
            self.customers = []
            self._render_customers()
            return
        search = self.search_input.text().strip()
        try:
            rows = list_customers(search=search or None)
            self._load_error_shown = False
        except ApiError as exc:
            self.customers = []
            if not self._load_error_shown:
                error_dialog(self, "Error", str(exc))
                self._load_error_shown = True
            self._render_customers()
            return

        self.customers = [self._normalize_backend_customer(row) for row in rows]
        self._render_customers()

    def _normalize_backend_customer(self, row):
        name = row.get("full_name") or "Walk-in"
        return {
            "id": row.get("id"),
            "name": name,
            "type": row.get("customer_type") or "Walk-in",
            "contact": row.get("contact_number") or "-",
            "total_purchases": float(row.get("total_purchases") or 0),
            "balance": float(row.get("balance") or 0),
        }

    def _render_customers(self):
        total = len(self.customers)
        with_balance = sum(1 for row in self.customers if float(row.get("balance") or 0) > 0)
        self.total_badge.setText(f"{total} total")
        self.balance_badge.setText(f"{with_balance} with balance")

        self.table.setRowCount(total)
        for row_index, row in enumerate(self.customers):
            balance = float(row.get("balance") or 0)
            values = [
                row["name"],
                row.get("contact") or "-",
                format_currency(row.get("total_purchases") or 0),
                format_currency(balance),
            ]
            if balance > 0:
                background = QColor(COLORS["paper_warning"])
            else:
                background = None

            self.table.setItem(row_index, 0, self._item(values[0], background=background))
            self.table.setCellWidget(row_index, 1, make_badge(row.get("type") or "Walk-in", self._type_tone(row.get("type"))))
            self.table.setItem(row_index, 2, self._item(values[1], background=background))
            self.table.setItem(row_index, 3, self._item(values[2], mono=True, bold=True, background=background))
            self.table.setItem(
                row_index,
                4,
                self._item(
                    values[3],
                    mono=True,
                    bold=balance > 0,
                    color=COLORS["red"] if balance > 0 else COLORS["green"],
                    background=background,
                ),
            )
            self.table.setCellWidget(row_index, 5, self._action_buttons(row))
            self.table.setRowHeight(row_index, 46)

    @staticmethod
    def _item(text, mono=False, bold=False, color=None, background=None):
        item = table_item(text, mono=mono, bold=bold, color=color)
        if background:
            item.setBackground(background)
        return item

    @staticmethod
    def _type_tone(customer_type):
        return {
            "Wholesale": "blue",
            "Reseller": "teal",
            "Walk-in": "gray",
        }.get(customer_type or "Walk-in", "gray")

    def _action_buttons(self, row):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        if self._can("customers.view"):
            view = QPushButton("View")
            view.setFixedSize(54, 28)
            set_button_kind(view, "outline")
            view.clicked.connect(lambda checked=False, data=row: self.view_customer(data))
            layout.addWidget(view)

        if self._can("customers.manage"):
            pay = QPushButton("Pay")
            pay.setFixedSize(54, 28)
            set_button_kind(pay, "teal")
            pay.setEnabled(float(row.get("balance") or 0) > 0)
            pay.clicked.connect(lambda checked=False, data=row: self.pay_customer(data))
            layout.addWidget(pay)

            edit = QPushButton("Edit")
            edit.setFixedSize(54, 28)
            set_button_kind(edit, "outline")
            edit.clicked.connect(lambda checked=False, data=row: self.edit_customer(data))
            layout.addWidget(edit)

        if layout.count() == 0:
            layout.addWidget(QLabel("-"))
        return widget

    def view_customer(self, row):
        info_dialog(
            self,
            "Customer",
            f"{row['name']}\nType: {row.get('type')}\nPurchases: {format_currency(row.get('total_purchases') or 0)}\nBalance: {format_currency(row.get('balance') or 0)}",
        )

    def pay_customer(self, row):
        dialog = CustomerPaymentDialog(self, row)
        if dialog.exec_():
            self.load_customers()

    def edit_customer(self, row):
        dialog = AddCustomerDialog(self, row)
        if dialog.exec_():
            self.load_customers()

    def open_add_dialog(self):
        dialog = AddCustomerDialog(self)
        if dialog.exec_():
            self.load_customers()


class CustomerPaymentDialog(QDialog):
    def __init__(self, parent, customer):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Record Payment")
        self.setMinimumWidth(360)
        self._build_ui()

    def _build_ui(self):
        balance = float(self.customer.get("balance") or 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(self.customer.get("name") or "Customer")
        title.setObjectName("login_title")
        layout.addWidget(title)

        balance_lbl = QLabel(f"Current Balance: {format_currency(balance)}")
        balance_lbl.setStyleSheet(f"color:{COLORS['red']}; font-size:14px; font-weight:700;")
        layout.addWidget(balance_lbl)

        form = QVBoxLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setFixedHeight(36)
        self.amount_input.setRange(0.01, max(balance, 0.01))
        self.amount_input.setValue(max(balance, 0.01))
        self.amount_input.setPrefix("PHP ")
        form.addWidget(self._form_label("Payment Amount *"))
        form.addWidget(self.amount_input)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        cancel = QPushButton("Cancel")
        set_button_kind(cancel, "outline")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Record Payment")
        set_button_kind(save, "teal")
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def _save(self):
        amount = self.amount_input.value()
        try:
            update_customer_balance(self.customer["id"], amount)
            info_dialog(self, "Recorded", f"Payment of {format_currency(amount)} recorded.")
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))

    @staticmethod
    def _form_label(text):
        label = QLabel(text.upper())
        label.setObjectName("form_label")
        return label


class AddCustomerDialog(QDialog):
    def __init__(self, parent, existing=None):
        super().__init__(parent)
        self.existing = existing or {}
        self.setWindowTitle("Edit Customer" if existing else "Add Customer")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Edit Customer" if self.existing else "Add Customer")
        title.setObjectName("login_title")
        layout.addWidget(title)

        form = QVBoxLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(36)
        self.name_input.setText(self.existing.get("name", ""))
        self.contact_input = QLineEdit()
        self.contact_input.setFixedHeight(36)
        self.contact_input.setText(self.existing.get("contact", "") if self.existing.get("contact") != "-" else "")
        self.type_combo = QComboBox()
        self.type_combo.setFixedHeight(36)
        self.type_combo.addItems(["Walk-in", "Reseller", "Wholesale"])
        self.type_combo.setCurrentText(self.existing.get("type", "Walk-in"))

        form.addWidget(self._form_label("Full Name *"))
        form.addWidget(self.name_input)
        form.addWidget(self._form_label("Contact"))
        form.addWidget(self.contact_input)
        form.addWidget(self._form_label("Customer Type"))
        form.addWidget(self.type_combo)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        cancel = QPushButton("Cancel")
        set_button_kind(cancel, "outline")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save Customer")
        set_button_kind(save, "teal")
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            warning_dialog(self, "Validation", "Full Name is required.")
            return
        payload = {
            "full_name": name,
            "contact_number": self.contact_input.text().strip(),
            "customer_type": self.type_combo.currentText(),
        }
        try:
            if self.existing.get("id"):
                update_customer(self.existing["id"], payload)
            else:
                create_customer(payload)
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))

    @staticmethod
    def _form_label(text):
        label = QLabel(text.upper())
        label.setObjectName("form_label")
        return label
