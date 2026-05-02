from PyQt5.QtCore import Qt
from PyQt5.QtPrintSupport import QPrintDialog, QPrinter
from PyQt5.QtGui import QTextDocument
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components import error_dialog, info_dialog, warning_dialog
from utils.api_client import (
    ApiError,
    create_invoice,
    get_invoice_html,
    get_order,
    list_available_orders,
    list_invoices,
)
from utils.helpers import format_currency, format_date
from utils.styles import (
    COLORS,
    configure_table,
    make_badge,
    set_button_kind,
    table_item,
)


PAYMENT_METHODS = [
    "Cash",
    "GCash",
    "Bank Transfer",
    "Credit Card",
    "Debit Card",
    "Cheque",
    "Other",
]


class InvoicesPage(QWidget):
    def __init__(self, permissions=None):
        super().__init__()
        self.permissions = set(permissions or ())
        self.setObjectName("content_area")
        self._build_ui()
        self.load_invoices()

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
        title = QLabel("Invoice Management")
        title.setObjectName("page_title")
        sub = QLabel("Digital invoices with audit trail")
        sub.setObjectName("page_subtitle")
        title_block.addWidget(title)
        title_block.addWidget(sub)
        header.addLayout(title_block)
        header.addStretch()
        page.addLayout(header)

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
        card_title = QLabel("Invoices")
        card_title.setObjectName("card_title")
        toolbar.addWidget(card_title)
        toolbar.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search customer or invoice...")
        self.search_input.textChanged.connect(self.load_invoices)
        self.search_input.setFixedWidth(280)
        self.search_input.setFixedHeight(36)
        toolbar.addWidget(self.search_input)

        if self._can("invoices.create"):
            btn_new = QPushButton("Create Invoice")
            set_button_kind(btn_new, "teal")
            btn_new.clicked.connect(self.open_create_dialog)
            toolbar.addWidget(btn_new)
        card_layout.addWidget(card_header)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "INVOICE #",
            "CUSTOMER",
            "ORDER #",
            "TOTAL",
            "PAID",
            "PAYMENT",
            "ISSUED AT",
            "ACTION",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 150)
        configure_table(self.table)
        self.table.setMinimumHeight(470)
        card_layout.addWidget(self.table)
        page.addWidget(card)
        page.addStretch()

    def load_invoices(self):
        if not self._can("invoices.view"):
            self.table.setRowCount(0)
            return
        search = self.search_input.text().strip()
        try:
            rows = list_invoices(search=search or None)
        except ApiError:
            return

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            inv_id = row["id"]
            values = [
                row["invoice_number"],
                row["customer_name"],
                row["order_number"] or "-",
                format_currency(row["total_amount"]),
                format_currency(row["amount_paid"]),
                format_date(str(row["issued_at"])),
            ]
            for col, value in enumerate(values):
                table_col = col if col < 5 else col + 1
                mono = table_col in {0, 2, 3, 4}
                bold = table_col in {0, 2, 3, 4}
                color = COLORS["navy"] if table_col == 0 else None
                self.table.setItem(row_index, table_col, table_item(value, mono=mono, bold=bold, color=color))

            payment_method = row.get("payment_method") or "-"
            self.table.setCellWidget(
                row_index,
                5,
                make_badge(payment_method, "teal" if payment_method != "-" else "gray"),
            )
            self.table.setCellWidget(row_index, 7, self._make_action_buttons(inv_id))
            self.table.setRowHeight(row_index, 46)

    def _make_action_buttons(self, inv_id):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        if self._can("invoices.view"):
            btn_view = QPushButton("View")
            btn_view.setFixedSize(58, 28)
            set_button_kind(btn_view, "teal")
            btn_view.clicked.connect(lambda checked=False, iid=inv_id: self.view_invoice(iid))
            layout.addWidget(btn_view)

        if self._can("invoices.print"):
            btn_print = QPushButton("Print")
            btn_print.setFixedSize(68, 28)
            set_button_kind(btn_print, "outline")
            btn_print.clicked.connect(lambda checked=False, iid=inv_id: self.print_invoice(iid))
            layout.addWidget(btn_print)

        if layout.count() == 0:
            layout.addWidget(QLabel("-"))
        return widget

    def open_create_dialog(self):
        dialog = CreateInvoiceDialog(self)
        if dialog.exec_():
            self.load_invoices()

    def view_invoice(self, inv_id):
        dialog = InvoiceViewDialog(self, inv_id, can_print=self._can("invoices.print"))
        dialog.exec_()

    def print_invoice(self, inv_id):
        try:
            html = build_invoice_html(inv_id)
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
            return
        doc = QTextDocument()
        doc.setHtml(html)
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec_() == QPrintDialog.Accepted:
            doc.print_(printer)


class CreateInvoiceDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Create Invoice")
        self.setMinimumWidth(440)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        title = QLabel("New Invoice")
        title.setObjectName("login_title")
        layout.addWidget(title)

        form = QVBoxLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self.customer_input = QLineEdit()
        self.customer_input.setFixedHeight(36)
        self.customer_input.setPlaceholderText("Customer name")

        try:
            self.orders = list_available_orders()
        except ApiError as exc:
            self.orders = []
            error_dialog(self, "Error", str(exc))

        self.order_combo = QComboBox()
        self.order_combo.setFixedHeight(36)
        self.order_combo.addItem("No linked order", None)
        for order in self.orders:
            self.order_combo.addItem(
                f"{order['order_number']} - {format_currency(order['total_amount'])}",
                order["id"],
            )
        self.order_combo.currentIndexChanged.connect(self._auto_fill_total)

        self.total_input = QDoubleSpinBox()
        self.total_input.setFixedHeight(36)
        self.total_input.setRange(0, 9999999)
        self.total_input.setPrefix("PHP ")
        self.paid_input = QDoubleSpinBox()
        self.paid_input.setFixedHeight(36)
        self.paid_input.setRange(0, 9999999)
        self.paid_input.setPrefix("PHP ")
        self.payment_method_combo = QComboBox()
        self.payment_method_combo.setFixedHeight(36)
        self.payment_method_combo.addItem("Select payment method", None)
        for method in PAYMENT_METHODS:
            self.payment_method_combo.addItem(method, method)

        form.addWidget(self._form_label("Customer Name *"))
        form.addWidget(self.customer_input)
        form.addWidget(self._form_label("Linked Order"))
        form.addWidget(self.order_combo)
        form.addWidget(self._form_label("Total Amount *"))
        form.addWidget(self.total_input)
        form.addWidget(self._form_label("Amount Paid"))
        form.addWidget(self.paid_input)
        form.addWidget(self._form_label("Payment Method *"))
        form.addWidget(self.payment_method_combo)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        btn_cancel = QPushButton("Cancel")
        set_button_kind(btn_cancel, "outline")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Create Invoice")
        set_button_kind(btn_save, "teal")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _auto_fill_total(self):
        order_id = self.order_combo.currentData()
        if order_id:
            order = next((row for row in self.orders if row["id"] == order_id), None)
            if order:
                self.total_input.setValue(order["total_amount"])

    def _save(self):
        name = self.customer_input.text().strip()
        total = self.total_input.value()
        payment_method = self.payment_method_combo.currentData()
        if not name or total == 0:
            warning_dialog(self, "Validation", "Customer name and total are required.")
            return
        if not payment_method:
            warning_dialog(self, "Validation", "Please select a payment method.")
            return

        try:
            result = create_invoice({
                "order_id": self.order_combo.currentData(),
                "customer_name": name,
                "total_amount": total,
                "amount_paid": self.paid_input.value(),
                "payment_method": payment_method,
            })
            info_dialog(
                self,
                "Invoice Created",
                f"Invoice {result['invoice_number']} created successfully.",
            )
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))

    @staticmethod
    def _form_label(text):
        label = QLabel(text.upper())
        label.setObjectName("form_label")
        return label


class InvoiceViewDialog(QDialog):
    def __init__(self, parent, inv_id, can_print=True):
        super().__init__(parent)
        self.inv_id = inv_id
        self.can_print = can_print
        self.setWindowTitle("Invoice Preview")
        self.setMinimumWidth(640)
        self.setMinimumHeight(720)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(8)

        try:
            html = build_invoice_html(self.inv_id)
            try:
                from PyQt5.QtWebEngineWidgets import QWebEngineView

                view = QWebEngineView()
                view.setHtml(html)
                layout.addWidget(view)
            except ImportError:
                text = QTextEdit()
                text.setReadOnly(True)
                text.setHtml(html)
                layout.addWidget(text)
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
            self.reject()
            return

        btns = QHBoxLayout()
        btns.addStretch()
        btn_print = QPushButton("Print")
        set_button_kind(btn_print, "teal")
        btn_print.clicked.connect(self._print)
        btn_print.setVisible(self.can_print)
        btn_close = QPushButton("Close")
        set_button_kind(btn_close, "outline")
        btn_close.clicked.connect(self.accept)
        btns.addWidget(btn_print)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

    def _print(self):
        try:
            html = build_invoice_html(self.inv_id)
            doc = QTextDocument()
            doc.setHtml(html)
            printer = QPrinter(QPrinter.HighResolution)
            dlg = QPrintDialog(printer, self)
            if dlg.exec_() == QPrintDialog.Accepted:
                doc.print_(printer)
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))


def build_invoice_html(inv_id):
    return get_invoice_html(inv_id)
