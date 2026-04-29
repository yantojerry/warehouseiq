from dataclasses import dataclass

from ui.customers import CustomersPage
from ui.balance_sheet import BalanceSheetPage
from ui.dashboard import DashboardPage
from ui.dispatch import DispatchPage
from ui.inventory import InventoryPage
from ui.invoices import InvoicesPage
from ui.orders import OrdersPage
from ui.pos import PosPage
from ui.products import ProductsPage
from ui.reports import ReportsPage
from ui.users import UserManagementPage


@dataclass(frozen=True)
class ModuleSpec:
    key: str
    label: str
    group: str
    icon: str
    page_class: object
    roles: tuple


ALL_ROLES = ("Admin", "Sales Staff", "Warehouse Staff", "Bookkeeper")

MODULES = [
    ModuleSpec("dashboard", "Dashboard", "Overview", "fa5s.chart-line", DashboardPage, ALL_ROLES),
    ModuleSpec("pos", "POS", "Sales", "fa5s.cash-register", PosPage, ("Admin", "Sales Staff")),
    ModuleSpec("orders", "Orders", "Sales", "fa5s.clipboard-list", OrdersPage, ("Admin", "Sales Staff")),
    ModuleSpec("dispatch", "Dispatch", "Warehouse", "fa5s.truck-loading", DispatchPage, ("Admin", "Warehouse Staff")),
    ModuleSpec("inventory", "Inventory", "Warehouse", "fa5s.boxes", InventoryPage, ("Admin", "Warehouse Staff")),
    ModuleSpec("products", "Products", "Warehouse", "fa5s.tags", ProductsPage, ("Admin", "Warehouse Staff")),
    ModuleSpec("invoices", "Invoices", "Finance", "fa5s.file-invoice", InvoicesPage, ("Admin", "Sales Staff", "Bookkeeper")),
    ModuleSpec("customers", "Customers", "Finance", "fa5s.users", CustomersPage, ("Admin", "Sales Staff")),
    ModuleSpec("balance", "Balance Sheet", "Finance", "fa5s.balance-scale", BalanceSheetPage, ("Admin", "Bookkeeper")),
    ModuleSpec("reports", "Reports", "Finance", "fa5s.chart-pie", ReportsPage, ("Admin", "Bookkeeper")),
    ModuleSpec("users", "User Management", "Admin", "fa5s.user-shield", UserManagementPage, ("Admin",)),
]

MODULE_BY_KEY = {module.key: module for module in MODULES}

ROLE_START_PAGE = {
    "Admin": "dashboard",
    "Sales Staff": "dashboard",
    "Warehouse Staff": "dispatch",
    "Bookkeeper": "dashboard",
}


def allowed_modules(role):
    return [module for module in MODULES if role in module.roles]


def can_access(role, module_key):
    module = MODULE_BY_KEY.get(module_key)
    return bool(module and role in module.roles)
