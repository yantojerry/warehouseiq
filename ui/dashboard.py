from datetime import date, datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from backend.infrastructure.api_client import ApiError, get_dashboard_overview
from backend.core.helpers import format_currency, format_date
from ui.styles import (
    COLORS,
    configure_table,
    display_order_status,
    make_badge,
    table_item,
    tone_for_status,
)


class DashboardPage(QWidget):
    def __init__(self, username="User", permissions=None, navigate_callback=None):
        super().__init__()
        self.username = username or "User"
        self.permissions = set(permissions or ())
        self.navigate_callback = navigate_callback
        self.setObjectName("content_area")
        self._build_ui()
        self.refresh()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(15000)

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
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(14)
        scroll.setWidget(content)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(3)
        self.title = QLabel(f"{self._greeting()}, {self.username}")
        self.title.setObjectName("page_title")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("page_subtitle")
        title_block.addWidget(self.title)
        title_block.addWidget(self.subtitle)
        header.addLayout(title_block)
        header.addStretch()
        self.live_label = QLabel("Live")
        self.live_label.setObjectName("live_dot")
        header.addWidget(self.live_label, alignment=Qt.AlignTop)
        self.layout.addLayout(header)

        self.alerts_layout = QVBoxLayout()
        self.alerts_layout.setContentsMargins(0, 0, 0, 0)
        self.alerts_layout.setSpacing(8)
        self.layout.addLayout(self.alerts_layout)

        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(14)
        self.layout.addLayout(self.stats_grid)

        grid_one = QHBoxLayout()
        grid_one.setSpacing(14)
        self.transactions_card, self.transactions_table = self._make_table_card(
            "Recent Transactions",
            ["INVOICE #", "CUSTOMER", "TOTAL", "STATUS"],
        )
        grid_one.addWidget(self.transactions_card, 1)
        self.orders_card = self._make_progress_card("Pending Tasks")
        grid_one.addWidget(self.orders_card, 1)
        self.layout.addLayout(grid_one)

        grid_two = QHBoxLayout()
        grid_two.setSpacing(14)
        self.restock_card, self.restock_table = self._make_table_card(
            "Products Needing Restock",
            ["ITEM", "FLOOR", "STOCK", "MIN."],
        )
        grid_two.addWidget(self.restock_card, 1)
        self.top_card, self.top_table = self._make_table_card(
            "Top Selling Products",
            ["PRODUCT", "QTY SOLD", "SALES"],
        )
        grid_two.addWidget(self.top_card, 1)
        self.layout.addLayout(grid_two)

        grid_three = QHBoxLayout()
        grid_three.setSpacing(14)
        self.stock_updates_card, self.stock_updates_table = self._make_table_card(
            "Recent Stock Updates",
            ["ITEM", "FLOOR", "STOCK", "UPDATED"],
        )
        grid_three.addWidget(self.stock_updates_card, 1)
        self.orders_table_card, self.orders_table = self._make_table_card(
            "Recent Orders",
            ["ORDER #", "CUSTOMER", "TOTAL", "STATUS"],
        )
        grid_three.addWidget(self.orders_table_card, 1)
        self.layout.addLayout(grid_three)
        self.layout.addStretch()

    def _make_table_card(self, title, headers):
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("card_header")
        header.setMinimumHeight(46)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 13, 18, 13)
        title_label = QLabel(title)
        title_label.setObjectName("card_title")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        outer.addWidget(header)

        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        configure_table(table)
        table.setMinimumHeight(235)
        outer.addWidget(table)
        return card, table

    def _make_progress_card(self, title):
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("card_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 13, 18, 13)
        label = QLabel(title)
        label.setObjectName("card_title")
        header_layout.addWidget(label)
        header_layout.addStretch()
        outer.addWidget(header)

        body = QFrame()
        body.setObjectName("card_body")
        self.progress_layout = QVBoxLayout(body)
        self.progress_layout.setContentsMargins(18, 18, 18, 18)
        self.progress_layout.setSpacing(14)
        outer.addWidget(body)
        return card

    def refresh(self):
        self.subtitle.setText(date.today().strftime("%B %d, %Y") + "  |  Live")

        try:
            overview = get_dashboard_overview()
        except ApiError:
            return

        self.permissions = set(overview.get("permissions") or self.permissions)
        stats = overview.get("stats") or {}
        widgets = overview.get("widgets") or {}
        self._load_alerts(stats, widgets)
        self._load_stats(stats, widgets)
        self._load_transactions(overview.get("recent_transactions") or [])
        self._load_progress(overview.get("recent_orders") or [])
        self._load_restock(overview.get("products_needing_restock") or [])
        self._load_top_products(overview.get("top_selling_products") or [])
        self._load_stock_updates(overview.get("recent_stock_updates") or [])
        self._load_recent_orders(overview.get("recent_orders") or [])

        self.transactions_card.setVisible(bool(widgets.get("sales")))
        self.top_card.setVisible(bool(widgets.get("sales")))
        self.restock_card.setVisible(bool(widgets.get("inventory")))
        self.stock_updates_card.setVisible(bool(widgets.get("inventory")))
        self.orders_card.setVisible(bool(widgets.get("orders") or widgets.get("inventory") or widgets.get("finance")))
        self.orders_table_card.setVisible(bool(widgets.get("orders")))

    def _load_alerts(self, stats, widgets):
        self._clear_layout(self.alerts_layout)
        low_stock = int(stats.get("low_stock_items") or 0)
        out_of_stock = int(stats.get("out_of_stock_items") or 0)
        pending_orders = int(stats.get("pending_orders") or 0)
        partial_payments = int(stats.get("partial_payments") or 0)
        if widgets.get("inventory") and (low_stock or out_of_stock):
            self.alerts_layout.addWidget(
                self._make_alert("red", f"{low_stock} low stock and {out_of_stock} out of stock item(s) need attention.", "inventory")
            )
        if widgets.get("orders") and pending_orders:
            self.alerts_layout.addWidget(
                self._make_alert(
                    "amber",
                    f"{pending_orders} order(s) are waiting for action.",
                    self._first_allowed(("orders", "orders.view"), ("dispatch", "dispatch.view")),
                )
            )
        if widgets.get("finance") and partial_payments:
            self.alerts_layout.addWidget(
                self._make_alert("teal", f"{partial_payments} partial payment(s) still have balances.", "payments")
            )

    def _make_alert(self, tone, message, target=None):
        frame = QFrame()
        frame.setObjectName(f"alert_{tone}")
        if target and self.navigate_callback:
            frame.setCursor(Qt.PointingHandCursor)
            frame.mousePressEvent = lambda event, key=target: self.navigate_callback(key)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 11, 14, 11)
        label = QLabel(message)
        label.setObjectName(f"alert_text_{tone}")
        label.setWordWrap(True)
        layout.addWidget(label)
        return frame

    def _load_stats(self, stats, widgets):
        self._clear_layout(self.stats_grid)
        cards = []
        if widgets.get("inventory"):
            cards.extend([
                ("Total Products", stats.get("total_products") or 0, "navy", self._first_allowed(("products", "products.view"), ("inventory", "inventory.view"))),
                ("Total Stock Qty", stats.get("total_stock_quantity") or 0, "teal", self._first_allowed(("inventory", "inventory.view"), ("products", "products.view"))),
                ("Stock Value", format_currency(stats.get("total_stock_value") or 0), "teal", self._first_allowed(("inventory", "inventory.view"), ("products", "products.view"))),
                ("Low Stock Items", stats.get("low_stock_items") or 0, "amber", self._first_allowed(("inventory", "inventory.view"), ("products", "products.view"))),
                ("Out of Stock", stats.get("out_of_stock_items") or 0, "red", self._first_allowed(("inventory", "inventory.view"), ("products", "products.view"))),
            ])
        if widgets.get("sales"):
            cards.extend([
                ("Total Sales", format_currency(stats.get("total_sales") or 0), "navy", self._first_allowed(("reports", "reports.view"), ("invoices", "invoices.view"), ("pos", "pos.create_sale"))),
                ("Sales Today", format_currency(stats.get("sales_today") or 0), "teal", self._first_allowed(("invoices", "invoices.view"), ("pos", "pos.create_sale"))),
            ])
        if widgets.get("orders"):
            cards.append(("Pending Tasks", stats.get("pending_tasks") or 0, "amber", self._first_allowed(("dispatch", "dispatch.view"), ("orders", "orders.view"))))
        if widgets.get("finance"):
            cards.append(("Outstanding Balances", format_currency(stats.get("outstanding_balance") or 0), "red", self._first_allowed(("payments", "payments.view"), ("balance", "balance.view"))))
        if widgets.get("users"):
            cards.append(("Total Users", stats.get("total_users") or 0, "gray", "users"))

        if not cards:
            cards.append(("Settings Available", "Yes", "teal", "settings"))

        for index, (label, value, tone, target) in enumerate(cards):
            self.stats_grid.addWidget(self._make_stat_card(label, value, tone, target), index // 4, index % 4)

    def _make_stat_card(self, label, value, tone, target=None):
        card = QFrame()
        card.setObjectName(f"stat_card_{tone}")
        if target and self.navigate_callback:
            card.setCursor(Qt.PointingHandCursor)
            card.mousePressEvent = lambda event, key=target: self.navigate_callback(key)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)
        value_label = QLabel(str(value))
        value_label.setObjectName("stat_value")
        label_widget = QLabel(label)
        label_widget.setObjectName("stat_label")
        layout.addWidget(value_label)
        layout.addWidget(label_widget)
        return card

    def _first_allowed(self, *options):
        for module_key, permission_key in options:
            if permission_key in self.permissions:
                return module_key
        return None

    def _load_transactions(self, rows):
        self.transactions_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            total = float(row.get("total_amount") or 0)
            paid = float(row.get("amount_paid") or 0)
            if paid >= total and total > 0:
                status = "Paid"
            elif paid > 0:
                status = "Partial"
            else:
                status = row.get("status") or "Unpaid"

            values = [
                row.get("invoice_number") or "-",
                row.get("customer_name") or "Walk-in",
                format_currency(total),
            ]
            for col, value in enumerate(values):
                mono = col in {0, 2}
                color = COLORS["navy"] if col == 0 else None
                self.transactions_table.setItem(row_index, col, table_item(value, mono=mono, bold=mono, color=color))
            self.transactions_table.setCellWidget(row_index, 3, make_badge(status, tone_for_status(status)))
            self.transactions_table.setRowHeight(row_index, 38)

    def _load_progress(self, orders):
        self._clear_layout(self.progress_layout)
        active_orders = [row for row in orders if row.get("status") not in {"Completed", "Cancelled"}][:4]
        if not active_orders:
            empty = QLabel("No pending tasks.")
            empty.setObjectName("stat_label")
            self.progress_layout.addWidget(empty)
            self.progress_layout.addStretch()
            return

        for order in active_orders:
            self.progress_layout.addWidget(self._make_progress_item(order))
        self.progress_layout.addStretch()

    def _make_progress_item(self, order):
        frame = QFrame()
        frame.setObjectName("card_body")
        frame.setContentsMargins(12, 10, 12, 10)
        target = self._first_allowed(("orders", "orders.view"), ("dispatch", "dispatch.view"))
        if target and self.navigate_callback:
            frame.setCursor(Qt.PointingHandCursor)
            frame.mousePressEvent = lambda event, key=target: self.navigate_callback(key)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top = QHBoxLayout()
        number = QLabel(order.get("order_number") or "-")
        number.setStyleSheet(
            f"background: transparent; color: {COLORS['navy']}; font-family: Courier New; "
            "font-size: 13px; font-weight: 700;"
        )
        customer = QLabel(order.get("customer_name") or "Walk-in")
        customer.setStyleSheet(f"background: transparent; color: {COLORS['text_2']}; font-weight: 600;")
        top.addWidget(number)
        top.addWidget(customer, 1)
        display_status = display_order_status(order.get("status"))
        top.addWidget(make_badge(display_status, tone_for_status(display_status)))
        layout.addLayout(top)
        layout.addLayout(self._make_steps(display_status))
        return frame

    def _make_steps(self, status):
        row = QHBoxLayout()
        row.setSpacing(6)
        steps = ["Pending", "Preparing", "Ready", "Completed"]
        try:
            current = steps.index(status)
        except ValueError:
            current = 0

        for index, step in enumerate(steps):
            if index < current:
                tone = "teal"
            elif index == current:
                tone = "navy"
            else:
                tone = "gray"
            row.addWidget(make_badge(step, tone))
        row.addStretch()
        return row

    def _load_restock(self, rows):
        self.restock_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("item_name") or row.get("item_code") or "-",
                f"F{row.get('floor') or '-'}",
                str(row.get("quantity") or 0),
                str(row.get("low_stock_threshold") or 0),
            ]
            for col, value in enumerate(values):
                self.restock_table.setItem(row_index, col, table_item(value, mono=col > 0, bold=col in {0, 2}))
            self.restock_table.setRowHeight(row_index, 38)

    def _load_top_products(self, rows):
        self.top_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("item_name") or "-",
                str(row.get("quantity_sold") or 0),
                format_currency(row.get("gross_sales") or 0),
            ]
            for col, value in enumerate(values):
                self.top_table.setItem(row_index, col, table_item(value, mono=col > 0, bold=col > 0))
            self.top_table.setRowHeight(row_index, 38)

    def _load_stock_updates(self, rows):
        self.stock_updates_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("item_name") or row.get("item_code") or "-",
                f"F{row.get('floor') or '-'}",
                str(row.get("quantity") or 0),
                format_date(row.get("updated_at")),
            ]
            for col, value in enumerate(values):
                self.stock_updates_table.setItem(row_index, col, table_item(value, mono=col in {1, 2, 3}, bold=col in {0, 2}))
            self.stock_updates_table.setRowHeight(row_index, 38)

    def _load_recent_orders(self, rows):
        self.orders_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            display_status = display_order_status(row.get("status"))
            values = [
                row.get("order_number") or "-",
                row.get("customer_name") or "Walk-in",
                format_currency(row.get("total_amount") or 0),
            ]
            for col, value in enumerate(values):
                self.orders_table.setItem(row_index, col, table_item(value, mono=col in {0, 2}, bold=col in {0, 2}))
            self.orders_table.setCellWidget(row_index, 3, make_badge(display_status, tone_for_status(display_status)))
            self.orders_table.setRowHeight(row_index, 38)

    @staticmethod
    def _greeting():
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning"
        if hour < 18:
            return "Good afternoon"
        return "Good evening"

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                DashboardPage._clear_layout(child_layout)