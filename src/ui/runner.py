"""Drive a session by showing exercise windows one card at a time.

The runner owns no study rules: those live in :mod:`src.session`. It consumes
the engine's ``Delay`` and ``Presentation`` events, feeds Anki cards to the UI,
records grades, and quits when the session ends.
"""

import tkinter as tk
from tkinter import messagebox

try:  # imported as ui.runner
    from .anki import AnkiCard, Application as AnkiApplication, CardSide
    from ..errors import ConfigError
    from ..session import Delay, Presentation
except ImportError:  # started as a script from src/ui
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from anki import AnkiCard, Application as AnkiApplication, CardSide
    from src.errors import ConfigError
    from src.session import Delay, Presentation


class SessionRunner:
    """Show the Anki slice of a session and handle its delays and results."""

    def __init__(self, owner, session):
        self.owner = owner
        self.session = session

        events = list(session)
        # Warning for a short deck is appended while the generator runs.
        self.warnings = list(session.warnings)
        skipped = sorted({
            event.exercise for event in events
            if isinstance(event, Presentation) and event.exercise != "anki"
        })
        self.skipped = skipped
        if skipped:
            self.warnings.append(
                "only Anki is wired up in this release; skipped: "
                + ", ".join(skipped)
            )
        self.events = self._filter_events(events)
        self.index = 0
        self.current = None
        self._shown = []
        self.window = None
        self.app = None
        self._after = None
        self._after_widget = None
        self._ended = False

    @staticmethod
    def _filter_events(events):
        """Keep Anki cards and only the delays that introduce them.

        Non-Anki presentations are skipped in this release. Keeping delays from
        their batches would leave silent waits with no card to show; unknown
        event kinds are ignored rather than assuming an ``exercise`` field.
        """
        kept = []
        delay = None
        for event in events:
            if isinstance(event, Delay):
                # A still-pending delay belongs to a batch with no Anki card.
                delay = event
            elif getattr(event, "exercise", None) == "anki":
                if delay is not None:
                    kept.append(delay)
                    delay = None
                kept.append(event)
        return kept

    @property
    def has_work(self):
        return any(
            isinstance(event, Presentation) for event in self.events
        )

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
            self._show_anki(event)
            return
        self._end()

    def _show_anki(self, presentation):
        self.current = presentation
        self._shown.append(presentation)
        window = self._new_window("DeskCard - Anki")
        self.window = window
        self.app = AnkiApplication(
            window,
            card=self._anki_card(presentation),
            warnings=presentation.warnings,
            on_grade=self._on_grade,
            on_skip=self._close_and_advance,
            on_quit=self.quit,
        )
        self._focus(window)

    @staticmethod
    def _anki_card(presentation):
        spec = presentation.spec
        category, direction = spec.category, spec.direction

        def side(face):
            return CardSide(
                face.text or "", face.sub or "",
                audio=face.audio, image=face.image,
                category=category, direction=direction,
            )

        return AnkiCard(side(spec.front), side(spec.back))

    def _on_grade(self, grade):
        presentation = self.current
        if presentation is None:
            self._advance()
            return
        self.session.commit_visible(self._shown)
        try:
            self.session.record(presentation, grade.lower())
        except (ConfigError, OSError) as error:
            self._report_error(error)
        close_time = self.session.settings.exercises["anki"].other_close_time
        if close_time:
            self.app.freeze("Saved · closing…")
            self._schedule(close_time, self._close_and_advance)
        else:
            self._close_and_advance()

    def _close_and_advance(self):
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
        window.protocol("WM_DELETE_WINDOW", self.quit)
        return window

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
