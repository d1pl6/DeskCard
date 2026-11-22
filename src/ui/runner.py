"""Drive a session by showing exercise windows one card at a time.

The runner owns no study rules: those live in :mod:`src.session`. It consumes
the engine's ``Delay`` and ``Presentation`` events, feeds each exercise screen
with real card data, records results, and quits when the session ends.
"""

import time
import tkinter as tk
from tkinter import messagebox

try:  # imported as ui.runner
    from ..app_preferences import (
        apply_window_preferences, load_preferences, remember_window_preferences,
        save_preferences,
    )
    from .anki import AnkiCard, Application as AnkiApplication, CardSide
    from .choose import Application as ChooseApplication, ChooseCard
    from .connect import Application as ConnectApplication, ConnectCard, ConnectPair
    from .write import Application as WriteApplication, WriteCard
    from ..errors import ConfigError
    from ..session import Delay, Presentation
    from .helpers.theme import (
        THEME_BG, THEME_FIELD_BG, THEME_FG, THEME_FG_DIM, THEME_FONT_SMALL, ui,
    )
    from .media import configure_images, stop_audio
except ImportError:  # started as a script from src/ui
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app_preferences import (
        apply_window_preferences, load_preferences, remember_window_preferences,
        save_preferences,
    )
    from anki import AnkiCard, Application as AnkiApplication, CardSide
    from choose import Application as ChooseApplication, ChooseCard
    from connect import Application as ConnectApplication, ConnectCard, ConnectPair
    from write import Application as WriteApplication, WriteCard
    from src.errors import ConfigError
    from src.session import Delay, Presentation
    from helpers.theme import (
        THEME_BG, THEME_FIELD_BG, THEME_FG, THEME_FG_DIM, THEME_FONT_SMALL, ui,
    )
    from media import configure_images, stop_audio


# How long an intermediate wrong answer stays on screen before a retry.
RETRY_FEEDBACK_SECONDS = 0.7


class SessionRunner:
    """Show all four exercise screens and handle delays, retries and results."""

    def __init__(self, owner, session, preferences=None):
        self.owner = owner
        self.session = session
        self.preferences = preferences if preferences is not None else load_preferences()
        self.restrict_close = bool(
            self.preferences.get("restrict_exercise_close", False))
        configure_images(
            self.preferences.get("image_display_mode", "fit"),
            self.preferences.get("max_image_width", 0),
            self.preferences.get("max_image_height", 0),
        )

        self.events = list(session)
        # Warnings are added while the generator runs, so read them afterwards.
        self.warnings = list(session.warnings)
        self.index = 0
        self.current = None
        self.attempts = 0
        self._shown = []
        self.window = None
        self.app = None
        self._after = None
        self._after_widget = None
        self._timer = None
        self._timer_widget = None
        self._ended = False
        self.started_at = None
        self.cards_shown = 0
        self.cards_in_batch = 0
        self.session_batch = 0
        self.session_batches_total = None
        self._status_frame = None
        self._status_labels = {}
        self._status_job = None

    @property
    def has_work(self):
        return any(isinstance(event, Presentation) for event in self.events)

    def start(self):
        self.owner.withdraw()
        self._advance()

    # -- event flow ---------------------------------------------------------
    def _advance(self):
        if self._ended:
            return
        while self.index < len(self.events):
            event = self.events[self.index]
            self.index += 1
            if isinstance(event, Delay):
                self._wait(event.seconds)
                return
            if isinstance(event, Presentation):
                self.attempts = 0
                self._show(event)
                return
        self._end()

    def _show(self, presentation):
        self.current = presentation
        # The status time measures the current card, not the whole session.
        self.started_at = time.monotonic()
        exercise = presentation.exercise
        global_ = self.session.settings.global_
        batch_size = max(1, global_.batch_size)
        self.cards_in_batch = self.cards_shown % batch_size + 1
        self.session_batch = self.cards_shown // batch_size + 1
        self.session_batches_total = global_.batches
        self.cards_shown += len(presentation.card_ids)
        title = f"DeskCard - {exercise.title()}"
        listens = self.session.settings.exercises[exercise].prompt_listens
        quit_callback = self._blocked_quit if self.restrict_close else self.request_quit
        if exercise == "anki":
            self._open(title, lambda window: AnkiApplication(
                window,
                card=self._anki_card(presentation),
                warnings=presentation.warnings,
                on_grade=self._on_grade,
                score_deltas=self.preferences.get("score_deltas"),
                on_skip=self._close_and_advance,
                on_quit=quit_callback,
            ))
        elif exercise == "choose":
            self._open(title, lambda window: ChooseApplication(
                window,
                card=self._choose_card(presentation),
                warnings=presentation.warnings,
                prompt_listens=listens,
                on_result=self._on_result,
                on_skip=self._close_and_advance,
                on_quit=quit_callback,
            ))
        elif exercise == "connect":
            self._open(title, lambda window: ConnectApplication(
                window,
                card=self._connect_card(presentation),
                warnings=presentation.warnings,
                prompt_listens=listens,
                on_result=self._on_result,
                on_skip=self._close_and_advance,
                on_quit=quit_callback,
            ))
        elif exercise == "write":
            self._open(title, lambda window: WriteApplication(
                window,
                card=self._write_card(presentation),
                warnings=presentation.warnings,
                prompt_listens=listens,
                on_result=self._on_result,
                on_skip=self._close_and_advance,
                on_quit=quit_callback,
            ))
        else:
            self._close_and_advance()
            return
        self._shown.append(presentation)
        self._start_timer()

    def _open(self, title, factory):
        window = self._new_window(title)
        self.window = window
        try:
            self.app = factory(window)
            self._build_status()
            self._apply_app_preferences()
            apply_window_preferences(window, self.preferences, "exercise")
        except Exception:
            self.window = None
            window.destroy()
            raise
        self._focus(window)
        focus_input = getattr(self.app, "focus_input", None)
        if callable(focus_input):
            window.after_idle(focus_input)
        auto_play = getattr(self.app, "auto_play", None)
        if callable(auto_play):
            window.after_idle(auto_play)

    def _anki_card(self, presentation):
        spec = presentation.spec
        settings = self._settings()

        def side(face, sub_mode, front=False):
            # The back is only built into the reveal area, so ``after`` is
            # already satisfied when it becomes visible.
            if not front and sub_mode == "after":
                sub_mode = "always"
            return CardSide(
                face.text or "", face.sub or "",
                audio=face.audio, image=face.image,
                category=spec.category, direction=spec.direction,
                show_sub=sub_mode,
            )

        return AnkiCard(
            side(spec.front, settings.prompt_sub, front=True),
            side(spec.back, settings.answer_sub),
        )

    @staticmethod
    def _choose_card(presentation):
        spec = presentation.spec
        return ChooseCard(
            spec.prompt.text or "", spec.prompt.sub or "",
            spec.answer.text or "", spec.answer.sub or "",
            list(spec.choices), spec.correct,
            category=spec.category, direction=spec.direction,
            has_image=bool(spec.answer.image),
            prompt_audio=spec.prompt.audio, answer_audio=spec.answer.audio,
            prompt_image=spec.prompt.image, answer_image=spec.answer.image,
        )

    @staticmethod
    def _connect_card(presentation):
        pairs = [
            ConnectPair(
                pair.prompt.text or "", pair.prompt.sub or "",
                pair.answer.text or "", pair.answer.sub or "",
                category=pair.category, direction=pair.direction,
                prompt_audio=pair.prompt.audio, answer_audio=pair.answer.audio,
                prompt_image=pair.prompt.image, answer_image=pair.answer.image,
            )
            for pair in presentation.spec.pairs
        ]
        return ConnectCard(pairs)

    @staticmethod
    def _write_card(presentation):
        spec = presentation.spec
        return WriteCard(
            spec.prompt.text or "", spec.prompt.sub or "",
            spec.answer.text or "", spec.answer.sub or "",
            category=spec.category, direction=spec.direction,
            card_id=spec.card_id,
            prompt_audio=spec.prompt.audio, answer_audio=spec.answer.audio,
            prompt_image=spec.prompt.image, answer_image=spec.answer.image,
        )

    # -- results ------------------------------------------------------------
    def _on_grade(self, grade):
        presentation = self.current
        if presentation is None:
            self._advance()
            return
        self._clear_timer()
        self._commit_visible()
        try:
            self.session.record(presentation, grade.lower())
        except (ConfigError, OSError) as error:
            self._report_error(error)
        self._finalize()

    def _on_result(self, correct):
        """Handle a binary result from Choose, Connect or Write."""
        presentation = self.current
        if presentation is None:
            self._advance()
            return
        self._clear_timer()
        settings = self.session.settings.exercises[presentation.exercise]
        self.attempts += 1

        if correct:
            self._record_binary(True)
            self._finalize()
            return
        if settings.other_repeat or self.attempts < settings.other_attempts:
            self._retry()
            return
        self._record_binary(False)
        self._finalize()

    def _record_binary(self, correct):
        self._commit_visible()
        try:
            self.session.record_correct(self.current, correct)
        except (ConfigError, OSError) as error:
            self._report_error(error)

    def _commit_visible(self):
        self.session.commit_visible(self._shown)

    def _retry(self):
        if self.app is None or not hasattr(self.app, "retry"):
            self._close_and_advance()
            return
        self.app.attempt = self.attempts + 1
        show_retry = getattr(self.app, "show_retry", None)
        if callable(show_retry):
            show_retry()
            self._schedule(RETRY_FEEDBACK_SECONDS, self._retry_now)
        else:
            self._retry_now()

    def _retry_now(self):
        if self._ended or self.app is None:
            return
        stop_audio()
        self.app.retry()
        auto_play = getattr(self.app, "auto_play", None)
        if callable(auto_play) and self.window is not None:
            self.window.after_idle(auto_play)
        self._start_timer()

    def _finalize(self):
        if self.app is not None and hasattr(self.app, "freeze"):
            self.app.freeze("Saved · closing…")
        close_time = self._settings().other_close_time
        if close_time:
            self._schedule(close_time, self._close_and_advance)
        else:
            self._close_and_advance()

    def _settings(self):
        return self.session.settings.exercises[self.current.exercise]

    # -- answer timer -------------------------------------------------------
    def _start_timer(self):
        self._clear_timer()
        if self.window is None or self.current is None:
            return
        limit = self._settings().answer_time
        if not limit:
            return
        self._timer_widget = self.window
        self._timer = self.window.after(limit * 1000, self._on_timeout)

    def _on_timeout(self):
        self._clear_timer()
        if self.current is None or self.app is None:
            return
        if self.current.exercise == "anki":
            self._on_grade("impossible")
        else:
            reveal = getattr(self.app, "reveal_timeout", None)
            if callable(reveal):
                reveal()
            self._on_result(False)

    def _clear_timer(self):
        if self._timer is None:
            return
        widget = self._timer_widget
        try:
            if widget is not None:
                widget.after_cancel(self._timer)
        except tk.TclError:
            pass
        self._timer = None
        self._timer_widget = None

    def _close_and_advance(self):
        self._clear_timer()
        self._clear_after()
        self._destroy_window()
        self._advance()

    # -- silent delay -------------------------------------------------------
    def _wait(self, seconds):
        """Wait before the next card without showing a delay window."""
        self._clear_after()
        if seconds > 0:
            self._after_widget = self.owner
            self._after = self.owner.after(seconds * 1000, self._after_delay)
        else:
            self._after_delay()

    def _after_delay(self):
        self._clear_after()
        self._advance()

    # -- windows ------------------------------------------------------------
    def _new_window(self, title):
        window = tk.Toplevel(self.owner)
        window.title(title)
        # Not transient: the owner is withdrawn while the session runs, and a
        # transient child of a withdrawn window never becomes viewable.
        window.attributes(
            "-topmost", bool(self.preferences.get("exercise_always_on_top", True)))
        window.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self._apply_opacity(window)
        return window

    def _on_window_close(self):
        # The window manager sends this for the X button and for closing
        # keybinds; restricted sessions must stay open until the deck is done.
        if self.restrict_close:
            return
        # Once locked, the in-app Skip/Quit controls are inert; the X button
        # must not end the whole session while the close delay runs.
        if self.app is not None and getattr(self.app, "locked", False):
            return
        self.request_quit()

    def _clear_status(self):
        if self._status_job is not None:
            widget = self.window
            try:
                if widget is not None:
                    widget.after_cancel(self._status_job)
            except tk.TclError:
                pass
            self._status_job = None
        self._status_frame = None
        self._status_labels = {}

    def _build_status(self):
        self._clear_status()
        keys = [
            ("time_passed", "show_time_passed"),
            ("cards_in_batch", "show_cards_in_batch"),
            ("session_batches", "show_session_batches"),
        ]
        enabled = [key for key, pref in keys if self.preferences.get(pref)]
        if not enabled or self.window is None:
            return

        frame = tk.Frame(self.window, bg=THEME_BG)
        position = self.preferences.get("status_position", "top")
        anchor = getattr(self.app, "_header" if position == "top" else "_footer", None)
        options = dict(fill="x")
        if anchor is not None:
            options["before"] = anchor
        frame.pack(side="top" if position == "top" else "bottom", **options)

        self._status_frame = frame
        self._status_labels = {}
        for key in enabled:
            label = tk.Label(
                frame, text="", bg=THEME_BG, fg=THEME_FG,
                font=THEME_FONT_SMALL, anchor="w",
            )
            label.pack(side="left", padx=ui((12, 4)), pady=ui(2))
            self._status_labels[key] = label
        self._update_status()

    def _update_status(self):
        if not self._status_labels or self.window is None:
            return
        elapsed = 0
        if self.started_at is not None:
            elapsed = max(0, int(time.monotonic() - self.started_at))
        values = {
            "time_passed": f"time passed: {elapsed // 60:02d}:{elapsed % 60:02d}",
            "cards_in_batch": (
                f"cards in batch: {self.cards_in_batch}/{self.session.settings.global_.batch_size}"
            ),
            "session_batches": (
                f"session batches: {self.session_batch}/"
                f"{self.session_batches_total if self.session_batches_total else '∞'}"
            ),
        }
        for key, label in self._status_labels.items():
            label.configure(text=values[key])
        try:
            self._status_job = self.window.after(1000, self._update_status)
        except tk.TclError:
            self._status_job = None

    def _apply_app_preferences(self):
        quit_button = getattr(self.app, "_quit_button", None)
        if self.restrict_close and quit_button is not None:
            try:
                quit_button.configure(
                    state="disabled", bg=THEME_FIELD_BG, fg=THEME_FG_DIM,
                    disabledforeground=THEME_FG_DIM,
                    activebackground=THEME_FIELD_BG,
                    activeforeground=THEME_FG_DIM, cursor="arrow",
                )
            except tk.TclError:
                pass
        if self.preferences.get("show_skip_quit", True):
            return
        for attribute in ("_skip_button", "_quit_button"):
            button = getattr(self.app, attribute, None)
            if button is not None:
                try:
                    button.pack_forget()
                except tk.TclError:
                    pass

    def _apply_opacity(self, window):
        opacity = self.preferences.get("exercise_opacity", 100)
        value = max(0.1, min(1.0, opacity / 100))
        try:
            if window.winfo_exists():
                window.attributes("-alpha", value)
                # Some WMs only honour alpha once the window is fully mapped.
                window.after_idle(
                    lambda: window.winfo_exists()
                    and window.attributes("-alpha", value)
                )
        except tk.TclError:
            pass

    def _focus(self, window):
        window.update_idletasks()
        window.deiconify()
        window.lift()
        window.focus_force()
        # Alpha must be set after the window is mapped; a child of the
        # withdrawn owner silently ignores it before that point.
        self._apply_opacity(window)

    def _schedule(self, seconds, callback):
        # A later schedule supersedes any pending callback; never leave an
        # orphaned after id behind.
        self._clear_after()
        self._after_widget = self.window
        self._after = self.window.after(seconds * 1000, callback)

    def _clear_after(self):
        if self._after is None:
            return
        widget = self._after_widget
        try:
            if widget is not None:
                widget.after_cancel(self._after)
        except tk.TclError:
            pass
        self._after = None
        self._after_widget = None

    def _destroy_window(self):
        stop_audio()
        self._clear_status()
        window = self.window
        self.window = None
        self.app = None
        self.current = None
        if window is not None:
            remember_window_preferences(window, self.preferences, "exercise")
            save_preferences(self.preferences)
            try:
                window.destroy()
            except tk.TclError:
                pass

    # -- end ----------------------------------------------------------------
    def _end(self):
        self.quit()

    def _blocked_quit(self):
        """Keep exercise windows open while closing is restricted."""

    def request_quit(self):
        """User-initiated quit, which may ask for confirmation."""
        if self._ended:
            return
        if self.preferences.get("confirm_quit_reset", True):
            parent = self.window if self.window is not None else self.owner
            confirmed = messagebox.askyesno(
                "Quit session", "Quit the current study session?",
                parent=parent, icon="question", default="no",
            )
            if not confirmed:
                return
        self.quit()

    def quit(self):
        if self._ended:
            return
        self._ended = True
        self._clear_timer()
        self._clear_after()
        self._save_session()
        self._destroy_window()
        try:
            self.owner.destroy()
        except tk.TclError:
            pass

    def finish_quietly(self):
        """Save session state without closing the app (no cards to show)."""
        self._save_session()

    def _save_session(self):
        try:
            self.session.commit_visible(self._shown)
            self.session.finish()
        except (ConfigError, OSError) as error:
            self._report_error(error)

    @staticmethod
    def _report_error(error):
        try:
            messagebox.showerror("DeskCard", str(error))
        except tk.TclError:
            pass
