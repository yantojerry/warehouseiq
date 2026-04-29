from fastapi import APIRouter, HTTPException, status
from sqlite3 import Error

from database.connection import get_connection


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview")
def get_dashboard_overview():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) AS total_items FROM inventory")
        total_items = cursor.fetchone()["total_items"]

        cursor.execute(
            "SELECT COUNT(*) AS low_stock FROM inventory WHERE quantity <= low_stock_threshold"
        )
        low_stock = cursor.fetchone()["low_stock"]

        cursor.execute("SELECT COUNT(*) AS pending_orders FROM orders WHERE status = 'Pending'")
        pending_orders = cursor.fetchone()["pending_orders"]

        cursor.execute(
            """
            SELECT COALESCE(SUM(total_amount - amount_paid), 0) AS outstanding_balance
            FROM payments
            WHERE payment_status = 'Partial'
            """
        )
        outstanding_balance = float(cursor.fetchone()["outstanding_balance"] or 0.0)

        cursor.execute("SELECT COUNT(*) AS total_users FROM users")
        total_users = cursor.fetchone()["total_users"]

        cursor.execute(
            """
            SELECT item_code, item_name, floor, quantity, low_stock_threshold
            FROM inventory
            WHERE quantity <= low_stock_threshold
            ORDER BY quantity ASC
            """
        )
        low_stock_items = cursor.fetchall()

        cursor.execute(
            """
            SELECT order_number, customer_name, status, total_amount, created_at
            FROM orders
            ORDER BY created_at DESC
            LIMIT 10
            """
        )
        recent_orders = cursor.fetchall()

        return {
            "stats": {
                "total_items": total_items,
                "low_stock": low_stock,
                "pending_orders": pending_orders,
                "outstanding_balance": outstanding_balance,
                "total_users": total_users,
            },
            "low_stock_items": low_stock_items,
            "recent_orders": recent_orders,
        }
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load dashboard data: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()
