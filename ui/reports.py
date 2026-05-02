from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.components import CardFrame
from utils.api_client import ApiError, get_orders_report, get_payments_report, get_sales_report
from utils.helpers import format_currency
from utils.styles import make_badge, set_button_kind


class ReportsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("content_area")
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        header = QHBoxLayout()
        block = QVBoxLayout()
        title = QLabel("Reports & Analytics")
        title.setObjectName("page_title")
        sub = QLabel("Sales, order, and payment performance")
        sub.setObjectName("page_subtitle")
        block.addWidget(title)
        block.addWidget(sub)
        header.addLayout(block)
        header.addStretch()
        refresh = QPushButton("Refresh")
        set_button_kind(refresh, "outline")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        self.cards = QHBoxLayout()
        self.cards.setSpacing(14)
        root.addLayout(self.cards)

        self.orders_card = CardFrame("Orders by Status")
        root.addWidget(self.orders_card)
        self.payments_card = CardFrame("Collections by Payment Method")
        root.addWidget(self.payments_card)
        root.addStretch()

    def refresh(self):
        try:
            sales = get_sales_report()
            orders = get_orders_report()
            payments = get_payments_report()
        except ApiError:
            return
        self._clear(self.cards)
        for title, value, tone in [
            ("Invoices", str(sales.get("invoices", 0)), "navy"),
            ("Gross Sales", format_currency(float(sales.get("gross_sales") or 0)), "teal"),
            ("Collected", format_currency(float(sales.get("collected") or 0)), "green"),
            ("Uncollected", format_currency(float(sales.get("uncollected") or 0)), "red"),
        ]:
            self.cards.addWidget(self._stat(title, value, tone))
        self._list(self.orders_card.body_layout, orders, "status", "count")
        self._list(self.payments_card.body_layout, payments, "payment_method", "collected", money=True)

    def _stat(self, label, value, tone):
        card = CardFrame()
        card.setObjectName(f"stat_card_{tone}")
        card.body_layout.addWidget(QLabel(value))
        card.body_layout.itemAt(0).widget().setObjectName("stat_value")
        card.body_layout.addWidget(QLabel(label))
        card.body_layout.itemAt(1).widget().setObjectName("stat_label")
        return card

    def _list(self, layout, rows, key, value, money=False):
        self._clear(layout)
        if not rows:
            empty = QLabel("No records found")
            empty.setObjectName("stat_label")
            layout.addWidget(empty)
            return
        for row in rows:
            line = QHBoxLayout()
            line.setSpacing(10)
            line.addWidget(make_badge(row.get(key) or "Unknown", "navy"))
            line.addStretch()
            amount = row.get(value) or 0
            text = format_currency(float(amount)) if money else str(amount)
            label = QLabel(text)
            label.setObjectName("stat_value")
            line.addWidget(label)
            layout.addLayout(line)

    @staticmethod
    def _clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                ReportsPage._clear(item.layout())
