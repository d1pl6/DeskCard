"""Headless tests for the session engine (run from the repository root)."""

import json
import random
import tempfile
import unittest
from pathlib import Path

from src.config.loader import load_config
from src.errors import SettingsError
from src.session import (
    Presentation, Session, normalize_settings, parse_score_filter, parse_time,
)


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


def write_simple_deck(directory, count):
    """A deck with `count` text-only cards in one enabled category."""
    cards = {
        str(index): {"front": {"text": f"f{index}"}, "back": {"text": f"b{index}"}}
        for index in range(1, count + 1)
    }
    path = Path(directory) / "deck.json"
    path.write_text(json.dumps({"c": {"enabled": True, **cards}}), encoding="utf-8")
    return path


def connect_settings(connections, batch="1", session=""):
    data = settings()
    data["exercises"]["anki"]["enabled"] = False
    data["global"].update({"batch": batch, "session": session})
    data["exercises"]["connect"] = {
        "enabled": True,
        "settings": {
            "prompt_type": ["text_only"],
            "answer_prompt": ["text_only"],
            "answer_connections": str(connections),
        },
    }
    return data


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
                    "random_score": "0",
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

    def test_random_score_default_and_bounds(self):
        data = settings()
        del data["exercises"]["anki"]["settings"]["random_score"]
        parsed = normalize_settings(data)
        self.assertEqual(parsed.exercises["anki"].random_score, 10)

        data["exercises"]["anki"]["settings"]["random_score"] = "250"
        with self.assertRaises(SettingsError):
            normalize_settings(data)

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

    def test_connect_group_respects_connection_limit(self):
        session = Session(
            load_config(write_simple_deck(tempfile.mkdtemp(), 3)),
            connect_settings(2), rng=random.Random(1), save_categories=False,
        )
        sizes = [len(event.card_ids) for event in session
                 if hasattr(event, "card_ids")]
        self.assertEqual(sizes, [2])

    def test_connect_gets_delay_per_round(self):
        session = Session(
            load_config(write_simple_deck(tempfile.mkdtemp(), 6)),
            connect_settings(3, batch="2"), rng=random.Random(1),
            save_categories=False,
        )
        shapes = [
            type(event).__name__ + (f":{len(event.card_ids)}"
                                    if hasattr(event, "card_ids") else "")
            for event in session
        ]
        self.assertEqual(shapes, ["Delay", "Presentation:3",
                                  "Delay", "Presentation:3"])
        self.assertEqual(session.warnings, [])

    def test_connect_leftover_does_not_warn(self):
        session = Session(
            load_config(write_simple_deck(tempfile.mkdtemp(), 5)),
            connect_settings(3, batch="2", session="2"),
            rng=random.Random(1), save_categories=False,
        )
        list(session)
        self.assertEqual(session.warnings, [])

    def test_no_break_space_is_an_ordinary_space(self):
        directory = tempfile.mkdtemp()
        path = Path(directory) / "deck.json"
        path.write_text(json.dumps({
            "c": {"enabled": True,
                  "one": {"front": {"text": "\u00a0"}, "back": {"text": "b"}}},
        }), encoding="utf-8")
        session = Session(
            load_config(path), settings(), rng=random.Random(1),
            save_categories=False,
        )
        presentation = next(event for event in session if hasattr(event, "spec"))
        self.assertEqual(presentation.spec.front.text, " ")

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

    def test_custom_score_deltas(self):
        path = write_deck(tempfile.mkdtemp())
        config = load_config(path)
        session = Session(
            config, settings(), rng=random.Random(1), save_categories=False,
            score_deltas={"easy": 7, "impossible": -9},
        )
        presentation = next(event for event in session if hasattr(event, "spec"))
        session.record(presentation, "easy")
        self.assertEqual(config.card("one").score, 17)
        self.assertEqual(json.loads(path.read_text())["first"]["one"]["score"], 17)

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

    def test_forced_direction_counter_preference(self):
        for mode, field in (("normal", "normal"), ("reverse", "reverse")):
            with self.subTest(mode=mode):
                data = settings()
                data["exercises"]["anki"]["settings"]["other_direction"] = mode
                config = load_config(write_deck(tempfile.mkdtemp()))
                session = Session(
                    config, data, rng=random.Random(1), save_categories=False,
                    count_all_directions=True,
                )
                self.assertEqual(
                    next(event for event in session if hasattr(event, "spec")).card_ids[0],
                    "one",
                )
                self.assertEqual(getattr(config.card("one"), field), 6)

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

    def test_random_score_jitters_ordering(self):
        deck = {
            "example": {
                "enabled": True,
                "a": {"front": {"text": "A"}, "back": {"text": "a"}, "score": 10},
                "b": {"front": {"text": "B"}, "back": {"text": "b"}, "score": 15},
                "c": {"front": {"text": "C"}, "back": {"text": "c"}, "score": 20},
            },
        }
        path = Path(tempfile.mkdtemp()) / "deck.json"
        path.write_text(json.dumps(deck), encoding="utf-8")
        for jitter, expected in (("0", ["a", "b", "c"]),
                                 ("10", ["a", "c", "b"])):
            with self.subTest(random_score=jitter):
                data = settings()
                data["exercises"]["anki"]["settings"]["random_score"] = jitter
                session = Session(
                    load_config(path), data,
                    rng=random.Random(4), save_categories=False,
                )
                order = [
                    event.spec.card_id for event in session
                    if isinstance(event, Presentation)
                ]
                self.assertEqual(order, expected)

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

    def test_combined_modes_render_only_requested_parts(self):
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
                        "text": "Hello", "sub": "hi",
                        "audio": audio.name, "image": image.name,
                    },
                    "back": {
                        "text": "Hola", "sub": "hola",
                        "audio": audio.name, "image": image.name,
                    },
                    "score": 50,
                },
            },
        }
        path = directory / "deck.json"
        path.write_text(json.dumps(deck), encoding="utf-8")
        expected = {
            "text_audio": (True, True, False),
            "text_image": (True, False, True),
            "audio_image": (False, True, True),
        }
        for mode, (text, audio_part, image_part) in expected.items():
            with self.subTest(mode=mode):
                data = settings()
                data["exercises"]["anki"]["settings"]["prompt_type"] = [mode]
                data["exercises"]["anki"]["settings"]["answer_prompt"] = [mode]
                session = Session(
                    load_config(path), data,
                    rng=random.Random(1), save_categories=False,
                )
                event = next(item for item in session if isinstance(item, Presentation))
                for face in (event.spec.front, event.spec.back):
                    self.assertEqual(bool(face.text), text)
                    self.assertEqual(bool(face.sub), text)
                    self.assertEqual(bool(face.audio), audio_part)
                    self.assertEqual(bool(face.image), image_part)


if __name__ == "__main__":
    unittest.main()
