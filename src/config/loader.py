"""Config loader: parse, validate, and prepare the flashcard tree for write-back.

Design notes:
- The parsed JSON tree is the single source of truth; :class:`CardRecord`
  objects are typed views over the tree, so mutations flow back and a
  re-dump is a lossless round-trip (unknown fields and key order survive).
- ``#`` comments are stripped before parsing and are not
  preserved on write-back.
- Validation collects per-card warnings; structurally broken cards are
  reported and skipped instead of failing the whole file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

try:
    from ..errors import ConfigError
except ImportError:  # imported with `src` on sys.path (tools, script mode)
    from errors import ConfigError

__all__ = ["CardRecord", "Category", "Config", "load_config"]

_CATEGORY_META = frozenset({"enabled", "$version"})
_TOP_LEVEL_MEMOS = frozenset({"$version"})
_GRADES = ("easy", "light", "medium", "hard", "impossible")
# easy +10, light +5 (>=90%), medium +2, hard +0, impossible -5.
SCORE_DELTAS = {"easy": 10, "light": 5, "medium": 2, "hard": 0, "impossible": -5}


def _strip_comments(text: str) -> str:
    """Drop ``#`` comments that sit outside JSON string literals."""
    out: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            out.append(char)
            in_string = True
        elif char == "#":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue  # the newline itself is kept
        else:
            out.append(char)
        index += 1
    return "".join(out)


def _opt_str(face: dict[str, Any], field: str) -> str | None:
    """Optional string field; present-but-empty counts as absent."""
    value = face.get(field)
    return value if isinstance(value, str) and value else None


def _opt_int(data: dict[str, Any], field: str) -> int:
    value = data.get(field)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _parse_timestamp(raw: Any) -> datetime | None:
    """ISO 8601; a trailing ``Z`` is rewritten for Python 3.10's fromisoformat."""
    if not isinstance(raw, str) or not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


class _Face:
    """One side of a card (``front`` or ``back``)."""

    def __init__(self, face: dict[str, Any]) -> None:
        self._face = face

    @property
    def text(self) -> str | None:
        """Main content; this is what v1 exercises render and compare."""
        return _opt_str(self._face, "text")

    @property
    def sub(self) -> str | None:
        """Supplemental line; front.sub always, back.sub only after answering."""
        return _opt_str(self._face, "sub")

    @property
    def audio(self) -> str | None:
        return _opt_str(self._face, "audio")

    @property
    def image(self) -> str | None:
        return _opt_str(self._face, "image")


class CardRecord:
    """Typed view of one card in the config tree; mutations write straight through."""

    def __init__(self, category: str, key: str, data: dict[str, Any]) -> None:
        self.category = category
        self.key = key
        self.data = data

    @property
    def front(self) -> _Face:
        face = self.data.get("front")
        return _Face(face if isinstance(face, dict) else {})

    @property
    def back(self) -> _Face:
        face = self.data.get("back")
        return _Face(face if isinstance(face, dict) else {})

    @property
    def last_reviewed(self) -> datetime | None:
        return _parse_timestamp(self.data.get("last-reviewed"))

    @property
    def score(self) -> int:
        return _clamp_score(_opt_int(self.data, "score"))

    @property
    def normal(self) -> int:
        return _opt_int(self.data, "normal")

    @property
    def reverse(self) -> int:
        return _opt_int(self.data, "reverse")

    def count(self, grade: str) -> int:
        """Number of times this card was graded ``grade`` (0 if never)."""
        return _opt_int(self.data, grade)


@dataclass
class Category:
    """One top-level category with its enabled flag and version."""

    name: str
    enabled: bool
    version: int | None
    data: dict[str, Any]


class Config:
    """A parsed and validated flashcard config.

    ``cards`` contains only cards from enabled categories that passed
    validation, keyed by card id, in file order. ``warnings`` lists every
    validation problem, including why a card was skipped. ``disabled``
    counts the skipped cards per disabled category. ``tree`` keeps every
    field the file arrived with, so re-dumping it is a lossless round-trip.
    """

    def __init__(
        self,
        path: Path,
        tree: dict[str, Any],
        categories: dict[str, Category],
        cards: dict[str, CardRecord],
        warnings: list[str],
        disabled: dict[str, int],
    ) -> None:
        self.path = path
        self.tree = tree
        self.categories = categories
        self.cards = cards
        self.warnings = warnings
        self.disabled = disabled

    def card(self, card_id: str) -> CardRecord | None:
        return self.cards.get(card_id)

    def __iter__(self) -> Iterator[CardRecord]:
        return iter(self.cards.values())

    def __len__(self) -> int:
        return len(self.cards)


def load_config(path: str | Path) -> Config:
    """Read, parse, and validate a config file; see :class:`Config`."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {file_path}: {exc}") from exc
    try:
        tree = json.loads(_strip_comments(text))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{file_path}: invalid JSON: {exc}") from exc
    if not isinstance(tree, dict):
        raise ConfigError(f"{file_path}: top level must be an object, got {type(tree).__name__}")
    warnings: list[str] = []
    categories = _load_categories(file_path, tree, warnings)
    # Media paths are deck-relative: relative to the file being loaded, so the
    # result does not depend on the working directory.
    media_base = file_path.resolve().parent
    cards = _load_cards(file_path, categories, warnings, media_base)
    disabled = {
        name: _count_cards(category.data)
        for name, category in categories.items()
        if not category.enabled
    }
    return Config(file_path, tree, categories, cards, warnings, disabled)


def save_config(config: Config, path: str | Path | None = None) -> None:
    """Write the config tree back to disk, atomically.

    The parsed tree is the source of truth, so writing is a plain JSON dump:
    unknown fields and key order survive, ``#`` comments do not (they are
    stripped on load). The file is written to a temporary file next to the
    target and renamed over it, so a crash mid-write cannot corrupt the deck.
    """
    target = Path(path) if path is not None else config.path
    payload = json.dumps(config.tree, indent=2, ensure_ascii=False) + "\n"
    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(target)
    except OSError as exc:
        raise ConfigError(f"cannot write {target}: {exc}") from exc


def _count_cards(category_data: dict[str, Any]) -> int:
    return sum(
        1 for key, value in category_data.items()
        if key not in _CATEGORY_META and isinstance(value, dict)
    )


def _load_categories(
    path: Path, tree: dict[str, Any], warnings: list[str]
) -> dict[str, Category]:
    categories: dict[str, Category] = {}
    for name, data in tree.items():
        if name in _TOP_LEVEL_MEMOS:
            continue
        if not isinstance(data, dict):
            warnings.append(f"{path}: {name}: category is not an object, skipping")
            continue
        enabled = data.get("enabled", True)
        if not isinstance(enabled, bool):
            warnings.append(f"{path}: {name}: enabled must be true/false, treating as enabled")
            enabled = True
        version = data.get("$version")
        if version is not None and (isinstance(version, bool) or not isinstance(version, int)):
            warnings.append(f"{path}: {name}: $version must be an integer")
            version = None
        categories[name] = Category(name=name, enabled=enabled, version=version, data=data)
    return categories


def _load_cards(
    path: Path,
    categories: dict[str, Category],
    warnings: list[str],
    media_base: Path,
) -> dict[str, CardRecord]:
    cards: dict[str, CardRecord] = {}
    for category in categories.values():
        if not category.enabled:
            continue
        for key, data in category.data.items():
            if key in _CATEGORY_META:
                continue
            label = f"{path}: {category.name}/{key}"
            if not isinstance(data, dict):
                warnings.append(f"{label}: card is not an object, skipping")
                continue
            if not _validate_card(label, data, warnings, media_base):
                continue
            if key in cards:
                warnings.append(f"{label}: duplicate card id, skipping the second one")
                continue
            cards[key] = CardRecord(category.name, key, data)
    return cards


def _validate_card(
    label: str, data: dict[str, Any], warnings: list[str], media_base: Path
) -> bool:
    """front/back each need text, or audio, or image.

    v1 exercises are text-only, so a card without text stays valid but earns
    a warning; selection must skip it later. Media paths are checked against
    ``media_base`` and reported when the file is missing.
    """
    front = data.get("front")
    back = data.get("back")
    valid = True
    if isinstance(front, dict):
        valid = _validate_face(
            f"{label}/front", front, warnings, answer=False, media_base=media_base
        ) and valid
    else:
        warnings.append(f"{label}: missing front block, skipping the card")
        valid = False
    if isinstance(back, dict):
        valid = _validate_face(
            f"{label}/back", back, warnings, answer=True, media_base=media_base
        ) and valid
    else:
        warnings.append(f"{label}: missing back block, skipping the card")
        valid = False
    _validate_counts(label, data, warnings)
    _validate_last_reviewed(label, data, warnings)
    return valid


def _validate_face(
    prefix: str,
    face: dict[str, Any],
    warnings: list[str],
    answer: bool,
    media_base: Path,
) -> bool:
    if _missing_media(face):
        warnings.append(f"{prefix}: has neither text, audio nor image, skipping the card")
        return False
    if _opt_str(face, "text") is None:
        if answer:
            warnings.append(f"{prefix}: no text; the answer cannot be shown in v1 exercises")
        else:
            warnings.append(f"{prefix}: no text; card cannot be used by the text-only exercises")
    for field in ("text", "sub", "audio", "image"):
        if field in face and not isinstance(face[field], str):
            warnings.append(f"{prefix}/{field}: must be a string")
    _validate_media(prefix, face, warnings, media_base)
    return True


def _validate_media(
    prefix: str, face: dict[str, Any], warnings: list[str], media_base: Path
) -> None:
    """Audio/image strings must name an existing regular file."""
    for field in ("audio", "image"):
        value = _opt_str(face, field)
        if value is None:
            continue
        target = media_base / value  # absolute values replace the base as usual
        if not target.exists():
            warnings.append(f"{prefix}/{field}: no such file: {value}")
        elif not target.is_file():
            warnings.append(f"{prefix}/{field}: not a file: {value}")


def _missing_media(face: dict[str, Any]) -> bool:
    return all(_opt_str(face, field) is None for field in ("text", "audio", "image"))


def _validate_counts(label: str, data: dict[str, Any], warnings: list[str]) -> None:
    for field in (*_GRADES, "normal", "reverse"):
        if field not in data:
            continue
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, int):
            warnings.append(f"{label}/{field}: must be an integer, treating as 0")
            data[field] = 0
        elif value < 0:
            warnings.append(f"{label}/{field}: negative, treating as 0")
            data[field] = 0
    if "score" in data:
        value = data["score"]
        if isinstance(value, bool) or not isinstance(value, int):
            warnings.append(f"{label}/score: must be an integer, treating as 0")
            data["score"] = 0
        elif not 0 <= value <= 100:
            clamped = _clamp_score(value)
            warnings.append(f"{label}/score: {value} out of range 0-100, clamped to {clamped}")
            data["score"] = clamped


def _validate_last_reviewed(label: str, data: dict[str, Any], warnings: list[str]) -> None:
    if "last-reviewed" not in data:
        return
    raw = data["last-reviewed"]
    if not isinstance(raw, str) or _parse_timestamp(raw) is None:
        warnings.append(f"{label}/last-reviewed: not ISO 8601, treating as never reviewed")
        # keep the original value; no silent data loss on write-back
