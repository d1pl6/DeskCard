import os
import unittest

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from src.ui.helpers.tooltips import (  # noqa: E402
    APP_SETTING_TOOLTIPS, SETTING_TOOLTIPS,
)


def tooltip_texts(widget):
    found = []
    text = getattr(widget, "_tooltip_text", None)
    if text:
        found.append(text)
    for child in widget.winfo_children():
        found.extend(tooltip_texts(child))
    return found


class TooltipTests(unittest.TestCase):
    def test_every_setting_tooltip_has_text(self):
        for key, text in SETTING_TOOLTIPS.items():
            self.assertIsInstance(text, str, f"non-string tooltip: {key}")
            self.assertTrue(text.strip(), f"empty tooltip: {key}")

    def test_every_app_setting_tooltip_has_text(self):
        for key, text in APP_SETTING_TOOLTIPS.items():
            self.assertIsInstance(text, str, f"non-string tooltip: {key}")
            self.assertTrue(text.strip(), f"empty tooltip: {key}")

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_settings_ui_binds_every_tooltip(self):
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

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_preferences_ui_binds_every_app_tooltip(self):
        import tkinter as tk

        from src.ui.preferences import show_preferences

        root = tk.Tk()
        root.withdraw()
        collected = {}

        def close_dialog():
            collected["texts"] = tooltip_texts(root)
            for child in root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.destroy()

        try:
            root.after(50, close_dialog)
            show_preferences(root)
            bound = set(collected["texts"])
            missing = set(APP_SETTING_TOOLTIPS.values()) - bound
            self.assertEqual(missing, set())
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
