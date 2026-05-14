import tkinter as tk
from tkinter import messagebox
import db as db_module
from base_window import BaseWindow
from image_utils import set_icon
from theme import PRIMARY, ACCENT, WHITE_BG, SECONDARY


class LoginWindow(BaseWindow):
    def __init__(self, parent, on_success):
        super().__init__(parent,
                         title="Login — Ethan's Music Essentials",
                         width=380, height=240)
        self.parent = parent
        self.on_success = on_success

        self.resizable(False, False)
        set_icon(self, "main")
        self.build_ui()

        self.grab_set()
        self.show()
        self.entry_user.focus_set()
        self.bind("<Return>", lambda _: self.attempt_login())

    def build_ui(self):
        self.configure(bg=WHITE_BG)
        card = tk.Frame(self, bg="white")
        card.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(
            card,
            text="Login",
            font=("Segoe UI", 16, "bold"),
            bg="white",
            fg=SECONDARY
        ).pack(pady=(0, 12))

        tk.Label(card, text="Username", bg="white").pack(anchor="w")
        self.entry_user = tk.Entry(
            card, bd=1, relief="solid", font=("Segoe UI", 10)
        )
        self.entry_user.pack(fill="x", pady=(4, 8), ipady=4)

        tk.Label(card, text="Password", bg="white").pack(anchor="w")
        self.entry_pass = tk.Entry(
            card, bd=1, relief="solid", show="*", font=("Segoe UI", 10)
        )
        self.entry_pass.pack(fill="x", pady=(4, 12), ipady=4)

        btn_frame = tk.Frame(card, bg="white")
        btn_frame.pack(fill="x")

        tk.Button(
            btn_frame,
            text="Login",
            bg=PRIMARY, fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            command=self.attempt_login
        ).pack(side="left", expand=True, fill="x", padx=(0, 6), ipady=6)

        tk.Button(
            btn_frame,
            text="Quit",
            bg=ACCENT, fg="black",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            command=self.on_close
        ).pack(side="left", expand=True, fill="x", padx=(6, 0), ipady=6)

    def attempt_login(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()

        row = db_module.verify_user(username, password)
        if row:
            role = row["role"]
            db_module.log_action(username, "LOGIN", f"Role: {role}")
            self.grab_release()
            self.destroy()
            # Pass both role AND username so the rest of the app
            # can show the username and write it to the audit log
            self.on_success(role, username)
        else:
            messagebox.showerror("Login failed", "Invalid username or password.")

    def on_close(self):
        try:
            self.grab_release()
        except Exception as e:
            print(f"[login] grab_release error: {e}")
        self.destroy()
        try:
            self.parent.destroy()
        except Exception as e:
            print(f"[login] parent destroy error: {e}")