# Owns version 1 shipment API endpoints.

from fastapi import APIRouter


router = APIRouter(prefix="/shipments", tags=["Shipments"])

