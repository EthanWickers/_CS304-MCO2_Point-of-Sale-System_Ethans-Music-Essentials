from dataclasses import dataclass, field
from typing import Optional
import db as db_module


@dataclass
class Product:
    id:           int
    name:         str
    price:        float
    quantity:     int
    sku:          str
    brand:        str
    product_type: str
    image_path:   Optional[str]   = None   
    image_blob:   Optional[bytes] = None   

    @staticmethod
    def from_row(row):
        if not row:
            return None
        keys = row.keys()
        return Product(
            id           = row["id"],
            name         = row["name"],
            price        = row["price"],
            quantity     = row["quantity"],
            sku          = row["sku"],
            brand        = row["brand"],
            product_type = row["product_type"],
            image_path   = row["image_path"] if "image_path" in keys else None,
            image_blob   = row["image_blob"] if "image_blob" in keys else None,
        )


def get_all_products():
    conn = db_module.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM products ORDER BY name COLLATE NOCASE ASC")
    rows = c.fetchall()
    conn.close()
    return [Product.from_row(r) for r in rows]


def get_product_by_sku(sku):
    row = db_module.get_product_by_sku(sku)
    return Product.from_row(row)


def get_product_by_id(pid):
    row = db_module.get_product_by_id(pid)
    return Product.from_row(row)