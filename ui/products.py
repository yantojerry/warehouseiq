import base64
import os

from PyQt5.QtCore import Qt
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
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components import confirm_dialog, error_dialog, warning_dialog
from backend.infrastructure.api_client import (
    ApiError,
    create_inventory_item,
    delete_inventory_item,
    get_inventory_item,
    list_inventory,
    update_inventory_item,
)
from backend.core.helpers import format_currency
from ui.styles import (
    COLORS,
    configure_table,
    repolish,
    set_button_kind,
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


class ProductsPage(QWidget):
    def __init__(self, permissions=None):
        super().__init__()
        self.permissions = set(permissions or ())
        self.setObjectName("content_area")
        self.selected_category = "All Categories"
        self._view_mode = "list"
        self._build_ui()
        self._refresh_category_options()
        self.load_products()

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
        title_block.setSpacing(3)
        title = QLabel("Products")
        title.setObjectName("page_title")
        sub = QLabel("Manage and view all products")
        sub.setObjectName("page_subtitle")
        title_block.addWidget(title)
        title_block.addWidget(sub)
        header.addLayout(title_block)
        header.addStretch()
        page.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)
        page.addLayout(body)

        sidebar = QFrame()
        sidebar.setObjectName("card")
        sidebar.setFixedWidth(200)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 14, 14, 14)
        side_layout.setSpacing(6)

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
            "Price: Low to High",
            "Price: High to Low",
        ])
        self.sort_combo.currentTextChanged.connect(self.load_products)
        side_layout.addWidget(self.sort_combo)

        side_layout.addStretch()
        body.addWidget(sidebar)

        card = QFrame()
        card.setObjectName("card")
        main_layout = QVBoxLayout(card)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        card_header = QFrame()
        card_header.setObjectName("card_header")
        header_layout = QHBoxLayout(card_header)
        header_layout.setContentsMargins(18, 13, 18, 13)
        header_layout.setSpacing(8)

        card_title = QLabel("Product Catalog")
        card_title.setObjectName("card_title")
        header_layout.addWidget(card_title)
        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search item name or code...")
        self.search_input.setFixedWidth(220)
        self.search_input.textChanged.connect(self.load_products)
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

        if self._can("products.add"):
            btn_add = QPushButton("+ Add Item")
            set_button_kind(btn_add, "teal")
            btn_add.clicked.connect(self.open_add_dialog)
            header_layout.addWidget(btn_add)

        main_layout.addWidget(card_header)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "IMAGE",
            "PRODUCT",
            "CATEGORY",
            "PRICE",
            "ACTION",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 64)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 160)
        configure_table(self.table)
        self.table.setMinimumHeight(430)
        main_layout.addWidget(self.table)

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

    def _set_view(self, mode):
        self._view_mode = mode
        self.table.setVisible(mode == "list")
        self.grid_scroll.setVisible(mode == "grid")
        self.btn_list_view.setObjectName("pill_button_selected" if mode == "list" else "pill_button")
        self.btn_grid_view.setObjectName("pill_button_selected" if mode == "grid" else "pill_button")
        repolish(self.btn_list_view)
        repolish(self.btn_grid_view)
        self.load_products()

    def _set_category(self, category):
        self.selected_category = category or "All Categories"
        self.load_products()

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
        self.load_products()

    def _sort_rows(self, rows):
        sort = self.sort_combo.currentText() if hasattr(self, "sort_combo") else "Name (A-Z)"
        if sort == "Name (A-Z)":
            return sorted(rows, key=lambda row: row["item_name"].lower())
        if sort == "Name (Z-A)":
            return sorted(rows, key=lambda row: row["item_name"].lower(), reverse=True)
        if sort == "Price: Low to High":
            return sorted(rows, key=lambda row: float(row.get("unit_price", 0)))
        if sort == "Price: High to Low":
            return sorted(rows, key=lambda row: float(row.get("unit_price", 0)), reverse=True)
        return rows

    def load_products(self):
        search = self.search_input.text().strip() if hasattr(self, "search_input") else ""
        try:
            rows = list_inventory(search=search or None)
        except ApiError:
            return

        if self.selected_category != "All Categories":
            rows = [row for row in rows if (row.get("category") or "Other") == self.selected_category]

        rows = self._sort_rows(rows)

        if self._view_mode == "list":
            self._load_list_view(rows)
        else:
            self._load_grid_view(rows)

    def _load_list_view(self, rows):
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            item_id = row["id"]
            self.table.setCellWidget(row_index, 0, self._image_label(row, 52, 44, 44, 36))

            values = [
                row["item_name"],
                row.get("category") or "Other",
                format_currency(row.get("unit_price") or 0),
            ]
            for col, value in enumerate(values, start=1):
                mono = col == 3
                bold = col in {1, 3}
                color = COLORS["navy"] if col == 1 else None
                self.table.setItem(row_index, col, table_item(value, mono=mono, bold=bold, color=color))

            self.table.setCellWidget(row_index, 4, self._make_action_buttons(item_id, row["item_name"]))
            self.table.setRowHeight(row_index, 52)

    def _load_grid_view(self, rows):
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        cols = 4
        for index, row in enumerate(rows):
            self.grid_layout.addWidget(self._make_grid_card(row), index // cols, index % cols)

        remainder = len(rows) % cols
        if remainder:
            for index in range(cols - remainder):
                spacer = QWidget()
                self.grid_layout.addWidget(spacer, len(rows) // cols, remainder + index)

    def _make_grid_card(self, row):
        item_id = row["id"]
        card = QFrame()
        card.setObjectName("product_card")
        card.setFixedSize(200, 252)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        layout.addWidget(self._image_label(row, None, 100, 180, 95))

        name = QLabel(row["item_name"])
        name.setObjectName("card_title")
        name.setWordWrap(True)
        name.setMinimumHeight(34)
        name.setMaximumHeight(42)
        layout.addWidget(name)

        category = QLabel(row.get("category") or "Other")
        category.setObjectName("stat_label")
        layout.addWidget(category)

        price = QLabel(format_currency(row.get("unit_price") or 0))
        price.setStyleSheet(f"color: {COLORS['text']}; font-weight: 700; font-size: 13px; background: transparent;")
        layout.addWidget(price)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        if self._can("products.edit"):
            btn_edit = QPushButton("Edit")
            btn_edit.setFixedSize(82, 30)
            set_button_kind(btn_edit, "outline")
            btn_edit.clicked.connect(lambda _, rid=item_id: self.open_edit_dialog(rid))
            btn_row.addWidget(btn_edit, 1)

        if self._can("products.delete"):
            btn_del = QPushButton("Delete")
            btn_del.setFixedSize(82, 30)
            set_button_kind(btn_del, "danger")
            btn_del.clicked.connect(lambda _, rid=item_id, name=row["item_name"]: self._confirm_delete(rid, name))
            btn_row.addWidget(btn_del, 1)

        if btn_row.count() == 0:
            empty = QLabel("-")
            empty.setAlignment(Qt.AlignCenter)
            btn_row.addWidget(empty)
        btn_row.setAlignment(Qt.AlignCenter)
        layout.addLayout(btn_row)
        return card

    def _image_label(self, row, width, height, pix_width, pix_height):
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        if width is not None:
            label.setFixedSize(width, height)
        else:
            label.setFixedHeight(height)
        label.setStyleSheet(f"font-size:11px; background:{COLORS['surface']}; border-radius:8px; color:{COLORS['muted']};")

        img_data = row.get("image_data")
        if img_data:
            try:
                pix = QPixmap()
                pix.loadFromData(base64.b64decode(img_data))
                label.setPixmap(pix.scaled(pix_width, pix_height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                label.setStyleSheet(f"background:{COLORS['surface']}; border-radius:8px;")
                label.setCursor(Qt.PointingHandCursor)
                label.setToolTip("Click to view image")
                label.mousePressEvent = lambda event, data=row: self.open_image_preview(data)
            except Exception:
                label.setText("No image")
        else:
            label.setText("No image")
        return label

    def _make_action_buttons(self, item_id, name):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        if self._can("products.edit"):
            btn_edit = QPushButton("Edit")
            btn_edit.setFixedSize(64, 30)
            set_button_kind(btn_edit, "outline")
            btn_edit.clicked.connect(lambda _, rid=item_id: self.open_edit_dialog(rid))
            layout.addWidget(btn_edit)

        if self._can("products.delete"):
            btn_del = QPushButton("Delete")
            btn_del.setFixedSize(76, 30)
            set_button_kind(btn_del, "danger")
            btn_del.clicked.connect(lambda _, rid=item_id, item_name=name: self._confirm_delete(rid, item_name))
            layout.addWidget(btn_del)

        if layout.count() == 0:
            empty = QLabel("-")
            empty.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty)
        layout.setAlignment(Qt.AlignCenter)
        return widget

    def open_image_preview(self, row):
        dialog = ProductImageDialog(self, row)
        dialog.exec_()

    def _confirm_delete(self, item_id, name):
        item_label = f'"{name}"' if name else "this product"
        if confirm_dialog(self, "Delete Product", f"Deactivate {item_label}? It will remain in the audit trail."):
            try:
                delete_inventory_item(item_id)
                self._reload_all()
            except ApiError as exc:
                error_dialog(self, "Error", str(exc))

    def open_add_dialog(self):
        dialog = ProductDialog(self)
        if dialog.exec_():
            self._reload_all()

    def open_edit_dialog(self, item_id):
        dialog = ProductDialog(self, item_id=item_id)
        if dialog.exec_():
            self._reload_all()


class ProductImageDialog(QDialog):
    def __init__(self, parent, row):
        super().__init__(parent)
        self.row = row
        self.setWindowTitle(row.get("item_name") or "Product Image")
        self.setMinimumSize(560, 460)
        self.setAttribute(Qt.WA_StyledBackground)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(self.row.get("item_name") or "Product Image")
        title.setObjectName("login_title")
        title.setWordWrap(True)
        layout.addWidget(title)

        meta = QLabel(self.row.get("category") or "Product Catalog")
        meta.setObjectName("login_subtitle")
        layout.addWidget(meta)

        image_card = QFrame()
        image_card.setObjectName("card")
        image_layout = QVBoxLayout(image_card)
        image_layout.setContentsMargins(14, 14, 14, 14)

        image_label = QLabel("No image")
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setMinimumSize(500, 320)
        image_label.setStyleSheet(f"background:{COLORS['surface']}; border-radius:8px; color:{COLORS['muted']};")
        img_data = self.row.get("image_data")
        if img_data:
            try:
                pix = QPixmap()
                pix.loadFromData(base64.b64decode(img_data))
                image_label.setPixmap(pix.scaled(500, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                image_label.setStyleSheet(f"background:{COLORS['surface']}; border-radius:8px;")
            except Exception:
                pass
        image_layout.addWidget(image_label)
        layout.addWidget(image_card, 1)

        btns = QHBoxLayout()
        btns.addStretch()
        close = QPushButton("Close")
        set_button_kind(close, "outline")
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        layout.addLayout(btns)


class ProductDialog(QDialog):
    def __init__(self, parent, item_id=None):
        super().__init__(parent)
        self.item_id = item_id
        self._image_b64 = None
        self._existing_row = None
        self.setWindowTitle("Edit Product" if item_id else "Add Product")
        self.setMinimumWidth(480)
        self.setAttribute(Qt.WA_StyledBackground)
        self._build_ui()
        if item_id:
            self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Edit Product" if self.item_id else "Add Product")
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
        self.btn_clear = QPushButton("Remove")
        set_button_kind(self.btn_clear, "danger")
        self.btn_clear.clicked.connect(self._clear_image)
        self.btn_clear.setVisible(False)
        img_hint = QLabel("PNG, JPG or JPEG - max 2MB")
        img_hint.setObjectName("stat_label")
        img_btn_col.addWidget(btn_pick)
        img_btn_col.addWidget(self.btn_clear)
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
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 999999)
        self.price_input.setPrefix("PHP ")

        form.addRow("Item Code *", self.code_input)
        form.addRow("Item Name *", self.name_input)
        form.addRow("Category", self.cat_input)
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
        with open(path, "rb") as file:
            self._image_b64 = base64.b64encode(file.read()).decode("utf-8")
        pix = QPixmap(path).scaled(80, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img_preview.setPixmap(pix)
        self.img_preview.setStyleSheet(f"background:{COLORS['surface']}; border-radius:8px;")
        self.btn_clear.setVisible(True)

    def _clear_image(self):
        self._image_b64 = None
        self.img_preview.clear()
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            f"background:{COLORS['surface']}; border-radius:8px; color:{COLORS['muted']}; font-size:11px;"
        )
        self.btn_clear.setVisible(False)

    def _load_data(self):
        try:
            row = get_inventory_item(self.item_id)
        except ApiError as exc:
            error_dialog(self, "Error", str(exc))
            return
        if not row:
            return

        self._existing_row = row
        self.code_input.setText(row["item_code"])
        self.name_input.setText(row["item_name"])
        category = (row["category"] or "").strip()
        if category and self.cat_input.findText(category) == -1:
            self.cat_input.addItem(category)
        self.cat_input.setCurrentText(category)
        self.price_input.setValue(row["unit_price"])

        img_data = row.get("image_data")
        if img_data:
            self._image_b64 = img_data
            pix = QPixmap()
            try:
                pix.loadFromData(base64.b64decode(img_data))
                self.img_preview.setPixmap(pix.scaled(80, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.img_preview.setStyleSheet(f"background:{COLORS['surface']}; border-radius:8px;")
                self.btn_clear.setVisible(True)
            except Exception:
                pass

    def _preserved_stock_fields(self):
        row = self._existing_row or {}
        return {
            "floor": int(row.get("floor") or 1),
            "quantity": int(row.get("quantity") or 0),
            "low_stock_threshold": int(row.get("low_stock_threshold") or 5),
        }

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
            "unit_price": self.price_input.value(),
            **self._preserved_stock_fields(),
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