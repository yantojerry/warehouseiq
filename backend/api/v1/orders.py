# Owns version 1 order API endpoints.

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from mysql.connector import Error

from backend.auth.security import current_user_from_request
from backend.core.helpers import generate_order_number
from backend.domains.orders.schemas import OrderCreate, OrderNotesUpdate, OrderStatusUpdate
from database.connection import get_connection


router = APIRouter(prefix="/orders", tags=["Orders"])


def _is_duplicate_key_error(exc):
    text = str(exc).lower()
    return "duplicate" in text or "unique" in text


@router.get("")
def list_orders(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    exclude_status: Optional[str] = Query(default=None),
):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        query = """
            SELECT o.*,
                   COALESCE(item_counts.item_count, 0) AS item_count
            FROM orders o
            LEFT JOIN (
                SELECT order_id, COUNT(*) AS item_count
                FROM order_items
                GROUP BY order_id
            ) item_counts ON item_counts.order_id = o.id
            WHERE 1=1
        """
        params = []
        if status_filter:
            query += " AND status = %s"
            params.append(status_filter)
        if exclude_status:
            query += " AND status != %s"
            params.append(exclude_status)
        query += " ORDER BY o.created_at DESC"

        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch orders: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/available")
def list_available_orders():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, order_number, total_amount
            FROM orders
            WHERE status NOT IN ('Cancelled', 'Completed')
            ORDER BY created_at DESC
            """
        )
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch order options: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/{order_id}")
def get_order(order_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        cursor.execute(
            """
            SELECT oi.id AS order_item_id, oi.item_id, i.item_name, i.category, i.floor,
                   oi.quantity, oi.unit_price, oi.pick_status, oi.picked_quantity,
                   (oi.quantity * oi.unit_price) AS subtotal
            FROM order_items oi
            JOIN inventory i ON oi.item_id = i.id
            WHERE oi.order_id = %s
            ORDER BY oi.id ASC
            """,
            (order_id,),
        )
        items = cursor.fetchall()
        return {"order": order, "items": items}
    except HTTPException:
        raise
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch order: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/{order_id}/notes")
def update_order_notes(order_id: int, payload: OrderNotesUpdate):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM orders WHERE id = %s", (order_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        cursor.execute(
            """
            UPDATE orders
            SET notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (payload.notes, order_id),
        )
        connection.commit()

        cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        return cursor.fetchone()
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update order notes: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, request: Request):
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order must contain at least one item",
        )

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        created_by = current_user_from_request(request).get("username")
        total_amount = 0.0
        inventory_rows = []
        for order_item in payload.items:
            cursor.execute(
                """
                SELECT id, item_name, unit_price
                FROM inventory
                WHERE id = %s
                """,
                (order_item.item_id,),
            )
            inventory_item = cursor.fetchone()
            if not inventory_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Inventory item {order_item.item_id} not found",
                )
            inventory_rows.append((order_item, inventory_item))
            total_amount += order_item.quantity * float(inventory_item["unit_price"])

        order_number = payload.order_number
        for attempt in range(3):
            try:
                cursor.execute(
                    """
                    INSERT INTO orders (order_number, customer_name, status, total_amount, notes, created_by)
                    VALUES (%s, %s, 'Pending', %s, %s, %s)
                    """,
                    (
                        order_number,
                        payload.customer_name or "Walk-in",
                        total_amount,
                        payload.notes,
                        created_by,
                    ),
                )
                break
            except Error as exc:
                if attempt == 2 or not _is_duplicate_key_error(exc):
                    raise
                order_number = generate_order_number()
        order_id = cursor.lastrowid

        for order_item, inventory_item in inventory_rows:
            cursor.execute(
                """
                UPDATE inventory
                SET quantity = quantity - %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND quantity >= %s
                """,
                (order_item.quantity, order_item.item_id, order_item.quantity),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "SELECT item_name, quantity FROM inventory WHERE id = %s",
                    (order_item.item_id,),
                )
                current = cursor.fetchone() or {}
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Only {current.get('quantity', 0)} units available for "
                        f"{current.get('item_name') or f'item {order_item.item_id}'}"
                    ),
                )
            cursor.execute(
                """
                INSERT INTO order_items (order_id, item_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    order_id,
                    order_item.item_id,
                    order_item.quantity,
                    inventory_item["unit_price"],
                ),
            )

        connection.commit()
        return {"message": "Order created successfully", "id": order_id, "order_number": order_number}
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/{order_id}/status")
def update_order_status(order_id: int, payload: OrderStatusUpdate):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM orders WHERE id = %s", (order_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        cursor.execute(
            """
            UPDATE orders
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (payload.status, order_id),
        )
        connection.commit()
        return {"message": "Order status updated successfully", "id": order_id}
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update order status: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()
