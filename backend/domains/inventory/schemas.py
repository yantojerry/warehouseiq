# Owns inventory domain schemas and serializers.

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


INVENTORY_CREATE_EXAMPLE = {
    "item_code": "ITM-101",
    "item_name": "PVC Pipe 2in",
    "category": "Plumbing",
    "floor": 2,
    "quantity": 120,
    "low_stock_threshold": 15,
    "unit_price": 185.5,
}

INVENTORY_UPDATE_EXAMPLE = {
    "item_code": "ITM-101",
    "item_name": "PVC Pipe 2in - Updated",
    "category": "Plumbing",
    "floor": 3,
    "quantity": 95,
    "low_stock_threshold": 20,
    "unit_price": 190.0,
}


class InventoryBase(BaseModel):
    item_code: str = Field(..., min_length=1, max_length=50)
    item_name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field(default=None, max_length=100)
    floor: int = Field(default=1, ge=1)
    quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=5, ge=0)
    unit_price: float = Field(default=0.0, ge=0)
    image_data: Optional[str] = None
    is_active: int = 1


class InventoryCreate(InventoryBase):
    pass


class InventoryUpdate(InventoryBase):
    pass


class InventoryItem(InventoryBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
