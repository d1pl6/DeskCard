"""Optional file logging for normal app operations."""

from __future__ import annotations

import logging
import logging.handlers

try:  # imported as src.debug_log
    from . import app_preferences
except ImportError:  # started as a script from src/ui
    import app_preferences

_LOGGER = logging.getLogger("deskcard")
_LOGGER.propagate = False
_HANDLER: logging.Handler | None = None


def configure_debug_log(enabled: bool) -> None:
    """Attach or detach the log file according to the preference."""
    global _HANDLER
    if not enabled:
        if _HANDLER is not None:
            _LOGGER.removeHandler(_HANDLER)
            _HANDLER.close()
            _HANDLER = None
        _LOGGER.setLevel(logging.WARNING)
        return
    if _HANDLER is not None:
        return
    target = app_preferences.debug_log_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            target, maxBytes=1_000_000, backupCount=1, encoding="utf-8",
        )
    except OSError:
        return
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
    ))
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.DEBUG)
    _HANDLER = handler
    _LOGGER.debug("debug log enabled")


def log_debug(message: str) -> None:
    """Write one debug line when logging is enabled."""
    _LOGGER.debug(message)


def log_error(message: str) -> None:
    """Write one error line when logging is enabled."""
    _LOGGER.error(message)
