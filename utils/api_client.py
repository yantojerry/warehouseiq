import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


API_BASE_URL = os.getenv("WAREHOUSEIQ_API_URL", "http://127.0.0.1:8000")
API_TIMEOUT = float(os.getenv("WAREHOUSEIQ_API_TIMEOUT", "10"))
_SESSION_TOKEN = None
_CURRENT_USER = None


class ApiError(Exception):
    def __init__(self, message, status_code=None, detail=None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def _build_url(path, params=None):
    base = API_BASE_URL.rstrip("/")
    url = f"{base}{path}"
    if params:
        cleaned = {key: value for key, value in params.items() if value is not None}
        if cleaned:
            url = f"{url}?{urllib.parse.urlencode(cleaned)}"
    return url


def _request(method, path, data=None, params=None, expect_json=True):
    body = None
    headers = {"Accept": "application/json"}
    if _SESSION_TOKEN:
        headers["Authorization"] = f"Bearer {_SESSION_TOKEN}"
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        _build_url(path, params=params),
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT) as response:
            raw_body = response.read().decode("utf-8")
            if not raw_body:
                return None
            if expect_json:
                return json.loads(raw_body)
            return raw_body
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            detail = payload.get("detail")
            if isinstance(detail, dict):
                message = detail.get("message") or payload.get("message") or str(exc)
            else:
                message = detail or payload.get("message") or str(exc)
        except Exception:
            message = str(exc)
            detail = None
        raise ApiError(message, status_code=exc.code, detail=detail) from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"Could not reach the backend API: {exc.reason}") from exc


def is_api_available():
    try:
        health()
        return True
    except ApiError:
        return False


def wait_for_api(timeout=15):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            return health()
        except ApiError as exc:
            last_error = exc
            time.sleep(0.5)
    raise last_error or ApiError("Timed out waiting for the backend API.")


def health():
    return _request("GET", "/health")


def set_session(token=None, user=None):
    global _SESSION_TOKEN, _CURRENT_USER
    _SESSION_TOKEN = token
    _CURRENT_USER = user


def clear_session():
    set_session(None, None)


def current_user():
    return _CURRENT_USER or {}


def current_permission_keys():
    return {item.get("key") for item in (_CURRENT_USER or {}).get("permissions", []) if item.get("key")}


def login(username, password):
    user = _request("POST", "/auth/login", {"username": username, "password": password})
    set_session(user.get("session_token"), user)
    return user


def register(username, password, role="Cashier", display_name=None):
    return _request(
        "POST",
        "/auth/register",
        {
            "username": username,
            "password": password,
            "role": role,
            "display_name": display_name,
        },
    )


def list_users():
    return _request("GET", "/users")


def create_user(payload):
    return _request("POST", "/users", payload)


def update_user(user_id, payload):
    return _request("PUT", f"/users/{user_id}", payload)


def reset_user_password(user_id, password):
    return _request("POST", f"/users/{user_id}/reset-password", {"password": password})


def get_user_tasks(user_id):
    return _request("GET", f"/users/{user_id}/tasks")


def update_user_tasks(user_id, permissions):
    return _request("PUT", f"/users/{user_id}/tasks", {"permissions": permissions})


def list_roles():
    return _request("GET", "/roles")


def create_role(payload):
    return _request("POST", "/roles", payload)


def update_role(role_id, payload):
    return _request("PUT", f"/roles/{urllib.parse.quote(str(role_id))}", payload)


def get_role_permissions(role_id):
    return _request("GET", f"/roles/{urllib.parse.quote(str(role_id))}/permissions")


def update_role_permissions(role_id, permissions):
    return _request("PUT", f"/roles/{urllib.parse.quote(str(role_id))}/permissions", {"permissions": permissions})


def list_permissions():
    return _request("GET", "/permissions")


def create_permission(payload):
    return _request("POST", "/permissions", payload)


def update_permission(permission_id, payload):
    return _request("PUT", f"/permissions/{permission_id}", payload)


def delete_permission(permission_id):
    return _request("DELETE", f"/permissions/{permission_id}")


def get_dashboard_overview():
    return _request("GET", "/dashboard/overview")


def list_inventory(search=None, floor=None):
    return _request("GET", "/inventory", params={"search": search, "floor": floor})


def get_products(search=None, category=None):
    rows = list_inventory(search=search)
    if category and category != "All Categories":
        rows = [row for row in rows if (row.get("category") or "") == category]
    return rows


def get_inventory_item(item_id):
    return _request("GET", f"/inventory/{item_id}")


def create_inventory_item(payload):
    return _request("POST", "/inventory", payload)


def update_inventory_item(item_id, payload):
    return _request("PUT", f"/inventory/{item_id}", payload)


def delete_inventory_item(item_id):
    return _request("DELETE", f"/inventory/{item_id}")


def restock_inventory_item(item_id, amount):
    return _request("POST", f"/inventory/{item_id}/restock", {"amount": amount})


def receive_stock_grn(item_id, supplier_name, quantity_received, condition="Good", date_received=None, notes=None):
    return _request("POST", "/inventory/grn", {
        "item_id": item_id,
        "supplier_name": supplier_name,
        "quantity_received": quantity_received,
        "condition": condition,
        "date_received": date_received,
        "notes": notes,
    })


def stock_out_inventory_item(item_id, amount):
    return _request("POST", f"/inventory/{item_id}/stock-out", {"amount": amount})


def list_orders(status=None, exclude_status=None):
    return _request("GET", "/orders", params={"status": status, "exclude_status": exclude_status})


def list_available_orders():
    return _request("GET", "/orders/available")


def get_order(order_id):
    return _request("GET", f"/orders/{order_id}")


def create_order(payload):
    return _request("POST", "/orders", payload)


def update_order_status(order_id, status_value):
    return _request("PUT", f"/orders/{order_id}/status", {"status": status_value})


def update_order_notes(order_id, notes):
    return _request("PUT", f"/orders/{order_id}/notes", {"notes": notes})


def checkout_pos(payload):
    return _request("POST", "/pos/checkout", payload)


def get_dispatch_queue(status=None):
    return _request("GET", "/dispatch/queue", params={"status_filter": status})


def update_dispatch_item(order_id, item_id, status_value, picked_quantity=None, actor=None):
    return _request(
        "PUT",
        f"/dispatch/{order_id}/items/{item_id}",
        {"status": status_value, "picked_quantity": picked_quantity, "actor": actor},
    )


def list_payments(search=None, status=None):
    return _request("GET", "/payments", params={"search": search, "status": status})


def get_payments_summary():
    return _request("GET", "/payments/summary")


def create_payment(payload):
    return _request("POST", "/payments", payload)


def get_payment(payment_id):
    return _request("GET", f"/payments/{payment_id}")


def record_payment(payment_id, amount_paid, note=None, payment_method=None, recorded_by=None):
    return _request(
        "POST",
        f"/payments/{payment_id}/record",
        {
            "amount_paid": amount_paid,
            "note": note,
            "payment_method": payment_method,
            "recorded_by": recorded_by,
        },
    )


def get_payment_history(payment_id):
    return _request("GET", f"/payments/{payment_id}/history")


def list_invoices(search=None):
    return _request("GET", "/invoices", params={"search": search})


def create_invoice(payload):
    return _request("POST", "/invoices", payload)


def get_invoice(invoice_id):
    return _request("GET", f"/invoices/{invoice_id}")


def get_invoice_html(invoice_id):
    return _request("GET", f"/invoices/{invoice_id}/html", expect_json=False)


def cancel_invoice(invoice_id, reason, actor=None):
    return _request("POST", f"/invoices/{invoice_id}/cancel", {"reason": reason, "actor": actor})


def list_customers(search=None):
    return _request("GET", "/customers", params={"search": search})


def create_customer(payload):
    return _request("POST", "/customers", payload)


def get_customer(customer_id):
    return _request("GET", f"/customers/{urllib.parse.quote(str(customer_id))}")


def update_customer(customer_id, payload):
    return _request("PUT", f"/customers/{urllib.parse.quote(str(customer_id))}", payload)


def get_customer_balance(customer_id_or_name):
    return _request("GET", f"/customers/{urllib.parse.quote(str(customer_id_or_name))}/balance")


def update_customer_balance(customer_id, amount_paid):
    return _request(
        "PUT",
        f"/customers/{urllib.parse.quote(str(customer_id))}/balance",
        {"amount_paid": amount_paid},
    )


def get_balance_customers():
    return _request("GET", "/balance/customers")


def get_balance_summary():
    return _request("GET", "/balance/summary")


def get_sales_report(date_from=None, date_to=None):
    return _request("GET", "/reports/sales", params={"date_from": date_from, "date_to": date_to})


def get_orders_report(date_from=None, date_to=None):
    return _request("GET", "/reports/orders", params={"date_from": date_from, "date_to": date_to})


def get_payments_report(date_from=None, date_to=None):
    return _request("GET", "/reports/payments", params={"date_from": date_from, "date_to": date_to})

def get_stock_movements(item_id):
    return _request("GET", f"/inventory/{item_id}/movements")

def get_all_stock_movements():
    return _request("GET", "/stock-movements")