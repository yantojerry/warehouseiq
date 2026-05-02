import base64
import os

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components import confirm_dialog, error_dialog, info_dialog, warning_dialog
from utils.api_client import (
    ApiError,
    create_inventory_item,
    delete_inventory_item,
    get_inventory_item,
    list_inventory,
    restock_inventory_item,
    stock_out_inventory_item,
    update_inventory_item,
)
from utils.helpers import format_currency
from utils.styles import (
    COLORS,
    configure_table,
    make_badge,
    repolish,
    set_button_kind,
    stock_color,
    stock_status,
    table_item,
)


PRODUCT_CATEGORIES = [
    "Construction",
    "Electrical",
    "Plumbing",
    "Hardware",
    "Paint",
    "Tools",
    "Safety",
    "Fasteners",
    "Flooring",
    "Roofing",
    "Adhesives",
    "Other",
]


class InventoryPage(QWidget):
    def __init__(self, permissions=None):
        super().__init__()
        self.permissions = set(permissions or ())
        self.setObjectName("content_area")
        self.selected_floor = None
        self.selected_category = "All Categories"
        self._floor_buttons = {}
        self._view_mode = "list"
        self._build_ui()
        self._refresh_category_options()
        self.load_inventory()

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

        # Page header
        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(3)
        title = QLabel("Inventory")
        title.setObjectName("page_title")
        sub = QLabel("Real-time stock levels across all floors")
        sub.setObjectName("page_subtitle")
        title_block.addWidget(title)
        title_block.addWidget(sub)
        header.addLayout(title_block)
        header.addStretch()
        page.addLayout(header)

        # Low stock alert
        self.low_alert = QFrame()
        self.low_alert.setObjectName("alert_red")
        alert_layout = QHBoxLayout(self.low_alert)
        alert_layout.setContentsMargins(14, 11, 14, 11)
        self.low_alert_label = QLabel("")
        self.low_alert_label.setObjectName("alert_text_red")
        self.low_alert_label.setWordWrap(True)
        alert_layout.addWidget(self.low_alert_label)
        page.addWidget(self.low_alert)

        # Body
        body = QHBoxLayout()
        body.setSpacing(14)
        page.addLayout(body)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("card")
        sidebar.setFixedWidth(200)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 14, 14, 14)
        side_layout.setSpacing(6)

        floor_label = QLabel("FLOOR FILTER")
        floor_label.setObjectName("section_label")
        side_layout.addWidget(floor_label)
        for label, floor in [("All Floors", None)] + [(f"Floor {i}", i) for i in range(1, 7)]:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=floor: self._set_floor(v))
            side_layout.addWidget(btn)
            self._floor_buttons[floor] = btn

        side_layout.addSpacing(10)

        category_label = QLabel("CATEGORY")
        category_label.setObjectName("section_label")
        side_layout.addWidget(category_label)
        self.category_filter = QComboBox()
        self.category_filter.currentTextChanged.connect(self._set_category)
        side_layout.addWidget(self.category_filter)

        side_layout.addSpacing(10)

        sort_label = QLabel("SORT BY")
        sort_label.setObjectName("section_label")
        side_layout.addWidget(sort_label)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Name (A-Z)",
            "Name (Z-A)",
            "Stock: Low to High",
            "Stock: High to Low",
            "Price: Low to High",
            "Price: High to Low",
        ])
        self.sort_combo.currentTextChanged.connect(self.load_inventory)
        side_layout.addWidget(self.sort_combo)

        side_layout.addStretch()
        body.addWidget(sidebar)

        # Main card
        card = QFrame()
        card.setObjectName("card")
        main_layout = QVBoxLayout(card)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Card header
        card_header = QFrame()
        card_header.setObjectName("card_header")
        header_layout = QHBoxLayout(card_header)
        header_layout.setContentsMargins(18, 13, 18, 13)
        header_layout.setSpacing(8)

        card_title = QLabel("Stock Ledger")
        card_title.setObjectName("card_title")
        header_layout.addWidget(card_title)
        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search item name or code...")
        self.search_input.setFixedWidth(220)
        self.search_input.textChanged.connect(self.load_inventory)
        header_layout.addWidget(self.search_input)

        self.btn_list_view = QPushButton("List")
        self.btn_list_view.setObjectName("pill_button_selected")
        self.btn_list_view.setFixedHeight(30)
        self.btn_list_view.setCursor(Qt.PointingHandCursor)
        self.btn_list_view.clicked.connect(lambda: self._set_view("list"))
        header_layout.addWidget(self.btn_list_view)

        self.btn_grid_view = QPushButton("Grid")
        self.btn_grid_view.setObjectName("pill_button")
        self.btn_grid_view.setFixedHeight(30)
        self.btn_grid_view.setCursor(Qt.PointingHandCursor)
        self.btn_grid_view.clicked.connect(lambda: self._set_view("grid"))
        header_layout.addWidget(self.btn_grid_view)

        btn_refresh = QPushButton("Refresh")
        set_button_kind(btn_refresh, "outline")
        btn_refresh.clicked.connect(self._reload_all)
        header_layout.addWidget(btn_refresh)

        if self._can("inventory.add"):
            btn_add = QPushButton("+ Add Item")
            set_button_kind(btn_add, "teal")
            btn_add.clicked.connect(self.open_add_dialog)
            header_layout.addWidget(btn_add)

        main_layout.addWidget(card_header)

        # List view
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "IMAGE", "PRODUCT", "CATEGORY", "FLOOR",
            "STOCK", "MIN.", "STATUS", "ACTION",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 64)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 280)
        configure_table(self.table)
        self.table.setMinimumHeight(430)
        main_layout.addWidget(self.table)

        # Grid view
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setFrameShape(QFrame.NoFrame)
        self.grid_scroll.setObjectName("grid_scroll_area")
        self.grid_container = QWidget()
        self.grid_container.setObjectName("page_content")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(16, 16, 16, 16)
        self.grid_layout.setSpacing(12)
        self.grid_scroll.setWidget(self.grid_container)
        self.grid_scroll.hide()
        main_layout.addWidget(self.grid_scroll)

        body.addWidget(card, 1)
        self._update_floor_buttons()

    def _set_view(self, mode):
        self._view_mode = mode
        self.table.setVisible(mode == "list")
        self.grid_scroll.setVisible(mode == "grid")
        self.btn_list_view.setObjectName("pill_button_selected" if mode == "list" else "pill_button")
        self.btn_grid_view.setObjectName("pill_button_selected" if mode == "grid" else "pill_button")
        repolish(self.btn_list_view)
        repolish(self.btn_grid_view)
        self.load_inventory()

    def _set_floor(self, floor):
        self.selected_floor = floor
        self._update_floor_buttons()
        self.load_inventory()

    def _update_floor_buttons(self):
        for floor, btn in self._floor_buttons.items():
            btn.setObjectName("filter_button_active" if floor == self.selected_floor else "filter_button")
            repolish(btn)

    def _set_category(self, category):
        self.selected_category = category or "All Categories"
        self.load_inventory()

    def _refresh_category_options(self):
        current = self.selected_category
        try:
            rows = list_inventory()
        except ApiError:
            rows = []
        categories = sorted({(row.get("category") or "Other").strip() for row in rows if row.get("category")})
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All Categories")
        for cat in categories:
            self.category_filter.addItem(cat)
        index = self.category_filter.findText(current)
        self.category_filter.setCurrentIndex(index if index >= 0 else 0)
        self.category_filter.blockSignals(False)

    def _reload_all(self):
        self._refresh_category_options()
        self.load_inventory()

    def _sort_rows(self, rows):
        sort = self.sort_combo.currentText() if hasattr(self, "sort_combo") else "Name (A-Z)"
        if sort == "Name (A-Z)":
            return sorted(rows, key=lambda r: r["item_name"].lower())
        if sort == "Name (Z-A)":
            return sorted(rows, key=lambda r: r["item_name"].lower(), reverse=True)
        if sort == "Stock: Low to High":
            return sorted(rows, key=lambda r: int(r["quantity"]))
        if sort == "Stock: High to Low":
            return sorted(rows, key=lambda r: int(r["quantity"]), reverse=True)
        if sort == "Price: Low to High":
            return sorted(rows, key=lambda r: float(r.get("unit_price", 0)))
        if sort == "Price: High to Low":
            return sorted(rows, key=lambda r: float(r.get("unit_price", 0)), reverse=True)
        return rows

    def load_inventory(self):
        search = self.search_input.text().strip() if hasattr(self, "search_input") else ""
        try:
            rows = list_inventory(search=search or None, floor=self.selected_floor)
        except ApiError:
            return

        if self.selected_category != "All Categories":
            rows = [r for r in rows if (r.get("category") or "Other") == self.selected_category]

        rows = self._sort_rows(rows)

        low_count = sum(
            1 for r in rows
            if stock_status(int(r["quantity"]), int(r["low_stock_threshold"])) != "OK"
        )
        self.low_alert.setVisible(low_count > 0)
        self.low_alert_label.setText(f"{low_count} item(s) are low or critical in the current view.")

        if self._view_mode == "list":
            self._load_list_view(rows)
        else:
            self._load_grid_view(rows)

    def _load_list_view(self, rows):
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            item_id = row["id"]
            status = stock_status(int(row["quantity"]), int(row["low_stock_threshold"]))

            img_lbl = QLabel()
            img_lbl.setAlignment(Qt.AlignCenter)
            img_lbl.setFixedSize(52, 44)
            img_data = row.get("image_data")
            if img_data:
                try:
                    pix = QPixmap()
                    pix.loadFromData(base64.b64decode(img_data))
                    img_lbl.setPixmap(pix.scaled(44, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                except Exception:
                    img_lbl.setText("No image")
            else:
                img_lbl.setText("No image")
                img_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['muted']};")
            self.table.setCellWidget(i, 0, img_lbl)

            values = [
                row["item_name"],
                row.get("category") or "Other",
                f"F{row['floor']}",
                str(row["quantity"]),
                str(row["low_stock_threshold"]),
            ]
            for col, value in enumerate(values):
                mono = col in {2, 3, 4}
                bold = col in {0, 2, 3, 4}
                color = stock_color(status) if col == 3 else None
                self.table.setItem(i, col + 1, table_item(value, mono=mono, bold=bold, color=color))

            self.table.setCellWidget(i, 6, make_badge(status, {"OK": "teal", "Low": "amber", "Critical": "red"}[status]))
            self.table.setCellWidget(i, 7, self._make_action_buttons(item_id, row["quantity"]))
            self.table.setRowHeight(i, 52)

    def _load_grid_view(self, rows):
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        cols = 4
        for idx, row in enumerate(rows):
            card = self._make_grid_card(row)
            self.grid_layout.addWidget(card, idx // cols, idx % cols)

        remainder = len(rows) % cols
        if remainder:
            for i in range(cols - remainder):
                spacer = QWidget()
                self.grid_layout.addWidget(spacer, len(rows) // cols, remainder + i)

    def _make_grid_card(self, row):
        item_id = row["id"]
        status = stock_status(int(row["quantity"]), int(row["low_stock_threshold"]))
        tone = {"OK": "teal", "Low": "amber", "Critical": "red"}[status]

        card = QFrame()
        card.setObjectName("product_card")
        card.setFixedWidth(200)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setFixedHeight(100)
        img_lbl.setStyleSheet(f"background:{COLORS['surface']}; border-radius:8px;")
        img_data = row.get("image_data")
        if img_data:
            try:
                pix = QPixmap()
                pix.loadFromData(base64.b64decode(img_data))
                img_lbl.setPixmap(pix.scaled(180, 95, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except Exception:
                img_lbl.setText("No image")
                img_lbl.setStyleSheet(f"font-size:11px; background:{COLORS['surface']}; border-radius:8px;")
        else:
            img_lbl.setText("No image")
            img_lbl.setStyleSheet(f"font-size:11px; background:{COLORS['surface']}; border-radius:8px;")
        layout.addWidget(img_lbl)

        name = QLabel(row["item_name"])
        name.setObjectName("card_title")
        name.setWordWrap(True)
        layout.addWidget(name)

        cat = QLabel(row.get("category") or "Other")
        cat.setObjectName("stat_label")
        layout.addWidget(cat)

        stock_row = QHBoxLayout()
        stock_lbl = QLabel(f"Stock: {row['quantity']}")
        stock_lbl.setStyleSheet(f"color: {stock_color(status)}; font-weight: 700; font-size: 12px; background: transparent;")
        stock_row.addWidget(stock_lbl)
        stock_row.addStretch()
        stock_row.addWidget(make_badge(status, tone))
        layout.addLayout(stock_row)

        price = QLabel(f"₱{float(row.get('unit_price', 0)):,.2f}")
        price.setStyleSheet(f"color: {COLORS['text']}; font-weight: 700; font-size: 13px; background: transparent;")
        layout.addWidget(price)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        if self._can("inventory.edit"):
            btn_edit = QPushButton("Edit")
            btn_edit.setFixedHeight(28)
            set_button_kind(btn_edit, "outline")
            btn_edit.clicked.connect(lambda _, rid=item_id: self.open_edit_dialog(rid))
            btn_row.addWidget(btn_edit)

        if self._can("inventory.delete"):
            btn_del = QPushButton("Delete")
            btn_del.setFixedHeight(28)
            set_button_kind(btn_del, "danger")
            btn_del.clicked.connect(lambda _, rid=item_id, n=row["item_name"]: self._confirm_delete(rid, n))
            btn_row.addWidget(btn_del)

        if btn_row.count() == 0:
            btn_row.addWidget(QLabel("-"))
        layout.addLayout(btn_row)

        return card

    def _make_action_buttons(self, item_id, quantity):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        if self._can("inventory.edit"):
            btn_edit = QPushButton("Edit")
            btn_edit.setFixedSize(52, 28)
            set_button_kind(btn_edit, "outline")
            btn_edit.clicked.connect(lambda _, rid=item_id: self.open_edit_dialog(rid))
            layout.addWidget(btn_edit)

        if self._can("inventory.update_stock"):
            btn_restock = QPushButton("Restock")
            btn_restock.setFixedSize(68, 28)
            set_button_kind(btn_restock, "teal")
            btn_restock.clicked.connect(lambda _, rid=item_id: self.open_restock_dialog(rid))
            layout.addWidget(btn_restock)

            btn_out = QPushButton("Stock Out")
            btn_out.setFixedSize(76, 28)
            set_button_kind(btn_out, "warning")
            btn_out.setEnabled(quantity > 0)
            btn_out.clicked.connect(lambda _, rid=item_id: self.open_stock_out_dialog(rid))
            layout.addWidget(btn_out)

        if self._can("inventory.delete"):
            btn_del = QPushButton("X")
            btn_del.setFixedSize(28, 28)
            set_button_kind(btn_del, "danger")
            btn_del.clicked.connect(lambda _, rid=item_id: self._confirm_delete(rid, ""))
            layout.addWidget(btn_del)

        if layout.count() == 0:
            layout.addWidget(QLabel("-"))
        return widget

    def _confirm_delete(self, item_id, name):
        item_label = f'"{name}"' if name else "this item"
        if confirm_dialog(self, "Delete Item", f"Deactivate {item_label}? It will remain in the audit trail."):
            try:
                delete_inventory_item(item_id)
                self._reload_all()
            except ApiError as exc:
                error_dialog(self, "Error", str(exc))

    def open_add_dialog(self):
        dialog = ItemDialog(self)
        if dialog.exec_():
            self._reload_all()

    def open_edit_dialog(self, item_id):
        dialog = ItemDialog(self, item_id=item_id)
        if dialog.exec_():
            self._reload_all()

    def open_restock_dialog(self, item_id):
        dialog = RestockDialog(self, item_id=item_id)
        if dialog.exec_():
            self.load_inventory()

    def open_stock_out_dialog(self, item_id):
        dialog = StockOutDialog(self, item_id=item_id)
        if dialog.exec_():
            self.load_inventory()


class ItemDialog(QDialog):
    def __init__(self, parent, item_id=None):
        super().__init__(parent)
        self.item_id = item_id
        self._image_b64 = None
        self.setWindowTitle("Edit Item" if item_id else "Add New Item")
        self.setMinimumWidth(480)
        self.setAttribute(Qt.WA_StyledBackground)
        self._build_ui()
        if item_id:
            self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Edit Inventory Item" if self.item_id else "Add Inventory Item")
        title.setObjectName("login_title")
        layout.addWidget(title)

        img_frame = QFrame()
        img_frame.setObjectName("card")
        img_layout = QHBoxLayout(img_frame)
        img_layout.setContentsMargins(12, 12, 12, 12)
        img_layout.setSpacing(12)

        self.img_preview = QLabel("No Image")
        self.img_preview.setAlignment(Qt.AlignCenter)
        self.img_preview.setFixedSize(80, 70)
        self.img_preview.setStyleSheet(
            f"background:{COLORS['surface']}; border-radius:8px; color:{COLORS['muted']}; font-size:11px;"
        )
        img_layout.addWidget(self.img_preview)

        img_btn_col = QVBoxLayout()
        img_btn_col.setSpacing(6)
        btn_pick = QPushButton("Choose Image")
        set_button_kind(btn_pick, "outline")
        btn_pick.clicked.connect(self._pick_image)
        btn_clear = QPushButton("Remove")
        set_button_kind(btn_clear, "danger")
        btn_clear.clicked.connect(self._clear_image)
        img_hint = QLabel("PNG, JPG or JPEG  ·  max 2MB")
        img_hint.setObjectName("stat_label")
        img_btn_col.addWidget(btn_pick)
        img_btn_col.addWidget(btn_clear)
        img_btn_col.addWidget(img_hint)
        img_layout.addLayout(img_btn_col)
        layout.addWidget(img_frame)

        form = QFormLayout()
        form.setSpacing(10)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("e.g. ITM-011")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Cement Bag 40kg")
        self.cat_input = QComboBox()
        self.cat_input.setEditable(True)
        self.cat_input.addItems(PRODUCT_CATEGORIES)
        self.cat_input.setCurrentText("")
        self.cat_input.lineEdit().setPlaceholderText("Select or type category")
        self.floor_input = QSpinBox()
        self.floor_input.setRange(1, 6)
        self.qty_input = QSpinBox()
        self.qty_input.setRange(0, 9999)
        self.thresh_input = QSpinBox()
        self.thresh_input.setRange(1, 999)
        self.thresh_input.setValue(5)
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 999999)
        self.price_input.setPrefix("PHP ")

        form.addRow("Item Code *", self.code_input)
        form.addRow("Item Name *", self.name_input)
        form.addRow("Category", self.cat_input)
        form.addRow("Floor (1-6) *", self.floor_input)
        form.addRow("Quantity *", self.qty_input)
        form.addRow("Low Stock Alert *", self.thresh_input)
        form.addRow("Unit Price *", self.price_input)
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

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Product Image", "",
            "Images (*.png *.jpg *.jpeg)"
        )
        if not path:
            return
        if os.path.getsize(path) > 2 * 1024 * 1024:
            warning_dialog(self, "Image Too Large", "Please choose an image under 2MB.")
            return
        with open(path, "rb") as f:
            self._image_b64 = base64.b64encode(f.read()).decode("utf-8")
        pix = QPixmap(path).scaled(80, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img_preview.setPixmap(pix)
        self.img_preview.setStyleSheet(f"background:{COLORS['surface']}; border-radius:8px;")

    def _clear_image(self):
        self._image_b64 = None
        self.img_preview.clear()
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            f"background:{COLORS['surface']}; border-radius:8px; color:{COLORS['muted']}; font-size:11px;"
        )

    def _load_data(self):
        try:
            row = get_inventory_item(self.item_id)
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
            return
        if row:
            self.code_input.setText(row["item_code"])
            self.name_input.setText(row["item_name"])
            category = (row["category"] or "").strip()
            if category and self.cat_input.findText(category) == -1:
                self.cat_input.addItem(category)
            self.cat_input.setCurrentText(category)
            self.floor_input.setValue(row["floor"])
            self.qty_input.setValue(row["quantity"])
            self.thresh_input.setValue(row["low_stock_threshold"])
            self.price_input.setValue(row["unit_price"])
            img_data = row.get("image_data")
            if img_data:
                self._image_b64 = img_data
                pix = QPixmap()
                try:
                    pix.loadFromData(base64.b64decode(img_data))
                    self.img_preview.setPixmap(pix.scaled(80, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.img_preview.setStyleSheet(f"background:{COLORS['surface']}; border-radius:8px;")
                except Exception:
                    pass

    def _save(self):
        code = self.code_input.text().strip()
        name = self.name_input.text().strip()
        if not code or not name:
            warning_dialog(self, "Validation", "Item Code and Name are required.")
            return
        payload = {
            "item_code": code,
            "item_name": name,
            "category": self.cat_input.currentText().strip() or None,
            "floor": self.floor_input.value(),
            "quantity": self.qty_input.value(),
            "low_stock_threshold": self.thresh_input.value(),
            "unit_price": self.price_input.value(),
        }
        if self._image_b64:
            payload["image_data"] = self._image_b64
        try:
            if self.item_id:
                update_inventory_item(self.item_id, payload)
            else:
                create_inventory_item(payload)
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Error", f"Could not save: {exc}")


class RestockDialog(QDialog):
    def __init__(self, parent, item_id):
        super().__init__(parent)
        self.item_id = item_id
        self.setWindowTitle("Restock Item")
        self.setMinimumWidth(340)
        self.setAttribute(Qt.WA_StyledBackground)
        self._build_ui()

    def _build_ui(self):
        try:
            row = get_inventory_item(self.item_id)
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
            self.reject()
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(row["item_name"])
        title.setObjectName("login_title")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Current Qty: {row['quantity']}"))

        form = QFormLayout()
        self.add_qty = QSpinBox()
        self.add_qty.setRange(1, 9999)
        self.add_qty.setValue(10)
        form.addRow("Add Quantity:", self.add_qty)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        set_button_kind(btn_cancel, "outline")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Restock")
        set_button_kind(btn_ok, "teal")
        btn_ok.clicked.connect(self._restock)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _restock(self):
        try:
            restock_inventory_item(self.item_id, self.add_qty.value())
            info_dialog(self, "Success", f"Added {self.add_qty.value()} units.")
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))


class StockOutDialog(QDialog):
    def __init__(self, parent, item_id):
        super().__init__(parent)
        self.item_id = item_id
        self.setWindowTitle("Stock Out Item")
        self.setMinimumWidth(340)
        self.setAttribute(Qt.WA_StyledBackground)
        self._build_ui()

    def _build_ui(self):
        try:
            row = get_inventory_item(self.item_id)
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
            self.reject()
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(row["item_name"])
        title.setObjectName("login_title")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Current Qty: {row['quantity']}"))

        form = QFormLayout()
        self.remove_qty = QSpinBox()
        self.remove_qty.setRange(1, max(row["quantity"], 1))
        self.remove_qty.setValue(1)
        form.addRow("Remove Quantity:", self.remove_qty)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        set_button_kind(btn_cancel, "outline")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Stock Out")
        set_button_kind(btn_ok, "danger")
        btn_ok.setEnabled(row["quantity"] > 0)
        btn_ok.clicked.connect(self._stock_out)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _stock_out(self):
        try:
            stock_out_inventory_item(self.item_id, self.remove_qty.value())
            info_dialog(self, "Success", f"Removed {self.remove_qty.value()} units.")
            self.accept()
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
