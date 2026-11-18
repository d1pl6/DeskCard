"""Choose exercise: prompt on top, choices below, an answer sheet after picking.

Run it:

    python src/ui/choose.py

Idle: prompt on top, choices below in one or two columns, wrapped text.
Answered: the choices are covered by a centred answer sheet, so the eye stays in
the middle of the window while the prompt remains above. The answer sheet has
two sides: text on the left, image on the right; either side may be empty.

Choices scroll when a long list does not fit; the answer sheet is sized to fit
and only scrolls as a last resort, so an image answer never forces a scroll hunt.
"""

import tkinter as tk

try:  # imported as ui.choose
    from .helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme,
    )
    from .media import image_frame, play_audio, stop_audio
except ImportError:  # started as a script: python src/ui/choose.py
    from helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme,
    )
    from media import image_frame, play_audio, stop_audio


WINDOW_SIZE = (1000, 760)
WINDOW_MIN = (860, 640)
WINDOW_MARGIN = (120, 140)


# --- Look -----------------------------------------------------------------
# Success/danger tokens do not exist in theme.py yet; keep the pair local so
# the screen can use them without changing the shared theme first.
SUCCESS_BG = "#2f6b46"
SUCCESS_BORDER = "#64c98a"
SUCCESS_FG = "#eaf7ee"
WRONG_BG = "#6e302d"
WRONG_FG = "#fbeceb"
PANEL_BG = "#333333"
CARD_BG = "#3c3c3c"
CARD_HOVER = "#474747"
CARD_BORDER = "#4a4a4a"
CARD_SELECTED = "#24405e"
COVER_BG = "#242424"

FONT = (THEME_FONT_FAMILY, 10)
FONT_CHOICE = (THEME_FONT_FAMILY, 12)
FONT_PROMPT = (THEME_FONT_FAMILY, 28, "bold")
FONT_PROMPT_MEDIUM = (THEME_FONT_FAMILY, 22, "bold")
FONT_PROMPT_SMALL = (THEME_FONT_FAMILY, 18, "bold")
FONT_ANSWER = (THEME_FONT_FAMILY, 30, "bold")
FONT_ANSWER_MEDIUM = (THEME_FONT_FAMILY, 22, "bold")
FONT_ANSWER_SMALL = (THEME_FONT_FAMILY, 16, "bold")
FONT_CHIP = (THEME_FONT_FAMILY, 9, "bold")
FONT_HINT = (THEME_FONT_FAMILY, 9)
FONT_META = (THEME_FONT_FAMILY, 8)

KEY_HINTS = "1234567890"


class ChooseCard:
    """One card's worth of data: what the screen needs, nothing more."""

    def __init__(self, prompt, prompt_sub, answer, answer_sub, choices,
                 correct, category="greetings", direction="normal",
                 has_image=False, prompt_audio=None, answer_audio=None,
                 prompt_image=None, answer_image=None):
        self.prompt = prompt
        self.prompt_sub = prompt_sub
        self.answer = answer
        self.answer_sub = answer_sub
        self.choices = choices
        self.correct = correct
        self.category = category
        self.direction = direction
        self.has_image = has_image
        self.prompt_audio = prompt_audio
        self.answer_audio = answer_audio
        self.prompt_image = prompt_image
        self.answer_image = answer_image


DEFAULT_CARD = ChooseCard(
    "Adiós", "/aˈðjos/", "Goodbye", "/ɡʊdˈbaɪ/",
    ["Goodbye", "Hello", "Please", "Thank you"], 0,
)


# --- Small building blocks ------------------------------------------------
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


class ScrollFrame(tk.Frame):
    """Vertical scroller that centres short content and scrolls long content.

    Tk has no built-in scrollable frame, and the two places that need one have
    different width rules: the choice grid should fill the window, the answer
    sheet should stay a readable card. `fill_width` picks between them.
    """

    def __init__(self, parent, bg, *, fill_width=True, restore_fraction=None):
        super().__init__(parent, bg=bg)
        self._fill_width = fill_width
        self._last_width = None
        self._pending = False
        self._bar_shown = False
        self._restore = restore_fraction

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill="both", expand=True)

        self.content = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window(
            0, 0, window=self.content, anchor="nw")

        self.bar = tk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview,
            width=8, bg="#4a4a4a", troughcolor=bg,
            activebackground="#5a5a5a", relief="flat", borderwidth=0,
            highlightthickness=0,
        )
        self.canvas.configure(yscrollcommand=self._on_scroll)

        self.canvas.bind("<Configure>", lambda _e: self._schedule())
        self.content.bind("<Configure>", lambda _e: self._schedule())
        self._bind_wheel(self)

    def _on_scroll(self, first, last):
        if float(first) <= 0.0 and float(last) >= 1.0:
            if self._bar_shown:
                self.bar.place_forget()
                self._bar_shown = False
        elif not self._bar_shown:
            self.bar.place(relx=1.0, rely=0.0, anchor="ne", relheight=1.0)
            self.bar.lift()
            self._bar_shown = True
        self.bar.set(first, last)

    def _schedule(self):
        if self._pending:
            return
        self._pending = True
        self.after_idle(self._settle)

    def _settle(self):
        self._pending = False
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width < 2 or height < 2:
            return

        available = width - 22
        if self._fill_width:
            content_width = available
        else:
            content_width = min(self.content.winfo_reqwidth(), width - 40)
        content_width = max(1, content_width)

        if content_width != self._last_width:
            width_changed = True
            self._last_width = content_width
            self.canvas.itemconfigure(self._window, width=content_width)
            # Re-wrap first; the height has to be measured again afterwards.
            self._schedule()
        else:
            width_changed = False

        content_height = self.content.winfo_reqheight()
        if content_height <= height:
            if self._restore is None:
                self.canvas.yview_moveto(0)
            y = max(0, (height - content_height) // 2)
        else:
            y = 0
        x = max(0, (width - content_width) // 2)
        self.canvas.coords(self._window, x, y)
        self.canvas.configure(
            scrollregion=(0, 0, width, max(content_height, height)))
        if self._restore is not None and not width_changed:
            self.canvas.yview_moveto(self._restore)
            self._restore = None

    def _bind_wheel(self, widget):
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            widget.bind(sequence, self._wheel, add="+")
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def bind_wheel_tree(self):
        """Call again after adding children to `content`."""
        for child in self.content.winfo_children():
            self._bind_wheel(child)

    def _wheel(self, event):
        if not self._bar_shown:
            return None
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        return "break"


def choice_colors(state):
    if state == "selected":
        return CARD_SELECTED, THEME_ACCENT, "#ffffff", "#31567c"
    return CARD_BG, CARD_BORDER, THEME_FG, "#4d4d4d"


class ChoiceCard(tk.Frame):
    """One clickable answer. The result is shown on the answer sheet, so the
    cards themselves only need idle and selected states."""

    def __init__(self, parent, index, text, *, state="idle", command=None,
                 wraplength=380, font=FONT_CHOICE):
        bg, border, fg, cap_bg = choice_colors(state)
        super().__init__(parent, bg=bg, highlightthickness=2,
                         highlightbackground=border, highlightcolor=border)
        self.state = state
        self.command = command
        self._parts = []  # (widget, colour) for hover recolouring

        row = tk.Frame(self, bg=bg)
        row.pack(fill="both", expand=True, padx=12, pady=10)

        cap_text = KEY_HINTS[index] if index < len(KEY_HINTS) else "·"
        cap = tk.Label(row, text=cap_text, bg=cap_bg, fg=fg, font=FONT_META,
                       width=2, pady=2)
        cap.pack(side="left", padx=(0, 10), anchor="n")
        self._parts += [(cap, cap_bg)]

        label = tk.Label(row, text=text, bg=bg, fg=fg, font=font,
                         anchor="w", justify="left", wraplength=wraplength)
        label.pack(side="left", fill="x", expand=True)
        self._parts += [(self, bg), (row, bg), (label, bg)]

        if self.command is not None:
            for widget, _colour in self._parts:
                widget.bind("<Button-1>", self._click)
            self.bind("<Enter>", self._hover_on)
            self.bind("<Leave>", self._hover_off)
            for widget, _colour in self._parts:
                widget.bind("<Enter>", self._hover_on, add="+")
                widget.bind("<Leave>", self._hover_off, add="+")
            self.configure(cursor="hand2")

    def _click(self, _event):
        self.command()

    def _hover_on(self, _event=None):
        if self.state == "idle":
            self._recolour(CARD_HOVER)

    def _hover_off(self, _event=None):
        if self.state == "idle":
            self._recolour(CARD_BG)

    def _recolour(self, bg):
        for widget, colour in self._parts:
            if colour in (CARD_BG, CARD_HOVER):
                widget.configure(bg=bg)


# --- The Choose screen ----------------------------------------------------
class Application:
    """Prompt, choices, and a centred answer sheet after confirming."""

    def __init__(self, root, card=None, on_result=None, on_skip=None,
                 on_quit=None, warnings=(), prompt_listens=0):
        self.root = root
        root.title("DeskCard - Choose")
        apply_theme(root)

        self.card = card or DEFAULT_CARD
        self.warnings = tuple(warnings)
        self.selected = None
        self.revealed = False
        self.reveal_correct = None
        self.locked = False
        self._freeze_message = ""
        self._on_result = on_result or (lambda _correct: self._continue())
        self._on_skip = on_skip or self._continue
        self._on_quit = on_quit or (lambda: self.root.destroy())
        self._choice_scroll = None
        self._choice_fraction = 0.0
        self._resize_job = None
        self._window_width = 0
        self.prompt_listens = int(prompt_listens)
        self.prompt_plays = 0
        self._prompt_audio_button = None
        self._answer_audio_button = None

        root.bind("<Key-1>", lambda _e: self._pick_key(0))
        root.bind("<Key-2>", lambda _e: self._pick_key(1))
        root.bind("<Key-3>", lambda _e: self._pick_key(2))
        root.bind("<Key-4>", lambda _e: self._pick_key(3))
        root.bind("<Key-5>", lambda _e: self._pick_key(4))
        root.bind("<Key-6>", lambda _e: self._pick_key(5))
        root.bind("<Key-7>", lambda _e: self._pick_key(6))
        root.bind("<Key-8>", lambda _e: self._pick_key(7))
        root.bind("<Key-9>", lambda _e: self._pick_key(8))
        root.bind("<Key-0>", lambda _e: self._pick_key(9))
        root.bind("<Return>", lambda _e: self._enter())
        root.bind("<KP_Enter>", lambda _e: self._enter())
        root.bind("<Escape>", lambda _e: self.on_quit())
        root.bind("<Configure>", self._on_configure)
        root.bind("<Destroy>", self._on_destroy)

        self._fit_window()
        self._build()

    def set_card(self, card):
        """Show another card, e.g. when the session advances."""
        self.card = card
        self._reset()
        self._build()

    # -- state -------------------------------------------------------------
    def _reset(self):
        self.selected = None
        self.revealed = False
        self.reveal_correct = None
        self.locked = False
        self._freeze_message = ""
        self._choice_fraction = 0.0
        self.prompt_plays = 0
        self._prompt_audio_button = None
        self._answer_audio_button = None

    def _pick(self, index):
        if self.locked or self.revealed or index >= len(self.card.choices):
            return
        if self._choice_scroll is not None:
            self._choice_fraction = self._choice_scroll.canvas.yview()[0]
        self.selected = index
        self._build()

    def _pick_key(self, index):
        if not self.revealed:
            self._pick(index)

    def _enter(self):
        if self.locked:
            return
        if self.revealed:
            self._continue()
        elif self.selected is not None:
            self._confirm()

    def _confirm(self):
        if self.locked or self.selected is None:
            return
        self.reveal_correct = self.selected == self.card.correct
        self.revealed = True
        self.locked = True
        self._build()
        self._on_result(self.reveal_correct)

    def _continue(self):
        """Standalone-mode advance; the session runner supplies its own flow."""
        self._reset()
        self._build()

    def retry(self):
        """Show the same card again for another attempt."""
        self._reset()
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

    def freeze(self, message):
        """Lock the card and show a short status while the session waits."""
        self.locked = True
        self._freeze_message = message
        self._build()

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
            self._build_footer()

    def _on_configure(self, event):
        """Re-wrap text when the window is resized; debounced to avoid churn."""
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
        if self._choice_scroll is not None:
            self._choice_fraction = self._choice_scroll.canvas.yview()[0]
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
        """Size the window to the screen, centre it, and set a sane minimum."""
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

    def _build(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        if width > 1:
            self._window_width = width
        self._choice_scroll = None
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
        tk.Label(title, text="  Choose", bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT).pack(side="left")

        actions = tk.Frame(header, bg=THEME_BG)
        actions.pack(side="right")
        flat_button(actions, "Skip", command=self.on_skip,
                    kind="ghost").pack(side="left", padx=(0, 6))
        flat_button(actions, "Quit", command=self.on_quit,
                    kind="danger").pack(side="left")

    def _build_footer(self):
        footer = tk.Frame(self.root, bg=THEME_BG)
        footer.pack(fill="x", side="bottom", padx=28, pady=(4, 16))

        if self._freeze_message:
            hint = self._freeze_message
        elif self.revealed:
            hint = "Enter / Continue for the next card"
        elif self.selected is None:
            hint = "1–9, 0 pick a choice"
        else:
            hint = "Enter confirms · pick another to change"
        tk.Label(footer, text=hint, bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT_HINT).pack(side="left")
        if self.warnings:
            tk.Label(
                footer, text="⚠ " + " · ".join(self.warnings),
                bg=THEME_BG, fg="#d9c04f", font=FONT_META,
                justify="left", wraplength=self._window_width - 160,
            ).pack(side="bottom", anchor="w", pady=(2, 0))

        action_text = "Continue" if self.revealed else "Confirm"
        action_command = self._continue if self.revealed else self._confirm
        action = flat_button(footer, action_text, command=action_command,
                             kind="accent")
        if self.locked or (not self.revealed and self.selected is None):
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
            self._build_answer_stage(stage)
        else:
            self._build_choice_stage(stage)

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
            tk.Label(
                inner, text=meta, bg=PANEL_BG, fg=THEME_FG_DIM, font=FONT_META,
            ).pack(anchor="w")

        row = tk.Frame(inner, bg=PANEL_BG)
        row.pack(anchor="w", pady=(4, 0))
        prompt_length = len(data.prompt)
        if prompt_length <= 32:
            prompt_font = FONT_PROMPT
        elif prompt_length <= 80:
            prompt_font = FONT_PROMPT_MEDIUM
        else:
            prompt_font = FONT_PROMPT_SMALL
        tk.Label(
            row, text=data.prompt, bg=PANEL_BG, fg=THEME_FG,
            font=prompt_font, justify="left", wraplength=wrap,
        ).pack(side="left", anchor="n")
        if data.prompt_audio:
            self._prompt_audio_button = flat_button(
                row, "▶", command=self._play_prompt, small=True)
            self._prompt_audio_button.pack(side="left", padx=(12, 0), pady=(8, 0))

        if data.prompt_sub:
            tk.Label(inner, text=data.prompt_sub, bg=PANEL_BG,
                     fg=THEME_FG_DIM, font=FONT_HINT, justify="left",
                     wraplength=wrap).pack(anchor="w", pady=(2, 0))
        if data.prompt_image:
            image_frame(
                inner, data.prompt_image, width=220, height=136,
                max_size=(212, 128), bg=PANEL_BG, font=FONT_META,
            ).pack(anchor="w", pady=(8, 0))
        return panel

    def _choice_wraplength(self, columns):
        """Text width for one choice card, measured from the window size."""
        available = self._window_width - 78  # body padding + scroll gutter
        column_width = (available - (columns - 1) * 12) / columns
        return max(220, min(760, int(column_width - 70)))

    def _build_choice_stage(self, stage):
        grid_holder = ScrollFrame(
            stage, THEME_BG, fill_width=True,
            restore_fraction=self._choice_fraction,
        )
        grid_holder.pack(fill="both", expand=True)
        self._choice_scroll = grid_holder
        grid = grid_holder.content

        choices = self.card.choices
        # Two columns from four choices on. Long text wraps inside its column
        # instead of collapsing the grid to one column.
        columns = 1 if len(choices) <= 3 else 2
        wraplength = self._choice_wraplength(columns)

        # One frame per row, like test.py: each row keeps its cards together and
        # gives them equal width, so a long label cannot break the grid.
        for start in range(0, len(choices), columns):
            row = tk.Frame(grid, bg=THEME_BG)
            row.pack(fill="x", pady=6)
            for column in range(columns):
                row.columnconfigure(column, weight=1, uniform="choice")

            for column, index in enumerate(
                    range(start, min(start + columns, len(choices)))):
                card = ChoiceCard(
                    row, index, choices[index],
                    state="selected" if index == self.selected else "idle",
                    command=lambda value=index: self._pick(value),
                    wraplength=wraplength,
                )
                card.grid(row=0, column=column, sticky="nsew", padx=6)

        grid_holder.bind_wheel_tree()

    def _build_answer_stage(self, stage):
        overlay = ScrollFrame(stage, COVER_BG, fill_width=False)
        overlay.pack(fill="both", expand=True)

        shadow = tk.Frame(overlay.content, bg="#161616")
        shadow.pack(padx=6, pady=6)
        sheet = tk.Frame(shadow, bg=PANEL_BG)
        sheet.pack(padx=6, pady=6)
        inner = tk.Frame(sheet, bg=PANEL_BG)
        inner.pack(padx=44, pady=20)

        self._answer_body(inner)
        overlay.bind_wheel_tree()

    def _answer_wraplength(self, has_image):
        """Text column width, leaving room for the image side when present."""
        available = self._window_width - 56 - 40 - 110 - 12
        available -= 40  # answer audio button
        if has_image:
            available -= 204  # image slot + gap
        available -= 16  # font-metric safety margin
        return max(240, min(560, int(available)))

    def _chosen_block(self, parent, wrap, anchor="w"):
        """The wrong pick, laid out vertically so it can never widen the sheet."""
        picked = self.card.choices[self.selected]
        block = tk.Frame(parent, bg=PANEL_BG)
        block.pack(anchor=anchor, pady=(8, 0))
        tk.Label(block, text="YOU CHOSE", bg=PANEL_BG, fg=THEME_FG_DIM,
                 font=FONT_META).pack(anchor="w")
        tk.Label(block, text=picked, bg=WRONG_BG, fg=WRONG_FG,
                 font=FONT, padx=8, pady=2, wraplength=wrap,
                 justify="left").pack(anchor="w", pady=(2, 0))

    def _answer_body(self, parent):
        data = self.card
        has_image = data.has_image
        has_text = bool(data.answer or data.answer_sub)
        wrap = self._answer_wraplength(has_image)
        justify = "left" if has_image else "center"

        chip = tk.Label(
            parent, text="CORRECT" if self.reveal_correct else "WRONG",
            bg=SUCCESS_BG if self.reveal_correct else WRONG_BG,
            fg=SUCCESS_FG if self.reveal_correct else WRONG_FG,
            font=FONT_CHIP, padx=12, pady=4,
        )
        chip.pack(anchor="center")

        if not self.reveal_correct:
            tk.Label(parent, text="CORRECT ANSWER", bg=PANEL_BG,
                     fg=THEME_FG_DIM, font=FONT_META).pack(
                anchor="center", pady=(8, 0))

        # Two sides: text on the left, image on the right. Either side may be
        # absent, so image-only and text-only answers share this layout.
        sides = tk.Frame(parent, bg=PANEL_BG)
        sides.pack(anchor="center", pady=(8, 0))

        left = None
        if has_text:
            left = tk.Frame(sides, bg=PANEL_BG)
            left.pack(side="left", anchor="n")

            if data.answer:
                answer_row = tk.Frame(left, bg=PANEL_BG)
                answer_row.pack(anchor="w")
                length = len(data.answer)
                if length <= 30:
                    answer_font = FONT_ANSWER
                elif length <= 60:
                    answer_font = FONT_ANSWER_MEDIUM
                else:
                    answer_font = FONT_ANSWER_SMALL
                tk.Label(
                    answer_row, text=data.answer, bg=PANEL_BG,
                    fg=SUCCESS_BORDER, font=answer_font, wraplength=wrap,
                    justify=justify,
                ).pack(side="left", anchor="n")
                if data.answer_audio:
                    self._answer_audio_button = flat_button(
                        answer_row, "▶", command=self._play_answer, small=True)
                    self._answer_audio_button.pack(side="left", padx=(12, 0),
                                                   pady=(4, 0))

            if data.answer_sub:
                tk.Label(
                    left, text=data.answer_sub, bg=PANEL_BG,
                    fg=THEME_FG_DIM, font=FONT_HINT, wraplength=wrap,
                    justify=justify,
                ).pack(anchor="w", pady=(2, 0))

        if has_image:
            image_size = (180, 112) if has_text else (240, 150)
            slot = self._image_slot(sides, data.answer_image, *image_size)
            slot.pack(side="left", anchor="n",
                      padx=(24 if has_text else 0, 0))

        if not self.reveal_correct:
            if left is not None:
                self._chosen_block(left, wrap)
            else:
                self._chosen_block(parent, wrap, anchor="center")

    def _image_slot(self, parent, path, width=190, height=118):
        """Show the answer image, or a placeholder if it cannot be loaded."""
        return image_frame(
            parent, path, width=width, height=height,
            max_size=(width - 8, height - 8), bg="#2a2a2a", font=FONT_META,
        )


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
