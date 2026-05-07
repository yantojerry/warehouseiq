import hashlib
import os
import secrets
import sqlite3
from pathlib import Path

from utils.permission_catalog import PERMISSIONS
from utils.roles import ROLE_ADMIN, ROLE_SUPER_ADMIN, SYSTEM_ROLES, canonical_role


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

    @property
    def rowcount(self):
        return self._cursor.rowcount

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
    translated = (query or "").replace("INSERT " + "IGNORE", "INSERT " + "OR IGNORE").replace("%s", "?")
    translated = translated.replace("AUTO_INCREMENT", "AUTOINCREMENT")
    translated = translated.replace("id INT PRIMARY KEY AUTOINCREMENT", "id INTEGER PRIMARY KEY AUTOINCREMENT")
    translated = translated.replace("NOW()", "CURRENT_TIMESTAMP")
    translated = translated.replace("CURDATE()", "DATE('now')")
    return translated


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
        _ensure_super_admin_account(connection)

        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("admin", hash_password("admin123"), "System Super Admin", ROLE_SUPER_ADMIN, "Active"),
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
                password_hash TEXT,
                display_name TEXT,
                role TEXT NOT NULL DEFAULT 'Cashier',
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
                customer_id INTEGER,
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
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id)
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
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_system INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_key TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'General',
                module_key TEXT,
                description TEXT,
                is_system INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (role_id, permission_id),
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_tasks (
                user_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                assigned_by INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, permission_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                revoked_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity_change INTEGER NOT NULL,
                reason TEXT NOT NULL,
                reference TEXT,
                actor TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES inventory(id)
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_permissions_module ON permissions(module_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_hash ON user_sessions(token_hash)")
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
        _backfill_invoice_customer_ids(connection)
        _ensure_roles_and_permissions(connection)
        _apply_role_permission_migrations(connection)
        _ensure_super_admin_account(connection)
        _repair_payment_history_fk(connection)
        connection.commit()
    finally:
        cursor.close()


def _ensure_columns(connection):
    additions = {
        "users": {
            "password_hash": "TEXT",
            "display_name": "TEXT",
            "role": "TEXT NOT NULL DEFAULT 'Cashier'",
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
            "customer_id": "INTEGER",
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


def _backfill_invoice_customer_ids(connection):
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE invoices i
            JOIN customers c ON c.full_name = i.customer_name
            SET i.customer_id = c.id
            WHERE i.customer_id IS NULL
            """
        )
    except sqlite3.Error:
        cursor.execute(
            """
            UPDATE invoices
            SET customer_id = (
                SELECT c.id
                FROM customers c
                WHERE c.full_name = invoices.customer_name
                LIMIT 1
            )
            WHERE customer_id IS NULL
            """
        )
    finally:
        cursor.close()


def _ensure_roles_and_permissions(connection):
    cursor = connection.cursor(dictionary=True)
    try:
        for role in SYSTEM_ROLES:
            cursor.execute(
                """
                INSERT IGNORE INTO roles (name, description, is_system)
                VALUES (?, ?, 1)
                """,
                (role, f"{role} system role"),
            )

        cursor.execute("SELECT id, role FROM users")
        for row in cursor.fetchall():
            normalized = canonical_role(row.get("role"))
            if normalized and normalized != row.get("role"):
                cursor.execute("UPDATE users SET role = ? WHERE id = ?", (normalized, row["id"]))

        for permission in PERMISSIONS:
            cursor.execute(
                """
                INSERT IGNORE INTO permissions (
                    permission_key, label, category, module_key,
                    description, is_system, sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    permission.key,
                    permission.label,
                    permission.category,
                    permission.module_key,
                    permission.description,
                    permission.is_system,
                    permission.sort_order,
                ),
            )

        cursor.execute("SELECT id, name FROM roles")
        role_ids = {row["name"]: row["id"] for row in cursor.fetchall()}
        cursor.execute("SELECT id, permission_key FROM permissions")
        permission_ids = {row["permission_key"]: row["id"] for row in cursor.fetchall()}

        for permission in PERMISSIONS:
            default_roles = set(permission.default_roles)
            default_roles.add(ROLE_SUPER_ADMIN)
            for role_name in default_roles:
                role_id = role_ids.get(role_name)
                permission_id = permission_ids.get(permission.key)
                if role_id and permission_id:
                    cursor.execute(
                        """
                        INSERT IGNORE INTO role_permissions (role_id, permission_id, is_enabled)
                        VALUES (?, ?, 1)
                        """,
                        (role_id, permission_id),
                    )
    finally:
        cursor.close()


def _set_role_permissions(cursor, role_id, permission_ids, enabled_keys):
    for permission_key, permission_id in permission_ids.items():
        is_enabled = 1 if permission_key in enabled_keys else 0
        cursor.execute(
            """
            INSERT IGNORE INTO role_permissions (role_id, permission_id, is_enabled)
            VALUES (?, ?, ?)
            """,
            (role_id, permission_id, is_enabled),
        )
        cursor.execute(
            """
            UPDATE role_permissions
            SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE role_id = ? AND permission_id = ?
            """,
            (is_enabled, role_id, permission_id),
        )


def _apply_role_permission_migrations(connection):
    migration_key = "2026_05_super_admin_role_defaults"
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT value FROM schema_meta WHERE key = ? LIMIT 1", (migration_key,))
        if not cursor.fetchone():
            cursor.execute("SELECT id, name FROM roles")
            role_ids = {row["name"]: row["id"] for row in cursor.fetchall()}
            cursor.execute("SELECT id, permission_key FROM permissions")
            permission_ids = {row["permission_key"]: row["id"] for row in cursor.fetchall()}

            for permission in PERMISSIONS:
                cursor.execute(
                    """
                    UPDATE permissions
                    SET label = ?, category = ?, module_key = ?, description = ?,
                        is_system = ?, sort_order = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE permission_key = ?
                    """,
                    (
                        permission.label,
                        permission.category,
                        permission.module_key,
                        permission.description,
                        permission.is_system,
                        permission.sort_order,
                        permission.key,
                    ),
                )

            super_admin_id = role_ids.get(ROLE_SUPER_ADMIN)
            admin_id = role_ids.get(ROLE_ADMIN)
            if super_admin_id:
                _set_role_permissions(cursor, super_admin_id, permission_ids, set(permission_ids.keys()))
            if admin_id:
                _set_role_permissions(
                    cursor,
                    admin_id,
                    permission_ids,
                    {"settings.view", "users.add", "users.add_admin"},
                )

            cursor.execute(
                """
                INSERT INTO schema_meta (key, value, updated_at)
                VALUES (?, 'applied', CURRENT_TIMESTAMP)
                """,
                (migration_key,),
            )
    finally:
        cursor.close()

    migration_key = "2026_05_admin_user_view_access"
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT value FROM schema_meta WHERE key = ? LIMIT 1", (migration_key,))
        if cursor.fetchone():
            return

        cursor.execute("SELECT id FROM roles WHERE name = ? LIMIT 1", (ROLE_ADMIN,))
        admin = cursor.fetchone()
        cursor.execute("SELECT id FROM permissions WHERE permission_key = 'users.view' LIMIT 1")
        permission = cursor.fetchone()
        if admin and permission:
            cursor.execute(
                """
                INSERT IGNORE INTO role_permissions (role_id, permission_id, is_enabled)
                VALUES (?, ?, 1)
                """,
                (admin["id"], permission["id"]),
            )
            cursor.execute(
                """
                UPDATE role_permissions
                SET is_enabled = 1, updated_at = CURRENT_TIMESTAMP
                WHERE role_id = ? AND permission_id = ?
                """,
                (admin["id"], permission["id"]),
            )

        cursor.execute(
            """
            INSERT INTO schema_meta (key, value, updated_at)
            VALUES (?, 'applied', CURRENT_TIMESTAMP)
            """,
            (migration_key,),
        )
    finally:
        cursor.close()


def _ensure_super_admin_account(connection):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE role = ? LIMIT 1", (ROLE_SUPER_ADMIN,))
        if cursor.fetchone():
            return

        cursor.execute("SELECT id, password_hash FROM users WHERE LOWER(username) = 'admin' LIMIT 1")
        existing_admin = cursor.fetchone()
        if existing_admin:
            cursor.execute(
                """
                UPDATE users
                SET role = ?, status = 'Active', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (ROLE_SUPER_ADMIN, existing_admin["id"]),
            )
            return

        cursor.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("admin", hash_password("admin123"), "System Super Admin", ROLE_SUPER_ADMIN, "Active"),
        )
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
