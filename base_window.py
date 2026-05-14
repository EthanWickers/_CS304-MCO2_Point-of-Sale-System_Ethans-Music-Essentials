import tkinter as tk

class BaseWindow(tk.Toplevel):
    """
    Base class for every Toplevel window in this app.

    Provides:
      - center() — centres the window on screen
      - show()   — makes the window visible and centred in one call

    All windows subclass this instead of tk.Toplevel directly.
    """

    def __init__(self, master, title: str = "", width: int = 800, height: int = 500):
        super().__init__(master)
        self._win_w = width
        self._win_h = height
        if title:
            self.title(title)
        self.geometry(f"{width}x{height}")

    def center(self):
        """Centre this window on the screen."""
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - self._win_w) // 2
        y = (sh - self._win_h) // 2
        self.geometry(f"{self._win_w}x{self._win_h}+{x}+{y}")

    def show(self):
        """Make the window visible, centred, and focused."""
        self.deiconify()
        self.center()
        self.lift()
        self.focus_force()