import os
import unittest

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from src.ui.anki import AnkiCard, CardSide  # noqa: E402
from src.ui.anki import Application as AnkiApplication  # noqa: E402
from src.ui.loader import Application as LoaderApplication  # noqa: E402


def labels_named(widget, text):
    found = []
    if isinstance(widget, __import__("tkinter").Label) and widget.cget("text") == text:
        found.append(widget)
    for child in widget.winfo_children():
        found.extend(labels_named(child, text))
    return found


@unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
class AnkiSettingsTests(unittest.TestCase):
    def test_loader_has_content_and_sub_fields(self):
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            app = LoaderApplication(root)
            self.assertEqual(getattr(app, "anki_prompt_type_text_only_var").get(), 1)
            self.assertEqual(getattr(app, "anki_prompt_sub_var").get(), "always")
            self.assertEqual(getattr(app, "anki_answer_prompt_text_only_var").get(), 1)
            self.assertEqual(getattr(app, "anki_answer_sub_var").get(), "after")
            data = app._collect_settings()
            self.assertEqual(
                data["exercises"]["anki"]["settings"]["prompt_type"], ["text_only"]
            )
            self.assertEqual(
                data["exercises"]["anki"]["settings"]["answer_prompt"], ["text_only"]
            )
        finally:
            root.destroy()

    def test_sub_modes_control_visibility(self):
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        card = AnkiCard(
            CardSide("Front", "front sub", show_sub="after"),
            CardSide("Back", "answer sub", show_sub="never"),
        )
        try:
            app = AnkiApplication(root, card=card)
            front = labels_named(root, "front sub")[0]
            self.assertFalse(front.winfo_manager())
            self.assertEqual(labels_named(root, "answer sub"), [])

            app._reveal()
            root.update()
            self.assertTrue(front.winfo_manager())
            self.assertEqual(labels_named(root, "answer sub"), [])
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
