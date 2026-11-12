"""Setting blocks: one class per control kind, plus the tab that holds them.

A block owns its widgets and knows how to build, read, write, validate and
reset itself. Adding a setting kind therefore means writing one class here
instead of editing five parallel ``if kind == ...`` chains in the main window.

Every block keeps its widgets in :attr:`Block.widgets`, keyed by the suffix
used in the settings file (``other_score``, ``prompt_type_all``, ...), so the
main window can still expose them as ``<tab>_<suffix>`` attributes.
"""

import tkinter as tk

try:
    from .theme import THEME_FONT_BOLD, THEME_FONT_SMALL
except ImportError:  # started as a script, not as a package
    from theme import THEME_FONT_BOLD, THEME_FONT_SMALL


HINT_PADX = (10, 0)
SECTION_PADY = (12, 0)
SUBHEADING_PADY = (10, 0)
ROW_PADY_TEXT = (8, 0)
ROW_PADY_FIELD = (6, 0)


class Block:
    """One labelled control: a frame, its widgets, and its value."""

    kind = ""
    pady = ROW_PADY_FIELD

    def __init__(self, spec):
        self.spec = spec
        self.key = spec.get("key")
        self.advanced = bool(spec.get("advanced"))
        self.frame = None
        self.label = None
        self.widgets = {}

    def build(self, parent):
        """Create the frame and widgets under `parent`; returns the frame."""
        self.frame = tk.Frame(parent)
        self._populate(self.frame)
        return self.frame

    def _populate(self, frame):
        raise NotImplementedError

    def default(self):
        """The value a Reset restores."""
        raise NotImplementedError

    def value(self):
        """The current value, in the shape the settings file uses."""
        raise NotImplementedError

    def apply(self, value):
        """Show `value` in the widgets."""
        raise NotImplementedError

    def check(self, value, fail):
        """Validate a settings-file value; call `fail(why)` when it is wrong."""
        raise NotImplementedError

    def reset(self):
        self.apply(self.default())


class SubheadingBlock(Block):
    """A caption inside a section; holds no value."""

    kind = "subheading"
    pady = SUBHEADING_PADY

    def _populate(self, frame):
        tk.Label(frame, text=self.spec["text"]).grid(
            row=0, column=0, columnspan=2, sticky="w")

    def default(self):
        return None

    def value(self):
        return None

    def apply(self, value):
        pass

    def check(self, value, fail):
        return value


class ChecksBlock(Block):
    """Several independent checkboxes; the value is the list of ticked keys."""

    kind = "checks"
    pady = ROW_PADY_TEXT

    def __init__(self, spec):
        super().__init__(spec)
        self.vars = {}

    def _populate(self, frame):
        tk.Label(frame, text=self.spec["label"]).grid(
            row=0, column=0, columnspan=2, sticky="w")
        options = tk.Frame(frame)
        options.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
        default = self.spec.get("default")
        for column, (option_key, text) in enumerate(self.spec["options"]):
            var = tk.IntVar(value=1 if option_key == default else 0)
            widget = tk.Checkbutton(options, text=text, variable=var)
            widget.grid(row=0, column=column, sticky="w")
            self.vars[option_key] = var
            self.widgets[f"{self.key}_{option_key}"] = widget
            self.widgets[f"{self.key}_{option_key}_var"] = var

    def default(self):
        default = self.spec.get("default")
        return [default] if default else []

    def value(self):
        return [option for option, var in self.vars.items() if var.get()]

    def apply(self, value):
        for option, var in self.vars.items():
            var.set(1 if option in value else 0)

    def check(self, value, fail):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            fail("must be a list of option names")
        return value


class RadiosBlock(Block):
    """One exclusive group of radio buttons; the value is the selected key."""

    kind = "radios"
    pady = ROW_PADY_TEXT

    def __init__(self, spec):
        super().__init__(spec)
        self.var = None

    def _populate(self, frame):
        tk.Label(frame, text=self.spec["label"]).grid(
            row=0, column=0, columnspan=2, sticky="w")
        options = tk.Frame(frame)
        options.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.var = tk.StringVar(value=self.spec.get("default", ""))
        for column, (option_key, text) in enumerate(self.spec["options"]):
            widget = tk.Radiobutton(options, text=text, variable=self.var, value=option_key)
            widget.grid(row=0, column=column, sticky="w")
            self.widgets[f"{self.key}_{option_key}"] = widget
        self.widgets[f"{self.key}_var"] = self.var

    def default(self):
        return self.spec.get("default", "")

    def value(self):
        return self.var.get()

    def apply(self, value):
        if value in dict(self.spec["options"]):
            self.var.set(value)

    def check(self, value, fail):
        if not isinstance(value, str):
            fail("must be a string")
        return value


class CheckBlock(Block):
    """A single checkbox with an optional hint."""

    kind = "check"

    def __init__(self, spec):
        super().__init__(spec)
        self.var = None

    def _populate(self, frame):
        self.var = tk.IntVar(value=1 if self.spec.get("default") else 0)
        widget = tk.Checkbutton(frame, text=self.spec["text"], variable=self.var)
        widget.grid(row=0, column=0, sticky="w")
        self.widgets[self.key] = widget
        self.widgets[f"{self.key}_var"] = self.var
        if self.spec.get("hint"):
            tk.Label(frame, text=self.spec["hint"], font=THEME_FONT_SMALL).grid(
                row=0, column=1, sticky="w", padx=HINT_PADX)

    def default(self):
        return bool(self.spec.get("default"))

    def value(self):
        return bool(self.var.get())

    def apply(self, value):
        self.var.set(1 if value else 0)

    def check(self, value, fail):
        if not isinstance(value, bool):
            fail("must be true/false")
        return value


class EntryBlock(Block):
    """A label and a text field, with an optional hint."""

    kind = "entry"

    def __init__(self, spec):
        super().__init__(spec)
        self.entry = None

    def _populate(self, frame):
        self.label = tk.Label(frame, text=self.spec["label"])
        self.label.grid(row=0, column=0, sticky="w")
        self.entry = tk.Entry(frame)
        if self.spec.get("default") is not None:
            self.entry.insert(0, self.spec["default"])
        self.entry.grid(row=0, column=1, sticky="w")
        self.widgets[self.key] = self.entry
        if self.spec.get("hint"):
            tk.Label(frame, text=self.spec["hint"], font=THEME_FONT_SMALL).grid(
                row=0, column=2, sticky="w", padx=HINT_PADX)

    def default(self):
        return self.spec.get("default") or ""

    def value(self):
        return self.entry.get()

    def apply(self, value):
        self.entry.delete(0, "end")
        if value:
            self.entry.insert(0, value)

    def check(self, value, fail):
        if not isinstance(value, str):
            fail("must be a string")
        return value


BLOCK_TYPES = {
    "checks": ChecksBlock,
    "radios": RadiosBlock,
    "check": CheckBlock,
    "entry": EntryBlock,
    "subheading": SubheadingBlock,
}


def make_block(spec):
    """Build the right Block subclass for one schema entry."""
    try:
        block_type = BLOCK_TYPES[spec["kind"]]
    except KeyError:
        raise ValueError(f"unknown block kind: {spec.get('kind')!r}") from None
    return block_type(spec)


class Section:
    """A titled group of blocks; hiding it hides its heading too."""

    def __init__(self, spec):
        self.title = spec["title"]
        self.advanced = bool(spec.get("advanced"))
        self.blocks = [make_block(block) for block in spec["blocks"]]
        self.frame = None

    def build(self, parent):
        """Create the section frame, heading and blocks under `parent`."""
        self.frame = tk.Frame(parent)
        tk.Label(self.frame, text=self.title, font=THEME_FONT_BOLD).pack(
            fill="x", pady=SECTION_PADY)
        for block in self.blocks:
            block.build(self.frame)
        return self.frame

    def pack(self, show_advanced):
        """Pack the visible parts in authored order, or hide the whole section."""
        if self.frame is None:
            return
        self.frame.pack_forget()
        if self.advanced and not show_advanced:
            return
        self.frame.pack(fill="x")
        for block in self.blocks:
            block.frame.pack_forget()
        for block in self.blocks:
            if block.advanced and not show_advanced:
                continue
            block.frame.pack(fill="x", pady=block.pady)


class ExerciseTab:
    """One exercise tab: its toggles, sections and scroll area."""

    def __init__(self, name, enabled_var, advanced_var, sections, scrollframe):
        self.name = name
        self.enabled_var = enabled_var
        self.advanced_var = advanced_var
        self.sections = sections
        self.scrollframe = scrollframe

    @property
    def blocks(self):
        """Every block that holds a value, in authored order."""
        return [block for section in self.sections for block in section.blocks if block.key]

    def show_advanced(self):
        """Hide or show advanced blocks according to the tab's toggle."""
        show = bool(self.advanced_var.get())
        for section in self.sections:
            section.pack(show)

    def reset(self):
        """Every block back to its schema default; toggles off."""
        self.enabled_var.set(0)
        self.advanced_var.set(0)
        for block in self.blocks:
            block.reset()
        self.show_advanced()

    def collect(self):
        """This tab in the shape the settings file uses."""
        return {
            "enabled": bool(self.enabled_var.get()),
            "advanced": bool(self.advanced_var.get()),
            "settings": {block.key: block.value() for block in self.blocks},
        }
