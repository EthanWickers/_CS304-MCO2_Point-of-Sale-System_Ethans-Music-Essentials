import tkinter as tk
from tkinter import messagebox, filedialog
import shutil
from datetime import datetime
import db as db_module
import config
from base_window import BaseWindow
from image_utils import set_icon
from theme import WHITE_BG, PRIMARY, ACCENT, SECONDARY


class SettingsWindow(BaseWindow):
    """
    App settings screen — admin only.

    Configures:
      - Shop name
      - Currency symbol (base PHP symbol, e.g. "P" or "₱")
      - Tax rate
      - Low stock alert threshold
      - USD exchange rate  ← NEW (PHP per 1 USD, set manually, no internet needed)

    All values persist in the DB settings table.
    Provides a one-click database backup.
    """

    def __init__(self, master, username: str = "unknown"):
        super().__init__(master, title="Settings", width=460, height=440)
        self.configure(bg=WHITE_BG, padx=16, pady=14)
        self.username = username
        self.resizable(False, False)
        set_icon(self, "settings")
        self.build()
        self.center()

    def build(self):
        tk.Label(
            self, text="Settings",
            font=("Segoe UI", 13, "bold"),
            bg=WHITE_BG, fg=SECONDARY
        ).pack(pady=(0, 10))

        form = tk.Frame(self, bg=WHITE_BG)
        form.pack(fill="x")

        self._fields = {}
        rows = [
            ("shop_name",           "Shop Name"),
            ("currency_symbol",     "Currency Symbol  (base, e.g. P or ₱)"),
            ("tax_rate",            "Tax Rate  (e.g. 0.12 = 12%)"),
            ("low_stock_threshold", "Low Stock Alert  (units)"),
            ("exchange_rate_usd",   "USD Rate  (PHP per 1 USD, e.g. 57.00)"),
        ]

        for i, (key, label) in enumerate(rows):
            tk.Label(form, text=label, bg=WHITE_BG, anchor="w").grid(
                row=i, column=0, sticky="w", pady=7, padx=(0, 12)
            )
            var = tk.StringVar(value=config.get_setting(key))
            tk.Entry(form, textvariable=var, bd=1, relief="solid", width=22).grid(
                row=i, column=1, sticky="ew", pady=7
            )
            self._fields[key] = var

        tk.Label(
            form,
            text="↑  Set manually. Used for USD display in the POS.",
            font=("Segoe UI", 8), bg=WHITE_BG, fg="#888", anchor="w"
        ).grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=(0, 6))

        form.columnconfigure(1, weight=1)

        btn_frame = tk.Frame(self, bg=WHITE_BG)
        btn_frame.pack(fill="x", pady=(14, 0))

        tk.Button(
            btn_frame, text="Save Settings",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.save
        ).pack(side="left", padx=(0, 8), ipady=4, fill="x", expand=True)

        tk.Button(
            btn_frame, text="Backup Database",
            bg=ACCENT, fg="black", relief="flat",
            command=self.backup_db
        ).pack(side="left", ipady=4, fill="x", expand=True)

        self.bind("<Return>", lambda _: self.save())

    def save(self):
        tax_str       = self._fields["tax_rate"].get().strip()
        threshold_str = self._fields["low_stock_threshold"].get().strip()
        rate_str      = self._fields["exchange_rate_usd"].get().strip()
        shop_name     = self._fields["shop_name"].get().strip()
        currency      = self._fields["currency_symbol"].get().strip()

        if not shop_name:
            messagebox.showerror("Validation", "Shop name cannot be empty.")
            return
        if not currency:
            messagebox.showerror("Validation", "Currency symbol cannot be empty.")
            return

        try:
            tax = float(tax_str)
            if not (0.0 <= tax <= 1.0):
                raise ValueError("Tax rate must be between 0.0 and 1.0.")
        except ValueError as e:
            messagebox.showerror("Validation", f"Invalid tax rate:\n{e}")
            return

        try:
            threshold = int(threshold_str)
            if threshold < 0:
                raise ValueError("Threshold must be 0 or greater.")
        except ValueError as e:
            messagebox.showerror("Validation", f"Invalid low stock threshold:\n{e}")
            return

        try:
            rate = float(rate_str)
            if rate <= 0:
                raise ValueError("Exchange rate must be greater than zero.")
        except ValueError as e:
            messagebox.showerror("Validation", f"Invalid USD exchange rate:\n{e}")
            return

        config.set_setting("shop_name",           shop_name)
        config.set_setting("currency_symbol",     currency)
        config.set_setting("tax_rate",            str(tax))
        config.set_setting("low_stock_threshold", str(threshold))
        config.set_setting("exchange_rate_usd",   str(rate))

        db_module.log_action(
            self.username, "SAVE_SETTINGS",
            f"shop='{shop_name}'  currency='{currency}'  "
            f"tax={tax}  low_stock={threshold}  usd_rate={rate}"
        )

        messagebox.showinfo("Saved", "Settings saved successfully.")
        self.destroy()

    def backup_db(self):
        ts           = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"eme_backup_{ts}.db"
        dest = filedialog.asksaveasfilename(
            title="Save Database Backup",
            initialfile=default_name,
            defaultextension=".db",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")]
        )
        if not dest:
            return
        try:
            shutil.copy2(db_module.DB_PATH, dest)
            db_module.log_action(
                self.username, "BACKUP_DB",
                f"Backup saved to: {dest}"
            )
            messagebox.showinfo("Backup Complete", f"Database backed up to:\n{dest}")
        except Exception as e:
            messagebox.showerror("Backup Failed", str(e))