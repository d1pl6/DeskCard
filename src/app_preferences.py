"""App-level preferences stored as JSON.

These are global UI preferences, not deck data or exercise/session settings.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

APP_DIR_NAME = "DeskCard"
LEGACY_PREFERENCES_PATH = Path.home() / ".deskcard" / "preferences.json"


def config_directory(platform: str | None = None) -> Path:
    """Return the platform's config directory for DeskCard."""
    system = platform or sys.platform
    if system == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata and Path(appdata).is_absolute():
            return Path(appdata) / APP_DIR_NAME
        return Path.home() / "AppData" / "Roaming" / APP_DIR_NAME
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg) / APP_DIR_NAME
    return Path.home() / ".config" / APP_DIR_NAME


DEFAULT_PREFERENCES_PATH = config_directory() / "preferences.json"
PREFERENCES_PATH = DEFAULT_PREFERENCES_PATH

GRADES = ("impossible", "hard", "medium", "light", "easy")
STATUS_POSITIONS = ("top", "bottom")
IMAGE_DISPLAY_MODES = ("fit", "stretch", "original")

DEFAULT_SCORE_DELTAS = {
    "impossible": -5,
    "hard": 0,
    "medium": 2,
    "light": 5,
    "easy": 10,
}

DEFAULT_PREFERENCES: dict[str, Any] = {
    "exercise_opacity": 100,
    "show_skip_quit": True,
    "restrict_exercise_close": False,
    "confirm_quit_reset": True,
    "show_time_passed": False,
    "show_cards_in_batch": False,
    "show_session_batches": False,
    "status_position": "top",
    "remember_geometry": False,
    "remember_position": False,
    "exercise_always_on_top": True,
    "auto_load_last_deck": False,
    "auto_load_last_settings": False,
    "last_deck": "",
    "last_settings": "",
    "image_display_mode": "fit",
    "max_image_width": 0,
    "max_image_height": 0,
    "font_scale": 100,
    "enable_debug_log": False,
    "count_all_directions": True,
    "default_global_settings": {
        "delay": "1m", "session": "", "batch": "1", "jitter": "0",
    },
    "recent_decks": [],
    "score_deltas": dict(DEFAULT_SCORE_DELTAS),
    "windows": {},
}


def _copy_defaults() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_PREFERENCES))


def debug_log_path() -> Path:
    """Return the log file beside the active preferences file."""
    return PREFERENCES_PATH.parent / "debug.log"


def migrate_legacy_preferences() -> None:
    """Copy an existing home-directory preferences file into the config dir."""
    if PREFERENCES_PATH != DEFAULT_PREFERENCES_PATH:
        return
    if PREFERENCES_PATH.exists() or not LEGACY_PREFERENCES_PATH.is_file():
        return
    try:
        PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
        PREFERENCES_PATH.write_bytes(LEGACY_PREFERENCES_PATH.read_bytes())
    except OSError:
        return


def load_preferences(path: str | Path | None = None) -> dict[str, Any]:
    """Read preferences, falling back to defaults for missing or bad values."""
    if path is None:
        migrate_legacy_preferences()
    target = Path(path) if path is not None else PREFERENCES_PATH
    result = _copy_defaults()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return result
    if not isinstance(data, dict):
        return result

    opacity = data.get("exercise_opacity", result["exercise_opacity"])
    try:
        result["exercise_opacity"] = min(100, max(10, int(opacity)))
    except (TypeError, ValueError):
        pass
    for key in (
        "show_skip_quit", "restrict_exercise_close", "confirm_quit_reset",
        "show_time_passed", "show_cards_in_batch", "show_session_batches",
        "remember_geometry", "remember_position",
        "exercise_always_on_top", "auto_load_last_deck",
        "auto_load_last_settings", "enable_debug_log",
        "count_all_directions",
    ):
        value = data.get(key)
        if isinstance(value, bool):
            result[key] = value

    if data.get("status_position") in STATUS_POSITIONS:
        result["status_position"] = data["status_position"]

    for key in ("last_deck", "last_settings"):
        value = data.get(key)
        if isinstance(value, str):
            result[key] = value

    if data.get("image_display_mode") in IMAGE_DISPLAY_MODES:
        result["image_display_mode"] = data["image_display_mode"]

    for key in ("max_image_width", "max_image_height"):
        try:
            result[key] = max(0, min(4096, int(data.get(key, 0))))
        except (TypeError, ValueError):
            pass

    try:
        result["font_scale"] = max(50, min(200, int(data.get("font_scale", 100))))
    except (TypeError, ValueError):
        pass

    defaults = data.get("default_global_settings")
    if isinstance(defaults, dict):
        for key in result["default_global_settings"]:
            value = defaults.get(key)
            if isinstance(value, str):
                result["default_global_settings"][key] = value[:120]

    value = data.get("recent_decks")
    if isinstance(value, list):
        paths = []
        for item in value:
            if isinstance(item, str) and item not in paths:
                paths.append(item)
        result["recent_decks"] = paths[:10]

    deltas = data.get("score_deltas")
    if isinstance(deltas, dict):
        for grade in GRADES:
            if grade in deltas:
                try:
                    result["score_deltas"][grade] = max(
                        -100, min(100, int(deltas[grade]))
                    )
                except (TypeError, ValueError):
                    pass

    windows = data.get("windows")
    if isinstance(windows, dict):
        result["windows"] = {
            name: values for name, values in windows.items()
            if isinstance(values, dict)
        }
    return result


def save_preferences(preferences: dict[str, Any],
                     path: str | Path | None = None) -> None:
    """Write preferences atomically, creating the parent directory if needed."""
    target = Path(path) if path is not None else PREFERENCES_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(preferences, indent=2, ensure_ascii=False) + "\n"
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(payload, encoding="utf-8")
    os.replace(temp, target)


def clear_remembered_files(preferences: dict[str, Any]) -> None:
    """Forget remembered decks/settings without touching other preferences."""
    preferences["last_deck"] = ""
    preferences["last_settings"] = ""
    preferences["recent_decks"] = []


def remember_recent_deck(preferences: dict[str, Any], path: str | Path) -> None:
    """Put a successfully loaded deck first in the recent list (max 10)."""
    value = str(path)
    paths = [item for item in preferences.get("recent_decks", [])
             if isinstance(item, str) and item != value]
    preferences["recent_decks"] = [value, *paths][:10]


def window_geometry(window) -> dict[str, int]:
    """Read size and position from a Tk window."""
    window.update_idletasks()
    return {
        "width": max(1, window.winfo_width()),
        "height": max(1, window.winfo_height()),
        "x": window.winfo_rootx(),
        "y": window.winfo_rooty(),
    }


def apply_window_preferences(window, preferences: dict[str, Any], key: str) -> None:
    """Apply remembered size/position to a Tk window, when enabled."""
    saved = preferences.get("windows", {}).get(key)
    if not saved:
        return
    current = window_geometry(window)
    width = _positive_int(saved.get("width"))
    height = _positive_int(saved.get("height"))
    x = _integer(saved.get("x"))
    y = _integer(saved.get("y"))

    if preferences.get("remember_geometry") and width and height:
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        width = min(width, screen_w)
        height = min(height, screen_h)
        window.geometry(f"{width}x{height}+{current['x']}+{current['y']}")
    if preferences.get("remember_position") and x is not None and y is not None:
        window.geometry(f"+{x}+{y}")


def remember_window_preferences(window, preferences: dict[str, Any], key: str) -> None:
    """Update ``preferences`` with the current window state."""
    geometry = window_geometry(window)
    saved = dict(preferences.get("windows", {}).get(key, {}))
    if preferences.get("remember_geometry"):
        saved["width"] = geometry["width"]
        saved["height"] = geometry["height"]
    if preferences.get("remember_position"):
        saved["x"] = geometry["x"]
        saved["y"] = geometry["y"]
    if saved:
        preferences.setdefault("windows", {})[key] = saved


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
