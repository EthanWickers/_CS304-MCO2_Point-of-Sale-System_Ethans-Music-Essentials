import tkinter as tk
from tkinter import ttk, messagebox
from base_window import BaseWindow
from image_utils import set_icon
from theme import PRIMARY, ACCENT, WHITE_BG, SECONDARY
from inventory_window import InventoryWindow
from pos_window import POSWindow
from report_window import ReportWindow
from settings_window import SettingsWindow
import db as db_module
import config


class MainMenu(BaseWindow):
    def __init__(self, parent, role, username, on_logout=None):
        super().__init__(parent,
                         title="Main Menu — Ethan's Music Essentials",
                         width=480, height=460)
        self.parent = parent
        self.role = role
        self.username = username
        self._on_logout = on_logout
        self.resizable(False, False)
        set_icon(self, "main")
        self.build()
        self.center()
        self.lift()
        self.focus_force()

        # >>> Keyboard Shortcuts in Menu >>>
        self.bind("<F1>", lambda _: POSWindow(self, username=self.username))
        self.bind("<F2>", lambda _: ReportWindow(self, username=self.username))
        if self.role == "admin":
            self.bind("<F3>", lambda _: InventoryWindow(self, username=self.username))
            self.bind("<F4>", lambda _: SettingsWindow(self, username=self.username))

    def build(self):
        container = tk.Frame(self, bg=WHITE_BG, padx=16, pady=14)
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            text="Ethan's Music Essentials",
            font=("Segoe UI", 14, "bold"),
            bg=WHITE_BG
        ).pack(pady=(0, 4))

        tk.Label(
            container,
            text=f"Logged in as: {self.username}  ({self.role.title()})",
            bg=WHITE_BG,
            font=("Segoe UI", 10),
            fg=SECONDARY
        ).pack(pady=(0, 10))

        btn_frame = tk.Frame(container, bg=WHITE_BG)
        btn_frame.pack(fill="both", expand=True)

        def nav_btn(text, cmd, shortcut=""):
            label = f"{text}  {shortcut}" if shortcut else text
            tk.Button(
                btn_frame,
                text=label,
                bg=PRIMARY, fg="white", relief="flat",
                font=("Segoe UI", 11, "bold"),
                anchor="w", padx=12,
                command=cmd
            ).pack(fill="x", pady=5)

        if self.role == "admin":
            nav_btn("Inventory",   lambda: InventoryWindow(self, username=self.username), "[F3]")

        nav_btn("Point of Sale",   lambda: POSWindow(self, username=self.username),       "[F1]")
        nav_btn("Sales History",   lambda: ReportWindow(self, username=self.username),    "[F2]")

        if self.role == "admin":
            nav_btn("Settings",        lambda: SettingsWindow(self, username=self.username), "[F4]")
            nav_btn("User Management", lambda: UserManagementWindow(self, self.username))
            nav_btn("Audit Log",       lambda: AuditLogWindow(self))

        # >>> Status bar >>>
        status_frame = tk.Frame(container, bg=ACCENT, padx=8, pady=5)
        status_frame.pack(fill="x", pady=(10, 4))
        self.status_var = tk.StringVar(value="Loading…")
        tk.Label(
            status_frame,
            textvariable=self.status_var,
            bg=ACCENT,
            font=("Segoe UI", 9)
        ).pack(side="left")
        tk.Button(
            status_frame, text="↻",
            bg=ACCENT, fg="black", relief="flat",
            font=("Segoe UI", 9),
            command=self._refresh_status
        ).pack(side="right")
        self._refresh_status()

        # >>> Bottom buttons >>>
        bottom = tk.Frame(container, bg=WHITE_BG)
        bottom.pack(fill="x", pady=(6, 0))
        tk.Button(
            bottom, text="Logout",
            bg=ACCENT, fg="black", relief="flat",
            command=self.logout
        ).pack(side="left")
        tk.Button(
            bottom, text="Change Password",
            bg=ACCENT, fg="black", relief="flat",
            command=self._change_own_password
        ).pack(side="left", padx=8)
        tk.Button(
            bottom, text="Exit",
            bg=ACCENT, fg="black", relief="flat",
            command=self.exit_app
        ).pack(side="right")

    def _refresh_status(self):
        try:
            summary = db_module.get_daily_summary()
            tx = summary["tx_count"] if summary else 0
            rev = summary["revenue"] if summary else 0.0
            sym = config.get_currency_symbol()
            threshold = config.get_low_stock_threshold()
            from models import get_all_products
            low = sum(1 for p in get_all_products() if p.quantity <= threshold)
            text = f"Today: {tx} sale{'s' if tx != 1 else ''}  |  Revenue: {sym}{rev:,.2f}"
            if low:
                text += f"  |  ⚠ {low} low-stock item{'s' if low != 1 else ''}"
            self.status_var.set(text)
        except Exception as e:
            self.status_var.set("Status unavailable")
            print(f"[menu] status error: {e}")

    def _change_own_password(self):
        ChangePasswordWindow(self, self.username)

    def logout(self):
        db_module.log_action(self.username, "LOGOUT")
        self.destroy()
        if self._on_logout:
            self._on_logout()
        else:
            try:
                from login_window import LoginWindow
                LoginWindow(self.parent, on_success=self.parent.on_login)
            except tk.TclError as e:
                print(f"[menu] logout error: {e}")

    def exit_app(self):
        db_module.log_action(self.username, "EXIT")
        try:
            self.parent.destroy()
        except tk.TclError as e:
            print(f"[menu] exit error: {e}")

# >>>>>>> User Management Window >>>>>>>

class UserManagementWindow(tk.Toplevel):
    def __init__(self, master, current_username):
        super().__init__(master)
        self.current_username = current_username
        self.title("User Management")
        self.geometry("500x380")
        self.configure(bg=WHITE_BG, padx=12, pady=10)
        self.resizable(False, False)
        set_icon(self, "users")
        self.build()
        self._center()
        self.load_users()

    def _center(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - 500) // 2
        y = (sh - 380) // 2
        self.geometry(f"500x380+{x}+{y}")

    def build(self):
        tk.Label(
            self, text="User Management",
            font=("Segoe UI", 13, "bold"),
            bg=WHITE_BG, fg=SECONDARY
        ).pack(pady=(0, 10))

        cols = ("id", "username", "role")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        self.tree.heading("id", text="ID")
        self.tree.heading("username", text="Username")
        self.tree.heading("role", text="Role")
        self.tree.column("id", width=40, anchor="center")
        self.tree.column("username", width=220)
        self.tree.column("role", width=100, anchor="center")
        self.tree.pack(fill="x", pady=(0, 8))

        btns = tk.Frame(self, bg=WHITE_BG)
        btns.pack(fill="x")
        tk.Button(
            btns, text="Add User",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.add_user
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            btns, text="Reset Password",
            bg=ACCENT, fg="black", relief="flat",
            command=self.reset_password
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            btns, text="Delete User",
            bg=ACCENT, fg="black", relief="flat",
            command=self.delete_user
        ).pack(side="left")

    def load_users(self):
        self.tree.delete(*self.tree.get_children())
        for row in db_module.get_all_users():
            self.tree.insert("", "end", values=(row["id"], row["username"], row["role"]))

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a user first.")
            return None
        return self.tree.item(sel[0])["values"][0]

    def add_user(self):
        AddUserDialog(self, on_done=self.load_users,
                      current_username=self.current_username)

    def reset_password(self):
        uid = self._selected_id()
        if uid is None:
            return
        row = db_module.get_user_by_id(uid)
        if not row:
            return
        ResetPasswordDialog(self, user_id=uid, username=row["username"],
                            current_username=self.current_username,
                            on_done=self.load_users)

    def delete_user(self):
        uid = self._selected_id()
        if uid is None:
            return
        row = db_module.get_user_by_id(uid)
        if not row:
            return
        if row["username"] == self.current_username:
            messagebox.showerror("Error", "You cannot delete your own account.")
            return
        if not messagebox.askyesno("Confirm", f"Delete user '{row['username']}'?"):
            return
        db_module.delete_user(uid)
        db_module.log_action(self.current_username, "DELETE_USER",
                             f"Deleted user: {row['username']}")
        self.load_users()


class AddUserDialog(tk.Toplevel):
    def __init__(self, master, on_done, current_username):
        super().__init__(master)
        self.on_done = on_done
        self.current_username = current_username
        self.title("Add User")
        self.geometry("340x260")
        self.configure(bg=WHITE_BG, padx=14, pady=12)
        self.resizable(False, False)
        set_icon(self, "users")
        self.build()

    def build(self):
        fields = [("Username", "username"), ("Password", "password"),
                  ("Confirm Password", "confirm")]
        self.entries = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(self, text=label, bg=WHITE_BG).grid(
                row=i, column=0, sticky="e", padx=6, pady=7)
            show = "*" if "assword" in label else ""
            e = tk.Entry(self, bd=1, relief="solid", show=show)
            e.grid(row=i, column=1, padx=6, pady=7, sticky="ew")
            self.entries[key] = e

        tk.Label(self, text="Role", bg=WHITE_BG).grid(
            row=3, column=0, sticky="e", padx=6, pady=7)
        self.role_var = tk.StringVar(value="cashier")
        ttk.Combobox(
            self, textvariable=self.role_var,
            values=["cashier", "admin"], state="readonly"
        ).grid(row=3, column=1, padx=6, pady=7, sticky="ew")

        tk.Button(
            self, text="Add User",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.save
        ).grid(row=4, column=0, columnspan=2, pady=12)
        self.columnconfigure(1, weight=1)
        self.bind("<Return>", lambda _: self.save())

    def save(self):
        username = self.entries["username"].get().strip()
        password = self.entries["password"].get()
        confirm  = self.entries["confirm"].get()
        role     = self.role_var.get()
        if not username:
            messagebox.showerror("Validation", "Username is required.")
            return
        if not password:
            messagebox.showerror("Validation", "Password is required.")
            return
        if password != confirm:
            messagebox.showerror("Validation", "Passwords do not match.")
            return
        try:
            db_module.add_user(username, password, role)
            db_module.log_action(self.current_username, "ADD_USER",
                                 f"Added user: {username} ({role})")
            if self.on_done:
                self.on_done()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Could not add user:\n{e}")


class ResetPasswordDialog(tk.Toplevel):
    def __init__(self, master, user_id, username, current_username, on_done):
        super().__init__(master)
        self.user_id = user_id
        self.username = username
        self.current_username = current_username
        self.on_done = on_done
        self.title(f"Reset Password — {username}")
        self.geometry("320x200")
        self.configure(bg=WHITE_BG, padx=14, pady=12)
        self.resizable(False, False)
        set_icon(self, "users")
        self.build()

    def build(self):
        tk.Label(
            self, text=f"Reset password for: {self.username}",
            bg=WHITE_BG, font=("Segoe UI", 10, "bold")
        ).grid(row=0, column=0, columnspan=2, pady=(0, 10))
        for i, (label, key) in enumerate(
            [("New Password", "password"), ("Confirm", "confirm")], start=1
        ):
            tk.Label(self, text=label, bg=WHITE_BG).grid(
                row=i, column=0, sticky="e", padx=6, pady=7)
            e = tk.Entry(self, bd=1, relief="solid", show="*")
            e.grid(row=i, column=1, padx=6, pady=7, sticky="ew")
            setattr(self, f"entry_{key}", e)
        tk.Button(
            self, text="Save",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.save
        ).grid(row=3, column=0, columnspan=2, pady=12)
        self.columnconfigure(1, weight=1)
        self.bind("<Return>", lambda _: self.save())

    def save(self):
        pw      = self.entry_password.get()
        confirm = self.entry_confirm.get()
        if not pw:
            messagebox.showerror("Validation", "Password cannot be empty.")
            return
        if pw != confirm:
            messagebox.showerror("Validation", "Passwords do not match.")
            return
        db_module.update_user_password(self.user_id, pw)
        db_module.log_action(self.current_username, "RESET_PASSWORD",
                             f"Reset password for: {self.username}")
        messagebox.showinfo("Done", "Password updated successfully.")
        if self.on_done:
            self.on_done()
        self.destroy()

# >>>>>>> Change Own Password Window/Feature >>>>>>>

class ChangePasswordWindow(tk.Toplevel):
    def __init__(self, master, username):
        super().__init__(master)
        self.username = username
        self.title("Change Password")
        self.geometry("320x240")
        self.configure(bg=WHITE_BG, padx=14, pady=12)
        self.resizable(False, False)
        set_icon(self, "users")
        self.build()

    def build(self):
        tk.Label(
            self, text="Change Your Password",
            font=("Segoe UI", 11, "bold"), bg=WHITE_BG
        ).grid(row=0, column=0, columnspan=2, pady=(0, 12))

        labels = [("Current Password", "current"),
                  ("New Password", "new"),
                  ("Confirm New", "confirm")]
        self.entries = {}
        for i, (label, key) in enumerate(labels, start=1):
            tk.Label(self, text=label, bg=WHITE_BG).grid(
                row=i, column=0, sticky="e", padx=6, pady=7)
            e = tk.Entry(self, bd=1, relief="solid", show="*")
            e.grid(row=i, column=1, padx=6, pady=7, sticky="ew")
            self.entries[key] = e

        tk.Button(
            self, text="Update Password",
            bg=PRIMARY, fg="white", relief="flat",
            command=self.save
        ).grid(row=len(labels) + 1, column=0, columnspan=2, pady=12)
        self.columnconfigure(1, weight=1)
        self.bind("<Return>", lambda _: self.save())

    def save(self):
        current = self.entries["current"].get()
        new_pw  = self.entries["new"].get()
        confirm = self.entries["confirm"].get()

        if not db_module.verify_user(self.username, current):
            messagebox.showerror("Error", "Current password is incorrect.")
            return
        if not new_pw:
            messagebox.showerror("Validation", "New password cannot be empty.")
            return
        if new_pw != confirm:
            messagebox.showerror("Validation", "New passwords do not match.")
            return

        row = db_module.verify_user(self.username, current)
        db_module.update_user_password(row["id"], new_pw)
        db_module.log_action(self.username, "CHANGE_PASSWORD", "Self-service")
        messagebox.showinfo("Done", "Password changed successfully.")
        self.destroy()

# >>>>>>> Audit Log Window >>>>>>>

class AuditLogWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Audit Log")
        self.geometry("700x440")
        self.configure(bg=WHITE_BG, padx=10, pady=10)
        set_icon(self, "users")
        self.build()
        self.load()
        self._center()

    def _center(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - 700) // 2
        y = (sh - 440) // 2
        self.geometry(f"700x440+{x}+{y}")

    def build(self):
        tk.Label(
            self, text="Audit Log",
            font=("Segoe UI", 12, "bold"), bg=WHITE_BG
        ).pack(pady=(0, 8))

        frame = tk.Frame(self, bg=WHITE_BG)
        frame.pack(fill="both", expand=True)

        cols = ("timestamp", "username", "action", "detail")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        self.tree.heading("timestamp", text="Timestamp")
        self.tree.heading("username",  text="User")
        self.tree.heading("action",    text="Action")
        self.tree.heading("detail",    text="Detail")
        self.tree.column("timestamp", width=150)
        self.tree.column("username",  width=110)
        self.tree.column("action",    width=130)
        self.tree.column("detail",    width=280)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def load(self):
        self.tree.delete(*self.tree.get_children())
        for row in db_module.get_audit_log(limit=200):
            self.tree.insert("", "end", values=(
                row["timestamp"],
                row["username"],
                row["action"],
                row["detail"] or ""
            ))