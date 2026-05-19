from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components import error_dialog, info_dialog, warning_dialog
from backend.infrastructure.api_client import (
    ApiError,
    create_order,
    get_order,
    list_inventory,
    list_invoices,
    list_orders,
    list_payments,
    update_order_status,
)
from backend.core.helpers import format_currency, format_date, generate_order_number
from ui.styles import (
    COLORS,
    backend_order_status,
    configure_table,
    display_order_status,
    make_badge,
    set_button_kind,
    table_item,
    tone_for_status,
)


class OrdersPage(QWidget):
    def __init__(self, permissions=None):
        super().__init__()
        self.permissions = set(permissions or ())
        self.setObjectName("content_area")
        self._build_ui()
        self.load_orders()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_orders)
        self.timer.start(10000)

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
        title = QLabel("All Orders")
        title.setObjectName("page_title")
        sub = QLabel("Track every transaction from creation to release")
        sub.setObjectName("page_subtitle")
        title_block.addWidget(title)
        title_block.addWidget(sub)
        header.addLayout(title_block)
        header.addStretch()

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Status", "Pending", "Preparing", "Ready", "Completed"])
        self.status_filter.currentIndexChanged.connect(self.load_orders)
        header.addWidget(self.status_filter)

        btn_refresh = QPushButton("Refresh")
        set_button_kind(btn_refresh, "outline")
        btn_refresh.clicked.connect(self.load_orders)
        header.addWidget(btn_refresh)

        if self._can("orders.create"):
            btn_new = QPushButton("New Order")
            set_button_kind(btn_new, "teal")
            btn_new.clicked.connect(self.open_new_order)
            header.addWidget(btn_new)
        page.addLayout(header)

        notice = QFrame()
        notice.setObjectName("alert_amber")
        notice_layout = QHBoxLayout(notice)
        notice_layout.setContentsMargins(14, 11, 14, 11)
        msg = QLabel("Orders marked Preparing are visible to warehouse staff through the Orders screen.")
        msg.setObjectName("alert_text_amber")
        msg.setWordWrap(True)
        notice_layout.addWidget(msg)
        page.addWidget(notice)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        card_header = QFrame()
        card_header.setObjectName("card_header")
        card_header_layout = QHBoxLayout(card_header)
        card_header_layout.setContentsMargins(18, 13, 18, 13)
        card_title = QLabel("Order Queue")
        card_title.setObjectName("card_title")
        card_header_layout.addWidget(card_title)
        card_header_layout.addStretch()
        card_layout.addWidget(card_header)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "INVOICE #",
            "TIME",
            "CUSTOMER",
            "TYPE",
            "ITEMS",
            "TOTAL",
            "PAYMENT",
            "STATUS",
            "ACTION",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self.table.setColumnWidth(8, 160)
        configure_table(self.table)
        self.table.setMinimumHeight(460)
        card_layout.addWidget(self.table)
        page.addWidget(card)
        page.addStretch()

    def load_orders(self):
        if not self._can("orders.view"):
            self.table.setRowCount(0)
            return
        display_filter = self.status_filter.currentText()
        status = backend_order_status(display_filter)

        try:
            rows = list_orders(status=status)
        except ApiError:
            return
        try:
            invoices = list_invoices() if self._can("invoices.view") else []
        except ApiError:
            invoices = []
        try:
            payments = list_payments() if self._can("payments.view") else []
        except ApiError:
            payments = []

        invoice_by_order = {
            row.get("order_number"): row
            for row in invoices
            if row.get("order_number")
        }
        payment_by_order = {
            row.get("order_number"): row
            for row in payments
            if row.get("order_number")
        }

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            order_id = row["id"]
            order_number = row.get("order_number") or "-"
            invoice = invoice_by_order.get(order_number)
            payment = payment_by_order.get(order_number)
            display_status = display_order_status(row.get("status"))
            customer = row.get("customer_name") or "Walk-in"
            customer_type = "Walk-in" if customer.strip().lower() == "walk-in" else "Wholesale"
            invoice_number = invoice.get("invoice_number") if invoice else order_number
            payment_status = self._payment_status(invoice, payment)
            item_count = row.get("item_count", 0)

            values = [
                invoice_number,
                format_date(str(row.get("created_at"))),
                customer,
                customer_type,
                str(item_count),
                format_currency(row.get("total_amount") or 0),
            ]
            for col, value in enumerate(values):
                mono = col in {0, 4, 5}
                bold = col in {0, 4, 5}
                color = COLORS["navy"] if col == 0 else None
                self.table.setItem(row_index, col, table_item(value, mono=mono, bold=bold, color=color))

            self.table.setCellWidget(row_index, 6, make_badge(payment_status, tone_for_status(payment_status)))
            self.table.setCellWidget(row_index, 7, make_badge(display_status, tone_for_status(display_status)))
            self.table.setCellWidget(row_index, 8, self._make_action_buttons(order_id, row.get("status")))
            self.table.setRowHeight(row_index, 46)

    @staticmethod
    def _payment_status(invoice, payment):
        if payment:
            return payment.get("payment_status") or "Unpaid"
        if invoice:
            total = float(invoice.get("total_amount") or 0)
            paid = float(invoice.get("amount_paid") or 0)
            if paid >= total and total > 0:
                return "Paid"
            if paid > 0:
                return "Partial"
        return "Unpaid"

    def _make_action_buttons(self, order_id, status):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        if self._can("orders.view"):
            btn_view = QPushButton("View")
            btn_view.setFixedSize(58, 28)
            set_button_kind(btn_view, "outline")
            btn_view.clicked.connect(lambda checked=False, oid=order_id: self.view_order(oid))
            layout.addWidget(btn_view)

        if self._can("orders.update"):
            btn_dispatch = QPushButton("Dispatch")
            btn_dispatch.setFixedSize(82, 28)
            set_button_kind(btn_dispatch, "teal")
            btn_dispatch.setEnabled(status != "Completed")
            btn_dispatch.clicked.connect(lambda checked=False, oid=order_id, current=status: self.dispatch_order(oid, current))
            layout.addWidget(btn_dispatch)

        if layout.count() == 0:
            layout.addWidget(QLabel("-"))
        return widget

    def dispatch_order(self, order_id, current_status):
        next_status = {
            "Pending": "Processing",
            "Processing": "Ready",
            "Ready": "Completed",
        }.get(current_status)
        if not next_status:
            return
        try:
            update_order_status(order_id, next_status)
            self.load_orders()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))

    def open_new_order(self):
        dialog = NewOrderDialog(self)
        if dialog.exec_():
            self.load_orders()

    def view_order(self, order_id):
        dialog = OrderDetailDialog(self, order_id)
        dialog.exec_()

    def update_status(self, order_id):
        dialog = UpdateStatusDialog(self, order_id)
        if dialog.exec_():
            self.load_orders()


class NewOrderDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Create New Order")
        self.setMinimumWidth(560)
        self.setMinimumHeight(520)
        self.order_items = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("New Order")
        title.setObjectName("login_title")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("Customer name (optional)")
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(70)
        self.notes_input.setPlaceholderText("Special instructions...")
        form.addRow("Customer Name:", self.customer_input)
        form.addRow("Notes:", self.notes_input)
        layout.addLayout(form)

        section = QLabel("ORDER ITEMS")
        section.setObjectName("section_label")
        layout.addWidget(section)

        add_row = QHBoxLayout()
        try:
            self.inventory_data = list_inventory()
        except ApiError as exc:
            self.inventory_data = []
            error_dialog(self, "Error", str(exc))

        self.item_combo = QComboBox()
        for row in self.inventory_data:
            self.item_combo.addItem(f"{row['item_name']}  [Stock: {row['quantity']}]", row["id"])

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 999)
        self.qty_spin.setFixedWidth(80)

        btn_add_item = QPushButton("Add to Order")
        set_button_kind(btn_add_item, "teal")
        btn_add_item.clicked.connect(self._add_item)

        add_row.addWidget(self.item_combo, 2)
        add_row.addWidget(QLabel("Qty:"))
        add_row.addWidget(self.qty_spin)
        add_row.addWidget(btn_add_item)
        layout.addLayout(add_row)

        self.items_table = QTableWidget(0, 4)
        self.items_table.setHorizontalHeaderLabels(["ITEM", "QTY", "UNIT PRICE", "SUBTOTAL"])
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        configure_table(self.items_table)
        self.items_table.setMaximumHeight(170)
        layout.addWidget(self.items_table)

        self.total_label = QLabel("Total: " + format_currency(0))
        self.total_label.setObjectName("stat_value")
        self.total_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.total_label)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        set_button_kind(btn_cancel, "outline")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Create Order")
        set_button_kind(btn_save, "teal")
        btn_save.clicked.connect(self._save_order)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _add_item(self):
        item_id = self.item_combo.currentData()
        qty = self.qty_spin.value()
        inv_row = next((row for row in self.inventory_data if row["id"] == item_id), None)
        if not inv_row:
            return

        if qty > inv_row["quantity"]:
            warning_dialog(
                self,
                "Insufficient Stock",
                f"Only {inv_row['quantity']} units available for '{inv_row['item_name']}'.",
            )
            return

        for existing in self.order_items:
            if existing["id"] == item_id:
                warning_dialog(self, "Duplicate", "Item already added.")
                return

        subtotal = qty * inv_row["unit_price"]
        self.order_items.append({
            "id": item_id,
            "name": inv_row["item_name"],
            "qty": qty,
            "price": inv_row["unit_price"],
            "subtotal": subtotal,
        })
        self._refresh_items_table()

    def _refresh_items_table(self):
        self.items_table.setRowCount(len(self.order_items))
        total = 0
        for row_index, item in enumerate(self.order_items):
            values = [
                item["name"],
                str(item["qty"]),
                format_currency(item["price"]),
                format_currency(item["subtotal"]),
            ]
            for col, value in enumerate(values):
                self.items_table.setItem(
                    row_index,
                    col,
                    table_item(value, mono=col > 0, bold=col > 0),
                )
            self.items_table.setRowHeight(row_index, 38)
            total += item["subtotal"]
        self.total_label.setText("Total: " + format_currency(total))

    def _save_order(self):
        if not self.order_items:
            warning_dialog(self, "Empty Order", "Please add at least one item.")
            return

        order_num = generate_order_number()
        payload = {
            "order_number": order_num,
            "customer_name": self.customer_input.text().strip() or "Walk-in",
            "notes": self.notes_input.toPlainText().strip() or None,
            "items": [
                {"item_id": item["id"], "quantity": item["qty"]}
                for item in self.order_items
            ],
        }
        try:
            create_order(payload)
            info_dialog(
                self,
                "Order Created",
                f"Order {order_num} created and sent to warehouse queue.",
            )
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))


class UpdateStatusDialog(QDialog):
    def __init__(self, parent, order_id):
        super().__init__(parent)
        self.order_id = order_id
        self.setWindowTitle("Update Order Status")
        self.setMinimumWidth(340)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        try:
            row = get_order(self.order_id)["order"]
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
            self.reject()
            return

        layout.addWidget(QLabel(f"Order: {row['order_number']}"))
        layout.addWidget(QLabel(f"Current Status: {display_order_status(row['status'])}"))

        form = QFormLayout()
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Pending", "Preparing", "Ready", "Completed", "Cancelled"])
        self.status_combo.setCurrentText(display_order_status(row["status"]))
        form.addRow("New Status:", self.status_combo)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        set_button_kind(btn_cancel, "outline")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Update")
        set_button_kind(btn_save, "teal")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _save(self):
        try:
            update_order_status(self.order_id, backend_order_status(self.status_combo.currentText()))
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))


class OrderDetailDialog(QDialog):
    def __init__(self, parent, order_id):
        super().__init__(parent)
        self.setWindowTitle("Order Details")
        self.setMinimumWidth(520)
        self._build_ui(order_id)

    def _build_ui(self, order_id):
        try:
            payload = get_order(order_id)
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
            self.reject()
            return

        order = payload["order"]
        items = payload["items"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel(f"Order {order['order_number']}")
        title.setObjectName("login_title")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Customer: {order['customer_name'] or 'Walk-in'}"))
        layout.addWidget(QLabel(f"Status: {display_order_status(order['status'])}"))
        layout.addWidget(QLabel(f"Total: {format_currency(order['total_amount'])}"))

        section = QLabel("PICKING LIST")
        section.setObjectName("section_label")
        layout.addWidget(section)

        table = QTableWidget(len(items), 4)
        table.setHorizontalHeaderLabels(["ITEM NAME", "FLOOR", "QTY", "SUBTOTAL"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        configure_table(table)
        for row_index, row in enumerate(items):
            values = [
                row["item_name"],
                f"F{row['floor']}",
                str(row["quantity"]),
                format_currency(row["subtotal"]),
            ]
            for col, value in enumerate(values):
                table.setItem(row_index, col, table_item(value, mono=col > 0, bold=col > 0))
            table.setRowHeight(row_index, 38)
        layout.addWidget(table)

        btn_close = QPushButton("Close")
        set_button_kind(btn_close, "outline")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)
