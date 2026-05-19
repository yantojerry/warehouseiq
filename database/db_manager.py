from database.connection import get_connection, hash_password, verify_password
from backend.auth.roles import ROLE_SUPER_ADMIN


def authenticate_user(username, password):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE username = ? LIMIT 1", (username,))
        user = cursor.fetchone()
        if user and verify_password(password, user.get("password_hash")):
            return user
        return None
    finally:
        cursor.close()
        conn.close()


def get_user_role(username):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT role FROM users WHERE username = ? LIMIT 1", (username,))
        row = cursor.fetchone()
        return row["role"] if row else None
    finally:
        cursor.close()
        conn.close()


def get_connection_summary():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) AS total_items FROM inventory")
        total_items = cursor.fetchone()["total_items"]
        cursor.execute("SELECT COALESCE(SUM(quantity * unit_price), 0) AS total_value FROM inventory")
        total_value = float(cursor.fetchone()["total_value"] or 0)
        cursor.execute("SELECT COUNT(*) AS low_stock FROM inventory WHERE quantity <= low_stock_threshold")
        low_stock = cursor.fetchone()["low_stock"]
        cursor.execute("SELECT COUNT(*) AS total_users FROM users")
        total_users = cursor.fetchone()["total_users"]
        return (
            f"Items: {total_items}\n"
            f"Value: PHP {total_value:,.2f}\n"
            f"Low Stock: {low_stock}\n"
            f"Users: {total_users}"
        )
    finally:
        cursor.close()
        conn.close()


def initialize_db():
    conn = get_connection()
    conn.commit()
    conn.close()


def seed_default_admin():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("admin",))
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("admin", hash_password("admin123"), "System Super Admin", ROLE_SUPER_ADMIN, "Active"),
            )
            conn.commit()
    finally:
        cursor.close()
        conn.close()


def seed_sample_data():
    from database.connection import seed_default_data

    seed_default_data()
