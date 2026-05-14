import sqlite3
import hashlib
import os
import sys
from datetime import datetime


def _get_base_dir() -> str:
    """Return the folder that contains the .exe (frozen) or the script (dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


_DIR = _get_base_dir()
DB_PATH = os.path.join(_DIR, "eme.db")

_PRODUCT_FIELDS = {
    "name", "price", "quantity", "sku", "brand", "product_type",
    "image_path", "image_blob",
}

#> Password Hashing Support
def hash_password(password: str) -> str:
    salt = "eme_pos_salt"
    return hashlib.sha256((salt + password).encode()).hexdigest()

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn



def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL,
                price        REAL    NOT NULL,
                quantity     INTEGER NOT NULL,
                sku          TEXT    UNIQUE NOT NULL,
                brand        TEXT,
                product_type TEXT,
                image_path   TEXT,
                image_blob   BLOB
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                total          REAL    NOT NULL,
                timestamp      DATETIME,
                customer_name  TEXT,
                payment_method TEXT    DEFAULT 'Cash',
                reference_no   TEXT    DEFAULT ''
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id  INTEGER,
                sku      TEXT,
                name     TEXT,
                price    REAL,
                quantity INTEGER,
                FOREIGN KEY(sale_id) REFERENCES sales(id)
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                role     TEXT
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT,
                action    TEXT,
                detail    TEXT,
                timestamp DATETIME
            );
        """)

        conn.commit()

        ensure_sales_timestamp_column(conn)
        ensure_sales_customer_column(conn)
        ensure_sales_payment_columns(conn)
        ensure_product_image_columns(conn)
        remove_legacy_sale_date_column(conn)
        _migrate_plaintext_passwords(conn)
        _seed_default_users(conn)

    finally:
        conn.close()

    from config import init_settings
    init_settings()


def _seed_default_users(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM users")
    if cur.fetchone()["cnt"] == 0:
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin7", hash_password("12777"), "admin")
        )
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("empl3_ethan", hash_password("777"), "cashier")
        )
        conn.commit()


def _migrate_plaintext_passwords(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, password FROM users")
    rows = cur.fetchall()
    for row in rows:
        pw = row["password"] or ""
        if len(pw) != 64:
            cur.execute(
                "UPDATE users SET password=? WHERE id=?",
                (hash_password(pw), row["id"])
            )
    conn.commit()


def ensure_sales_timestamp_column(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(sales);")
    cols = [r["name"] for r in cur.fetchall()]
    if "timestamp" not in cols:
        try:
            cur.execute("ALTER TABLE sales ADD COLUMN timestamp DATETIME;")
            conn.commit()
        except Exception as e:
            print(f"[db] Could not add timestamp column: {e}")
    try:
        cur.execute("""
            UPDATE sales
            SET timestamp = COALESCE(timestamp, datetime('now'))
            WHERE timestamp IS NULL OR timestamp = '';
        """)
        conn.commit()
    except Exception as e:
        print(f"[db] Could not backfill timestamps: {e}")


def ensure_sales_customer_column(conn):
    """Add customer_name column to existing sales tables that don't have it."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(sales);")
    cols = [r["name"] for r in cur.fetchall()]
    if "customer_name" not in cols:
        try:
            cur.execute("ALTER TABLE sales ADD COLUMN customer_name TEXT;")
            conn.commit()
        except Exception as e:
            print(f"[db] Could not add customer_name column: {e}")


def ensure_sales_payment_columns(conn):
    """
    Add payment_method and reference_no columns to existing sales tables.
    Safe to call on fresh or existing databases.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(sales);")
    cols = [r["name"] for r in cur.fetchall()]
    if "payment_method" not in cols:
        try:
            cur.execute(
                "ALTER TABLE sales ADD COLUMN payment_method TEXT DEFAULT 'Cash';"
            )
            conn.commit()
        except Exception as e:
            print(f"[db] Could not add payment_method column: {e}")
    if "reference_no" not in cols:
        try:
            cur.execute(
                "ALTER TABLE sales ADD COLUMN reference_no TEXT DEFAULT '';"
            )
            conn.commit()
        except Exception as e:
            print(f"[db] Could not add reference_no column: {e}")


def remove_legacy_sale_date_column(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(sales);")
    cols = [r["name"] for r in cur.fetchall()]
    if "sale_date" not in cols:
        return
    try:
        cur.execute("""
            CREATE TABLE sales_new (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                total          REAL    NOT NULL,
                timestamp      DATETIME,
                customer_name  TEXT,
                payment_method TEXT    DEFAULT 'Cash',
                reference_no   TEXT    DEFAULT ''
            );
        """)
        cur.execute("""
            INSERT INTO sales_new (id, total, timestamp)
            SELECT id, total, timestamp FROM sales;
        """)
        cur.execute("DROP TABLE sales;")
        cur.execute("ALTER TABLE sales_new RENAME TO sales;")
        conn.commit()
    except Exception as e:
        print(f"[db] Could not remove sale_date column: {e}")


def ensure_product_image_columns(conn):
    """
    Add image_path and image_blob columns to an existing products table.
    Safe to call on a fresh database (columns are already in the schema).
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(products);")
    cols = [r["name"] for r in cur.fetchall()]
    if "image_path" not in cols:
        try:
            cur.execute("ALTER TABLE products ADD COLUMN image_path TEXT;")
            conn.commit()
        except Exception as e:
            print(f"[db] Could not add image_path column: {e}")
    if "image_blob" not in cols:
        try:
            cur.execute("ALTER TABLE products ADD COLUMN image_blob BLOB;")
            conn.commit()
        except Exception as e:
            print(f"[db] Could not add image_blob column: {e}")

# ─── Product CRUD ───
def add_product(
    name, price, quantity, sku, brand, product_type,
    image_path=None, image_blob=None
):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO products
                (name, price, quantity, sku, brand, product_type, image_path, image_blob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, price, quantity, sku, brand, product_type, image_path, image_blob))
        conn.commit()
    finally:
        conn.close()


def update_product(pid, **fields):
    if not fields:
        return
    invalid = set(fields) - _PRODUCT_FIELDS
    if invalid:
        raise ValueError(f"Invalid product field(s): {invalid}")
    keys = [f"{k}=?" for k in fields]
    vals = list(fields.values()) + [pid]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE products SET {', '.join(keys)} WHERE id=?", vals)
        conn.commit()
    finally:
        conn.close()


def delete_product(pid):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit()
    finally:
        conn.close()


def get_product_by_id(pid):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id=?", (pid,))
        return cur.fetchone()
    finally:
        conn.close()


def get_product_by_sku(sku):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE sku=?", (sku,))
        return cur.fetchone()
    finally:
        conn.close()


def update_product_by_sku(sku, **fields):
    if not fields:
        return
    invalid = set(fields) - _PRODUCT_FIELDS
    if invalid:
        raise ValueError(f"Invalid product field(s): {invalid}")
    keys = [f"{k}=?" for k in fields]
    vals = list(fields.values()) + [sku]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE products SET {', '.join(keys)} WHERE sku=?", vals)
        conn.commit()
    finally:
        conn.close()


# -------------------------
# Sales & Sale Items
# -------------------------
def record_sale(
    total,
    customer_name: str = None,
    payment_method: str = "Cash",
    reference_no: str = ""
):
    """
    Insert a new sale record.

    total          — always stored in PHP (base currency).
    payment_method — "Cash", "Card", or "GCash".
    reference_no   — optional card/GCash transaction reference.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """INSERT INTO sales
               (timestamp, total, customer_name, payment_method, reference_no)
               VALUES (?, ?, ?, ?, ?)""",
            (
                local_time,
                total,
                customer_name or None,
                payment_method or "Cash",
                reference_no or ""
            )
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def record_sale_item(sale_id, sku, name, price, qty):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sale_items (sale_id, sku, name, price, quantity)
            VALUES (?, ?, ?, ?, ?)
        """, (sale_id, sku, name, price, qty))
        conn.commit()
    finally:
        conn.close()


def get_full_sales_history():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id            AS sale_id,
                   s.total,
                   s.timestamp,
                   s.customer_name,
                   s.payment_method,
                   s.reference_no,
                   si.sku,
                   si.name,
                   si.price,
                   si.quantity
            FROM sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            ORDER BY s.timestamp DESC, s.id DESC;
        """)
        return cur.fetchall()
    finally:
        conn.close()


def get_sales_by_date_range(date_from: str, date_to: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id            AS sale_id,
                   s.total,
                   s.timestamp,
                   s.customer_name,
                   s.payment_method,
                   s.reference_no,
                   si.sku,
                   si.name,
                   si.price,
                   si.quantity
            FROM sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE date(s.timestamp) >= date(?)
              AND date(s.timestamp) <= date(?)
            ORDER BY s.timestamp DESC, s.id DESC;
        """, (date_from, date_to))
        return cur.fetchall()
    finally:
        conn.close()


def get_daily_summary():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*)  AS tx_count,
                   COALESCE(SUM(total), 0.0) AS revenue
            FROM sales
            WHERE date(timestamp) = date('now');
        """)
        return cur.fetchone()
    finally:
        conn.close()


def get_top_products(limit: int = 5):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT si.name,
                   si.sku,
                   SUM(si.quantity) AS units_sold
            FROM sale_items si
            GROUP BY si.sku
            ORDER BY units_sold DESC
            LIMIT ?;
        """, (limit,))
        return cur.fetchall()
    finally:
        conn.close()


def delete_sale(sale_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM sale_items WHERE sale_id=?", (sale_id,))
        cur.execute("DELETE FROM sales WHERE id=?", (sale_id,))
        conn.commit()
    finally:
        conn.close()


# -------------------------
# Auth
# -------------------------
def verify_user(username: str, password: str):
    hashed = hash_password(password)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, hashed)
        )
        return cur.fetchone()
    finally:
        conn.close()


# -------------------------
# User management
# -------------------------
def get_all_users():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, role FROM users ORDER BY id")
        return cur.fetchall()
    finally:
        conn.close()


def add_user(username: str, password: str, role: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role)
        )
        conn.commit()
    finally:
        conn.close()


def update_user_password(user_id: int, new_password: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET password=? WHERE id=?",
            (hash_password(new_password), user_id)
        )
        conn.commit()
    finally:
        conn.close()


def update_user_role(user_id: int, role: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
        conn.commit()
    finally:
        conn.close()


def delete_user(user_id: int):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
        return cur.fetchone()
    finally:
        conn.close()


# -------------------------
# Audit log
# -------------------------
def log_action(username: str, action: str, detail: str = ""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO audit_log (username, action, detail, timestamp) VALUES (?, ?, ?, ?)",
            (username, action, detail, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
    finally:
        conn.close()


def get_audit_log(limit: int = 200):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT timestamp, username, action, detail
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?;
        """, (limit,))
        return cur.fetchall()
    finally:
        conn.close()


# -------------------------
# Stock helpers
# -------------------------
def get_live_stock(sku: str) -> int:
    row = get_product_by_sku(sku)
    return row["quantity"] if row else 0