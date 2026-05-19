# Owns registration of all WarehouseIQ API route modules.

from fastapi import APIRouter

from backend.api.v1.auth import router as auth_router
from backend.api.v1.balance import router as balance_router
from backend.api.v1.customers import ensure_customers_table, router as customers_router
from backend.api.v1.dashboard import router as dashboard_router
from backend.api.v1.dispatch import router as dispatch_router
from backend.api.v1.invoices import router as invoices_router
from backend.api.v1.inventory import router as inventory_router
from backend.api.v1.orders import router as orders_router
from backend.api.v1.payments import router as payments_router
from backend.api.v1.pos import router as pos_router
from backend.api.v1.reports import router as reports_router
from backend.api.v1.roles import router as roles_router
from backend.api.v1.shipments import router as shipments_router
from backend.api.v1.suppliers import router as suppliers_router
from backend.api.v1.users import router as users_router


api_router = APIRouter()

api_router.include_router(inventory_router)
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(orders_router)
api_router.include_router(payments_router)
api_router.include_router(invoices_router)
api_router.include_router(customers_router)
api_router.include_router(pos_router)
api_router.include_router(dispatch_router)
api_router.include_router(balance_router)
api_router.include_router(reports_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(suppliers_router)
api_router.include_router(shipments_router)

