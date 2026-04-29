from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlite3 import Error

from database.connection import get_connection, hash_password


router = APIRouter(prefix="/users", tags=["Users"])


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = None
    role: str = "Sales Staff"
    status: str = "Active"


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


class PasswordReset(BaseModel):
    password: str = Field(..., min_length=1, max_length=255)


USER_SELECT = """
    id, username, display_name, role, status, last_login_at, created_at, updated_at
"""


@router.get("")
def list_users():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(f"SELECT {USER_SELECT} FROM users ORDER BY username ASC")
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch users: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (payload.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Username already exists")
        cursor.execute(
            """
            INSERT INTO users (username, password, password_hash, display_name, role, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.username,
                payload.password,
                hash_password(payload.password),
                payload.display_name or payload.username,
                payload.role,
                payload.status,
            ),
        )
        user_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'create', 'user', ?, ?)
            """,
            ("system", user_id, payload.username),
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
def update_user(user_id: int, payload: UserUpdate):
    provided = getattr(payload, "model_fields_set", None) or getattr(payload, "__fields_set__", set())
    fields = []
    params = []
    for name in ["display_name", "role", "status"]:
        if name in provided:
            fields.append(f"{name} = ?")
            params.append(getattr(payload, name))
    if not fields:
        raise HTTPException(status_code=400, detail="No user fields provided")
    fields.append("updated_at = CURRENT_TIMESTAMP")
    params.append(user_id)

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", tuple(params))
        if cursor._cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'update', 'user', ?, ?)
            """,
            ("system", user_id, ",".join(fields)),
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
def reset_password(user_id: int, payload: PasswordReset):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET password = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.password, hash_password(payload.password), user_id),
        )
        if cursor._cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id)
            VALUES (?, 'reset-password', 'user', ?)
            """,
            ("system", user_id),
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
