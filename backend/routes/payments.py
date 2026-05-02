from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlite3 import Error

from database.connection import get_connection


router = APIRouter(prefix="/payments", tags=["Payments"])


class PaymentCreate(BaseModel):
    order_id: Optional[int] = None
    customer_name: str = Field(..., min_length=1, max_length=255)
    total_amount: float = Field(..., gt=0)
    amount_paid: float = Field(default=0.0, ge=0)
    payment_method: Optional[str] = None
    recorded_by: Optional[str] = "system"


class PaymentRecord(BaseModel):
    amount_paid: float = Field(..., gt=0)
    payment_method: Optional[str] = None
    note: Optional[str] = None
    recorded_by: Optional[str] = "system"


@router.get("")
def list_payments(
    search: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        query = """
            SELECT p.id, p.customer_name, o.order_number,
                   p.total_amount, p.amount_paid, p.payment_method,
                   (p.total_amount - p.amount_paid) AS balance,
                   p.payment_status, p.updated_at
            FROM payments p
            LEFT JOIN orders o ON p.order_id = o.id
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND p.customer_name LIKE %s"
            params.append(f"%{search}%")
        if status_filter and status_filter != "All":
            query += " AND p.payment_status = %s"
            params.append(status_filter)

        query += " ORDER BY p.updated_at DESC"
        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch payments: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/summary")
def get_payments_summary():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT COALESCE(SUM(total_amount), 0) AS total_amount,
                   COALESCE(SUM(amount_paid), 0) AS amount_paid
            FROM payments
            """
        )
        totals = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) AS partial_count FROM payments WHERE payment_status = 'Partial'")
        partial_count = cursor.fetchone()["partial_count"]
        return {
            "total_amount": float(totals["total_amount"] or 0.0),
            "amount_paid": float(totals["amount_paid"] or 0.0),
            "partial_count": partial_count,
        }
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch payment summary: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_payment(payload: PaymentCreate):
    if payload.amount_paid > payload.total_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount paid cannot exceed total amount",
        )

    payment_status = (
        "Paid" if payload.amount_paid >= payload.total_amount
        else "Partial" if payload.amount_paid > 0
        else "Unpaid"
    )

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO payments (
                order_id, customer_name, total_amount, amount_paid,
                payment_method, payment_status, recorded_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                payload.order_id,
                payload.customer_name,
                payload.total_amount,
                payload.amount_paid,
                payload.payment_method,
                payment_status,
                payload.recorded_by,
            ),
        )
        payment_id = cursor.lastrowid
        if payload.amount_paid > 0:
            cursor.execute(
                """
                INSERT INTO payment_history (
                    payment_id, amount_paid, payment_method, note, recorded_by
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (payment_id, payload.amount_paid, payload.payment_method, "Initial payment", payload.recorded_by),
            )
        connection.commit()
        return {"message": "Payment created successfully", "id": payment_id}
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/{payment_id}")
def get_payment(payment_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT p.id, p.order_id, p.customer_name, p.total_amount, p.amount_paid,
                   p.payment_method, p.payment_status, p.updated_at, o.order_number
            FROM payments p
            LEFT JOIN orders o ON p.order_id = o.id
            WHERE p.id = %s
            """,
            (payment_id,),
        )
        payment = cursor.fetchone()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )
        payment["balance"] = float(payment["total_amount"] - payment["amount_paid"])
        return payment
    except HTTPException:
        raise
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch payment: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.post("/{payment_id}/record")
def record_payment(payment_id: int, payload: PaymentRecord):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT total_amount, amount_paid, invoice_id FROM payments WHERE id = %s",
            (payment_id,),
        )
        payment = cursor.fetchone()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )

        new_paid_total = float(payment["amount_paid"]) + payload.amount_paid
        if new_paid_total > float(payment["total_amount"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment exceeds remaining balance",
            )

        payment_status = "Paid" if new_paid_total >= float(payment["total_amount"]) else "Partial"

        cursor.execute(
            """
            UPDATE payments
            SET amount_paid = %s, payment_status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (new_paid_total, payment_status, payment_id),
        )
        if payment.get("invoice_id"):
            cursor.execute(
                """
                UPDATE invoices
                SET amount_paid = %s, status = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (new_paid_total, payment_status, payment["invoice_id"]),
            )
        cursor.execute(
            """
            INSERT INTO payment_history (payment_id, amount_paid, payment_method, note, recorded_by)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (payment_id, payload.amount_paid, payload.payment_method, payload.note, payload.recorded_by),
        )
        connection.commit()
        return {"message": "Payment recorded successfully", "id": payment_id}
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record payment: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/{payment_id}/history")
def get_payment_history(payment_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT p.id, p.customer_name, p.total_amount, p.amount_paid,
                   p.payment_status, p.order_id, o.order_number
            FROM payments p
            LEFT JOIN orders o ON p.order_id = o.id
            WHERE p.id = %s
            """,
            (payment_id,),
        )
        payment = cursor.fetchone()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )

        cursor.execute(
            """
            SELECT amount_paid, payment_method, note, recorded_by, paid_at
            FROM payment_history
            WHERE payment_id = %s
            ORDER BY paid_at ASC
            """,
            (payment_id,),
        )
        history = cursor.fetchall()
        payment["balance"] = float(payment["total_amount"] - payment["amount_paid"])
        return {"payment": payment, "history": history}
    except HTTPException:
        raise
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch payment history: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()
