"""
Business logic layer — sits between the UI windows and db.py.

Rules:
  - Functions here may read/write the database.
  - Functions here must NOT import tkinter or touch any UI widget.
  - UI windows call these functions and handle the results themselves.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

import db as db_module
import config


# >>>>> Validation >>>>>
def validate_product_fields(
    name: str,
    price_str: str,
    qty_str: str,
    sku: str
) -> tuple:
    """
    Validate common product fields shared by Add and Edit forms.
    Returns (price: float, qty: int) on success.
    Raises ValueError with a human-readable message on failure.
    """
    if not name:
        raise ValueError("Name is required.")
    if not sku:
        raise ValueError("SKU is required.")
    try:
        price = float(price_str)
    except ValueError:
        raise ValueError(f"Price must be a number, got: '{price_str}'")
    if price < 0:
        raise ValueError("Price cannot be negative.")
    try:
        qty = int(qty_str)
    except ValueError:
        raise ValueError(f"Quantity must be a whole number, got: '{qty_str}'")
    if qty < 0:
        raise ValueError("Quantity cannot be negative.")
    return price, qty


# >>>>>>> Checkout data structures >>>>>>>

@dataclass
class StockError:
    name: str
    sku: str
    requested: int
    available: int


@dataclass
class SaleResult:
    sale_id: int
    subtotal: float          
    discount_pct: float      
    discount_amount: float   
    tax_amount: float        
    total: float             
    paid: float              
    change: float            
    customer_name: str = ""
    items: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""
    payment_method: str = "Cash"   
    reference_no: str = ""         
    display_currency: str = "PHP"  
    exchange_rate: float = 1.0     


# >>>>>>> Stock check >>>>>>>
def check_stock(cart: List[Dict[str, Any]]) -> List[StockError]:
    errors = []
    for item in cart:
        live = db_module.get_live_stock(item["sku"])
        if item["qty"] > live:
            errors.append(StockError(
                name=item["name"],
                sku=item["sku"],
                requested=item["qty"],
                available=live
            ))
    return errors


# >>>>>>> Sale processing >>>>>>>
def process_sale(
    cart: List[Dict[str, Any]],
    paid: float,
    discount_pct: float = 0.0,
    username: str = "unknown",
    customer_name: str = "",
    payment_method: str = "Cash",
    reference_no: str = "",
    display_currency: str = "PHP",
    exchange_rate: float = 1.0,
) -> SaleResult:
    """
    Commit a completed sale to the database.

    All monetary values (paid, totals) are in PHP (base currency).
    display_currency / exchange_rate are stored for receipt formatting only.

    discount_pct — percentage off the subtotal (0–100).
    payment_method — "Cash", "Card", or "GCash".
    reference_no   — optional card/GCash transaction reference.

    Raises ValueError if paid < total.
    Always call check_stock() before calling this.
    """
    tax_rate = config.get_tax_rate()

    subtotal = sum(item["price"] * item["qty"] for item in cart)

    discount_pct = max(0.0, min(discount_pct, 100.0))
    discount_amount = round(subtotal * (discount_pct / 100.0), 2)

    taxable = subtotal - discount_amount
    tax_amount = round(taxable * tax_rate, 2)
    total = round(taxable + tax_amount, 2)

    if paid < total - 0.005:          
        raise ValueError(
            f"Amount paid ({_fmt(paid)}) is less than total ({_fmt(total)})."
        )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sale_id = db_module.record_sale(
        total,
        customer_name=customer_name or None,
        payment_method=payment_method,
        reference_no=reference_no,
    )

    for item in cart:
        db_module.record_sale_item(
            sale_id,
            item["sku"],
            item["name"],
            float(item["price"]),
            int(item["qty"])
        )
        row = db_module.get_product_by_sku(item["sku"])
        if row:
            db_module.update_product_by_sku(
                item["sku"],
                quantity=row["quantity"] - item["qty"]
            )

    customer_label = customer_name.strip() if customer_name.strip() else "Walk-in"
    db_module.log_action(
        username, "SALE",
        f"Sale #{sale_id}  total {_fmt(total)}  "
        f"method: {payment_method}  items: {len(cart)}  customer: {customer_label}"
    )

    return SaleResult(
        sale_id=sale_id,
        subtotal=subtotal,
        discount_pct=discount_pct,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        total=total,
        paid=paid,
        change=round(paid - total, 2),
        customer_name=customer_name.strip(),
        items=list(cart),
        timestamp=timestamp,
        payment_method=payment_method,
        reference_no=reference_no.strip(),
        display_currency=display_currency,
        exchange_rate=exchange_rate,
    )


# >>>>>>> Receipt >>>>>>>
def build_receipt_text(result: SaleResult) -> str:
    """
    Build a plain-text receipt string.

    If result.display_currency == "USD", all amounts are shown in USD
    (converted via result.exchange_rate) and a PHP equivalent line is
    appended for record-keeping.
    """
    shop = config.get_shop_name()
    w    = 40

    # >>>>> Currency helpers >>>>>
    php_sym = config.get_currency_symbol()
    if result.display_currency == "USD":
        sym  = "$"
        rate = result.exchange_rate if result.exchange_rate > 0 else 1.0
        def cv(php_amt: float) -> float:
            return php_amt / rate
    else:
        sym  = php_sym
        rate = 1.0
        def cv(php_amt: float) -> float:
            return php_amt

    # >>> Header >>>
    lines = [
        shop.center(w),
        "=" * w,
        f"Sale ID  : #{result.sale_id}",
        f"Date     : {result.timestamp}",
    ]
    if result.customer_name:
        lines.append(f"Customer : {result.customer_name}")

    lines.append(f"Payment  : {result.payment_method}")
    if result.reference_no:
        lines.append(f"Ref #    : {result.reference_no}")

    if result.display_currency == "USD":
        lines.append(f"Currency : USD  (1 USD = {php_sym}{rate:,.2f})")

    lines.append("-" * w)

    # >>>>> Items >>>>>
    for item in result.items:
        sub = cv(item["price"] * item["qty"])
        lines.append(f"  {item['name'][:24]:<24} x{item['qty']}")
        lines.append(f"  {sym}{cv(item['price']):>8,.2f}        {sym}{sub:>8,.2f}")

    lines += [
        "-" * w,
        f"{'Subtotal':<20} {sym}{cv(result.subtotal):>10,.2f}",
    ]

    if result.discount_pct > 0:
        lines.append(
            f"{'Discount (' + str(round(result.discount_pct, 2)) + '%)':<20}"
            f"-{sym}{cv(result.discount_amount):>9,.2f}"
        )

    tax_rate = config.get_tax_rate()
    if tax_rate > 0:
        pct = round(tax_rate * 100, 2)
        lines.append(
            f"{'Tax (' + str(pct) + '%)':<20} {sym}{cv(result.tax_amount):>10,.2f}"
        )

    lines += [
        f"{'TOTAL':<20} {sym}{cv(result.total):>10,.2f}",
        f"{'Paid':<20} {sym}{cv(result.paid):>10,.2f}",
        f"{'Change':<20} {sym}{cv(result.change):>10,.2f}",
    ]

    if result.display_currency == "USD":
        lines.append(f"{'PHP Equiv. Total':<20} {php_sym}{result.total:>10,.2f}")

    lines += [
        "=" * w,
        "Thank you for your purchase!".center(w),
    ]

    return "\n".join(lines)


def save_receipt(result: SaleResult) -> str:
    receipts_dir = os.path.join(db_module._DIR, "receipts")
    os.makedirs(receipts_dir, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"receipt_{result.sale_id}_{ts}.txt"
    path     = os.path.join(receipts_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_receipt_text(result))
    return path


def save_receipt_text(text: str, sale_id) -> str:
    """Save an arbitrary receipt text string and return the file path."""
    receipts_dir = os.path.join(db_module._DIR, "receipts")
    os.makedirs(receipts_dir, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(receipts_dir, f"receipt_{sale_id}_{ts}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def print_receipt(text: str) -> tuple:
    """
    Print receipt text via Windows notepad /p (silent print to default printer).
    Works for both thermal receipt printers and regular inkjet/laser printers —
    set the target printer as the Windows default printer before printing.
    Returns (success: bool, message: str).
    """
    import subprocess
    import tempfile
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        tmp.write(text)
        tmp.close()
        subprocess.Popen(["notepad", "/p", tmp.name], shell=True)
        return True, "Sent to printer successfully."
    except Exception as e:
        return False, str(e)


def build_receipt_text_from_row(sale_info: dict) -> str:
    """
    Build a full receipt text string from a sales history record dict.
    Used by the Sales History 'View Full Receipt' modal.

    sale_info keys expected:
        sale_id, timestamp, customer_name, payment_method, reference_no,
        display_currency, exchange_rate, total, items (list of dicts with
        name, sku, price, qty keys)
    """
    base_sym = config.get_currency_symbol()
    shop     = config.get_shop_name()
    w        = 40

    display_currency = sale_info.get("display_currency") or "PHP"
    exchange_rate    = sale_info.get("exchange_rate") or 1.0
    rate             = exchange_rate if exchange_rate > 0 else 1.0

    if display_currency == "USD":
        sym = "$"
        def to_disp(php): return php / rate
    else:
        sym = base_sym
        def to_disp(php): return php

    lines = [
        shop.center(w),
        "=" * w,
        f"Sale ID  : #{sale_info.get('sale_id', '?')}",
        f"Date     : {sale_info.get('timestamp', '')}",
    ]

    customer = (sale_info.get("customer_name") or "").strip()
    if customer:
        lines.append(f"Customer : {customer}")

    method = sale_info.get("payment_method") or "Cash"
    lines.append(f"Payment  : {method}")

    ref = (sale_info.get("reference_no") or "").strip()
    if ref:
        lines.append(f"Ref #    : {ref}")

    if display_currency == "USD":
        lines.append(f"Currency : USD  (Rate: 1 USD = {base_sym}{rate:,.2f})")

    lines.append("-" * w)

    subtotal_php = 0.0
    for it in sale_info.get("items", []):
        if not it.get("name"):
            continue
        price_php = it.get("price") or 0.0
        qty       = it.get("qty") or 0
        sub_php   = price_php * qty
        subtotal_php += sub_php
        price_d = to_disp(price_php)
        sub_d   = to_disp(sub_php)
        lines.append(f"  {it['name'][:24]:<24} x{qty}")
        lines.append(f"  {sym}{price_d:>8,.2f}        {sym}{sub_d:>8,.2f}")

    total_php = sale_info.get("total", 0.0)
    total_d   = to_disp(total_php)

    lines += [
        "-" * w,
        f"{'TOTAL':<20} {sym}{total_d:>10,.2f}",
    ]

    if display_currency == "USD":
        lines.append(f"{'≈ PHP':<20} {base_sym}{total_php:>10,.2f}")

    lines += [
        "=" * w,
        "Thank you for your purchase!".center(w),
    ]

    return "\n".join(lines)


# >>>>>>> PDF export >>>>>>>
def export_sales_pdf(rows, date_from: str, date_to: str, dest_path: str):
    """
    Generate a sales history PDF using only Python stdlib (no third-party libs).
    Uses the PDF content stream format directly — no dependencies needed.

    rows      — result of get_full_sales_history() or get_sales_by_date_range()
    date_from / date_to — date strings shown in the report header
    dest_path — full file path to write the PDF to
    """
    shop = config.get_shop_name()
    sym  = config.get_currency_symbol()

    sales: Dict[int, Any] = {}
    for row in rows:
        sid = row["sale_id"]
        if sid not in sales:
            sales[sid] = {
                "timestamp":      row["timestamp"],
                "customer_name":  row["customer_name"] or "",
                "total":          row["total"],
                "payment_method": row["payment_method"] if "payment_method" in row.keys() else "Cash",
                "items":          []
            }
        if row["name"]:
            sales[sid]["items"].append({
                "name":  row["name"],
                "sku":   row["sku"] or "",
                "price": row["price"] or 0.0,
                "qty":   row["quantity"] or 0
            })

    grand_total = sum(s["total"] for s in sales.values())

    # >>> Build PDF content lines >>>
    content_lines = []

    def txt(x, y, size, text, bold=False):
        font = "Helvetica-Bold" if bold else "Helvetica"
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines.append(f"BT /{font} {size} Tf {x} {y} Td ({safe}) Tj ET")

    def hline(y, x1=40, x2=555):
        content_lines.append(f"{x1} {y} m {x2} {y} l S")

    PAGE_H = 842
    MARGIN = 40

    y = PAGE_H - 50

    txt(MARGIN, y, 16, shop, bold=True);       y -= 22
    txt(MARGIN, y, 10, f"Sales Report  |  {date_from}  to  {date_to}"); y -= 14
    txt(MARGIN, y, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"); y -= 8
    hline(y); y -= 16

    txt(MARGIN, y, 9, "Sale ID",   bold=True)
    txt(110,    y, 9, "Date",      bold=True)
    txt(270,    y, 9, "Customer",  bold=True)
    txt(370,    y, 9, "Payment",   bold=True)
    txt(430,    y, 9, "Items",     bold=True)
    txt(470,    y, 9, "Total",     bold=True)
    y -= 6
    hline(y); y -= 14

    for sid, sale in sales.items():
        if y < 80:
            break

        items_count = len(sale["items"])
        customer    = sale["customer_name"] or "Walk-in"
        total_str   = f"{sym}{sale['total']:,.2f}"
        method      = sale.get("payment_method", "Cash")

        txt(MARGIN, y, 9, f"#{sid}")
        txt(110,    y, 9, sale["timestamp"][:16])
        txt(270,    y, 9, customer[:18])
        txt(370,    y, 9, method)
        txt(430,    y, 9, str(items_count))
        txt(470,    y, 9, total_str)
        y -= 13

        for it in sale["items"]:
            if y < 80:
                break
            line = f"    {it['qty']} x {it['name'][:26]}  @ {sym}{it['price']:,.2f}"
            txt(MARGIN + 12, y, 8, line)
            y -= 11

        y -= 4

    hline(y); y -= 14
    txt(MARGIN, y, 10, f"Total sales shown: {len(sales)}", bold=True)
    txt(350,    y, 10, f"Grand Total: {sym}{grand_total:,.2f}", bold=True)

    content = "\n".join(content_lines)
    content_bytes = content.encode("latin-1", errors="replace")

    objects: list[bytes] = []

    def add_obj(s: str) -> int:
        objects.append(s.encode("latin-1", errors="replace"))
        return len(objects)

    add_obj("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj")
    add_obj("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj")
    resources = (
        "/Font << "
        "/Helvetica << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
        "/Helvetica-Bold << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> "
        ">>"
    )
    add_obj(
        f"3 0 obj\n"
        f"<< /Type /Page /Parent 2 0 R "
        f"/MediaBox [0 0 595 842] "
        f"/Contents 4 0 R "
        f"/Resources << {resources} >> >>\n"
        f"endobj"
    )
    add_obj(
        f"4 0 obj\n"
        f"<< /Length {len(content_bytes)} >>\n"
        f"stream\n"
        + content
        + "\nendstream\nendobj"
    )

    header = b"%PDF-1.4\n"
    body_parts = []
    offsets = []
    pos = len(header)
    for obj_bytes in objects:
        offsets.append(pos)
        body_parts.append(obj_bytes)
        pos += len(obj_bytes) + 1

    xref_offset = pos
    xref = [b"xref", f"0 {len(objects) + 1}".encode()]
    xref.append(b"0000000000 65535 f ")
    for off in offsets:
        xref.append(f"{off:010d} 00000 n ".encode())

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()

    with open(dest_path, "wb") as f:
        f.write(header)
        for part in body_parts:
            f.write(part)
            f.write(b"\n")
        f.write(b"\n".join(xref))
        f.write(b"\n")
        f.write(trailer)

def _fmt(amount: float) -> str:
    sym = config.get_currency_symbol()
    return f"{sym}{amount:,.2f}"