import db as db_module

#> Default setting in Settings 
_DEFAULTS = {
    "shop_name":          "Ethan's Music Essentials",
    "currency_symbol":    "P",
    "tax_rate":           "0.0",        
    "low_stock_threshold": "5",         
    "exchange_rate_usd":  "57.00",      
}

def init_settings():
    """
    Create the settings table if it doesn't exist and seed defaults.
    Called once from db.init_db() at startup.
    """
    conn = db_module.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        conn.commit()

        for key, value in _DEFAULTS.items():
            cur.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str) -> str:
    """Return the value for *key*, or an empty string if not found."""
    conn = db_module.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        return row["value"] if row else ""
    finally:
        conn.close()


def set_setting(key: str, value: str):
    """Insert or update *key* with *value*."""
    conn = db_module.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        conn.commit()
    finally:
        conn.close()

def get_shop_name() -> str:
    return get_setting("shop_name") or _DEFAULTS["shop_name"]


def get_currency_symbol() -> str:
    return get_setting("currency_symbol") or _DEFAULTS["currency_symbol"]



def get_tax_rate() -> float:
    """Return tax rate as a float (e.g. 0.12 for 12 %)."""
    try:
        return float(get_setting("tax_rate"))
    except (ValueError, TypeError):
        return 0.0


def get_low_stock_threshold() -> int:
    """Return the quantity at-or-below which a product is considered low stock."""
    try:
        return int(get_setting("low_stock_threshold"))
    except (ValueError, TypeError):
        return 5


def get_exchange_rate_usd() -> float:
    """
    Return the PHP-per-USD exchange rate (e.g. 57.0 means 1 USD = 57 PHP).
    Set manually by the admin in Settings. No internet required.
    """
    try:
        rate = float(get_setting("exchange_rate_usd"))
        return rate if rate > 0 else float(_DEFAULTS["exchange_rate_usd"])
    except (ValueError, TypeError):
        return float(_DEFAULTS["exchange_rate_usd"])