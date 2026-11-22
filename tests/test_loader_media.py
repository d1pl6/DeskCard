import os
import unittest

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from src.ui.helpers.tooltips import (  # noqa: E402
    CONTENT_LOCK_TOOLTIPS, content_lock_tooltip,
)
from src.ui.loader import CONTENT_MEDIA, broken_media  # noqa: E402


class BrokenMediaTests(unittest.TestCase):
    def test_extracts_media_errors_from_deck_warnings(self):
        warnings = [
            "deck.json: c/1/back/audio: no such file: missing.mp3",
            "deck.json: c/1/front/image: image not found - error",
            "deck.json: c/2/back: no text; the answer cannot be shown in v1 exercises",
            "deck.json: c/3: has neither text, audio nor image, skipping the card",
            "deck.json: c/4: negative, treating as 0",
        ]
        self.assertEqual(
            broken_media(warnings),
            {"text": True, "audio": True, "image": True},
        )
        self.assertEqual(
            broken_media(["deck.json: c/1/front/sub: must be a string"]),
            {"text": False, "audio": False, "image": False},
        )

    def test_content_options_declare_their_media(self):
        self.assertEqual(CONTENT_MEDIA["text_only"], ("text",))
        self.assertEqual(CONTENT_MEDIA["audio_image"], ("audio", "image"))
        self.assertEqual(CONTENT_MEDIA["all"], ("text", "audio", "image"))

    def test_lock_tooltip_names_each_reason(self):
        self.assertEqual(
            content_lock_tooltip("image", library_missing=True, deck_error=False),
            f"Image option is locked: {CONTENT_LOCK_TOOLTIPS['image_missing']}.",
        )
        message = content_lock_tooltip(
            "audio", library_missing=True, deck_error=True,
        )
        self.assertIn(CONTENT_LOCK_TOOLTIPS["audio_missing"], message)
        self.assertIn(CONTENT_LOCK_TOOLTIPS["audio_deck"], message)


if __name__ == "__main__":
    unittest.main()
