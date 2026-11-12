import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox

try:
    from .about import APP_NAME, show_about
    from .theme import (
        THEME_FG, THEME_FG_DIM, THEME_FONT, THEME_FONT_BOLD, THEME_FONT_SMALL,
        THEME_FONT_TITLE, apply_theme,
    )
    from ..config.loader import load_config
    from ..errors import ConfigError
except ImportError:  # started as a script, not as a package
    import sys

    from about import APP_NAME, show_about
    from theme import (
        THEME_FG, THEME_FG_DIM, THEME_FONT, THEME_FONT_BOLD, THEME_FONT_SMALL,
        THEME_FONT_TITLE, apply_theme,
    )

    # Make the project root importable so the shared config package is found.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.config.loader import load_config
    from src.errors import ConfigError


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
HINT_PADX = (10, 0)
SECTION_PADY = (12, 0)
SUBHEADING_PADY = (10, 0)
ROW_PADY_TEXT = (8, 0)
ROW_PADY_FIELD = (6, 0)

# Window sizing. WINDOW_SIZE is preferred, WINDOW_MIN is the smallest usable
# size; both are clamped to the screen so the window never opens off-screen.
WINDOW_SIZE = (950, 900)
WINDOW_MIN = (760, 520)
WINDOW_MARGIN = (60, 100)

# Global settings have no defaults in the deck yet, so reset clears them.
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


def prompt_section():
    """Prompt settings shared by Choose, Connect and Write."""
    return {
        "title": "Prompt settings",
        "blocks": [
            {"key": "prompt_type", "label": "Prompt content", "kind": "checks",
             "options": CONTENT_OPTIONS, "default": "text_only"},
            {"key": "prompt_sub", "label": "Show Sub", "kind": "radios",
             "advanced": True, "options": SUB_OPTIONS, "default": "always"},
            {"kind": "subheading", "text": "Difficulty", "advanced": True},
            {"key": "prompt_listens", "label": "Re-listens allowed",
             "kind": "entry", "hint": "0 = unlimited", "advanced": True, "default": "0"},
        ],
    }


ANKI_SECTIONS = [
    {
        "title": "Answer settings",
        "advanced": True,
        "blocks": [
            {"kind": "subheading", "text": "Difficulty", "advanced": True},
            {"key": "answer_time", "label": "Answer time limit (s)",
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
            {"key": "other_close_time", "label": "Delay before the window closes (s)",
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
            {"key": "answer_time", "label": "Answer time limit (s)",
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
            {"key": "other_close_time", "label": "Delay before the window closes (s)",
             "kind": "entry", "advanced": True, "default": "3s"},
            {"key": "other_repeat", "kind": "check", "text": "Repeat until correct",
             "hint": "Closes only after a no-mistake answer", "advanced": True},
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
            {"key": "answer_time", "label": "Answer time limit (s)",
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
            {"key": "other_close_time", "label": "Delay before the window closes (s)",
             "kind": "entry", "advanced": True, "default": "3s"},
            {"key": "other_repeat", "kind": "check", "text": "Repeat until correct",
             "hint": "Closes only after a no-mistake answer", "advanced": True},
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
            {"key": "answer_time", "label": "Answer time limit (s)",
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
            {"key": "other_close_time", "label": "Delay before the window closes (s)",
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
        root.title(f"{APP_NAME}.")
        self._fit_window()
        apply_theme(root)

        self._tabs = {}
        self.config = None
        self.settings_path = None
        self.category_vars = {}

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

        self.header_about = tk.Button(self.header_buttons, text="About", command=self.on_header_about)
        self.header_about.grid(column=1, row=0)


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

        self.desk_browse = tk.Button(self.desk_middle, text="Browse deck", command=self.on_desk_browse)
        self.desk_browse.grid(column=1, row=0, sticky="e")

        self.desk_actions = tk.Frame(self.desk)
        self.desk_actions.grid(column=0, row=2, sticky="ew")
        self.desk_actions.columnconfigure(1, weight=1)

        self.desk_edit = tk.Button(self.desk_actions, text="Edit deck", command=self.on_desk_edit)
        self.desk_edit.grid(column=0, row=0, sticky="w")

        self.desk_status = tk.Label(self.desk_actions, text="No deck selected")
        self.desk_status.grid(column=1, row=0, sticky="e")


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
        self.global_time_text, self.global_time_entry, self.global_time_hint, row = (
            self._global_setting(row, "Delay:"))
        self.global_session_text, self.global_session_entry, _hint, row = (
            self._global_setting(row, "Cards in session:"))
        self.global_batch_text, self.global_batch_entry, _hint, row = (
            self._global_setting(row, "Cards in batch:"))
        self.global_jitter_text, self.global_jitter_entry, self.global_jitter_hint, row = (
            self._global_setting(row, "Delay Jitter:"))
        self._reset_globals()

        # Loaded categories
        self.categories_frame = tk.Frame(self.right_column, relief="groove", bd=2)
        self.categories_frame.pack(side="bottom", fill="both", expand=True)

        self.categories_scroll = ScrollableFrame(self.categories_frame)
        self.categories_scroll.pack(fill="both", expand=True)

        self.categories_label = self.categories_scroll.label(text="Loaded categories", font=THEME_FONT_BOLD)
        self.categories_label.pack(fill="x", padx=2)

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

        self.footer_quit = tk.Button(self.footer, text="Quit", height=2, command=self.on_footer_quit)
        self.footer_quit.grid(column=0, row=0, sticky="w")

        self.footer_reset = tk.Button(self.footer, text="Reset", height=2, command=self.on_footer_reset)
        self.footer_reset.grid(column=2, row=0, padx=(0, 10))

        self.footer_load = tk.Button(self.footer, text="Load settings", height=2, command=self.on_footer_load)
        self.footer_load.grid(column=3, row=0, padx=(0, 10))

        self.footer_save = tk.Button(self.footer, text="Save settings", height=2, command=self.on_footer_save)
        self.footer_save.grid(column=4, row=0, padx=(0, 10))

        self.footer_start = tk.Button(self.footer, text="Start", height=2, command=self.on_footer_start)
        self.footer_start.grid(column=5, row=0)

        self._bind_keys()

    def _global_setting(self, row, label_text, hint_text=None):
        """One Global Settings row; the hint sits under its field so it fits."""
        label = tk.Label(self.global_frame, text=label_text, font=THEME_FONT)
        label.grid(row=row, column=0, sticky="w", padx=(2, 4))
        entry = tk.Entry(self.global_frame, width=5)
        entry.grid(row=row, column=1, sticky="w")
        hint = None
        if hint_text:
            hint = tk.Label(self.global_frame, text=hint_text, font=THEME_FONT_SMALL)
            hint.grid(row=row + 1, column=1, sticky="w")
            row += 1
        return label, entry, hint, row + 1

    def _fit_window(self):
        """Size the window to the screen, centre it, and set a sane minimum."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        width = min(WINDOW_SIZE[0], max(WINDOW_MIN[0], screen_w - WINDOW_MARGIN[0]))
        height = min(WINDOW_SIZE[1], max(WINDOW_MIN[1], screen_h - WINDOW_MARGIN[1]))

        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # The user can shrink the window, but never below the layout's needs.
        self.root.minsize(
            min(WINDOW_MIN[0], width),
            min(WINDOW_MIN[1], height),
        )

    def _bind_keys(self):
        """Enter starts the session; Ctrl+1..4 switch exercise tabs."""
        self.root.bind("<Return>", lambda _event: self.on_footer_start())
        self.root.bind("<KP_Enter>", lambda _event: self.on_footer_start())
        for index in range(len(self.exercise_notebook.tabs())):
            self.root.bind(
                f"<Control-Key-{index + 1}>",
                lambda _event, tab=index: self.exercise_notebook.select(tab),
            )

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
        setattr(self, f"{name}_enabled_var", enabled_var)
        setattr(self, f"{name}_enabled", enabled)

        advanced_var = tk.IntVar()
        advanced = tk.Checkbutton(
            bar, text="Advanced", variable=advanced_var,
            command=lambda: self._show_advanced(name),
        )
        advanced.grid(column=1, row=0, padx=10, pady=8, sticky="e")
        setattr(self, f"{name}_advanced_var", advanced_var)
        setattr(self, f"{name}_advanced", advanced)

        scrollframe = ScrollableFrame(tab)
        scrollframe.pack(fill="both", expand=True)
        setattr(self, f"{name}_scrollframe", scrollframe)

        section_states = []
        entry_blocks = []
        for section in sections:
            section_frame = tk.Frame(scrollframe.body)
            heading = tk.Label(section_frame, text=section["title"], font=THEME_FONT_BOLD)
            heading.pack(fill="x", pady=SECTION_PADY)

            blocks = []
            for spec in section["blocks"]:
                block, pad, label = self._build_block(section_frame, name, spec)
                blocks.append((block, pad, bool(spec.get("advanced")), spec))
                if label is not None:
                    entry_blocks.append((block, label))
            section_states.append((section_frame, bool(section.get("advanced")), blocks))

        # Line up every field with the widest label in the tab.
        label_width = max((label.winfo_reqwidth() for _block, label in entry_blocks), default=0)
        if label_width:
            for block, _label in entry_blocks:
                block.grid_columnconfigure(0, minsize=label_width + 10)

        self._tabs[name] = {
            "advanced_var": advanced_var,
            "enabled_var": enabled_var,
            "sections": section_states,
        }
        self._show_advanced(name)

    def _build_block(self, parent, prefix, spec):
        """Create one labelled control block; returns (frame, pady, label)."""
        kind = spec["kind"]
        block = tk.Frame(parent)
        pad = ROW_PADY_TEXT if kind in ("checks", "radios") else ROW_PADY_FIELD

        if kind == "subheading":
            tk.Label(block, text=spec["text"]).grid(row=0, column=0, columnspan=2, sticky="w")
            return block, SUBHEADING_PADY, None

        if kind in ("checks", "radios"):
            tk.Label(block, text=spec["label"]).grid(row=0, column=0, columnspan=2, sticky="w")
            options = tk.Frame(block)
            options.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
            group_var = tk.StringVar(value=spec.get("default", "")) if kind == "radios" else None
            if group_var is not None:
                setattr(self, f"{prefix}_{spec['key']}_var", group_var)
            for column, (option_key, text) in enumerate(spec["options"]):
                if group_var is None:
                    option_var = tk.IntVar(value=1 if option_key == spec.get("default") else 0)
                    widget = tk.Checkbutton(options, text=text, variable=option_var)
                    setattr(self, f"{prefix}_{spec['key']}_{option_key}_var", option_var)
                else:
                    widget = tk.Radiobutton(options, text=text, variable=group_var, value=option_key)
                widget.grid(row=0, column=column, sticky="w")
                setattr(self, f"{prefix}_{spec['key']}_{option_key}", widget)
            return block, pad, None

        if kind == "check":
            check_var = tk.IntVar(value=1 if spec.get("default") else 0)
            check = tk.Checkbutton(block, text=spec["text"], variable=check_var)
            check.grid(row=0, column=0, sticky="w")
            setattr(self, f"{prefix}_{spec['key']}", check)
            setattr(self, f"{prefix}_{spec['key']}_var", check_var)
            if spec.get("hint"):
                tk.Label(block, text=spec["hint"], font=THEME_FONT_SMALL).grid(
                    row=0, column=1, sticky="w", padx=HINT_PADX)
            return block, pad, None

        # kind == "entry"
        label = tk.Label(block, text=spec["label"])
        label.grid(row=0, column=0, sticky="w")
        entry = tk.Entry(block)
        if spec.get("width"):
            entry.configure(width=spec["width"])
        if spec.get("default") is not None:
            entry.insert(0, spec["default"])
        entry.grid(row=0, column=1, sticky="w")
        setattr(self, f"{prefix}_{spec['key']}", entry)
        if spec.get("hint"):
            tk.Label(block, text=spec["hint"], font=THEME_FONT_SMALL).grid(
                row=0, column=2, sticky="w", padx=HINT_PADX)
        return block, pad, label

    def _show_advanced(self, name):
        """Re-pack a tab in order, hiding advanced sections and blocks."""
        state = self._tabs[name]
        show = bool(state["advanced_var"].get())
        for section_frame, _advanced, _blocks in state["sections"]:
            section_frame.pack_forget()
        for section_frame, section_advanced, blocks in state["sections"]:
            if section_advanced and not show:
                continue
            section_frame.pack(fill="x")
            for block, _pad, _advanced, _spec in blocks:
                block.pack_forget()
            for block, pad, advanced, _spec in blocks:
                if advanced and not show:
                    continue
                block.pack(fill="x", pady=pad)

    # Reset
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
        state = self._tabs[name]
        state["enabled_var"].set(0)
        state["advanced_var"].set(0)
        for _section_frame, _advanced, blocks in state["sections"]:
            for _block, _pad, _advanced, spec in blocks:
                self._reset_block(name, spec)
        self._show_advanced(name)

    def _reset_block(self, prefix, spec):
        """Reset one block using the `default` from its schema entry."""
        kind = spec["kind"]
        default = spec.get("default", "")
        if kind == "checks":
            for option_key, _text in spec["options"]:
                var = getattr(self, f"{prefix}_{spec['key']}_{option_key}_var")
                var.set(1 if option_key == default else 0)
        elif kind == "radios":
            getattr(self, f"{prefix}_{spec['key']}_var").set(default)
        elif kind == "check":
            getattr(self, f"{prefix}_{spec['key']}_var").set(1 if default else 0)
        elif kind == "entry":
            self._set_entry(getattr(self, f"{prefix}_{spec['key']}"), default)

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

    def _load_deck(self, path):
        """Validate a deck file and show what was loaded; report problems."""
        try:
            config = load_config(path)
        except ConfigError as error:
            self._clear_deck()
            self.desk_status.configure(text="Failed to load deck")
            messagebox.showerror("Cannot load deck", str(error), parent=self.root)
            return

        self.config = config
        self._set_entry(self.desk_entry, str(config.path))
        self._fill_categories(config)
        self.desk_status.configure(text=self._describe(config))

        if config.warnings:
            self._show_warnings(config.warnings)

    def _clear_deck(self):
        """Forget the current deck and go back to the empty state."""
        self.config = None
        self._set_entry(self.desk_entry, "")
        self._fill_categories(None)
        self.desk_status.configure(text="No deck selected")

    def _fill_categories(self, config):
        """One checkbox per category: checked means it is used in the session."""
        for child in self.categories_list.winfo_children():
            child.destroy()
        self.category_vars = {}
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
            check.pack(fill="x", padx=6)
            self.category_vars[name] = var

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
        limit = 12
        prefix = f"{self.config.path}: " if self.config else ""
        text = "\n".join(warning.removeprefix(prefix) for warning in warnings[:limit])
        if len(warnings) > limit:
            text += f"\n…and {len(warnings) - limit} more."
        messagebox.showwarning("Deck loaded with warnings", text, parent=self.root)

    def on_desk_edit(self):
        print("TODO")
        pass

    def on_footer_quit(self):
        self.root.destroy()

    def on_footer_load(self):
        path = filedialog.askopenfilename(
            title="Select Saved Settings",
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return

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
                json.dumps(self._collect_settings(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            messagebox.showerror("Cannot save settings", str(error), parent=self.root)
            return
        self.settings_path = path
        messagebox.showinfo("Settings saved", f"Saved to {path}", parent=self.root)

    def _collect_settings(self):
        """Every visible setting, plus the deck and its category states."""
        config = self.config
        return {
            "$version": 1,
            "deck": None if config is None else str(config.path),
            "categories": {
                name: bool(var.get()) for name, var in self.category_vars.items()
            },
            "global": {
                name: getattr(self, attribute).get()
                for name, attribute in GLOBAL_FIELDS.items()
            },
            "exercises": {name: self._collect_tab(name) for name in self._tabs},
        }

    def _collect_tab(self, name):
        """One tab's toggles and block values, keyed by schema key."""
        state = self._tabs[name]
        values = {}
        for _section, _advanced, blocks in state["sections"]:
            for _block, _pad, _advanced, spec in blocks:
                key = spec.get("key")
                if not key:
                    continue
                kind = spec["kind"]
                if kind == "checks":
                    values[key] = [
                        option
                        for option, _text in spec["options"]
                        if getattr(self, f"{name}_{key}_{option}_var").get()
                    ]
                elif kind == "radios":
                    values[key] = getattr(self, f"{name}_{key}_var").get()
                elif kind == "check":
                    values[key] = bool(getattr(self, f"{name}_{key}_var").get())
                elif kind == "entry":
                    values[key] = getattr(self, f"{name}_{key}").get()
        return {
            "enabled": bool(state["enabled_var"].get()),
            "advanced": bool(state["advanced_var"].get()),
            "settings": values,
        }

    def on_footer_start(self):
        pass


def main():
    """Create the window and run the app; shared by every entry point."""
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
