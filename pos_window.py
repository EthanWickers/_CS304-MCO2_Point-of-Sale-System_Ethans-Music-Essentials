import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import db as db_module
import services
import config
from models import get_all_products, get_product_by_sku
from base_window import BaseWindow
from image_utils import ImagePreviewPanel, set_icon, resolve_product_image_path
from theme import ROW_EVEN, ROW_ODD, WHITE_BG, PRIMARY, ACCENT


class POSWindow(BaseWindow):
    def __init__(self, master, username: str = "unknown"):
        super().__init__(master, title="Point of Sale", width=1100, height=620)
        self.configure(bg=WHITE_BG, padx=10, pady=10)
        self.username = username
        self.cart     = []
        self.currency = "PHP"       
        set_icon(self, "main")
        self.create_widgets()
        self.load_products()
        self.center()
        self.state("zoomed")

        self.bind("<Return>", lambda _: self.checkout())
        self.bind("<Escape>", lambda _: self.clear_cart())
        self.bind("<F5>",     lambda _: self.load_products())

    # >>> Currency helpers >>> 

    def _sym(self) -> str:
        """Symbol for the active display currency."""
        return "$" if self.currency == "USD" else config.get_currency_symbol()

    def _rate(self) -> float:
        """PHP per 1 USD (from Settings)."""
        return config.get_exchange_rate_usd()

    def _to_disp(self, php: float) -> float:
        """Convert a PHP amount to the display currency."""
        return php / self._rate() if self.currency == "USD" else php

    def _from_disp(self, disp: float) -> float:
        """Convert a display-currency amount back to PHP."""
        return disp * self._rate() if self.currency == "USD" else disp

    # >>>>>>> UI >>>>>>>

    def create_widgets(self):
        left = tk.Frame(self, bg=WHITE_BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right = tk.Frame(self, bg=WHITE_BG, width=385)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        # [1] Scanner row
        scan_row = tk.Frame(left, bg="#dff0fb", padx=8, pady=5)
        scan_row.pack(fill="x", pady=(0, 6))
        tk.Label(
            scan_row, text="📷  Scan / SKU:", bg="#dff0fb",
            font=("Segoe UI", 10, "bold")
        ).pack(side="left")
        self.scan_var = tk.StringVar()
        self.scan_entry = tk.Entry(
            scan_row, textvariable=self.scan_var,
            font=("Segoe UI", 11), bd=1, relief="solid", width=22
        )
        self.scan_entry.pack(side="left", padx=(6, 8), ipady=3)
        self.scan_entry.bind("<Return>", self._scan_return)
        tk.Button(
            scan_row, text="Add  ↵",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.scan_product
        ).pack(side="left")
        tk.Label(
            scan_row,
            text="  Type or scan a product SKU and press Enter to add.",
            bg="#dff0fb", font=("Segoe UI", 9), fg="#446"
        ).pack(side="left", padx=8)

        # [2] Search bar
        top = tk.Frame(left, bg=WHITE_BG)
        top.pack(fill="x", pady=(0, 6))
        tk.Label(top, text="Search:", bg=WHITE_BG).pack(side="left")
        self.search_var = tk.StringVar()
        tk.Entry(top, textvariable=self.search_var, bd=1, relief="solid") \
            .pack(side="left", fill="x", expand=True, padx=6)
        tk.Button(
            top, text="Clear", bg=ACCENT, fg="black", relief="flat",
            command=lambda: self.search_var.set("")
        ).pack(side="left", padx=6)
        self.search_var.trace_add("write", lambda *_: self.apply_filter())

        # [3] Product treeview + image preview (side by side) 
        mid = tk.Frame(left, bg=WHITE_BG)
        mid.pack(fill="both", expand=True)

        # >>> Image panel >>>
        self.img_panel = ImagePreviewPanel(mid, width=210, label_text="")
        self.img_panel.pack(side="right", fill="y")

        tree_container = tk.Frame(mid, bg=WHITE_BG)
        tree_container.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(tree_container, orient="vertical")
        cols = ("sku", "name", "price", "qty")
        self.tree = ttk.Treeview(
            tree_container, columns=cols, show="headings",
            height=16, yscrollcommand=vsb.set
        )
        vsb.config(command=self.tree.yview)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)
        for c in cols:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, anchor="center", width=140 if c != "name" else 380)
        self.tree.tag_configure("odd",  background=ROW_ODD)
        self.tree.tag_configure("even", background=ROW_EVEN)
        self.tree.bind("<Double-1>", lambda _: self.add_to_cart())
        self.tree.bind("<<TreeviewSelect>>", self._on_product_select)

        btns = tk.Frame(left, bg=WHITE_BG)
        btns.pack(fill="x", pady=(8, 4))
        tk.Button(
            btns, text="Add to Cart  [Double-click]",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.add_to_cart
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            btns, text="Refresh  [F5]", bg=ACCENT, fg="black", relief="flat",
            command=self.load_products
        ).pack(side="left")

        # >>>>> RIGHT PANEL >>>>>

        # >>> Currency toggle >>>
        cart_header = tk.Frame(right, bg=WHITE_BG)
        cart_header.pack(fill="x", pady=(0, 4))
        tk.Label(
            cart_header, text="Cart", bg=WHITE_BG, font=("Segoe UI", 12, "bold")
        ).pack(side="left")
        cur_frame = tk.Frame(cart_header, bg=WHITE_BG)
        cur_frame.pack(side="right")
        tk.Label(cur_frame, text="Currency:", bg=WHITE_BG,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.currency_var = tk.StringVar(value="PHP")
        for code in ("PHP", "USD"):
            tk.Radiobutton(
                cur_frame, text=code, variable=self.currency_var, value=code,
                bg=WHITE_BG, font=("Segoe UI", 9, "bold"),
                command=self._on_currency_change
            ).pack(side="left")

        self.rate_label_var = tk.StringVar(value="")
        self.rate_label = tk.Label(
            right, textvariable=self.rate_label_var,
            bg=WHITE_BG, font=("Segoe UI", 8), fg="#777", anchor="e"
        )

        self.cart_list = tk.Listbox(right, height=11)
        self.cart_list.pack(fill="x", pady=(0, 4))

        cart_ops = tk.Frame(right, bg=WHITE_BG)
        cart_ops.pack(fill="x", pady=(0, 6))
        tk.Button(
            cart_ops, text="Remove", bg=ACCENT, fg="black", relief="flat",
            command=self.remove_selected
        ).pack(side="left")
        tk.Button(
            cart_ops, text="Clear  [Esc]", bg=ACCENT, fg="black", relief="flat",
            command=self.clear_cart
        ).pack(side="left", padx=6)
        tk.Button(
            cart_ops, text="Edit Qty", bg=ACCENT, fg="black", relief="flat",
            command=self.edit_qty
        ).pack(side="left")

        # >>> Customer name >>>
        cust_frame = tk.Frame(right, bg=WHITE_BG)
        cust_frame.pack(fill="x", pady=(0, 4))
        tk.Label(cust_frame, text="Customer:", bg=WHITE_BG,
                 font=("Segoe UI", 10)).pack(side="left")
        self.customer_var = tk.StringVar()
        tk.Entry(cust_frame, textvariable=self.customer_var,
                 bd=1, relief="solid").pack(side="left", fill="x", expand=True, padx=6)
        tk.Label(cust_frame, text="(optional)", bg=WHITE_BG,
                 font=("Segoe UI", 9), fg="#888").pack(side="left")

        # >>> Discount >>>
        disc_frame = tk.Frame(right, bg=WHITE_BG)
        disc_frame.pack(fill="x", pady=(0, 4))
        tk.Label(disc_frame, text="Discount:", bg=WHITE_BG,
                 font=("Segoe UI", 10)).pack(side="left")
        self.discount_var = tk.StringVar(value="0")
        tk.Entry(disc_frame, textvariable=self.discount_var,
                 width=8, bd=1, relief="solid").pack(side="left", padx=6)
        tk.Label(disc_frame, text="% off", bg=WHITE_BG,
                 font=("Segoe UI", 10)).pack(side="left")

        # >>> Totals grid >>>
        totals_frame = tk.Frame(right, bg=WHITE_BG)
        totals_frame.pack(fill="x", pady=(4, 6))

        tk.Label(totals_frame, text="Subtotal:", bg=WHITE_BG,
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        self.subtotal_var = tk.StringVar(value="0.00")
        tk.Label(totals_frame, textvariable=self.subtotal_var, bg=WHITE_BG,
                 font=("Segoe UI", 10)).grid(row=0, column=1, sticky="e", padx=(8, 0))

        # >>> Discount row >>>
        self.disc_label = tk.Label(totals_frame, text="Discount:", bg=WHITE_BG,
                                   font=("Segoe UI", 10))
        self.disc_var = tk.StringVar(value="")
        self.disc_value_label = tk.Label(totals_frame, textvariable=self.disc_var,
                                         bg=WHITE_BG, font=("Segoe UI", 10), fg="#c0392b")

        # >>> Tax row >>>
        self.tax_label = tk.Label(totals_frame, text="Tax:", bg=WHITE_BG,
                                  font=("Segoe UI", 10))
        self.tax_var = tk.StringVar(value="0.00")
        self.tax_value_label = tk.Label(totals_frame, textvariable=self.tax_var,
                                        bg=WHITE_BG, font=("Segoe UI", 10))
        if config.get_tax_rate() > 0:
            pct = round(config.get_tax_rate() * 100, 2)
            self.tax_label.config(text=f"Tax ({pct}%):")
            self.tax_label.grid(row=2, column=0, sticky="w")
            self.tax_value_label.grid(row=2, column=1, sticky="e", padx=(8, 0))

        tk.Label(totals_frame, text="TOTAL:", bg=WHITE_BG,
                 font=("Segoe UI", 11, "bold")).grid(row=3, column=0, sticky="w",
                                                      pady=(4, 0))
        self.total_var = tk.StringVar(value="0.00")
        tk.Label(totals_frame, textvariable=self.total_var, bg=WHITE_BG,
                 font=("Segoe UI", 12, "bold")).grid(row=3, column=1, sticky="e",
                                                      padx=(8, 0), pady=(4, 0))

        self.equiv_label = tk.Label(totals_frame, text="≈ PHP:", bg=WHITE_BG,
                                    font=("Segoe UI", 9), fg="#888")
        self.equiv_var = tk.StringVar(value="")
        self.equiv_value_label = tk.Label(totals_frame, textvariable=self.equiv_var,
                                          bg=WHITE_BG, font=("Segoe UI", 9), fg="#888")

        totals_frame.columnconfigure(1, weight=1)
        self._totals_frame = totals_frame

        tk.Button(
            right, text="Checkout  [Enter]",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.checkout
        ).pack(fill="x", pady=(4, 0))

        self.discount_var.trace_add("write", lambda *_: self.refresh_cart_list())

    # >>>>> Currency toggle >>>>>

    def _on_currency_change(self):
        self.currency = self.currency_var.get()
        if self.currency == "USD":
            rate    = self._rate()
            php_sym = config.get_currency_symbol()
            self.rate_label_var.set(f"Rate: 1 USD = {php_sym}{rate:,.2f}  (set in Settings)")
            self.rate_label.pack(fill="x", pady=(0, 4))
        else:
            self.rate_label.pack_forget()
        self.apply_filter()          
        self.refresh_cart_list()     

    # >>>>> Data >>>>>

    def load_products(self):
        self._all = get_all_products()
        self.apply_filter()

    def apply_filter(self):
        q   = (self.search_var.get() or "").lower().strip()
        sym = self._sym()
        self.tree.delete(*self.tree.get_children())
        for idx, p in enumerate(self._all):
            if not q \
               or q in (p.sku   or "").lower() \
               or q in (p.name  or "").lower() \
               or q in (p.brand or "").lower():
                disp_price = self._to_disp(p.price)
                tag = "even" if idx % 2 == 0 else "odd"
                self.tree.insert(
                    "", "end",
                    values=(p.sku, p.name, f"{sym}{disp_price:,.2f}", p.quantity),
                    tags=(tag,)
                )
        self.img_panel.clear()

    # >>>>> Image panel >>>>>

    def _on_product_select(self, event=None):
        """Update the image panel whenever a product row is selected."""
        sel = self.tree.selection()
        if not sel:
            self.img_panel.clear()
            return
        sku = str(self.tree.item(sel[0])["values"][0])
        row = db_module.get_product_by_sku(sku)
        if row:
            self.img_panel.update_image(
                path=resolve_product_image_path(
                    row["image_path"] if "image_path" in row.keys() else None
                ),
                blob=row["image_blob"] if "image_blob" in row.keys() else None,
            )
        else:
            self.img_panel.clear()

    # >>>>> Barcode / SKU scanner >>>>>

    def _scan_return(self, event):
        """
        Called when the user presses Enter inside the scan entry.
        Adds the product to cart and returns "break" to prevent the
        window-level <Return> binding (checkout) from also firing.
        """
        self.scan_product()
        return "break"

    def scan_product(self):
        """
        Resolve the SKU in the scan field, add 1 unit to the cart,
        then clear the field and return focus so the next scan is ready.
        Works with USB HID barcode scanners (which send SKU + Enter).
        """
        sku = self.scan_var.get().strip()
        if not sku:
            return
        product = get_product_by_sku(sku)
        if not product:
            messagebox.showwarning(
                "SKU Not Found",
                f"No product with SKU '{sku}'.\n"
                "Check the label and try again."
            )
            self.scan_var.set("")
            self.scan_entry.focus_set()
            return
        if product.quantity <= 0:
            messagebox.showwarning(
                "Out of Stock",
                f"'{product.name}' is currently out of stock."
            )
            self.scan_var.set("")
            self.scan_entry.focus_set()
            return
        self._add_to_cart_internal(product.sku, product.name, product.price, qty=1)
        self.scan_var.set("")
        self.scan_entry.focus_set()

    # >>>>> Cart >>>>>

    def add_to_cart(self):
        """Add the selected product from the treeview (asks for quantity)."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Add", "Select a product first.")
            return

        sku          = str(self.tree.item(sel[0])["values"][0])
        displayed_qty = int(self.tree.item(sel[0])["values"][3])

        product = get_product_by_sku(sku)
        if not product:
            messagebox.showerror("Error", "Could not load product data.")
            return

        q = simpledialog.askinteger(
            "Quantity", f"Quantity for '{product.name}':",
            minvalue=1, maxvalue=displayed_qty
        )
        if q is None:
            return
        self._add_to_cart_internal(product.sku, product.name, product.price, qty=q)

    def _add_to_cart_internal(self, sku: str, name: str, price_php: float, qty: int = 1):
        """
        Core cart-add logic used by both add_to_cart() and scan_product().
        price_php is always the PHP (base currency) price — never the display price.
        Increments quantity if the SKU is already in the cart.
        """
        for item in self.cart:
            if item["sku"] == sku:
                item["qty"] += qty
                self.refresh_cart_list()
                return
        self.cart.append({"sku": sku, "name": name, "price": price_php, "qty": qty})
        self.refresh_cart_list()

    def _get_discount_pct(self) -> float:
        try:
            val = float(self.discount_var.get().strip())
            return max(0.0, min(val, 100.0))
        except ValueError:
            return 0.0

    def _compute_totals_php(self):
        """
        Return (subtotal, discount_amount, tax_amount, total) all in PHP.
        The cart always holds PHP prices; currency conversion is display-only.
        """
        subtotal        = sum(item["price"] * item["qty"] for item in self.cart)
        disc_pct        = self._get_discount_pct()
        discount_amount = round(subtotal * (disc_pct / 100.0), 2)
        taxable         = max(0.0, subtotal - discount_amount)
        tax_amount      = round(taxable * config.get_tax_rate(), 2)
        total           = round(taxable + tax_amount, 2)
        return subtotal, discount_amount, tax_amount, total

    def refresh_cart_list(self):
        sym = self._sym()
        self.cart_list.delete(0, "end")
        for item in self.cart:
            disp_price = self._to_disp(item["price"])
            self.cart_list.insert(
                "end",
                f"{item['name']}  x{item['qty']}  —  {sym}{disp_price * item['qty']:,.2f}"
            )

        subtotal_php, disc_php, tax_php, total_php = self._compute_totals_php()
        disc_pct = self._get_discount_pct()

        sub_d   = self._to_disp(subtotal_php)
        disc_d  = self._to_disp(disc_php)
        tax_d   = self._to_disp(tax_php)
        total_d = self._to_disp(total_php)

        self.subtotal_var.set(f"{sym}{sub_d:,.2f}")
        self.tax_var.set(f"{sym}{tax_d:,.2f}")
        self.total_var.set(f"{sym}{total_d:,.2f}")

        if disc_pct > 0 and subtotal_php > 0:
            self.disc_label.config(text=f"Discount ({round(disc_pct, 2)}%):")
            self.disc_var.set(f"-{sym}{disc_d:,.2f}")
            self.disc_label.grid(row=1, column=0, sticky="w")
            self.disc_value_label.grid(row=1, column=1, sticky="e", padx=(8, 0))
        else:
            self.disc_label.grid_remove()
            self.disc_value_label.grid_remove()

        php_sym = config.get_currency_symbol()
        if self.currency == "USD" and total_php > 0:
            self.equiv_var.set(f"{php_sym}{total_php:,.2f}")
            self.equiv_label.grid(row=4, column=0, sticky="w")
            self.equiv_value_label.grid(row=4, column=1, sticky="e", padx=(8, 0))
        else:
            self.equiv_label.grid_remove()
            self.equiv_value_label.grid_remove()

    def remove_selected(self):
        sel = self.cart_list.curselection()
        if sel:
            del self.cart[sel[0]]
            self.refresh_cart_list()

    def clear_cart(self):
        self.cart.clear()
        self.discount_var.set("0")
        self.customer_var.set("")
        self.refresh_cart_list()

    def edit_qty(self):
        sel = self.cart_list.curselection()
        if not sel:
            return
        idx  = sel[0]
        item = self.cart[idx]
        live = db_module.get_live_stock(item["sku"])
        newq = simpledialog.askinteger(
            "Quantity",
            f"Set quantity for '{item['name']}' (max {live} in stock):",
            minvalue=1, maxvalue=live
        )
        if newq:
            item["qty"] = newq
            self.refresh_cart_list()

    # >>>>> Checkout >>>>>

    def checkout(self):
        if not self.cart:
            messagebox.showinfo("Checkout", "Cart is empty.")
            return

        errors = services.check_stock(self.cart)
        if errors:
            lines = [
                f"  • {e.name}: requested {e.requested}, only {e.available} left"
                for e in errors
            ]
            messagebox.showerror(
                "Stock error",
                "Not enough stock for:\n\n" + "\n".join(lines)
                + "\n\nUpdate the cart and try again."
            )
            self.load_products()
            return

        disc_pct                         = self._get_discount_pct()
        subtotal_php, _, _, total_php    = self._compute_totals_php()
        total_disp                       = self._to_disp(total_php)
        customer                         = self.customer_var.get().strip()

        result_data = self._ask_payment(total_php, total_disp)
        if result_data is None:
            return

        paid_disp, payment_method, reference_no = result_data

        paid_php = self._from_disp(paid_disp)
        if self.currency == "USD":
            paid_php = max(paid_php, total_php)

        try:
            result = services.process_sale(
                self.cart,
                paid_php,
                discount_pct    = disc_pct,
                username        = self.username,
                customer_name   = customer,
                payment_method  = payment_method,
                reference_no    = reference_no,
                display_currency= self.currency,
                exchange_rate   = self._rate() if self.currency == "USD" else 1.0,
            )
        except ValueError as e:
            messagebox.showerror("Payment", str(e))
            return

        receipt_path = services.save_receipt(result)
        receipt_text = services.build_receipt_text(result)
        messagebox.showinfo(
            "Payment Successful",
            f"{receipt_text}\n\nReceipt saved to:\n{receipt_path}"
        )
        self.clear_cart()
        self.load_products()

    def _ask_payment(self, total_php: float, total_disp: float):
        """
        Payment dialog supporting Cash, Card, and GCash.
        All three methods allow overpayment — change is computed and shown live.
        Card and GCash show an optional Reference / Transaction # field.

        Returns (paid_disp, payment_method, reference_no) or None if cancelled.
        paid_disp is in the active display currency (PHP or USD).
        """
        sym     = self._sym()
        php_sym = config.get_currency_symbol()
        rate    = self._rate()

        dialog = tk.Toplevel(self)
        dialog.title("Payment")
        dialog.geometry("370x370")
        dialog.configure(bg="white", padx=16, pady=12)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        set_icon(dialog, "main")

        self.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()  - 370) // 2
        py = self.winfo_y() + (self.winfo_height() - 370) // 2
        dialog.geometry(f"370x370+{px}+{py}")

        result = {"value": None}

        # >>> Total header >>>
        tk.Label(
            dialog, text=f"Total:  {sym}{total_disp:,.2f}",
            font=("Segoe UI", 14, "bold"), bg="white"
        ).pack(pady=(0, 2))
        if self.currency == "USD":
            tk.Label(
                dialog,
                text=f"≈ {php_sym}{total_php:,.2f}  (stored in PHP)",
                font=("Segoe UI", 9), bg="white", fg="#888"
            ).pack()

        tk.Frame(dialog, bg="#e0e0e0", height=1).pack(fill="x", pady=(8, 6))

        # >>>>> Payment method selector >>>>>
        method_row = tk.Frame(dialog, bg="white")
        method_row.pack(anchor="w", fill="x")
        tk.Label(
            method_row, text="Payment Method:", bg="white",
            font=("Segoe UI", 9, "bold")
        ).pack(side="left", padx=(0, 8))
        method_var = tk.StringVar(value="Cash")
        for m in ("Cash", "Card", "GCash"):
            tk.Radiobutton(
                method_row, text=m, variable=method_var, value=m,
                bg="white", font=("Segoe UI", 10),
                command=lambda: _on_method_change()
            ).pack(side="left", padx=5)

        tk.Frame(dialog, bg="#e0e0e0", height=1).pack(fill="x", pady=(6, 0))

        middle = tk.Frame(dialog, bg="white")
        middle.pack(fill="x", pady=(6, 0))

        # >>> Reference # >>>
        ref_frame = tk.Frame(middle, bg="white")
        tk.Label(
            ref_frame,
            text="Reference / Transaction # (optional):",
            font=("Segoe UI", 9), bg="white", fg="#555"
        ).pack(anchor="w")
        ref_var = tk.StringVar()
        ref_entry = tk.Entry(ref_frame, textvariable=ref_var,
                             font=("Segoe UI", 10), bd=1, relief="solid")
        ref_entry.pack(fill="x", ipady=3, pady=(2, 4))

        # >>> Amount tendered >>>
        amount_frame = tk.Frame(middle, bg="white")
        amount_frame.pack(fill="x")
        tk.Label(
            amount_frame,
            text=f"Amount tendered ({sym}):   [F1 = exact]",
            font=("Segoe UI", 9), bg="white", fg="#555"
        ).pack(anchor="w")
        amount_var = tk.StringVar()
        amount_entry = tk.Entry(amount_frame, textvariable=amount_var,
                                font=("Segoe UI", 12), bd=1, relief="solid",
                                justify="right")
        amount_entry.pack(fill="x", ipady=4, pady=(3, 0))
        amount_entry.focus_set()

        # >>> Live change label >>>
        change_row = tk.Frame(dialog, bg="white")
        change_row.pack(fill="x", pady=(8, 0))
        tk.Label(change_row, text="Change:", bg="white",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        change_var = tk.StringVar(value=f"{sym}0.00")
        tk.Label(change_row, textvariable=change_var, bg="white",
                 font=("Segoe UI", 10, "bold"), fg="#27ae60").pack(side="left", padx=6)

        def _update_change(*_):
            try:
                paid = float(amount_var.get().strip())
                diff = paid - total_disp
                change_var.set(
                    f"{sym}{diff:,.2f}" if diff >= 0 else f"-{sym}{abs(diff):,.2f}"
                )
            except ValueError:
                change_var.set(f"{sym}0.00")

        amount_var.trace_add("write", _update_change)

        def _on_method_change():
            """Show Reference # field only for Card / GCash."""
            m = method_var.get()
            ref_frame.pack_forget()
            amount_frame.pack_forget()
            if m in ("Card", "GCash"):
                ref_frame.pack(fill="x")
                ref_entry.focus_set()
            amount_frame.pack(fill="x")
            if m == "Cash":
                amount_entry.focus_set()

        #> Confirm / Cancel buttons
        tk.Frame(dialog, bg="#e0e0e0", height=1).pack(fill="x", pady=(8, 0))
        btn_frame = tk.Frame(dialog, bg="white")
        btn_frame.pack(fill="x", pady=(8, 0))

        def _confirm():
            try:
                val = float(amount_var.get().strip())
                if val < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid", "Enter a valid amount.", parent=dialog)
                return
            if val < total_disp - 0.005:
                messagebox.showerror(
                    "Insufficient",
                    f"Amount paid ({sym}{val:,.2f}) is less than "
                    f"total ({sym}{total_disp:,.2f}).",
                    parent=dialog
                )
                return
            result["value"] = (val, method_var.get(), ref_var.get().strip())
            dialog.destroy()

        def _exact(event=None):
            """F1 — fill the exact total. Uses 4 dp for USD to avoid rounding loss."""
            if self.currency == "USD":
                amount_var.set(f"{total_disp:.4f}")
            else:
                amount_var.set(f"{total_disp:.2f}")
            amount_entry.icursor("end")
            _update_change()

        tk.Button(
            btn_frame, text="Confirm",
            bg=PRIMARY, fg="white", relief="flat",
            command=_confirm
        ).pack(side="left", expand=True, fill="x", padx=(0, 6), ipady=5)
        tk.Button(
            btn_frame, text="Cancel",
            bg=ACCENT, fg="black", relief="flat",
            command=dialog.destroy
        ).pack(side="left", expand=True, fill="x", ipady=5)

        dialog.bind("<Return>", lambda _: _confirm())
        dialog.bind("<F1>",     _exact)

        dialog.wait_window()
        return result["value"]