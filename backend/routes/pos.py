from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlite3 import Error

from backend.routes.dispatch import dispatch_hub
from database.connection import get_connection
from utils.helpers import generate_invoice_number, generate_order_number


router = APIRouter(prefix="/pos", tags=["POS"])


class CheckoutItem(BaseModel):
    item_id: int
    quantity: int = Field(..., ge=1)


class CheckoutRequest(BaseModel):
    customer_name: Optional[str] = "Walk-in"
    customer_type: Optional[str] = "Walk-in"
    payment_method: str = "Cash"
    amount_paid: float = Field(default=0.0, ge=0)
    created_by: Optional[str] = "system"
    notes: Optional[str] = "Created from POS"
    items: list[CheckoutItem]


def _payment_status(total, paid):
    if paid >= total and total > 0:
        return "Paid"
    if paid > 0:
        return "Partial"
    return "Unpaid"


def _fetch_substitutes(cursor, category, exclude_item_id):
    cursor.execute(
        """
        SELECT id, item_code, item_name, category, floor, quantity, unit_price
        FROM inventory
        WHERE is_active = 1
          AND quantity > 0
          AND id != ?
          AND COALESCE(category, '') = COALESCE(?, '')
        ORDER BY quantity DESC, item_name ASC
        LIMIT 5
        """,
        (exclude_item_id, category),
    )
    return cursor.fetchall()


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def checkout(payload: CheckoutRequest):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        inventory_rows = []
        insufficient = []
        total_amount = 0.0
        for item in payload.items:
            cursor.execute(
                """
                SELECT id, item_code, item_name, category, floor, quantity, unit_price
                FROM inventory
                WHERE id = ? AND is_active = 1
                """,
                (item.item_id,),
            )
            inventory = cursor.fetchone()
            if not inventory:
                insufficient.append({
                    "item_id": item.item_id,
                    "message": "Item is no longer available",
                    "substitutes": [],
                })
                continue
            if item.quantity > int(inventory["quantity"] or 0):
                insufficient.append({
                    "item_id": item.item_id,
                    "item_name": inventory["item_name"],
                    "requested": item.quantity,
                    "available": int(inventory["quantity"] or 0),
                    "substitutes": _fetch_substitutes(cursor, inventory.get("category"), item.item_id),
                })
                continue
            inventory_rows.append((item, inventory))
            total_amount += item.quantity * float(inventory["unit_price"] or 0)

        if insufficient:
            raise HTTPException(
                status_code=409,
                detail={"message": "Insufficient stock", "items": insufficient},
            )
        if payload.amount_paid > total_amount:
            raise HTTPException(status_code=400, detail="Amount paid cannot exceed total")

        order_number = generate_order_number()
        invoice_number = generate_invoice_number()
        pay_status = _payment_status(total_amount, payload.amount_paid)
        customer = payload.customer_name or "Walk-in"

        cursor.execute(
            """
            INSERT INTO orders (
                order_number, customer_name, status, dispatch_status,
                total_amount, payment_method, notes, created_by
            )
            VALUES (?, ?, 'Pending', 'Pending', ?, ?, ?, ?)
            """,
            (order_number, customer, total_amount, payload.payment_method, payload.notes, payload.created_by),
        )
        order_id = cursor.lastrowid

        for item, inventory in inventory_rows:
            cursor.execute(
                """
                INSERT INTO order_items (order_id, item_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, item.item_id, item.quantity, inventory["unit_price"]),
            )
            cursor.execute(
                """
                UPDATE inventory
                SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (item.quantity, item.item_id),
            )

        cursor.execute(
            """
            INSERT INTO invoices (
                invoice_number, order_id, customer_name, total_amount,
                amount_paid, payment_method, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (invoice_number, order_id, customer, total_amount, payload.amount_paid, payload.payment_method, pay_status),
        )
        invoice_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO payments (
                order_id, invoice_id, customer_name, total_amount, amount_paid,
                payment_method, payment_status, recorded_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                invoice_id,
                customer,
                total_amount,
                payload.amount_paid,
                payload.payment_method,
                pay_status,
                payload.created_by,
            ),
        )
        payment_id = cursor.lastrowid
        if payload.amount_paid > 0:
            cursor.execute(
                """
                INSERT INTO payment_history (
                    payment_id, invoice_id, amount_paid, payment_method, note, recorded_by
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (payment_id, invoice_id, payload.amount_paid, payload.payment_method, "POS checkout", payload.created_by),
            )

        cursor.execute(
            "SELECT id, balance, total_purchases FROM customers WHERE full_name = ? LIMIT 1",
            (customer,),
        )
        existing_customer = cursor.fetchone()
        new_balance = max(0.0, total_amount - payload.amount_paid)
        if existing_customer:
            cursor.execute(
                """
                UPDATE customers
                SET total_purchases = total_purchases + ?,
                    balance = balance + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (total_amount, new_balance, existing_customer["id"]),
            )
        else:
            cursor.execute(
                """
                INSERT INTO customers (full_name, customer_type, total_purchases, balance)
                VALUES (?, ?, ?, ?)
                """,
                (customer, payload.customer_type or "Walk-in", total_amount, new_balance),
            )

        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'checkout', 'order', ?, ?)
            """,
            (payload.created_by, order_id, order_number),
        )
        connection.commit()
        result = {
            "message": "Checkout completed",
            "order_id": order_id,
            "order_number": order_number,
            "invoice_id": invoice_id,
            "invoice_number": invoice_number,
            "payment_id": payment_id,
            "total_amount": total_amount,
            "payment_status": pay_status,
        }
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Checkout failed: {exc}") from exc
    finally:
        cursor.close()
        connection.close()

    await dispatch_hub.broadcast({"type": "new_order", **result})
    return result
