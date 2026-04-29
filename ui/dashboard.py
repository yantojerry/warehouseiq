from datetime import date

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from utils.api_client import ApiError, get_dashboard_overview, list_invoices, list_orders
from utils.helpers import format_currency, format_date
from utils.styles import (
    COLORS,
    configure_table,
    display_order_status,
    make_badge,
    table_item,
    tone_for_status,
)


class DashboardPage(QWidget):
    def __init__(self, username="User"):
        super().__init__()
        self.username = username or "User"
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
        header.setSpacing(12)
        title_block = QVBoxLayout()
        title_block.setSpacing(3)
        self.title = QLabel(f"Good morning, {self.username}")
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

        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(14)
        self.layout.addLayout(self.stats_row)

        grid = QHBoxLayout()
        grid.setSpacing(14)
        self.transactions_card = self._make_table_card(
            "Recent Transactions",
            ["INVOICE #", "CUSTOMER", "TOTAL", "STATUS"],
        )
        self.transactions_table = self.transactions_card.findChild(QTableWidget)
        grid.addWidget(self.transactions_card, 1)

        self.progress_card = self._make_progress_card()
        grid.addWidget(self.progress_card, 1)
        self.layout.addLayout(grid)
        self.layout.addStretch()

    def _make_table_card(self, title, headers):
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("card_header")
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
        table.setMinimumHeight(250)
        outer.addWidget(table)
        return card

    def _make_progress_card(self):
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("card_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 13, 18, 13)
        title = QLabel("Orders in Progress")
        title.setObjectName("card_title")
        header_layout.addWidget(title)
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
        today = date.today()
        self.subtitle.setText(today.strftime("%B %d, %Y") + "  |  Live")

        try:
            overview = get_dashboard_overview()
            invoices = list_invoices()
            orders = list_orders()
        except ApiError:
            return

        stats = overview.get("stats", {})
        today_invoices = [row for row in invoices if self._is_today(row.get("issued_at"))]
        today_orders = [row for row in orders if self._is_today(row.get("created_at"))]
        sales_today = sum(float(row.get("total_amount") or 0) for row in today_invoices)

        self._load_alerts(
            low_stock_count=int(stats.get("low_stock") or 0),
            pending_orders=[row for row in orders if row.get("status") == "Pending"],
        )
        self._load_stats(
            sales_today=sales_today,
            orders_today=len(today_orders),
            low_stock=int(stats.get("low_stock") or 0),
            outstanding=float(stats.get("outstanding_balance") or 0),
        )
        self._load_transactions(invoices[:8])
        self._load_progress(orders)

    @staticmethod
    def _is_today(value):
        if value is None:
            return False
        return str(value).startswith(date.today().isoformat())

    def _load_alerts(self, low_stock_count, pending_orders):
        self._clear_layout(self.alerts_layout)
        if low_stock_count:
            self.alerts_layout.addWidget(
                self._make_alert(
                    "red",
                    f"{low_stock_count} low stock item(s) need attention.",
                )
            )
        if pending_orders:
            self.alerts_layout.addWidget(
                self._make_alert(
                    "amber",
                    f"{len(pending_orders)} order(s) awaiting warehouse dispatch.",
                )
            )

    def _make_alert(self, tone, message):
        frame = QFrame()
        frame.setObjectName(f"alert_{tone}")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 11, 14, 11)
        label = QLabel(message)
        label.setObjectName(f"alert_text_{tone}")
        label.setWordWrap(True)
        layout.addWidget(label)
        return frame

    def _load_stats(self, sales_today, orders_today, low_stock, outstanding):
        self._clear_layout(self.stats_row)
        cards = [
            ("Total Sales Today", format_currency(sales_today), "navy"),
            ("Orders Today", str(orders_today), "teal"),
            ("Low Stock Alerts", str(low_stock), "amber"),
            ("Outstanding Balances", format_currency(outstanding), "red"),
        ]
        for label, value, tone in cards:
            self.stats_row.addWidget(self._make_stat_card(label, value, tone))

    def _make_stat_card(self, label, value, tone):
        card = QFrame()
        card.setObjectName(f"stat_card_{tone}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)
        value_label = QLabel(str(value))
        value_label.setObjectName("stat_value")
        label_widget = QLabel(label)
        label_widget.setObjectName("stat_label")
        layout.addWidget(value_label)
        layout.addWidget(label_widget)
        return card

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
                status = "Unpaid"

            values = [
                row.get("invoice_number") or "-",
                row.get("customer_name") or "Walk-in",
                format_currency(total),
            ]
            for col, value in enumerate(values):
                mono = col in {0, 2}
                color = COLORS["navy"] if col == 0 else None
                self.transactions_table.setItem(
                    row_index,
                    col,
                    table_item(value, mono=mono, bold=mono, color=color),
                )
            self.transactions_table.setCellWidget(
                row_index,
                3,
                make_badge(status, tone_for_status(status)),
            )
            self.transactions_table.setRowHeight(row_index, 38)

    def _load_progress(self, orders):
        self._clear_layout(self.progress_layout)
        active_orders = [
            row for row in orders
            if row.get("status") not in {"Completed", "Cancelled"}
        ][:4]

        if not active_orders:
            empty = QLabel("No active orders.")
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
