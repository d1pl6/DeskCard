"""Shared look of the DeskCard UI: colours, fonts and the ttk theme."""

import tkinter as tk
from tkinter import ttk


THEME_BG = "#2b2b2b"
THEME_FG = "#e8e8e8"
THEME_ACCENT = "#4a9eff"
THEME_ACCENT_HOVER = "#2f6fae"
THEME_ACCENT_FG = "#ffffff"
THEME_FIELD_BG = "#3c3c3c"
THEME_FG_DIM = "#8a8a8a"

THEME_FONT_FAMILY = "Segoe UI"
THEME_FONT = (THEME_FONT_FAMILY, 10)
THEME_FONT_BOLD = (THEME_FONT_FAMILY, 10, "bold")
THEME_FONT_SMALL = (THEME_FONT_FAMILY, 8)
THEME_FONT_TITLE = (THEME_FONT_FAMILY, 12, "bold")


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
                    padding=[12, 4])
    style.map(
        "TNotebook.Tab",
        background=[("selected", THEME_ACCENT), ("active", THEME_ACCENT_HOVER)],
        foreground=[("selected", THEME_ACCENT_FG), ("active", THEME_ACCENT_FG)],
    )
