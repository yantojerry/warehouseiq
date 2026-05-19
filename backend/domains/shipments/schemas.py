# Owns shipments domain schemas and serializers.

from typing import Literal, Optional

from pydantic import BaseModel


class PickStatusUpdate(BaseModel):
    status: Literal["Pending", "Picked", "Partially Picked", "Out of Stock"]
    picked_quantity: Optional[int] = None
    actor: Optional[str] = "warehouse"
