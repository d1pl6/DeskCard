import os
import tempfile
import unittest
import wave
from pathlib import Path

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from src.ui.media import load_image, play_audio, stop_audio  # noqa: E402


class MediaTests(unittest.TestCase):
    def test_play_audio_and_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tone.wav"
            with wave.open(str(path), "wb") as sound:
                sound.setnchannels(1)
                sound.setsampwidth(1)
                sound.setframerate(8000)
                sound.writeframes(b"\x80" * 800)
            self.assertTrue(play_audio(path))
            stop_audio()

    def test_play_audio_reports_decode_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.wav"
            path.write_text("not audio", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                play_audio(path)

    def test_load_image_scales_and_caches(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")
        if not os.environ.get("DISPLAY"):
            self.skipTest("no display for Tk PhotoImage")
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "card.png"
                Image.new("RGB", (800, 600), "red").save(path)
                photo = load_image(path, (200, 120))
                self.assertIsNotNone(photo)
                self.assertIs(photo, load_image(path, (200, 120)))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
