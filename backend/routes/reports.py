from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlite3 import Error

from database.connection import get_connection


router = APIRouter(prefix="/reports", tags=["Reports"])


def _date_clause(column, date_from, date_to, params):
    clause = ""
    if date_from:
        clause += f" AND DATE({column}) >= DATE(?)"
        params.append(date_from)
    if date_to:
        clause += f" AND DATE({column}) <= DATE(?)"
        params.append(date_to)
    return clause


@router.get("/sales")
def sales_report(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    params = []
    try:
        clause = _date_clause("issued_at", date_from, date_to, params)
        cursor.execute(
            f"""
            SELECT COUNT(*) AS invoices,
                   COALESCE(SUM(total_amount), 0) AS gross_sales,
                   COALESCE(SUM(amount_paid), 0) AS collected,
                   COALESCE(SUM(total_amount - amount_paid), 0) AS uncollected
            FROM invoices
            WHERE status != 'Cancelled' {clause}
            """,
            tuple(params),
        )
        return cursor.fetchone()
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build sales report: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/orders")
def orders_report(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    params = []
    try:
        clause = _date_clause("created_at", date_from, date_to, params)
        cursor.execute(
            f"""
            SELECT status, COUNT(*) AS count, COALESCE(SUM(total_amount), 0) AS total
            FROM orders
            WHERE 1=1 {clause}
            GROUP BY status
            ORDER BY count DESC
            """,
            tuple(params),
        )
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build orders report: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/payments")
def payments_report(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    params = []
    try:
        clause = _date_clause("created_at", date_from, date_to, params)
        cursor.execute(
            f"""
            SELECT COALESCE(payment_method, 'Unknown') AS payment_method,
                   COUNT(*) AS count,
                   COALESCE(SUM(amount_paid), 0) AS collected
            FROM payments
            WHERE 1=1 {clause}
            GROUP BY COALESCE(payment_method, 'Unknown')
            ORDER BY collected DESC
            """,
            tuple(params),
        )
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build payments report: {exc}") from exc
    finally:
        cursor.close()
        connection.close()
