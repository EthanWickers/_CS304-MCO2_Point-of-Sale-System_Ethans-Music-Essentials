import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import db as db_module
import services
import config
from models import get_all_products, Product
from base_window import BaseWindow
from image_utils import (
    ImagePreviewPanel, pick_image_file,
    load_pil_image, path_to_blob, make_thumbnail,
    PILLOW_AVAILABLE, set_icon,
    copy_image_to_assets, resolve_product_image_path,
)
from theme import ROW_EVEN, ROW_ODD, WHITE_BG, PRIMARY, ACCENT

PRODUCT_TYPES = [
    "Guitars",
    "Keyboards",
    "Drums & Percussions",
    "Sound Systems",
    "Accessories",
]

LOW_STOCK_COLOR = "#ffe0e0"
IMG_PANEL_W     = 230


class InventoryWindow(BaseWindow):
    def __init__(self, master, username: str = "unknown"):
        super().__init__(master, title="Inventory", width=1000, height=560)
        self.configure(bg=WHITE_BG, padx=12, pady=12)
        self.username = username
        set_icon(self, "inventory")
        self.create_widgets()
        self.load_products()
        self.center()
        self.state("zoomed")

        self.bind("<Delete>", lambda _: self.delete_selected())
        self.bind("<F5>",     lambda _: self.load_products())

    # >>>>>>> UI Layout >>>>>>>

    def create_widgets(self):
        ctrl = tk.Frame(self, bg=WHITE_BG)
        ctrl.pack(fill="x", pady=(0, 8))
        tk.Label(ctrl, text="Search:", bg=WHITE_BG).pack(side="left")
        self.search_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self.search_var, bd=1, relief="solid") \
            .pack(side="left", fill="x", expand=True, padx=6)
        tk.Button(
            ctrl, text="Clear", bg=ACCENT, fg="black", relief="flat",
            command=lambda: self.search_var.set("")
        ).pack(side="left", padx=6)
        tk.Button(
            ctrl, text="Add Product", bg=PRIMARY, fg="white", relief="flat",
            command=self.open_add_product
        ).pack(side="right")

        # >>> Main content area: treeview (left/expand) + image panel (right/fixed) >>>
        content = tk.Frame(self, bg=WHITE_BG)
        content.pack(fill="both", expand=True)

        # >>> Image preview panel (right side — collapsible & resizable) >>>
        self.img_panel = ImagePreviewPanel(
            content, width=IMG_PANEL_W, label_text="Product Image"
        )
        self.img_panel.pack(side="right", fill="y")

        # >>> Treeview container (fills remaining space) >>>
        tree_container = tk.Frame(content, bg=WHITE_BG)
        tree_container.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_container, orient="vertical")
        hsb = ttk.Scrollbar(tree_container, orient="horizontal")
        cols = ("id", "sku", "name", "price", "quantity", "brand", "product_type")
        self.tree = ttk.Treeview(
            tree_container, columns=cols, show="headings",
            height=16, yscrollcommand=vsb.set, xscrollcommand=hsb.set
        )
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)

        for c in cols:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=120, anchor="center")
        self.tree.column("name", width=260)
        self.tree.tag_configure("even",      background=ROW_EVEN)
        self.tree.tag_configure("odd",       background=ROW_ODD)
        self.tree.tag_configure("low_stock", background=LOW_STOCK_COLOR)

        #> Update image panel whenever the selection changes
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

        # >>> Action buttons >>>
        btns = tk.Frame(self, bg=WHITE_BG)
        btns.pack(fill="x", pady=(8, 4))
        tk.Button(
            btns, text="Edit Selected", bg=ACCENT, fg="black", relief="flat",
            command=self.edit_selected
        ).pack(side="left", padx=6)
        tk.Button(
            btns, text="Delete  [Del]", bg=ACCENT, fg="black", relief="flat",
            command=self.delete_selected
        ).pack(side="left")
        tk.Button(
            btns, text="Adjust Stock", bg=ACCENT, fg="black", relief="flat",
            command=self.adjust_stock
        ).pack(side="left", padx=6)

        #> Low-stock legend
        legend = tk.Frame(self, bg=WHITE_BG)
        legend.pack(fill="x", pady=(2, 0))
        tk.Label(legend, text="  ", bg=LOW_STOCK_COLOR, relief="flat", width=2).pack(side="left")
        tk.Label(
            legend,
            text=f" Low stock (≤ {config.get_low_stock_threshold()} units)",
            bg=WHITE_BG, font=("Segoe UI", 9), fg="#555"
        ).pack(side="left")

        self.search_var.trace_add("write", lambda *_: self.apply_filter())

    # >>>>> Image Panel >>>>>

    def _on_row_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            self.img_panel.clear()
            return
        pid = self.tree.item(sel[0])["values"][0]
        row = db_module.get_product_by_id(pid)
        if row:
            self.img_panel.update_image(
                path=resolve_product_image_path(
                    row["image_path"] if "image_path" in row.keys() else None
                ),
                blob=row["image_blob"] if "image_blob" in row.keys() else None,
            )
        else:
            self.img_panel.clear()

    # >>>>> Data >>>>>

    def load_products(self):
        self._all = get_all_products()
        self.apply_filter()

    def apply_filter(self):
        threshold = config.get_low_stock_threshold()
        q = (self.search_var.get() or "").lower().strip()
        self.tree.delete(*self.tree.get_children())
        for idx, p in enumerate(self._all):
            if q and not (
                q in (p.name  or "").lower()
                or q in (p.sku   or "").lower()
                or q in (p.brand or "").lower()
            ):
                continue
            tag = "low_stock" if p.quantity <= threshold else (
                "even" if idx % 2 == 0 else "odd"
            )
            self.tree.insert(
                "", "end",
                values=(
                    p.id, p.sku, p.name,
                    f"{p.price:,.2f}",
                    p.quantity, p.brand, p.product_type,
                ),
                tags=(tag,)
            )
        self.img_panel.clear()

    # >>>>> Actions >>>>>

    def open_add_product(self):
        AddProductWindow(self, username=self.username, on_add=self.load_products)

    def edit_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Edit", "Select a product first.")
            return
        pid = self.tree.item(sel[0])["values"][0]
        row = db_module.get_product_by_id(pid)
        if not row:
            messagebox.showerror("Error", "Failed to load product.")
            return
        EditProductWindow(
            self, Product.from_row(row),
            username=self.username,
            on_save=self.load_products,
        )

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Delete", "Select a product first.")
            return
        pid = self.tree.item(sel[0])["values"][0]
        row = db_module.get_product_by_id(pid)
        if not row:
            return
        if messagebox.askyesno("Confirm", f"Delete '{row['name']}'?"):
            db_module.delete_product(pid)
            db_module.log_action(
                self.username, "DELETE_PRODUCT",
                f"Deleted: {row['name']} (SKU: {row['sku']})"
            )
            self.load_products()

    def adjust_stock(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Adjust Stock", "Select a product first.")
            return
        pid = self.tree.item(sel[0])["values"][0]
        row = db_module.get_product_by_id(pid)
        if not row:
            messagebox.showerror("Error", "Failed to load product.")
            return
        current = row["quantity"]
        delta = simpledialog.askinteger(
            "Adjust Stock",
            f"Product : {row['name']}\n"
            f"Current stock : {current}\n\n"
            f"Enter adjustment (e.g. +10 to add, -3 to remove):",
        )
        if delta is None:
            return
        new_qty = current + delta
        if new_qty < 0:
            messagebox.showerror(
                "Invalid",
                f"Adjustment would result in negative stock ({new_qty}).\n"
                f"Enter a smaller reduction."
            )
            return
        db_module.update_product(pid, quantity=new_qty)
        db_module.log_action(
            self.username, "ADJUST_STOCK",
            f"{row['name']} (SKU: {row['sku']})  {current} → {new_qty}  (delta: {delta:+d})"
        )
        self.load_products()
        messagebox.showinfo(
            "Stock Updated",
            f"{row['name']}\nPrevious: {current}  →  New: {new_qty}"
        )

# >>>>>>> Add Product Window >>>>>>>

class AddProductWindow(tk.Toplevel):
    def __init__(self, master, username: str = "unknown", on_add=None):
        super().__init__(master)
        self.username = username
        self.on_add   = on_add
        self.title("Add Product")
        self.geometry("440x510")
        self.configure(bg="white", padx=12, pady=10)
        self.resizable(False, False)
        set_icon(self, "inventory")

        #> Image state
        self._image_path: str   = ""
        self._image_blob: bytes = None
        self._img_photo         = None

        self.build()
        self.bind("<Return>", lambda _: self.add_product())

    def build(self):
        field_labels = ["Name", "Price", "Quantity", "SKU", "Brand", "Type"]
        self.entries = {}

        for i, lab in enumerate(field_labels):
            tk.Label(self, text=lab, bg="white").grid(
                row=i, column=0, sticky="e", padx=6, pady=5
            )
            if lab == "Type":
                cb = ttk.Combobox(self, values=PRODUCT_TYPES, state="readonly")
                cb.grid(row=i, column=1, padx=6, pady=5, sticky="ew")
                self.entries["type"] = cb
            else:
                e = tk.Entry(self, bd=1, relief="solid")
                e.grid(row=i, column=1, padx=6, pady=5, sticky="ew")
                self.entries[lab.lower()] = e

        # >>> Image section >>>
        sep_row = len(field_labels)
        tk.Frame(self, bg="#e8e8e8", height=1).grid(
            row=sep_row, column=0, columnspan=2, sticky="ew", pady=(8, 4)
        )

        img_row = sep_row + 1
        tk.Label(self, text="Image", bg="white", anchor="ne").grid(
            row=img_row, column=0, sticky="ne", padx=6, pady=6
        )

        img_area = tk.Frame(self, bg="white")
        img_area.grid(row=img_row, column=1, padx=6, pady=6, sticky="ew")

        #> Thumbnail preview canvas (150 × 120)
        self._img_canvas = tk.Canvas(
            img_area, width=150, height=120,
            bg="#f0f0f0", bd=1, relief="flat",
            highlightthickness=1, highlightbackground="#ccc"
        )
        self._img_canvas.pack(side="left", padx=(0, 10))
        self._img_canvas.create_text(
            75, 60, text="📷\nNo image", fill="#bbb",
            font=("Segoe UI", 9), anchor="center", justify="center"
        )

        #> Browse + Remove buttons
        btn_col = tk.Frame(img_area, bg="white")
        btn_col.pack(side="left", fill="y")
        tk.Button(
            btn_col, text="Browse...", bg=PRIMARY, fg="white", relief="flat",
            command=self._pick_image
        ).pack(fill="x", pady=(0, 6), ipady=3)
        tk.Button(
            btn_col, text="Remove Image", bg=ACCENT, fg="black", relief="flat",
            command=self._remove_image
        ).pack(fill="x", ipady=3)
        self._img_name_label = tk.Label(
            btn_col, text="", bg="white", fg="#777",
            font=("Segoe UI", 8), wraplength=120, justify="left"
        )
        self._img_name_label.pack(anchor="w", pady=(6, 0))

        if not PILLOW_AVAILABLE:
            tk.Label(
                img_area,
                text="⚠  pip install Pillow\nto enable images",
                bg="white", fg="#e74c3c", font=("Segoe UI", 8)
            ).pack(side="left", padx=6)

        #> Save button
        save_row = img_row + 1
        tk.Button(
            self, text="Add Product", bg=PRIMARY, fg="white", relief="flat",
            command=self.add_product
        ).grid(row=save_row, column=0, columnspan=2, pady=12, sticky="ew", padx=6)

        self.columnconfigure(1, weight=1)

    # >>>>> Image helpers >>>>>

    def _pick_image(self):
        if not PILLOW_AVAILABLE:
            messagebox.showwarning(
                "Pillow required",
                "Image support requires Pillow.\n\nRun:  pip install Pillow",
                parent=self
            )
            return
        path = pick_image_file(self)
        if not path:
            return
        try:
            with open(path, "rb") as _f:
                raw_bytes = _f.read()
        except OSError as err:
            messagebox.showerror("Error", f"Could not read image:\n{err}", parent=self)
            return
        pil_img = load_pil_image(blob=raw_bytes)
        if pil_img is None:
            messagebox.showerror("Error", "Could not open the selected image.", parent=self)
            return
        try:
            relative = copy_image_to_assets(path)
        except OSError as err:
            messagebox.showerror("Error", f"Could not copy image:\n{err}", parent=self)
            return
        self._image_path = relative          
        self._image_blob = raw_bytes         
        self._refresh_form_preview(pil_img)

    def _remove_image(self):
        self._image_path = ""
        self._image_blob = None
        self._img_photo  = None
        self._img_canvas.delete("all")
        self._img_canvas.create_text(
            75, 60, text="📷\nNo image", fill="#bbb",
            font=("Segoe UI", 9), anchor="center", justify="center"
        )
        self._img_name_label.config(text="")

    def _refresh_form_preview(self, pil_img):
        """Resize to thumbnail and show in the small canvas."""
        from PIL import ImageTk
        thumb = make_thumbnail(pil_img, 150, 120)
        self._img_photo = ImageTk.PhotoImage(thumb)
        self._img_canvas.delete("all")
        tw, th = thumb.size
        self._img_canvas.create_image(75, 60, anchor="center", image=self._img_photo)
        self._img_name_label.config(text=os.path.basename(self._image_path))

    # >>> Save >>>

    def add_product(self):
        name      = self.entries["name"].get().strip()
        price_str = self.entries["price"].get().strip()
        qty_str   = self.entries["quantity"].get().strip()
        sku       = self.entries["sku"].get().strip()
        brand     = self.entries["brand"].get().strip() or None
        ptype     = self.entries["type"].get()

        try:
            price, qty = services.validate_product_fields(name, price_str, qty_str, sku)
        except ValueError as e:
            messagebox.showerror("Validation", str(e))
            return

        try:
            db_module.add_product(
                name, price, qty, sku, brand, ptype,
                image_path=self._image_path or None,
                image_blob=self._image_blob,
            )
            db_module.log_action(
                self.username, "ADD_PRODUCT",
                f"Added: {name} (SKU: {sku})  price: {price}  qty: {qty}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add product:\n{e}")
            return

        if self.on_add:
            self.on_add()
        self.destroy()

# >>>>>>> Edit Product Window >>>>>>>

class EditProductWindow(tk.Toplevel):
    def __init__(self, master, product, username: str = "unknown", on_save=None):
        super().__init__(master)
        self.product  = product
        self.username = username
        self.on_save  = on_save
        self.title("Edit Product")
        self.geometry("440x510")
        self.configure(bg="white", padx=12, pady=10)
        self.resizable(False, False)
        set_icon(self, "inventory")

        self._image_path: str   = product.image_path or ""
        self._image_blob: bytes = product.image_blob
        self._img_photo         = None

        self.build()
        self.bind("<Return>", lambda _: self.save())

    def build(self):
        field_labels = ["Name", "Price", "Quantity", "SKU", "Brand", "Type"]
        values = [
            self.product.name,
            str(self.product.price),
            str(self.product.quantity),
            self.product.sku          or "",
            self.product.brand        or "",
            self.product.product_type or "",
        ]
        self.entries = {}

        for i, lab in enumerate(field_labels):
            tk.Label(self, text=lab, bg="white").grid(
                row=i, column=0, sticky="e", padx=6, pady=5
            )
            if lab == "Type":
                cb = ttk.Combobox(self, values=PRODUCT_TYPES, state="readonly")
                cb.grid(row=i, column=1, padx=6, pady=5, sticky="ew")
                cb.set(values[i])
                self.entries["type"] = cb
            else:
                e = tk.Entry(self, bd=1, relief="solid")
                e.grid(row=i, column=1, padx=6, pady=5, sticky="ew")
                e.insert(0, values[i])
                self.entries[lab.lower()] = e

        # >>> Image section >>>
        sep_row = len(field_labels)
        tk.Frame(self, bg="#e8e8e8", height=1).grid(
            row=sep_row, column=0, columnspan=2, sticky="ew", pady=(8, 4)
        )

        img_row = sep_row + 1
        tk.Label(self, text="Image", bg="white", anchor="ne").grid(
            row=img_row, column=0, sticky="ne", padx=6, pady=6
        )

        img_area = tk.Frame(self, bg="white")
        img_area.grid(row=img_row, column=1, padx=6, pady=6, sticky="ew")

        self._img_canvas = tk.Canvas(
            img_area, width=150, height=120,
            bg="#f0f0f0", bd=1, relief="flat",
            highlightthickness=1, highlightbackground="#ccc"
        )
        self._img_canvas.pack(side="left", padx=(0, 10))

        btn_col = tk.Frame(img_area, bg="white")
        btn_col.pack(side="left", fill="y")
        tk.Button(
            btn_col, text="Browse...", bg=PRIMARY, fg="white", relief="flat",
            command=self._pick_image
        ).pack(fill="x", pady=(0, 6), ipady=3)
        tk.Button(
            btn_col, text="Remove Image", bg=ACCENT, fg="black", relief="flat",
            command=self._remove_image
        ).pack(fill="x", ipady=3)
        self._img_name_label = tk.Label(
            btn_col, text="", bg="white", fg="#777",
            font=("Segoe UI", 8), wraplength=120, justify="left"
        )
        self._img_name_label.pack(anchor="w", pady=(6, 0))

        if not PILLOW_AVAILABLE:
            tk.Label(
                img_area,
                text="⚠  pip install Pillow\nto enable images",
                bg="white", fg="#e74c3c", font=("Segoe UI", 8)
            ).pack(side="left", padx=6)

        self._load_existing_image()

        # >>> Save button >>>
        save_row = img_row + 1
        tk.Button(
            self, text="Save Changes", bg=PRIMARY, fg="white", relief="flat",
            command=self.save
        ).grid(row=save_row, column=0, columnspan=2, pady=12, sticky="ew", padx=6)

        self.columnconfigure(1, weight=1)

    # >>>>> Image helpers >>>>>

    def _load_existing_image(self):
        """Show the product's current image in the form thumbnail on open."""
        if not PILLOW_AVAILABLE:
            self._img_canvas.create_text(
                75, 60, text="📷\nNo image", fill="#bbb",
                font=("Segoe UI", 9), anchor="center", justify="center"
            )
            return
        pil_img = load_pil_image(
            path=resolve_product_image_path(self._image_path),
            blob=self._image_blob,
        )
        if pil_img:
            self._refresh_form_preview(pil_img)
        else:
            self._img_canvas.create_text(
                75, 60, text="📷\nNo image", fill="#bbb",
                font=("Segoe UI", 9), anchor="center", justify="center"
            )

    def _pick_image(self):
        if not PILLOW_AVAILABLE:
            messagebox.showwarning(
                "Pillow required",
                "Image support requires Pillow.\n\nRun:  pip install Pillow",
                parent=self
            )
            return
        path = pick_image_file(self)
        if not path:
            return
        try:
            with open(path, "rb") as _f:
                raw_bytes = _f.read()
        except OSError as err:
            messagebox.showerror("Error", f"Could not read image:\n{err}", parent=self)
            return
        pil_img = load_pil_image(blob=raw_bytes)
        if pil_img is None:
            messagebox.showerror("Error", "Could not open the selected image.", parent=self)
            return
        try:
            relative = copy_image_to_assets(path)
        except OSError as err:
            messagebox.showerror("Error", f"Could not copy image:\n{err}", parent=self)
            return
        self._image_path = relative         
        self._image_blob = raw_bytes         
        self._refresh_form_preview(pil_img)

    def _remove_image(self):
        self._image_path = ""
        self._image_blob = None
        self._img_photo  = None
        self._img_canvas.delete("all")
        self._img_canvas.create_text(
            75, 60, text="📷\nNo image", fill="#bbb",
            font=("Segoe UI", 9), anchor="center", justify="center"
        )
        self._img_name_label.config(text="")

    def _refresh_form_preview(self, pil_img):
        from PIL import ImageTk
        import os
        thumb = make_thumbnail(pil_img, 150, 120)
        self._img_photo = ImageTk.PhotoImage(thumb)
        self._img_canvas.delete("all")
        self._img_canvas.create_image(75, 60, anchor="center", image=self._img_photo)
        label = os.path.basename(self._image_path) if self._image_path else "(embedded)"
        self._img_name_label.config(text=label)

    # >>>>> Save >>>>>

    def save(self):
        name      = self.entries["name"].get().strip()
        price_str = self.entries["price"].get().strip()
        qty_str   = self.entries["quantity"].get().strip()
        sku       = self.entries["sku"].get().strip()
        brand     = self.entries["brand"].get().strip() or None
        ptype     = self.entries["type"].get()

        try:
            price, qty = services.validate_product_fields(name, price_str, qty_str, sku)
        except ValueError as e:
            messagebox.showerror("Validation", str(e))
            return

        try:
            db_module.update_product(
                self.product.id,
                name=name, price=price, quantity=qty,
                sku=sku, brand=brand, product_type=ptype,
                image_path=self._image_path or None,
                image_blob=self._image_blob,
            )
            db_module.log_action(
                self.username, "EDIT_PRODUCT",
                f"Edited: {name} (SKU: {sku})"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save product:\n{e}")
            return

        if self.on_save:
            self.on_save()
        self.destroy()