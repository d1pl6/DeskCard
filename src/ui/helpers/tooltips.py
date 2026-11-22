"""Small hover tooltips for the settings UI."""

import tkinter as tk

try:
    from .theme import THEME_BG, THEME_FG, THEME_FONT_SMALL, ui
except ImportError:  # started as a script, not as a package
    from theme import THEME_BG, THEME_FG, THEME_FONT_SMALL, ui


SETTING_TOOLTIPS = {
    "answer_prompt": (
        "What appears after you answer: text, audio, image, or a combination. "
        "Missing requested parts are shown as warnings; if none of the "
        "requested parts exist, the card is skipped."
    ),
    "enabled": "Run this exercise in the session.",
    "advanced": "Show experimental and fine-tuning options",
    "prompt_sub": 'Show "sub" from deck',
    "answer_sub": 'Show "sub" from deck',
    "difficulty": "Controls how hard a card is: re-listens, choice count, time limit",
    "prompt_listens": "A number of extra prompt replays. (not a duration)",
    "answer_choices": "How many options to show. Minimum 2",
    "answer_connections": "How many pairs to connect. From 2 to 10",
    "answer_time": "Time to answer before the card counts as wrong. Empty/0 = no limit",
    "other_close_time": "Time the answer stays on screen after a mistake. 0 = immediate",
    "other_repeat": (
        "The card is not dismissed until the answer has no mistakes "
        "(card cannot be scored wrong in this mode). Max attempts is blocked"
    ),
    "other_attempts": (
        "Tries before the card is scored as wrong. Disabled while Repeat until correct is on"
    ),
    "prompt_type": "What is shown before you answer: text, audio, image, or a combination",
    "other_score": "0-100, 55, 55-60. Empty or malformed input blocks Start.",
    "other_direction": "Normal: prompt→answer. Reverse: answer→prompt. Random: per card",
    "random_score": (
        "Adds 0–N to each card's score when choosing the next card. "
        "Default 10; 0 = exact lowest score"
    ),
    "sub_always": "Show this side's sub text as soon as that side appears.",
    "sub_after": "Show the sub only after the answer is revealed.",
    "sub_never": "Hide this sub.",
    "global_delay": (
        "Time to wait before each card appears. Accepts 30s, 1m30s, 1h5m30s, "
        "or plain 30 (= 30 s). 0/empty = immediate. Jitter is applied to this delay."
    ),
    "global_session": (
        "How many batches to play. Empty = unlimited. The session ends after "
        "this many batches, not cards."
    ),
    "global_batch": (
        "Cards shown per batch. Empty = 1. The delay is applied before each "
        "batch, including the first."
    ),
    "global_jitter": (
        "Randomness applied only to the pre-card delay. 50% of 1m gives 30–90s. "
        "0/empty = exact delay."
    ),
    "loaded_categories": (
        "Categories come from the deck. Checkboxes control which categories "
        "are included in the session."
    ),
    "browse_deck": "Open a file picker to choose a deck JSON file.",
    "deck_entry": "Path to the deck JSON file. Press Enter or use Browse deck to load it.",
    "deck_status": "Shows card/category counts and load warnings for the current deck.",
    "edit_deck": "Planned: open the selected deck in an editor.",
    "settings": "Open app preferences.",
    "about": "Show version and about information.",
    "quit": "Close DeskCard immediately.",
    "reset": "Restore all settings to defaults and unload the current deck. Requires confirmation.",
    "load_settings": (
        "Load exercise and global settings from a JSON file, optionally "
        "including the deck path."
    ),
    "save_settings": "Save current settings and deck path to a JSON file.",
    "start": "Validate settings, write category states to the deck, and begin the study session.",
    "content_options": (
        "Use the corresponding field from the card. Combined modes can render "
        "several at once; missing parts produce warnings."
    ),
}


def tooltip_for_block(block):
    """Return the tooltip for a block, if it has one."""
    key = block.spec.get("key")
    if key:
        return SETTING_TOOLTIPS.get(key)
    if block.spec.get("text") == "Difficulty":
        return SETTING_TOOLTIPS["difficulty"]
    return None


CONTENT_LOCK_TOOLTIPS = {
    "audio_missing": "install pygame-ce (or python-pygame) to play audio",
    "image_missing": "install Pillow to display images",
    "audio_deck": "the loaded deck has audio errors",
    "image_deck": "the loaded deck has image errors",
    "text_deck": "the loaded deck has text errors",
}


def content_lock_tooltip(medium, *, library_missing, deck_error):
    """Explain why a content option is unavailable."""
    reasons = []
    if library_missing:
        reasons.append(CONTENT_LOCK_TOOLTIPS[f"{medium}_missing"])
    if deck_error:
        reasons.append(CONTENT_LOCK_TOOLTIPS[f"{medium}_deck"])
    return f"{medium.title()} option is locked: " + " and ".join(reasons) + "."


def tooltip_for_option(block_key, option_key):
    """Return a tooltip for an individual radio/check option, if it has one."""
    if block_key in ("prompt_sub", "answer_sub"):
        return SETTING_TOOLTIPS.get(f"sub_{option_key}")
    if block_key in ("prompt_type", "answer_prompt") and option_key in (
            "text_only", "audio_only", "image_only"):
        return SETTING_TOOLTIPS["content_options"]
    return None


_TOOLTIP_WINDOWS = {}


def _tooltip_window(root):
    """Reuse one tooltip window per root; creating one on every hover is
    unreliable with some window managers (it can stay hidden until a click)."""
    window = _TOOLTIP_WINDOWS.get(root)
    try:
        if window is not None and window.winfo_exists():
            return window
    except tk.TclError:
        pass
    window = tk.Toplevel(root)
    window.withdraw()
    window.wm_overrideredirect(True)
    window.transient(root)
    window.attributes("-topmost", True)
    try:  # X11 only; helps WMs map the window without a click.
        window.attributes("-type", "tooltip")
    except tk.TclError:
        pass
    window.configure(bg=THEME_BG)
    label = tk.Label(
        window, justify="left", wraplength=ui(320),
        bg=THEME_BG, fg=THEME_FG, font=THEME_FONT_SMALL,
        relief="solid", borderwidth=1, padx=ui(8), pady=ui(6),
    )
    label.pack()
    window._tooltip_label = label
    _TOOLTIP_WINDOWS[root] = window
    return window


class _Tooltip:
    """One hover bubble bound to one widget."""

    DELAY_MS = 400

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.root = widget.winfo_toplevel()
        self.window = None
        self.job = None
        widget._tooltip_text = text
        self.bindings = (
            ("<Enter>", widget.bind("<Enter>", self._schedule, add="+")),
            ("<Leave>", widget.bind("<Leave>", self._hide, add="+")),
            ("<Destroy>", widget.bind("<Destroy>", self._on_destroy, add="+")),
        )

    def _schedule(self, event):
        self._hide()
        x = getattr(event, "x_root", 0) or self.widget.winfo_pointerx()
        y = getattr(event, "y_root", 0) or self.widget.winfo_pointery()
        try:
            self.job = self.widget.after(self.DELAY_MS, lambda: self._show(x, y))
        except tk.TclError:
            pass

    def _show(self, x, y):
        self.job = None
        if not self.widget.winfo_exists():
            return
        window = _tooltip_window(self.root)
        label = window._tooltip_label
        label.configure(text=self.text)
        window.update_idletasks()
        width = label.winfo_reqwidth()
        height = label.winfo_reqheight()
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        x = min(max(0, x + 16), max(0, screen_w - width - 8))
        y = min(max(0, y + 22), max(0, screen_h - height - 8))
        window.wm_geometry(f"{width}x{height}+{x}+{y}")
        window.deiconify()
        window.lift()
        window.attributes("-topmost", True)
        self.window = window

    def _hide(self, _event=None):
        if self.job is not None:
            try:
                self.widget.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None
        if self.window is not None:
            try:
                self.window.withdraw()
            except tk.TclError:
                pass
            self.window = None

    def _on_destroy(self, event):
        if event.widget is self.widget:
            self._hide()


def set_tooltip(widget, text, *, remember_default=False):
    """Replace a widget's tooltip, keeping the original for later restoration."""
    if remember_default or not hasattr(widget, "_tooltip_default"):
        widget._tooltip_default = text
    old = getattr(widget, "_tooltip", None)
    if old is not None:
        old._hide()
        for sequence, command in old.bindings:
            try:
                widget.unbind(sequence, command)
            except tk.TclError:
                pass
        del widget._tooltip
    if not text:
        widget._tooltip_text = None
        return
    widget._tooltip = _Tooltip(widget, text)


def add_tooltip(widget, text):
    """Bind a tooltip to a widget and all of its descendants."""
    if not text:
        return
    for item in [widget, *_descendants(widget)]:
        if getattr(item, "_tooltip", None) is not None:
            continue
        set_tooltip(item, text, remember_default=True)


def _descendants(widget):
    found = []
    for child in widget.winfo_children():
        found.append(child)
        found.extend(_descendants(child))
    return found
