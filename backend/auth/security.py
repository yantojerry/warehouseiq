# Owns authentication sessions and permission enforcement.

import hashlib
import re
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from mysql.connector import Error

from database.connection import get_connection
from backend.auth.permission_catalog import PERMISSIONS
from backend.auth.roles import ROLE_ADMIN, ROLE_SUPER_ADMIN, canonical_role, is_super_admin


PUBLIC_PATHS = {"/", "/health", "/openapi.json", "/docs", "/redoc", "/favicon.ico"}
PUBLIC_PREFIXES = ("/docs/", "/redoc/", "/auth/login", "/auth/register")

PERMISSION_RULES = (
    ("GET", r"^/dashboard/overview/?$", "dashboard.view"),
    ("GET", r"^/roles/?$", "roles.manage"),
    ("POST", r"^/roles/?$", "roles.manage"),
    ("PUT", r"^/roles/[^/]+/?$", "roles.manage"),
    ("GET", r"^/roles/[^/]+/permissions/?$", "permissions.manage"),
    ("PUT", r"^/roles/[^/]+/permissions/?$", "tasks.assign"),
    ("GET", r"^/permissions/?$", "permissions.manage"),
    ("POST", r"^/permissions/?$", "permissions.manage"),
    ("PUT", r"^/permissions/\d+/?$", "permissions.manage"),
    ("DELETE", r"^/permissions/\d+/?$", "permissions.manage"),
    ("GET", r"^/users/?$", "users.view"),
    ("POST", r"^/users/?$", ("users.add", "users.add_admin")),
    ("PUT", r"^/users/\d+/?$", "users.edit"),
    ("POST", r"^/users/\d+/reset-password/?$", "users.reset"),
    ("GET", r"^/users/\d+/tasks/?$", "tasks.assign"),
    ("PUT", r"^/users/\d+/tasks/?$", "tasks.assign"),
    ("GET", r"^/inventory(?:/\d+)?/?$", ("inventory.view", "products.view", "pos.create_sale", "orders.create", "products.add", "inventory.add")),
    ("POST", r"^/inventory/?$", ("inventory.add", "products.add")),
    ("PUT", r"^/inventory/\d+/?$", ("inventory.edit", "products.edit")),
    ("DELETE", r"^/inventory/\d+/?$", ("inventory.delete", "products.delete")),
    ("POST", r"^/inventory/\d+/restock/?$", "inventory.update_stock"),
    ("POST", r"^/inventory/\d+/stock-out/?$", "inventory.update_stock"),
    ("GET", r"^/orders/?$", "orders.view"),
    ("GET", r"^/orders/available/?$", ("orders.view", "payments.manage", "invoices.create")),
    ("GET", r"^/orders/\d+/?$", "orders.view"),
    ("POST", r"^/orders/?$", "orders.create"),
    ("PUT", r"^/orders/\d+/status/?$", ("orders.update", "dispatch.update")),
    ("PUT", r"^/orders/\d+/notes/?$", ("orders.update", "dispatch.update")),
    ("POST", r"^/pos/checkout/?$", "pos.create_sale"),
    ("GET", r"^/dispatch/queue/?$", "dispatch.view"),
    ("PUT", r"^/dispatch/\d+/items/\d+/?$", "dispatch.update"),
    ("GET", r"^/payments(?:/\d+)?/?$", "payments.view"),
    ("GET", r"^/payments/summary/?$", "payments.view"),
    ("GET", r"^/payments/\d+/history/?$", "payments.view"),
    ("POST", r"^/payments/?$", "payments.manage"),
    ("POST", r"^/payments/\d+/record/?$", "payments.manage"),
    ("GET", r"^/invoices(?:/\d+)?/?$", "invoices.view"),
    ("GET", r"^/invoices/\d+/html/?$", ("invoices.print", "invoices.view")),
    ("POST", r"^/invoices/?$", "invoices.create"),
    ("POST", r"^/invoices/\d+/cancel/?$", "invoices.cancel"),
    ("GET", r"^/customers(?:/\d+)?/?$", "customers.view"),
    ("GET", r"^/customers/\d+/balance/?$", "customers.view"),
    ("POST", r"^/customers/?$", "customers.manage"),
    ("PUT", r"^/customers/\d+/?$", "customers.manage"),
    ("PUT", r"^/customers/\d+/balance/?$", "customers.manage"),
    ("GET", r"^/balance/.+/?$", "balance.view"),
    ("GET", r"^/reports/.+/?$", ("reports.view", "reports.financial.generate")),
)


def token_hash(token):
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=8)
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO user_sessions (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
            """,
            (user_id, token_hash(token), expires_at.strftime("%Y-%m-%d %H:%M:%S")),
        )
        connection.commit()
        return token
    finally:
        cursor.close()
        connection.close()


def is_public_path(path):
    clean_path = path.rstrip("/") or "/"
    if clean_path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def resolve_required_permission(method, path):
    clean_path = path.rstrip("/") or "/"
    for rule_method, pattern, permission in PERMISSION_RULES:
        if method.upper() == rule_method and re.match(pattern, clean_path):
            return permission
    return None


def _authorization_token(request):
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def user_from_token(token):
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT u.id, u.username, u.display_name, u.role, u.status
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?
              AND s.revoked_at IS NULL
              AND (s.expires_at IS NULL OR s.expires_at > CURRENT_TIMESTAMP)
            LIMIT 1
            """,
            (token_hash(token),),
        )
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
        if user.get("status") == "Inactive":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive")
        user["role"] = canonical_role(user.get("role"))
        return user
    finally:
        cursor.close()
        connection.close()


def current_user_from_request(request):
    if hasattr(request.state, "current_user"):
        return request.state.current_user
    return user_from_token(_authorization_token(request))


def effective_permission_keys(user_id, role):
    role = canonical_role(role)
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if is_super_admin(role):
            cursor.execute("SELECT permission_key FROM permissions ORDER BY sort_order ASC, label ASC")
            return {row["permission_key"] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT p.permission_key
            FROM roles r
            JOIN role_permissions rp ON rp.role_id = r.id
            JOIN permissions p ON p.id = rp.permission_id
            WHERE r.name = ? AND rp.is_enabled = 1
            """,
            (role,),
        )
        permissions = {row["permission_key"] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT p.permission_key, ut.is_enabled
            FROM user_tasks ut
            JOIN permissions p ON p.id = ut.permission_id
            WHERE ut.user_id = ?
            """,
            (user_id,),
        )
        for row in cursor.fetchall():
            if int(row.get("is_enabled") or 0):
                permissions.add(row["permission_key"])
            else:
                permissions.discard(row["permission_key"])
        if role == ROLE_ADMIN:
            permissions.add("users.view")
        permissions.add("settings.view")
        return permissions
    finally:
        cursor.close()
        connection.close()


def has_permission(user, required):
    if required is None:
        return True
    role = canonical_role(user.get("role"))
    if is_super_admin(role):
        return True
    if required == "settings.view":
        return True
    required_keys = required if isinstance(required, (tuple, list, set)) else (required,)
    permissions = effective_permission_keys(user["id"], role)
    return any(key in permissions for key in required_keys)


def require_permission(user, required):
    if has_permission(user, required):
        return True
    if isinstance(required, (tuple, list, set)):
        label = " or ".join(required)
    else:
        label = str(required)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Permission required: {label}",
    )


def can_assign_role(actor, target_role):
    role = canonical_role(target_role)
    if role == ROLE_SUPER_ADMIN:
        return False
    if is_super_admin(actor.get("role")):
        return True
    if role == ROLE_ADMIN:
        return has_permission(actor, "users.add_admin")
    return has_permission(actor, "users.add")


def permission_payload_for_user(user):
    keys = effective_permission_keys(user["id"], user.get("role"))
    labels = {permission.key: permission.label for permission in PERMISSIONS}
    return [
        {"key": key, "label": labels.get(key, key)}
        for key in sorted(keys)
    ]


async def permission_middleware(request, call_next):
    if request.method.upper() == "OPTIONS" or is_public_path(request.url.path):
        return await call_next(request)
    try:
        user = user_from_token(_authorization_token(request))
        request.state.current_user = user
        require_permission(user, resolve_required_permission(request.method, request.url.path))
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    except Error as exc:
        return JSONResponse(status_code=500, content={"detail": f"Authorization failed: {exc}"})
    return await call_next(request)
