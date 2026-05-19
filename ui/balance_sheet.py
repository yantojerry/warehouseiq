from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components import error_dialog
from backend.infrastructure.api_client import get_balance_customers, get_balance_summary
from backend.core.helpers import format_currency, format_date
from ui.styles import (
    COLORS,
    configure_table,
    make_badge,
    table_item,
    tone_for_status,
)


class BalanceSheetPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("content_area")
        self._build_ui()
        self.load_balance_sheet()

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
        title = QLabel("Balance Sheet")
        title.setObjectName("page_title")
        sub = QLabel("Receivables, collections, and open invoice balances")
        sub.setObjectName("page_subtitle")
        title_block.addWidget(title)
        title_block.addWidget(sub)
        header.addLayout(title_block)
        header.addStretch()
        page.addLayout(header)

        self.summary_row = QHBoxLayout()
        self.summary_row.setSpacing(14)
        page.addLayout(self.summary_row)

        self.method_row = QHBoxLayout()
        self.method_row.setSpacing(10)
        page.addLayout(self.method_row)

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

        card_title = QLabel("Customer Receivables")
        card_title.setObjectName("card_title")
        toolbar.addWidget(card_title)
        toolbar.addStretch()

        self.filter_combo = QComboBox()
        self.filter_combo.setFixedHeight(36)
        self.filter_combo.addItems(["All", "Partial", "Unpaid", "Pending"])
        self.filter_combo.currentIndexChanged.connect(self.load_balance_sheet)
        toolbar.addWidget(self.filter_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search customer...")
        self.search_input.textChanged.connect(self.load_balance_sheet)
        self.search_input.setFixedWidth(240)
        self.search_input.setFixedHeight(36)
        toolbar.addWidget(self.search_input)
        card_layout.addWidget(card_header)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "CUSTOMER",
            "INVOICE #",
            "TOTAL",
            "PAID",
            "BALANCE",
            "STATUS",
            "PAYMENT METHOD",
            "DATE ISSUED",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        configure_table(self.table)
        self.table.setMinimumHeight(450)
        card_layout.addWidget(self.table)
        page.addWidget(card)
        page.addStretch()

    def load_balance_sheet(self):
        search = self.search_input.text().strip().lower()
        status = self.filter_combo.currentText()

        try:
            summary = get_balance_summary()
            rows = get_balance_customers()
        except Exception as exc:
            error_dialog(self, "Balance Sheet", str(exc))
            return

        self._update_summary(summary)
        self._update_methods(summary.get("by_method") or [])

        if search:
            rows = [
                row for row in rows
                if search in str(row.get("full_name") or "").lower()
            ]
        if status != "All":
            rows = [
                row for row in rows
                if (row.get("status") or "") == status
            ]

        self._load_table(rows)

    def _update_summary(self, summary):
        self._clear_layout(self.summary_row)
        uncollected = float(summary.get("uncollected") or 0)
        cards = [
            ("Total Receivables", format_currency(summary.get("receivables") or 0), "navy"),
            ("Total Collected", format_currency(summary.get("collected") or 0), "teal"),
            ("Uncollected", format_currency(uncollected), "red" if uncollected > 0 else "green"),
        ]
        for label, value, tone in cards:
            self.summary_row.addWidget(self._make_stat_card(label, value, tone))

    def _update_methods(self, methods):
        self._clear_layout(self.method_row)
        if not methods:
            self.method_row.addWidget(self._make_method_card("No collections", format_currency(0)))
            self.method_row.addStretch()
            return

        for row in methods:
            self.method_row.addWidget(
                self._make_method_card(
                    row.get("payment_method") or "Unknown",
                    format_currency(row.get("collected") or 0),
                )
            )
        self.method_row.addStretch()

    def _load_table(self, rows):
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            total = float(row.get("total_amount") or 0)
            paid = float(row.get("amount_paid") or 0)
            if row.get("invoice_id"):
                balance = max(0.0, total - paid)
            else:
                balance = float(row.get("balance") or 0)
            status = row.get("status") or "-"
            values = [
                row.get("full_name") or "-",
                row.get("invoice_number") or "-",
                format_currency(total),
                format_currency(paid),
                format_currency(balance),
                row.get("payment_method") or "-",
                format_date(str(row.get("issued_at"))) if row.get("issued_at") else "-",
            ]

            table_columns = [0, 1, 2, 3, 4, 6, 7]
            for value, col in zip(values, table_columns):
                mono = col in {1, 2, 3, 4}
                bold = col in {1, 2, 3, 4}
                color = COLORS["red"] if col == 4 and balance > 0 else None
                self.table.setItem(
                    row_index,
                    col,
                    table_item(value, mono=mono, bold=bold, color=color),
                )

            self.table.setCellWidget(row_index, 5, make_badge(status, tone_for_status(status)))
            self.table.setRowHeight(row_index, 46)

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

    def _make_method_card(self, method, value):
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(190)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)
        amount = QLabel(value)
        amount.setObjectName("card_title")
        label = QLabel(method)
        label.setObjectName("stat_label")
        layout.addWidget(amount)
        layout.addWidget(label)
        return card

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
