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
        apply_theme, ui,
    )
    from ..config.loader import SCORE_DELTAS
    from .media import image_frame, play_audio, stop_audio
except ImportError:  # started as a script: python src/ui/anki.py
    from helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme, ui,
    )
    from config.loader import SCORE_DELTAS
    from media import image_frame, play_audio, stop_audio


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

GRADE_STYLES = {
    "impossible": ("Impossible", THEME_DANGER, THEME_DANGER_HOVER),
    "hard": ("Hard", "#5a5a5a", "#6a6a6a"),
    "medium": ("Medium", "#4a6b8a", "#5a7b9a"),
    "light": ("Light", "#4a8a6b", "#5a9a7b"),
    "easy": ("Easy", SUCCESS_BG, "#3f7b56"),
}


class CardSide:
    """One side of an Anki card."""

    def __init__(self, text, sub="", audio=None, image=None,
                 category="", direction="normal", show_sub="always"):
        """``audio``/``image`` are file paths; ``None`` means absent."""
        self.text = text
        self.sub = sub
        self.audio = audio
        self.image = image
        self.category = category
        self.direction = direction
        self.show_sub = show_sub


class AnkiCard:
    """A card with a front and a back side."""

    def __init__(self, front, back):
        self.front = front
        self.back = back


DEFAULT_CARD = AnkiCard(
    CardSide("Hello", "/həˈloʊ/", category="greetings", direction="normal"),
    CardSide("Hola", "/ˈoʊlɑː/", category="greetings", direction="normal"),
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
        padx=ui(8) if small else 16, pady=ui(2) if small else 8,
    )
    options.update(kw)
    return tk.Button(parent, **options)


class Application:
    """Show the front, reveal the back, then self-grade the card."""

    def __init__(self, root, card=None, on_grade=None, on_skip=None,
                 on_quit=None, warnings=(), score_deltas=None):
        self.root = root
        root.title("DeskCard - Anki")
        apply_theme(root)

        self.score_deltas = dict(SCORE_DELTAS)
        if score_deltas:
            for grade, delta in score_deltas.items():
                if grade in GRADE_STYLES:
                    self.score_deltas[grade] = int(delta)
        self.grade_rows = [
            (label, self.score_deltas[grade], bg, hover)
            for grade, (label, bg, hover) in GRADE_STYLES.items()
        ]

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
        self._auto_played = set()

        root.bind("<Return>", lambda _e: self._enter())
        root.bind("<KP_Enter>", lambda _e: self._enter())
        root.bind("<space>", lambda _e: self._enter())
        root.bind("<Escape>", lambda _e: self.on_quit())
        # Grade with 1–5 (main row or keypad) as a keyboard-only alternative
        # to clicking a button. The grade guard ignores keys while locked.
        for number, row in enumerate(self.grade_rows, start=1):
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
        self._sync_state()
        self._on_grade(grade)

    def _continue(self):
        """Standalone-mode advance; the session runner supplies its own callbacks."""
        self.revealed = False
        self.last_grade = None
        self.locked = False
        self._freeze_message = ""
        self._auto_played.clear()
        self._sync_state()

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
        self._sync_state()

    def auto_play(self):
        """Play the front audio once when the card first opens."""
        self._auto_play("front", self.card.front)

    def _auto_play(self, name, side):
        if name in self._auto_played or not side.audio:
            return
        self._auto_played.add(name)
        self._play(side)

    def _play(self, side, _event=None):
        """Play this side's audio with pygame."""
        if not side.audio:
            return
        try:
            play_audio(side.audio)
        except RuntimeError as error:
            self._warn(str(error))

    def _warn(self, message):
        if message not in self.warnings:
            self.warnings = self.warnings + (message,)
            self._sync_warning()

    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        if event.width == self._window_width:
            return
        self._window_width = event.width
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(120, self._sync_wrap)

    def _sync_wrap(self):
        """Re-wrap existing text after a resize; no widget teardown."""
        self._resize_job = None
        wrap = self._wraplength()
        for label in self._face_wrap_labels:
            if label.winfo_exists():
                label.configure(wraplength=wrap)
        if self._warning_label is not None and self._warning_label.winfo_exists():
            self._warning_label.configure(wraplength=max(ui(240), wrap - ui(260)))

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
            ui(WINDOW_SIZE[0]), max(ui(WINDOW_MIN[0]), screen_w - ui(WINDOW_MARGIN[0])))
        height = min(
            ui(WINDOW_SIZE[1]), max(ui(WINDOW_MIN[1]), screen_h - ui(WINDOW_MARGIN[1])))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(
            min(ui(WINDOW_MIN[0]), width),
            min(ui(WINDOW_MIN[1]), height),
        )
        self._window_width = width

    # -- build -------------------------------------------------------------
    def _build(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        if width > 1:
            self._window_width = width
        self._skip_button = None
        self._quit_button = None
        self._show_button = None
        self._reveal_area = None
        self._grade_frame = None
        self._grade_buttons = []
        self._hint_label = None
        self._warning_label = None
        self._footer = None
        self._face_wrap_labels = []
        self._front_after_sub_label = None
        for child in self.root.winfo_children():
            child.destroy()
        self._build_header()
        self._build_body()
        self._build_footer()
        self._sync_state()

    def _hint_text(self):
        if self._freeze_message:
            return self._freeze_message
        if self.locked and self.last_grade is not None:
            return f"Graded {self.last_grade}"
        if self.revealed:
            return "Grade with 1–5 or click a button"
        return "Enter or Space shows the answer"

    def _sync_state(self):
        """Apply the small set of changing properties without rebuilding."""
        state = "disabled" if self.locked else "normal"
        for button in (self._skip_button, self._quit_button,
                       *self._grade_buttons):
            if button is not None:
                button.configure(state=state)
        if self._reveal_area is not None:
            if self.revealed:
                self._reveal_area.pack(fill="x", pady=ui((6, 8)))
            else:
                self._reveal_area.pack_forget()
        if self._show_button is not None:
            if self.revealed:
                self._show_button.pack_forget()
            else:
                self._show_button.pack(side="bottom", pady=ui((12, 0)))
        if self._grade_frame is not None:
            if self.revealed:
                # The grade row takes the bottom slot; the revealed answer
                # stays in place in the body.
                self._grade_frame.pack(fill="x", side="bottom", pady=ui((8, 0)))
            else:
                self._grade_frame.pack_forget()
        if self._front_after_sub_label is not None:
            if self.revealed:
                self._front_after_sub_label.pack(anchor="center", pady=ui((4, 0)))
            else:
                self._front_after_sub_label.pack_forget()
        if self._hint_label is not None:
            self._hint_label.configure(text=self._hint_text())
        self._sync_warning()

    def _sync_warning(self):
        if self._footer is None:
            return
        wrap = max(ui(240), self._wraplength() - ui(260))
        if not self.warnings:
            if self._warning_label is not None:
                self._warning_label.pack_forget()
            return
        text = "⚠ " + " · ".join(self.warnings)
        if self._warning_label is None:
            self._warning_label = tk.Label(
                self._footer, text=text, bg=THEME_BG, fg="#d9a54f",
                font=FONT_HINT, wraplength=wrap,
            )
            self._warning_label.pack(side="right")
        else:
            self._warning_label.configure(text=text, wraplength=wrap)

    def _build_header(self):
        header = tk.Frame(self.root, bg=THEME_BG)
        self._header = header
        header.pack(fill="x", padx=ui(28), pady=ui((14, 4)))

        title = tk.Frame(header, bg=THEME_BG)
        title.pack(side="left")
        tk.Label(title, text="◆ DeskCard", bg=THEME_BG, fg=THEME_ACCENT,
                 font=THEME_FONT_BOLD).pack(side="left")
        tk.Label(title, text="  Anki", bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT).pack(side="left")

        actions = tk.Frame(header, bg=THEME_BG)
        actions.pack(side="right")
        self._skip_button = flat_button(
            actions, "Skip", command=self.on_skip, kind="ghost")
        self._skip_button.pack(side="left", padx=ui((0, 6)))
        self._quit_button = flat_button(
            actions, "Quit", command=self.on_quit, kind="danger")
        self._quit_button.pack(side="left")

    def _wraplength(self):
        return max(ui(320), min(ui(680), self._window_width - ui(120)))

    def _face_block(self, parent, side, wrap, is_front=False):
        """Render one side: text, sub, audio, and an optional image slot."""
        frame = tk.Frame(parent, bg=PANEL_BG)
        inner = tk.Frame(frame, bg=PANEL_BG)
        inner.pack(fill="x", padx=ui(24), pady=ui(16))

        meta = "   ·   ".join(
            part for part in (side.category.upper(), side.direction.upper())
            if part)
        if meta:
            tk.Label(inner, text=meta, bg=PANEL_BG, fg=THEME_FG_DIM,
                     font=FONT_META).pack(anchor="w")

        text = side.text or ""
        text_font = FONT_TITLE if len(text) <= 24 else FONT_TITLE_SMALL
        row = tk.Frame(inner, bg=PANEL_BG)
        row.pack(anchor="center", pady=ui((6, 0)))
        text_label = tk.Label(row, text=text, bg=PANEL_BG, fg=THEME_FG,
                              font=text_font, justify="center", wraplength=wrap)
        text_label.pack(side="left", anchor="n")
        self._face_wrap_labels.append(text_label)
        if side.audio:
            flat_button(row, "▶", command=lambda s=side: self._play(s),
                        small=True).pack(side="left", padx=ui((12, 0)), pady=ui((4, 0)))

        show_sub = getattr(side, "show_sub", "always")
        if side.sub and show_sub != "never":
            sub_label = tk.Label(inner, text=side.sub, bg=PANEL_BG,
                                 fg=THEME_FG_DIM, font=FONT_SUB,
                                 justify="center", wraplength=wrap)
            self._face_wrap_labels.append(sub_label)
            if show_sub == "always" or (show_sub == "after" and not is_front):
                sub_label.pack(anchor="center", pady=ui((4, 0)))
            else:
                self._front_after_sub_label = sub_label

        if side.image:
            slot = image_frame(
                inner, side.image, width=220, height=136,
                max_size=(212, 128), bg="#2a2a2a", font=FONT_META,
            )
            slot.pack(anchor="center", pady=ui((8, 0)))

        return frame

    def _build_body(self):
        body = tk.Frame(self.root, bg=THEME_BG)
        body.pack(fill="both", expand=True, padx=ui(28), pady=ui((6, 0)))

        wrap = self._wraplength()

        front = self._face_block(body, self.card.front, wrap, is_front=True)
        front.pack(fill="x", pady=ui((8, 6)))

        # Built once and shown/hidden by _sync_state; no teardown on reveal.
        self._reveal_area = tk.Frame(body, bg=THEME_BG)
        back = self._face_block(self._reveal_area, self.card.back, wrap)
        back.pack(fill="x", pady=ui((6, 8)))
        # The grade row is a sibling of the answer, not part of it, so only
        # the buttons move to the bottom when the answer is revealed.
        self._grade_frame = tk.Frame(body, bg=THEME_BG)
        for column in range(len(self.grade_rows)):
            self._grade_frame.columnconfigure(column, weight=1, uniform="grade")
        for column, (label, delta, bg, hover) in enumerate(self.grade_rows):
            sign = "+" if delta > 0 else ""
            button = flat_button(
                self._grade_frame, f"{label}\n{sign}{delta}",
                command=lambda grade=label: self._grade(grade),
                kind="ghost", small=False,
                bg=bg, activebackground=hover, fg="#ffffff",
                takefocus=1,
            )
            button.grid(row=0, column=column, sticky="nsew", padx=ui(4), pady=ui(4))
            self._grade_buttons.append(button)

        self._show_button = flat_button(
            body, "Show Answer", command=self._reveal, kind="accent")

    def _reveal(self):
        self.revealed = True
        self._sync_state()
        self._auto_play("back", self.card.back)

    def _build_footer(self):
        self._footer = tk.Frame(self.root, bg=THEME_BG)
        self._footer.pack(fill="x", side="bottom", padx=ui(28), pady=ui((4, 16)))
        self._hint_label = tk.Label(
            self._footer, text="", bg=THEME_BG, fg=THEME_FG_DIM,
            font=FONT_HINT,
        )
        self._hint_label.pack(side="left")


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
