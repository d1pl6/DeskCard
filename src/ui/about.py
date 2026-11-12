"""The About window: app identity, license and repository link."""

import tkinter as tk
import webbrowser

try:
    from .theme import THEME_ACCENT, THEME_FG, THEME_FONT, THEME_FONT_TITLE
except ImportError:  # started as a script, not as a package
    from theme import THEME_ACCENT, THEME_FG, THEME_FONT, THEME_FONT_TITLE


APP_NAME = "DeskCard"
APP_VERSION = "0.1.0"
APP_AUTHOR = "d1pl"
APP_REPO = "https://github.com/d1pl6/DeskCard"
APP_LICENSE = "GPL-2.0-or-later"


class AboutWindow(tk.Toplevel):
    """Static About dialog; one per parent, raised instead of reopened."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"About {APP_NAME}")
        self.resizable(False, False)
        self.transient(parent)

        frame = tk.Frame(self, padx=20, pady=16)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=APP_NAME, font=THEME_FONT_TITLE).pack(anchor="w")
        tk.Label(frame, text=f"Version {APP_VERSION}", font=THEME_FONT).pack(anchor="w", pady=(2, 12))
        tk.Label(frame, text=f"Author: {APP_AUTHOR or 'Not set'}", font=THEME_FONT).pack(anchor="w")
        tk.Label(frame, text=f"License: {APP_LICENSE}", font=THEME_FONT).pack(anchor="w")

        self.repository = tk.Label(
            frame,
            text=f"Repository: {APP_REPO or 'Not set'}",
            font=THEME_FONT,
            fg=THEME_ACCENT if APP_REPO else THEME_FG,
            cursor="hand2" if APP_REPO else "",
        )
        self.repository.pack(anchor="w", pady=(6, 0))
        if APP_REPO:
            self.repository.bind("<Button-1>", lambda _event: webbrowser.open(APP_REPO))

        tk.Button(frame, text="Close", command=self.destroy).pack(anchor="e", pady=(16, 0))

        self._place_over(parent)

    def _place_over(self, parent):
        """Centre horizontally and sit a third of the way down the main window."""
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.focus_set()


def show_about(parent):
    """Open the About window, or raise it when it is already open."""
    window = getattr(parent, "_about_window", None)
    if window is not None and window.winfo_exists():
        window.lift()
        window.focus_set()
        return window
    window = AboutWindow(parent)
    parent._about_window = window
    return window
