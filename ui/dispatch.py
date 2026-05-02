from datetime import date

from PyQt5.QtCore import QUrl, Qt, QTimer
from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components import error_dialog
from utils.api_client import (
    API_BASE_URL,
    ApiError,
    get_dispatch_queue,
    list_inventory,
    update_dispatch_item,
    update_order_notes,
    update_order_status,
)
from utils.helpers import format_date
from utils.styles import (
    COLORS,
    configure_table,
    display_order_status,
    make_badge,
    set_button_kind,
    stock_color,
    stock_status,
    table_item,
    tone_for_status,
)


class DispatchPage(QWidget):
    def __init__(self, permissions=None):
        super().__init__()
        self.permissions = set(permissions or ())
        self.setObjectName("content_area")
        self.inventory = []
        self._socket_backoff_seconds = 2
        self._build_ui()
        self._connect_dispatch_socket()
        self.refresh()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(10000)

    def _can(self, permission):
        return permission in self.permissions

    def _connect_dispatch_socket(self):
        self.socket = QWebSocket()
        self.socket.textMessageReceived.connect(lambda _message: self.refresh())
        self.socket.connected.connect(self._reset_dispatch_socket_backoff)
        self.socket.disconnected.connect(self._schedule_dispatch_socket_reconnect)
        ws_url = API_BASE_URL.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
        self.socket.open(QUrl(f"{ws_url}/dispatch/ws"))

    def _reset_dispatch_socket_backoff(self):
        self._socket_backoff_seconds = 2

    def _schedule_dispatch_socket_reconnect(self):
        delay = self._socket_backoff_seconds
        self._socket_backoff_seconds = min(delay * 2, 30)
        QTimer.singleShot(delay * 1000, self._connect_dispatch_socket)

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
        title = QLabel("Warehouse Dispatch")
        title.setObjectName("page_title")
        sub = QLabel("Floor picking queue and live stock snapshot")
        sub.setObjectName("page_subtitle")
        title_block.addWidget(title)
        title_block.addWidget(sub)
        header.addLayout(title_block)
        header.addStretch()
        live = QLabel("Live")
        live.setObjectName("live_dot")
        header.addWidget(live, alignment=Qt.AlignTop)
        page.addLayout(header)

        info = QFrame()
        info.setObjectName("alert_navy")
        info_layout = QHBoxLayout(info)
        info_layout.setContentsMargins(14, 11, 14, 11)
        text = QLabel("Orders are automatically assigned to the floor with matching stock")
        text.setObjectName("alert_text_navy")
        info_layout.addWidget(text)
        page.addWidget(info)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        page.addLayout(columns)

        left = QFrame()
        left.setObjectName("card")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_header = QFrame()
        left_header.setObjectName("card_header")
        left_header_layout = QHBoxLayout(left_header)
        left_header_layout.setContentsMargins(18, 13, 18, 13)
        left_title = QLabel("Pending Dispatches")
        left_title.setObjectName("card_title")
        left_header_layout.addWidget(left_title)
        left_header_layout.addStretch()
        left_layout.addWidget(left_header)
        left_body = QFrame()
        left_body.setObjectName("card_body")
        self.dispatch_layout = QVBoxLayout(left_body)
        self.dispatch_layout.setContentsMargins(14, 14, 14, 14)
        self.dispatch_layout.setSpacing(12)
        left_layout.addWidget(left_body)
        columns.addWidget(left, 3)

        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(self._build_snapshot_card())
        right.addWidget(self._build_completed_card())
        right.addStretch()
        columns.addLayout(right, 2)

    def _build_snapshot_card(self):
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("card_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 13, 18, 13)
        title = QLabel("Floor Inventory Snapshot")
        title.setObjectName("card_title")
        header_layout.addWidget(title)
        header_layout.addStretch()
        outer.addWidget(header)

        body = QFrame()
        body.setObjectName("card_body")
        self.snapshot_layout = QVBoxLayout(body)
        self.snapshot_layout.setContentsMargins(18, 18, 18, 18)
        self.snapshot_layout.setSpacing(10)
        outer.addWidget(body)
        return card

    def _build_completed_card(self):
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("card_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 13, 18, 13)
        title = QLabel("Completed Today")
        title.setObjectName("card_title")
        header_layout.addWidget(title)
        header_layout.addStretch()
        outer.addWidget(header)

        body = QFrame()
        body.setObjectName("card_body")
        self.completed_layout = QVBoxLayout(body)
        self.completed_layout.setContentsMargins(18, 18, 18, 18)
        self.completed_layout.setSpacing(8)
        outer.addWidget(body)
        return card

    def refresh(self):
        if not self._can("dispatch.view"):
            return
        try:
            self.inventory = list_inventory()
            orders = get_dispatch_queue()
        except ApiError:
            return

        dispatches = [row for row in orders if row.get("status") in {"Pending", "Processing", "Ready"}]
        completed_today = [
            row for row in orders
            if row.get("status") == "Completed" and str(row.get("updated_at") or row.get("created_at")).startswith(date.today().isoformat())
        ]
        self._render_dispatches(dispatches[:8])
        self._render_snapshot()
        self._render_completed(completed_today[:8])

    def _render_dispatches(self, orders):
        self._clear_layout(self.dispatch_layout)
        if not orders:
            empty = QLabel("No pending dispatches.")
            empty.setStyleSheet(f"background: transparent; color: {COLORS['text_3']};")
            self.dispatch_layout.addWidget(empty)
            self.dispatch_layout.addStretch()
            return

        for order in orders:
            self.dispatch_layout.addWidget(self._dispatch_card(order))
        self.dispatch_layout.addStretch()

    def _dispatch_card(self, order):
        items = order.get("items") or []
        current_note = order.get("notes")

        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("dispatch_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(8)
        header_layout.addWidget(make_badge(order.get("order_number") or "-", "navy"))
        customer = QLabel(order.get("customer_name") or "Walk-in")
        customer.setStyleSheet(f"background: transparent; color: {COLORS['white']}; font-size: 13px; font-weight: 800;")
        header_layout.addWidget(customer, 1)
        time = QLabel(format_date(str(order.get("created_at"))))
        time.setStyleSheet("background: transparent; color: rgba(255,255,255,0.62); font-size: 11px;")
        header_layout.addWidget(time)
        outer.addWidget(header)

        body = QFrame()
        body.setObjectName("card_body")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        if order.get("status") != "Pending":
            alert = QFrame()
            alert.setObjectName("alert_teal")
            alert_layout = QHBoxLayout(alert)
            alert_layout.setContentsMargins(12, 9, 12, 9)
            alert_text = QLabel(f"Progress update: {display_order_status(order.get('status'))}")
            alert_text.setObjectName("alert_text_teal")
            alert_layout.addWidget(alert_text)
            layout.addWidget(alert)

        table = QTableWidget(len(items), 5)
        table.setHorizontalHeaderLabels(["PRODUCT", "QTY", "FLOOR", "STOCK AVAILABLE", "PICK STATUS"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        configure_table(table)
        table.setMaximumHeight(180)
        for row_index, item in enumerate(items):
            available = self._available_stock(item.get("item_name"), item.get("floor"))
            values = [
                item.get("item_name") or "-",
                str(item.get("quantity") or 0),
                f"F{item.get('floor')}",
                str(available),
            ]
            for col, value in enumerate(values):
                color = stock_color(stock_status(available, 5)) if col == 3 else None
                table.setItem(row_index, col, table_item(value, mono=col > 0, bold=col > 0, color=color))
            table.setCellWidget(row_index, 4, self._pick_buttons(order["id"], item))
            table.setRowHeight(row_index, 38)
        layout.addWidget(table)

        layout.addLayout(self._floor_grid(items))

        if self._can("dispatch.update"):
            actions = QHBoxLayout()
            send = QPushButton(self._dispatch_button_text(order.get("status")))
            set_button_kind(send, "teal")
            send.clicked.connect(lambda checked=False, oid=order["id"], status=order.get("status"): self.advance_order(oid, status))
            actions.addWidget(send, 1)
            note = QPushButton("Note")
            set_button_kind(note, "outline")
            note.clicked.connect(
                lambda checked=False, oid=order["id"], text=current_note: self.open_note_dialog(oid, text)
            )
            actions.addWidget(note)
            layout.addLayout(actions)

        outer.addWidget(body)
        return card

    def _pick_buttons(self, order_id, item):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        if not self._can("dispatch.update"):
            layout.addWidget(QLabel(item.get("pick_status") or "Pending"))
            return widget
        choices = [
            ("Picked", "teal"),
            ("Partial", "outline"),
            ("Out", "danger"),
        ]
        item_id = item.get("item_id")
        for label, tone in choices:
            button = QPushButton(label)
            button.setFixedHeight(26)
            set_button_kind(button, tone)
            status_value = "Partially Picked" if label == "Partial" else "Out of Stock" if label == "Out" else "Picked"
            button.clicked.connect(
                lambda checked=False, oid=order_id, iid=item_id, status=status_value: self.update_pick(oid, iid, status)
            )
            layout.addWidget(button)
        return widget

    def update_pick(self, order_id, item_id, status):
        try:
            update_dispatch_item(order_id, item_id, status, actor="warehouse")
            self.refresh()
        except ApiError as exc:
            error_dialog(self, "Dispatch", str(exc))

    def open_note_dialog(self, order_id, current_note):
        dialog = NoteDialog(self, order_id, current_note)
        if dialog.exec_():
            self.refresh()

    def _floor_grid(self, items):
        grid = QGridLayout()
        grid.setSpacing(8)
        floors = {floor: [] for floor in range(1, 7)}
        for item in items:
            floors.setdefault(int(item.get("floor") or 1), []).append(item)
        for floor in range(1, 7):
            floor_items = floors.get(floor) or []
            card = QFrame()
            tone = "gray"
            if floor_items:
                low = any(self._available_stock(item.get("item_name"), item.get("floor")) <= 5 for item in floor_items)
                tone = "amber" if low else "teal"
            card.setObjectName(f"floor_card_{tone}")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            label = QLabel(f"F{floor}")
            label.setStyleSheet(f"background: transparent; color: {COLORS['navy']}; font-family: Courier New; font-size: 18px; font-weight: 800;")
            count = QLabel(f"{len(floor_items)} item(s)")
            count.setStyleSheet(f"background: transparent; color: {COLORS['text_3']}; font-size: 10.5px;")
            card_layout.addWidget(label)
            card_layout.addWidget(count)
            grid.addWidget(card, (floor - 1) // 3, (floor - 1) % 3)
        return grid

    def _render_snapshot(self):
        self._clear_layout(self.snapshot_layout)
        by_floor = {floor: [] for floor in range(1, 7)}
        for item in self.inventory:
            by_floor.setdefault(int(item.get("floor") or 1), []).append(item)

        for floor in range(1, 7):
            floor_items = by_floor.get(floor, [])[:4]
            frame = QFrame()
            frame.setObjectName("floor_card_gray")
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(10, 10, 10, 10)
            title = QLabel(f"Floor {floor}")
            title.setStyleSheet(f"background: transparent; color: {COLORS['navy']}; font-size: 13px; font-weight: 800;")
            layout.addWidget(title)
            if not floor_items:
                empty = QLabel("No items")
                empty.setStyleSheet(f"background: transparent; color: {COLORS['text_3']};")
                layout.addWidget(empty)
            for item in floor_items:
                row = QHBoxLayout()
                name = QLabel(item.get("item_name") or "-")
                name.setStyleSheet(f"background: transparent; color: {COLORS['text_2']}; font-size: 11px;")
                status = stock_status(int(item["quantity"]), int(item["low_stock_threshold"]))
                qty = QLabel(str(item["quantity"]))
                qty.setStyleSheet(
                    f"background: transparent; color: {stock_color(status)}; "
                    "font-family: Courier New; font-weight: 800;"
                )
                row.addWidget(name, 1)
                row.addWidget(qty)
                layout.addLayout(row)
            self.snapshot_layout.addWidget(frame)
        self.snapshot_layout.addStretch()

    def _render_completed(self, rows):
        self._clear_layout(self.completed_layout)
        if not rows:
            empty = QLabel("No completed orders today.")
            empty.setStyleSheet(f"background: transparent; color: {COLORS['text_3']};")
            self.completed_layout.addWidget(empty)
            return
        for row in rows:
            item = QFrame()
            item.setObjectName("alert_teal")
            layout = QHBoxLayout(item)
            layout.setContentsMargins(10, 8, 10, 8)
            number = QLabel(row.get("order_number") or "-")
            number.setStyleSheet(f"background: transparent; color: {COLORS['navy']}; font-family: Courier New; font-weight: 800;")
            layout.addWidget(number, 1)
            layout.addWidget(make_badge("Done", "teal"))
            self.completed_layout.addWidget(item)

    def _available_stock(self, item_name, floor):
        for item in self.inventory:
            if item.get("item_name") == item_name and int(item.get("floor") or 0) == int(floor or 0):
                return int(item.get("quantity") or 0)
        return 0

    @staticmethod
    def _dispatch_button_text(status):
        return {
            "Pending": "Send to Warehouse",
            "Processing": "Mark Ready",
            "Ready": "Complete",
        }.get(status, "Send to Warehouse")

    def advance_order(self, order_id, status):
        next_status = {
            "Pending": "Processing",
            "Processing": "Ready",
            "Ready": "Completed",
        }.get(status)
        if not next_status:
            return
        try:
            update_order_status(order_id, next_status)
            self.refresh()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                DispatchPage._clear_layout(child_layout)


class NoteDialog(QDialog):
    def __init__(self, parent, order_id, current_note=None):
        super().__init__(parent)
        self.order_id = order_id
        self.setWindowTitle("Dispatch Note")
        self.setMinimumWidth(420)
        self._build_ui(current_note)

    def _build_ui(self, current_note):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Dispatch Note")
        title.setObjectName("login_title")
        layout.addWidget(title)

        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("Add dispatch note...")
        self.note_input.setPlainText(current_note or "")
        self.note_input.setMinimumHeight(140)
        layout.addWidget(self.note_input)

        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        set_button_kind(cancel, "outline")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        set_button_kind(save, "teal")
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _save(self):
        note = self.note_input.toPlainText().strip() or None
        try:
            update_order_notes(self.order_id, note)
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Dispatch Note", str(exc))
