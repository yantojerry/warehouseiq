from contextlib import asynccontextmanager
import os
import socket

from fastapi import FastAPI
import uvicorn

from backend.api.router import api_router, ensure_customers_table
from backend.auth.security import permission_middleware
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

app.include_router(api_router)


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
