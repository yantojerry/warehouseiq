from contextlib import asynccontextmanager
import os
import socket

from fastapi import FastAPI
import uvicorn

from backend.routes.auth import router as auth_router
from backend.routes.balance import router as balance_router
from backend.routes.customers import ensure_customers_table, router as customers_router
from backend.routes.dashboard import router as dashboard_router
from backend.routes.dispatch import router as dispatch_router
from backend.routes.invoices import router as invoices_router
from backend.routes.inventory import router as inventory_router
from backend.routes.orders import router as orders_router
from backend.routes.payments import router as payments_router
from backend.routes.pos import router as pos_router
from backend.routes.reports import router as reports_router
from backend.routes.roles import router as roles_router
from backend.routes.users import router as users_router
from backend.security import permission_middleware
from database.connection import initialize_database, seed_default_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    seed_default_data()
    ensure_customers_table()
    yield


app = FastAPI(
    title="WarehouseIQ API",
    version="1.0.0",
    description="FastAPI backend for the WarehouseIQ warehouse management system.",
    lifespan=lifespan,
)

app.middleware("http")(permission_middleware)

app.include_router(inventory_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(invoices_router)
app.include_router(customers_router)
app.include_router(pos_router)
app.include_router(dispatch_router)
app.include_router(balance_router)
app.include_router(reports_router)
app.include_router(users_router)
app.include_router(roles_router)


@app.get("/")
def root():
    return {"message": "WarehouseIQ API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


def _port_is_in_use(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


if __name__ == "__main__":
    host = os.getenv("WAREHOUSEIQ_API_HOST", "127.0.0.1")
    port = int(os.getenv("WAREHOUSEIQ_API_PORT", "8000"))
    if _port_is_in_use(host, port):
        print(f"WarehouseIQ API is already running on http://{host}:{port}")
        print("Close the existing backend process, or set WAREHOUSEIQ_API_PORT to use another port.")
    else:
        uvicorn.run("main:app", host=host, port=port, reload=False)
