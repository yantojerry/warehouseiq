from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components import confirm_dialog, error_dialog, info_dialog, warning_dialog
from utils.api_client import (
    ApiError,
    create_permission,
    create_role,
    delete_permission,
    get_role_permissions,
    list_roles,
    update_permission,
    update_role_permissions,
)
from utils.styles import make_badge, set_button_kind


MODULE_KEYS = [
    "",
    "dashboard",
    "users",
    "role_tasks",
    "products",
    "inventory",
    "dispatch",
    "orders",
    "pos",
    "invoices",
    "payments",
    "customers",
    "balance",
    "reports",
    "settings",
]


class RoleTaskManagementPage(QWidget):
    def __init__(self, permissions=None, current_role=None):
        super().__init__()
        self.permissions = set(permissions or ())
        self.current_role = current_role
        self.roles = []
        self.current_role_payload = None
        self.current_permissions = []
        self._checks = {}
        self.editing_permission = None
        self.setObjectName("content_area")
        self._build_ui()
        self.load_roles()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Role Tasks")
        title.setObjectName("page_title")
        subtitle = QLabel("Manage task checkboxes and role access")
        subtitle.setObjectName("page_subtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block)
        header.addStretch()

        self.role_combo = QComboBox()
        self.role_combo.setMinimumWidth(240)
        self.role_combo.setFixedHeight(36)
        self.role_combo.currentIndexChanged.connect(self.load_selected_role)
        header.addWidget(self.role_combo)

        new_role = QPushButton("New Role")
        set_button_kind(new_role, "outline")
        new_role.clicked.connect(self.add_role)
        header.addWidget(new_role)

        self.save_permissions_btn = QPushButton("Save Permissions")
        set_button_kind(self.save_permissions_btn, "teal")
        self.save_permissions_btn.clicked.connect(self.save_permissions)
        header.addWidget(self.save_permissions_btn)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)

        left_card = QFrame()
        left_card.setObjectName("card")
        left = QVBoxLayout(left_card)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)

        list_header = QFrame()
        list_header.setObjectName("card_header")
        list_header_layout = QHBoxLayout(list_header)
        list_header_layout.setContentsMargins(18, 13, 18, 13)
        self.role_title = QLabel("Tasks")
        self.role_title.setObjectName("card_title")
        list_header_layout.addWidget(self.role_title)
        self.perm_count_label = QLabel("")
        self.perm_count_label.setObjectName("page_subtitle")
        list_header_layout.addWidget(self.perm_count_label)
        list_header_layout.addStretch()
        left.addWidget(list_header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.permission_container = QWidget()
        self.permission_container.setObjectName("page_content")
        self.permission_container.setMinimumWidth(400)
        self.permission_layout = QVBoxLayout(self.permission_container)
        self.permission_layout.setContentsMargins(18, 14, 18, 18)
        self.permission_layout.setSpacing(8)
        self.scroll.setWidget(self.permission_container)
        left.addWidget(self.scroll, 1)
        body.addWidget(left_card, 2)

        form_card = QFrame()
        form_card.setObjectName("card")
        form = QVBoxLayout(form_card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setSpacing(10)

        form_title = QLabel("Task Details")
        form_title.setObjectName("card_title")
        form.addWidget(form_title)

        self.label_input = self._line(form, "Label")
        self.key_input = self._line(form, "Permission Key")
        self.category_input = QLineEdit()
        self.category_input.setMinimumHeight(34)
        self._add_field(form, "Category", self.category_input)
        self.module_combo = QComboBox()
        self.module_combo.setMinimumHeight(34)
        self.module_combo.setEditable(True)
        self.module_combo.addItems(MODULE_KEYS)
        self._add_field(form, "Module", self.module_combo)

        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(80)
        self._add_field(form, "Description", self.description_input)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        self.new_task_btn = QPushButton("New Task")
        self.new_task_btn.setMinimumHeight(34)
        set_button_kind(self.new_task_btn, "outline")
        self.new_task_btn.clicked.connect(self.clear_form)
        self.save_task_btn = QPushButton("Save Task")
        self.save_task_btn.setMinimumHeight(34)
        set_button_kind(self.save_task_btn, "teal")
        self.save_task_btn.clicked.connect(self.save_task)
        btns.addWidget(self.new_task_btn)
        btns.addWidget(self.save_task_btn)
        form.addLayout(btns)
        form.addStretch()
        body.addWidget(form_card, 1)

    def _line(self, layout, label):
        field = QLineEdit()
        field.setMinimumHeight(34)
        self._add_field(layout, label, field)
        return field

    def _add_field(self, layout, label, field):
        field_layout = QVBoxLayout()
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)
        field_layout.addWidget(self._form_label(label))
        field_layout.addWidget(field)
        layout.addLayout(field_layout)

    @staticmethod
    def _form_label(text):
        label = QLabel(text.upper())
        label.setObjectName("form_label")
        return label

    @staticmethod
    def _separator():
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("line_divider")
        line.setFrameShadow(QFrame.Sunken)
        line.setFixedHeight(1)
        return line

    def load_roles(self):
        try:
            self.roles = list_roles()
        except ApiError as exc:
            error_dialog(self, "Roles", str(exc))
            return
        self.role_combo.blockSignals(True)
        self.role_combo.clear()
        for role in self.roles:
            self.role_combo.addItem(role.get("name") or "-", role.get("id"))
        self.role_combo.blockSignals(False)
        if self.role_combo.count():
            self.load_selected_role()

    def selected_role_id(self):
        return self.role_combo.currentData()

    def load_selected_role(self):
        role_id = self.selected_role_id()
        if role_id is None:
            return
        try:
            payload = get_role_permissions(role_id)
        except ApiError as exc:
            error_dialog(self, "Role Tasks", str(exc))
            return
        self.current_role_payload = payload.get("role") or {}
        self.current_permissions = payload.get("permissions") or []
        self.role_title.setText(f"{self.current_role_payload.get('name', 'Role')} Tasks")
        self.render_permissions()
        self.clear_form()

    def render_permissions(self):
        self._clear_layout(self.permission_layout)
        self._checks.clear()
        grouped = {}
        for permission in self.current_permissions:
            grouped.setdefault(permission.get("category") or "General", []).append(permission)

        total = len(self.current_permissions)
        enabled = sum(1 for p in self.current_permissions if p.get("is_enabled"))
        self.perm_count_label.setText(f"{enabled} of {total} enabled")
        is_super_admin_role = self.current_role_payload.get("name") == "Super Admin"
        self.save_permissions_btn.setEnabled(not is_super_admin_role)
        for category, rows in grouped.items():
            self.permission_layout.addWidget(self._separator())
            header = QLabel(category.upper())
            header.setObjectName("section_label")
            header.setStyleSheet("color: #94a3b8; background: transparent; font-size: 11px; font-weight: 800; letter-spacing: 0.6px;")
            self.permission_layout.addWidget(header)
            for permission in rows:
                self.permission_layout.addWidget(self._permission_row(permission, disabled=is_super_admin_role))
        self.permission_layout.addStretch()

    def _permission_row(self, permission, disabled=False):
        row = QFrame()
        row.setObjectName("card_body")
        row.setMinimumHeight(48)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        check = QCheckBox(permission.get("label") or permission.get("permission_key"))
        check.setMinimumWidth(160)
        check.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        check.setChecked(bool(permission.get("is_enabled")))
        check.setEnabled(not disabled)
        layout.addWidget(check, 2)
        self._checks[permission["id"]] = check

        permission_key = permission.get("permission_key") or "-"
        badge = make_badge(permission_key, "gray")
        badge.setMaximumWidth(160)
        badge.setToolTip(permission_key)
        badge.setText(badge.fontMetrics().elidedText(permission_key, Qt.ElideRight, 150))
        layout.addWidget(badge)

        edit = QPushButton("Edit")
        edit.setFixedSize(60, 28)
        set_button_kind(edit, "outline")
        edit.clicked.connect(lambda checked=False, data=permission: self.edit_task(data))
        layout.addWidget(edit)

        delete = QPushButton("Delete")
        delete.setFixedSize(70, 28)
        set_button_kind(delete, "danger")
        delete.setEnabled(not permission.get("is_system"))
        delete.clicked.connect(lambda checked=False, data=permission: self.delete_task(data))
        layout.addWidget(delete)
        return row

    def edit_task(self, permission):
        self.editing_permission = permission
        self.label_input.setText(permission.get("label") or "")
        self.key_input.setText(permission.get("permission_key") or "")
        self.key_input.setEnabled(not permission.get("is_system"))
        self.category_input.setText(permission.get("category") or "General")
        module_key = permission.get("module_key") or ""
        if self.module_combo.findText(module_key) == -1:
            self.module_combo.addItem(module_key)
        self.module_combo.setCurrentText(module_key)
        self.description_input.setPlainText(permission.get("description") or "")

    def clear_form(self):
        self.editing_permission = None
        self.label_input.clear()
        self.key_input.clear()
        self.key_input.setEnabled(True)
        self.category_input.setText("General")
        self.module_combo.setCurrentText("")
        self.description_input.clear()

    def _form_payload(self):
        label = self.label_input.text().strip()
        if not label:
            warning_dialog(self, "Validation", "Task label is required.")
            return None
        return {
            "label": label,
            "permission_key": self.key_input.text().strip() or None,
            "category": self.category_input.text().strip() or "General",
            "module_key": self.module_combo.currentText().strip() or None,
            "description": self.description_input.toPlainText().strip() or None,
        }

    def save_task(self):
        payload = self._form_payload()
        if not payload:
            return
        try:
            if self.editing_permission:
                permission = update_permission(self.editing_permission["id"], payload)
                info_dialog(self, "Task Saved", f"{permission.get('label')} was updated.")
                self.load_selected_role()
            else:
                permission = create_permission(payload)
                self._enable_new_permission(permission["id"])
                info_dialog(self, "Task Added", f"{permission.get('label')} was added.")
                self.load_selected_role()
        except ApiError as exc:
            error_dialog(self, "Task", str(exc))

    def _enable_new_permission(self, permission_id):
        role_id = self.selected_role_id()
        if role_id is None:
            return
        permissions = self._collect_permission_payload()
        permissions.append({"permission_id": permission_id, "is_enabled": True})
        update_role_permissions(role_id, permissions)

    def delete_task(self, permission):
        if not confirm_dialog(self, "Delete Task", f"Delete {permission.get('label')}?"):
            return
        try:
            delete_permission(permission["id"])
            info_dialog(self, "Task Deleted", "Task deleted.")
            self.load_selected_role()
        except ApiError as exc:
            error_dialog(self, "Task", str(exc))

    def save_permissions(self):
        if not self.selected_role_id():
            return
        if self.current_role_payload.get("name") == "Super Admin":
            warning_dialog(self, "Role Tasks", "Super Admin always has all permissions.")
            return
        try:
            update_role_permissions(self.selected_role_id(), self._collect_permission_payload())
            info_dialog(self, "Role Tasks", "Permissions saved.")
            self.load_selected_role()
        except ApiError as exc:
            error_dialog(self, "Role Tasks", str(exc))

    def _collect_permission_payload(self):
        return [
            {"permission_id": permission_id, "is_enabled": checkbox.isChecked()}
            for permission_id, checkbox in self._checks.items()
        ]

    def add_role(self):
        name, ok = QInputDialog.getText(self, "New Role", "Role name:")
        if not ok or not name.strip():
            return
        try:
            role = create_role({"name": name.strip(), "description": f"{name.strip()} role"})
            self.load_roles()
            index = self.role_combo.findData(role.get("id"))
            if index >= 0:
                self.role_combo.setCurrentIndex(index)
        except ApiError as exc:
            error_dialog(self, "Role", str(exc))

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                RoleTaskManagementPage._clear_layout(child_layout)
