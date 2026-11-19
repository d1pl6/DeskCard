import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox

try:
    from .about import APP_NAME, show_about
    from .helpers.blocks import ExerciseTab, Section
    from .helpers.tooltips import SETTING_TOOLTIPS, add_tooltip
    from .runner import SessionRunner
    from .helpers.theme import (
        THEME_ACCENT, THEME_DANGER, THEME_DANGER_HOVER, THEME_FIELD_BG,
        THEME_FG, THEME_FG_DIM, THEME_FONT, THEME_FONT_BOLD, THEME_FONT_SMALL,
        THEME_FONT_TITLE, apply_theme,
    )
    from ..config.loader import load_config
    from ..errors import ConfigError
    from ..session import Session, SettingsError, normalize_settings
except ImportError:  # started as a script, not as a package
    import sys

    from about import APP_NAME, show_about
    from helpers.blocks import ExerciseTab, Section
    from helpers.tooltips import SETTING_TOOLTIPS, add_tooltip
    from runner import SessionRunner
    from helpers.theme import (
        THEME_ACCENT, THEME_DANGER, THEME_DANGER_HOVER, THEME_FIELD_BG,
        THEME_FG, THEME_FG_DIM, THEME_FONT, THEME_FONT_BOLD, THEME_FONT_SMALL,
        THEME_FONT_TITLE, apply_theme,
    )

    # Make the project root importable so the shared config package is found.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.config.loader import load_config
    from src.errors import ConfigError
    from src.session import Session, SettingsError, normalize_settings


def _scroll_wheel(event):
    """Scroll the ScrollableFrame under the pointer, wherever the pointer is."""
    widget = event.widget.winfo_containing(event.x_root, event.y_root)
    while widget is not None and not isinstance(widget, ScrollableFrame):
        widget = widget.master
    if widget is None:
        return
    if getattr(event, "num", 0) == 4:
        step = -1
    elif getattr(event, "num", 0) == 5:
        step = 1
    elif getattr(event, "delta", 0) > 0:
        step = -1
    elif getattr(event, "delta", 0) < 0:
        step = 1
    else:
        return
    # Shift turns the wheel into horizontal scrolling.
    if event.state & 0x0001:
        widget.scroll_x(step)
    else:
        widget.scroll(step)


class ScrollableFrame(tk.Frame):
    """A frame that scrolls both ways. Put your widgets in `.body`, not in this."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._canvas = tk.Canvas(self, highlightthickness=0, xscrollincrement=20, yscrollincrement=20)
        self._vbar = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._hbar = tk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=self._vbar.set, xscrollcommand=self._hbar.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vbar.grid(row=0, column=1, sticky="ns")
        self._hbar.grid(row=1, column=0, sticky="ew")
        self._vbar.grid_remove()
        self._hbar.grid_remove()
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.body = tk.Frame(self._canvas)
        self._window = self._canvas.create_window((0, 0), window=self.body, anchor="nw")
        # The scroll region follows whatever size the body is given.
        self.body.bind("<Configure>", self._on_body)
        self._canvas.bind("<Configure>", self._on_canvas)
        self._bind_wheel()

    def _bind_wheel(self):
        """Bind the wheel once per window; the handler picks the panel."""
        top = self.winfo_toplevel()
        if getattr(top, "_scroll_wheel_bound", False):
            return
        top._scroll_wheel_bound = True
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            top.bind_all(sequence, _scroll_wheel)

    def _on_body(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._update_bars()

    def _on_canvas(self, event):
        # Keep the body at least as wide as the canvas, but let it grow past
        # it when the content is wider (that is what the horizontal bar is for).
        width = max(event.width, self.body.winfo_reqwidth())
        self._canvas.itemconfigure(self._window, width=width)
        self._update_bars()

    def _update_bars(self):
        """Show each scrollbar only while it is actually needed."""
        width = self._canvas.winfo_width()
        height = self._canvas.winfo_height()
        if width <= 1 or height <= 1:
            return
        self._toggle(self._vbar, self.body.winfo_reqheight() > height)
        self._toggle(self._hbar, self.body.winfo_reqwidth() > width)

    @staticmethod
    def _toggle(bar, needed):
        managed = bool(bar.grid_info())
        if needed and not managed:
            bar.grid()
        elif not needed and managed:
            bar.grid_remove()

    def scroll(self, units):
        """Scroll the body vertically by `units` steps (positive scrolls down)."""
        self._canvas.yview_scroll(units, "units")

    def scroll_x(self, units):
        """Scroll the body horizontally by `units` steps (positive scrolls right)."""
        self._canvas.xview_scroll(units, "units")

    def label(self, **kwargs):
        return tk.Label(self.body, **kwargs)


# Shared spacing so every tab and panel lines up the same way.
# Window sizing. WINDOW_SIZE is preferred, WINDOW_MIN is the smallest usable
# size; both are clamped to the screen so the window never opens off-screen.
WINDOW_SIZE = (950, 900)
WINDOW_MIN = (760, 520)
WINDOW_MARGIN = (60, 100)

# Keys are the widget attribute names; "" means an empty field.
GLOBAL_FIELDS = {
    "delay": "global_time_entry",
    "session": "global_session_entry",
    "batch": "global_batch_entry",
    "jitter": "global_jitter_entry",
}
GLOBAL_DEFAULTS = {
    "global_time_entry": "1m",
    "global_session_entry": "",
    "global_batch_entry": "1",
    "global_jitter_entry": "0",
}


# Setting blocks. Each tab is a list of sections; a block is one labelled
# control. `advanced` blocks are hidden until the tab's Advanced box is on.
# A section can be marked advanced too, which hides its heading as well.
CONTENT_OPTIONS = [
    ("text_only", "Text only"),
    ("audio_only", "Audio only"),
    ("image_only", "Image only"),
    ("text_audio", "Text + Audio"),
    ("text_image", "Text + Image"),
    ("audio_image", "Audio + Image"),
    ("all", "All"),
]

SUB_OPTIONS = [
    ("always", "Always"),
    ("after", "After answer"),
    ("never", "Never"),
]

DIRECTION_OPTIONS = [
    ("normal", "Normal (P - A)"),
    ("reverse", "Reverse (A - P)"),
    ("random", "Random"),
]


def prompt_section(include_listens=True):
    """Prompt settings shared by Anki, Choose, Connect and Write."""
    blocks = [
        {"key": "prompt_type", "label": "Prompt content", "kind": "checks",
         "options": CONTENT_OPTIONS, "default": "text_only"},
        {"key": "prompt_sub", "label": "Show Sub", "kind": "radios",
         "advanced": True, "options": SUB_OPTIONS, "default": "always"},
    ]
    if include_listens:
        blocks.extend([
            {"kind": "subheading", "text": "Difficulty", "advanced": True},
            {"key": "prompt_listens", "label": "Re-listens allowed",
             "kind": "entry", "hint": "0 = none", "advanced": True, "default": "5"},
        ])
    return {"title": "Prompt settings", "blocks": blocks}


ANKI_SECTIONS = [
    prompt_section(include_listens=False),
    {
        "title": "Answer settings",
        "blocks": [
            {"key": "answer_prompt", "label": "Answer content", "kind": "checks",
             "options": CONTENT_OPTIONS, "default": "text_only"},
            {"key": "answer_sub", "label": "Show Sub", "kind": "radios",
             "advanced": True, "options": SUB_OPTIONS, "default": "after"},
            {"kind": "subheading", "text": "Difficulty", "advanced": True},
            {"key": "answer_time", "label": "Answer time limit",
             "kind": "entry", "hint": "0 = unlimited", "advanced": True, "default": "0"},
        ],
    },
    {
        "title": "Other",
        "blocks": [
            {"key": "other_direction", "label": "Direction", "kind": "radios",
             "options": DIRECTION_OPTIONS, "default": "normal"},
            {"key": "other_score", "label": "Score (0-100)", "kind": "entry",
             "default": "0-99"},
            {"key": "random_score", "label": "Random score for next card",
             "kind": "entry", "hint": "0 = exact lowest score", "advanced": True,
             "default": "10"},
            {"key": "other_close_time", "label": "Delay before the window closes",
             "kind": "entry", "advanced": True, "default": "3s"},
        ],
    },
]

CHOOSE_SECTIONS = [
    prompt_section(),
    {
        "title": "Answer settings",
        "blocks": [
            {"key": "answer_prompt", "label": "Answer content", "kind": "checks",
             "options": CONTENT_OPTIONS, "default": "text_only"},
            {"key": "answer_sub", "label": "Show Sub", "kind": "radios",
             "advanced": True, "options": SUB_OPTIONS, "default": "after"},
            {"kind": "subheading", "text": "Difficulty", "advanced": True},
            {"key": "answer_choices", "label": "Answer choices",
             "kind": "entry", "advanced": True, "default": "5"},
            {"key": "answer_time", "label": "Answer time limit",
             "kind": "entry", "hint": "0 = unlimited", "advanced": True, "default": "0"},
        ],
    },
    {
        "title": "Other",
        "blocks": [
            {"key": "other_direction", "label": "Direction", "kind": "radios",
             "options": DIRECTION_OPTIONS, "default": "normal"},
            {"key": "other_score", "label": "Score (0-100)", "kind": "entry",
             "default": "0-99"},
            {"key": "random_score", "label": "Random score for next card",
             "kind": "entry", "hint": "0 = exact lowest score", "advanced": True,
             "default": "10"},
            {"key": "other_close_time", "label": "Delay before the window closes",
             "kind": "entry", "advanced": True, "default": "3s"},
            {"key": "other_repeat", "kind": "check", "text": "Repeat until correct",
             "hint": "Closes only after a mistake-free answer", "advanced": True},
            {"key": "other_attempts", "label": "Max attempts", "kind": "entry",
             "hint": "Tries allowed before the card is marked wrong", "advanced": True},
        ],
    },
]

CONNECT_SECTIONS = [
    prompt_section(),
    {
        "title": "Answer settings",
        "blocks": [
            {"key": "answer_prompt", "label": "Answer content", "kind": "checks",
             "options": CONTENT_OPTIONS, "default": "text_only"},
            {"key": "answer_sub", "label": "Show Sub", "kind": "radios",
             "advanced": True, "options": SUB_OPTIONS, "default": "after"},
            {"kind": "subheading", "text": "Difficulty", "advanced": True},
            {"key": "answer_connections", "label": "Number of connections (max 10)",
             "kind": "entry", "advanced": True, "default": "5"},
            {"key": "answer_time", "label": "Answer time limit",
             "kind": "entry", "hint": "0 = unlimited", "advanced": True, "default": "0"},
        ],
    },
    {
        "title": "Other",
        "blocks": [
            {"key": "other_direction", "label": "Direction", "kind": "radios",
             "options": DIRECTION_OPTIONS, "default": "normal"},
            {"key": "other_score", "label": "Score (0-100)", "kind": "entry",
             "default": "0-99"},
            {"key": "random_score", "label": "Random score for next card",
             "kind": "entry", "hint": "0 = exact lowest score", "advanced": True,
             "default": "10"},
            {"key": "other_close_time", "label": "Delay before the window closes",
             "kind": "entry", "advanced": True, "default": "3s"},
            {"key": "other_repeat", "kind": "check", "text": "Repeat until correct",
             "hint": "Closes only after a mistake-free answer", "advanced": True},
            {"key": "other_attempts", "label": "Max attempts", "kind": "entry",
             "hint": "Tries allowed before the card is marked wrong", "advanced": True},
        ],
    },
]

WRITE_SECTIONS = [
    prompt_section(),
    {
        "title": "Answer settings",
        "blocks": [
            {"key": "answer_prompt", "label": "Answer content", "kind": "checks",
             "options": CONTENT_OPTIONS, "default": "text_only"},
            {"key": "answer_sub", "label": "Show Sub", "kind": "radios",
             "advanced": True, "options": SUB_OPTIONS, "default": "after"},
            {"kind": "subheading", "text": "Difficulty"},
            {"key": "highlight_character", "text": "Highlight wrong characters",
             "kind": "check"},
            {"key": "highlight_word", "text": "Highlight wrong words",
             "kind": "check"},
            {"key": "answer_time", "label": "Answer time limit",
             "kind": "entry", "hint": "0 = unlimited", "advanced": True, "default": "0"},
        ],
    },
    {
        "title": "Other",
        "blocks": [
            {"key": "other_direction", "label": "Direction", "kind": "radios",
             "options": DIRECTION_OPTIONS, "default": "normal"},
            {"key": "other_score", "label": "Score (0-100)", "kind": "entry",
             "default": "0-99"},
            {"key": "random_score", "label": "Random score for next card",
             "kind": "entry", "hint": "0 = exact lowest score", "advanced": True,
             "default": "10"},
            {"key": "other_close_time", "label": "Delay before the window closes",
             "kind": "entry", "advanced": True, "default": "3s"},
            {"key": "other_repeat", "kind": "check", "text": "Repeat until correct",
             "hint": "Closes only after a mistake-free answer", "advanced": True},
            {"key": "other_attempts", "label": "Max attempts", "kind": "entry",
             "hint": "Tries allowed before the card is marked wrong", "advanced": True},
        ],
    },
]


class Application:
    def __init__(self, root):
        self.root = root
        root.title(f"{APP_NAME}")
        self._fit_window()
        apply_theme(root)

        self._tabs = {}
        self.config = None
        self.settings_path = None
        self.category_vars = {}
        self.category_checks = {}

    # Header
        self.header = tk.Frame(root, borderwidth=1, relief=tk.GROOVE)
        self.header.pack(fill="x", side="top")
        self.header.rowconfigure(0, weight=1)
        self.header.rowconfigure(1, weight=1)
        self.header.columnconfigure(0, weight=1)
        self.header.columnconfigure(1, weight=3)
        self.header.columnconfigure(2, weight=3)

        self.header_name = tk.Label(self.header, text=APP_NAME, pady=10, padx=10, font=THEME_FONT_TITLE)
        self.header_name.grid(column=0, row=0, sticky="w")

        self.header_instructions = tk.Frame(self.header, pady=10, padx=10)
        self.header_instructions.grid(column=1, row=0, sticky="ns")

        self.header_instructions1 = tk.Label(self.header_instructions, text="1. Load deck")
        self.header_instructions1.grid(column=0, row=0, sticky="w", padx=10)

        self.header_instructions2 = tk.Label(self.header_instructions, text="2. Configure Exercises")
        self.header_instructions2.grid(column=0, row=1, sticky="w", padx=10)

        self.header_instructions3 = tk.Label(self.header_instructions, text="3. Configure Global Settings")
        self.header_instructions3.grid(column=1, row=0, sticky="w", padx=10)

        self.header_instructions4 = tk.Label(self.header_instructions, text="4. Start")
        self.header_instructions4.grid(column=1, row=1, sticky="w", padx=10)

        self.header_buttons = tk.Frame(self.header, pady=10, padx=10)
        self.header_buttons.grid(column=2, row=0, sticky="e")

        self.header_settings = tk.Button(self.header_buttons, text="Settings", command=self.on_header_settings)
        self.header_settings.grid(column=0, row=0, padx=10)
        add_tooltip(self.header_settings, SETTING_TOOLTIPS["settings"])

        self.header_about = tk.Button(self.header_buttons, text="About", command=self.on_header_about)
        self.header_about.grid(column=1, row=0)
        add_tooltip(self.header_about, SETTING_TOOLTIPS["about"])


    # Load desk
        self.desk = tk.Frame(root, borderwidth=1, relief=tk.GROOVE)
        self.desk.pack(fill="x")
        self.desk.columnconfigure(0, weight=1)

        self.desk_label = tk.Label(self.desk, text="Load deck", font=THEME_FONT_TITLE)
        self.desk_label.grid(column=0, row=0, sticky="w")

        self.desk_middle = tk.Frame(self.desk)
        self.desk_middle.grid(column=0, row=1, sticky="ew", pady=10)
        self.desk_middle.columnconfigure(0, weight=1)

        self.desk_entry = tk.Entry(self.desk_middle, borderwidth=1, relief=tk.SOLID)
        self.desk_entry.grid(column=0, row=0, sticky="ew", padx=(0, 10))
        self.desk_entry.bind("<Return>", self.on_desk_entry_submit)
        self.desk_entry.bind("<KP_Enter>", self.on_desk_entry_submit)
        add_tooltip(self.desk_entry, SETTING_TOOLTIPS["deck_entry"])

        self.desk_browse = tk.Button(self.desk_middle, text="Browse deck", command=self.on_desk_browse)
        self.desk_browse.grid(column=1, row=0, sticky="e")
        add_tooltip(self.desk_browse, SETTING_TOOLTIPS["browse_deck"])

        self.desk_actions = tk.Frame(self.desk)
        self.desk_actions.grid(column=0, row=2, sticky="ew")
        self.desk_actions.columnconfigure(1, weight=1)

        self.desk_edit = tk.Button(self.desk_actions, text="Edit deck", command=self.on_desk_edit)
        self.desk_edit.grid(column=0, row=0, sticky="w")
        add_tooltip(self.desk_edit, SETTING_TOOLTIPS["edit_deck"])

        self.desk_status = tk.Label(self.desk_actions, text="No deck selected")
        self.desk_status.grid(column=1, row=0, sticky="e")
        add_tooltip(self.desk_status, SETTING_TOOLTIPS["deck_status"])


    # Exercises
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=0, minsize=200)
        self.main_frame.rowconfigure(0, weight=1)

        # Notebook
        self.exercise_notebook = ttk.Notebook(self.main_frame)
        self.exercise_notebook.grid(column=0, row=0, sticky="nsew")

        self._build_exercise_tab("anki", "Anki", ANKI_SECTIONS)
        self._build_exercise_tab("choose", "Choose", CHOOSE_SECTIONS)
        self._build_exercise_tab("connect", "Connect", CONNECT_SECTIONS)
        self._build_exercise_tab("write", "Write", WRITE_SECTIONS)

    # Right column
        self.right_column = tk.Frame(self.main_frame, width=200)
        self.right_column.grid(column=1, row=0, sticky="ns")
        self.right_column.pack_propagate(False)

        # Global settings
        self.global_frame = tk.Frame(self.right_column, relief="groove", bd=2)
        self.global_frame.pack(side="top", fill="x")

        self.global_label = tk.Label(self.global_frame, text="Global Settings", font=THEME_FONT_BOLD)
        self.global_label.grid(row=0, column=0, columnspan=2, pady=(4, 6))

        row = 1
        self.global_time_text, self.global_time_entry, row = (
            self._global_setting(row, "Delay:", SETTING_TOOLTIPS["global_delay"]))
        self.global_session_text, self.global_session_entry, row = (
            self._global_setting(row, "Batches in session:", SETTING_TOOLTIPS["global_session"]))
        self.global_batch_text, self.global_batch_entry, row = (
            self._global_setting(row, "Cards in batch:", SETTING_TOOLTIPS["global_batch"]))
        self.global_jitter_text, self.global_jitter_entry, row = (
            self._global_setting(row, "Delay Jitter:", SETTING_TOOLTIPS["global_jitter"]))
        self._reset_globals()

        # Loaded categories
        self.categories_frame = tk.Frame(self.right_column, relief="groove", bd=2)
        self.categories_frame.pack(side="bottom", fill="both", expand=True)

        self.categories_scroll = ScrollableFrame(self.categories_frame)
        self.categories_scroll.pack(fill="both", expand=True)

        self.categories_label = self.categories_scroll.label(text="Loaded categories", font=THEME_FONT_BOLD)
        self.categories_label.pack(fill="x", padx=2)
        add_tooltip(self.categories_label, SETTING_TOOLTIPS["loaded_categories"])

        self.categories_list = tk.Frame(self.categories_scroll.body)
        self.categories_list.pack(fill="x")

        self.categories_empty = self.categories_scroll.label(text="No deck loaded", font=THEME_FONT_SMALL)
        self.categories_empty.pack(anchor="w", padx=6, pady=(4, 0))


    # Footer
        self.footer = tk.Frame(root, borderwidth=1, relief=tk.GROOVE)
        # Packed before the main area so the buttons keep their height when the
        # window is short.
        self.footer.pack(fill="x", side="bottom", before=self.main_frame)
        self.footer.columnconfigure(0, weight=1)

        self.footer_quit = tk.Button(
            self.footer, text="Quit", height=2, command=self.on_footer_quit,
            background=THEME_DANGER, activebackground=THEME_DANGER_HOVER,
        )
        self.footer_quit.grid(column=0, row=0, sticky="w")
        add_tooltip(self.footer_quit, SETTING_TOOLTIPS["quit"])

        self.footer_reset = tk.Button(
            self.footer, text="Reset", height=2, command=self.on_footer_reset,
            background=THEME_DANGER, activebackground=THEME_DANGER_HOVER,
        )
        self.footer_reset.grid(column=2, row=0, padx=(0, 10))
        add_tooltip(self.footer_reset, SETTING_TOOLTIPS["reset"])

        self.footer_load = tk.Button(self.footer, text="Load settings", height=2, command=self.on_footer_load)
        self.footer_load.grid(column=3, row=0, padx=(0, 10))
        add_tooltip(self.footer_load, SETTING_TOOLTIPS["load_settings"])

        self.footer_save = tk.Button(self.footer, text="Save settings", height=2, command=self.on_footer_save)
        self.footer_save.grid(column=4, row=0, padx=(0, 10))
        add_tooltip(self.footer_save, SETTING_TOOLTIPS["save_settings"])

        # Start stays disabled until a deck is loaded.
        self.footer_start = tk.Button(
            self.footer, text="Start", height=2, command=self.on_footer_start,
            disabledforeground=THEME_FG_DIM,
        )
        self.footer_start.grid(column=5, row=0)
        add_tooltip(self.footer_start, SETTING_TOOLTIPS["start"])
        self._set_start_enabled(False)

        self._bind_keys()

    def _set_start_enabled(self, enabled):
        """Start is usable only with a deck loaded; grey it out otherwise."""
        self.footer_start.configure(
            state="normal" if enabled else "disabled",
            background=THEME_ACCENT if enabled else THEME_FIELD_BG,
        )

    def _global_setting(self, row, label_text, tooltip_text=None):
        """One Global Settings row"""
        label = tk.Label(self.global_frame, text=label_text, font=THEME_FONT)
        label.grid(row=row, column=0, sticky="w", padx=(2, 4))
        entry = tk.Entry(self.global_frame, width=5)
        entry.grid(row=row, column=1, sticky="w")
        add_tooltip(label, tooltip_text)
        add_tooltip(entry, tooltip_text)
        return label, entry, row + 1

    def _fit_window(self):
        """Size the window to the screen, centre it, and set a sane minimum."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        width = min(WINDOW_SIZE[0], max(WINDOW_MIN[0], screen_w - WINDOW_MARGIN[0]))
        height = min(WINDOW_SIZE[1], max(WINDOW_MIN[1], screen_h - WINDOW_MARGIN[1]))

        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.root.minsize(
            min(WINDOW_MIN[0], width),
            min(WINDOW_MIN[1], height),
        )

    def _bind_keys(self):
        """Ctrl+1..4 switch tabs; Enter or a click outside the field loads a typed path."""
        for index in range(len(self.exercise_notebook.tabs())):
            self.root.bind(
                f"<Control-Key-{index + 1}>",
                lambda _event, tab=index: self.exercise_notebook.select(tab),
            )
        # Clicking anywhere else commits whatever is typed in the deck field.
        self.root.bind_all("<Button-1>", self._on_click_outside_deck_entry, add="+")

    # Exercise tabs
    def _add_tab(self, name, title):
        """Create an empty tab and expose it as `self.exercise_<name>`."""
        tab = ttk.Frame(self.exercise_notebook)
        self.exercise_notebook.add(tab, text=title)
        setattr(self, f"exercise_{name}", tab)
        return tab

    def _build_exercise_tab(self, name, title, sections):
        """Build a tab from a section list; `name` prefixes all widget names."""
        tab = self._add_tab(name, title)

        bar = tk.Frame(tab)
        bar.pack(fill="x", side="top")
        bar.columnconfigure(1, weight=1)
        setattr(self, f"{name}_frame", bar)

        enabled_var = tk.IntVar()
        enabled = tk.Checkbutton(bar, text="Enabled", variable=enabled_var)
        enabled.grid(column=0, row=0, padx=10, pady=8, sticky="w")
        add_tooltip(enabled, SETTING_TOOLTIPS["enabled"])
        setattr(self, f"{name}_enabled_var", enabled_var)
        setattr(self, f"{name}_enabled", enabled)

        advanced_var = tk.IntVar()
        advanced = tk.Checkbutton(
            bar, text="Advanced", variable=advanced_var,
            command=lambda: self._show_advanced(name),
        )
        advanced.grid(column=1, row=0, padx=10, pady=8, sticky="e")
        add_tooltip(advanced, SETTING_TOOLTIPS["advanced"])
        setattr(self, f"{name}_advanced_var", advanced_var)
        setattr(self, f"{name}_advanced", advanced)

        scrollframe = ScrollableFrame(tab)
        scrollframe.pack(fill="both", expand=True)
        setattr(self, f"{name}_scrollframe", scrollframe)

        sections = [Section(section) for section in sections]
        for section in sections:
            section.build(scrollframe.body)
            for block in section.blocks:
                for suffix, widget in block.widgets.items():
                    setattr(self, f"{name}_{suffix}", widget)

        # Line up every field with the widest label in the tab.
        label_width = max(
            (block.label.winfo_reqwidth()
             for section in sections for block in section.blocks
             if block.label is not None),
            default=0,
        )
        if label_width:
            for section in sections:
                for block in section.blocks:
                    if block.label is not None:
                        block.frame.grid_columnconfigure(0, minsize=label_width + 10)

        state = ExerciseTab(name, enabled_var, advanced_var, sections, scrollframe)
        self._tabs[name] = state
        state.show_advanced()

    def _show_advanced(self, name):
        """Re-pack a tab in order, hiding advanced sections and blocks."""
        self._tabs[name].show_advanced()

    def on_footer_reset(self):
        """Put every setting back to its default and unload the deck, after confirming."""
        confirmed = messagebox.askyesno(
            "Reset settings",
            "Reset all settings to their defaults and unload the current deck?\n\n"
            "This cannot be undone.",
            parent=self.root,
            icon="warning",
            default="no",
        )
        if not confirmed:
            return
        for name in self._tabs:
            self._reset_tab(name)
        self._reset_globals()
        self._clear_deck()

    def _reset_globals(self):
        """Put the global settings back to their defaults."""
        for attribute, value in GLOBAL_DEFAULTS.items():
            self._set_entry(getattr(self, attribute), value)

    def _reset_tab(self, name):
        """Reset one tab: its toggles and every block, from the schema."""
        self._tabs[name].reset()

    @staticmethod
    def _set_entry(entry, value):
        entry.delete(0, "end")
        if value:
            entry.insert(0, value)

    def on_header_settings(self):
        pass

    def on_header_about(self):
        show_about(self.root)

    def on_desk_browse(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Choose a deck file",
            filetypes=[("Deck JSON", "*.json"), ("All files", "*")],
        )
        if not path:
            return
        self._load_deck(path)

    def on_desk_entry_submit(self, _event=None):
        """Enter in the deck field loads the typed path."""
        self._load_typed_deck()
        return "break"

    def _on_click_outside_deck_entry(self, event):
        """Clicking anywhere but the field (and Browse) commits the typed path."""
        widget = event.widget
        # Native dialogs (and some Tk bindings) deliver a widget path string
        # instead of a widget object; those clicks are not ours to handle.
        if not isinstance(widget, tk.Misc):
            return
        if widget.winfo_toplevel() is not self.root:
            return
        if str(widget).startswith(str(self.desk_entry)) or widget is self.desk_browse:
            return
        self._load_typed_deck()

    def _load_typed_deck(self):
        """Load the deck field's path when it is non-empty and differs from the loaded one."""
        text = self.desk_entry.get().strip()
        if not text or text == self._loaded_deck_text():
            return
        self._load_deck(text)

    def _loaded_deck_text(self):
        """The deck field's canonical value for the deck that is actually loaded."""
        return "" if self.config is None else str(self.config.path)

    def _load_deck(self, path):
        """Validate a deck file and show what was loaded; report problems."""
        try:
            config = load_config(path)
        except ConfigError as error:
            # Keep the deck that is already loaded: a typo must not throw it away.
            self._set_entry(self.desk_entry, self._loaded_deck_text())
            messagebox.showerror("Cannot load deck", str(error), parent=self.root)
            return False

        self.config = config
        self._set_entry(self.desk_entry, str(config.path))
        self._fill_categories(config)
        self.desk_status.configure(text=self._describe(config))
        self._set_start_enabled(True)

        if config.warnings:
            self._show_warnings(config.warnings)
        return True

    def _clear_deck(self):
        """Forget the current deck and go back to the empty state."""
        self.config = None
        self._set_entry(self.desk_entry, "")
        self._fill_categories(None)
        self.desk_status.configure(text="No deck selected")
        self._set_start_enabled(False)

    def _fill_categories(self, config):
        """One checkbox per category: checked means it is used in the session."""
        for child in self.categories_list.winfo_children():
            child.destroy()
        self.category_vars = {}
        self.category_checks = {}
        if config is None:
            self.categories_empty.pack(anchor="w", padx=6, pady=(4, 0))
            return

        self.categories_empty.pack_forget()
        for name, category in config.categories.items():
            if category.enabled:
                count = sum(1 for card in config.cards.values() if card.category == name)
            else:
                count = config.disabled.get(name, 0)
            var = tk.IntVar(value=1 if category.enabled else 0)
            check = tk.Checkbutton(
                self.categories_list,
                text=f"{name} ({count})",
                variable=var,
                font=THEME_FONT,
                fg=self._category_colour(var),
                anchor="w", justify="left", wraplength=170,
            )
            check.configure(command=lambda box=check, box_var=var: box.configure(
                fg=self._category_colour(box_var)))
            add_tooltip(check, SETTING_TOOLTIPS["loaded_categories"])
            check.pack(fill="x", padx=6)
            self.category_vars[name] = var
            self.category_checks[name] = check

    def _set_category(self, name, enabled):
        """Set one category checkbox from loaded settings."""
        var = self.category_vars.get(name)
        check = self.category_checks.get(name)
        if var is None or check is None:
            return
        var.set(1 if enabled else 0)
        check.configure(fg=self._category_colour(var))

    @staticmethod
    def _category_colour(var):
        """Checked categories read normally; unchecked ones are dimmed."""
        return THEME_FG if var.get() else THEME_FG_DIM

    @staticmethod
    def _describe(config):
        """One-line summary of a loaded deck for the status label."""
        cards = len(config)
        categories = len(config.categories)
        summary = (
            f"{cards} card{'s' if cards != 1 else ''} · "
            f"{categories} categor{'ies' if categories != 1 else 'y'}"
        )
        if config.warnings:
            warnings = len(config.warnings)
            summary += f" · {warnings} warning{'s' if warnings != 1 else ''}"
        return summary

    def _show_warnings(self, warnings):
        """Show validation warnings, truncated if the file has many."""
        self._show_messages("Deck loaded with warnings", warnings)

    def _show_messages(self, title, messages):
        """Show a list of messages, truncated if there are many."""
        limit = 12
        text = "\n".join(str(message) for message in messages[:limit])
        if len(messages) > limit:
            text += f"\n…and {len(messages) - limit} more."
        messagebox.showwarning(title, text, parent=self.root)

    def on_desk_edit(self):
        # TODO
        pass

    def on_footer_quit(self):
        try:
            self.root.destroy()
        except Exception as e:
            print(f"Couldn't destroy window: {e}")


    def on_footer_load(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Load settings",
            filetypes=[("JSON", "*.json"), ("All files", "*")],
        )
        if not path:
            return
        try:
            data = _read_settings(path)
            deck_ok = self._apply_settings(path, data)
        except ConfigError as error:
            messagebox.showerror("Cannot load settings", str(error), parent=self.root)
            return
        self.settings_path = path
        if deck_ok:
            messagebox.showinfo("Settings loaded", f"Loaded from {path}", parent=self.root)

    def _apply_settings(self, path, data):
        """Validate a settings file first, then apply it; False if the deck failed."""
        plan = self._plan_settings(path, data)

        for name, value in plan["global"].items():
            self._set_entry(getattr(self, GLOBAL_FIELDS[name]), value)

        for name, tab in plan["tabs"].items():
            state = self._tabs[name]
            if "enabled" in tab:
                state.enabled_var.set(1 if tab["enabled"] else 0)
            if "advanced" in tab:
                state.advanced_var.set(1 if tab["advanced"] else 0)
            for block, value in tab.get("values", []):
                block.apply(value)
            state.show_advanced()

        deck_ok = True
        if "deck" in plan:
            if plan["deck"]:
                deck_ok = self._load_deck(self._resolve_deck_path(plan["deck"], path))
            else:
                self._clear_deck()

        for name, enabled in plan["categories"].items():
            self._set_category(name, enabled)
        return deck_ok

    def _plan_settings(self, path, data):
        """Check a settings file against the schema without touching any widget."""
        def fail(message):
            raise ConfigError(f"{path}: {message}")

        plan = {"global": {}, "tabs": {}, "categories": {}}

        if "global" in data:
            raw = data["global"]
            if not isinstance(raw, dict):
                fail("global must be an object")
            for name, value in raw.items():
                if name not in GLOBAL_FIELDS:
                    continue
                if not isinstance(value, str):
                    fail(f"global.{name} must be a string")
                plan["global"][name] = value

        if "exercises" in data:
            raw = data["exercises"]
            if not isinstance(raw, dict):
                fail("exercises must be an object")
            for name, tab_raw in raw.items():
                if name not in self._tabs:
                    continue
                if not isinstance(tab_raw, dict):
                    fail(f"exercises.{name} must be an object")
                tab = {}
                for field in ("enabled", "advanced"):
                    if field in tab_raw:
                        if not isinstance(tab_raw[field], bool):
                            fail(f"exercises.{name}.{field} must be true/false")
                        tab[field] = tab_raw[field]
                if "settings" in tab_raw:
                    values_raw = tab_raw["settings"]
                    if not isinstance(values_raw, dict):
                        fail(f"exercises.{name}.settings must be an object")
                    values = []
                    for block in self._tabs[name].blocks:
                        if block.key not in values_raw:
                            continue
                        value = block.check(
                            values_raw[block.key], self._value_fail(path, name, block.key))
                        values.append((block, value))
                    tab["values"] = values
                plan["tabs"][name] = tab

        if "deck" in data:
            deck = data["deck"]
            if deck is not None and not isinstance(deck, str):
                fail("deck must be a path string or null")
            plan["deck"] = deck

        if "categories" in data:
            raw = data["categories"]
            if not isinstance(raw, dict):
                fail("categories must be an object")
            for name, enabled in raw.items():
                if not isinstance(enabled, bool):
                    fail(f"categories.{name} must be true/false")
                plan["categories"][name] = enabled

        return plan

    @staticmethod
    def _value_fail(path, tab, key):
        """A fail() for one setting, so blocks only describe the type error."""
        def fail(why):
            raise ConfigError(f"{path}: exercises.{tab}.settings.{key} {why}")
        return fail

    @staticmethod
    def _resolve_deck_path(deck, settings_path):
        """Deck paths in a settings file are relative to that file, then to cwd."""
        candidate = Path(deck)
        if candidate.is_absolute():
            return str(candidate)
        beside = Path(settings_path).parent / candidate
        if beside.exists():
            return str(beside)
        return str(candidate)

    @staticmethod
    def _deck_for_settings(deck_path, settings_path):
        """Save the deck relative to the settings file when it lives inside that folder."""
        deck = Path(deck_path).resolve()
        if settings_path is None:
            return str(deck)
        try:
            relative = os.path.relpath(deck, Path(settings_path).resolve().parent)
        except ValueError:
            return str(deck)
        if relative == os.pardir or relative.startswith(os.pardir + os.sep):
            return str(deck)
        return relative

    def on_footer_save(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save settings",
            defaultextension=".json",
            initialdir=str(Path(self.settings_path).parent) if self.settings_path else None,
            initialfile=Path(self.settings_path).name if self.settings_path else "settings.json",
            filetypes=[("JSON", "*.json"), ("All files", "*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(self._collect_settings(path), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            messagebox.showerror("Cannot save settings", str(error), parent=self.root)
            return
        self.settings_path = path
        messagebox.showinfo("Settings saved", f"Saved to {path}", parent=self.root)

    def _collect_settings(self, target_path=None):
        """Every visible setting, plus the deck and its category states."""
        config = self.config
        return {
            "deck": None if config is None else self._deck_for_settings(config.path, target_path),
            "categories": {
                name: bool(var.get()) for name, var in self.category_vars.items()
            },
            "global": {
                name: getattr(self, attribute).get()
                for name, attribute in GLOBAL_FIELDS.items()
            },
            "exercises": {name: tab.collect() for name, tab in self._tabs.items()},
        }

    def on_footer_start(self):
        """Validate settings, write category states, and run an Anki session."""
        if self.config is None:
            messagebox.showwarning(
                "No deck loaded", "Load a deck before starting a session.",
                parent=self.root,
            )
            return

        data = self._collect_settings()
        try:
            normalized = normalize_settings(data)
            session = Session(
                self.config, normalized,
                category_states=data.get("categories"), save_categories=True,
            )
        except (SettingsError, ConfigError, OSError) as error:
            messagebox.showerror("Cannot start session", str(error), parent=self.root)
            return

        runner = SessionRunner(self.root, session)
        if runner.warnings:
            self._show_messages("Session warnings", runner.warnings)
        if not runner.has_work:
            messagebox.showwarning(
                "Nothing to study",
                "No cards match the current deck, categories, and score filter.",
                parent=self.root,
            )
            runner.finish_quietly()
            return
        runner.start()


def _read_settings(path):
    """Read a settings file as JSON; raises ConfigError when it cannot be read."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"cannot read {file_path}: {error}") from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConfigError(f"{file_path}: invalid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ConfigError(f"{file_path}: top level must be an object")
    return data


def main():
    """Create the window and run the app; shared by every entry point."""
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
