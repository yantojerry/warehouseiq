from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.components import confirm_dialog, error_dialog, info_dialog, warning_dialog
from backend.infrastructure.api_client import (
    ApiError,
    create_permission,
    create_role,
    delete_permission,
    get_role_permissions,
    list_roles,
    update_permission,
    update_role_permissions,
)
from ui.styles import COLORS, set_button_kind


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

        new_role = QPushButton("Add a new role")
        new_role.setMinimumHeight(34)
        set_button_kind(new_role, "outline")
        new_role.clicked.connect(self.add_role)
        header.addWidget(new_role)

        self.add_task_combo = QComboBox()
        self.add_task_combo.setMinimumWidth(190)
        self.add_task_combo.setFixedHeight(36)
        self.add_task_combo.addItem("Add New Task", None)
        self.add_task_combo.addItem("Custom Task", "")
        for module in MODULE_KEYS:
            if module:
                self.add_task_combo.addItem(f"{module.replace('_', ' ').title()} Task", module)
        self.add_task_combo.activated.connect(self._add_task_from_dropdown)
        header.addWidget(self.add_task_combo)

        root.addLayout(header)

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
        self.save_permissions_btn = QPushButton("Save Permissions")
        self.save_permissions_btn.setMinimumHeight(32)
        set_button_kind(self.save_permissions_btn, "teal")
        self.save_permissions_btn.clicked.connect(self.save_permissions)
        list_header_layout.addWidget(self.save_permissions_btn)
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
        root.addWidget(left_card, 1)

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
        self.permission_layout.addWidget(self._permission_header())
        for category, rows in grouped.items():
            self.permission_layout.addWidget(self._separator())
            header = QLabel(category.upper())
            header.setObjectName("section_label")
            header.setStyleSheet("color: #94a3b8; background: transparent; font-size: 11px; font-weight: 800; letter-spacing: 0.6px;")
            self.permission_layout.addWidget(header)
            for permission in rows:
                self.permission_layout.addWidget(self._permission_row(permission, disabled=is_super_admin_role))
        self.permission_layout.addStretch()

    def _permission_header(self):
        row = QFrame()
        row.setObjectName("role_tasks_header")
        row.setFixedHeight(30)
        layout = QGridLayout(row)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setHorizontalSpacing(12)
        layout.setColumnStretch(0, 1)
        layout.setColumnMinimumWidth(1, 150)
        layout.setColumnMinimumWidth(2, 164)

        for text, col, align in [
            ("TASK", 0, Qt.AlignLeft | Qt.AlignVCenter),
            ("MODULE", 1, Qt.AlignLeft | Qt.AlignVCenter),
            ("ACTIONS", 2, Qt.AlignRight | Qt.AlignVCenter),
        ]:
            label = QLabel(text)
            label.setObjectName("role_tasks_column_label")
            label.setAlignment(align)
            layout.addWidget(label, 0, col)
        return row

    def _permission_row(self, permission, disabled=False):
        row = QFrame()
        row.setObjectName("role_task_row")
        row.setMinimumHeight(62)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QGridLayout(row)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(2)
        layout.setColumnStretch(0, 1)
        layout.setColumnMinimumWidth(1, 150)
        layout.setColumnMinimumWidth(2, 164)

        task_cell = QWidget()
        task_cell.setObjectName("transparent_cell")
        task_layout = QHBoxLayout(task_cell)
        task_layout.setContentsMargins(0, 0, 0, 0)
        task_layout.setSpacing(10)

        check = QCheckBox()
        check.setFixedWidth(22)
        check.setStyleSheet(
            "QCheckBox {"
            f" color: {COLORS['text']};"
            " background: transparent;"
            " spacing: 8px;"
            "}"
            "QCheckBox::indicator {"
            " width: 16px;"
            " height: 16px;"
            " border-radius: 3px;"
            f" border: 1px solid {COLORS['text_3']};"
            f" background-color: {COLORS['white']};"
            "}"
            "QCheckBox::indicator:checked {"
            f" background-color: {COLORS['teal']};"
            f" border: 1px solid {COLORS['teal']};"
            "}"
            "QCheckBox::indicator:disabled {"
            f" border: 1px solid {COLORS['border_2']};"
            f" background-color: {COLORS['surface_2']};"
            "}"
        )
        check.setChecked(bool(permission.get("is_enabled")))
        check.setEnabled(not disabled)
        self._checks[permission["id"]] = check

        task_text = QVBoxLayout()
        task_text.setContentsMargins(0, 0, 0, 0)
        task_text.setSpacing(1)
        label = QLabel(permission.get("label") or permission.get("permission_key") or "Untitled task")
        label.setObjectName("role_task_label")
        label.setWordWrap(True)
        key = QLabel(permission.get("permission_key") or "-")
        key.setObjectName("role_task_key")
        key.setWordWrap(True)
        task_text.addWidget(label)
        task_text.addWidget(key)

        task_layout.addWidget(check, 0, Qt.AlignVCenter)
        task_layout.addLayout(task_text, 1)
        layout.addWidget(task_cell, 0, 0, Qt.AlignVCenter)

        module = QLabel(permission.get("module_key") or "-")
        module.setObjectName("role_task_meta")
        module.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        module.setWordWrap(True)
        layout.addWidget(module, 0, 1, Qt.AlignVCenter)

        actions = QWidget()
        actions.setObjectName("transparent_cell")
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        action_layout.addStretch()

        edit = QPushButton("Edit")
        edit.setFixedSize(68, 30)
        set_button_kind(edit, "outline")
        edit.clicked.connect(lambda checked=False, data=permission: self.edit_task(data))
        action_layout.addWidget(edit)

        delete = QPushButton("Delete")
        delete.setFixedSize(78, 30)
        set_button_kind(delete, "danger")
        delete.setEnabled(not permission.get("is_system"))
        delete.clicked.connect(lambda checked=False, data=permission: self.delete_task(data))
        action_layout.addWidget(delete)
        layout.addWidget(actions, 0, 2, Qt.AlignVCenter)
        return row

    def edit_task(self, permission):
        dialog = RoleTaskDialog(
            self,
            categories=self._visible_categories(),
            modules=self._visible_modules(),
            permission=permission,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        payload = dialog.payload()
        if not confirm_dialog(
            self,
            "Confirm Task Change",
            f"Do you want to update this task?\n\n{payload['label']}",
            "Save Task",
        ):
            return
        try:
            saved = update_permission(permission["id"], payload)
            info_dialog(self, "Task Saved", f"{saved.get('label')} was updated.")
            self.load_selected_role()
        except ApiError as exc:
            error_dialog(self, "Task", str(exc))

    def _add_task_from_dropdown(self, index):
        module_key = self.add_task_combo.itemData(index)
        if module_key is None:
            return
        self.add_task(module_key)
        self.add_task_combo.setCurrentIndex(0)

    def add_task(self, default_module=None):
        dialog = RoleTaskDialog(
            self,
            categories=self._visible_categories(),
            modules=self._visible_modules(),
            default_module=default_module,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        payload = dialog.payload()
        if not confirm_dialog(
            self,
            "Confirm Task Change",
            f"Do you want to add this task?\n\n{payload['label']}",
            "Save Task",
        ):
            return
        try:
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
        role_name = self.current_role_payload.get("name", "this role")
        if not confirm_dialog(
            self,
            "Confirm Permission Changes",
            f"Save task access changes for {role_name}?",
            "Save Permissions",
        ):
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
        dialog = RoleDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        name = dialog.role_name()
        try:
            role = create_role({"name": name, "description": f"{name} role"})
            self.load_roles()
            index = self.role_combo.findData(role.get("id"))
            if index >= 0:
                self.role_combo.setCurrentIndex(index)
        except ApiError as exc:
            error_dialog(self, "Role", str(exc))

    def _visible_categories(self):
        categories = sorted(
            {
                (permission.get("category") or "General").strip()
                for permission in self.current_permissions
                if (permission.get("category") or "General").strip()
            }
        )
        return categories or ["General"]

    def _visible_modules(self):
        modules = []
        seen = set()
        for module in MODULE_KEYS:
            key = (module or "").strip()
            if key not in seen:
                modules.append(key)
                seen.add(key)
        for permission in self.current_permissions:
            key = (permission.get("module_key") or "").strip()
            if key and key not in seen:
                modules.append(key)
                seen.add(key)
        return modules

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


class RoleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add a new role")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("Add a new role")
        title.setObjectName("card_title")
        layout.addWidget(title)

        self.name_input = QLineEdit()
        self.name_input.setMinimumHeight(36)
        self._add_field(layout, "Name of the role", self.name_input)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        set_button_kind(cancel, "outline")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save Role")
        set_button_kind(save, "teal")
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def accept(self):
        if not self.role_name():
            warning_dialog(self, "Validation", "Name of the role is required.")
            return
        super().accept()

    def role_name(self):
        return self.name_input.text().strip()

    def _add_field(self, layout, label, field):
        field_layout = QVBoxLayout()
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)
        field_layout.addWidget(RoleTaskManagementPage._form_label(label))
        field_layout.addWidget(field)
        layout.addLayout(field_layout)


class RoleTaskDialog(QDialog):
    def __init__(self, parent=None, categories=None, modules=None, permission=None, default_module=None):
        super().__init__(parent)
        self.permission = permission or {}
        self.setWindowTitle("Add a new task" if not permission else "Edit Task")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("Add a new task" if not permission else "Edit Task")
        title.setObjectName("card_title")
        layout.addWidget(title)

        self.label_input = QLineEdit()
        self.label_input.setMinimumHeight(36)
        self.label_input.setText(self.permission.get("label") or "")
        self._add_field(layout, "Label", self.label_input)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setMinimumHeight(36)
        self.category_combo.addItems(categories or ["General"])
        self.category_combo.setCurrentText(self.permission.get("category") or "General")
        self._add_field(layout, "Category", self.category_combo)

        self.key_input = QLineEdit()
        self.key_input.setMinimumHeight(36)
        self.key_input.setPlaceholderText("Example: orders approve")
        self.key_input.setText(self.permission.get("permission_key") or "")
        self.key_input.setEnabled(not self.permission.get("is_system"))
        self._add_field(layout, "Permission key", self.key_input)

        self.module_combo = QComboBox()
        self.module_combo.setEditable(True)
        self.module_combo.setMinimumHeight(36)
        self.module_combo.addItems(modules or MODULE_KEYS)
        module_key = self.permission.get("module_key") or default_module or ""
        if self.module_combo.findText(module_key) == -1:
            self.module_combo.addItem(module_key)
        self.module_combo.setCurrentText(module_key)
        self._add_field(layout, "Module", self.module_combo)

        add_module = QPushButton("Add another module")
        set_button_kind(add_module, "outline")
        add_module.clicked.connect(self.add_module)
        layout.addWidget(add_module)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        set_button_kind(cancel, "outline")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save Task")
        set_button_kind(save, "teal")
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def accept(self):
        if not self.label_input.text().strip():
            warning_dialog(self, "Validation", "Task label is required.")
            return
        if not self.key_input.text().strip():
            warning_dialog(self, "Validation", "Permission key is required.")
            return
        if len(self.key_input.text().strip().split()) > 3:
            warning_dialog(self, "Validation", "Permission key should be 1 to 3 words.")
            return
        super().accept()

    def add_module(self):
        dialog = ModuleDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        module_name = dialog.module_name()
        if self.module_combo.findText(module_name) == -1:
            self.module_combo.addItem(module_name)
        self.module_combo.setCurrentText(module_name)

    def payload(self):
        payload = {
            "label": self.label_input.text().strip(),
            "category": self.category_combo.currentText().strip() or "General",
            "module_key": self.module_combo.currentText().strip() or None,
            "description": None,
        }
        if not self.permission.get("is_system"):
            payload["permission_key"] = self._permission_key()
        return payload

    def _permission_key(self):
        words = [
            "".join(ch for ch in word.lower() if ch.isalnum() or ch in "_.-").strip("_.-")
            for word in self.key_input.text().strip().split()
        ]
        return ".".join(word for word in words if word)

    def _add_field(self, layout, label, field):
        field_layout = QVBoxLayout()
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)
        field_layout.addWidget(RoleTaskManagementPage._form_label(label))
        field_layout.addWidget(field)
        layout.addLayout(field_layout)


class ModuleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add another module")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("Add another module")
        title.setObjectName("card_title")
        layout.addWidget(title)

        self.module_input = QLineEdit()
        self.module_input.setMinimumHeight(36)
        self._add_field(layout, "Module name", self.module_input)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        set_button_kind(cancel, "outline")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Add Module")
        set_button_kind(save, "teal")
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def accept(self):
        if not self.module_name():
            warning_dialog(self, "Validation", "Module name is required.")
            return
        super().accept()

    def module_name(self):
        return self.module_input.text().strip()

    def _add_field(self, layout, label, field):
        field_layout = QVBoxLayout()
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)
        field_layout.addWidget(RoleTaskManagementPage._form_label(label))
        field_layout.addWidget(field)
        layout.addLayout(field_layout)
