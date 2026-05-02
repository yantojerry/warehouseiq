from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlite3 import Error

from backend.security import create_session, permission_payload_for_user
from database.connection import get_connection, hash_password, verify_password
from utils.roles import ROLE_ADMIN, ROLE_CASHIER, ROLE_SUPER_ADMIN, SYSTEM_ROLES, canonical_role


router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=255)


class RegisterRequest(LoginRequest):
    display_name: Optional[str] = None
    role: str = ROLE_CASHIER


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    role: str = ROLE_CASHIER
    status: str = "Active"
    created_at: Optional[datetime] = None
    session_token: Optional[str] = None
    permissions: list[dict] = []


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, username, password, password_hash, display_name, role, status, created_at
            FROM users
            WHERE username = ?
            """,
            (payload.username,),
        )
        user = cursor.fetchone()
        if not user or not verify_password(payload.password, user.get("password_hash") or user.get("password")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        if user.get("status") == "Inactive":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is inactive. Contact an administrator.",
            )
        if not user.get("password_hash"):
            cursor.execute(
                "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (hash_password(payload.password), user["id"]),
            )
        role = canonical_role(user.get("role") or ROLE_CASHIER)
        if role != user.get("role"):
            cursor.execute(
                "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (role, user["id"]),
            )
        cursor.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"],),
        )
        connection.commit()
        user["role"] = role
        session_token = create_session(user["id"])
        return {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name") or user["username"],
            "role": role,
            "status": user.get("status") or "Active",
            "created_at": user.get("created_at"),
            "session_token": session_token,
            "permissions": permission_payload_for_user(user),
        }
    except HTTPException:
        raise
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to authenticate user: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest):
    role = canonical_role(payload.role or ROLE_CASHIER)
    if role not in SYSTEM_ROLES or role in {ROLE_ADMIN, ROLE_SUPER_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public registration cannot create Admin or Super Admin accounts.",
        )
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE username = ? LIMIT 1", (payload.username,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )
        cursor.execute(
            """
            INSERT INTO users (username, password, password_hash, display_name, role, status)
            VALUES (?, ?, ?, ?, ?, 'Active')
            """,
            (
                payload.username,
                payload.password,
                hash_password(payload.password),
                payload.display_name or payload.username,
                role,
            ),
        )
        connection.commit()
        user_id = cursor.lastrowid
        cursor.execute(
            """
            SELECT id, username, display_name, role, status, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        )
        return cursor.fetchone()
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register user: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()
