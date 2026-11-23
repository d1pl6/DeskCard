"""Headless tests for deck loading edge cases."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from src.config.loader import load_config, save_config
from src.errors import ConfigError
from src.ui.helpers.blocks import ChecksBlock, RadiosBlock


class ConfigLoaderTests(unittest.TestCase):
    def test_invalid_encoding_is_a_config_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_bytes(b'{"c":\xff}')
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_bom_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bom.json"
            path.write_bytes(b'\xef\xbb\xbf{"c": {"enabled": true}}')
            self.assertEqual(len(load_config(path).cards), 0)

    def test_relative_paths_are_resolved_for_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "deck.json"
            path.write_text(json.dumps({"c": {
                "enabled": True,
                "one": {"front": {"text": "a"}, "back": {"text": "b"}},
            }}), encoding="utf-8")
            other = root / "other"
            other.mkdir()
            previous = Path.cwd()
            os.chdir(root)
            try:
                config = load_config("deck.json")
                os.chdir(other)
                save_config(config)
            finally:
                os.chdir(previous)
            self.assertTrue(path.is_file())
            self.assertFalse((other / "deck.json").exists())

    def test_duplicate_id_is_reported_before_card_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dup.json"
            path.write_text(json.dumps({
                "c1": {"enabled": True,
                       "1": {"front": {"text": "a"}, "back": {"text": "b"}}},
                "c2": {"enabled": True, "1": {"back": {"text": "b"}}},
            }), encoding="utf-8")
            warnings = load_config(path).warnings
            self.assertIn("c2/1: duplicate card id, skipping the second one",
                          " ".join(warnings))
            self.assertNotIn("c2/1: missing front block", " ".join(warnings))

    def test_blank_text_warns_but_no_break_space_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spaces.json"
            path.write_text(json.dumps({"c": {
                "enabled": True,
                "one": {"front": {"text": " "}, "back": {"text": "b"}},
                "two": {"front": {"text": "\u00a0"}, "back": {"text": "b"}},
            }}), encoding="utf-8")
            warnings = " ".join(load_config(path).warnings)
            self.assertIn("c/one/front/text: only spaces", warnings)
            self.assertNotIn("c/two/front/text", warnings)


class BlockValidationTests(unittest.TestCase):
    def test_radios_reject_unknown_option(self):
        block = RadiosBlock({"kind": "radios", "key": "mode",
                             "options": [["a", "A"], ["b", "B"]]})
        with self.assertRaises(ConfigError):
            block.check("bogus", lambda message: (_ for _ in ()).throw(
                ConfigError(f"mode {message}")))

    def test_checks_reject_unknown_option(self):
        block = ChecksBlock({"kind": "checks", "key": "modes",
                             "options": [["a", "A"], ["b", "B"]]})
        with self.assertRaises(ConfigError):
            block.check(["a", "bogus"], lambda message: (_ for _ in ()).throw(
                ConfigError(f"modes {message}")))


if __name__ == "__main__":
    unittest.main()
