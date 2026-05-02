from dataclasses import dataclass

from utils.roles import (
    ROLE_ADMIN,
    ROLE_BOOKKEEPER,
    ROLE_CASHIER,
    ROLE_SUPER_ADMIN,
    ROLE_WAREHOUSEMAN,
)


@dataclass(frozen=True)
class PermissionSpec:
    key: str
    label: str
    category: str
    module_key: str | None = None
    description: str = ""
    default_roles: tuple[str, ...] = ()
    sort_order: int = 0
    is_system: int = 1


PERMISSIONS = (
    PermissionSpec("dashboard.view", "View Dashboard", "Dashboard", "dashboard", default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN, ROLE_BOOKKEEPER, ROLE_CASHIER), sort_order=10),
    PermissionSpec("settings.view", "View Settings", "System", "settings", default_roles=(ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_WAREHOUSEMAN, ROLE_BOOKKEEPER, ROLE_CASHIER), sort_order=20),
    PermissionSpec("settings.manage", "Manage Settings", "System", "settings", default_roles=(ROLE_SUPER_ADMIN,), sort_order=21),
    PermissionSpec("users.view", "Manage Users", "User Management", "users", default_roles=(ROLE_SUPER_ADMIN, ROLE_ADMIN), sort_order=30),
    PermissionSpec("users.add", "Add User", "User Management", "users", default_roles=(ROLE_SUPER_ADMIN, ROLE_ADMIN), sort_order=31),
    PermissionSpec("users.add_admin", "Add Admin", "User Management", "users", default_roles=(ROLE_SUPER_ADMIN, ROLE_ADMIN), sort_order=32),
    PermissionSpec("users.edit", "Edit Users", "User Management", "users", default_roles=(ROLE_SUPER_ADMIN,), sort_order=33),
    PermissionSpec("users.reset", "Reset User Passwords", "User Management", "users", default_roles=(ROLE_SUPER_ADMIN,), sort_order=34),
    PermissionSpec("roles.manage", "Manage Roles", "Super Admin", "role_tasks", default_roles=(ROLE_SUPER_ADMIN,), sort_order=40),
    PermissionSpec("permissions.manage", "Manage Permissions", "Super Admin", "role_tasks", default_roles=(ROLE_SUPER_ADMIN,), sort_order=41),
    PermissionSpec("tasks.assign", "Assign Tasks", "Super Admin", "role_tasks", default_roles=(ROLE_SUPER_ADMIN,), sort_order=42),
    PermissionSpec("products.view", "View Products", "Warehouse", "products", default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN, ROLE_CASHIER), sort_order=50),
    PermissionSpec("products.add", "Add Products", "Warehouse", "products", default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN), sort_order=51),
    PermissionSpec("products.edit", "Edit Products", "Warehouse", "products", default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN), sort_order=52),
    PermissionSpec("products.delete", "Delete Products", "Warehouse", "products", default_roles=(ROLE_SUPER_ADMIN,), sort_order=53),
    PermissionSpec("inventory.view", "View Inventory", "Warehouse", "inventory", default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN), sort_order=60),
    PermissionSpec("inventory.add", "Add Inventory Items", "Warehouse", "inventory", default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN), sort_order=61),
    PermissionSpec("inventory.edit", "Edit Inventory Items", "Warehouse", "inventory", default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN), sort_order=62),
    PermissionSpec("inventory.delete", "Delete Inventory Items", "Warehouse", "inventory", default_roles=(ROLE_SUPER_ADMIN,), sort_order=63),
    PermissionSpec("inventory.update_stock", "Update Stock", "Warehouse", "inventory", default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN), sort_order=64),
    PermissionSpec("suppliers.view", "View Suppliers", "Warehouse", None, default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN), sort_order=65),
    PermissionSpec("dispatch.view", "View Dispatch Queue", "Warehouse", "dispatch", default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN), sort_order=70),
    PermissionSpec("dispatch.update", "Update Dispatch Status", "Warehouse", "dispatch", default_roles=(ROLE_SUPER_ADMIN, ROLE_WAREHOUSEMAN), sort_order=71),
    PermissionSpec("orders.view", "View Customer Orders", "Cashier", "orders", default_roles=(ROLE_SUPER_ADMIN, ROLE_CASHIER), sort_order=80),
    PermissionSpec("orders.create", "Create Customer Orders", "Cashier", "orders", default_roles=(ROLE_SUPER_ADMIN, ROLE_CASHIER), sort_order=81),
    PermissionSpec("orders.update", "Update Customer Orders", "Cashier", "orders", default_roles=(ROLE_SUPER_ADMIN, ROLE_CASHIER, ROLE_WAREHOUSEMAN), sort_order=82),
    PermissionSpec("pos.create_sale", "Create Sales Transaction", "Cashier", "pos", default_roles=(ROLE_SUPER_ADMIN, ROLE_CASHIER), sort_order=90),
    PermissionSpec("invoices.view", "View Invoices", "Finance", "invoices", default_roles=(ROLE_SUPER_ADMIN, ROLE_BOOKKEEPER, ROLE_CASHIER), sort_order=100),
    PermissionSpec("invoices.create", "Create Invoices", "Finance", "invoices", default_roles=(ROLE_SUPER_ADMIN, ROLE_BOOKKEEPER, ROLE_CASHIER), sort_order=101),
    PermissionSpec("invoices.print", "Print Receipt", "Finance", "invoices", default_roles=(ROLE_SUPER_ADMIN, ROLE_BOOKKEEPER, ROLE_CASHIER), sort_order=102),
    PermissionSpec("invoices.cancel", "Cancel Invoices", "Finance", "invoices", default_roles=(ROLE_SUPER_ADMIN,), sort_order=103),
    PermissionSpec("payments.view", "View Payments", "Bookkeeping", "payments", default_roles=(ROLE_SUPER_ADMIN, ROLE_BOOKKEEPER), sort_order=110),
    PermissionSpec("payments.manage", "Manage Payments", "Bookkeeping", "payments", default_roles=(ROLE_SUPER_ADMIN, ROLE_BOOKKEEPER), sort_order=111),
    PermissionSpec("customers.view", "View Customers", "Cashier", "customers", default_roles=(ROLE_SUPER_ADMIN, ROLE_CASHIER), sort_order=120),
    PermissionSpec("customers.manage", "Manage Customers", "Cashier", "customers", default_roles=(ROLE_SUPER_ADMIN, ROLE_CASHIER), sort_order=121),
    PermissionSpec("balance.view", "View Expenses", "Bookkeeping", "balance", default_roles=(ROLE_SUPER_ADMIN, ROLE_BOOKKEEPER), sort_order=130),
    PermissionSpec("reports.view", "View Sales Reports", "Bookkeeping", "reports", default_roles=(ROLE_SUPER_ADMIN, ROLE_BOOKKEEPER), sort_order=140),
    PermissionSpec("reports.financial.generate", "Generate Financial Reports", "Bookkeeping", "reports", default_roles=(ROLE_SUPER_ADMIN, ROLE_BOOKKEEPER), sort_order=141),
)

PERMISSION_BY_KEY = {permission.key: permission for permission in PERMISSIONS}


def permission_keys_for_module(module_key):
    return tuple(permission.key for permission in PERMISSIONS if permission.module_key == module_key)
