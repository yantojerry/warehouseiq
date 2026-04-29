from contextlib import asynccontextmanager

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
from backend.routes.users import router as users_router
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


@app.get("/")
def root():
    return {"message": "WarehouseIQ API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8000, reload=False)
