from fastapi import APIRouter, HTTPException
from sqlite3 import Error

from database.connection import get_connection


router = APIRouter(prefix="/balance", tags=["Balance"])


@router.get("/customers")
def customer_balances():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT c.id, c.full_name, c.customer_type, c.contact_number,
                   c.total_purchases, c.balance,
                   i.id AS invoice_id, i.invoice_number, i.total_amount,
                   i.amount_paid, i.status, i.payment_method, i.issued_at
            FROM customers c
            LEFT JOIN invoices i ON i.customer_name = c.full_name
            WHERE c.balance > 0 OR i.status IN ('Partial', 'Unpaid', 'Pending')
            ORDER BY c.full_name ASC, i.issued_at DESC
            """
        )
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch balances: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/summary")
def balance_summary():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT COALESCE(SUM(total_amount), 0) AS receivables,
                   COALESCE(SUM(amount_paid), 0) AS collected,
                   COALESCE(SUM(total_amount - amount_paid), 0) AS uncollected
            FROM invoices
            WHERE status != 'Cancelled'
            """
        )
        totals = cursor.fetchone()
        cursor.execute(
            """
            SELECT COALESCE(payment_method, 'Unknown') AS payment_method,
                   COALESCE(SUM(amount_paid), 0) AS collected
            FROM payments
            GROUP BY COALESCE(payment_method, 'Unknown')
            ORDER BY collected DESC
            """
        )
        by_method = cursor.fetchall()
        return {**totals, "by_method": by_method}
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch balance summary: {exc}") from exc
    finally:
        cursor.close()
        connection.close()
