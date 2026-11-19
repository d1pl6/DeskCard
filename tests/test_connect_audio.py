import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from src.ui.connect import Application, ConnectCard, ConnectPair  # noqa: E402


@unittest.skipUnless(os.environ.get("DISPLAY"), "needs a Tk display")
class ConnectAudioTests(unittest.TestCase):
    def test_each_pair_has_its_own_prompt_replay_budget(self):
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        card = ConnectCard([
            ConnectPair("One", prompt_audio="/tmp/one.wav",
                        answer="Uno", answer_audio="/tmp/uno.wav"),
            ConnectPair("Two", prompt_audio="/tmp/two.wav",
                        answer="Dos", answer_audio="/tmp/dos.wav"),
        ])
        try:
            with patch("src.ui.connect.play_audio") as play:
                app = Application(root, card=card, prompt_listens=0)
                play.reset_mock()

                app.auto_play()
                self.assertEqual(play.call_args.args[0], "/tmp/one.wav")

                app._play_prompt("/tmp/two.wav", "p1")
                self.assertEqual(play.call_args.args[0], "/tmp/two.wav")
                self.assertEqual(play.call_count, 2)

                app._play_prompt("/tmp/one.wav", "p0")
                self.assertEqual(play.call_count, 2)

                app._play_answer("/tmp/uno.wav")
                self.assertEqual(play.call_count, 3)
                self.assertEqual(play.call_args.args[0], "/tmp/uno.wav")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
