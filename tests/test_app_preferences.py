import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from src import app_preferences  # noqa: E402


class AppPreferencesTests(unittest.TestCase):
    def test_defaults_when_file_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            prefs = app_preferences.load_preferences(Path(directory) / "missing.json")
            self.assertEqual(prefs["exercise_opacity"], 100)
            self.assertFalse(prefs["remember_geometry"])
            self.assertFalse(prefs["remember_position"])
            self.assertTrue(prefs["show_skip_quit"])
            self.assertFalse(prefs["restrict_exercise_close"])
            self.assertTrue(prefs["confirm_quit_reset"])
            self.assertFalse(prefs["show_time_passed"])
            self.assertFalse(prefs["show_cards_in_batch"])
            self.assertFalse(prefs["show_session_batches"])
            self.assertEqual(prefs["status_position"], "top")
            self.assertEqual(prefs["score_deltas"]["easy"], 10)
            self.assertTrue(prefs["exercise_always_on_top"])
            self.assertFalse(prefs["auto_load_last_deck"])
            self.assertFalse(prefs["auto_load_last_settings"])
            self.assertEqual(prefs["last_deck"], "")
            self.assertEqual(prefs["last_settings"], "")
            self.assertEqual(prefs["image_display_mode"], "fit")
            self.assertEqual(prefs["max_image_width"], 0)
            self.assertEqual(prefs["max_image_height"], 0)
            self.assertEqual(prefs["font_scale"], 100)
            self.assertFalse(prefs["enable_debug_log"])
            self.assertTrue(prefs["count_all_directions"])
            self.assertEqual(
                prefs["default_global_settings"],
                {"delay": "1m", "session": "", "batch": "1", "jitter": "0"},
            )
            self.assertEqual(prefs["recent_decks"], [])

    def test_round_trip_and_clamping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prefs.json"
            prefs = app_preferences.load_preferences(path)
            prefs["exercise_opacity"] = 500
            prefs["confirm_quit_reset"] = False
            prefs["show_time_passed"] = True
            prefs["show_cards_in_batch"] = True
            prefs["show_session_batches"] = True
            prefs["status_position"] = "bottom"
            prefs["remember_geometry"] = True
            prefs["remember_position"] = True
            prefs["windows"]["exercise"] = {
                "width": 800, "height": 600, "x": 40, "y": 80,
            }
            app_preferences.save_preferences(prefs, path)
            loaded = app_preferences.load_preferences(path)
            self.assertEqual(loaded["exercise_opacity"], 100)
            self.assertFalse(loaded["confirm_quit_reset"])
            self.assertTrue(loaded["show_time_passed"])
            self.assertTrue(loaded["show_cards_in_batch"])
            self.assertTrue(loaded["show_session_batches"])
            self.assertEqual(loaded["status_position"], "bottom")
            self.assertTrue(loaded["remember_geometry"])
            self.assertTrue(loaded["remember_position"])
            self.assertEqual(loaded["windows"]["exercise"]["x"], 40)

            prefs.update({
                "exercise_always_on_top": False,
                "auto_load_last_deck": True,
                "auto_load_last_settings": True,
                "last_deck": "/tmp/deck.json",
                "last_settings": "/tmp/settings.json",
                "image_display_mode": "stretch",
                "max_image_width": 9999,
                "max_image_height": -5,
                "font_scale": 999,
            })
            app_preferences.save_preferences(prefs, path)
            loaded = app_preferences.load_preferences(path)
            self.assertFalse(loaded["exercise_always_on_top"])
            self.assertTrue(loaded["auto_load_last_deck"])
            self.assertTrue(loaded["auto_load_last_settings"])
            self.assertEqual(loaded["last_deck"], "/tmp/deck.json")
            self.assertEqual(loaded["last_settings"], "/tmp/settings.json")
            self.assertEqual(loaded["image_display_mode"], "stretch")
            self.assertEqual(loaded["max_image_width"], 4096)
            self.assertEqual(loaded["max_image_height"], 0)
            self.assertEqual(loaded["font_scale"], 200)
            app_preferences.clear_remembered_files(loaded)
            self.assertEqual(loaded["last_deck"], "")
            self.assertEqual(loaded["last_settings"], "")

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_hide_skip_quit_buttons(self):
        import tkinter as tk

        from src.ui.runner import SessionRunner

        class DummySession:
            warnings = ()

            def __iter__(self):
                return iter(())

        root = tk.Tk()
        root.withdraw()
        skip = tk.Button(root, text="Skip")
        quit_button = tk.Button(root, text="Quit")
        skip.pack()
        quit_button.pack()
        runner = SessionRunner(root, DummySession(), {
            "show_skip_quit": False, "exercise_opacity": 100,
            "windows": {},
        })
        runner.app = type("App", (), {
            "_skip_button": skip, "_quit_button": quit_button,
        })()
        runner._apply_app_preferences()
        self.assertEqual(skip.winfo_manager(), "")
        self.assertEqual(quit_button.winfo_manager(), "")
        root.destroy()

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_restrict_close_blocks_every_quit_path(self):
        import tkinter as tk
        from unittest.mock import patch

        from src.ui.helpers.theme import THEME_FIELD_BG
        from src.ui.runner import SessionRunner

        class DummySession:
            warnings = ()

            def __iter__(self):
                return iter(())

        root = tk.Tk()
        root.withdraw()
        skip = tk.Button(root, text="Skip")
        quit_button = tk.Button(root, text="Quit")
        runner = SessionRunner(root, DummySession(), {
            "show_skip_quit": True, "restrict_exercise_close": True,
            "exercise_opacity": 100, "windows": {},
        })
        runner.app = type("App", (), {
            "_skip_button": skip, "_quit_button": quit_button,
        })()
        runner._apply_app_preferences()
        self.assertEqual(quit_button.cget("state"), "disabled")
        self.assertEqual(quit_button.cget("bg"), THEME_FIELD_BG)
        self.assertEqual(skip.cget("state"), "normal")
        with patch.object(runner, "request_quit") as request:
            runner._on_window_close()
            runner._blocked_quit()
            request.assert_not_called()
        root.destroy()

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_request_quit_honours_confirmation_preference(self):
        import tkinter as tk
        from unittest.mock import patch

        from src.ui import runner as runner_module
        from src.ui.runner import SessionRunner

        class DummySession:
            warnings = ()

            def __iter__(self):
                return iter(())

            def commit_visible(self, shown):
                pass

            def finish(self):
                pass

        root = tk.Tk()
        root.withdraw()
        try:
            runner = SessionRunner(root, DummySession(), {
                "confirm_quit_reset": False, "exercise_opacity": 100,
                "windows": {},
            })
            with patch.object(runner_module.messagebox, "askyesno") as ask:
                runner.request_quit()
                ask.assert_not_called()
            self.assertTrue(runner._ended)
            try:
                root.destroy()
            except tk.TclError:
                pass

            root = tk.Tk()
            root.withdraw()
            runner = SessionRunner(root, DummySession(), {
                "confirm_quit_reset": True, "exercise_opacity": 100,
                "windows": {},
            })
            with patch.object(runner_module.messagebox, "askyesno", return_value=False):
                runner.request_quit()
            self.assertFalse(runner._ended)
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_status_bar_renders_selected_metrics(self):
        import tkinter as tk
        from types import SimpleNamespace

        from src.ui.runner import SessionRunner

        class DummySession:
            warnings = ()
            settings = SimpleNamespace(
                global_=SimpleNamespace(batch_size=5, batches=3)
            )

            def __iter__(self):
                return iter(())

        root = tk.Tk()
        root.withdraw()
        try:
            for position, anchor_name in (("top", "_header"), ("bottom", "_footer")):
                window = tk.Toplevel(root)
                header = tk.Frame(window)
                header.pack(side="top")
                footer = tk.Frame(window)
                footer.pack(side="bottom")
                app = type("App", (), {
                    "_header": header, "_footer": footer,
                })()
                runner = SessionRunner(root, DummySession(), {
                    "show_time_passed": True,
                    "show_cards_in_batch": True,
                    "show_session_batches": True,
                    "status_position": position,
                    "exercise_opacity": 100,
                    "windows": {},
                })
                runner.window = window
                runner.app = app
                runner.started_at = time.monotonic() - 12
                runner.cards_in_batch = 3
                runner.session_batch = 2
                runner.session_batches_total = 3
                runner._build_status()
                texts = [label.cget("text")
                         for label in runner._status_labels.values()]
                self.assertIn("time passed: 00:12", texts)
                self.assertIn("cards in batch: 3/5", texts)
                self.assertIn("session batches: 2/3", texts)
                anchor = getattr(app, anchor_name)
                slaves = window.pack_slaves()
                self.assertLess(
                    slaves.index(runner._status_frame), slaves.index(anchor)
                )
                runner._clear_status()
                window.destroy()
        finally:
            root.destroy()

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_settings_window_saves_preferences(self):
        import tkinter as tk

        from src.ui.preferences import show_preferences

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prefs.json"
            with patch.object(app_preferences, "PREFERENCES_PATH", path):
                root = tk.Tk()
                root.withdraw()

                def click_save():
                    def walk(widget):
                        if isinstance(widget, tk.Button) and widget.cget("text") == "Save":
                            widget.invoke()
                            return True
                        for child in widget.winfo_children():
                            if walk(child):
                                return True
                        return False
                    for child in root.winfo_children():
                        walk(child)

                root.after(50, click_save)
                show_preferences(root)
                root.destroy()

                loaded = app_preferences.load_preferences(path)
                self.assertEqual(loaded["exercise_opacity"], 100)
                self.assertIn("windows", loaded)

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_settings_window_reset_button(self):
        import tkinter as tk

        from src.ui.preferences import show_preferences

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prefs.json"
            path.write_text(json.dumps({
                "exercise_opacity": 30,
                "show_time_passed": True,
                "status_position": "bottom",
                "score_deltas": {"easy": 42},
            }), encoding="utf-8")
            with patch.object(app_preferences, "PREFERENCES_PATH", path):
                root = tk.Tk()
                root.withdraw()

                def click_reset_then_save():
                    buttons = {}

                    def walk(widget):
                        if isinstance(widget, tk.Button):
                            buttons[widget.cget("text")] = widget
                        for child in widget.winfo_children():
                            walk(child)

                    for child in root.winfo_children():
                        walk(child)
                    buttons["Reset"].invoke()
                    buttons["Save"].invoke()

                root.after(50, click_reset_then_save)
                show_preferences(root)
                root.destroy()

                loaded = app_preferences.load_preferences(path)
                self.assertEqual(loaded["exercise_opacity"], 100)
                self.assertFalse(loaded["show_time_passed"])
                self.assertEqual(loaded["status_position"], "top")
                self.assertEqual(loaded["score_deltas"]["easy"], 10)
                self.assertEqual(loaded["windows"], {})


class NewPreferenceBehaviourTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_auto_load_last_deck_and_settings(self):
        import tkinter as tk

        from src.ui.loader import Application

        with tempfile.TemporaryDirectory() as directory:
            deck = Path(directory) / "deck.json"
            deck.write_text(json.dumps({
                "first": {
                    "enabled": True,
                    "one": {"front": {"text": "Hello"}, "back": {"text": "Hi"}},
                },
            }), encoding="utf-8")
            settings = Path(directory) / "settings.json"
            settings.write_text(json.dumps({
                "global": {"delay": "7s"}, "exercises": {},
            }), encoding="utf-8")
            prefs_path = Path(directory) / "prefs.json"
            prefs = app_preferences.load_preferences(prefs_path)
            prefs.update({
                "auto_load_last_deck": True,
                "auto_load_last_settings": True,
                "last_deck": str(deck),
                "last_settings": str(settings),
            })
            app_preferences.save_preferences(prefs, prefs_path)

            with patch.object(app_preferences, "PREFERENCES_PATH", prefs_path):
                root = tk.Tk()
                root.withdraw()
                try:
                    app = Application(root)
                    self.assertEqual(app.desk_entry.get(), str(deck))
                    self.assertEqual(app.global_time_entry.get(), "7s")
                    self.assertEqual(app.settings_path, str(settings))
                    self.assertIsNotNone(app.config)
                finally:
                    root.destroy()

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_topmost_preference_controls_exercise_window(self):
        import tkinter as tk
        from unittest.mock import MagicMock, call

        from src.ui import runner as runner_module
        from src.ui.runner import SessionRunner

        class DummySession:
            warnings = ()

            def __iter__(self):
                return iter(())

        for enabled in (True, False):
            root = tk.Tk()
            root.withdraw()
            try:
                runner = SessionRunner(root, DummySession(), {
                    "exercise_always_on_top": enabled,
                    "exercise_opacity": 100, "windows": {},
                })
                window = MagicMock()
                with patch.object(runner_module.tk, "Toplevel", return_value=window):
                    self.assertIs(runner._new_window("DeskCard - test"), window)
                self.assertIn(call("-topmost", enabled),
                              window.attributes.call_args_list)
            finally:
                root.destroy()

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_font_scale_updates_existing_widgets(self):
        import tkinter as tk

        from src.ui.helpers.theme import apply_font_scale

        root = tk.Tk()
        root.withdraw()
        try:
            label = tk.Label(root, text="Hello DeskCard", font=("Segoe UI", 10))
            label.pack()
            root.update_idletasks()
            normal = label.winfo_reqwidth()
            apply_font_scale(root, 150)
            root.update_idletasks()
            large = label.winfo_reqwidth()
            apply_font_scale(root, 80)
            root.update_idletasks()
            small = label.winfo_reqwidth()
            self.assertGreater(large, normal)
            self.assertLess(small, normal)
        finally:
            apply_font_scale(root, 100)
            root.destroy()

    @unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
    def test_image_display_modes_and_global_cap(self):
        import tkinter as tk

        from PIL import Image

        from src.ui import media

        root = tk.Tk()
        root.withdraw()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            Image.new("RGB", (40, 30), "red").save(path)
            try:
                media.configure_images("fit", 0, 0)
                photo = media.load_image(path, (20, 20))
                self.assertEqual((photo.width(), photo.height()), (20, 15))

                media.configure_images("stretch", 0, 0)
                photo = media.load_image(path, (20, 20))
                self.assertEqual((photo.width(), photo.height()), (20, 20))

                media.configure_images("original", 0, 0)
                photo = media.load_image(path, (20, 20))
                self.assertEqual((photo.width(), photo.height()), (20, 20))

                media.configure_images("fit", 8, 0)
                photo = media.load_image(path, (20, 20))
                self.assertEqual((photo.width(), photo.height()), (8, 6))
            finally:
                media.configure_images("fit", 0, 0)
        root.destroy()


class FileAndDirectionPreferenceTests(unittest.TestCase):
    def test_validation_of_new_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prefs.json"
            path.write_text(json.dumps({
                "enable_debug_log": "yes",
                "count_all_directions": False,
                "default_global_settings": {"delay": "5s", "batch": "3", "extra": "x"},
                "recent_decks": ["a", "a", "b"] + [f"p{i}" for i in range(12)],
            }), encoding="utf-8")
            prefs = app_preferences.load_preferences(path)
            self.assertFalse(prefs["enable_debug_log"])
            self.assertFalse(prefs["count_all_directions"])
            self.assertEqual(prefs["default_global_settings"]["delay"], "5s")
            self.assertEqual(prefs["default_global_settings"]["batch"], "3")
            self.assertEqual(prefs["default_global_settings"]["jitter"], "0")
            self.assertNotIn("extra", prefs["default_global_settings"])
            self.assertEqual(prefs["recent_decks"][:3], ["a", "b", "p0"])
            self.assertEqual(len(prefs["recent_decks"]), 10)

    def test_recent_deck_helpers(self):
        prefs = {"recent_decks": ["b", "c"]}
        app_preferences.remember_recent_deck(prefs, "a")
        self.assertEqual(prefs["recent_decks"], ["a", "b", "c"])
        app_preferences.remember_recent_deck(prefs, "a")
        self.assertEqual(prefs["recent_decks"], ["a", "b", "c"])
        app_preferences.clear_remembered_files(prefs)
        self.assertEqual(prefs["recent_decks"], [])
        self.assertEqual(prefs["last_deck"], "")
        self.assertEqual(prefs["last_settings"], "")

    def test_debug_log_file(self):
        from src import debug_log

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prefs.json"
            with patch.object(app_preferences, "PREFERENCES_PATH", path):
                try:
                    debug_log.configure_debug_log(True)
                    debug_log.log_debug("probe line")
                    log_path = path.parent / "debug.log"
                    self.assertTrue(log_path.is_file())
                    self.assertIn("probe line", log_path.read_text(encoding="utf-8"))
                finally:
                    debug_log.configure_debug_log(False)


class ScrollWheelTests(unittest.TestCase):
    def test_string_widget_from_native_dialog_is_ignored(self):
        from types import SimpleNamespace

        from src.ui.loader import _scroll_wheel

        event = SimpleNamespace(widget=".tkfilefilter", x_root=10, y_root=10,
                                num=0, delta=-120, state=0)
        _scroll_wheel(event)


class UiScaleMathTests(unittest.TestCase):
    def test_ui_converts_design_pixels_at_current_scale(self):
        from src.ui.helpers import theme

        with patch.object(theme, "UI_SCALE", 2.0):
            self.assertEqual(theme.ui(10), 20)
            self.assertEqual(theme.ui((0, 6)), (0, 12))
            self.assertEqual(theme.ui(0), 0)
            self.assertEqual(theme.ui(1), 2)

    def test_scaled_number_round_trips_both_directions(self):
        from src.ui.helpers import theme

        self.assertEqual(theme._scaled_number(20, 0.5), 10)
        self.assertEqual(theme._scaled_number("0 6", 2.0), (0, 12))
        self.assertEqual(theme._scaled_number(0, 2.0), 0)


if __name__ == "__main__":
    unittest.main()
