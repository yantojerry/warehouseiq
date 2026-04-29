import hashlib
import os
import secrets
import sqlite3
from pathlib import Path


DB_PATH = Path(os.getenv("WAREHOUSEIQ_DB_PATH", Path(__file__).resolve().parent.parent / "warehouse.db"))
_SCHEMA_VERIFIED = False

SAMPLE_ITEMS = [
    ("ITM-001", "Cement Bag 40kg", "Construction", 1, 50, 10, 280.00),
    ("ITM-002", "Steel Bar 10mm", "Construction", 2, 30, 5, 150.00),
    ("ITM-003", "GI Wire Roll", "Hardware", 2, 20, 5, 320.00),
]


def hash_password(password):
    text = password or ""
    if text.startswith("pbkdf2_sha256$"):
        return text
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", text.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password, stored):
    stored = stored or ""
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, salt, digest = stored.split("$", 2)
        except ValueError:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            (password or "").encode("utf-8"),
            salt.encode("utf-8"),
            120000,
        ).hex()
        return secrets.compare_digest(candidate, digest)
    return secrets.compare_digest(password or "", stored)


class SQLiteCursor:
    def __init__(self, cursor, dictionary=False):
        self._cursor = cursor
        self._dictionary = dictionary

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def execute(self, query, params=None):
        query = _translate_query(query)
        self._cursor.execute(query, tuple(params or ()))
        return self

    def executemany(self, query, seq_of_params):
        query = _translate_query(query)
        self._cursor.executemany(query, seq_of_params)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return self._convert(row)

    def fetchall(self):
        return [self._convert(row) for row in self._cursor.fetchall()]

    def close(self):
        self._cursor.close()

    def _convert(self, row):
        if row is None:
            return None
        if self._dictionary:
            return dict(row)
        return tuple(row)


class SQLiteConnection:
    def __init__(self, path):
        self._conn = sqlite3.connect(path, timeout=20)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def cursor(self, dictionary=False):
        return SQLiteCursor(self._conn.cursor(), dictionary=dictionary)

    def execute(self, query, params=None):
        return self._conn.execute(_translate_query(query), tuple(params or ()))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _translate_query(query):
    return (query or "").replace("%s", "?")


def _table_columns(connection, table):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        return {row["name"] for row in cursor.fetchall()}
    finally:
        cursor.close()


def _add_column(connection, table, column, definition):
    if column not in _table_columns(connection, table):
        cursor = connection.cursor()
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        finally:
            cursor.close()


def ensure_database_exists():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        DB_PATH.touch()


def get_connection():
    ensure_database_exists()
    connection = SQLiteConnection(str(DB_PATH))
    global _SCHEMA_VERIFIED
    if not _SCHEMA_VERIFIED:
        _ensure_schema(connection)
        _SCHEMA_VERIFIED = True
    return connection


def initialize_database():
    connection = get_connection()
    connection.commit()
    connection.close()


def seed_default_data():
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                """
                INSERT INTO users (username, password, password_hash, display_name, role, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("admin", "admin123", hash_password("admin123"), "System Admin", "Admin", "Active"),
            )

        cursor.execute("SELECT COUNT(*) FROM inventory")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                """
                INSERT INTO inventory (
                    item_code, item_name, category, floor,
                    quantity, low_stock_threshold, unit_price
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                SAMPLE_ITEMS,
            )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def fetch_inventory_item(item_id):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, item_code, item_name, category, floor, quantity,
                   low_stock_threshold, unit_price, image_data, is_active,
                   created_at, updated_at
            FROM inventory
            WHERE id = ?
            """,
            (item_id,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def _ensure_schema(connection):
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT,
                password_hash TEXT,
                display_name TEXT,
                role TEXT NOT NULL DEFAULT 'Sales Staff',
                status TEXT NOT NULL DEFAULT 'Active',
                last_login_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT NOT NULL UNIQUE,
                item_name TEXT NOT NULL,
                category TEXT,
                floor INTEGER NOT NULL DEFAULT 1,
                quantity INTEGER NOT NULL DEFAULT 0,
                low_stock_threshold INTEGER DEFAULT 5,
                unit_price REAL NOT NULL DEFAULT 0.0,
                image_data TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT NOT NULL UNIQUE,
                customer_name TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                dispatch_status TEXT NOT NULL DEFAULT 'Pending',
                total_amount REAL DEFAULT 0.0,
                payment_method TEXT,
                notes TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                pick_status TEXT NOT NULL DEFAULT 'Pending',
                picked_quantity INTEGER NOT NULL DEFAULT 0,
                is_substitute INTEGER DEFAULT 0,
                substitute_approved INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (item_id) REFERENCES inventory(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL UNIQUE,
                order_id INTEGER,
                customer_name TEXT NOT NULL,
                total_amount REAL NOT NULL,
                amount_paid REAL DEFAULT 0.0,
                payment_method TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                cancel_reason TEXT,
                cancelled_by TEXT,
                cancelled_at TEXT,
                issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                invoice_id INTEGER,
                customer_name TEXT NOT NULL,
                total_amount REAL NOT NULL,
                amount_paid REAL NOT NULL DEFAULT 0.0,
                payment_method TEXT,
                payment_status TEXT DEFAULT 'Partial',
                recorded_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id INTEGER NOT NULL,
                invoice_id INTEGER,
                amount_paid REAL NOT NULL,
                payment_method TEXT,
                note TEXT,
                recorded_by TEXT,
                paid_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (payment_id) REFERENCES payments(id)
            )
            """
        )
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
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                reason TEXT,
                old_value TEXT,
                new_value TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS inventory_updated_at
            AFTER UPDATE ON inventory
            FOR EACH ROW
            WHEN NEW.updated_at = OLD.updated_at
            BEGIN
                UPDATE inventory SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
            """
        )
        _ensure_columns(connection)
        _repair_payment_history_fk(connection)
        _upgrade_legacy_passwords(connection)
        connection.commit()
    finally:
        cursor.close()


def _ensure_columns(connection):
    additions = {
        "users": {
            "password": "TEXT",
            "password_hash": "TEXT",
            "display_name": "TEXT",
            "role": "TEXT NOT NULL DEFAULT 'Sales Staff'",
            "status": "TEXT NOT NULL DEFAULT 'Active'",
            "last_login_at": "TEXT",
            "updated_at": "TEXT",
        },
        "inventory": {
            "image_data": "TEXT",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
        },
        "orders": {
            "dispatch_status": "TEXT NOT NULL DEFAULT 'Pending'",
            "payment_method": "TEXT",
            "created_by": "TEXT",
        },
        "order_items": {
            "pick_status": "TEXT NOT NULL DEFAULT 'Pending'",
            "picked_quantity": "INTEGER NOT NULL DEFAULT 0",
            "updated_at": "TEXT",
        },
        "invoices": {
            "payment_method": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'Pending'",
            "cancel_reason": "TEXT",
            "cancelled_by": "TEXT",
            "cancelled_at": "TEXT",
            "updated_at": "TEXT",
        },
        "payments": {
            "invoice_id": "INTEGER",
            "payment_method": "TEXT",
            "recorded_by": "TEXT",
        },
        "payment_history": {
            "invoice_id": "INTEGER",
            "payment_method": "TEXT",
            "recorded_by": "TEXT",
        },
        "customers": {
            "updated_at": "TEXT",
        },
    }
    for table, columns in additions.items():
        for column, definition in columns.items():
            _add_column(connection, table, column, definition)


def _upgrade_legacy_passwords(connection):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, password, password_hash, display_name, username FROM users")
        rows = cursor.fetchall()
        for row in rows:
            updates = []
            params = []
            if not row.get("password_hash") and row.get("password"):
                updates.append("password_hash = ?")
                params.append(hash_password(row["password"]))
            if not row.get("display_name"):
                updates.append("display_name = ?")
                params.append(str(row.get("username") or "User").replace("_", " ").title())
            if updates:
                params.append(row["id"])
                cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", tuple(params))
    finally:
        cursor.close()


def _repair_payment_history_fk(connection):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("PRAGMA foreign_key_list(payment_history)")
        refs = cursor.fetchall()
        if not any(row.get("table") == "payments_legacy" for row in refs):
            return
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_history_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id INTEGER NOT NULL,
                invoice_id INTEGER,
                amount_paid REAL NOT NULL,
                payment_method TEXT,
                note TEXT,
                recorded_by TEXT,
                paid_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (payment_id) REFERENCES payments(id)
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO payment_history_new (
                id, payment_id, invoice_id, amount_paid, payment_method, note, recorded_by, paid_at
            )
            SELECT id, payment_id, invoice_id, amount_paid, payment_method, note, recorded_by, paid_at
            FROM payment_history
            """
        )
        cursor.execute("DROP TABLE payment_history")
        cursor.execute("ALTER TABLE payment_history_new RENAME TO payment_history")
    finally:
        cursor.close()
