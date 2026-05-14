import tkinter as tk
from theme import apply_theme
import db as db_module
from login_window import LoginWindow
from main_menu import MainMenu

#> Inactive Session Timeout
INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000


def main():
    global root
    root = tk.Tk()
    root.title("Ethan's Music Essentials")

    apply_theme(root)
    db_module.init_db()
    root.withdraw() 

    _state = {"timeout_id": None, "menu": None}

    def _reset_timer(event=None):
        """Restart the inactivity timer on any user input."""
        if INACTIVITY_TIMEOUT_MS <= 0:
            return
        if _state["timeout_id"]:
            root.after_cancel(_state["timeout_id"])
        _state["timeout_id"] = root.after(INACTIVITY_TIMEOUT_MS, _auto_logout)

    def _auto_logout():
        """Called when the timer fires — close the menu and reopen login."""
        menu = _state.get("menu")
        if menu and menu.winfo_exists():
            menu.destroy()
        _state["menu"] = None
        open_login()

    def on_login(role, username):
        _state["timeout_id"] = None
        menu = MainMenu(root, role, username, on_logout=open_login)
        _state["menu"] = menu
        for widget in (root, menu):
            try:
                widget.bind_all("<Any-KeyPress>", _reset_timer, add="+")
                widget.bind_all("<Any-ButtonPress>", _reset_timer, add="+")
                widget.bind_all("<Motion>", _reset_timer, add="+")
            except tk.TclError:
                pass
        _reset_timer()

    root.on_login = on_login

    def open_login():
        if _state["timeout_id"]:
            root.after_cancel(_state["timeout_id"])
            _state["timeout_id"] = None
        LoginWindow(root, on_success=on_login)

    root.after(100, open_login)
    root.mainloop()


if __name__ == "__main__":
    main()