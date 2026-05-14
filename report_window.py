import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
from datetime import datetime, timedelta
import db as db_module
import services
import config
from base_window import BaseWindow
from image_utils import set_icon
from theme import ROW_EVEN, ROW_ODD, WHITE_BG, PRIMARY, ACCENT


class ReportWindow(BaseWindow):
    def __init__(self, master, username: str = "unknown"):
        super().__init__(master, title="Sales History", width=900, height=620)
        self.configure(bg=WHITE_BG, padx=8, pady=8)
        self.username = username
        set_icon(self, "sales")
        self.build()
        self.load_history()
        self.center()

    def build(self):
        tk.Label(
            self, text="Sales History",
            font=("Segoe UI", 12, "bold"), bg=WHITE_BG
        ).pack(pady=(2, 6))

        # >>> Daily summary bar >>>
        summary_frame = tk.Frame(self, bg=ACCENT, padx=10, pady=6)
        summary_frame.pack(fill="x", pady=(0, 8))
        self.summary_tx_var  = tk.StringVar(value="Today: — transactions")
        self.summary_rev_var = tk.StringVar(value="Revenue: —")
        tk.Label(
            summary_frame, textvariable=self.summary_tx_var,
            bg=ACCENT, font=("Segoe UI", 10, "bold")
        ).pack(side="left", padx=(0, 20))
        tk.Label(
            summary_frame, textvariable=self.summary_rev_var,
            bg=ACCENT, font=("Segoe UI", 10, "bold")
        ).pack(side="left")
        tk.Button(
            summary_frame, text="Refresh Summary",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.refresh_summary
        ).pack(side="right")

        # >>> Date range filter >>>
        filter_frame = tk.Frame(self, bg=WHITE_BG)
        filter_frame.pack(fill="x", pady=(0, 6))
        tk.Label(filter_frame, text="From:", bg=WHITE_BG).pack(side="left")
        self.date_from_var = tk.StringVar(
            value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        )
        tk.Entry(
            filter_frame, textvariable=self.date_from_var,
            width=12, bd=1, relief="solid"
        ).pack(side="left", padx=(4, 12))
        tk.Label(filter_frame, text="To:", bg=WHITE_BG).pack(side="left")
        self.date_to_var = tk.StringVar(
            value=datetime.now().strftime("%Y-%m-%d")
        )
        tk.Entry(
            filter_frame, textvariable=self.date_to_var,
            width=12, bd=1, relief="solid"
        ).pack(side="left", padx=(4, 12))
        tk.Button(
            filter_frame, text="Apply Filter",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.load_history
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            filter_frame, text="Show All",
            bg=ACCENT, fg="black", relief="flat",
            command=self.show_all
        ).pack(side="left")
        tk.Label(
            filter_frame, text="(YYYY-MM-DD)",
            bg=WHITE_BG, font=("Segoe UI", 9), fg="#888"
        ).pack(side="left", padx=8)

        # >>>>>>> Main area >>>>>>>

        main_area = tk.Frame(self, bg=WHITE_BG)
        main_area.pack(fill="both", expand=True)

        left = tk.Frame(main_area, bg=WHITE_BG)
        left.pack(side="left", fill="both", expand=True)

        self.tree = ttk.Treeview(
            left, columns=("sale_id", "date", "customer", "total"), show="headings"
        )
        self.tree.heading("sale_id",  text="Sale ID")
        self.tree.heading("date",     text="Date")
        self.tree.heading("customer", text="Customer")
        self.tree.heading("total",    text="Total")
        self.tree.column("sale_id",  width=65)
        self.tree.column("date",     width=160)
        self.tree.column("customer", width=140)
        self.tree.column("total",    width=100)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("odd",  background=ROW_ODD)
        self.tree.tag_configure("even", background=ROW_EVEN)
        self.tree.bind("<<TreeviewSelect>>", self.show_details)

        # >>> Best sellers panel >>>
        right = tk.Frame(main_area, bg=WHITE_BG, width=200, padx=8)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        tk.Label(
            right, text="Top 5 Products",
            font=("Segoe UI", 10, "bold"), bg=WHITE_BG
        ).pack(anchor="w", pady=(0, 6))
        self.best_list = tk.Listbox(right, height=10, bd=1, relief="solid")
        self.best_list.pack(fill="both", expand=True)

        # >>> Bottom controls >>>
        ops = tk.Frame(self, bg=WHITE_BG)
        ops.pack(fill="x", pady=6)
        tk.Button(
            ops, text="Delete Selected Sale",
            bg=ACCENT, fg="black", relief="flat",
            command=self.delete_selected_sale
        ).pack(side="left")
        tk.Button(
            ops, text="View Full Receipt",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.view_full_receipt
        ).pack(side="left", padx=6)
        tk.Button(
            ops, text="Print Receipt",
            bg=ACCENT, fg="black", relief="flat",
            command=self.print_selected_receipt
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            ops, text="Export CSV",
            bg=ACCENT, fg="black", relief="flat",
            command=self.export_csv
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            ops, text="Export PDF",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.export_pdf
        ).pack(side="left")

        # >>> Purchase detail panel w/ full receipt view >>>
        detail_lbl_frame = tk.Frame(self, bg=WHITE_BG)
        detail_lbl_frame.pack(fill="x", pady=(4, 2))
        tk.Label(
            detail_lbl_frame, text="Purchase Detail",
            font=("Segoe UI", 10, "bold"), bg=WHITE_BG
        ).pack(side="left")
        tk.Label(
            detail_lbl_frame, text="(select a sale above to preview receipt)",
            font=("Segoe UI", 9), fg="#888", bg=WHITE_BG
        ).pack(side="left", padx=8)

        detail_frame = tk.Frame(self, bg=WHITE_BG, bd=1, relief="solid")
        detail_frame.pack(fill="both", expand=False, pady=(0, 4))

        self.detail_text = tk.Text(
            detail_frame,
            font=("Courier New", 9),
            bd=0, relief="flat",
            wrap="none",
            height=10,
            state="disabled",
            bg="#fafafa"
        )
        detail_sb = tk.Scrollbar(detail_frame, command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_sb.set)
        self.detail_text.pack(side="left", fill="both", expand=True)
        detail_sb.pack(side="right", fill="y")

    # >>>>> Data >>>>>
    def load_history(self, rows=None):
        if rows is None:
            date_from = self.date_from_var.get().strip()
            date_to   = self.date_to_var.get().strip()
            for d in (date_from, date_to):
                try:
                    datetime.strptime(d, "%Y-%m-%d")
                except ValueError:
                    messagebox.showerror(
                        "Invalid date",
                        f"'{d}' is not a valid date.\nUse YYYY-MM-DD format."
                    )
                    return
            rows = db_module.get_sales_by_date_range(date_from, date_to)

        self.sales = {}
        self.tree.delete(*self.tree.get_children())
        sym = config.get_currency_symbol()
        idx = 0

        for row in rows:
            sale_id = row["sale_id"]
            if sale_id not in self.sales:
                customer = row["customer_name"] or "Walk-in"
                self.sales[sale_id] = {
                    "sale_id":         sale_id,
                    "timestamp":       row["timestamp"],
                    "customer_name":   row["customer_name"] or "",
                    "payment_method":  row["payment_method"] if "payment_method" in row.keys() else "Cash",
                    "reference_no":    row["reference_no"]   if "reference_no"   in row.keys() else "",
                    "display_currency": row["display_currency"] if "display_currency" in row.keys() else "PHP",
                    "exchange_rate":   row["exchange_rate"]   if "exchange_rate"   in row.keys() else 1.0,
                    "total":           row["total"],
                    "items":           []
                }
                tag = "even" if idx % 2 == 0 else "odd"
                self.tree.insert(
                    "", "end",
                    iid=str(sale_id),
                    values=(
                        sale_id,
                        row["timestamp"],
                        customer,
                        f"{sym}{row['total']:,.2f}"
                    ),
                    tags=(tag,)
                )
                idx += 1
            self.sales[sale_id]["items"].append({
                "sku":   row["sku"],
                "name":  row["name"],
                "price": row["price"],
                "qty":   row["quantity"]
            })

        self._last_rows = rows

        self.refresh_summary()
        self.load_best_sellers()

    def show_all(self):
        rows = db_module.get_full_sales_history()
        self.load_history(rows=rows)

    def refresh_summary(self):
        row = db_module.get_daily_summary()
        if row:
            sym = config.get_currency_symbol()
            tx  = row["tx_count"]
            rev = row["revenue"]
            self.summary_tx_var.set(
                f"Today: {tx} transaction{'s' if tx != 1 else ''}"
            )
            self.summary_rev_var.set(f"Revenue: {sym}{rev:,.2f}")

    def load_best_sellers(self):
        self.best_list.delete(0, "end")
        rows = db_module.get_top_products(limit=5)
        if not rows:
            self.best_list.insert("end", "(no sales yet)")
            return
        for i, row in enumerate(rows, 1):
            self.best_list.insert(
                "end",
                f"{i}. {row['name'][:18]} ({row['units_sold']} sold)"
            )

    def show_details(self, _=None):
        """
        Update the purchase detail panel with the full receipt text
        of the selected sale.
        """
        sel = self.tree.selection()
        if not sel:
            return
        sale_id = int(sel[0])
        info    = self.sales.get(sale_id)
        if not info:
            return

        receipt_text = services.build_receipt_text_from_row(info)
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", receipt_text)
        self.detail_text.config(state="disabled")

    def _get_selected_sale_info(self):
        """Return the info dict for the selected sale, or None if nothing selected."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a sale first.")
            return None
        return self.sales.get(int(sel[0]))

    def view_full_receipt(self):
        """Open the full receipt in a larger modal window."""
        info = self._get_selected_sale_info()
        if not info:
            return
        receipt_text = services.build_receipt_text_from_row(info)
        self._open_receipt_modal(receipt_text, info.get("sale_id", "?"))

    def print_selected_receipt(self):
        """Send the selected sale's receipt directly to the default printer."""
        info = self._get_selected_sale_info()
        if not info:
            return
        receipt_text = services.build_receipt_text_from_row(info)
        ok, msg = services.print_receipt(receipt_text)
        if ok:
            messagebox.showinfo("Print", msg)
        else:
            messagebox.showerror(
                "Print failed",
                f"{msg}\n\nMake sure a printer is set as your Windows default printer."
            )

    def _open_receipt_modal(self, receipt_text: str, sale_id):
        """Full-size receipt modal with Print and Save options."""
        win = tk.Toplevel(self)
        win.title(f"Receipt — Sale #{sale_id}")
        win.geometry("440x540")
        win.configure(bg="white", padx=14, pady=12)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        set_icon(win, "sales")

        self.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()  - 440) // 2
        py = self.winfo_y() + (self.winfo_height() - 540) // 2
        win.geometry(f"440x540+{px}+{py}")

        tk.Label(
            win, text=f"Receipt — Sale #{sale_id}",
            font=("Segoe UI", 12, "bold"), bg="white"
        ).pack(pady=(0, 8))

        txt_frame = tk.Frame(win, bg="white", bd=1, relief="solid")
        txt_frame.pack(fill="both", expand=True, pady=(0, 10))
        txt = tk.Text(
            txt_frame, font=("Courier New", 9),
            bd=0, relief="flat", wrap="none", width=48, height=24
        )
        sb = tk.Scrollbar(txt_frame, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.insert("1.0", receipt_text)
        txt.config(state="disabled")

        btn_frame = tk.Frame(win, bg="white")
        btn_frame.pack(fill="x")

        def do_print():
            ok, msg = services.print_receipt(receipt_text)
            if ok:
                messagebox.showinfo("Print", msg, parent=win)
            else:
                messagebox.showerror("Print failed", msg, parent=win)

        def do_save():
            path = filedialog.asksaveasfilename(
                parent=win,
                defaultextension=".txt",
                filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
                initialfile=f"receipt_{sale_id}.txt"
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(receipt_text)
                messagebox.showinfo("Saved", f"Receipt saved to:\n{path}", parent=win)

        tk.Button(
            btn_frame, text="🖨  Print",
            bg=ACCENT, fg="black", relief="flat", command=do_print
        ).pack(side="left", expand=True, fill="x", padx=(0, 4), ipady=5)
        tk.Button(
            btn_frame, text="💾  Save Copy",
            bg=ACCENT, fg="black", relief="flat", command=do_save
        ).pack(side="left", expand=True, fill="x", padx=(0, 4), ipady=5)
        tk.Button(
            btn_frame, text="Close",
            bg=PRIMARY, fg="white", relief="flat", command=win.destroy
        ).pack(side="left", expand=True, fill="x", ipady=5)

        win.bind("<Escape>", lambda _: win.destroy())

    # >>>>> Actions >>>>>
    def delete_selected_sale(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Delete", "No sale selected.")
            return
        sale_id = int(sel[0])
        if not messagebox.askyesno("Confirm", f"Delete sale #{sale_id}?"):
            return
        db_module.delete_sale(sale_id)
        db_module.log_action(self.username, "DELETE_SALE", f"Deleted sale #{sale_id}")
        self.load_history()
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.config(state="disabled")
        messagebox.showinfo("Deleted", "Sale removed.")

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not path:
            return
        rows = db_module.get_full_sales_history()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "sale_id", "timestamp", "customer_name",
                "sku", "name", "price", "quantity", "total"
            ])
            for r in rows:
                writer.writerow([
                    r["sale_id"], r["timestamp"], r["customer_name"] or "",
                    r["sku"], r["name"], r["price"], r["quantity"], r["total"]
                ])
        db_module.log_action(self.username, "EXPORT_CSV", f"Exported to: {path}")
        messagebox.showinfo("Exported", f"Sales history exported to:\n{path}")

    def export_pdf(self):
        """Export the currently displayed sales (respects date filter) to PDF."""
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"sales_report_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        if not path:
            return

        rows = getattr(self, "_last_rows", None)
        if not rows:
            rows = db_module.get_full_sales_history()

        date_from = self.date_from_var.get().strip()
        date_to   = self.date_to_var.get().strip()

        try:
            services.export_sales_pdf(rows, date_from, date_to, path)
            db_module.log_action(self.username, "EXPORT_PDF", f"Exported to: {path}")
            messagebox.showinfo("Exported", f"PDF report saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))