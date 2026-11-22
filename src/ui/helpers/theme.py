"""Shared look of the DeskCard UI: colours, fonts and the ttk theme."""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


THEME_BG = "#2b2b2b"
THEME_FG = "#e8e8e8"
THEME_ACCENT = "#4a9eff"
THEME_ACCENT_HOVER = "#2f6fae"
THEME_ACCENT_FG = "#ffffff"
THEME_FIELD_BG = "#3c3c3c"
THEME_FG_DIM = "#8a8a8a"
THEME_DANGER = "#a03a37"
THEME_DANGER_HOVER = "#7d2b29"

THEME_FONT_FAMILY = "Segoe UI"
THEME_FONT = (THEME_FONT_FAMILY, 10)
THEME_FONT_BOLD = (THEME_FONT_FAMILY, 10, "bold")
THEME_FONT_SMALL = (THEME_FONT_FAMILY, 8)
THEME_FONT_TITLE = (THEME_FONT_FAMILY, 12, "bold")

UI_SCALE = 1.0
_BASE_SCALING = None
_FONT_CACHE = {}


def ui(value):
    """Convert a design-space pixel value to the current UI scale."""
    if value is None:
        return None
    if isinstance(value, (tuple, list)):
        return type(value)(ui(item) for item in value)
    number = float(value)
    if number == 0:
        return 0
    return max(1, int(round(number * UI_SCALE)))


def apply_font_scale(root, percent):
    """Scale fonts, padding and other pixel metrics across the widget tree.

    Point sizes follow Tk's ``scaling``. Pixel values do not, so existing
    widgets are updated in place and new widgets use :func:`ui` at build time.
    """
    global UI_SCALE, _BASE_SCALING
    try:
        value = max(50, min(200, int(percent))) / 100
    except (TypeError, ValueError):
        value = 1.0
    if _BASE_SCALING is None:
        _BASE_SCALING = float(root.tk.call("tk", "scaling"))
    try:
        root.tk.call("tk", "scaling", _BASE_SCALING * value)
    except tk.TclError:
        return
    if abs(value - UI_SCALE) < 1e-6:
        return
    ratio = value / UI_SCALE
    _rescale_widget_fonts(root)
    _rescale_widget_metrics(root, ratio)
    UI_SCALE = value
    ttk.Style(root).configure("TNotebook.Tab", padding=ui([12, 4]))


def _scaled_number(value, ratio):
    if isinstance(value, (tuple, list)):
        return type(value)(_scaled_number(item, ratio) for item in value)
    parts = str(value).split()
    if len(parts) == 2:
        return tuple(_scaled_number(part, ratio) for part in parts)
    try:
        number = int(parts[0])
    except (ValueError, IndexError):
        return value
    return 0 if number == 0 else max(1, int(round(number * ratio)))


def _rescale_widget_metrics(root, ratio):
    """Scale padding, wrapping and slider lengths of existing widgets."""
    for widget in _walk(root):
        for key in ("wraplength", "length"):
            try:
                current = widget.cget(key)
            except (tk.TclError, KeyError):
                continue
            scaled = _scaled_number(current, ratio)
            if scaled != current:
                try:
                    widget.configure(**{key: scaled})
                except tk.TclError:
                    pass
        for key in ("padx", "pady", "ipadx", "ipady"):
            try:
                current = widget.cget(key)
            except (tk.TclError, KeyError):
                continue
            scaled = _scaled_number(current, ratio)
            if scaled != current:
                try:
                    widget.configure(**{key: scaled})
                except tk.TclError:
                    pass
        manager = widget.winfo_manager()
        if manager == "pack":
            info, setter = widget.pack_info(), widget.pack_configure
        elif manager == "grid":
            info, setter = widget.grid_info(), widget.grid_configure
        else:
            continue
        updates = {}
        for key in ("padx", "pady", "ipadx", "ipady"):
            if key in info:
                scaled = _scaled_number(info[key], ratio)
                if scaled != info[key]:
                    updates[key] = scaled
        if updates:
            setter(**updates)
        if manager == "grid":
            columns, rows = widget.grid_size()
            for index in range(columns):
                current = widget.grid_columnconfigure(index).get("minsize", 0)
                scaled = _scaled_number(current, ratio)
                if scaled != current:
                    widget.grid_columnconfigure(index, minsize=scaled)
            for index in range(rows):
                current = widget.grid_rowconfigure(index).get("minsize", 0)
                scaled = _scaled_number(current, ratio)
                if scaled != current:
                    widget.grid_rowconfigure(index, minsize=scaled)


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _rescale_widget_fonts(root):
    """Re-create the fonts of all existing widgets under the new scaling."""
    _FONT_CACHE.clear()

    def walk(widget):
        try:
            spec = widget.cget("font")
        except (tk.TclError, KeyError):
            spec = None
        if spec:
            try:
                current = tkfont.Font(root, font=spec)
                attributes = {
                    "family": current["family"],
                    "size": current["size"],
                    "weight": current["weight"],
                    "slant": current["slant"],
                    "underline": current["underline"],
                    "overstrike": current["overstrike"],
                }
                key = tuple(attributes.values())
                font = _FONT_CACHE.get(key)
                if font is None:
                    font = tkfont.Font(root, **attributes)
                    _FONT_CACHE[key] = font
                widget.configure(font=font)
            except (tk.TclError, ValueError):
                pass
        for child in widget.winfo_children():
            walk(child)

    walk(root)


def apply_theme(root):
    """Apply the project theme as defaults; per-widget options override these."""
    root.configure(bg=THEME_BG)
    root.option_add("*background", THEME_BG)
    root.option_add("*foreground", THEME_FG)
    root.option_add("*font", THEME_FONT)
    root.option_add("*selectColor", THEME_FIELD_BG)
    root.option_add("*Entry.background", THEME_FIELD_BG)
    root.option_add("*Text.background", THEME_FIELD_BG)
    root.option_add("*Listbox.background", THEME_FIELD_BG)
    root.option_add("*Button.background", THEME_ACCENT)
    root.option_add("*Button.foreground", THEME_ACCENT_FG)
    style = ttk.Style(root)
    try:
        style.theme_use("default")
    except tk.TclError:
        pass
    style.configure(".", background=THEME_BG, foreground=THEME_FG,
                    fieldbackground=THEME_FIELD_BG, font=THEME_FONT)
    style.configure("TNotebook.Tab", background=THEME_BG, foreground=THEME_FG,
                    padding=ui([12, 4]))
    style.map(
        "TNotebook.Tab",
        background=[("selected", THEME_ACCENT), ("active", THEME_ACCENT_HOVER)],
        foreground=[("selected", THEME_ACCENT_FG), ("active", THEME_ACCENT_FG)],
    )
