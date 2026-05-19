# Owns version 1 user management API endpoints.

from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlite3 import Error

from backend.auth.security import can_assign_role, current_user_from_request
from database.connection import get_connection, hash_password
from backend.auth.roles import ROLE_CASHIER, ROLE_SUPER_ADMIN, canonical_role, is_super_admin


router = APIRouter(prefix="/users", tags=["Users"])


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = None
    role: str = ROLE_CASHIER
    status: str = "Active"


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


class PasswordReset(BaseModel):
    password: str = Field(..., min_length=1, max_length=255)


class UserTaskUpdate(BaseModel):
    permission_id: int
    is_enabled: bool = True


class UserTaskPayload(BaseModel):
    permissions: list[UserTaskUpdate]


USER_SELECT = """
    id, username, display_name, role, status, last_login_at, created_at, updated_at
"""


def _role_exists(cursor, role):
    cursor.execute("SELECT id FROM roles WHERE LOWER(name) = LOWER(?) LIMIT 1", (role,))
    return bool(cursor.fetchone())


def _user_by_id(cursor, user_id):
    cursor.execute(f"SELECT {USER_SELECT} FROM users WHERE id = ? LIMIT 1", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["role"] = canonical_role(user.get("role"))
    return user


@router.get("")
def list_users(request: Request):
    actor = current_user_from_request(request)
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if is_super_admin(actor.get("role")):
            cursor.execute(f"SELECT {USER_SELECT} FROM users ORDER BY username ASC")
        else:
            cursor.execute(
                f"""
                SELECT {USER_SELECT}
                FROM users
                WHERE LOWER(role) != LOWER(?)
                ORDER BY username ASC
                """,
                (ROLE_SUPER_ADMIN,),
            )
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch users: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, request: Request):
    actor = current_user_from_request(request)
    role = canonical_role(payload.role or ROLE_CASHIER)
    if not can_assign_role(actor, role):
        raise HTTPException(status_code=403, detail=f"You cannot create a {role} account.")
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if not _role_exists(cursor, role):
            raise HTTPException(status_code=400, detail="Selected role does not exist")
        cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (payload.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Username already exists")
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.username,
                hash_password(payload.password),
                payload.display_name or payload.username,
                role,
                payload.status,
            ),
        )
        user_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'create', 'user', ?, ?)
            """,
            (actor.get("username"), user_id, payload.username),
        )
        connection.commit()
        return {"message": "User created", "id": user_id}
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create user: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/{user_id}")
def update_user(user_id: int, payload: UserUpdate, request: Request):
    actor = current_user_from_request(request)
    provided = getattr(payload, "model_fields_set", None) or getattr(payload, "__fields_set__", set())
    fields = []
    params = []
    for name in ["display_name", "role", "status"]:
        if name in provided:
            if name == "role" and payload.role:
                payload.role = canonical_role(payload.role)
            fields.append(f"{name} = ?")
            params.append(getattr(payload, name))
    if not fields:
        raise HTTPException(status_code=400, detail="No user fields provided")
    fields.append("updated_at = CURRENT_TIMESTAMP")
    params.append(user_id)

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        existing_user = _user_by_id(cursor, user_id)
        if existing_user.get("role") == ROLE_SUPER_ADMIN and not is_super_admin(actor.get("role")):
            raise HTTPException(status_code=403, detail="You cannot manage a Super Admin account.")
        if "role" in provided and payload.role and payload.role != existing_user.get("role"):
            if not can_assign_role(actor, payload.role):
                raise HTTPException(status_code=403, detail=f"You cannot assign the {payload.role} role.")
        if "role" in provided and payload.role and not _role_exists(cursor, payload.role):
            raise HTTPException(status_code=400, detail="Selected role does not exist")
        cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", tuple(params))
        if cursor._cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'update', 'user', ?, ?)
            """,
            (actor.get("username"), user_id, ",".join(fields)),
        )
        connection.commit()
        return {"message": "User updated", "id": user_id}
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update user: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, payload: PasswordReset, request: Request):
    actor = current_user_from_request(request)
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        existing_user = _user_by_id(cursor, user_id)
        if existing_user.get("role") == ROLE_SUPER_ADMIN and not is_super_admin(actor.get("role")):
            raise HTTPException(status_code=403, detail="You cannot reset a Super Admin account.")
        cursor.execute(
            """
            UPDATE users
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (hash_password(payload.password), user_id),
        )
        if cursor._cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id)
            VALUES (?, 'reset-password', 'user', ?)
            """,
            (actor.get("username"), user_id),
        )
        connection.commit()
        return {"message": "Password reset", "id": user_id}
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset password: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/{user_id}/tasks")
def list_user_tasks(user_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        user = _user_by_id(cursor, user_id)
        role = user.get("role")
        cursor.execute(
            """
            SELECT p.*,
                   COALESCE(rp.is_enabled, 0) AS role_enabled,
                   ut.is_enabled AS user_enabled
            FROM permissions p
            LEFT JOIN roles r ON LOWER(r.name) = LOWER(?)
            LEFT JOIN role_permissions rp
              ON rp.role_id = r.id
             AND rp.permission_id = p.id
            LEFT JOIN user_tasks ut
              ON ut.permission_id = p.id
             AND ut.user_id = ?
            ORDER BY p.category ASC, p.sort_order ASC, p.label ASC
            """,
            (role, user_id),
        )
        rows = []
        for row in cursor.fetchall():
            role_enabled = True if role == ROLE_SUPER_ADMIN else bool(row.get("role_enabled"))
            override = row.get("user_enabled")
            effective = role_enabled if override is None else bool(override)
            if role == ROLE_SUPER_ADMIN:
                effective = True
            rows.append(
                {
                    "id": row["id"],
                    "permission_key": row["permission_key"],
                    "key": row["permission_key"],
                    "label": row["label"],
                    "category": row.get("category") or "General",
                    "module_key": row.get("module_key"),
                    "description": row.get("description"),
                    "is_system": bool(row.get("is_system")),
                    "role_enabled": role_enabled,
                    "user_override": None if override is None else bool(override),
                    "is_enabled": effective,
                }
            )
        return {"user": user, "permissions": rows}
    except HTTPException:
        raise
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch user tasks: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/{user_id}/tasks")
def update_user_tasks(user_id: int, payload: UserTaskPayload, request: Request):
    actor = current_user_from_request(request)
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        user = _user_by_id(cursor, user_id)
        if user.get("role") == ROLE_SUPER_ADMIN:
            raise HTTPException(status_code=400, detail="Super Admin always has all permissions.")

        cursor.execute("SELECT id FROM permissions")
        valid_ids = {row["id"] for row in cursor.fetchall()}
        requested = {item.permission_id: bool(item.is_enabled) for item in payload.permissions}
        if set(requested) - valid_ids:
            raise HTTPException(status_code=400, detail="One or more permissions do not exist.")

        cursor.execute("DELETE FROM user_tasks WHERE user_id = ?", (user_id,))
        for permission_id, is_enabled in requested.items():
            cursor.execute(
                """
                INSERT INTO user_tasks (user_id, permission_id, is_enabled, assigned_by)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, permission_id, 1 if is_enabled else 0, actor.get("id")),
            )

        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'update-tasks', 'user', ?, ?)
            """,
            (actor.get("username"), user_id, user.get("username")),
        )
        connection.commit()
        return {"message": "User tasks updated", "id": user_id}
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update user tasks: {exc}") from exc
    finally:
        cursor.close()
        connection.close()
