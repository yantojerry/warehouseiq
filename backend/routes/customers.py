from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlite3 import Error

from database.connection import get_connection


router = APIRouter(prefix="/customers", tags=["Customers"])

CustomerType = Literal["Walk-in", "Reseller", "Wholesale"]


class CustomerCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    contact_number: Optional[str] = Field(default=None, max_length=50)
    customer_type: CustomerType = "Walk-in"
    total_purchases: float = Field(default=0.0, ge=0)
    balance: float = Field(default=0.0, ge=0)


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    contact_number: Optional[str] = Field(default=None, max_length=50)
    customer_type: Optional[CustomerType] = None
    total_purchases: Optional[float] = Field(default=None, ge=0)
    balance: Optional[float] = Field(default=None, ge=0)


class CustomerBalancePayment(BaseModel):
    amount_paid: float = Field(..., gt=0)


CUSTOMER_COLUMNS = """
    id, full_name, contact_number, customer_type,
    total_purchases, balance, created_at
"""


def ensure_customers_table():
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                contact_number TEXT,
                customer_type TEXT DEFAULT 'Walk-in',
                total_purchases REAL DEFAULT 0.0,
                balance REAL DEFAULT 0.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _clean_text(value):
    if value is None:
        return None
    value = value.strip()
    return value or None


def _serialize_customer(row):
    if not row:
        return None
    row["total_purchases"] = float(row.get("total_purchases") or 0.0)
    row["balance"] = float(row.get("balance") or 0.0)
    return row


def _provided_fields(payload):
    fields = getattr(payload, "model_fields_set", None)
    if fields is None:
        fields = getattr(payload, "__fields_set__", set())
    return fields


def _fetch_customer(cursor, customer_id: int):
    cursor.execute(
        f"""
        SELECT {CUSTOMER_COLUMNS}
        FROM customers
        WHERE id = %s
        """,
        (customer_id,),
    )
    return _serialize_customer(cursor.fetchone())


@router.get("")
def list_customers(search: Optional[str] = Query(default=None)):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        query = f"SELECT {CUSTOMER_COLUMNS} FROM customers"
        params = []
        if search:
            query += " WHERE full_name LIKE %s OR contact_number LIKE %s OR customer_type LIKE %s"
            like_search = f"%{search}%"
            params.extend([like_search, like_search, like_search])
        query += " ORDER BY full_name ASC"

        cursor.execute(query, tuple(params))
        return [_serialize_customer(row) for row in cursor.fetchall()]
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch customers: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate):
    full_name = _clean_text(payload.full_name)
    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name is required",
        )

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            INSERT INTO customers (
                full_name, contact_number, customer_type, total_purchases, balance
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                full_name,
                _clean_text(payload.contact_number),
                payload.customer_type,
                payload.total_purchases,
                payload.balance,
            ),
        )
        customer_id = cursor.lastrowid
        connection.commit()
        customer = _fetch_customer(cursor, customer_id)
        return {"message": "Customer created successfully", "customer": customer, "id": customer_id}
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create customer: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/{customer_id}")
def get_customer(customer_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        customer = _fetch_customer(cursor, customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )
        return customer
    except HTTPException:
        raise
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch customer: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/{customer_id}")
def update_customer(customer_id: int, payload: CustomerUpdate):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if not _fetch_customer(cursor, customer_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        provided = _provided_fields(payload)
        fields = []
        params = []
        if "full_name" in provided:
            full_name = _clean_text(payload.full_name)
            if not full_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Full name is required",
                )
            fields.append("full_name = %s")
            params.append(full_name)
        if "contact_number" in provided:
            fields.append("contact_number = %s")
            params.append(_clean_text(payload.contact_number))
        if "customer_type" in provided:
            if payload.customer_type is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Customer type is required",
                )
            fields.append("customer_type = %s")
            params.append(payload.customer_type)
        if "total_purchases" in provided:
            if payload.total_purchases is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Total purchases is required",
                )
            fields.append("total_purchases = %s")
            params.append(payload.total_purchases)
        if "balance" in provided:
            if payload.balance is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Balance is required",
                )
            fields.append("balance = %s")
            params.append(payload.balance)

        if not fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No customer fields provided",
            )

        params.append(customer_id)
        cursor.execute(
            f"UPDATE customers SET {', '.join(fields)} WHERE id = %s",
            tuple(params),
        )
        connection.commit()
        return {
            "message": "Customer updated successfully",
            "customer": _fetch_customer(cursor, customer_id),
            "id": customer_id,
        }
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/{customer_id}/balance")
def get_customer_balance(customer_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        customer = _fetch_customer(cursor, customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )
        return {
            "id": customer["id"],
            "full_name": customer["full_name"],
            "balance": customer["balance"],
        }
    except HTTPException:
        raise
    except Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch customer balance: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/{customer_id}/balance")
def update_customer_balance(customer_id: int, payload: CustomerBalancePayment):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        customer = _fetch_customer(cursor, customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        current_balance = float(customer["balance"] or 0.0)
        if payload.amount_paid > current_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment exceeds customer balance",
            )

        new_balance = max(0.0, current_balance - payload.amount_paid)
        cursor.execute(
            "UPDATE customers SET balance = %s WHERE id = %s",
            (new_balance, customer_id),
        )
        connection.commit()
        return {
            "message": "Customer balance updated successfully",
            "id": customer_id,
            "amount_paid": payload.amount_paid,
            "balance": new_balance,
        }
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer balance: {exc}",
        ) from exc
    finally:
        cursor.close()
        connection.close()
