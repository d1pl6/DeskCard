"""Session engine for DeskCard.

This module is plain Python: it knows nothing about tkinter or how a delay is
displayed. The UI builds a :class:`Session` from a loaded deck and the settings
collected by the main window, iterates it, renders each :class:`Presentation`,
and reports the result with :meth:`Session.record`.

Delays are yielded as :class:`Delay` events instead of sleeping, so the UI can
schedule them. Card results are written straight back to the deck through the
existing ``save_config()``.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    from .config.loader import CardRecord, Config, SCORE_DELTAS, save_config
    from .errors import SettingsError
except ImportError:
    from config.loader import CardRecord, Config, SCORE_DELTAS, save_config
    from errors import SettingsError

__all__ = [
    "AnkiCardSpec", "ChooseCardSpec", "ConnectCardSpec", "ConnectPairSpec",
    "Delay", "ExerciseSettings", "FaceSpec", "GlobalSettings", "NormalizedSettings",
    "Presentation", "Session", "SettingsError", "WriteCardSpec",
    "normalize_settings", "parse_time",
]


EXERCISE_ORDER = ("anki", "choose", "connect", "write")

CONTENT_MODES = {
    "text_only": ("text",),
    "audio_only": ("audio",),
    "image_only": ("image",),
    "text_audio": ("text", "audio"),
    "text_image": ("text", "image"),
    "audio_image": ("audio", "image"),
    "all": ("text", "audio", "image"),
}
SINGLE_MODES = frozenset({"text_only", "audio_only", "image_only"})
SUB_MODES = frozenset({"always", "after", "never"})
DIRECTIONS = frozenset({"normal", "reverse", "random"})

_TIME_RE = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")
_SCORE_RE = re.compile(r"^(\d+)(?:-(\d+))?$")
_INT_RE = re.compile(r"^\d+$")

# Defaults mirror the schema in src/ui/loader.py. A settings file may omit
# fields; these keep the engine usable without a full settings file.
_GLOBAL_DEFAULTS = {"delay": "1m", "session": "", "batch": "1", "jitter": "0"}
_EXERCISE_DEFAULTS = {
    "prompt_type": ["text_only"],
    "prompt_sub": "always",
    "prompt_listens": "0",
    "answer_prompt": ["text_only"],
    "answer_sub": "after",
    "answer_choices": "5",
    "answer_connections": "5",
    "answer_time": "0",
    "other_direction": "normal",
    "other_score": "0-99",
    "random_score": "10",
    "other_close_time": "3s",
    "other_repeat": False,
    "other_attempts": "",
}


# ---------------------------------------------------------------------------
# Settings parsing
# ---------------------------------------------------------------------------
def _fail(path: str, message: str) -> None:
    raise SettingsError(f"{path}: {message}")


def parse_time(raw: str, path: str, *, empty: int | None) -> int | None:
    """Parse a duration string into seconds.

    Accepted: ``1h5m30s``, ``61m30s``, ``90s`` and bare ``90``. Units are
    lowercase and ordered; spaces, uppercase and repeated units are rejected.
    ``empty`` is the value returned for an empty string.
    """
    if not isinstance(raw, str):
        _fail(path, "must be a time string")
    if raw == "":
        return empty
    if _INT_RE.fullmatch(raw):
        return int(raw)
    match = _TIME_RE.fullmatch(raw)
    if match is None or not any(match.groups()):
        _fail(path, "must look like 90, 90s, 61m30s or 1h5m30s")
    hours, minutes, seconds = (int(group or 0) for group in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def parse_score_filter(raw: str, path: str) -> tuple[int, int]:
    """Parse the card-score selection filter: ``N`` or ``N-M``, 0–100."""
    if not isinstance(raw, str) or raw == "":
        _fail(path, "must be a number or range from 0 to 100")
    match = _SCORE_RE.fullmatch(raw)
    if match is None:
        _fail(path, "must be N or N-M, e.g. 55 or 0-99")
    low, high = int(match.group(1)), int(match.group(2) or match.group(1))
    if not 0 <= low <= 100 or not 0 <= high <= 100:
        _fail(path, "must be within 0-100")
    if low > high:
        _fail(path, "range start must not be greater than range end")
    return low, high


def _parse_int(
    raw: Any,
    path: str,
    *,
    empty: int | None,
    minimum: int = 0,
    maximum: int | None = None,
) -> int | None:
    if not isinstance(raw, str):
        _fail(path, "must be a whole number")
    if raw == "":
        return empty
    if _INT_RE.fullmatch(raw) is None:
        _fail(path, "must be a whole number")
    value = int(raw)
    if value < minimum or (maximum is not None and value > maximum):
        expected = f"{minimum}-{maximum}" if maximum is not None else f">= {minimum}"
        _fail(path, f"must be {expected}")
    return value


def _parse_bool(raw: Any, path: str) -> bool:
    if not isinstance(raw, bool):
        _fail(path, "must be true/false")
    return raw


def _parse_choice(raw: Any, path: str, allowed: frozenset[str] | set[str],
                  default: str) -> str:
    if raw is None or raw == "":
        return default
    if not isinstance(raw, str) or raw not in allowed:
        _fail(path, f"must be one of: {', '.join(sorted(allowed))}")
    return raw


def _parse_modes(raw: Any, path: str, default: list[str]) -> tuple[str, ...]:
    if raw is None:
        raw = default
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        _fail(path, "must be a list of content names")
    for mode in raw:
        if mode not in CONTENT_MODES:
            _fail(path, f"unknown content mode {mode!r}")
    return tuple(raw)


@dataclass(frozen=True)
class GlobalSettings:
    delay: int          # seconds before a batch; 0 means immediate
    jitter: int         # percent, 0 means exact
    batches: int | None # None means unlimited
    batch_size: int     # cards per batch


@dataclass(frozen=True)
class ExerciseSettings:
    name: str
    enabled: bool
    advanced: bool
    prompt_type: tuple[str, ...]
    prompt_sub: str
    prompt_listens: int
    answer_prompt: tuple[str, ...]
    answer_sub: str
    answer_choices: int
    answer_connections: int
    answer_time: int | None  # None means no limit
    other_direction: str
    other_score: tuple[int, int]
    random_score: int
    other_close_time: int
    other_repeat: bool
    other_attempts: int


@dataclass(frozen=True)
class NormalizedSettings:
    global_: GlobalSettings
    exercises: dict[str, ExerciseSettings]
    categories: dict[str, bool]
    deck: str | None


def normalize_settings(data: dict[str, Any]) -> NormalizedSettings:
    """Validate raw settings from the UI and return typed values.

    Any malformed value raises :class:`SettingsError`; the caller should block
    Start and show the message rather than guessing a value.
    """
    if not isinstance(data, dict):
        _fail("settings", "top level must be an object")

    raw_global = data.get("global", {})
    if not isinstance(raw_global, dict):
        _fail("global", "must be an object")
    global_values = dict(_GLOBAL_DEFAULTS)
    global_values.update(raw_global)
    global_ = GlobalSettings(
        delay=int(parse_time(global_values["delay"], "global.delay", empty=0) or 0),
        jitter=int(_parse_int(global_values["jitter"], "global.jitter",
                              empty=0, maximum=100) or 0),
        batches=_parse_int(global_values["session"], "global.session",
                           empty=None, minimum=1),
        batch_size=int(_parse_int(global_values["batch"], "global.batch",
                                  empty=1, minimum=1) or 1),
    )

    raw_exercises = data.get("exercises", {})
    if not isinstance(raw_exercises, dict):
        _fail("exercises", "must be an object")
    exercises: dict[str, ExerciseSettings] = {}
    for name in EXERCISE_ORDER:
        raw = raw_exercises.get(name, {})
        if not isinstance(raw, dict):
            _fail(f"exercises.{name}", "must be an object")
        raw_settings = raw.get("settings")
        if raw_settings is None:
            raw_settings = {}
        if not isinstance(raw_settings, dict):
            _fail(f"exercises.{name}.settings", "must be an object")
        values = dict(_EXERCISE_DEFAULTS)
        values.update(raw_settings)
        path = f"exercises.{name}.settings"
        exercises[name] = ExerciseSettings(
            name=name,
            enabled=_parse_bool(raw.get("enabled", False), f"exercises.{name}.enabled"),
            advanced=_parse_bool(raw.get("advanced", False), f"exercises.{name}.advanced"),
            prompt_type=_parse_modes(values["prompt_type"], f"{path}.prompt_type",
                                     _EXERCISE_DEFAULTS["prompt_type"]),
            prompt_sub=_parse_choice(values["prompt_sub"], f"{path}.prompt_sub",
                                     SUB_MODES, "always"),
            prompt_listens=int(_parse_int(values["prompt_listens"],
                                          f"{path}.prompt_listens", empty=0) or 0),
            answer_prompt=_parse_modes(values["answer_prompt"], f"{path}.answer_prompt",
                                       _EXERCISE_DEFAULTS["answer_prompt"]),
            answer_sub=_parse_choice(values["answer_sub"], f"{path}.answer_sub",
                                     SUB_MODES, "after"),
            answer_choices=int(_parse_int(values["answer_choices"],
                                          f"{path}.answer_choices", empty=5,
                                          minimum=2) or 5),
            answer_connections=int(_parse_int(values["answer_connections"],
                                              f"{path}.answer_connections", empty=5,
                                              minimum=2, maximum=10) or 5),
            answer_time=parse_time(values["answer_time"], f"{path}.answer_time",
                                   empty=None) or None,
            other_direction=_parse_choice(values["other_direction"],
                                          f"{path}.other_direction", DIRECTIONS, "normal"),
            other_score=parse_score_filter(values["other_score"], f"{path}.other_score"),
            random_score=int(_parse_int(values["random_score"], f"{path}.random_score",
                                        empty=10, minimum=0, maximum=100) or 0),
            other_close_time=int(parse_time(values["other_close_time"],
                                            f"{path}.other_close_time", empty=0) or 0),
            other_repeat=_parse_bool(values["other_repeat"], f"{path}.other_repeat"),
            other_attempts=int(_parse_int(values["other_attempts"],
                                          f"{path}.other_attempts", empty=1,
                                          minimum=1) or 1),
        )
        settings = exercises[name]
        if settings.other_repeat and raw_settings.get("other_attempts") not in (None, ""):
            _fail(f"exercises.{name}.settings.other_attempts",
                  "must be empty when Repeat until correct is on")

    raw_categories = data.get("categories", {})
    if not isinstance(raw_categories, dict):
        _fail("categories", "must be an object")
    categories = {
        str(name): _parse_bool(enabled, f"categories.{name}")
        for name, enabled in raw_categories.items()
    }
    deck = data.get("deck")
    if deck is not None and not isinstance(deck, str):
        _fail("deck", "must be a path string or null")
    return NormalizedSettings(global_, exercises, categories, deck)


# ---------------------------------------------------------------------------
# Exercise data
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FaceSpec:
    """One card face, with media paths resolved against the deck file."""

    text: str | None
    sub: str | None
    audio: str | None  # absolute path, or None when missing
    image: str | None  # absolute path, or None when missing

    def has(self, part: str) -> bool:
        return {
            "text": bool(self.text),
            "audio": self.audio is not None,
            "image": self.image is not None,
        }[part]


@dataclass(frozen=True)
class AnkiCardSpec:
    front: FaceSpec
    back: FaceSpec
    category: str
    direction: str
    card_id: str


@dataclass(frozen=True)
class ChooseCardSpec:
    prompt: FaceSpec
    answer: FaceSpec
    choices: tuple[str, ...]
    correct: int
    category: str
    direction: str
    card_id: str


@dataclass(frozen=True)
class ConnectPairSpec:
    prompt: FaceSpec
    answer: FaceSpec
    category: str
    direction: str
    card_id: str


@dataclass(frozen=True)
class ConnectCardSpec:
    pairs: tuple[ConnectPairSpec, ...]
    category: str
    direction: str


@dataclass(frozen=True)
class WriteCardSpec:
    prompt: FaceSpec
    answer: FaceSpec
    category: str
    direction: str
    card_id: str


@dataclass(frozen=True)
class Presentation:
    """One card (or Connect batch) ready for an exercise screen."""

    exercise: str
    spec: Any
    card_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Delay:
    """A pre-card pause; the UI should schedule it without blocking."""

    seconds: int
    reason: str = "batch"


@dataclass
class _Draw:
    card_id: str
    direction: str  # resolved normal/reverse
    count_direction: bool  # True only for the random direction setting


@dataclass
class _Pool:
    settings: ExerciseSettings
    draws: list[_Draw]


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
class Session:
    """A study session built from a deck, settings, and category checkboxes."""

    def __init__(
        self,
        config: Config,
        settings: dict[str, Any] | NormalizedSettings,
        category_states: dict[str, bool] | None = None,
        *,
        rng: random.Random | None = None,
        save_categories: bool = True,
        score_deltas: dict[str, int] | None = None,
        count_all_directions: bool = False,
    ) -> None:
        """Build a session from a deck and settings.

        ``save_categories`` only controls write-back of category checkboxes;
        results are always saved by :meth:`record` and :meth:`finish`.
        """
        self.config = config
        self.count_all_directions = count_all_directions
        self.settings = (
            settings if isinstance(settings, NormalizedSettings)
            else normalize_settings(settings)
        )
        self.rng = rng or random.Random()
        self.score_deltas = dict(SCORE_DELTAS)
        if score_deltas:
            for grade, delta in score_deltas.items():
                if grade in SCORE_DELTAS:
                    self.score_deltas[grade] = int(delta)
        self.media_base = config.path.resolve().parent
        self.warnings: list[str] = []
        # Presentations are built (and their direction counters bumped) as a
        # batch. Keep the baseline so only draws the UI really displayed are
        # persisted; see commit_visible().
        self._initial_directions = {
            key: (card.normal, card.reverse)
            for key, card in self.config.cards.items()
        }
        self._presented_draws: dict[int, tuple[tuple[str, bool, str], ...]] = {}
        # A settings file's category states override the deck's own enabled
        # flags; the UI passes its checkboxes explicitly when they differ.
        states = self.settings.categories if category_states is None else category_states
        if states:
            self.apply_categories(states, save_categories=save_categories)
        self._pools = self._build_pools()
        self._warn_if_short()
        self._cursor = 0

    # -- categories ---------------------------------------------------------
    def apply_categories(
        self, states: dict[str, bool], *, save_categories: bool = True
    ) -> None:
        """Set category enabled flags in memory and, by default, on disk."""
        changed = False
        for name, category in self.config.categories.items():
            if name not in states:
                continue
            enabled = bool(states[name])
            if category.enabled == enabled and category.data.get("enabled") == enabled:
                continue
            category.enabled = enabled
            category.data["enabled"] = enabled
            changed = True
        if changed and save_categories:
            save_config(self.config)

    def _warn_if_short(self) -> None:
        """Warn up front when the deck cannot fill the requested batches."""
        batches = self.settings.global_.batches
        if batches is None:
            return
        available = sum(len(pool.draws) for pool in self._pools)
        if available < batches * self.settings.global_.batch_size:
            self.warnings.append("session ended early: not enough playable cards")

    # -- pool construction --------------------------------------------------
    def _build_pools(self) -> list[_Pool]:
        pools: list[_Pool] = []
        for name in EXERCISE_ORDER:
            exercise = self.settings.exercises[name]
            if not exercise.enabled:
                continue
            low, high = exercise.other_score
            candidates = [
                card for card in self.config.cards.values()
                if self.config.categories[card.category].enabled
                and low <= card.score <= high
            ]
            # Shuffle first so equal scores do not silently follow file order,
            # then sort by score: weakest cards are shown first in every
            # exercise, not just Anki. `random_score` adds 0..N to the score
            # used for this ordering, giving close scores a chance to swap.
            self.rng.shuffle(candidates)
            if exercise.random_score:
                candidates.sort(
                    key=lambda card: card.score
                    + self.rng.randint(0, exercise.random_score)
                )
            else:
                candidates.sort(key=lambda card: card.score)
            draws: list[_Draw] = []
            answer_texts: set[str] = set()
            for card in candidates:
                direction, count = self._choose_direction(card, exercise.other_direction)
                answer_text = card.back.text if direction == "normal" else card.front.text
                if answer_text:
                    answer_texts.add(answer_text)
                prompt, answer, _ = self._faces(
                    card, direction, f"{card.category}/{card.key}"
                )
                if name != "anki" and not self._content_ok(
                    prompt, exercise.prompt_type, f"{card.category}/{card.key}/prompt"
                ):
                    continue
                if name in ("choose", "connect", "write") and not self._content_ok(
                    answer, exercise.answer_prompt, f"{card.category}/{card.key}/answer"
                ):
                    continue
                if name == "choose" and not answer.text:
                    continue
                draws.append(_Draw(card.key, direction, count))
            if name == "choose" and len(answer_texts) < 2:
                self.warnings.append(
                    f"choose: needs at least 2 choices, only {len(answer_texts)} available"
                )
                continue
            if name == "connect" and len(draws) < 2:
                self.warnings.append(
                    f"connect: needs at least 2 cards, only {len(draws)} available"
                )
                continue
            if draws:
                pools.append(_Pool(exercise, draws))
            else:
                self.warnings.append(f"{name}: no playable cards")
        return pools

    def _choose_direction(self, card: CardRecord, mode: str) -> tuple[str, bool]:
        """Return the resolved direction and whether it should be counted."""
        if mode == "normal":
            return "normal", self.count_all_directions
        if mode == "reverse":
            return "reverse", self.count_all_directions
        normal, reverse = card.normal, card.reverse
        if normal == reverse:
            direction = self.rng.choice(("normal", "reverse"))
        elif normal == 0:
            direction = "reverse"
        elif reverse == 0:
            direction = "normal"
        else:
            direction = "normal" if normal < reverse else "reverse"
        return direction, True

    def _count_direction(self, card: CardRecord, direction: str) -> None:
        field = "normal" if direction == "normal" else "reverse"
        card.data[field] = card.count(field) + 1

    def _media_path(self, value: str | None, label: str,
                    warnings: list[str]) -> str | None:
        if not value:
            return None
        path = Path(value)
        target = path if path.is_absolute() else self.media_base / path
        if not target.is_file():
            warnings.append(f"{label}: media file missing: {value}")
            return None
        return str(target)

    def _faces(self, card: CardRecord, direction: str,
               label: str) -> tuple[FaceSpec, FaceSpec, tuple[str, ...]]:
        warnings: list[str] = []
        prompt_data, answer_data = (
            (card.front, card.back) if direction == "normal"
            else (card.back, card.front)
        )

        def build(face: Any, side: str) -> FaceSpec:
            prefix = f"{label}/{side}"
            return FaceSpec(
                text=face.text,
                sub=face.sub,
                audio=self._media_path(face.audio, f"{prefix}/audio", warnings),
                image=self._media_path(face.image, f"{prefix}/image", warnings),
            )

        prompt, answer = build(prompt_data, "prompt"), build(answer_data, "answer")
        return prompt, answer, tuple(warnings)

    @staticmethod
    def _filter_face(face: FaceSpec, modes: tuple[str, ...]) -> FaceSpec:
        """Keep only the parts requested by the exercise's content modes."""
        parts = {part for mode in modes for part in CONTENT_MODES[mode]}
        return FaceSpec(
            text=face.text if "text" in parts else None,
            sub=face.sub if "text" in parts else None,
            audio=face.audio if "audio" in parts else None,
            image=face.image if "image" in parts else None,
        )

    @classmethod
    def _wanted_warnings(cls, warnings: tuple[str, ...],
                         *mode_groups: tuple[str, ...]) -> tuple[str, ...]:
        parts = {
            part for modes in mode_groups for mode in modes
            for part in CONTENT_MODES[mode]
        }
        return tuple(
            warning for warning in warnings
            if any(f"/{part}:" in warning for part in parts)
        )

    @staticmethod
    def _content_ok(face: FaceSpec, modes: tuple[str, ...], label: str,
                    warnings: list[str] | None = None) -> bool:
        if not modes:
            return False
        parts = [part for mode in modes for part in CONTENT_MODES[mode]]
        missing = [part for part in parts if not face.has(part)]
        if len(modes) == 1 and modes[0] in SINGLE_MODES:
            return not missing
        if len(missing) == len(parts):
            return False
        if missing and warnings is not None:
            warnings.append(f"{label}: missing {', '.join(missing)}")
        return True

    # -- event flow ---------------------------------------------------------
    def presentations(self) -> Iterator[Delay | Presentation]:
        """Yield delays and cards in session order.

        A delay comes before the first card and before every new batch. The
        generator stops at the configured number of batches or when no cards
        remain, whichever comes first.
        """
        if not self._pools:
            return
        global_ = self.settings.global_
        limit = None if global_.batches is None else global_.batches * global_.batch_size
        shown = 0
        while True:
            if limit is not None and shown >= limit:
                return
            remaining = None if limit is None else limit - shown
            presentation = self._next_presentation(remaining)
            if presentation is None:
                message = "session ended early: not enough playable cards"
                if limit is not None and shown < limit and message not in self.warnings:
                    self.warnings.append(message)
                return
            # Batches count cards, not presentations; Connect shows several
            # cards at once. Fetching first also avoids a delay after the end.
            if shown % global_.batch_size == 0:
                yield Delay(self._delay_seconds())
            yield presentation
            shown += len(presentation.card_ids)

    def __iter__(self) -> Iterator[Delay | Presentation]:
        return self.presentations()

    def _delay_seconds(self) -> int:
        delay = self.settings.global_.delay
        jitter = self.settings.global_.jitter
        if delay == 0 or jitter == 0:
            return delay
        low = max(0, math.ceil(delay * (100 - jitter) / 100))
        high = math.floor(delay * (100 + jitter) / 100)
        return self.rng.randint(low, max(low, high))

    def _next_presentation(self, remaining: int | None = None) -> Presentation | None:
        while self._pools:
            pool = self._pools[self._cursor % len(self._pools)]
            self._cursor += 1
            if not pool.draws:
                self._pools.remove(pool)
                continue
            draw = pool.draws.pop(0)
            card = self.config.card(draw.card_id)
            if card is None:
                continue
            prompt, answer, warnings = self._faces(
                card, draw.direction, f"{card.category}/{card.key}"
            )
            exercise = pool.settings
            content_warnings: list[str] = []
            self._content_ok(
                prompt, exercise.prompt_type,
                f"{card.category}/{card.key}/prompt", content_warnings,
            )
            if exercise.name in ("choose", "connect", "write"):
                self._content_ok(
                    answer, exercise.answer_prompt,
                    f"{card.category}/{card.key}/answer", content_warnings,
                )
            if exercise.name in ("choose", "write") and not any(
                    "text" in CONTENT_MODES[mode] for mode in exercise.answer_prompt):
                message = f"{exercise.name}: answer must include text"
                if message not in self.warnings:
                    self.warnings.append(message)
                continue
            prompt = self._filter_face(prompt, exercise.prompt_type)
            answer = self._filter_face(answer, exercise.answer_prompt)
            visible_warnings = self._wanted_warnings(
                tuple(warnings), exercise.prompt_type, exercise.answer_prompt,
            )
            counted: list[tuple[CardRecord, _Draw]] = []
            presentation = self._build_spec(
                exercise, card, draw, prompt, answer,
                visible_warnings + tuple(content_warnings), counted, remaining,
            )
            if presentation is None:
                continue
            # Only cards that actually make it onto a presentation get their
            # direction counter bumped. Forced modes count when enabled.
            for used_card, used_draw in counted:
                if used_draw.count_direction:
                    self._count_direction(used_card, used_draw.direction)
            self._presented_draws[id(presentation)] = tuple(
                (used_draw.card_id, used_draw.count_direction, used_draw.direction)
                for _, used_draw in counted
            )
            return presentation
        return None

    def _build_spec(self, exercise: ExerciseSettings, card: CardRecord,
                    draw: _Draw, prompt: FaceSpec, answer: FaceSpec,
                    warnings: tuple[str, ...],
                    counted: list[tuple[CardRecord, _Draw]],
                    remaining: int | None = None) -> Presentation | None:
        common = (card.category, draw.direction, card.key)
        category, direction, card_key = common
        if exercise.name == "anki":
            counted.append((card, draw))
            spec = AnkiCardSpec(prompt, answer, category, direction, card_key)
            return Presentation("anki", spec, (card.key,), warnings)
        if exercise.name == "choose":
            choices = self._choices(exercise, card, draw.direction, answer.text or "")
            if choices is None:
                return None
            counted.append((card, draw))
            spec = ChooseCardSpec(
                prompt, answer, choices[0], choices[1], category, direction, card_key,
            )
            return Presentation("choose", spec, (card.key,), warnings)
        if exercise.name == "write":
            counted.append((card, draw))
            spec = WriteCardSpec(prompt, answer, category, direction, card_key)
            return Presentation("write", spec, (card.key,), warnings)
        if exercise.name == "connect":
            return self._connect_presentation(
                exercise, draw, prompt, answer, warnings, counted, remaining
            )
        return None

    def _choices(self, exercise: ExerciseSettings, card: CardRecord,
                 direction: str, answer: str) -> tuple[tuple[str, ...], int] | None:
        others = [
            other.back.text if direction == "normal" else other.front.text
            for other in self.config.cards.values()
            if other.key != card.key and self.config.categories[other.category].enabled
        ]
        distractors = list(dict.fromkeys(text for text in others if text and text != answer))
        self.rng.shuffle(distractors)
        choices = distractors[:exercise.answer_choices - 1]
        choices.append(answer)
        self.rng.shuffle(choices)
        return tuple(choices), choices.index(answer)

    def _connect_presentation(self, exercise: ExerciseSettings, draw: _Draw,
                              prompt: FaceSpec, answer: FaceSpec,
                              warnings: tuple[str, ...],
                              counted: list[tuple[CardRecord, _Draw]],
                              allowance: int | None = None) -> Presentation | None:
        pool = next((item for item in self._pools if item.settings.name == "connect"), None)
        if pool is None:
            return None
        available = len(pool.draws) + 1  # the current draw is already popped
        wanted = min(exercise.answer_connections, available)
        if allowance is not None:
            wanted = min(wanted, allowance)
        if wanted < 2:
            return None
        if available - wanted == 1:
            # Leave no orphaned card: either shrink this group to leave two,
            # or absorb the stray card when the allowance permits it.
            if wanted - 1 >= 2:
                wanted -= 1
            elif allowance is None or allowance > wanted:
                wanted += 1
        used = [draw]
        all_warnings = list(warnings)
        while len(used) < wanted and pool.draws:
            used.append(pool.draws.pop(0))
        if len(used) < 2:
            return None
        pairs: list[ConnectPairSpec] = []
        used_cards: list[tuple[CardRecord, _Draw]] = []
        for index, item in enumerate(used):
            card = self.config.card(item.card_id)
            if card is None:
                continue
            faces = self._faces(card, item.direction, f"{card.category}/{card.key}")
            pair_prompt = self._filter_face(faces[0], exercise.prompt_type)
            pair_answer = self._filter_face(faces[1], exercise.answer_prompt)
            pairs.append(ConnectPairSpec(
                pair_prompt, pair_answer, card.category, item.direction, card.key,
            ))
            used_cards.append((card, item))
            if index:
                all_warnings.extend(self._wanted_warnings(
                    faces[2], exercise.prompt_type, exercise.answer_prompt,
                ))
        if len(pairs) < 2:
            return None
        if len(pairs) < exercise.answer_connections:
            all_warnings.append(
                f"connect: only {len(pairs)} pairs available "
                f"({exercise.answer_connections} requested)"
            )
        spec = ConnectCardSpec(tuple(pairs), pairs[0].category, pairs[0].direction)
        counted.extend(used_cards)
        return Presentation("connect", spec, tuple(pair.card_id for pair in pairs),
                            tuple(all_warnings))

    # -- results ------------------------------------------------------------
    def commit_visible(self, presentations: list[Presentation]) -> None:
        """Keep direction counters only for presentations the UI displayed.

        Materializing a session builds every presentation up front, which also
        bumps counters for cards the user may never see. Before any save, reset
        each counter to its pre-session value and re-apply only the draws that
        were actually shown.
        """
        for card_id, (normal, reverse) in self._initial_directions.items():
            card = self.config.card(card_id)
            if card is None:
                continue
            card.data["normal"] = normal
            card.data["reverse"] = reverse
        for presentation in presentations:
            for card_id, counted, direction in self._presented_draws.get(
                id(presentation), ()
            ):
                if not counted:
                    continue
                card = self.config.card(card_id)
                if card is not None:
                    self._count_direction(card, direction)

    def record(self, presentation: Presentation, grade: str) -> None:
        """Apply one result to every card used by ``presentation`` and save."""
        if grade not in self.score_deltas:
            raise ValueError(f"unknown grade {grade!r}")
        delta = self.score_deltas[grade]
        stamp = (
            datetime.now(timezone.utc).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z")
        )
        for card_id in presentation.card_ids:
            card = self.config.card(card_id)
            if card is None:
                continue
            card.data["score"] = max(0, min(100, card.score + delta))
            card.data[grade] = card.count(grade) + 1
            card.data["last-reviewed"] = stamp
        save_config(self.config)

    def record_correct(self, presentation: Presentation, correct: bool) -> None:
        """Record a binary result using the initial Easy/Impossible rule."""
        self.record(presentation, "easy" if correct else "impossible")

    def finish(self) -> None:
        """Persist any in-memory changes (direction counters, for example)."""
        save_config(self.config)
