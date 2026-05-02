import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlite3 import Error

from backend.security import current_user_from_request
from database.connection import get_connection
from utils.roles import ROLE_SUPER_ADMIN, SYSTEM_ROLES, canonical_role, is_super_admin


router = APIRouter(tags=["Roles"])


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=60)
    description: Optional[str] = None


class PermissionCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    permission_key: Optional[str] = Field(None, max_length=120)
    category: str = Field("General", min_length=1, max_length=80)
    module_key: Optional[str] = Field(None, max_length=80)
    description: Optional[str] = None


class PermissionUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=120)
    permission_key: Optional[str] = Field(None, max_length=120)
    category: Optional[str] = Field(None, min_length=1, max_length=80)
    module_key: Optional[str] = Field(None, max_length=80)
    description: Optional[str] = None


class RolePermissionUpdate(BaseModel):
    permission_id: int
    is_enabled: bool = True


class RolePermissionPayload(BaseModel):
    permissions: list[RolePermissionUpdate]


def _clean_text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _permission_key(value, fallback_label):
    key = _clean_text(value)
    if not key:
        slug = re.sub(r"[^a-z0-9]+", ".", fallback_label.lower()).strip(".")
        key = f"custom.{slug or 'task'}"
    key = key.lower()
    if not re.match(r"^[a-z0-9_.-]+$", key):
        raise HTTPException(status_code=400, detail="Permission key can only contain letters, numbers, dots, underscores, and hyphens.")
    return key


def _unique_permission_key(cursor, key):
    candidate = key
    index = 2
    while True:
        cursor.execute("SELECT id FROM permissions WHERE permission_key = ? LIMIT 1", (candidate,))
        if not cursor.fetchone():
            return candidate
        candidate = f"{key}.{index}"
        index += 1


def _role_by_ref(cursor, role_ref):
    ref = str(role_ref or "").strip()
    if ref.isdigit():
        cursor.execute("SELECT * FROM roles WHERE id = ? LIMIT 1", (int(ref),))
    else:
        normalized = canonical_role(ref)
        cursor.execute(
            "SELECT * FROM roles WHERE LOWER(name) = LOWER(?) LIMIT 1",
            (normalized or ref,),
        )
    role = cursor.fetchone()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


def _permission_by_id(cursor, permission_id):
    cursor.execute("SELECT * FROM permissions WHERE id = ? LIMIT 1", (permission_id,))
    permission = cursor.fetchone()
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    return permission


def _role_payload(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row.get("description"),
        "is_system": bool(row.get("is_system")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _permission_payload(row, enabled=None):
    payload = {
        "id": row["id"],
        "permission_key": row["permission_key"],
        "key": row["permission_key"],
        "label": row["label"],
        "category": row.get("category") or "General",
        "module_key": row.get("module_key"),
        "description": row.get("description"),
        "is_system": bool(row.get("is_system")),
        "sort_order": row.get("sort_order") or 0,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
    if enabled is not None:
        payload["is_enabled"] = bool(enabled)
    return payload


@router.get("/roles")
def list_roles():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT r.*, COUNT(rp.permission_id) AS permission_rows
            FROM roles r
            LEFT JOIN role_permissions rp ON rp.role_id = r.id AND rp.is_enabled = 1
            GROUP BY r.id
            ORDER BY r.is_system DESC, r.name ASC
            """
        )
        rows = []
        for row in cursor.fetchall():
            payload = _role_payload(row)
            payload["enabled_permissions"] = row.get("permission_rows") or 0
            rows.append(payload)
        return rows
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch roles: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleCreate, request: Request):
    actor = current_user_from_request(request)
    name = canonical_role(payload.name)
    if name in SYSTEM_ROLES:
        raise HTTPException(status_code=400, detail="That system role already exists.")
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM roles WHERE LOWER(name) = LOWER(?) LIMIT 1", (name,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Role already exists")
        cursor.execute(
            """
            INSERT INTO roles (name, description, is_system)
            VALUES (?, ?, 0)
            """,
            (name, _clean_text(payload.description)),
        )
        role_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'create', 'role', ?, ?)
            """,
            (actor.get("username"), role_id, name),
        )
        connection.commit()
        cursor.execute("SELECT * FROM roles WHERE id = ?", (role_id,))
        return _role_payload(cursor.fetchone())
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create role: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/roles/{role_ref}")
def update_role(role_ref: str, payload: RoleUpdate, request: Request):
    actor = current_user_from_request(request)
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        role = _role_by_ref(cursor, role_ref)
        fields = []
        params = []
        provided = getattr(payload, "model_fields_set", None) or getattr(payload, "__fields_set__", set())
        if "name" in provided and payload.name:
            if role.get("is_system"):
                raise HTTPException(status_code=400, detail="System role names cannot be changed.")
            fields.append("name = ?")
            params.append(canonical_role(payload.name))
        if "description" in provided:
            fields.append("description = ?")
            params.append(_clean_text(payload.description))
        if not fields:
            raise HTTPException(status_code=400, detail="No role fields provided")
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(role["id"])
        cursor.execute(f"UPDATE roles SET {', '.join(fields)} WHERE id = ?", tuple(params))
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'update', 'role', ?, ?)
            """,
            (actor.get("username"), role["id"], ",".join(fields)),
        )
        connection.commit()
        cursor.execute("SELECT * FROM roles WHERE id = ?", (role["id"],))
        return _role_payload(cursor.fetchone())
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update role: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/roles/{role_ref}/permissions")
def get_role_permissions(role_ref: str):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        role = _role_by_ref(cursor, role_ref)
        cursor.execute(
            """
            SELECT p.*, COALESCE(rp.is_enabled, 0) AS role_enabled
            FROM permissions p
            LEFT JOIN role_permissions rp
              ON rp.permission_id = p.id
             AND rp.role_id = ?
            ORDER BY p.category ASC, p.sort_order ASC, p.label ASC
            """,
            (role["id"],),
        )
        permissions = []
        for row in cursor.fetchall():
            enabled = True if role["name"] == ROLE_SUPER_ADMIN else bool(row.get("role_enabled"))
            permissions.append(_permission_payload(row, enabled=enabled))
        return {"role": _role_payload(role), "permissions": permissions}
    except HTTPException:
        raise
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch role permissions: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/roles/{role_ref}/permissions")
def update_role_permissions(role_ref: str, payload: RolePermissionPayload, request: Request):
    actor = current_user_from_request(request)
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        role = _role_by_ref(cursor, role_ref)
        cursor.execute("SELECT id FROM permissions")
        valid_ids = {row["id"] for row in cursor.fetchall()}
        requested = {item.permission_id: bool(item.is_enabled) for item in payload.permissions}
        missing = set(requested) - valid_ids
        if missing:
            raise HTTPException(status_code=400, detail="One or more permissions do not exist.")

        if role["name"] == ROLE_SUPER_ADMIN:
            requested = {permission_id: True for permission_id in valid_ids}

        for permission_id, is_enabled in requested.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id, is_enabled)
                VALUES (?, ?, ?)
                """,
                (role["id"], permission_id, 1 if is_enabled else 0),
            )
            cursor.execute(
                """
                UPDATE role_permissions
                SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE role_id = ? AND permission_id = ?
                """,
                (1 if is_enabled else 0, role["id"], permission_id),
            )

        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'update-permissions', 'role', ?, ?)
            """,
            (actor.get("username"), role["id"], role["name"]),
        )
        connection.commit()
        return get_role_permissions(str(role["id"]))
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update role permissions: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/permissions")
def list_permissions():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM permissions ORDER BY category ASC, sort_order ASC, label ASC")
        return [_permission_payload(row) for row in cursor.fetchall()]
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch permissions: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.post("/permissions", status_code=status.HTTP_201_CREATED)
def create_permission(payload: PermissionCreate, request: Request):
    actor = current_user_from_request(request)
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        key = _unique_permission_key(cursor, _permission_key(payload.permission_key, payload.label))
        cursor.execute("SELECT COALESCE(MAX(sort_order), 0) AS sort_order FROM permissions")
        sort_order = int(cursor.fetchone().get("sort_order") or 0) + 10
        cursor.execute(
            """
            INSERT INTO permissions (
                permission_key, label, category, module_key,
                description, is_system, sort_order
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (
                key,
                payload.label.strip(),
                payload.category.strip(),
                _clean_text(payload.module_key),
                _clean_text(payload.description),
                sort_order,
            ),
        )
        permission_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'create', 'permission', ?, ?)
            """,
            (actor.get("username"), permission_id, key),
        )
        connection.commit()
        cursor.execute("SELECT * FROM permissions WHERE id = ?", (permission_id,))
        return _permission_payload(cursor.fetchone())
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create permission: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/permissions/{permission_id}")
def update_permission(permission_id: int, payload: PermissionUpdate, request: Request):
    actor = current_user_from_request(request)
    provided = getattr(payload, "model_fields_set", None) or getattr(payload, "__fields_set__", set())
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        permission = _permission_by_id(cursor, permission_id)
        fields = []
        params = []
        if "permission_key" in provided and payload.permission_key:
            if permission.get("is_system"):
                raise HTTPException(status_code=400, detail="System permission keys cannot be changed.")
            fields.append("permission_key = ?")
            params.append(_permission_key(payload.permission_key, permission["label"]))
        if "label" in provided and payload.label:
            fields.append("label = ?")
            params.append(payload.label.strip())
        if "category" in provided and payload.category:
            fields.append("category = ?")
            params.append(payload.category.strip())
        if "module_key" in provided:
            fields.append("module_key = ?")
            params.append(_clean_text(payload.module_key))
        if "description" in provided:
            fields.append("description = ?")
            params.append(_clean_text(payload.description))
        if not fields:
            raise HTTPException(status_code=400, detail="No permission fields provided")
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(permission_id)
        cursor.execute(f"UPDATE permissions SET {', '.join(fields)} WHERE id = ?", tuple(params))
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'update', 'permission', ?, ?)
            """,
            (actor.get("username"), permission_id, ",".join(fields)),
        )
        connection.commit()
        cursor.execute("SELECT * FROM permissions WHERE id = ?", (permission_id,))
        return _permission_payload(cursor.fetchone())
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update permission: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.delete("/permissions/{permission_id}")
def delete_permission(permission_id: int, request: Request):
    actor = current_user_from_request(request)
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        permission = _permission_by_id(cursor, permission_id)
        if permission["permission_key"] == "settings.view" or permission.get("is_system"):
            raise HTTPException(status_code=400, detail="Built-in permissions are protected. Disable them for a role instead.")
        cursor.execute("DELETE FROM permissions WHERE id = ?", (permission_id,))
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, old_value)
            VALUES (?, 'delete', 'permission', ?, ?)
            """,
            (actor.get("username"), permission_id, permission["permission_key"]),
        )
        connection.commit()
        return {"message": "Permission deleted", "id": permission_id}
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete permission: {exc}") from exc
    finally:
        cursor.close()
        connection.close()
