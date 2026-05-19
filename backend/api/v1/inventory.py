# Owns version 1 inventory API endpoints.

from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request, status
from mysql.connector import Error

from backend.auth.security import current_user_from_request
from backend.domains.inventory.schemas import (
    INVENTORY_CREATE_EXAMPLE,
    INVENTORY_UPDATE_EXAMPLE,
    InventoryCreate,
    InventoryItem,
    InventoryUpdate,
)
from database.connection import fetch_inventory_item, get_connection


router = APIRouter(tags=["Inventory"])


@router.get("/inventory", response_model=list[InventoryItem])
def get_inventory(
    search: Optional[str] = Query(default=None),
    floor: Optional[int] = Query(default=None, ge=1),
):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        query = """
            SELECT id, item_code, item_name, category, floor, quantity,
                   low_stock_threshold, unit_price, image_data, is_active, created_at, updated_at
            FROM inventory
            WHERE is_active = 1
        """
        params = []
        if search:
            query += " AND (item_name LIKE %s OR item_code LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])
        if floor:
            query += " AND floor = %s"
            params.append(floor)
        query += " ORDER BY floor ASC, item_name ASC"

        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch inventory: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: int):
    try:
        item = fetch_inventory_item(item_id)
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch inventory item: {exc}",
        ) from exc

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    return item


@router.post("/inventory/grn")
def receive_stock_grn(
    item_id: int = Body(...),
    supplier_name: str = Body(...),
    quantity_received: int = Body(..., ge=1),
    condition: str = Body("Good"),
    date_received: str = Body(None),
    notes: str = Body(None),
    request: Request = None,
):
    item = fetch_inventory_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    actor = None
    if request:
        try:
            actor = current_user_from_request(request).get("username")
        except Exception:
            pass
    reason = f"GRN - {supplier_name}"
    reference = f"Condition: {condition}" + (f" | {notes}" if notes else "")
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE inventory SET quantity = quantity + %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (quantity_received, item_id),
        )
        cursor.execute(
            """
            INSERT INTO stock_movements (item_id, item_name, quantity_change, reason, reference, actor)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (item_id, item["item_name"], quantity_received, reason, reference, actor),
        )
        connection.commit()
        return {"message": "Stock received successfully", "id": item_id}
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to receive stock: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.post("/inventory/{item_id}/restock")
def restock_inventory_item(item_id: int, amount: int = Body(..., embed=True, ge=1), request: Request = None):
    item = fetch_inventory_item(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
    actor = None
    if request:
        try:
            actor = current_user_from_request(request).get("username")
        except Exception:
            pass
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE inventory SET quantity = quantity + %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (amount, item_id),
        )
        cursor.execute(
            """
            INSERT INTO stock_movements (item_id, item_name, quantity_change, reason, actor)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (item_id, item["item_name"], amount, "Restocked", actor),
        )
        connection.commit()
        return {"message": "Inventory restocked successfully", "id": item_id}
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to restock: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.post("/inventory/{item_id}/stock-out")
def stock_out_inventory_item(item_id: int, amount: int = Body(..., embed=True, ge=1)):
    item = fetch_inventory_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )
    if amount > item["quantity"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot stock out {amount} units. "
                f"Only {item['quantity']} units are available."
            ),
        )

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE inventory SET quantity = quantity - %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (amount, item_id),
        )
        cursor.execute(
            """
            INSERT INTO stock_movements (item_id, item_name, quantity_change, reason, actor)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (item_id, item["item_name"], -amount, "Stock Out", None),
        )
        connection.commit()
        return {"message": "Inventory stock deducted successfully", "id": item_id}
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to stock out: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.post("/inventory", response_model=InventoryItem, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    payload: InventoryCreate = Body(
        ...,
        examples={
            "default": {
                "summary": "Create a new inventory item",
                "value": INVENTORY_CREATE_EXAMPLE,
            }
        },
    )
):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO inventory (
                item_code, item_name, category, floor, quantity,
                low_stock_threshold, unit_price, image_data, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                payload.item_code,
                payload.item_name,
                payload.category,
                payload.floor,
                payload.quantity,
                payload.low_stock_threshold,
                payload.unit_price,
                payload.image_data,
                payload.is_active,
            ),
        )
        connection.commit()
        created_item = fetch_inventory_item(cursor.lastrowid)
        return created_item
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create inventory item: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/inventory/{item_id}", response_model=InventoryItem)
def update_inventory_item(
    item_id: int,
    payload: InventoryUpdate = Body(
        ...,
        examples={
            "default": {
                "summary": "Update an existing inventory item",
                "value": INVENTORY_UPDATE_EXAMPLE,
            }
        },
    ),
):
    if not fetch_inventory_item(item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE inventory
            SET item_code = %s,
                item_name = %s,
                category = %s,
                floor = %s,
                quantity = %s,
                low_stock_threshold = %s,
                unit_price = %s,
                image_data = %s,
                is_active = %s
            WHERE id = %s
            """,
            (
                payload.item_code,
                payload.item_name,
                payload.category,
                payload.floor,
                payload.quantity,
                payload.low_stock_threshold,
                payload.unit_price,
                payload.image_data,
                payload.is_active,
                item_id,
            ),
        )
        connection.commit()
        updated_item = fetch_inventory_item(item_id)
        return updated_item
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update inventory item: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.delete("/inventory/{item_id}")
def delete_inventory_item(item_id: int, request: Request):
    if not fetch_inventory_item(item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    connection = get_connection()
    cursor = connection.cursor()
    try:
        actor = current_user_from_request(request).get("username")
        cursor.execute(
            """
            UPDATE inventory
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (item_id,),
        )
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, reason)
            VALUES (%s, 'deactivate', 'inventory', %s, %s)
            """,
            (actor, item_id, "Inventory item removed from active catalog"),
        )
        connection.commit()
        return {"message": "Inventory item deleted successfully", "id": item_id}
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete inventory item: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()

@router.get("/inventory/{item_id}/movements")
def get_stock_movements(item_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, item_id, item_name, quantity_change, reason, reference, actor, created_at
            FROM stock_movements
            WHERE item_id = %s
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (item_id,),
        )
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch movements: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/stock-movements")
def get_all_stock_movements():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT sm.id, sm.item_id, sm.item_name, sm.quantity_change,
                   sm.reason, sm.reference, sm.actor, sm.created_at,
                   i.category, i.floor
            FROM stock_movements sm
            LEFT JOIN inventory i ON i.id = sm.item_id
            ORDER BY sm.created_at DESC
            LIMIT 200
            """
        )
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch movements: {exc}") from exc
    finally:
        cursor.close()
        connection.close()
