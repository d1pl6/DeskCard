"""Headless tests for the session engine (run from the repository root)."""

import json
import random
import tempfile
import unittest
from pathlib import Path

from src.config.loader import load_config
from src.errors import SettingsError
from src.session import Presentation, Session, parse_score_filter, parse_time


DECK = {
    "first": {
        "enabled": True,
        "one": {
            "front": {"text": "Hello", "audio": "hello.mp3"},
            "back": {"text": "Hola"},
            "score": 10,
            "normal": 5,
            "reverse": 5,
        },
        "two": {
            "front": {"text": "Bye"},
            "back": {"text": "Adiós"},
            "score": 50,
            "normal": 1,
            "reverse": 2,
        },
    },
    "second": {
        "enabled": False,
        "three": {
            "front": {"text": "Cat"},
            "back": {"text": "Kočka"},
            "score": 20,
        },
    },
}


def write_deck(directory):
    path = Path(directory) / "deck.json"
    path.write_text(json.dumps(DECK), encoding="utf-8")
    return path


def settings(**overrides):
    base = {
        "global": {"delay": "0", "session": "", "batch": "1", "jitter": "0"},
        "exercises": {
            "anki": {
                "enabled": True,
                "settings": {
                    "prompt_type": ["text_only"],
                    "answer_prompt": ["text_only"],
                    "other_direction": "normal",
                    "other_score": "0-100",
                },
            },
        },
    }
    base.update(overrides)
    return base


class SettingsTests(unittest.TestCase):
    def test_time_strings(self):
        self.assertEqual(parse_time("1h5m30s", "x", empty=0), 3930)
        self.assertEqual(parse_time("61m30s", "x", empty=0), 3690)
        self.assertEqual(parse_time("90s", "x", empty=0), 90)
        self.assertEqual(parse_time("90", "x", empty=0), 90)
        self.assertIsNone(parse_time("", "x", empty=None))
        for raw in ("90 S", "90M", "1m1h", "abc"):
            with self.assertRaises(SettingsError):
                parse_time(raw, "x", empty=0)

    def test_score_filter(self):
        self.assertEqual(parse_score_filter("55", "x"), (55, 55))
        self.assertEqual(parse_score_filter("0-99", "x"), (0, 99))
        for raw in ("", "55-*", "44-12", "abc", "200", "0-49,80-99"):
            with self.assertRaises(SettingsError):
                parse_score_filter(raw, "x")

    def test_repeat_blocks_max_attempts(self):
        data = settings()
        data["exercises"]["anki"]["settings"].update(
            {"other_repeat": True, "other_attempts": "3"}
        )
        with self.assertRaises(SettingsError):
            Session(load_config(write_deck(tempfile.mkdtemp())), data, save_categories=False)


class LoaderTests(unittest.TestCase):
    def test_disabled_cards_stay_in_memory(self):
        config = load_config(write_deck(tempfile.mkdtemp()))
        self.assertEqual(len(config.cards), 3)
        self.assertEqual(len(config.active_cards()), 2)
        self.assertIn("three", config.cards)
        self.assertNotIn("three", config.active_cards())


class SessionTests(unittest.TestCase):
    def test_delay_comes_before_each_batch(self):
        data = settings()
        data["global"].update({"session": "2", "batch": "1"})
        session = Session(
            load_config(write_deck(tempfile.mkdtemp())), data,
            rng=random.Random(1), save_categories=False,
        )
        events = list(session)
        self.assertEqual(
            [type(event).__name__ for event in events],
            ["Delay", "Presentation", "Delay", "Presentation"],
        )

    def test_result_updates_and_saves_deck(self):
        path = write_deck(tempfile.mkdtemp())
        config = load_config(path)
        session = Session(config, settings(), rng=random.Random(1), save_categories=False)
        presentation = next(
            event for event in session if hasattr(event, "spec")
        )
        session.record(presentation, "easy")
        self.assertEqual(config.card("one").score, 20)
        self.assertEqual(config.card("one").count("easy"), 1)
        self.assertIsNotNone(config.card("one").last_reviewed)
        self.assertEqual(json.loads(path.read_text())["first"]["one"]["score"], 20)

    def test_direction_counter_only_in_random(self):
        data = settings()
        data["exercises"]["anki"]["settings"]["other_direction"] = "random"
        config = load_config(write_deck(tempfile.mkdtemp()))
        session = Session(config, data, rng=random.Random(1), save_categories=False)
        before = {key: (card.normal, card.reverse)
                  for key, card in config.cards.items()}
        presentation = next(
            event for event in session if hasattr(event, "spec")
        )
        card_id = presentation.card_ids[0]
        after = {key: (card.normal, card.reverse)
                 for key, card in config.cards.items()}
        changed = [key for key in before if before[key] != after[key]]
        self.assertEqual(changed, [card_id])
        self.assertEqual(sum(after[card_id]) - sum(before[card_id]), 1)

        forced = settings()
        config = load_config(write_deck(tempfile.mkdtemp()))
        session = Session(config, forced, rng=random.Random(1), save_categories=False)
        list(session)
        self.assertEqual(config.card("one").normal, 5)
        self.assertEqual(config.card("one").reverse, 5)

    def test_score_filter_skips_cards(self):
        data = settings()
        data["exercises"]["anki"]["settings"]["other_score"] = "50-100"
        config = load_config(write_deck(tempfile.mkdtemp()))
        session = Session(config, data, rng=random.Random(1), save_categories=False)
        cards = [event.card_ids[0] for event in session if hasattr(event, "spec")]
        self.assertEqual(cards, ["two"])

    def test_anki_orders_by_lowest_score(self):
        deck = {
            "example": {
                "enabled": True,
                "high": {
                    "front": {"text": "High"},
                    "back": {"text": "High back"},
                    "score": 90,
                },
                "low": {
                    "front": {"text": "Low"},
                    "back": {"text": "Low back"},
                    "score": 5,
                },
                "mid": {
                    "front": {"text": "Mid"},
                    "back": {"text": "Mid back"},
                    "score": 40,
                },
            },
        }
        path = Path(tempfile.mkdtemp()) / "deck.json"
        path.write_text(json.dumps(deck), encoding="utf-8")
        session = Session(
            load_config(path), settings(), rng=random.Random(1), save_categories=False,
        )
        cards = [event.card_ids[0] for event in session if hasattr(event, "spec")]
        self.assertEqual(cards, ["low", "mid", "high"])

    def test_all_exercises_order_by_lowest_score(self):
        deck = {
            "example": {
                "enabled": True,
                "high": {
                    "front": {"text": "High"},
                    "back": {"text": "High back"},
                    "score": 90,
                },
                "low": {
                    "front": {"text": "Low"},
                    "back": {"text": "Low back"},
                    "score": 5,
                },
                "mid": {
                    "front": {"text": "Mid"},
                    "back": {"text": "Mid back"},
                    "score": 40,
                },
            },
        }
        path = Path(tempfile.mkdtemp()) / "deck.json"
        path.write_text(json.dumps(deck), encoding="utf-8")
        base = settings()["exercises"]["anki"]["settings"]
        for name in ("anki", "choose", "connect", "write"):
            with self.subTest(exercise=name):
                data = {
                    "global": {
                        "delay": "0", "session": "3", "batch": "1", "jitter": "0",
                    },
                    "exercises": {
                        name: {"enabled": True, "settings": dict(base)},
                    },
                }
                session = Session(
                    load_config(path), data,
                    rng=random.Random(1), save_categories=False,
                )
                cards = []
                for event in session:
                    if hasattr(event, "spec"):
                        cards.extend(event.card_ids)
                self.assertEqual(cards, ["low", "mid", "high"])

    def test_category_states_override_deck(self):
        path = write_deck(tempfile.mkdtemp())
        data = settings()
        data["categories"] = {"first": False, "second": True}
        config = load_config(path)
        session = Session(config, data, rng=random.Random(1), save_categories=True)
        written = json.loads(path.read_text())
        self.assertFalse(written["first"]["enabled"])
        self.assertTrue(written["second"]["enabled"])
        self.assertEqual(session.settings.global_.batch_size, 1)

    def test_single_mode_renders_only_requested_content(self):
        directory = Path(tempfile.mkdtemp())
        audio = directory / "hello.wav"
        image = directory / "hello.png"
        audio.write_bytes(b"audio")
        image.write_bytes(b"image")
        deck = {
            "example": {
                "enabled": True,
                "one": {
                    "front": {
                        "text": "Hello", "audio": audio.name, "image": image.name,
                    },
                    "back": {"text": "Hola", "audio": audio.name},
                    "score": 50,
                },
            },
        }
        path = directory / "deck.json"
        path.write_text(json.dumps(deck), encoding="utf-8")
        data = settings()
        data["exercises"]["anki"]["settings"]["prompt_type"] = ["audio_only"]
        data["exercises"]["anki"]["settings"]["answer_prompt"] = ["text_only"]
        session = Session(
            load_config(path), data, rng=random.Random(1), save_categories=False,
        )
        event = next(item for item in session if isinstance(item, Presentation))
        self.assertIsNone(event.spec.front.text)
        self.assertIsNone(event.spec.front.image)
        self.assertTrue(event.spec.front.audio.endswith("hello.wav"))
        self.assertEqual(event.spec.back.text, "Hola")
        self.assertIsNone(event.spec.back.audio)


if __name__ == "__main__":
    unittest.main()
