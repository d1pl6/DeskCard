import os
import unittest
from pathlib import Path

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from src.ui.helpers.tooltips import SETTING_TOOLTIPS  # noqa: E402


def tooltip_texts(widget):
    found = []
    text = getattr(widget, "_tooltip_text", None)
    if text:
        found.append(text)
    for child in widget.winfo_children():
        found.extend(tooltip_texts(child))
    return found


class TooltipTests(unittest.TestCase):
    def test_readme_tooltips_are_all_defined(self):
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        for text in SETTING_TOOLTIPS.values():
            self.assertIn(text, readme, f"missing from README: {text}")

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_settings_ui_binds_every_readme_tooltip(self):
        import tkinter as tk

        from src.ui.loader import Application

        root = tk.Tk()
        root.withdraw()
        try:
            app = Application(root)
            bound = set(tooltip_texts(root))
            missing = set(SETTING_TOOLTIPS.values()) - bound
            self.assertEqual(missing, set())
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
