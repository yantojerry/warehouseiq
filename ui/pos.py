import base64

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components import error_dialog, info_dialog, warning_dialog
from utils.api_client import ApiError, checkout_pos, list_inventory
from utils.helpers import format_currency, generate_order_number
from utils.styles import COLORS, make_badge, repolish, set_button_kind


PAYMENT_METHODS = ["Cash", "GCash", "Maya", "Bank Transfer"]


class PosPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("content_area")
        self._cart = {}
        self._selected_category = "All"
        self._payment_method = "Cash"
        self._all_products = []
        self._category_buttons = {}
        self._pay_buttons = {}
        self._build_ui()
        self._load_products()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_products_panel(), 5)
        root.addWidget(self._build_cart_panel(), 4)
        root.addWidget(self._build_summary_panel(), 3)

    # ── LEFT: products ────────────────────────────────────────────────────────

    def _build_products_panel(self):
        panel = QFrame()
        panel.setObjectName("pos_panel_left")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 8, 16)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("Products")
        title.setObjectName("page_title")
        title_row.addWidget(title)
        title_row.addStretch()
        view_all = QPushButton("View all")
        view_all.setObjectName("btn_link")
        view_all.clicked.connect(lambda: self._set_category("All"))
        title_row.addWidget(view_all)
        layout.addLayout(title_row)

        # category scroll
        self._cat_scroll_widget = QWidget()
        self._cat_scroll_widget.setObjectName("page_content")
        cat_row = QHBoxLayout(self._cat_scroll_widget)
        cat_row.setContentsMargins(0, 0, 0, 0)
        cat_row.setSpacing(8)
        self._cat_layout = cat_row

        cat_scroll = QScrollArea()
        cat_scroll.setWidgetResizable(True)
        cat_scroll.setFixedHeight(90)
        cat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        cat_scroll.setFrameShape(QFrame.NoFrame)
        cat_scroll.setObjectName("pos_cat_scroll")
        cat_scroll.setWidget(self._cat_scroll_widget)
        layout.addWidget(cat_scroll)

        # search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search products...")
        self.search_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_input)

        # product grid
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        self._grid_scroll.setObjectName("pos_grid_scroll")

        self._grid_container = QWidget()
        self._grid_container.setObjectName("page_content")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(0, 4, 0, 0)
        self._grid_layout.setSpacing(10)
        self._grid_scroll.setWidget(self._grid_container)
        layout.addWidget(self._grid_scroll, 1)

        return panel

    # ── MIDDLE: cart ──────────────────────────────────────────────────────────

    def _build_cart_panel(self):
        panel = QFrame()
        panel.setObjectName("pos_panel_mid")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 16, 10, 16)
        layout.setSpacing(0)

        header_row = QHBoxLayout()
        cart_title = QLabel("Cart")
        cart_title.setObjectName("page_title")
        header_row.addWidget(cart_title)
        header_row.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("btn_link")
        clear_btn.clicked.connect(self._clear_cart)
        header_row.addWidget(clear_btn)
        layout.addLayout(header_row)
        layout.addSpacing(10)

        # customer name
        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("Customer name (optional)")
        layout.addWidget(self.customer_input)
        layout.addSpacing(8)

        # cart scroll
        self._cart_scroll = QScrollArea()
        self._cart_scroll.setWidgetResizable(True)
        self._cart_scroll.setFrameShape(QFrame.NoFrame)
        self._cart_scroll.setObjectName("pos_cart_scroll")

        self._cart_container = QWidget()
        self._cart_container.setObjectName("page_content")
        self._cart_vbox = QVBoxLayout(self._cart_container)
        self._cart_vbox.setContentsMargins(0, 0, 0, 0)
        self._cart_vbox.setSpacing(6)
        self._cart_vbox.addStretch()
        self._cart_scroll.setWidget(self._cart_container)
        layout.addWidget(self._cart_scroll, 1)

        self._empty_label = QLabel("No items in cart")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setObjectName("pos_empty_label")
        layout.addWidget(self._empty_label)

        # totals
        layout.addWidget(self._h_line())
        totals_grid = QGridLayout()
        totals_grid.setContentsMargins(4, 10, 4, 4)
        totals_grid.setSpacing(6)

        def tot_row(label):
            lbl = QLabel(label)
            lbl.setObjectName("stat_label")
            lbl.setStyleSheet("color: #ffffff; background: transparent;")
            val = QLabel("₱ 0.00")
            val.setObjectName("pos_total_value")
            val.setAlignment(Qt.AlignRight)
            return lbl, val

        sub_lbl, self.lbl_subtotal = tot_row("Subtotal")
        tax_lbl, self.lbl_tax      = tot_row("Tax")
        disc_lbl, self.lbl_disc    = tot_row("Discount")
        totals_grid.addWidget(sub_lbl,           0, 0)
        totals_grid.addWidget(self.lbl_subtotal, 0, 1)
        totals_grid.addWidget(tax_lbl,           1, 0)
        totals_grid.addWidget(self.lbl_tax,      1, 1)
        totals_grid.addWidget(disc_lbl,          2, 0)
        totals_grid.addWidget(self.lbl_disc,     2, 1)
        layout.addLayout(totals_grid)

        layout.addWidget(self._h_line())

        live_row = QHBoxLayout()
        live_lbl = QLabel("Live Total")
        live_lbl.setObjectName("card_title")
        live_lbl.setStyleSheet("color: #ffffff; background: transparent;")
        self.lbl_live = QLabel("₱ 0.00")
        self.lbl_live.setObjectName("pos_live_total")
        self.lbl_live.setAlignment(Qt.AlignRight)
        live_row.addWidget(live_lbl)
        live_row.addStretch()
        live_row.addWidget(self.lbl_live)
        layout.addLayout(live_row)

        return panel

    # ── RIGHT: order summary ──────────────────────────────────────────────────

    def _build_summary_panel(self):
        panel = QFrame()
        panel.setObjectName("pos_panel_right")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Order Summary")
        title.setObjectName("page_title")
        layout.addWidget(title)

        summary_grid = QGridLayout()
        summary_grid.setSpacing(8)

        def s_row(label):
            lbl = QLabel(label)
            lbl.setObjectName("stat_label")
            lbl.setStyleSheet("color: #ffffff; background: transparent;")
            val = QLabel("₱ 0.00")
            val.setObjectName("card_title")
            val.setStyleSheet("color: #ffffff; background: transparent;")
            val.setAlignment(Qt.AlignRight)
            return lbl, val

        s_sub_lbl, self.s_subtotal = s_row("Subtotal")
        s_tax_lbl, self.s_tax      = s_row("Tax")
        s_dis_lbl, self.s_discount = s_row("Discount")
        summary_grid.addWidget(s_sub_lbl,       0, 0)
        summary_grid.addWidget(self.s_subtotal, 0, 1)
        summary_grid.addWidget(s_tax_lbl,       1, 0)
        summary_grid.addWidget(self.s_tax,      1, 1)
        summary_grid.addWidget(s_dis_lbl,       2, 0)
        summary_grid.addWidget(self.s_discount, 2, 1)
        layout.addLayout(summary_grid)

        layout.addWidget(self._h_line())

        pay_title = QLabel("Payment Method")
        pay_title.setObjectName("card_title")
        pay_title.setStyleSheet("color: #ffffff; background: transparent;")
        layout.addWidget(pay_title)

        for method in PAYMENT_METHODS:
            btn = QPushButton(method)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, m=method: self._select_payment(m))
            layout.addWidget(btn)
            self._pay_buttons[method] = btn

        self._select_payment("Cash")

        layout.addWidget(self._h_line())

        tender_lbl = QLabel("Amount Tendered")
        tender_lbl.setObjectName("stat_label")
        tender_lbl.setStyleSheet("color: #ffffff; background: transparent;")
        layout.addWidget(tender_lbl)

        self.tender_input = QLineEdit()
        self.tender_input.setPlaceholderText("₱ 0.00")
        self.tender_input.textChanged.connect(self._update_totals)
        layout.addWidget(self.tender_input)

        self.change_label = QLabel("Change: ₱ 0.00")
        self.change_label.setObjectName("pos_change_label")
        self.change_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.change_label)

        layout.addStretch()

        self.btn_process = QPushButton("Process Order")
        self.btn_process.setFixedHeight(48)
        set_button_kind(self.btn_process, "teal")
        self.btn_process.clicked.connect(self._process_order)
        layout.addWidget(self.btn_process)

        return panel

    # ── products ──────────────────────────────────────────────────────────────

    def _load_products(self):
        try:
            self._all_products = list_inventory()
        except ApiError:
            self._all_products = []
        self._rebuild_categories()
        self._apply_filter()

    def _rebuild_categories(self):
        while self._cat_layout.count():
            item = self._cat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._category_buttons.clear()

        categories = ["All"] + sorted({
            (r.get("category") or "Other") for r in self._all_products
        })
        for cat in categories:
            btn = QPushButton(cat)
            btn.setObjectName("pos_cat_btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(60)
            btn.setFixedWidth(88)
            btn.clicked.connect(lambda _, c=cat: self._set_category(c))
            self._cat_layout.addWidget(btn)
            self._category_buttons[cat] = btn
        self._cat_layout.addStretch()
        self._update_cat_buttons()

    def _set_category(self, category):
        self._selected_category = category
        self._update_cat_buttons()
        self._apply_filter()

    def _update_cat_buttons(self):
        for cat, btn in self._category_buttons.items():
            btn.setObjectName(
                "pos_cat_btn_active" if cat == self._selected_category else "pos_cat_btn"
            )
            repolish(btn)

    def _apply_filter(self):
        search = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        filtered = [
            r for r in self._all_products
            if (self._selected_category == "All" or (r.get("category") or "Other") == self._selected_category)
            and (not search or search in r["item_name"].lower())
            and int(r["quantity"]) > 0
        ]
        self._render_grid(filtered)

    def _render_grid(self, products):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 4
        for idx, row in enumerate(products):
            card = self._make_product_card(row)
            self._grid_layout.addWidget(card, idx // cols, idx % cols)

    def _make_product_card(self, row):
        item_id = row["id"]
        in_cart = item_id in self._cart

        card = QFrame()
        card.setObjectName("product_card_selected" if in_cart else "product_card")
        card.setFixedSize(138, 160)
        card.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # image
        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setFixedHeight(72)
        img_lbl.setStyleSheet(f"background: {COLORS['surface']}; border-radius: 6px;")
        img_data = row.get("image_data")
        if img_data:
            try:
                pix = QPixmap()
                pix.loadFromData(base64.b64decode(img_data))
                img_lbl.setPixmap(pix.scaled(118, 66, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                img_lbl.setStyleSheet(f"background: {COLORS['surface']}; border-radius: 6px;")
            except Exception:
                img_lbl.setText("No image")
                img_lbl.setStyleSheet(f"font-size:11px; background:{COLORS['surface']}; border-radius:6px;")
        else:
            img_lbl.setText("No image")
            img_lbl.setStyleSheet(f"font-size:11px; background:{COLORS['surface']}; border-radius:6px;")
        layout.addWidget(img_lbl)

        # stock badge
        qty = int(row["quantity"])
        stock_badge = QLabel(f"Stock: {qty}")
        stock_badge.setObjectName("badge_teal" if qty > 5 else "badge_amber")
        stock_badge.setAlignment(Qt.AlignCenter)
        stock_badge.setFixedHeight(18)
        layout.addWidget(stock_badge)

        # name
        name_lbl = QLabel(row["item_name"])
        name_lbl.setObjectName("card_title")
        name_lbl.setWordWrap(True)
        name_lbl.setMaximumHeight(34)
        layout.addWidget(name_lbl)

        # price
        price_lbl = QLabel(f"₱{float(row.get('unit_price', 0)):,.0f}")
        price_lbl.setStyleSheet(
            f"color: {COLORS['teal']}; font-weight: 800; font-size: 13px; background: transparent;"
        )
        layout.addWidget(price_lbl)

        card.mousePressEvent = lambda event, r=row: self._add_to_cart(r)
        return card

    # ── cart ──────────────────────────────────────────────────────────────────

    def _add_to_cart(self, row):
        item_id = row["id"]
        max_qty = int(row["quantity"])
        if item_id in self._cart:
            if self._cart[item_id]["qty"] < max_qty:
                self._cart[item_id]["qty"] += 1
        else:
            self._cart[item_id] = {"row": row, "qty": 1}
        self._refresh_cart()
        self._apply_filter()

    def _remove_from_cart(self, item_id):
        self._cart.pop(item_id, None)
        self._refresh_cart()
        self._apply_filter()

    def _set_cart_qty(self, item_id, qty):
        if qty <= 0:
            self._remove_from_cart(item_id)
        else:
            max_qty = int(self._cart[item_id]["row"]["quantity"])
            self._cart[item_id]["qty"] = min(qty, max_qty)
            self._refresh_cart()

    def _clear_cart(self):
        self._cart.clear()
        self._refresh_cart()
        self._apply_filter()

    def _refresh_cart(self):
        while self._cart_vbox.count():
            item = self._cart_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._cart:
            self._empty_label.show()
            self._cart_scroll.hide()
        else:
            self._empty_label.hide()
            self._cart_scroll.show()
            for item_id, entry in self._cart.items():
                self._cart_vbox.addWidget(
                    self._make_cart_row(item_id, entry["row"], entry["qty"])
                )
            self._cart_vbox.addStretch()

        self._update_totals()

    def _make_cart_row(self, item_id, row, qty):
        widget = QFrame()
        widget.setObjectName("pos_cart_row")
        h = QHBoxLayout(widget)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(8)

        # thumbnail
        img_lbl = QLabel()
        img_lbl.setFixedSize(44, 40)
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setStyleSheet(f"background:{COLORS['surface']}; border-radius:6px;")
        img_data = row.get("image_data")
        if img_data:
            try:
                pix = QPixmap()
                pix.loadFromData(base64.b64decode(img_data))
                img_lbl.setPixmap(pix.scaled(40, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                img_lbl.setStyleSheet(f"background:{COLORS['surface']}; border-radius:6px;")
            except Exception:
                img_lbl.setText("No image")
        else:
            img_lbl.setText("No image")
        h.addWidget(img_lbl)

        # info
        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(row["item_name"][:20] + ("…" if len(row["item_name"]) > 20 else ""))
        name.setObjectName("card_title")
        unit_price = QLabel(f"₱{float(row.get('unit_price', 0)):,.2f} each")
        unit_price.setObjectName("stat_label")
        line_total = QLabel(f"₱{float(row.get('unit_price', 0)) * qty:,.2f}")
        line_total.setStyleSheet(f"color:{COLORS['text']}; font-weight:800; font-size:12px; background:transparent;")
        info.addWidget(name)
        info.addWidget(unit_price)
        info.addWidget(line_total)
        h.addLayout(info, 1)

        # qty controls
        qty_row = QHBoxLayout()
        qty_row.setSpacing(4)

        btn_minus = QPushButton("−")
        btn_minus.setObjectName("pos_qty_btn")
        btn_minus.setFixedSize(26, 26)
        btn_minus.clicked.connect(
            lambda _, iid=item_id: self._set_cart_qty(iid, self._cart[iid]["qty"] - 1)
        )

        qty_lbl = QLabel(str(qty))
        qty_lbl.setObjectName("pos_qty_label")
        qty_lbl.setAlignment(Qt.AlignCenter)
        qty_lbl.setFixedWidth(26)

        btn_plus = QPushButton("+")
        btn_plus.setObjectName("pos_qty_btn")
        btn_plus.setFixedSize(26, 26)
        btn_plus.clicked.connect(
            lambda _, iid=item_id: self._set_cart_qty(iid, self._cart[iid]["qty"] + 1)
        )

        btn_del = QPushButton("✕")
        btn_del.setObjectName("pos_del_btn")
        btn_del.setFixedSize(26, 26)
        btn_del.clicked.connect(lambda _, iid=item_id: self._remove_from_cart(iid))

        qty_row.addWidget(btn_minus)
        qty_row.addWidget(qty_lbl)
        qty_row.addWidget(btn_plus)
        qty_row.addWidget(btn_del)
        h.addLayout(qty_row)

        return widget

    # ── totals / payment ──────────────────────────────────────────────────────

    def _update_totals(self):
        subtotal = sum(
            float(e["row"].get("unit_price", 0)) * e["qty"]
            for e in self._cart.values()
        )
        tax = 0.0
        discount = 0.0
        live = subtotal + tax - discount

        try:
            tendered = float(self.tender_input.text().replace(",", "").strip() or 0)
        except ValueError:
            tendered = 0.0
        change = max(0.0, tendered - live)

        fmt = lambda v: f"₱ {v:,.2f}"
        self.lbl_subtotal.setText(fmt(subtotal))
        self.lbl_tax.setText(fmt(tax))
        self.lbl_disc.setText(fmt(discount))
        self.lbl_live.setText(fmt(live))
        self.s_subtotal.setText(fmt(subtotal))
        self.s_tax.setText(fmt(tax))
        self.s_discount.setText(fmt(discount))
        self.change_label.setText(f"Change: {fmt(change)}")

    def _select_payment(self, method):
        self._payment_method = method
        style_map = {
            "Cash":          "btn_navy",
            "GCash":         "pos_gcash",
            "Maya":          "pos_maya",
            "Bank Transfer": "btn_outline",
        }
        for m, btn in self._pay_buttons.items():
            btn.setObjectName(style_map.get(m, "btn_navy") if m == method else "btn_outline")
            repolish(btn)

    # ── process order  ────────────────────────────────────────────────────────

    def _process_order(self):
        if not self._cart:
            warning_dialog(self, "Empty Cart", "Add items to the cart first.")
            return

        items = [
            {
                "item_id": iid,
                "quantity": e["qty"],
                "unit_price": float(e["row"].get("unit_price", 0)),
            }
            for iid, e in self._cart.items()
        ]
        subtotal = sum(i["quantity"] * i["unit_price"] for i in items)
        order_number = generate_order_number()
        customer = self.customer_input.text().strip() if hasattr(self, "customer_input") else "Walk-in"

        payload = {
            "customer_name": customer or "Walk-in",
            "items": items,
            "payment_method": self._payment_method,
            "amount_paid": self._amount_tendered(),
            "created_by": "pos",
            "notes": "Created from POS",
        }

        try:
            result = checkout_pos(payload)
            info_dialog(
                self,
                "Order Placed",
                f"Order {result.get('order_number')} processed via {self._payment_method}.\nInvoice: {result.get('invoice_number')}",
            )
            self._cart.clear()
            self.customer_input.clear()
            self.tender_input.clear()
            self._refresh_cart()
            self._load_products()
        except ApiError as exc:
            message = str(exc)
            if exc.status_code == 409:
                message = f"{message}\n\nUse the same-category substitute suggestions in the product grid, then try again."
            error_dialog(self, "Checkout Blocked", message)

    def _amount_tendered(self):
        try:
            return float(self.tender_input.text().replace(",", "").strip() or 0)
        except ValueError:
            return 0.0

    # ── helper ────────────────────────────────────────────────────────────────

    def _h_line(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("pos_divider")
        return line
