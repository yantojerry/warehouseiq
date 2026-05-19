import hashlib
import os
import re
import secrets
import sqlite3
from pathlib import Path

from backend.auth.permission_catalog import PERMISSIONS
from backend.auth.roles import ROLE_ADMIN, ROLE_SUPER_ADMIN, SYSTEM_ROLES, canonical_role


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
DB_PATH = Path(os.getenv("WAREHOUSEIQ_DB_PATH", Path(__file__).resolve().parent.parent / "warehouse.db"))
_SCHEMA_VERIFIED = False

SAMPLE_ITEMS = [
    ("ITM-001", "Cement Bag 40kg", "Construction", 1, 50, 10, 280.00),
    ("ITM-002", "Steel Bar 10mm", "Construction", 2, 30, 5, 150.00),
    ("ITM-003", "GI Wire Roll", "Hardware", 2, 20, 5, 320.00),
]


def _load_powershell_env_file():
    if not ENV_PATH.exists():
        return
    pattern = re.compile(r'^\s*\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"(.*)"\s*$')
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match and match.group(1) not in os.environ:
            os.environ[match.group(1)] = match.group(2)


_load_powershell_env_file()


def _db_backend():
    return os.getenv("WAREHOUSEIQ_DB_BACKEND", "sqlite").strip().lower()


def _using_mysql():
    return _db_backend() in {"mysql", "mariadb"}


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


class MySQLCursor:
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
        query = _translate_query(query, "mysql")
        self._cursor.execute(query, tuple(params or ()))
        return self

    def executemany(self, query, seq_of_params):
        query = _translate_query(query, "mysql")
        self._cursor.executemany(query, seq_of_params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()


class MySQLConnection:
    dialect = "mysql"

    def __init__(self):
        try:
            import mysql.connector
        except ImportError as exc:
            raise RuntimeError(
                "MySQL mode needs mysql-connector-python. Run: python -m pip install -r requirements.txt"
            ) from exc

        config = {
            "host": os.getenv("WAREHOUSEIQ_DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("WAREHOUSEIQ_DB_PORT", "3307")),
            "user": os.getenv("WAREHOUSEIQ_DB_USER", "root"),
            "password": os.getenv("WAREHOUSEIQ_DB_PASSWORD", ""),
            "autocommit": False,
        }
        database = os.getenv("WAREHOUSEIQ_DB_NAME", "warehouseiq")
        try:
            self._conn = mysql.connector.connect(**config)
        except mysql.connector.Error:
            if config["host"] in {"127.0.0.1", "localhost"} and config["port"] == 3307:
                config["port"] = 3306
                self._conn = mysql.connector.connect(**config)
            else:
                raise
        cursor = self._conn.cursor()
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute(f"USE `{database}`")
        finally:
            cursor.close()
        self._conn.database = database

    def cursor(self, dictionary=False):
        return MySQLCursor(self._conn.cursor(dictionary=dictionary), dictionary=dictionary)

    def execute(self, query, params=None):
        cursor = self._conn.cursor()
        cursor.execute(_translate_query(query, "mysql"), tuple(params or ()))
        return cursor

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


SQLiteConnection.dialect = "sqlite"


def _translate_query(query, dialect="sqlite"):
    if dialect == "mysql":
        return _translate_mysql_query(query)
    translated = (query or "").replace("INSERT " + "IGNORE", "INSERT " + "OR IGNORE").replace("%s", "?")
    translated = translated.replace("AUTO_INCREMENT", "AUTOINCREMENT")
    translated = translated.replace("id INT PRIMARY KEY AUTOINCREMENT", "id INTEGER PRIMARY KEY AUTOINCREMENT")
    translated = translated.replace("NOW()", "CURRENT_TIMESTAMP")
    translated = translated.replace("CURDATE()", "DATE('now')")
    return translated


def _translate_mysql_query(query):
    translated = query or ""
    translated = translated.replace("?", "%s")
    translated = translated.replace("INSERT OR IGNORE", "INSERT IGNORE")
    translated = translated.replace("DATE('now')", "CURDATE()")
    translated = translated.replace("id INTEGER PRIMARY KEY AUTOINCREMENT", "id INT PRIMARY KEY AUTO_INCREMENT")
    translated = translated.replace("id INTEGER PRIMARY KEY AUTO_INCREMENT", "id INT PRIMARY KEY AUTO_INCREMENT")
    translated = translated.replace("key TEXT PRIMARY KEY", "`key` VARCHAR(120) PRIMARY KEY")
    translated = translated.replace("WHERE key =", "WHERE `key` =")
    translated = translated.replace("(key, value, updated_at)", "(`key`, value, updated_at)")
    translated = translated.replace("CREATE INDEX IF NOT EXISTS", "CREATE INDEX")
    translated = _mysql_convert_create_table(translated)
    return translated


def _mysql_convert_create_table(query):
    if "CREATE TABLE" not in query.upper():
        return query
    replacements = {
        "username TEXT": "username VARCHAR(50)",
        "password_hash TEXT": "password_hash VARCHAR(255)",
        "display_name TEXT": "display_name VARCHAR(120)",
        "role TEXT": "role VARCHAR(50)",
        "status TEXT": "status VARCHAR(50)",
        "last_login_at TEXT": "last_login_at DATETIME",
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP": "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP": "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        "expires_at TEXT": "expires_at DATETIME",
        "revoked_at TEXT": "revoked_at DATETIME",
        "item_code TEXT": "item_code VARCHAR(50)",
        "item_name TEXT": "item_name VARCHAR(255)",
        "category TEXT": "category VARCHAR(100)",
        "image_data TEXT": "image_data LONGTEXT",
        "order_number TEXT": "order_number VARCHAR(50)",
        "customer_name TEXT": "customer_name VARCHAR(255)",
        "dispatch_status TEXT": "dispatch_status VARCHAR(50)",
        "total_amount REAL": "total_amount DOUBLE",
        "payment_method TEXT": "payment_method VARCHAR(50)",
        "created_by TEXT": "created_by VARCHAR(50)",
        "pick_status TEXT": "pick_status VARCHAR(50)",
        "unit_price REAL": "unit_price DOUBLE",
        "invoice_number TEXT": "invoice_number VARCHAR(50)",
        "amount_paid REAL": "amount_paid DOUBLE",
        "cancel_reason TEXT": "cancel_reason TEXT",
        "cancelled_by TEXT": "cancelled_by VARCHAR(50)",
        "cancelled_at TEXT": "cancelled_at DATETIME",
        "issued_at TEXT DEFAULT CURRENT_TIMESTAMP": "issued_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "payment_status TEXT": "payment_status VARCHAR(50)",
        "recorded_by TEXT": "recorded_by VARCHAR(50)",
        "paid_at TEXT DEFAULT CURRENT_TIMESTAMP": "paid_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "full_name TEXT": "full_name VARCHAR(255)",
        "contact_number TEXT": "contact_number VARCHAR(50)",
        "customer_type TEXT": "customer_type VARCHAR(50)",
        "total_purchases REAL": "total_purchases DOUBLE",
        "balance REAL": "balance DOUBLE",
        "actor TEXT": "actor VARCHAR(50)",
        "action TEXT": "action VARCHAR(80)",
        "entity_type TEXT": "entity_type VARCHAR(80)",
        "entity_id TEXT": "entity_id VARCHAR(80)",
        "old_value TEXT": "old_value TEXT",
        "new_value TEXT": "new_value TEXT",
        "name TEXT": "name VARCHAR(60)",
        "permission_key TEXT": "permission_key VARCHAR(120)",
        "label TEXT": "label VARCHAR(120)",
        "module_key TEXT": "module_key VARCHAR(80)",
        "description TEXT": "description TEXT",
        "value TEXT": "value TEXT",
        "token_hash TEXT": "token_hash VARCHAR(128)",
        "reason TEXT": "reason TEXT",
        "reference TEXT": "reference VARCHAR(120)",
        "note TEXT": "note TEXT",
    }
    for old, new in replacements.items():
        query = query.replace(old, new)
    if query.rstrip().endswith(")"):
        query = query.rstrip() + " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    return query


def _table_columns(connection, table):
    cursor = connection.cursor(dictionary=True)
    try:
        if getattr(connection, "dialect", "sqlite") == "mysql":
            cursor.execute(f"SHOW COLUMNS FROM {table}")
            return {row["Field"] for row in cursor.fetchall()}
        cursor.execute(f"PRAGMA table_info({table})")
        return {row["name"] for row in cursor.fetchall()}
    finally:
        cursor.close()


def _add_column(connection, table, column, definition):
    if column not in _table_columns(connection, table):
        cursor = connection.cursor()
        try:
            if getattr(connection, "dialect", "sqlite") == "mysql":
                definition = _mysql_column_definition(column, definition)
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        finally:
            cursor.close()


def _mysql_column_definition(column, definition):
    text = definition
    if "TEXT" in text and ("DEFAULT" in text or column in {"role", "status", "payment_method"}):
        text = text.replace("TEXT", "VARCHAR(80)", 1)
    text = text.replace("REAL", "DOUBLE")
    return text


def _safe_execute_schema(cursor, query, connection):
    try:
        cursor.execute(query)
    except Exception:
        if getattr(connection, "dialect", "sqlite") == "mysql" and "CREATE INDEX" in query.upper():
            return
        raise


def ensure_database_exists():
    if _using_mysql():
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        DB_PATH.touch()


def get_connection():
    ensure_database_exists()
    connection = MySQLConnection() if _using_mysql() else SQLiteConnection(str(DB_PATH))
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
        _ensure_default_admin_account(connection)

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
        _safe_execute_schema(cursor, "CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_id)", connection)
        _safe_execute_schema(cursor, "CREATE INDEX IF NOT EXISTS idx_permissions_module ON permissions(module_key)", connection)
        _safe_execute_schema(cursor, "CREATE INDEX IF NOT EXISTS idx_sessions_hash ON user_sessions(token_hash)", connection)
        if getattr(connection, "dialect", "sqlite") == "sqlite":
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
    if getattr(connection, "dialect", "sqlite") == "mysql":
        _migrate_legacy_user_passwords(connection)


def _migrate_legacy_user_passwords(connection):
    columns = _table_columns(connection, "users")
    if "password" not in columns:
        return
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("ALTER TABLE users MODIFY password VARCHAR(255) NULL")
        cursor.execute("SELECT id, password, password_hash FROM users")
        for row in cursor.fetchall():
            if row.get("password") and not row.get("password_hash"):
                cursor.execute(
                    "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (hash_password(row["password"]), row["id"]),
                )
    finally:
        cursor.close()


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
                    {"settings.view", "users.view", "users.add", "users.add_admin", "users.edit", "users.reset"},
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
        if not cursor.fetchone():
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

    migration_key = "2026_05_admin_user_crud_access"
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT value FROM schema_meta WHERE key = ? LIMIT 1", (migration_key,))
        if not cursor.fetchone():
            cursor.execute("SELECT id FROM roles WHERE name = ? LIMIT 1", (ROLE_ADMIN,))
            admin = cursor.fetchone()
            cursor.execute(
                """
                SELECT id, permission_key
                FROM permissions
                WHERE permission_key IN ('users.view', 'users.add', 'users.add_admin', 'users.edit', 'users.reset')
                """
            )
            permissions = cursor.fetchall()
            if admin:
                for permission in permissions:
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

    migration_key = "2026_05_admin_operations_manager_access"
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT value FROM schema_meta WHERE key = ? LIMIT 1", (migration_key,))
        if not cursor.fetchone():
            admin_permissions = {
                "dashboard.view",
                "settings.view",
                "users.view",
                "users.add",
                "users.add_admin",
                "users.edit",
                "users.reset",
                "products.view",
                "products.add",
                "products.edit",
                "inventory.view",
                "inventory.add",
                "inventory.edit",
                "inventory.update_stock",
                "suppliers.view",
                "dispatch.view",
                "dispatch.update",
                "orders.view",
                "orders.create",
                "orders.update",
                "pos.create_sale",
                "invoices.view",
                "invoices.create",
                "invoices.print",
                "payments.view",
                "payments.manage",
                "customers.view",
                "customers.manage",
                "balance.view",
                "reports.view",
                "reports.financial.generate",
            }

            cursor.execute("SELECT id FROM roles WHERE name = ? LIMIT 1", (ROLE_ADMIN,))
            admin = cursor.fetchone()
            cursor.execute("SELECT id, permission_key FROM permissions")
            permissions = cursor.fetchall()
            if admin:
                for permission in permissions:
                    if permission["permission_key"] not in admin_permissions:
                        continue
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

    migration_key = "2026_05_admin_super_admin_exclusions"
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT value FROM schema_meta WHERE key = ? LIMIT 1", (migration_key,))
        if cursor.fetchone():
            return

        super_admin_only = {
            "settings.manage",
            "roles.manage",
            "permissions.manage",
            "tasks.assign",
            "products.delete",
            "inventory.delete",
            "invoices.cancel",
        }
        cursor.execute("SELECT id FROM roles WHERE name = ? LIMIT 1", (ROLE_ADMIN,))
        admin = cursor.fetchone()
        cursor.execute("SELECT id, permission_key FROM permissions")
        permissions = cursor.fetchall()
        if admin:
            for permission in permissions:
                if permission["permission_key"] not in super_admin_only:
                    continue
                cursor.execute(
                    """
                    INSERT IGNORE INTO role_permissions (role_id, permission_id, is_enabled)
                    VALUES (?, ?, 0)
                    """,
                    (admin["id"], permission["id"]),
                )
                cursor.execute(
                    """
                    UPDATE role_permissions
                    SET is_enabled = 0, updated_at = CURRENT_TIMESTAMP
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


def _ensure_default_admin_account(connection):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE LOWER(username) = 'admin_user' LIMIT 1")
        existing_admin = cursor.fetchone()
        if existing_admin:
            cursor.execute(
                """
                UPDATE users
                SET password_hash = ?, display_name = ?, role = ?, status = 'Active',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (hash_password("admin123"), "ADMIN", ROLE_ADMIN, existing_admin["id"]),
            )
            return

        cursor.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("admin_user", hash_password("admin123"), "ADMIN", ROLE_ADMIN, "Active"),
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
    if getattr(connection, "dialect", "sqlite") == "mysql":
        return
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
