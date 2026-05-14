import tkinter as tk
from tkinter import ttk

PRIMARY   = "#00b4d8"
SECONDARY = "#023e8a"
ACCENT    = "#90e0ef"
WHITE_BG  = "#ebebeb"
TEXT      = "#000000"
ROW_EVEN  = "#f4fbff"   
ROW_ODD   = "#ffffff"

def apply_theme(root: tk.Misc):
    """Apply global ttk/theme settings. Call once on the root Tk only."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # root background
    try:
        root.configure(bg=WHITE_BG)
    except Exception:
        pass

    root.option_add("*Font", ("Segoe UI", 10))

    # Frames
    style.configure("Card.TFrame", background=WHITE_BG)
    style.configure("TFrame", background=WHITE_BG)

    # Labels
    style.configure("TLabel", background=WHITE_BG, foreground=TEXT)
    style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"),
                    background=WHITE_BG, foreground=SECONDARY)

    # Entry fields
    style.configure("TEntry",
                    padding=4,
                    fieldbackground="white",
                    background="white")

    # Treeview
    style.configure("Treeview",
                    background="white",
                    fieldbackground="white",
                    foreground=TEXT,
                    rowheight=26,
                    font=("Segoe UI", 10))

    style.configure("Treeview.Heading",
                    background=ACCENT,
                    foreground="black",
                    font=("Segoe UI", 10, "bold"))

    style.map("Treeview",
              background=[("selected", PRIMARY)],
              foreground=[("selected", "white")])
