"""Connect exercise: match prompts on the left with answers on the right.

Run it:

    python src/ui/connect.py

Click a prompt, then an answer (or the other way around) to connect them.
Connected pairs get a colour; Confirm checks every connection.
"""

import random
import tkinter as tk

try:  # imported as ui.connect
    from .helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme,
    )
    from .media import image_frame, play_audio, stop_audio
except ImportError:  # started as a script: python src/ui/connect.py
    from helpers.theme import (
        THEME_ACCENT, THEME_ACCENT_FG, THEME_ACCENT_HOVER, THEME_BG,
        THEME_DANGER, THEME_DANGER_HOVER, THEME_FG, THEME_FG_DIM,
        THEME_FONT_BOLD, THEME_FONT_FAMILY, THEME_FONT_SMALL,
        apply_theme,
    )
    from media import image_frame, play_audio, stop_audio


WINDOW_SIZE = (920, 740)
WINDOW_MIN = (780, 620)
WINDOW_MARGIN = (120, 140)

SUCCESS_BG = "#2f6b46"
SUCCESS_BORDER = "#64c98a"
SUCCESS_FG = "#eaf7ee"
WRONG_BG = "#6e302d"
WRONG_BORDER = "#e0716a"
WRONG_FG = "#fbeceb"
PANEL_BG = "#333333"
CARD_BG = "#3c3c3c"
CARD_HOVER = "#474747"
CARD_BORDER = "#4a4a4a"
CARD_SELECTED = "#24405e"
CONNECTED_BG = "#2f4358"
COVER_BG = "#242424"

PAIR_COLORS = [
    "#5b8db8", "#b87a5b", "#6fbf73", "#c96fd9", "#d9c04f",
    "#4fd9c9", "#d94f8b", "#8b4fd9", "#9fd94f", "#d94f4f",
]

FONT = (THEME_FONT_FAMILY, 10)
FONT_PROMPT = (THEME_FONT_FAMILY, 15, "bold")
FONT_ANSWER = (THEME_FONT_FAMILY, 15, "bold")
FONT_SUB = (THEME_FONT_FAMILY, 9)
FONT_CHIP = (THEME_FONT_FAMILY, 9, "bold")
FONT_HINT = (THEME_FONT_FAMILY, 9)
FONT_META = (THEME_FONT_FAMILY, 8)


class ConnectPair:
    """One matched pair: a prompt side and an answer side."""

    def __init__(self, prompt, prompt_sub="", answer="", answer_sub="",
                 category="greetings", direction="normal",
                 prompt_audio=None, answer_audio=None,
                 prompt_image=None, answer_image=None):
        self.prompt = prompt
        self.prompt_sub = prompt_sub
        self.answer = answer
        self.answer_sub = answer_sub
        self.category = category
        self.direction = direction
        self.prompt_audio = prompt_audio
        self.answer_audio = answer_audio
        self.prompt_image = prompt_image
        self.answer_image = answer_image


class ConnectCard:
    """A set of pairs to connect (2 to 10)."""

    def __init__(self, pairs):
        if len(pairs) < 2:
            raise ValueError("Connect needs at least 2 pairs")
        if len(pairs) > 10:
            raise ValueError("Connect supports at most 10 pairs")
        self.pairs = list(pairs)


DEFAULT_CARD = ConnectCard([
    ConnectPair("Hello", "/həˈloʊ/", "Hola", "/ˈoʊlɑː/"),
    ConnectPair("Goodbye", "/ɡʊdˈbaɪ/", "Adiós", "/aˈðjos/"),
    ConnectPair("Please", "/pliːz/", "Por favor AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP", "/poɾ faˈβoɾ/"),
    ConnectPair("Thank you The Virus and Antidote - babynoitwontstop-ft-lambo-lawson AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP  AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP AND IT WON'T STOP BABY IT WON'T STOP", "/ˈθæŋk juː/", "Gracias", "/ˈɡɾasjas/"),
])


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


def connect_colors(state, color, revealed, correct):
    if revealed:
        if correct:
            return SUCCESS_BG, SUCCESS_BORDER, SUCCESS_FG
        return WRONG_BG, WRONG_BORDER, WRONG_FG
    if state == "selected":
        return CARD_SELECTED, THEME_ACCENT, THEME_FG
    if state == "paired":
        return CONNECTED_BG, color, THEME_FG
    return CARD_BG, CARD_BORDER, THEME_FG


class ConnectItem(tk.Frame):
    """One prompt or answer card in a Connect column."""

    def __init__(self, parent, text, sub, state, selected, paired, color,
                 revealed, correct, on_click, wraplength, audio=None,
                 on_play=None, image=None):
        bg, border, fg = connect_colors(state, color, revealed, correct)

        super().__init__(parent, bg=bg, highlightthickness=2,
                         highlightbackground=border, cursor="hand2")
        self._fg_widgets = []
        self._wrap_labels = []
        self._parts = [(self, bg)]
        inner = tk.Frame(self, bg=bg)
        inner.pack(fill="x", padx=12, pady=8)
        self._parts.append((inner, bg))

        label = tk.Label(inner, text=text, bg=bg, fg=fg, font=FONT,
                         anchor="w", justify="left", wraplength=wraplength)
        label.pack(anchor="w")
        self._parts.append((label, bg))
        self._fg_widgets.append(label)
        self._wrap_labels.append(label)

        if audio:
            audio_row = tk.Frame(inner, bg=bg)
            audio_row.pack(anchor="w")
            flat_button(audio_row, "▶", command=on_play, small=True).pack(
                side="left")
            self._parts.append((audio_row, bg))

        if image:
            image_frame(
                inner, image, width=120, height=72, max_size=(112, 64), bg=bg,
                font=FONT_SUB,
            ).pack(anchor="w", pady=(4, 0))

        if sub:
            sub_label = tk.Label(inner, text=sub, bg=bg, fg=THEME_FG_DIM,
                                 font=FONT_SUB, anchor="w", justify="left",
                                 wraplength=wraplength)
            sub_label.pack(anchor="w", pady=(2, 0))
            self._parts.append((sub_label, bg))
            self._fg_widgets.append(sub_label)
            self._wrap_labels.append(sub_label)

        for widget, _colour in self._parts:
            widget.bind("<Button-1>", lambda _e, cb=on_click: cb())
        self.bind("<Button-1>", lambda _e, cb=on_click: cb())
        self.bind("<Enter>", lambda _e: self._hover(bg, True))
        self.bind("<Leave>", lambda _e: self._hover(bg, False))

    def set_wraplength(self, wraplength):
        for label in self._wrap_labels:
            label.configure(wraplength=wraplength)

    def set_appearance(self, state, color, revealed, correct):
        """Recolour an existing card instead of rebuilding the whole grid."""
        bg, border, fg = connect_colors(state, color, revealed, correct)
        self.configure(highlightbackground=border, highlightcolor=border)
        for widget, _colour in self._parts:
            widget.configure(bg=bg)
        for widget in self._fg_widgets:
            widget.configure(fg=fg)

    def _hover(self, base, entering):
        pass


class Application:
    """Match the prompts on the left with the answers on the right."""

    def __init__(self, root, card=None, on_result=None, on_skip=None,
                 on_quit=None, warnings=(), prompt_listens=0):
        self.root = root
        root.title("DeskCard - Connect")
        apply_theme(root)

        self.card = card or DEFAULT_CARD
        self.warnings = tuple(warnings)
        self.locked = False
        self._freeze_message = ""
        self._on_result = on_result or (lambda _correct: self._continue())
        self._on_skip = on_skip or (lambda: self._continue())
        self._on_quit = on_quit or (lambda: self.root.destroy())
        self.left_selected = None
        self.right_selected = None
        self.pairs = {}          # left index -> right index
        self.reverse = {}        # right index -> left index
        self.pair_color = {}
        self.revealed = False
        self.reveal_correct = None
        self.correct_count = 0
        self._left_widgets = {}
        self._right_widgets = {}
        self._canvas = None
        self._resize_job = None
        self._draw_job = None
        self._window_width = 0
        self.prompt_listens = int(prompt_listens)
        self.prompt_plays = 0
        self._prompt_plays = {}

        root.bind("<Return>", lambda _e: self._enter())
        root.bind("<KP_Enter>", lambda _e: self._enter())
        root.bind("<Escape>", lambda _e: self.on_quit())
        root.bind("<Configure>", self._on_configure)
        root.bind("<Destroy>", self._on_destroy)

        self._fit_window()
        self._reset()
        self._build()

    def set_card(self, card):
        self.card = card
        self._reset()
        self._build()

    # -- state -------------------------------------------------------------
    def _reset(self):
        self.locked = False
        self._freeze_message = ""
        self.left_selected = None
        self.right_selected = None
        self.pairs = {}
        self.reverse = {}
        self.pair_color = {}
        self.revealed = False
        self.reveal_correct = None
        self.correct_count = 0
        self.prompt_plays = 0
        self._prompt_plays = {}
        self._left_widgets = {}
        self._right_widgets = {}
        n = len(self.card.pairs)
        self.left_order = list(range(n))
        self.right_order = list(range(n))
        random.shuffle(self.left_order)
        random.shuffle(self.right_order)

    def _pair(self, left, right):
        self.pairs[left] = right
        self.reverse[right] = left
        used = set(self.pair_color.values())
        color = None
        for candidate in PAIR_COLORS:
            if candidate not in used:
                color = candidate
                break
        if color is None:
            color = PAIR_COLORS[len(self.pairs) % len(PAIR_COLORS)]
        self.pair_color[left] = color

    def _unpair(self, left):
        right = self.pairs.pop(left, None)
        if right is not None:
            self.reverse.pop(right, None)
        self.pair_color.pop(left, None)

    def _click_left(self, index):
        if self.locked or self.revealed:
            return
        if index in self.pairs:
            self._unpair(index)
        if self.right_selected is not None and index not in self.pairs:
            right = self.right_selected
            if right in self.reverse:
                self._unpair(self.reverse[right])
            self._pair(index, right)
            self.left_selected = None
            self.right_selected = None
        else:
            self.left_selected = index
        self._sync_state()

    def _click_right(self, index):
        if self.locked or self.revealed:
            return
        if index in self.reverse:
            self._unpair(self.reverse[index])
        if self.left_selected is not None and index not in self.reverse:
            left = self.left_selected
            if left in self.pairs:
                self._unpair(left)
            self._pair(left, index)
            self.left_selected = None
            self.right_selected = None
        else:
            self.right_selected = index
        self._sync_state()

    def _enter(self):
        if self.locked:
            return
        if self.revealed:
            self._continue()
        else:
            self._confirm()

    def _confirm(self):
        if self.locked:
            return
        n = len(self.card.pairs)
        if len(self.pairs) != n:
            return
        self.correct_count = sum(
            1 for left, right in self.pairs.items()
            if self.left_order[left] == self.right_order[right]
        )
        self.reveal_correct = self.correct_count == n
        self.revealed = True
        self.locked = True
        self._sync_state()
        self._on_result(self.reveal_correct)

    def _continue(self):
        self._reset()
        self._sync_state()

    def retry(self):
        """Show the same pairs again for another attempt."""
        self._reset()
        self._sync_state()

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
        self._sync_state()

    def auto_play(self):
        """Play the first prompt's audio once when the card opens."""
        pairs = self.card.pairs
        if pairs and pairs[0].prompt_audio:
            self._play_prompt(pairs[0].prompt_audio, "p0")

    def _play_prompt(self, path, key=None):
        if not path:
            return
        key = key or path
        limit = 1 + self.prompt_listens
        plays = self._prompt_plays.get(key, 0)
        if plays >= limit:
            return
        self._prompt_plays[key] = plays + 1
        self.prompt_plays += 1
        self._play(path)

    def _play_answer(self, path):
        self._play(path)

    def _play(self, path):
        try:
            play_audio(path)
        except RuntimeError as error:
            self._warn(str(error))

    def _warn(self, message):
        if message not in self.warnings:
            self.warnings = self.warnings + (message,)
            self._sync_warning()

    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        if abs(event.width - self._window_width) < 8:
            return
        self._window_width = event.width
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(120, self._sync_wrap)

    def _sync_wrap(self):
        """Re-wrap existing cards after a resize; no widget teardown."""
        self._resize_job = None
        wrap = self._wraplength()
        for item in (*self._left_widgets.values(), *self._right_widgets.values()):
            item.set_wraplength(wrap)
        self._schedule_draw()
        self._sync_warning()

    def _on_destroy(self, event):
        if event.widget is not self.root:
            return
        for name in ("_resize_job", "_draw_job"):
            job = getattr(self, name)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, name, None)

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
        self._left_widgets = {}
        self._right_widgets = {}
        self._skip_button = None
        self._quit_button = None
        self._action_button = None
        self._hint_label = None
        self._warning_label = None
        self._footer = None
        self._canvas = None
        for child in self.root.winfo_children():
            child.destroy()
        self._build_header()
        self._build_body()
        self._build_footer()
        self._sync_state()
        self._schedule_draw()

    def _hint_text(self):
        n = len(self.card.pairs)
        if self._freeze_message:
            return self._freeze_message
        if self.revealed:
            return f"{self.correct_count} of {n} correct"
        if len(self.pairs) < n:
            return f"Connect {n - len(self.pairs)} more"
        if self.left_selected is None and self.right_selected is None:
            return "Enter confirms"
        return "Pick the other side"

    def _right_color(self, row):
        for left, right in self.pairs.items():
            if right == row:
                return self.pair_color.get(left, PAIR_COLORS[0])
        return PAIR_COLORS[0]

    def _sync_state(self):
        """Recolour cards and refresh labels; never rebuild the tree."""
        state = "disabled" if self.locked else "normal"
        for button in (self._skip_button, self._quit_button):
            if button is not None:
                button.configure(state=state)
        if self._action_button is not None:
            disabled = self.locked or (
                not self.revealed and len(self.pairs) != len(self.card.pairs))
            self._action_button.configure(
                state="disabled" if disabled else "normal",
                bg="#3a3a3a" if disabled else THEME_ACCENT,
                fg="#777777" if disabled else THEME_ACCENT_FG,
            )
        if self._hint_label is not None:
            self._hint_label.configure(text=self._hint_text())
        for row, item in self._left_widgets.items():
            correct = self._pair_correct(row) if self.revealed else None
            item.set_appearance(
                self._left_state(row),
                self.pair_color.get(row, PAIR_COLORS[0]),
                self.revealed, correct,
            )
        for row, item in self._right_widgets.items():
            correct = None
            if self.revealed and row in self.reverse:
                correct = (self.left_order[self.reverse[row]]
                           == self.right_order[row])
            item.set_appearance(
                self._right_state(row), self._right_color(row),
                self.revealed, correct,
            )
        self._schedule_draw()
        self._sync_warning()

    def _sync_warning(self):
        if self._footer is None:
            return
        wrap = max(240, self._window_width - 160)
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
            self._warning_label.pack(side="bottom", anchor="w", pady=(2, 0))
        else:
            self._warning_label.configure(text=text, wraplength=wrap)

    def _schedule_draw(self):
        if self._draw_job is not None:
            try:
                self.root.after_cancel(self._draw_job)
            except tk.TclError:
                pass
        self._draw_job = self.root.after_idle(self._draw_lines)

    def _build_header(self):
        header = tk.Frame(self.root, bg=THEME_BG)
        header.pack(fill="x", padx=28, pady=(14, 4))

        title = tk.Frame(header, bg=THEME_BG)
        title.pack(side="left")
        tk.Label(title, text="◆ DeskCard", bg=THEME_BG, fg=THEME_ACCENT,
                 font=THEME_FONT_BOLD).pack(side="left")
        tk.Label(title, text="  Connect", bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT).pack(side="left")

        actions = tk.Frame(header, bg=THEME_BG)
        actions.pack(side="right")
        self._skip_button = flat_button(
            actions, "Skip", command=self.on_skip, kind="ghost")
        self._skip_button.pack(side="left", padx=(0, 6))
        self._quit_button = flat_button(
            actions, "Quit", command=self.on_quit, kind="danger")
        self._quit_button.pack(side="left")

    def _build_body(self):
        body = tk.Frame(self.root, bg=THEME_BG)
        body.pack(fill="both", expand=True, padx=28, pady=(6, 0))

        titles = tk.Frame(body, bg=THEME_BG)
        titles.pack(fill="x", pady=(0, 8))
        tk.Label(titles, text="Prompts", bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT_HINT).pack(side="left")
        tk.Label(titles, text="Answers", bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT_HINT).pack(side="right")

    def _build_body(self):
        body = tk.Frame(self.root, bg=THEME_BG)
        body.pack(fill="both", expand=True, padx=28, pady=(6, 0))

        titles = tk.Frame(body, bg=THEME_BG)
        titles.pack(fill="x", pady=(0, 8))
        tk.Label(titles, text="Prompts", bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT_HINT).pack(side="left")
        tk.Label(titles, text="Answers", bg=THEME_BG, fg=THEME_FG_DIM,
                 font=FONT_HINT).pack(side="right")

        scroller = tk.Frame(body, bg=THEME_BG)
        scroller.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(scroller, bg=THEME_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(scroller, orient="vertical",
                                 command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._content = tk.Frame(self._canvas, bg=THEME_BG)
        self._content_window = self._canvas.create_window(
            (0, 0), window=self._content, anchor="nw")
        self._content.bind("<Configure>", lambda _e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfigure(
            self._content_window, width=e.width))

        columns = tk.Frame(self._content, bg=THEME_BG)
        columns.pack(fill="both", expand=True)
        columns.columnconfigure(0, weight=1, uniform="connect")
        columns.columnconfigure(1, weight=1, uniform="connect")

        wrap = self._wraplength()
        n = len(self.card.pairs)
        for row in range(n):
            columns.rowconfigure(row, weight=1)

            left_index = self.left_order[row]
            pair = self.card.pairs[left_index]
            color = self.pair_color.get(row, PAIR_COLORS[0])

            item = ConnectItem(
                columns, pair.prompt, pair.prompt_sub,
                self._left_state(row), row == self.left_selected,
                row in self.pairs, color, self.revealed,
                self._pair_correct(row) if self.revealed else None,
                lambda value=row: self._click_left(value), wrap,
                audio=pair.prompt_audio,
                on_play=lambda path=pair.prompt_audio, key=f"p{row}": (
                    self._play_prompt(path, key)
                ),
                image=pair.prompt_image,
            )
            item.grid(row=row, column=0, sticky="nsew", padx=(0, 12), pady=6)
            self._left_widgets[row] = item

            right_index = self.right_order[row]
            rpair = self.card.pairs[right_index]
            right_color = PAIR_COLORS[0]
            for left, right in self.pairs.items():
                if right == row:
                    right_color = self.pair_color.get(left, PAIR_COLORS[0])
            rstate = self._right_state(row)
            rcorrect = None
            if self.revealed and row in self.reverse:
                rcorrect = self.left_order[self.reverse[row]] == self.right_order[row]
            ritem = ConnectItem(
                columns, rpair.answer, rpair.answer_sub,
                rstate, row == self.right_selected,
                row in self.reverse, right_color, self.revealed, rcorrect,
                lambda value=row: self._click_right(value), wrap,
                audio=rpair.answer_audio,
                on_play=lambda path=rpair.answer_audio: self._play_answer(path),
                image=rpair.answer_image,
            )
            ritem.grid(row=row, column=1, sticky="nsew", padx=(12, 0), pady=6)
            self._right_widgets[row] = ritem

        self._bind_wheel(self._content)

    def _bind_wheel(self, widget):
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            widget.bind(sequence, self._wheel, add="+")
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def _wheel(self, event):
        if event.delta:
            step = -1 if event.delta > 0 else 1
        elif getattr(event, "num", 0) == 4:
            step = -1
        elif getattr(event, "num", 0) == 5:
            step = 1
        else:
            return
        self._canvas.yview_scroll(step, "units")

    def _left_state(self, index):
        if self.revealed:
            if index in self.pairs:
                return "correct" if self._pair_correct(index) else "wrong"
            return "idle"
        if index in self.pairs:
            return "paired"
        if index == self.left_selected:
            return "selected"
        return "idle"

    def _right_state(self, index):
        if self.revealed:
            if index in self.reverse:
                left = self.reverse[index]
                return "correct" if self.left_order[left] == self.right_order[index] else "wrong"
            return "idle"
        if index in self.reverse:
            return "paired"
        if index == self.right_selected:
            return "selected"
        return "idle"

    def _pair_correct(self, left):
        right = self.pairs.get(left)
        if right is None:
            return False
        return self.left_order[left] == self.right_order[right]

    def _wraplength(self):
        available = self._window_width - 56 - 36 - 40
        column = available // 2
        return max(180, min(420, int(column - 70)))

    def _build_footer(self):
        self._footer = tk.Frame(self.root, bg=THEME_BG)
        self._footer.pack(fill="x", side="bottom", padx=28, pady=(4, 16))
        self._hint_label = tk.Label(
            self._footer, text="", bg=THEME_BG, fg=THEME_FG_DIM,
            font=FONT_HINT)
        self._hint_label.pack(side="left")
        self._action_button = flat_button(
            self._footer, "Confirm", command=self._confirm, kind="accent")
        self._action_button.pack(side="right")

    def _draw_lines(self):
        self._draw_job = None
        if self._canvas is None:
            return
        try:
            # The runner may replace this card before the idle callback runs;
            # the old canvas command then no longer exists.
            if not self.root.winfo_exists() or not self._canvas.winfo_exists():
                return
            self._canvas.delete("connect_line")
        except tk.TclError:
            return
        for left, right in self.pairs.items():
            lw = self._left_widgets.get(left)
            rw = self._right_widgets.get(right)
            if lw is None or rw is None:
                continue
            try:
                x1 = lw.winfo_x() + lw.winfo_width()
                y1 = lw.winfo_y() + lw.winfo_height() // 2
                x2 = rw.winfo_x()
                y2 = rw.winfo_y() + rw.winfo_height() // 2
            except tk.TclError:
                return
            if self.revealed:
                color = SUCCESS_BORDER if self.left_order[left] == self.right_order[right] else WRONG_BORDER
            else:
                color = self.pair_color.get(left, PAIR_COLORS[0])
            self._canvas.create_line(
                x1, y1, x2, y2, fill=color, width=3, smooth=True,
                capstyle=tk.ROUND, tags=("connect_line",))
        self._canvas.tag_raise(self._content_window)


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
