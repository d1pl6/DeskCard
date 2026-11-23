"""Write exercise: type the exact answer, then reveal the result.

Run it:

    python src/ui/write.py

The initial release uses exact matching, including capitalization. Prompt and
answer audio use pygame; images are shown with Pillow when available.
"""

import tkinter as tk

try:  # imported as ui.write
    from .helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme, ui,
    )
    from .media import image_frame, play_audio, stop_audio
except ImportError:  # started as a script: python src/ui/write.py
    from helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme, ui,
    )
    from media import image_frame, play_audio, stop_audio


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
                 category="greetings", direction="normal", card_id="",
                 prompt_audio=None, answer_audio=None,
                 prompt_image=None, answer_image=None):
        self.prompt = prompt
        self.prompt_sub = prompt_sub
        self.answer = answer
        self.answer_sub = answer_sub
        self.category = category
        self.direction = direction
        self.card_id = card_id
        self.prompt_audio = prompt_audio
        self.answer_audio = answer_audio
        self.prompt_image = prompt_image
        self.answer_image = answer_image


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
        padx=ui(8) if small else 16, pady=ui(2) if small else 8,
    )
    options.update(kw)
    return tk.Button(parent, **options)


class Application:
    """Prompt, a text entry, and the exact-match result sheet."""

    def __init__(self, root, card=None, on_result=None, on_skip=None,
                 on_quit=None, warnings=(), prompt_listens=0):
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
        self._standalone = on_result is None
        self._on_result = on_result or (lambda _correct: None)
        self._on_skip = on_skip or (lambda: self._continue())
        self._on_quit = on_quit or (lambda: self.root.destroy())
        self._window_width = 0
        self._resize_job = None
        self._entry = None
        self.prompt_listens = int(prompt_listens)
        self.prompt_plays = 0
        self._prompt_audio_button = None
        self._answer_audio_button = None

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
        self.prompt_plays = 0
        self._prompt_audio_button = None
        self._answer_audio_button = None

    def _refresh_entry(self):
        """Restore the entry panel for another attempt."""
        if self._entry is not None:
            self._entry.configure(state="normal")
            self._entry.delete(0, tk.END)
        if not self.locked:
            self.root.after_idle(self.focus_input)

    def _enter(self):
        if self.locked and not (self._standalone and self.revealed):
            return
        if self.revealed:
            self._continue()
        elif self._current_text():
            self._confirm()

    def _confirm(self):
        typed = self._current_text()
        if self.locked or not typed:
            return
        self.typed = typed
        self.reveal_correct = typed == self.card.answer
        self.revealed = True
        self.locked = True
        self._sync_state()
        self._on_result(self.reveal_correct)

    def _continue(self):
        """Standalone-mode advance; the session runner supplies its own flow."""
        self._reset()
        self._refresh_entry()
        self._sync_state()

    def retry(self, attempt=None):
        """Show the same card again for another attempt."""
        if attempt is not None:
            self.attempt = attempt
        self._reset()
        self._refresh_entry()
        self._sync_state()

    def show_retry(self):
        """Show a brief wrong-answer sheet without giving away the answer."""
        self.revealed = True
        self.reveal_correct = False
        self._retry_feedback = True
        self.locked = True
        self._sync_state()

    def reveal_timeout(self):
        """Show the missed answer when the answer timer expires."""
        if self.revealed:
            return
        self.revealed = True
        self.reveal_correct = False
        self.locked = True
        self._sync_state()

    def on_skip(self):
        if self.locked:
            return
        self.locked = True
        self._on_skip()

    def on_quit(self, event=None):
        if self.locked:
            return
        self._on_quit()

    def auto_play(self):
        """Play the prompt once when the card first opens."""
        self._play_prompt(auto=True)

    def _play_prompt(self, auto=False):
        if not self.card.prompt_audio:
            return
        limit = 1 + self.prompt_listens
        if self.prompt_plays >= limit:
            return
        self.prompt_plays += 1
        self._play(self.card.prompt_audio)
        self._update_audio_buttons()

    def _play_answer(self):
        if self.card.answer_audio:
            self._play(self.card.answer_audio)

    def _play(self, path):
        try:
            play_audio(path)
        except RuntimeError as error:
            self._warn(str(error))

    def _update_audio_buttons(self):
        button = self._prompt_audio_button
        if button is not None:
            remaining = max(0, 1 + self.prompt_listens - self.prompt_plays)
            button.configure(text=f"▶{remaining}" if remaining else "▶")
        answer = self._answer_audio_button
        if answer is not None:
            answer.configure(state="normal")

    def _warn(self, message):
        if message not in self.warnings:
            self.warnings = self.warnings + (message,)
            self._sync_warning()

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
        self._sync_state()

    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        if event.width == self._window_width:
            return
        self._window_width = event.width
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(120, self._sync_wrap)

    def _prompt_wraplength(self):
        return max(ui(400), min(ui(900), self._window_width - ui(220)))

    def _warning_wraplength(self):
        return max(ui(240), self._window_width - ui(160))

    def _result_wraplength(self):
        return max(ui(300), self._window_width - ui(200))

    def _sync_wrap(self):
        """Re-wrap existing text after a resize; no widget teardown."""
        self._resize_job = None
        wrap = self._prompt_wraplength()
        for label in self._prompt_wrap_labels:
            if label.winfo_exists():
                label.configure(wraplength=wrap)
        self._sync_result()
        self._sync_warning()

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
        self.root.minsize(min(ui(WINDOW_MIN[0]), width), min(ui(WINDOW_MIN[1]), height))
        self._window_width = width

    def _build(self):
        self._entry = None
        self.root.update_idletasks()
        width = self.root.winfo_width()
        if width > 1:
            self._window_width = width
        self._skip_button = None
        self._quit_button = None
        self._confirm_button = None
        self._hint_label = None
        self._warning_label = None
        self._footer = None
        self._entry_panel = None
        self._result_panel = None
        self._prompt_wrap_labels = []
        self._chip_label = None
        self._caption_label = None
        self._answer_block = None
        self._answer_label = None
        self._answer_sub_label = None
        self._typed_label = None
        for child in self.root.winfo_children():
            child.destroy()
        self._build_header()
        self._build_footer()
        self._build_body()
        self._sync_state()

    def _hint_text(self):
        if self._freeze_message:
            return self._freeze_message
        if self._retry_feedback:
            return "Not quite — try again"
        return "Type the exact answer, then press Enter to confirm"

    def _sync_state(self):
        """Apply changing widgets without tearing down the whole screen."""
        state = "disabled" if self.locked else "normal"
        for button in (self._skip_button, self._quit_button):
            if button is not None:
                button.configure(state=state)
        if self._entry is not None:
            self._entry.configure(state=state)
        if self._entry_panel is not None:
            if self.revealed:
                self._entry_panel.pack_forget()
            else:
                self._entry_panel.pack(fill="both", expand=True, padx=ui(6), pady=ui(6))
        if self._result_panel is not None:
            if self.revealed:
                self._result_panel.pack(fill="both", expand=True, padx=ui(6), pady=ui(6))
            else:
                self._result_panel.pack_forget()
        if self._hint_label is not None:
            self._hint_label.configure(text=self._hint_text())
        self._refresh_action()
        self._sync_result()
        self._sync_warning()

    def _refresh_action(self):
        if self._confirm_button is None:
            return
        disabled = self.locked or not self._current_text()
        self._confirm_button.configure(
            state="disabled" if disabled else "normal",
            bg="#3a3a3a" if disabled else THEME_ACCENT,
            fg="#777777" if disabled else THEME_ACCENT_FG,
        )

    def _sync_warning(self):
        if self._footer is None:
            return
        wrap = self._warning_wraplength()
        if not self.warnings:
            if self._warning_label is not None:
                self._warning_label.pack_forget()
            return
        text = "⚠ " + " · ".join(self.warnings)
        if self._warning_label is None:
            self._warning_label = tk.Label(
                self._footer, text=text, bg=THEME_BG, fg="#d9c04f",
                font=FONT_META, justify="left", wraplength=wrap,
            )
            self._warning_label.pack(side="bottom", anchor="w", pady=ui((2, 0)))
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
        tk.Label(title, text="  Write", bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT).pack(side="left")
        actions = tk.Frame(header, bg=THEME_BG)
        actions.pack(side="right")
        self._skip_button = flat_button(
            actions, "Skip", command=self.on_skip, kind="ghost")
        self._skip_button.pack(side="left", padx=ui((0, 6)))
        self._quit_button = flat_button(
            actions, "Quit", command=self.on_quit, kind="danger")
        self._quit_button.pack(side="left")

    def _build_footer(self):
        self._footer = tk.Frame(self.root, bg=THEME_BG)
        self._footer.pack(fill="x", side="bottom", padx=ui(28), pady=ui((4, 16)))
        self._hint_label = tk.Label(
            self._footer, text="", bg=THEME_BG, fg=THEME_FG_DIM,
            font=FONT_HINT,
        )
        self._hint_label.pack(side="left")
        self._confirm_button = flat_button(
            self._footer, "Confirm", command=self._confirm, kind="accent")
        self._confirm_button.pack(side="right")

    # -- body --------------------------------------------------------------
    def _build_body(self):
        body = tk.Frame(self.root, bg=THEME_BG)
        body.pack(fill="both", expand=True, padx=ui(28), pady=ui((6, 0)))
        self._prompt_card(body).pack(fill="x")

        stage = tk.Frame(body, bg=THEME_BG)
        stage.pack(fill="both", expand=True, pady=ui((14, 0)))
        # Both stages are built once; _sync_state only toggles which is shown.
        self._entry_panel = tk.Frame(stage, bg=THEME_BG)
        self._build_entry(self._entry_panel)
        self._result_panel = tk.Frame(stage, bg=THEME_BG)
        self._build_result(self._result_panel)

    def _prompt_card(self, parent):
        data = self.card
        panel = tk.Frame(parent, bg=PANEL_BG)
        inner = tk.Frame(panel, bg=PANEL_BG)
        inner.pack(fill="x", padx=ui(28), pady=ui(18))
        wrap = self._prompt_wraplength()
        meta = "   ·   ".join(
            part for part in (data.category.upper(), data.direction.upper())
            if part)
        if meta:
            tk.Label(inner, text=meta, bg=PANEL_BG, fg=THEME_FG_DIM,
                     font=FONT_META).pack(anchor="w")
        length = len(data.prompt or "")
        font = (FONT_PROMPT if length <= 32 else
                FONT_PROMPT_MEDIUM if length <= 80 else FONT_PROMPT_SMALL)
        row = tk.Frame(inner, bg=PANEL_BG)
        row.pack(anchor="w")
        prompt_label = tk.Label(row, text=data.prompt, bg=PANEL_BG,
                                fg=THEME_FG, font=font, justify="left",
                                wraplength=wrap)
        prompt_label.pack(side="left", anchor="n")
        self._prompt_wrap_labels.append(prompt_label)
        if data.prompt_audio:
            self._prompt_audio_button = flat_button(
                row, "▶", command=self._play_prompt, small=True)
            self._prompt_audio_button.pack(side="left", padx=ui((12, 0)), pady=ui((8, 0)))
        if data.prompt_sub:
            sub_label = tk.Label(inner, text=data.prompt_sub, bg=PANEL_BG,
                                 fg=THEME_FG_DIM, font=FONT_HINT,
                                 justify="left", wraplength=wrap)
            sub_label.pack(anchor="w", pady=ui((2, 0)))
            self._prompt_wrap_labels.append(sub_label)
        if data.prompt_image:
            image_frame(
                inner, data.prompt_image, width=220, height=136,
                max_size=(212, 128), bg=PANEL_BG, font=FONT_META,
            ).pack(anchor="w", pady=ui((8, 0)))
        return panel

    def _build_entry(self, parent):
        card = tk.Frame(parent, bg=COVER_BG)
        card.pack(fill="both", expand=True)
        inner = tk.Frame(card, bg=PANEL_BG)
        inner.pack(fill="both", expand=True, padx=ui(6), pady=ui(6))
        box = tk.Frame(inner, bg=PANEL_BG)
        box.pack(anchor="center", pady=ui((40, 0)))

        tk.Label(box, text="YOUR ANSWER", bg=PANEL_BG, fg=THEME_FG_DIM,
                 font=FONT_META).pack(anchor="w")
        entry = tk.Entry(
            box, font=FONT_ENTRY, width=42, bg="#292929", fg=THEME_FG,
            insertbackground=THEME_FG, relief="flat", highlightthickness=1,
            highlightbackground="#4a4a4a", highlightcolor=THEME_ACCENT,
        )
        entry.pack(pady=ui((6, 0)), ipady=ui(8))
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

    def _build_result(self, parent):
        overlay = tk.Frame(parent, bg=COVER_BG)
        overlay.pack(fill="both", expand=True)
        sheet = tk.Frame(overlay, bg=PANEL_BG)
        sheet.pack(anchor="center", padx=ui(6), pady=ui(6))
        inner = tk.Frame(sheet, bg=PANEL_BG)
        inner.pack(padx=ui(60), pady=ui(26))

        self._chip_label = tk.Label(
            inner, text="", font=FONT_CHIP, padx=ui(12), pady=ui(4))
        self._chip_label.pack(anchor="center")
        self._caption_label = tk.Label(
            inner, text="CORRECT ANSWER", bg=PANEL_BG,
            fg=THEME_FG_DIM, font=FONT_META)

        self._answer_block = tk.Frame(inner, bg=PANEL_BG)
        answer_row = tk.Frame(self._answer_block, bg=PANEL_BG)
        answer_row.pack(anchor="center", pady=ui((6, 0)))
        self._answer_label = tk.Label(
            answer_row, text=self.card.answer, bg=PANEL_BG, font=FONT_ANSWER)
        self._answer_label.pack(side="left", anchor="n")
        if self.card.answer_audio:
            self._answer_audio_button = flat_button(
                answer_row, "▶", command=self._play_answer, small=True)
            self._answer_audio_button.pack(side="left", padx=ui((12, 0)), pady=ui((4, 0)))
        if self.card.answer_sub:
            self._answer_sub_label = tk.Label(
                self._answer_block, text=self.card.answer_sub, bg=PANEL_BG,
                fg=THEME_FG_DIM, font=FONT_HINT)
            self._answer_sub_label.pack(anchor="center", pady=ui((2, 0)))
        if self.card.answer_image:
            image_frame(
                self._answer_block, self.card.answer_image, width=260, height=160,
                max_size=(252, 152), bg=PANEL_BG, font=FONT_META,
            ).pack(anchor="center", pady=ui((8, 0)))

        self._typed_label = tk.Label(
            inner, text="", bg=PANEL_BG, fg=THEME_FG_DIM, font=FONT_HINT,
            justify="center")
        self._typed_label.pack(anchor="center", pady=ui((10, 0)))

    def _sync_result(self):
        if self._chip_label is None:
            return
        correct = self.reveal_correct
        # An intermediate retry must not give the answer away; only the final
        # failure (or a timeout) shows the expected text.
        hide_answer = bool(self._retry_feedback) and not correct
        chip = "CORRECT" if correct else "TRY AGAIN" if hide_answer else "WRONG"
        self._chip_label.configure(
            text=chip,
            bg=SUCCESS_BG if correct else WRONG_BG,
            fg=SUCCESS_FG if correct else WRONG_FG,
        )
        wrap = self._result_wraplength()
        self._answer_label.configure(
            text=self.card.answer, wraplength=wrap,
            fg=SUCCESS_BORDER if correct else WRONG_FG)
        if self._answer_sub_label is not None:
            self._answer_sub_label.configure(wraplength=wrap)
        self._typed_label.configure(
            text=f"YOU TYPED: {self.typed}", wraplength=wrap)
        if hide_answer:
            self._caption_label.pack_forget()
            self._answer_block.pack_forget()
        else:
            if correct:
                self._caption_label.pack_forget()
            else:
                self._caption_label.pack(anchor="center", pady=ui((10, 0)))
            self._answer_block.pack(anchor="center")


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
