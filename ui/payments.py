from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
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
    create_payment,
    current_user,
    get_payment,
    get_payment_history,
    get_payments_summary,
    list_available_orders,
    list_payments,
    record_payment,
)
from backend.core.helpers import format_currency, format_date
from ui.styles import (
    COLORS,
    configure_table,
    make_badge,
    set_button_kind,
    table_item,
    tone_for_status,
)


class PaymentsPage(QWidget):
    def __init__(self, permissions=None):
        super().__init__()
        self.permissions = set(permissions or ())
        self.setObjectName("content_area")
        self._build_ui()
        self.load_payments()

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
        title = QLabel("Balance Monitoring")
        title.setObjectName("page_title")
        sub = QLabel("Track partial payments and outstanding balances")
        sub.setObjectName("page_subtitle")
        title_block.addWidget(title)
        title_block.addWidget(sub)
        header.addLayout(title_block)
        header.addStretch()
        page.addLayout(header)

        self.summary_row = QHBoxLayout()
        self.summary_row.setSpacing(14)
        page.addLayout(self.summary_row)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        card_header = QFrame()
        card_header.setObjectName("card_header")
        toolbar = QHBoxLayout(card_header)
        toolbar.setContentsMargins(18, 13, 18, 13)
        toolbar.setSpacing(8)

        card_title = QLabel("Outstanding Balances")
        card_title.setObjectName("card_title")
        toolbar.addWidget(card_title)
        toolbar.addStretch()

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Partial", "Paid", "Unpaid"])
        self.filter_combo.currentIndexChanged.connect(self.load_payments)
        toolbar.addWidget(self.filter_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search customer...")
        self.search_input.textChanged.connect(self.load_payments)
        self.search_input.setFixedWidth(240)
        toolbar.addWidget(self.search_input)

        if self._can("payments.manage"):
            btn_add = QPushButton("Add Payment Record")
            set_button_kind(btn_add, "teal")
            btn_add.clicked.connect(self.open_add_payment)
            toolbar.addWidget(btn_add)
        card_layout.addWidget(card_header)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "CUSTOMER",
            "ORDER #",
            "TOTAL",
            "PAID",
            "BALANCE",
            "STATUS",
            "LAST UPDATED",
            "ACTION",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 194)
        configure_table(self.table)
        self.table.setMinimumHeight(450)
        card_layout.addWidget(self.table)
        page.addWidget(card)
        page.addStretch()

    def load_payments(self):
        if not self._can("payments.view"):
            self.table.setRowCount(0)
            return
        search = self.search_input.text().strip()
        status = self.filter_combo.currentText()
        try:
            rows = list_payments(search=search or None, status=status)
            summary = get_payments_summary()
        except ApiError:
            return

        self._update_summary(summary["total_amount"], summary["amount_paid"], summary["partial_count"])

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            pay_id = row["id"]
            balance = float(row["balance"] or 0)
            payment_status = row["payment_status"]
            values = [
                row["customer_name"],
                row["order_number"] or "-",
                format_currency(row["total_amount"]),
                format_currency(row["amount_paid"]),
                format_currency(balance),
                format_date(str(row["updated_at"])),
            ]
            for col, value in enumerate(values):
                table_col = col if col < 5 else col + 1
                mono = table_col in {1, 2, 3, 4}
                bold = table_col in {1, 2, 3, 4}
                color = COLORS["red"] if table_col == 4 and balance > 0 else None
                self.table.setItem(
                    row_index,
                    table_col,
                    table_item(value, mono=mono, bold=bold, color=color),
                )

            self.table.setCellWidget(row_index, 5, make_badge(payment_status, tone_for_status(payment_status)))
            self.table.setCellWidget(row_index, 7, self._make_action_buttons(pay_id, payment_status))
            self.table.setRowHeight(row_index, 50)

    def _update_summary(self, total, paid, partial_count):
        self._clear_layout(self.summary_row)
        outstanding = total - paid
        cards = [
            ("Total Billed", format_currency(total), "navy"),
            ("Total Collected", format_currency(paid), "teal"),
            ("Outstanding Balance", format_currency(outstanding), "red" if outstanding > 0 else "green"),
            ("Partial Accounts", str(partial_count), "amber" if partial_count > 0 else "teal"),
        ]
        for label, value, tone in cards:
            self.summary_row.addWidget(self._make_stat_card(label, value, tone))

    def _make_stat_card(self, label, value, tone):
        card = QFrame()
        card.setObjectName(f"stat_card_{tone}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)
        value_label = QLabel(value)
        value_label.setObjectName("stat_value")
        label_widget = QLabel(label)
        label_widget.setObjectName("stat_label")
        layout.addWidget(value_label)
        layout.addWidget(label_widget)
        return card

    def _make_action_buttons(self, payment_id, payment_status):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        layout.addStretch()

        if self._can("payments.manage"):
            btn_pay = QPushButton("Add")
            btn_pay.setFixedSize(72, 30)
            btn_pay.setCursor(Qt.PointingHandCursor)
            set_button_kind(btn_pay, "teal")
            btn_pay.setEnabled(payment_status != "Paid")
            btn_pay.clicked.connect(lambda checked=False, pid=payment_id: self.add_payment(pid))
            layout.addWidget(btn_pay)

        if self._can("payments.view"):
            btn_hist = QPushButton("History")
            btn_hist.setFixedSize(88, 30)
            btn_hist.setCursor(Qt.PointingHandCursor)
            set_button_kind(btn_hist, "outline")
            btn_hist.clicked.connect(lambda checked=False, pid=payment_id: self.view_history(pid))
            layout.addWidget(btn_hist)

        if layout.count() == 0:
            empty = QLabel("-")
            empty.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty)
        layout.addStretch()
        return widget

    def open_add_payment(self):
        dialog = AddPaymentDialog(self)
        if dialog.exec_():
            self.load_payments()

    def add_payment(self, payment_id):
        dialog = RecordPaymentDialog(self, payment_id)
        if dialog.exec_():
            self.load_payments()

    def view_history(self, payment_id):
        dialog = PaymentHistoryDialog(self, payment_id)
        dialog.exec_()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()


class AddPaymentDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Add Payment Record")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        title = QLabel("New Payment Record")
        title.setObjectName("login_title")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("Customer name")

        try:
            self.orders = list_available_orders()
        except ApiError as exc:
            self.orders = []
            error_dialog(self, "Error", str(exc))

        self.order_combo = QComboBox()
        self.order_combo.addItem("No linked order", None)
        for order in self.orders:
            self.order_combo.addItem(order["order_number"], order["id"])

        self.total_input = QDoubleSpinBox()
        self.total_input.setRange(0, 9999999)
        self.total_input.setPrefix("PHP ")
        self.paid_input = QDoubleSpinBox()
        self.paid_input.setRange(0, 9999999)
        self.paid_input.setPrefix("PHP ")

        form.addRow("Customer Name *:", self.customer_input)
        form.addRow("Linked Order:", self.order_combo)
        form.addRow("Total Amount *:", self.total_input)
        form.addRow("Amount Paid:", self.paid_input)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        set_button_kind(btn_cancel, "outline")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save")
        set_button_kind(btn_save, "teal")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _save(self):
        name = self.customer_input.text().strip()
        total = self.total_input.value()
        paid = self.paid_input.value()
        if not name or total == 0:
            warning_dialog(self, "Validation", "Customer name and total amount are required.")
            return
        if paid > total:
            warning_dialog(self, "Validation", "Amount paid cannot exceed total.")
            return

        try:
            create_payment({
                "order_id": self.order_combo.currentData(),
                "customer_name": name,
                "total_amount": total,
                "amount_paid": paid,
            })
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))


class RecordPaymentDialog(QDialog):
    def __init__(self, parent, payment_id):
        super().__init__(parent)
        self.payment_id = payment_id
        self.setWindowTitle("Record Payment")
        self.setMinimumWidth(360)
        self._build_ui()

    def _build_ui(self):
        try:
            row = get_payment(self.payment_id)
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
            self.reject()
            return

        balance = float(row["balance"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(row["customer_name"])
        title.setObjectName("login_title")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Total: {format_currency(row['total_amount'])}"))
        layout.addWidget(QLabel(f"Already Paid: {format_currency(row['amount_paid'])}"))
        balance_lbl = QLabel(f"Remaining Balance: {format_currency(balance)}")
        balance_lbl.setStyleSheet(f"color:{COLORS['red']}; font-size:14px; font-weight:700;")
        layout.addWidget(balance_lbl)

        form = QFormLayout()
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, max(balance, 0.01))
        self.amount_input.setValue(max(balance, 0.01))
        self.amount_input.setPrefix("PHP ")
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Optional note")
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Cash", "GCash", "Maya", "Bank Transfer"])
        form.addRow("Payment Amount *:", self.amount_input)
        form.addRow("Payment Method *:", self.method_combo)
        form.addRow("Note:", self.note_input)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        set_button_kind(btn_cancel, "outline")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Record Payment")
        set_button_kind(btn_save, "teal")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _save(self):
        amount = self.amount_input.value()
        try:
            record_payment(
                self.payment_id,
                amount,
                self.note_input.text().strip() or None,
                payment_method=self.method_combo.currentText(),
                recorded_by=current_user().get("username"),
            )
            info_dialog(self, "Recorded", f"Payment of {format_currency(amount)} recorded.")
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))


class PaymentHistoryDialog(QDialog):
    def __init__(self, parent, payment_id):
        super().__init__(parent)
        self.setWindowTitle("Payment History")
        self.setMinimumWidth(480)
        self._build_ui(payment_id)

    def _build_ui(self, payment_id):
        try:
            payload = get_payment_history(payment_id)
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
            self.reject()
            return

        info = payload["payment"]
        history = payload["history"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel(info["customer_name"])
        title.setObjectName("login_title")
        layout.addWidget(title)
        layout.addWidget(QLabel(
            f"Total: {format_currency(info['total_amount'])}  |  "
            f"Paid: {format_currency(info['amount_paid'])}  |  "
            f"Balance: {format_currency(info['total_amount'] - info['amount_paid'])}"
        ))

        table = QTableWidget(len(history), 3)
        table.setHorizontalHeaderLabels(["AMOUNT PAID", "NOTE", "DATE"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        configure_table(table)
        for row_index, row in enumerate(history):
            values = [
                format_currency(row["amount_paid"]),
                row["note"] or "-",
                format_date(str(row["paid_at"])),
            ]
            for col, value in enumerate(values):
                table.setItem(row_index, col, table_item(value, mono=col == 0, bold=col == 0))
            table.setRowHeight(row_index, 38)
        layout.addWidget(table)

        btn_close = QPushButton("Close")
        set_button_kind(btn_close, "outline")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)
