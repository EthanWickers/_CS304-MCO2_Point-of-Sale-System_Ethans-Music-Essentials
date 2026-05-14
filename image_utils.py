"""
Product image utilities for EME POS.

Requires Pillow:
    pip install Pillow

If Pillow is not installed the app still runs; image widgets display a
friendly warning instead of crashing.

Storage strategy
────────────────
  1. image_path  — absolute path to the original file on disk (fast, small)
  2. image_blob  — raw bytes stored in SQLite (portable fallback)

When loading, path is tried first; blob is the fallback.
When saving, both are written together so portability is automatic.
"""

import io
import os
import sys
import tkinter as tk

try:
    from PIL import Image, ImageTk
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

_PRIMARY   = "#00b4d8"
_ACCENT    = "#90e0ef"
_WHITE_BG  = "#ebebeb"
_SECONDARY = "#023e8a"

_BAR_NORMAL = "#c0c0c0"
_BAR_HOVER  = "#a0a0a0"
_BAR_DRAG   = "#808080"

_ICON_FILES = {
    "main":      "main_icon.ico",
    "inventory": "inventory.ico",
    "sales":     "sales.ico",
    "settings":  "settings.ico",
    "users":     "users.ico",
}

def _icons_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "assets", "icons")
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "icons")


def set_icon(window, icon: str = "main") -> None:
    """
    Set the title-bar icon on *window* (any tk.Tk or tk.Toplevel).

    *icon* must be one of: 'main', 'inventory', 'sales', 'settings', 'users'.
    Silently does nothing if the file is missing or the call fails
    (so the rest of the app is never broken by a missing .ico).
    """
    filename = _ICON_FILES.get(icon, _ICON_FILES["main"])
    path = os.path.join(_icons_dir(), filename)
    try:
        window.iconbitmap(path)
    except Exception as e:
        print(f"[icon] failed to set '{icon}' icon -- {path!r}: {e}")


# >>> Product image directory helpers >>>
def prod_images_dir() -> str:
    """
    Absolute path to the product-images folder.

    Dev  (.py)  ->  <project root>/assets/prod_images/
    Dist (.exe) ->  sys._MEIPASS/assets/prod_images/
                    (files must be added to PyInstaller datas)

    The folder is created automatically on first use.
    """
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(base, "assets", "prod_images")
    os.makedirs(folder, exist_ok=True)
    return folder

def resolve_product_image_path(relative_filename: str) -> str:
    """
    Convert a stored relative filename (e.g. 'guitar_001.jpg') to the
    full absolute path inside assets/prod_images/.

    Also handles legacy records that stored an absolute path — those
    are returned as-is so old products still display until re-saved.
    Returns an empty string if relative_filename is falsy.
    """
    if not relative_filename:
        return ""
    if os.path.isabs(relative_filename):
        return relative_filename
    return os.path.join(prod_images_dir(), relative_filename)

def copy_image_to_assets(src_path: str) -> str:
    """
    Copy the image at src_path into assets/prod_images/ and return
    the relative filename (e.g. 'guitar_001.jpg').

    If src is already inside assets/prod_images/ no copy is made.
    If a file with the same name already exists it is overwritten,
    keeping re-saves of the same product idempotent.
    Raises OSError if the copy fails.
    """
    import shutil
    filename = os.path.basename(src_path)
    dest = os.path.join(prod_images_dir(), filename)
    if os.path.normcase(os.path.abspath(src_path)) == os.path.normcase(os.path.abspath(dest)):
        return filename
    shutil.copy2(src_path, dest)
    return filename   


# >>> Image I/O >>>
def load_pil_image(path: str = None, blob: bytes = None):
    """
    Load a PIL Image from a file path or raw BLOB bytes.
    Path is tried first; blob is used as fallback.
    Returns None if Pillow is missing or both sources fail.
    """
    if not PILLOW_AVAILABLE:
        return None

    if path and os.path.isfile(path):
        try:
            img = Image.open(path)
            img.load()
            return img
        except Exception:
            pass

    if blob:
        try:
            return Image.open(io.BytesIO(blob))
        except Exception:
            pass

    return None

def path_to_blob(path: str) -> bytes:
    """Read an image file from disk and return its raw bytes for BLOB storage."""
    with open(path, "rb") as f:
        return f.read()

def make_thumbnail(pil_img, max_w: int = 150, max_h: int = 120):
    """
    Return a copy of *pil_img* shrunk to fit within (max_w x max_h),
    preserving the aspect ratio. The original image is not modified.
    """
    img = pil_img.copy()
    img.thumbnail((max_w, max_h), Image.LANCZOS)
    return img

def pick_image_file(parent=None) -> str:
    """
    Open a native file-chooser dialog for image selection.
    Returns the chosen absolute path, or an empty string if cancelled.
    """
    from tkinter import filedialog
    path = filedialog.askopenfilename(
        title="Select Product Image",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff"),
            ("All files", "*.*"),
        ],
        parent=parent,
    )
    return path or ""


# >>>>>>> Image Preview Panel >>>>>>>
class ImagePreviewPanel(tk.Frame):
    """
    Collapsible, resizable side panel that displays a product image.

    Features
    --------
    * A single combined bar on the left edge acts as BOTH the drag handle
      (resize by dragging) and the collapse/expand toggle (click without
      dragging).  It is styled in scrollbar-gray to match the OS scrollbars.
    * update_image() NEVER auto-expands the panel — the user's collapse
      state is always respected.
    * Scrollable canvas with mouse-wheel support.
    * Placeholder graphic when no image is loaded.

    Typical usage
    -------------
        panel = ImagePreviewPanel(parent, width=230, label_text="Product Image")
        panel.pack(side="right", fill="y")

        panel.update_image(path="/path/to/photo.jpg", blob=None)
        panel.clear()
    """

    _PLACEHOLDER    = "No image"
    _MIN_WIDTH      = 120
    _MAX_WIDTH      = 480
    _COLLAPSED_W    = 14    
    _BAR_W          = 14    
    _DRAG_THRESHOLD = 4

    def __init__(
        self,
        master,
        width: int = 230,
        label_text: str = "Product Image",
        bg: str = _WHITE_BG,
        **kwargs,
    ):
        kwargs.pop("width", None)
        super().__init__(master, bg=bg, **kwargs)

        self._expanded_w  = max(self._MIN_WIDTH, width)
        self._label_text  = label_text
        self._bg          = bg
        self._photo       = None    
        self._collapsed   = False

        #> Drag Tracking
        self._drag_start_x = None
        self._drag_start_w = None
        self._drag_moved   = False

        self._build()
        self.after(10, self._apply_width)



    def _build(self):
        self._bar = tk.Frame(
            self, bg=_BAR_NORMAL, width=self._BAR_W,
            cursor="sb_h_double_arrow",
        )
        self._bar.pack(side="left", fill="y")
        self._bar.pack_propagate(False)

        self._arrow = tk.Label(
            self._bar, text="<",
            bg=_BAR_NORMAL, fg="#404040",
            font=("Segoe UI", 7, "bold"),
            cursor="sb_h_double_arrow",
        )
        self._arrow.place(relx=0.5, rely=0.5, anchor="center")

        for widget in (self._bar, self._arrow):
            widget.bind("<ButtonPress-1>",   self._on_press)
            widget.bind("<B1-Motion>",       self._on_motion)
            widget.bind("<ButtonRelease-1>", self._on_release)
            widget.bind("<Enter>",           self._on_enter)
            widget.bind("<Leave>",           self._on_leave)


        self._content = tk.Frame(self, bg=self._bg)
        self._content.pack(side="left", fill="both", expand=True)

        if self._label_text:
            header = tk.Frame(self._content, bg=self._bg)
            header.pack(fill="x", pady=(6, 2), padx=4)
            tk.Label(
                header, text=self._label_text,
                font=("Segoe UI", 9, "bold"),
                bg=self._bg, fg=_SECONDARY,
            ).pack(side="left")

        wrap = tk.Frame(self._content, bg=self._bg)
        wrap.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        vbar = tk.Scrollbar(wrap, orient="vertical")
        hbar = tk.Scrollbar(wrap, orient="horizontal")

        self.canvas = tk.Canvas(
            wrap,
            bg="#f0f0f0", bd=0,
            highlightthickness=1, highlightbackground="#d0d0d0",
            yscrollcommand=vbar.set,
            xscrollcommand=hbar.set,
        )
        vbar.config(command=self.canvas.yview)
        hbar.config(command=self.canvas.xview)

        vbar.pack(side="right", fill="y")
        hbar.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(-(e.delta // 120), "units"),
        )
        self.canvas.bind(
            "<Shift-MouseWheel>",
            lambda e: self.canvas.xview_scroll(-(e.delta // 120), "units"),
        )

        self._show_placeholder()


    def update_image(self, path: str = None, blob: bytes = None):
        """
        Load and display an image from *path* or *blob*.

        The panel's collapsed/expanded state is NEVER changed automatically —
        the user's choice is always respected.
        """
        if not PILLOW_AVAILABLE:
            self._show_pillow_missing()
            return

        pil_img = load_pil_image(path, blob)
        if pil_img is None:
            self._show_placeholder()
            return

        self._photo = ImageTk.PhotoImage(pil_img)
        w, h = pil_img.size
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, w, h))
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self.canvas.after(10, self._center_view)

    def _center_view(self):
        """Scroll the canvas so the image is centred in the viewport."""
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        sr = self.canvas.cget("scrollregion")
        if not sr:
            return
        try:
            _, _, img_w, img_h = (float(v) for v in str(sr).split())
        except ValueError:
            return
        if img_w > cw:
            self.canvas.xview_moveto((img_w / 2 - cw / 2) / img_w)
        else:
            self.canvas.xview_moveto(0)
        if img_h > ch:
            self.canvas.yview_moveto((img_h / 2 - ch / 2) / img_h)
        else:
            self.canvas.yview_moveto(0)

    def clear(self):
        """Reset the panel to its empty / placeholder state."""
        self._show_placeholder()

    def toggle(self):
        """Collapse or expand the content area."""
        if self._collapsed:
            self._expand()
        else:
            self._collapse()

    # >>> Collapse / expand >>>
    def _collapse(self):
        self._collapsed = True
        self._content.pack_forget()
        self._arrow.config(text=">")
        self.config(width=self._COLLAPSED_W)
        self.pack_propagate(False)

    def _expand(self):
        self._collapsed = False
        self._content.pack(side="left", fill="both", expand=True)
        self._arrow.config(text="<")
        self.pack_propagate(True)
        self._apply_width()

    # >>> Bar event handlers >>>
    def _on_press(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_w = self._expanded_w
        self._drag_moved   = False
        self._set_bar_color(_BAR_DRAG)

    def _on_motion(self, event):
        if self._drag_start_x is None:
            return
        delta = self._drag_start_x - event.x_root
        if not self._drag_moved and abs(delta) >= self._DRAG_THRESHOLD:
            self._drag_moved = True

        if self._drag_moved and not self._collapsed:
            new_w = max(self._MIN_WIDTH, min(self._MAX_WIDTH, self._drag_start_w + delta))
            self._expanded_w = new_w
            self._apply_width()

    def _on_release(self, event):
        was_drag = self._drag_moved
        self._drag_start_x = None
        self._drag_start_w = None
        self._drag_moved   = False

        self._set_bar_color(_BAR_HOVER)

        if not was_drag:
            self.toggle()

    def _on_enter(self, event):
        if self._drag_start_x is None:
            self._set_bar_color(_BAR_HOVER)

    def _on_leave(self, event):
        if self._drag_start_x is None:
            self._set_bar_color(_BAR_NORMAL)

    def _set_bar_color(self, color: str):
        self._bar.config(bg=color)
        self._arrow.config(bg=color)

    def _apply_width(self):
        if not self._collapsed:
            self.config(width=self._expanded_w)
            self.pack_propagate(False)


    def _show_placeholder(self):
        self._photo = None
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, 1, 1))
        self.canvas.after(10, self._draw_placeholder_text)

    def _draw_placeholder_text(self):
        cw = self.canvas.winfo_width()  or 190
        ch = self.canvas.winfo_height() or 190
        self.canvas.delete("all")
        self.canvas.create_text(
            cw // 2, ch // 2,
            text=self._PLACEHOLDER,
            font=("Segoe UI", 10), fill="#c0c0c0",
            anchor="center", justify="center",
        )

    def _show_pillow_missing(self):
        self.canvas.delete("all")
        self.canvas.after(10, lambda: self.canvas.create_text(
            (self.canvas.winfo_width() or 190) // 2,
            (self.canvas.winfo_height() or 190) // 2,
            text="Pillow not installed\n\npip install Pillow",
            font=("Segoe UI", 9), fill="#e74c3c",
            anchor="center", justify="center",
        ))