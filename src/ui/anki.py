"""Anki-style card exercise: show front, reveal back, then self-grade.

Run it:

    python src/ui/anki.py
"""

import tkinter as tk

try:  # imported as ui.anki
    from .helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme,
    )
except ImportError:  # started as a script: python src/ui/anki.py
    from helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme,
    )


WINDOW_SIZE = (760, 800)
WINDOW_MIN = (620, 640)
WINDOW_MARGIN = (120, 140)

SUCCESS_BG = "#2f6b46"
PANEL_BG = "#333333"
CARD_BORDER = "#4a4a4a"

FONT = (THEME_FONT_FAMILY, 10)
FONT_TITLE = (THEME_FONT_FAMILY, 24, "bold")
FONT_TITLE_SMALL = (THEME_FONT_FAMILY, 18, "bold")
FONT_SUB = (THEME_FONT_FAMILY, 10)
FONT_HINT = (THEME_FONT_FAMILY, 9)
FONT_META = (THEME_FONT_FAMILY, 8)

GRADES = [
    ("Impossible", -5, THEME_DANGER, THEME_DANGER_HOVER),
    ("Hard", 0, "#5a5a5a", "#6a6a6a"),
    ("Medium", 2, "#4a6b8a", "#5a7b9a"),
    ("Light", 5, "#4a8a6b", "#5a9a7b"),
    ("Easy", 10, SUCCESS_BG, "#3f7b56"),
]


class CardSide:
    """One side of an Anki card."""

    def __init__(self, text, sub="", audio=False, image=False,
                 category="", direction="normal"):
        self.text = text
        self.sub = sub
        self.audio = audio
        self.image = image
        self.category = category
        self.direction = direction


class AnkiCard:
    """A card with a front and a back side."""

    def __init__(self, front, back):
        self.front = front
        self.back = back


DEFAULT_CARD = AnkiCard(
    CardSide("Hello", "/həˈloʊ/", audio=True, image=False,
             category="greetings", direction="normal"),
    CardSide("Hola", "/ˈoʊlɑː/", audio=True, image=True,
             category="greetings", direction="normal"),
)


def flat_button(parent, text, command=None, kind="dark", small=False, **kw):
    """A tk.Button stripped down to blend into the dark UI."""
    if kind == "accent":
        bg, hover, fg = THEME_ACCENT, THEME_ACCENT_HOVER, THEME_ACCENT_FG
    elif kind == "danger":
        bg, hover, fg = THEME_DANGER, THEME_DANGER_HOVER, "#ffffff"
    elif kind == "ghost":
        bg, hover, fg = THEME_BG, CARD_BORDER, THEME_FG_DIM
    else:
        bg, hover, fg = "#454545", "#525252", THEME_FG
    options = dict(
        text=text, command=command, relief="flat", borderwidth=0,
        highlightthickness=0, bg=bg, fg=fg, activebackground=hover,
        activeforeground=fg, cursor="hand2", takefocus=0,
        font=THEME_FONT_SMALL if small else FONT,
        padx=8 if small else 16, pady=2 if small else 8,
    )
    options.update(kw)
    return tk.Button(parent, **options)


class Application:
    """Show the front, reveal the back, then self-grade the card."""

    def __init__(self, root, card=None, on_grade=None, on_skip=None,
                 on_quit=None, warnings=()):
        self.root = root
        root.title("DeskCard - Anki")
        apply_theme(root)

        self.card = card or DEFAULT_CARD
        self.warnings = tuple(warnings)
        self.revealed = False
        self.last_grade = None
        self.locked = False
        self._freeze_message = ""
        self._on_grade = on_grade or (lambda _grade: self._continue())
        self._on_skip = on_skip or self._continue
        self._on_quit = on_quit or (lambda: self.root.destroy())
        self._window_width = 0
        self._resize_job = None

        root.bind("<Return>", lambda _e: self._enter())
        root.bind("<KP_Enter>", lambda _e: self._enter())
        root.bind("<space>", lambda _e: self._enter())
        root.bind("<Escape>", lambda _e: self.on_quit())
        # Grade with 1–5 (main row or keypad) as a keyboard-only alternative
        # to clicking a button. The grade guard ignores keys while locked.
        for number, row in enumerate(GRADES, start=1):
            grade = row[0]
            root.bind(f"<Key-{number}>", lambda _e, g=grade: self._grade(g))
            root.bind(f"<KP_{number}>", lambda _e, g=grade: self._grade(g))
        root.bind("<Configure>", self._on_configure)
        root.bind("<Destroy>", self._on_destroy)

        self._fit_window()
        self._build()

    # -- state -------------------------------------------------------------
    def _enter(self):
        if self.locked:
            return
        if not self.revealed:
            self._reveal()

    def _grade(self, grade):
        if self.locked:
            return
        self.last_grade = grade
        self.locked = True
        # Reflect the lock and grade immediately; the callback may then close
        # the window or freeze it, but the UI is never left looking clickable.
        self._build()
        self._on_grade(grade)

    def _continue(self):
        """Standalone-mode advance; the session runner supplies its own callbacks."""
        self.revealed = False
        self.last_grade = None
        self.locked = False
        self._freeze_message = ""
        self._build()

    def on_skip(self):
        if self.locked:
            return
        self.locked = True
        self._on_skip()

    def on_quit(self, event=None):
        # A grade starts a short transition; keep every action inert until the
        # runner closes the window, so Escape cannot end the whole session.
        if self.locked:
            return
        self._on_quit()

    def freeze(self, message):
        """Lock the card and show a short status while the session waits."""
        self.locked = True
        self._freeze_message = message
        self._build()

    def _play(self, side, _event=None):
        """Audio placeholder: a real screen plays the side's audio."""
        return None

    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        if abs(event.width - self._window_width) < 8:
            return
        self._window_width = event.width
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(120, self._rebuild)

    def _rebuild(self):
        self._resize_job = None
        self._build()

    def _on_destroy(self, event):
        if event.widget is self.root and self._resize_job is not None:
            try:
                self.root.after_cancel(self._resize_job)
            except tk.TclError:
                pass
            self._resize_job = None

    # -- window ------------------------------------------------------------
    def _fit_window(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(
            WINDOW_SIZE[0], max(WINDOW_MIN[0], screen_w - WINDOW_MARGIN[0]))
        height = min(
            WINDOW_SIZE[1], max(WINDOW_MIN[1], screen_h - WINDOW_MARGIN[1]))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(
            min(WINDOW_MIN[0], width),
            min(WINDOW_MIN[1], height),
        )
        self._window_width = width

    # -- build -------------------------------------------------------------
    def _build(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        if width > 1:
            self._window_width = width
        for child in self.root.winfo_children():
            child.destroy()
        self._build_header()
        self._build_body()
        self._build_footer()

    def _build_header(self):
        header = tk.Frame(self.root, bg=THEME_BG)
        header.pack(fill="x", padx=28, pady=(14, 4))

        title = tk.Frame(header, bg=THEME_BG)
        title.pack(side="left")
        tk.Label(title, text="◆ DeskCard", bg=THEME_BG, fg=THEME_ACCENT,
                 font=THEME_FONT_BOLD).pack(side="left")
        tk.Label(title, text="  Anki", bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT).pack(side="left")

        actions = tk.Frame(header, bg=THEME_BG)
        actions.pack(side="right")
        state = "disabled" if self.locked else "normal"
        flat_button(actions, "Skip", command=self.on_skip, kind="ghost",
                    state=state).pack(side="left", padx=(0, 6))
        flat_button(actions, "Quit", command=self.on_quit, kind="danger",
                    state=state).pack(side="left")

    def _wraplength(self):
        return max(320, min(680, self._window_width - 120))

    def _face_block(self, parent, side, wrap):
        """Render one side: text, sub, audio, and an optional image slot."""
        frame = tk.Frame(parent, bg=PANEL_BG)
        inner = tk.Frame(frame, bg=PANEL_BG)
        inner.pack(fill="x", padx=24, pady=16)

        meta = "   ·   ".join(
            part for part in (side.category.upper(), side.direction.upper())
            if part)
        if meta:
            tk.Label(inner, text=meta, bg=PANEL_BG, fg=THEME_FG_DIM,
                     font=FONT_META).pack(anchor="w")

        text = side.text or ""
        text_font = FONT_TITLE if len(text) <= 24 else FONT_TITLE_SMALL
        row = tk.Frame(inner, bg=PANEL_BG)
        row.pack(anchor="center", pady=(6, 0))
        tk.Label(row, text=text, bg=PANEL_BG, fg=THEME_FG,
                 font=text_font, justify="center", wraplength=wrap
                 ).pack(side="left", anchor="n")
        if side.audio:
            flat_button(row, "▶", command=lambda s=side: self._play(s),
                        small=True).pack(side="left", padx=(12, 0), pady=(4, 0))

        if side.sub:
            tk.Label(inner, text=side.sub, bg=PANEL_BG, fg=THEME_FG_DIM,
                     font=FONT_SUB, justify="center", wraplength=wrap
                     ).pack(anchor="center", pady=(4, 0))

        if side.image:
            slot = tk.Frame(inner, bg="#2a2a2a", width=220, height=136,
                            highlightthickness=1, highlightbackground="#4f4f4f")
            slot.pack_propagate(False)
            tk.Label(slot, text="image", bg="#2a2a2a", fg="#666666",
                     font=FONT_META).place(relx=0.5, rely=0.5, anchor="center")
            slot.pack(anchor="center", pady=(8, 0))

        return frame

    def _build_body(self):
        body = tk.Frame(self.root, bg=THEME_BG)
        body.pack(fill="both", expand=True, padx=28, pady=(6, 0))

        wrap = self._wraplength()

        front = self._face_block(body, self.card.front, wrap)
        front.pack(fill="x", pady=(8, 6))

        if self.revealed:
            back = self._face_block(body, self.card.back, wrap)
            back.pack(fill="x", pady=(6, 8))

            grade_frame = tk.Frame(body, bg=THEME_BG)
            grade_frame.pack(fill="x", side="bottom", pady=(8, 0))
            for column in range(len(GRADES)):
                grade_frame.columnconfigure(column, weight=1, uniform="grade")
            for column, (label, delta, bg, hover) in enumerate(GRADES):
                sign = "+" if delta > 0 else ""
                flat_button(
                    grade_frame, f"{label}\n{sign}{delta}",
                    command=lambda grade=label: self._grade(grade),
                    kind="ghost", small=False,
                    bg=bg, activebackground=hover, fg="#ffffff",
                    takefocus=1,
                    state="disabled" if self.locked else "normal",
                ).grid(row=0, column=column, sticky="nsew", padx=4, pady=4)
        else:
            show = flat_button(body, "Show Answer", command=self._reveal,
                               kind="accent")
            show.pack(pady=(12, 0))

    def _reveal(self):
        self.revealed = True
        self._build()

    def _build_footer(self):
        footer = tk.Frame(self.root, bg=THEME_BG)
        footer.pack(fill="x", side="bottom", padx=28, pady=(4, 16))

        if self._freeze_message:
            hint = self._freeze_message
        elif self.locked and self.last_grade is not None:
            hint = f"Graded {self.last_grade}"
        elif self.revealed:
            hint = "Grade with 1–5 or click a button"
        else:
            hint = "Enter or Space shows the answer"
        tk.Label(footer, text=hint, bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT_HINT).pack(side="left")
        if self.warnings:
            warning = "⚠ " + " · ".join(self.warnings)
            tk.Label(footer, text=warning, bg=THEME_BG, fg="#d9a54f",
                     font=FONT_HINT, wraplength=max(240, self._wraplength() - 260)
                     ).pack(side="right")


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
