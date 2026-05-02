from fastapi import APIRouter, HTTPException, Request, status
from sqlite3 import Error

from backend.security import current_user_from_request, effective_permission_keys
from database.connection import get_connection


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _has_any(permission_keys, *keys):
    return any(key in permission_keys for key in keys)


@router.get("/overview")
def get_dashboard_overview(request: Request):
    user = current_user_from_request(request)
    permission_keys = effective_permission_keys(user["id"], user.get("role"))
    can_inventory = _has_any(
        permission_keys,
        "products.view",
        "products.add",
        "products.edit",
        "inventory.view",
        "inventory.add",
        "inventory.edit",
        "inventory.update_stock",
        "dispatch.view",
    )
    can_sales = _has_any(
        permission_keys,
        "pos.create_sale",
        "orders.view",
        "orders.create",
        "invoices.view",
        "payments.view",
        "reports.view",
        "reports.financial.generate",
    )
    can_orders = _has_any(permission_keys, "orders.view", "orders.create", "dispatch.view", "dispatch.update")
    can_finance = _has_any(permission_keys, "payments.view", "payments.manage", "balance.view", "reports.view")
    can_users = "users.view" in permission_keys

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        stats = {}
        low_stock_items = []
        recent_orders = []
        recent_transactions = []
        recent_stock_updates = []
        top_selling_products = []
        products_needing_restock = []
        sales_summary = {}
        inventory_summary = {}

        if can_inventory:
            cursor.execute(
                """
                SELECT COUNT(*) AS total_products,
                       COALESCE(SUM(quantity), 0) AS total_stock_quantity,
                       SUM(CASE WHEN quantity > 0 AND quantity <= low_stock_threshold THEN 1 ELSE 0 END) AS low_stock_items,
                       SUM(CASE WHEN quantity <= 0 THEN 1 ELSE 0 END) AS out_of_stock_items
                FROM inventory
                WHERE is_active = 1
                """
            )
            inventory_summary = cursor.fetchone() or {}
            stats.update(inventory_summary)

            cursor.execute(
                """
                SELECT item_code, item_name, category, floor, quantity, low_stock_threshold, unit_price
                FROM inventory
                WHERE is_active = 1
                  AND quantity > 0
                  AND quantity <= low_stock_threshold
                ORDER BY quantity ASC, item_name ASC
                LIMIT 10
                """
            )
            low_stock_items = cursor.fetchall()

            cursor.execute(
                """
                SELECT item_code, item_name, category, floor, quantity, low_stock_threshold, unit_price
                FROM inventory
                WHERE is_active = 1
                  AND quantity <= low_stock_threshold
                ORDER BY quantity ASC, item_name ASC
                LIMIT 10
                """
            )
            products_needing_restock = cursor.fetchall()

            cursor.execute(
                """
                SELECT item_code, item_name, category, floor, quantity, updated_at
                FROM inventory
                WHERE is_active = 1
                ORDER BY updated_at DESC
                LIMIT 8
                """
            )
            recent_stock_updates = cursor.fetchall()

        if can_orders:
            cursor.execute("SELECT COUNT(*) AS pending_orders FROM orders WHERE status = 'Pending'")
            stats["pending_orders"] = cursor.fetchone()["pending_orders"]
            cursor.execute(
                """
                SELECT order_number, customer_name, status, dispatch_status, total_amount, created_at
                FROM orders
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
            recent_orders = cursor.fetchall()

        if can_sales:
            cursor.execute(
                """
                SELECT COALESCE(SUM(total_amount), 0) AS total_sales
                FROM invoices
                WHERE status != 'Cancelled'
                """
            )
            stats["total_sales"] = float(cursor.fetchone()["total_sales"] or 0.0)
            cursor.execute(
                """
                SELECT COALESCE(SUM(total_amount), 0) AS sales_today,
                       COUNT(*) AS invoices_today
                FROM invoices
                WHERE status != 'Cancelled'
                  AND DATE(issued_at) = CURDATE()
                """
            )
            sales_summary = cursor.fetchone() or {}
            sales_summary["sales_today"] = float(sales_summary.get("sales_today") or 0.0)
            stats.update(sales_summary)
            cursor.execute(
                """
                SELECT invoice_number, customer_name, total_amount, amount_paid, status, issued_at
                FROM invoices
                ORDER BY issued_at DESC
                LIMIT 10
                """
            )
            recent_transactions = cursor.fetchall()
            cursor.execute(
                """
                SELECT i.item_name,
                       SUM(oi.quantity) AS quantity_sold,
                       SUM(oi.quantity * oi.unit_price) AS gross_sales
                FROM order_items oi
                JOIN inventory i ON i.id = oi.item_id
                GROUP BY i.id, i.item_name
                ORDER BY quantity_sold DESC
                LIMIT 8
                """
            )
            top_selling_products = cursor.fetchall()

        if can_finance:
            cursor.execute(
                """
                SELECT COALESCE(SUM(total_amount - amount_paid), 0) AS outstanding_balance,
                       SUM(CASE WHEN payment_status = 'Partial' THEN 1 ELSE 0 END) AS partial_payments
                FROM payments
                WHERE payment_status = 'Partial'
                """
            )
            finance = cursor.fetchone() or {}
            stats["outstanding_balance"] = float(finance.get("outstanding_balance") or 0.0)
            stats["partial_payments"] = int(finance.get("partial_payments") or 0)

        if can_users:
            cursor.execute("SELECT COUNT(*) AS total_users FROM users")
            stats["total_users"] = cursor.fetchone()["total_users"]

        stats["pending_tasks"] = int(stats.get("pending_orders") or 0) + int(stats.get("low_stock_items") or 0) + int(stats.get("partial_payments") or 0)

        return {
            "role": user.get("role"),
            "permissions": sorted(permission_keys),
            "widgets": {
                "inventory": can_inventory,
                "sales": can_sales,
                "orders": can_orders,
                "finance": can_finance,
                "users": can_users,
            },
            "stats": stats,
            "inventory_summary": inventory_summary,
            "sales_summary": sales_summary,
            "low_stock_items": low_stock_items,
            "recent_orders": recent_orders,
            "recent_transactions": recent_transactions,
            "recent_stock_updates": recent_stock_updates,
            "top_selling_products": top_selling_products,
            "products_needing_restock": products_needing_restock,
        }
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load dashboard data: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()
