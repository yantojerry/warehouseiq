# Owns orders domain schemas and serializers.

from typing import Literal, Optional

from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    item_id: int
    quantity: int = Field(..., ge=1)


class OrderCreate(BaseModel):
    order_number: str = Field(..., min_length=1, max_length=50)
    customer_name: Optional[str] = Field(default="Walk-in", max_length=255)
    notes: Optional[str] = None
    items: list[OrderItemCreate]


class OrderStatusUpdate(BaseModel):
    status: Literal["Pending", "Processing", "Ready", "Completed", "Cancelled"]


class OrderNotesUpdate(BaseModel):
    notes: Optional[str] = None
