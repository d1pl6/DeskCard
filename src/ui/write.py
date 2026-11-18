"""Write exercise: type the exact answer, then reveal the result.

Run it:

    python src/ui/write.py

The initial release uses exact matching, including capitalization. Audio and
image placeholders are kept consistent with the other exercise screens; media
playback is still a separate task.
"""

import tkinter as tk

try:  # imported as ui.write
    from .helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme,
    )
except ImportError:  # started as a script: python src/ui/write.py
    from helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme,
    )


WINDOW_SIZE = (920, 620)
WINDOW_MIN = (760, 520)
WINDOW_MARGIN = (120, 140)

SUCCESS_BG = "#2f6b46"
SUCCESS_BORDER = "#64c98a"
SUCCESS_FG = "#eaf7ee"
WRONG_BG = "#6e302d"
WRONG_FG = "#fbeceb"
PANEL_BG = "#333333"
COVER_BG = "#242424"

FONT = (THEME_FONT_FAMILY, 10)
FONT_PROMPT = (THEME_FONT_FAMILY, 28, "bold")
FONT_PROMPT_MEDIUM = (THEME_FONT_FAMILY, 22, "bold")
FONT_PROMPT_SMALL = (THEME_FONT_FAMILY, 18, "bold")
FONT_ANSWER = (THEME_FONT_FAMILY, 26, "bold")
FONT_ENTRY = (THEME_FONT_FAMILY, 16)
FONT_CHIP = (THEME_FONT_FAMILY, 9, "bold")
FONT_HINT = (THEME_FONT_FAMILY, 9)
FONT_META = (THEME_FONT_FAMILY, 8)


class WriteCard:
    """One card's worth of data for the Write screen."""

    def __init__(self, prompt, prompt_sub="", answer="", answer_sub="",
                 category="greetings", direction="normal", card_id=""):
        self.prompt = prompt
        self.prompt_sub = prompt_sub
        self.answer = answer
        self.answer_sub = answer_sub
        self.category = category
        self.direction = direction
        self.card_id = card_id


DEFAULT_CARD = WriteCard(
    "Goodbye", "/ɡʊdˈbaɪ/", "Adiós", "/aˈðjos/",
)


def flat_button(parent, text, command=None, kind="dark", small=False, **kw):
    if kind == "accent":
        bg, hover, fg = THEME_ACCENT, THEME_ACCENT_HOVER, THEME_ACCENT_FG
    elif kind == "danger":
        bg, hover, fg = THEME_DANGER, THEME_DANGER_HOVER, "#ffffff"
    elif kind == "ghost":
        bg, hover, fg = THEME_BG, "#4a4a4a", THEME_FG_DIM
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
    """Prompt, a text entry, and the exact-match result sheet."""

    def __init__(self, root, card=None, on_result=None, on_skip=None,
                 on_quit=None, warnings=()):
        self.root = root
        root.title("DeskCard - Write")
        apply_theme(root)

        self.card = card or DEFAULT_CARD
        self.warnings = tuple(warnings)
        self.typed = ""
        self.revealed = False
        self.reveal_correct = None
        self.locked = False
        self.attempt = 1
        self._freeze_message = ""
        self._retry_feedback = False
        self._on_result = on_result or (lambda _correct: self._continue())
        self._on_skip = on_skip or (lambda: self._continue())
        self._on_quit = on_quit or (lambda: self.root.destroy())
        self._window_width = 0
        self._resize_job = None
        self._entry = None

        root.bind("<Return>", lambda _e: self._enter())
        root.bind("<KP_Enter>", lambda _e: self._enter())
        root.bind("<Escape>", lambda _e: self.on_quit())
        root.bind("<Configure>", self._on_configure)
        root.bind("<Destroy>", self._on_destroy)

        self._fit_window()
        self._build()

    # -- state -------------------------------------------------------------
    def _current_text(self):
        """Read the Entry directly: paste and drag-drop emit no KeyRelease."""
        if self._entry is not None:
            try:
                return self._entry.get()
            except tk.TclError:
                pass
        return self.typed

    def _reset(self):
        self.typed = ""
        self.revealed = False
        self.reveal_correct = None
        self.locked = False
        self._freeze_message = ""
        self._retry_feedback = False

    def _enter(self):
        if self.locked:
            return
        if self._current_text():
            self._confirm()

    def _confirm(self):
        typed = self._current_text()
        if self.locked or not typed:
            return
        self.typed = typed
        self.reveal_correct = typed == self.card.answer
        self.revealed = True
        self.locked = True
        self._build()
        self._on_result(self.reveal_correct)

    def _continue(self):
        """Standalone-mode advance; the session runner supplies its own flow."""
        self._reset()
        self._build()

    def retry(self, attempt=None):
        """Show the same card again for another attempt."""
        if attempt is not None:
            self.attempt = attempt
        self._reset()
        self._build()

    def show_retry(self):
        """Show a brief wrong-answer sheet without giving away the answer."""
        if self.revealed:
            return
        self.revealed = True
        self.reveal_correct = False
        self._retry_feedback = True
        self.locked = True
        self._build()

    def reveal_timeout(self):
        """Show the missed answer when the answer timer expires."""
        if self.revealed:
            return
        self.revealed = True
        self.reveal_correct = False
        self.locked = True
        self._build()

    def on_skip(self):
        if self.locked:
            return
        self.locked = True
        self._on_skip()

    def on_quit(self, event=None):
        if self.locked:
            return
        self.locked = True
        self._on_quit()

    def focus_input(self):
        """Put the caret in the answer entry when the pop-up becomes active."""
        entry = self._entry
        if entry is None:
            return
        try:
            if entry.winfo_exists():
                entry.focus_set()
        except tk.TclError:
            pass

    def freeze(self, message):
        """Lock the card and show a short status while the session waits."""
        self.locked = True
        self._freeze_message = message
        self._build()

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
        self.root.minsize(min(WINDOW_MIN[0], width), min(WINDOW_MIN[1], height))
        self._window_width = width

    def _build(self):
        self._entry = None
        self.root.update_idletasks()
        width = self.root.winfo_width()
        if width > 1:
            self._window_width = width
        for child in self.root.winfo_children():
            child.destroy()
        self._build_header()
        self._build_footer()
        self._build_body()

    def _build_header(self):
        header = tk.Frame(self.root, bg=THEME_BG)
        header.pack(fill="x", padx=28, pady=(14, 4))
        title = tk.Frame(header, bg=THEME_BG)
        title.pack(side="left")
        tk.Label(title, text="◆ DeskCard", bg=THEME_BG, fg=THEME_ACCENT,
                 font=THEME_FONT_BOLD).pack(side="left")
        tk.Label(title, text="  Write", bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT).pack(side="left")
        actions = tk.Frame(header, bg=THEME_BG)
        actions.pack(side="right")
        state = "disabled" if self.locked else "normal"
        flat_button(actions, "Skip", command=self.on_skip, kind="ghost",
                    state=state).pack(side="left", padx=(0, 6))
        flat_button(actions, "Quit", command=self.on_quit, kind="danger",
                    state=state).pack(side="left")

    def _build_footer(self):
        footer = tk.Frame(self.root, bg=THEME_BG)
        footer.pack(fill="x", side="bottom", padx=28, pady=(4, 16))
        if self._freeze_message:
            hint = self._freeze_message
        elif self._retry_feedback:
            hint = "Not quite — try again"
        else:
            hint = "Type the exact answer, then press Enter to confirm"
        tk.Label(footer, text=hint, bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT_HINT).pack(side="left")
        if self.warnings:
            tk.Label(
                footer, text="⚠ " + " · ".join(self.warnings),
                bg=THEME_BG, fg="#d9c04f", font=FONT_META,
                justify="left", wraplength=self._window_width - 160,
            ).pack(side="bottom", anchor="w", pady=(2, 0))

        action = flat_button(footer, "Confirm", command=self._confirm,
                             kind="accent")
        if self.locked or not self._current_text():
            action.configure(state="disabled", bg="#3a3a3a", fg="#777777")
        action.pack(side="right")

    # -- body --------------------------------------------------------------
    def _build_body(self):
        body = tk.Frame(self.root, bg=THEME_BG)
        body.pack(fill="both", expand=True, padx=28, pady=(6, 0))
        self._prompt_card(body).pack(fill="x")

        stage = tk.Frame(body, bg=THEME_BG)
        stage.pack(fill="both", expand=True, pady=(14, 0))
        if self.revealed:
            self._build_result(stage)
        else:
            self._build_entry(stage)

    def _prompt_card(self, parent):
        data = self.card
        panel = tk.Frame(parent, bg=PANEL_BG)
        inner = tk.Frame(panel, bg=PANEL_BG)
        inner.pack(fill="x", padx=28, pady=18)
        wrap = max(400, min(900, self._window_width - 220))
        meta = "   ·   ".join(
            part for part in (data.category.upper(), data.direction.upper())
            if part)
        if meta:
            tk.Label(inner, text=meta, bg=PANEL_BG, fg=THEME_FG_DIM,
                     font=FONT_META).pack(anchor="w")
        length = len(data.prompt or "")
        font = (FONT_PROMPT if length <= 32 else
                FONT_PROMPT_MEDIUM if length <= 80 else FONT_PROMPT_SMALL)
        tk.Label(inner, text=data.prompt, bg=PANEL_BG, fg=THEME_FG,
                 font=font, justify="left", wraplength=wrap).pack(anchor="w")
        if data.prompt_sub:
            tk.Label(inner, text=data.prompt_sub, bg=PANEL_BG,
                     fg=THEME_FG_DIM, font=FONT_HINT, justify="left",
                     wraplength=wrap).pack(anchor="w", pady=(2, 0))
        return panel

    def _build_entry(self, parent):
        card = tk.Frame(parent, bg=COVER_BG)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        inner = tk.Frame(card, bg=PANEL_BG)
        inner.pack(fill="both", expand=True, padx=6, pady=6)
        box = tk.Frame(inner, bg=PANEL_BG)
        box.pack(anchor="center", pady=(40, 0))

        tk.Label(box, text="YOUR ANSWER", bg=PANEL_BG, fg=THEME_FG_DIM,
                 font=FONT_META).pack(anchor="w")
        entry = tk.Entry(
            box, font=FONT_ENTRY, width=42, bg="#292929", fg=THEME_FG,
            insertbackground=THEME_FG, relief="flat", highlightthickness=1,
            highlightbackground="#4a4a4a", highlightcolor=THEME_ACCENT,
        )
        entry.pack(pady=(6, 0), ipady=8)
        entry.insert(0, self.typed)
        entry.configure(state="disabled" if self.locked else "normal")
        self._entry = entry
        if not self.locked:
            self.root.after_idle(self.focus_input)
        entry.bind("<KeyRelease>", self._on_type)
        for virtual in ("<<Paste>>", "<<Cut>>", "<<Clear>>"):
            entry.bind(virtual, lambda _e: self.root.after_idle(self._on_type))

    def _on_type(self, event=None):
        if self.locked:
            return
        self.typed = self._current_text()
        self._refresh_action()

    def _refresh_action(self):
        for child in self.root.winfo_children():
            if not isinstance(child, tk.Frame):
                continue
            for button in child.winfo_children():
                if isinstance(button, tk.Button) and button.cget("text") == "Confirm":
                    disabled = self.locked or not self._current_text()
                    button.configure(
                        state="disabled" if disabled else "normal",
                        bg="#3a3a3a" if disabled else THEME_ACCENT,
                        fg="#777777" if disabled else THEME_ACCENT_FG,
                    )

    def _build_result(self, parent):
        overlay = tk.Frame(parent, bg=COVER_BG)
        overlay.pack(fill="both", expand=True, padx=6, pady=6)
        sheet = tk.Frame(overlay, bg=PANEL_BG)
        sheet.pack(anchor="center", padx=6, pady=6)
        inner = tk.Frame(sheet, bg=PANEL_BG)
        inner.pack(padx=60, pady=26)

        correct = self.reveal_correct
        # An intermediate retry must not give the answer away; only the final
        # failure (or a timeout) shows the expected text.
        hide_answer = bool(self._retry_feedback) and not correct
        chip = "CORRECT" if correct else "TRY AGAIN" if hide_answer else "WRONG"
        tk.Label(
            inner, text=chip,
            bg=SUCCESS_BG if correct else WRONG_BG,
            fg=SUCCESS_FG if correct else WRONG_FG,
            font=FONT_CHIP, padx=12, pady=4,
        ).pack(anchor="center")
        wrap = max(300, self._window_width - 200)
        if not correct and not hide_answer:
            tk.Label(inner, text="CORRECT ANSWER", bg=PANEL_BG,
                     fg=THEME_FG_DIM, font=FONT_META).pack(
                anchor="center", pady=(10, 0))
        if not hide_answer:
            answer = tk.Label(
                inner, text=self.card.answer, bg=PANEL_BG,
                fg=SUCCESS_BORDER if correct else WRONG_FG,
                font=FONT_ANSWER, wraplength=wrap,
            )
            answer.pack(anchor="center", pady=(6, 0))
            if self.card.answer_sub:
                tk.Label(inner, text=self.card.answer_sub, bg=PANEL_BG,
                         fg=THEME_FG_DIM, font=FONT_HINT).pack(
                    anchor="center", pady=(2, 0))
        if not correct:
            tk.Label(inner, text=f"YOU TYPED: {self.typed}", bg=PANEL_BG,
                     fg=THEME_FG_DIM, font=FONT_HINT, wraplength=wrap,
                     justify="center").pack(anchor="center", pady=(10, 0))


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
