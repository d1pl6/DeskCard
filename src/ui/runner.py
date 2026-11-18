"""Drive a session by showing exercise windows one card at a time.

The runner owns no study rules: those live in :mod:`src.session`. It consumes
the engine's ``Delay`` and ``Presentation`` events, feeds each exercise screen
with real card data, records results, and quits when the session ends.
"""

import tkinter as tk
from tkinter import messagebox

try:  # imported as ui.runner
    from .anki import AnkiCard, Application as AnkiApplication, CardSide
    from .choose import Application as ChooseApplication, ChooseCard
    from .connect import Application as ConnectApplication, ConnectCard, ConnectPair
    from .write import Application as WriteApplication, WriteCard
    from ..errors import ConfigError
    from ..session import Delay, Presentation
except ImportError:  # started as a script from src/ui
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from anki import AnkiCard, Application as AnkiApplication, CardSide
    from choose import Application as ChooseApplication, ChooseCard
    from connect import Application as ConnectApplication, ConnectCard, ConnectPair
    from write import Application as WriteApplication, WriteCard
    from src.errors import ConfigError
    from src.session import Delay, Presentation


# How long an intermediate wrong answer stays on screen before a retry.
RETRY_FEEDBACK_SECONDS = 0.7


class SessionRunner:
    """Show all four exercise screens and handle delays, retries and results."""

    def __init__(self, owner, session):
        self.owner = owner
        self.session = session

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
        exercise = presentation.exercise
        title = f"DeskCard - {exercise.title()}"
        if exercise == "anki":
            self._open(title, lambda window: AnkiApplication(
                window,
                card=self._anki_card(presentation),
                warnings=presentation.warnings,
                on_grade=self._on_grade,
                on_skip=self._close_and_advance,
                on_quit=self.quit,
            ))
        elif exercise == "choose":
            self._open(title, lambda window: ChooseApplication(
                window,
                card=self._choose_card(presentation),
                warnings=presentation.warnings,
                on_result=self._on_result,
                on_skip=self._close_and_advance,
                on_quit=self.quit,
            ))
        elif exercise == "connect":
            self._open(title, lambda window: ConnectApplication(
                window,
                card=self._connect_card(presentation),
                warnings=presentation.warnings,
                on_result=self._on_result,
                on_skip=self._close_and_advance,
                on_quit=self.quit,
            ))
        elif exercise == "write":
            self._open(title, lambda window: WriteApplication(
                window,
                card=self._write_card(presentation),
                warnings=presentation.warnings,
                on_result=self._on_result,
                on_skip=self._close_and_advance,
                on_quit=self.quit,
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
        except Exception:
            self.window = None
            window.destroy()
            raise
        self._focus(window)
        focus_input = getattr(self.app, "focus_input", None)
        if callable(focus_input):
            window.after_idle(focus_input)

    @staticmethod
    def _anki_card(presentation):
        spec = presentation.spec

        def side(face):
            return CardSide(
                face.text or "", face.sub or "",
                audio=face.audio, image=face.image,
                category=spec.category, direction=spec.direction,
            )

        return AnkiCard(side(spec.front), side(spec.back))

    @staticmethod
    def _choose_card(presentation):
        spec = presentation.spec
        return ChooseCard(
            spec.prompt.text or "", spec.prompt.sub or "",
            spec.answer.text or "", spec.answer.sub or "",
            list(spec.choices), spec.correct,
            category=spec.category, direction=spec.direction,
            has_image=bool(spec.answer.image),
        )

    @staticmethod
    def _connect_card(presentation):
        pairs = [
            ConnectPair(
                pair.prompt.text or "", pair.prompt.sub or "",
                pair.answer.text or "", pair.answer.sub or "",
                category=pair.category, direction=pair.direction,
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
        self.app.retry()
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
        window.attributes("-topmost", True)
        window.protocol("WM_DELETE_WINDOW", self._on_window_close)
        return window

    def _on_window_close(self):
        # Once locked, the in-app Skip/Quit controls are inert; the X button
        # must not end the whole session while the close delay runs.
        if self.app is not None and getattr(self.app, "locked", False):
            return
        self.quit()

    @staticmethod
    def _focus(window):
        window.update_idletasks()
        window.deiconify()
        window.lift()
        window.focus_force()

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
        window = self.window
        self.window = None
        self.app = None
        self.current = None
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

    # -- end ----------------------------------------------------------------
    def _end(self):
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
