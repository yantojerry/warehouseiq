from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlite3 import Error

from backend.routes.dispatch import dispatch_hub
from database.connection import get_connection
from utils.helpers import generate_invoice_number, generate_order_number


router = APIRouter(prefix="/pos", tags=["POS"])
CENT = Decimal("0.01")


class CheckoutItem(BaseModel):
    item_id: int
    quantity: int = Field(..., ge=1)


class CheckoutRequest(BaseModel):
    customer_name: Optional[str] = "Walk-in"
    customer_type: Optional[str] = "Walk-in"
    payment_method: str = "Cash"
    amount_paid: float = Field(default=0.0, ge=0)
    amount_tendered: Optional[float] = Field(default=None, ge=0)
    created_by: Optional[str] = "system"
    notes: Optional[str] = "Created from POS"
    items: list[CheckoutItem]


def _payment_status(total, paid):
    total_value = _money(total)
    paid_value = _money(paid)
    if paid_value >= total_value and total_value > 0:
        return "Paid"
    if paid_value > 0:
        return "Partial"
    return "Unpaid"


def _money(value):
    try:
        return Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _money_float(value):
    return float(_money(value))


def _is_cash(payment_method):
    return (payment_method or "").strip().lower() == "cash"


def _fetch_substitutes(cursor, category, exclude_item_id):
    cursor.execute(
        """
        SELECT id, item_code, item_name, category, floor, quantity, unit_price
        FROM inventory
        WHERE is_active = 1
          AND quantity > 0
          AND id != %s
          AND COALESCE(category, '') = COALESCE(%s, '')
        ORDER BY quantity DESC, item_name ASC
        LIMIT 5
        """,
        (exclude_item_id, category),
    )
    return cursor.fetchall()


def _is_duplicate_key_error(exc):
    text = str(exc).lower()
    return "duplicate" in text or "unique" in text


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def checkout(payload: CheckoutRequest):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    tendered_amount = _money(
        payload.amount_tendered if payload.amount_tendered is not None else payload.amount_paid
    )
    if tendered_amount <= 0:
        raise HTTPException(status_code=400, detail="Payment is required before checkout")

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        inventory_rows = []
        insufficient = []
        total_amount = Decimal("0.00")
        for item in payload.items:
            cursor.execute(
                """
                SELECT id, item_code, item_name, category, floor, quantity, unit_price
                FROM inventory
                WHERE id = %s AND is_active = 1
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
            inventory_rows.append((item, inventory))
            total_amount += item.quantity * _money(inventory["unit_price"])
        total_amount = _money(total_amount)

        if insufficient:
            raise HTTPException(
                status_code=409,
                detail={"message": "Insufficient stock", "items": insufficient},
            )
        if tendered_amount > total_amount and not _is_cash(payload.payment_method):
            raise HTTPException(status_code=400, detail="Amount paid cannot exceed total")

        paid_amount = min(tendered_amount, total_amount) if _is_cash(payload.payment_method) else tendered_amount
        change_due = tendered_amount - total_amount if _is_cash(payload.payment_method) and tendered_amount > total_amount else Decimal("0.00")
        pay_status = _payment_status(total_amount, paid_amount)
        customer = payload.customer_name or "Walk-in"

        customer_id = None
        for attempt in range(3):
            order_number = generate_order_number()
            invoice_number = generate_invoice_number()
            try:
                cursor.execute(
                    """
                    INSERT INTO orders (
                        order_number, customer_name, status, dispatch_status,
                        total_amount, payment_method, notes, created_by
                    )
                    VALUES (%s, %s, 'Pending', 'Pending', %s, %s, %s, %s)
                    """,
                    (order_number, customer, _money_float(total_amount), payload.payment_method, payload.notes, payload.created_by),
                )
                order_id = cursor.lastrowid

                for item, inventory in inventory_rows:
                    cursor.execute(
                        """
                        UPDATE inventory
                        SET quantity = quantity - %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s AND quantity >= %s
                        """,
                        (item.quantity, item.item_id, item.quantity),
                    )
                    if cursor.rowcount == 0:
                        cursor.execute(
                            "SELECT item_name, category, quantity FROM inventory WHERE id = %s",
                            (item.item_id,),
                        )
                        current = cursor.fetchone() or {}
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "message": "Insufficient stock",
                                "items": [{
                                    "item_id": item.item_id,
                                    "item_name": current.get("item_name"),
                                    "requested": item.quantity,
                                    "available": int(current.get("quantity") or 0),
                                    "substitutes": _fetch_substitutes(cursor, current.get("category"), item.item_id),
                                }],
                            },
                        )
                    cursor.execute(
                        """
                        INSERT INTO order_items (order_id, item_id, quantity, unit_price)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (order_id, item.item_id, item.quantity, inventory["unit_price"]),
                    )

                cursor.execute(
                    "SELECT id FROM customers WHERE full_name = %s LIMIT 1",
                    (customer,),
                )
                existing_customer = cursor.fetchone()
                if existing_customer:
                    customer_id = existing_customer["id"]

                cursor.execute(
                    """
                    INSERT INTO invoices (
                        invoice_number, order_id, customer_id, customer_name, total_amount,
                        amount_paid, payment_method, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        invoice_number,
                        order_id,
                        customer_id,
                        customer,
                        _money_float(total_amount),
                        _money_float(paid_amount),
                        payload.payment_method,
                        pay_status,
                    ),
                )
                invoice_id = cursor.lastrowid
                break
            except Error as exc:
                connection.rollback()
                if attempt == 2 or not _is_duplicate_key_error(exc):
                    raise
        else:
            raise HTTPException(status_code=500, detail="Checkout failed: duplicate number retry exhausted")

        cursor.execute(
            """
            INSERT INTO payments (
                order_id, invoice_id, customer_name, total_amount, amount_paid,
                payment_method, payment_status, recorded_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                order_id,
                invoice_id,
                customer,
                _money_float(total_amount),
                _money_float(paid_amount),
                payload.payment_method,
                pay_status,
                payload.created_by,
            ),
        )
        payment_id = cursor.lastrowid
        if paid_amount > 0:
            cursor.execute(
                """
                INSERT INTO payment_history (
                    payment_id, invoice_id, amount_paid, payment_method, note, recorded_by
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (payment_id, invoice_id, _money_float(paid_amount), payload.payment_method, "POS checkout", payload.created_by),
            )

        cursor.execute(
            "SELECT id, balance, total_purchases FROM customers WHERE full_name = %s LIMIT 1",
            (customer,),
        )
        existing_customer = cursor.fetchone()
        new_balance = max(Decimal("0.00"), total_amount - paid_amount)
        if existing_customer:
            cursor.execute(
                """
                UPDATE customers
                SET total_purchases = total_purchases + %s,
                    balance = balance + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (_money_float(total_amount), _money_float(new_balance), existing_customer["id"]),
            )
        else:
            cursor.execute(
                """
                INSERT INTO customers (full_name, customer_type, total_purchases, balance)
                VALUES (%s, %s, %s, %s)
                """,
                (customer, payload.customer_type or "Walk-in", _money_float(total_amount), _money_float(new_balance)),
            )
            customer_id = cursor.lastrowid
            cursor.execute(
                "UPDATE invoices SET customer_id = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (customer_id, invoice_id),
            )

        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (%s, 'checkout', 'order', %s, %s)
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
            "total_amount": _money_float(total_amount),
            "amount_tendered": _money_float(tendered_amount),
            "amount_paid": _money_float(paid_amount),
            "change_due": _money_float(change_due),
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

    try:
        await dispatch_hub.broadcast({"type": "new_order", **result})
    except Exception:
        pass
    return result
