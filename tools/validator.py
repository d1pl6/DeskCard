#!/usr/bin/env python3
"""Standalone validator for DeskCard deck JSON files.

Usage:
    python3 tools/validator.py [all|text|sub|audio|image|other] FILE...

The check word selects which card fields are verified (default: all):

    all     every face field plus the card-level fields
    text    front.text / back.text
    sub     front.sub / back.sub
    audio   the audio fields
    image   the image fields
    other   card-level fields: last-reviewed, easy, light, medium, hard,
            impossible, score, normal, reverse

Structure is verified whichever check is given, because broken structure
makes the app silently drop cards: the top level must be an object of
categories, each category an object of cards (``enabled`` a boolean,
``$version`` an integer) with no card id reused across categories, each
card an object with front and back object faces, each face carrying at
least one of text, audio, image (a present-but-empty string counts as
absent, i.e. ``{}``). Those produce errors.

Field rules: face fields are non-empty strings; counters (easy .. impossible,
normal, reverse) are non-negative integers; score is an integer within
0-100; last-reviewed is ISO 8601. Wrong types and ranges are errors. An
audio or image string, unlike text and sub, names a media file: it must
resolve to an existing regular file in the deck file's directory (where
its audio/ or image/ subfolder lives); a directory, trailing slash or
otherwise, is an error.

Two warnings are tolerated by design:
    - text missing while audio or image covers the face (v1 exercises are
      text-only and would skip the card),
    - a present-but-empty string, which counts as absent.

Disabled categories are verified too and named in the summary; audio/image
paths are not checked, since that is the filesystem's business. The exit
code is 1 once any file has an error, 0 with warnings alone.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, NamedTuple

# Bare-script bootstrap: pytest puts src/ on sys.path (pythonpath=src in
# pyproject), but `python3 tools/validator.py` does not, so add src/ first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# The loader defines the deck rules; instead of duplicating how it parses,
# this tool shares its pieces and reports what the loader would silently
# patch (clamp, zero, ignore) as errors for the author to fix.
from config.loader import _GRADES, _parse_timestamp, _strip_comments  # noqa: E402

_MEMOS = ("$version",)
_METAS = ("enabled", "$version")
_FACE_FIELDS = ("text", "sub", "audio", "image")
_OTHER_FIELDS = (*_GRADES, "normal", "reverse")
# Ranges: score 0 to 100, counters cannot go below 0.
_SCORE_RANGE = range(0, 101)

_CHECKS = {
    "all": _FACE_FIELDS,
    "text": ("text",),
    "sub": ("sub",),
    "audio": ("audio",),
    "image": ("image",),
    "other": (),
}
_USAGE = "usage: python3 tools/validator.py [all|text|sub|audio|image|other] FILE..."


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _opt_str(value: Any) -> str | None:
    """Same view of a value as loader._opt_str: an empty string is absent."""
    return value if isinstance(value, str) and value else None


def _type_name(value: Any) -> str:
    """JSON-ish type names so reports read like the deck, not CPython."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _missing_media(face: dict[str, Any]) -> bool:
    """True when the face holds no text, audio, image at all."""
    return all(_opt_str(face.get(field)) is None for field in ("text", "audio", "image"))


class _Problem(NamedTuple):
    severity: str  # "error" or "warning"
    label: str  # "category/card[/face][/field]"
    message: str


def _err(label: str, message: str) -> _Problem:
    return _Problem("error", label, message)


def _warn(label: str, message: str) -> _Problem:
    return _Problem("warning", label, message)


class _Result(NamedTuple):
    problems: list[_Problem]
    cards: int
    categories: int
    disabled: tuple[str, ...]


def _validate_file(path: Path, check: str) -> _Result:
    """Check one deck file and report its problems."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return _Result([_err("", f"cannot read: {exc}")], 0, 0, ())
    try:
        tree = json.loads(_strip_comments(text))
    except json.JSONDecodeError as exc:
        return _Result([_err("", f"invalid JSON: {exc}")], 0, 0, ())
    if not isinstance(tree, dict):
        return _Result(
            [_err("", f"top level must be an object, got {_type_name(tree)}")], 0, 0, ()
        )

    problems: list[_Problem] = []
    cards = 0
    categories = 0
    disabled: list[str] = []
    seen_ids: set[str] = set()
    # Media paths are deck-relative: relative to the file being checked, so
    # running the tool from any working directory reports the same result.
    media_base = path.resolve().parent
    for name, category in tree.items():
        if name in _MEMOS:
            if not _is_int(category):
                problems.append(
                    _err(name, f"$version must be an integer, got {_type_name(category)}")
                )
            continue
        if not isinstance(category, dict):
            problems.append(_err(name, "category is not an object, the app skips it"))
            continue
        categories += 1
        enabled = category.get("enabled", True)
        if not isinstance(enabled, bool):
            problems.append(_err(name, f"enabled must be true/false, got {_type_name(enabled)}"))
        elif not enabled:
            disabled.append(name)
        version = category.get("$version")
        if version is not None and not _is_int(version):
            problems.append(
                _err(name, f"$version must be an integer, got {_type_name(version)}")
            )
        for card_key, card_data in category.items():
            if card_key in _METAS:
                continue
            label = f"{name}/{card_key}"
            if not isinstance(card_data, dict):
                problems.append(_err(label, "card is not an object, the app would skip it"))
                continue
            cards += 1
            if card_key in seen_ids:
                problems.append(
                    _err(label, "duplicate card id, the app keeps only the first one")
                )
            seen_ids.add(card_key)
            _check_card(label, card_data, check, problems, media_base)
    return _Result(problems, cards, categories, tuple(disabled))


_MEDIA_FILE_FIELDS = ("audio", "image")


def _check_path(
    label: str, value: str, media_base: Path, problems: list[_Problem]
) -> None:
    """Media strings must name an existing regular file (not a folder)."""
    target = media_base / value  # absolute values replace the base as usual
    if not target.exists():
        problems.append(_err(label, f"no such file: {value}"))
    elif not target.is_file():
        problems.append(_err(label, f"not a file: {value}"))


def _check_card(
    label: str,
    data: dict[str, Any],
    check: str,
    problems: list[_Problem],
    media_base: Path,
) -> None:
    """Faces plus, for ``all``/``other``, the card-level fields."""
    face_fields = _CHECKS[check]
    for side in ("front", "back"):
        face = data.get(side)
        prefix = f"{label}/{side}"
        if not isinstance(face, dict):
            if face is None:
                problems.append(_err(label, f"missing {side} block, the app would skip the card"))
            else:
                problems.append(_err(label, f"{side} is not an object, the app would skip the card"))
            continue
        face_broken = _missing_media(face)
        if face_broken:
            problems.append(_err(prefix, "has neither text, audio nor image, the app would skip the card"))
        warned_empty_text = False
        for field in face_fields:
            if field not in face:
                continue
            value = face[field]
            if not isinstance(value, str):
                problems.append(
                    _err(f"{prefix}/{field}", f"must be a string, got {_type_name(value)}")
                )
            elif value == "":
                if field == "text":
                    warned_empty_text = True
                problems.append(_warn(f"{prefix}/{field}", "empty string counts as absent"))
            elif field in _MEDIA_FILE_FIELDS:
                _check_path(f"{prefix}/{field}", value, media_base, problems)
        if (
            not face_broken
            and "text" in face_fields
            and _opt_str(face.get("text")) is None
            and not warned_empty_text
        ):
            if side == "back":
                problems.append(_warn(prefix, "no text; the answer cannot be shown in v1 exercises"))
            else:
                problems.append(_warn(prefix, "no text; card cannot be used by the text-only exercises"))
    if check in ("all", "other"):
        _check_other(label, data, problems)


def _check_other(
    label: str, data: dict[str, Any], problems: list[_Problem]
) -> None:
    """last-reviewed, the grade counters, score, and the direction counters."""
    if "last-reviewed" in data:
        raw = data["last-reviewed"]
        if not isinstance(raw, str):
            problems.append(
                _err(f"{label}/last-reviewed", f"must be an ISO 8601 string, got {_type_name(raw)}")
            )
        elif _parse_timestamp(raw) is None:
            problems.append(_err(f"{label}/last-reviewed", "not ISO 8601"))
    for field in _OTHER_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if not _is_int(value):
            problems.append(_err(f"{label}/{field}", f"must be an integer, got {_type_name(value)}"))
        elif value < 0:
            problems.append(_err(f"{label}/{field}", f"must be >= 0, got {value}"))
    if "score" in data:
        value = data["score"]
        if not _is_int(value):
            problems.append(_err(f"{label}/score", f"must be an integer, got {_type_name(value)}"))
        elif value not in _SCORE_RANGE:
            problems.append(_err(f"{label}/score", f"must be within 0-100, got {value}"))


def _report_file(result: _Result, prefix: str) -> tuple[int, int]:
    """Print one file's problems and its summary; return errors, warnings."""
    for problem in result.problems:
        if problem.label:
            print(f"{prefix}: {problem.label}: {problem.severity}: {problem.message}")
        else:
            print(f"{prefix}: {problem.severity}: {problem.message}")
    errors = sum(1 for problem in result.problems if problem.severity == "error")
    warnings = len(result.problems) - errors
    summary = f"{errors} error(s), {warnings} warning(s)"
    if result.cards:
        summary += f", {result.cards} cards in {result.categories} categories"
    if result.disabled:
        summary += f"; disabled: {', '.join(result.disabled)}"
    print(f"{prefix}: {summary}")
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv:
        print(_USAGE, file=sys.stderr)
        return 2
    if "-h" in argv or "--help" in argv:
        print(__doc__.strip())
        return 0
    check = "all"
    files = argv
    if argv[0] in _CHECKS:
        check, files = argv[0], argv[1:]
    if not files:
        print(_USAGE, file=sys.stderr)
        return 2
    total_errors = 0
    total_warnings = 0
    for raw in files:
        path = Path(raw)
        result = _validate_file(path, check)
        errors, warnings = _report_file(result, str(path))
        total_errors += errors
        total_warnings += warnings
    state = "FAILED" if total_errors else "OK"
    print(
        f"{state}: {total_errors} error(s), {total_warnings} warning(s) in {len(files)} file(s)"
    )
    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
