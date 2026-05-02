from dataclasses import dataclass

from ui.customers import CustomersPage
from ui.balance_sheet import BalanceSheetPage
from ui.dashboard import DashboardPage
from ui.dispatch import DispatchPage
from ui.inventory import InventoryPage
from ui.invoices import InvoicesPage
from ui.orders import OrdersPage
from ui.payments import PaymentsPage
from ui.pos import PosPage
from ui.products import ProductsPage
from ui.reports import ReportsPage
from ui.role_tasks import RoleTaskManagementPage
from ui.settings import SettingsPage
from ui.users import UserManagementPage
from utils.roles import (
    ROLE_ADMIN,
    ROLE_BOOKKEEPER,
    ROLE_CASHIER,
    ROLE_SUPER_ADMIN,
    ROLE_WAREHOUSEMAN,
    canonical_role,
    is_super_admin,
)


@dataclass(frozen=True)
class ModuleSpec:
    key: str
    label: str
    group: str
    icon: str
    page_class: object
    permissions: tuple[str, ...]


MODULES = [
    ModuleSpec("dashboard", "Dashboard", "Overview", "fa5s.chart-line", DashboardPage, ("dashboard.view",)),
    ModuleSpec("pos", "POS", "Sales", "fa5s.cash-register", PosPage, ("pos.create_sale",)),
    ModuleSpec("orders", "Orders", "Sales", "fa5s.clipboard-list", OrdersPage, ("orders.view", "orders.create")),
    ModuleSpec("customers", "Customers", "Sales", "fa5s.users", CustomersPage, ("customers.view", "customers.manage")),
    ModuleSpec("dispatch", "Dispatch", "Warehouse", "fa5s.truck-loading", DispatchPage, ("dispatch.view", "dispatch.update")),
    ModuleSpec("inventory", "Inventory", "Warehouse", "fa5s.boxes", InventoryPage, ("inventory.view", "inventory.add", "inventory.edit", "inventory.update_stock")),
    ModuleSpec("products", "Products", "Warehouse", "fa5s.tags", ProductsPage, ("products.view", "products.add", "products.edit")),
    ModuleSpec("invoices", "Invoices", "Finance", "fa5s.file-invoice", InvoicesPage, ("invoices.view", "invoices.create", "invoices.print")),
    ModuleSpec("payments", "Payments", "Finance", "fa5s.money-check-alt", PaymentsPage, ("payments.view", "payments.manage")),
    ModuleSpec("balance", "Balance Sheet", "Finance", "fa5s.balance-scale", BalanceSheetPage, ("balance.view",)),
    ModuleSpec("reports", "Reports", "Finance", "fa5s.chart-pie", ReportsPage, ("reports.view", "reports.financial.generate")),
    ModuleSpec("users", "User Accounts", "Admin", "fa5s.user-shield", UserManagementPage, ("users.view", "users.add", "users.add_admin")),
    ModuleSpec("role_tasks", "Role Tasks", "Super Admin", "fa5s.tasks", RoleTaskManagementPage, ("roles.manage", "permissions.manage", "tasks.assign")),
    ModuleSpec("settings", "Settings", "System", "fa5s.cog", SettingsPage, ("settings.view",)),
]

MODULE_BY_KEY = {module.key: module for module in MODULES}

ROLE_START_PAGE = {
    ROLE_SUPER_ADMIN: "dashboard",
    ROLE_ADMIN: "users",
    ROLE_WAREHOUSEMAN: "dispatch",
    ROLE_BOOKKEEPER: "dashboard",
    ROLE_CASHIER: "pos",
}


def _has_any_permission(role, permission_keys, required):
    role = canonical_role(role)
    if is_super_admin(role):
        return True
    keys = set(permission_keys or ())
    if "settings.view" in required:
        return True
    return any(permission in keys for permission in required)


def allowed_modules(role, permission_keys=None):
    return [module for module in MODULES if _has_any_permission(role, permission_keys, module.permissions)]


def can_access(role, module_key, permission_keys=None):
    module = MODULE_BY_KEY.get(module_key)
    return bool(module and _has_any_permission(role, permission_keys, module.permissions))


def first_accessible_module(role, permission_keys=None):
    preferred = ROLE_START_PAGE.get(canonical_role(role))
    if preferred and can_access(role, preferred, permission_keys):
        return preferred
    modules = allowed_modules(role, permission_keys)
    return modules[0].key if modules else "settings"
