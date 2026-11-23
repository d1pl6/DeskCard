import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from src.ui.anki import Application as AnkiApplication, AnkiCard, CardSide  # noqa: E402
from src.ui.choose import Application as ChooseApplication, ChooseCard  # noqa: E402
from src.ui.connect import (  # noqa: E402
    Application as ConnectApplication, ConnectCard, ConnectPair,
)
from src.ui.write import Application as WriteApplication, WriteCard  # noqa: E402


class WrapLengthTests(unittest.TestCase):
    def test_wrap_helpers_follow_font_scale(self):
        helpers = (
            ("anki", lambda width: AnkiApplication._wraplength(
                SimpleNamespace(_window_width=width))),
            ("connect", lambda width: ConnectApplication._wraplength(
                SimpleNamespace(_window_width=width))),
            ("choose choices", lambda width: ChooseApplication._choice_wraplength(
                SimpleNamespace(_window_width=width), 2)),
            ("choose answer", lambda width: ChooseApplication._answer_wraplength(
                SimpleNamespace(_window_width=width), False)),
            ("write prompt", lambda width: WriteApplication._prompt_wraplength(
                SimpleNamespace(_window_width=width))),
            ("write warning", lambda width: WriteApplication._warning_wraplength(
                SimpleNamespace(_window_width=width))),
            ("write result", lambda width: WriteApplication._result_wraplength(
                SimpleNamespace(_window_width=width))),
        )
        for name, helper in helpers:
            with self.subTest(name):
                with patch("src.ui.helpers.theme.UI_SCALE", 1.0):
                    base = helper(3000)
                with patch("src.ui.helpers.theme.UI_SCALE", 2.0):
                    scaled = helper(6000)
                self.assertEqual(scaled, 2 * base)


def label_texts(widget):
    import tkinter as tk

    found = []
    if isinstance(widget, tk.Label):
        found.append(widget.cget("text"))
    for child in widget.winfo_children():
        found.extend(label_texts(child))
    return found


@unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
class ExerciseFeedbackTests(unittest.TestCase):
    def choose_card(self, choices=None):
        return ChooseCard("Prompt", "", "Right answer", "",
                          choices or ["Wrong pick", "Right answer"], 1)

    def test_choose_retry_hides_the_correct_answer(self):
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            app = ChooseApplication(
                root, card=self.choose_card(), on_result=lambda _correct: None)
            app._pick(0)
            app._confirm()
            app.show_retry()
            texts = label_texts(app._answer_holder)
            self.assertIn("TRY AGAIN", texts)
            self.assertNotIn("CORRECT ANSWER", texts)
            self.assertNotIn("Right answer", texts)

            app.retry()
            self.assertFalse(app.revealed)
            self.assertFalse(app._answer_holder.winfo_manager())
        finally:
            root.destroy()

    def test_write_confirm_tracks_the_cleared_entry_after_retry(self):
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            app = WriteApplication(
                root, card=WriteCard("Prompt", answer="answer"),
                on_result=lambda _correct: None)
            for advance in (app.retry, app._continue):
                app._entry.delete(0, tk.END)
                app._entry.insert(0, "answer")
                app._confirm()
                advance()
                self.assertEqual(app._entry.get(), "")
                self.assertEqual(app._confirm_button.cget("state"), "disabled")
        finally:
            root.destroy()

    def test_standalone_result_sheets_wait_for_enter(self):
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            choose = ChooseApplication(root, card=self.choose_card())
            choose._pick(0)
            choose._confirm()
            self.assertTrue(choose.revealed)
            self.assertTrue(choose._answer_holder.winfo_manager())
            choose._enter()
            self.assertFalse(choose.revealed)
        finally:
            root.destroy()

        root = tk.Tk()
        root.withdraw()
        try:
            write = WriteApplication(root, card=WriteCard("Prompt", answer="answer"))
            write._entry.insert(0, "guess")
            write._confirm()
            self.assertTrue(write.revealed)
            self.assertTrue(write._result_panel.winfo_manager())
            write._enter()
            self.assertFalse(write.revealed)
        finally:
            root.destroy()

    def test_small_resize_steps_schedule_rewrapping(self):
        import tkinter as tk

        cases = (
            ("anki", lambda root: AnkiApplication(
                root, card=AnkiCard(CardSide("Front"), CardSide("Back")))),
            ("choose", lambda root: ChooseApplication(
                root, card=self.choose_card())),
            ("connect", lambda root: ConnectApplication(
                root, card=ConnectCard([
                    ConnectPair("One", answer="Uno"),
                    ConnectPair("Two", answer="Dos"),
                ]))),
            ("write", lambda root: WriteApplication(
                root, card=WriteCard("Prompt", answer="answer"))),
        )
        for name, factory in cases:
            with self.subTest(name):
                root = tk.Tk()
                root.withdraw()
                try:
                    app = factory(root)
                    for step in range(20):
                        app._on_configure(SimpleNamespace(
                            widget=root, width=app._window_width + 5 * (step + 1)))
                    self.assertIsNotNone(app._resize_job)
                finally:
                    if app._resize_job is not None:
                        root.after_cancel(app._resize_job)
                    root.destroy()

    def test_choose_retry_restores_choice_scroll(self):
        import tkinter as tk

        root = tk.Tk()
        root.geometry("900x700+0+0")
        root.update()
        try:
            choices = [f"Choice {index}" for index in range(30)]
            app = ChooseApplication(
                root, card=self.choose_card(choices), on_result=lambda _correct: None)
            root.update()
            app._pick(0)
            app._choice_fraction = 0.1
            app._choice_scroll.canvas.yview_moveto(0.1)
            app._confirm()
            app.show_retry()
            app.retry()
            root.update()
            self.assertAlmostEqual(app._choice_fraction, 0.1)
            self.assertAlmostEqual(
                app._choice_scroll.canvas.yview()[0], 0.1, delta=0.02)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
