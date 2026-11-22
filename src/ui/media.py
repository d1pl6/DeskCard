"""Shared media helpers for the exercise screens.

Audio uses pygame's mixer; images use Pillow when available. The helpers keep
PhotoImage objects alive in a cache so Tk never garbage-collects them while a
label is still displaying them.
"""

import os
import tkinter as tk

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

try:  # imported as src.ui.media
    from ..app_preferences import IMAGE_DISPLAY_MODES
except ImportError:  # started as a script from src/ui
    from app_preferences import IMAGE_DISPLAY_MODES

try:  # Pillow is optional; image-only cards degrade to a placeholder.
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - exercised only on minimal installs
    Image = None
    ImageTk = None


_AUDIO_INITIALIZED = False
_SOUND = None
_IMAGE_CACHE = {}
_IMAGE_MODE = "fit"
_IMAGE_MAX = (0, 0)


def configure_images(mode="fit", max_width=0, max_height=0):
    """Set the shared image display mode and global size cap."""
    global _IMAGE_MODE, _IMAGE_MAX
    if mode not in IMAGE_DISPLAY_MODES:
        mode = "fit"
    try:
        maximum = (max(0, int(max_width)), max(0, int(max_height)))
    except (TypeError, ValueError):
        maximum = (0, 0)
    if mode == _IMAGE_MODE and maximum == _IMAGE_MAX:
        return
    _IMAGE_MODE = mode
    _IMAGE_MAX = maximum
    _IMAGE_CACHE.clear()


def _effective_size(max_size):
    """Apply the global cap without ever enlarging a screen's own slot."""
    width, height = int(max_size[0]), int(max_size[1])
    cap_width, cap_height = _IMAGE_MAX
    if cap_width:
        width = min(width, cap_width)
    if cap_height:
        height = min(height, cap_height)
    return max(1, width), max(1, height)


def play_audio(path):
    """Play an audio file, stopping whatever was playing before it.

    Raises :class:`RuntimeError` with a readable message when pygame cannot
    open the device or decode the file, so exercise screens can show a warning
    instead of failing silently.
    """
    global _AUDIO_INITIALIZED, _SOUND
    if not path:
        return False
    try:
        if not _AUDIO_INITIALIZED:
            pygame.mixer.init()
            _AUDIO_INITIALIZED = True
        stop_audio()
        _SOUND = pygame.mixer.Sound(str(path))
        _SOUND.play()
        return True
    except pygame.error as error:
        raise RuntimeError(f"cannot play audio {path}: {error}") from error


def stop_audio():
    """Stop current playback; safe to call when nothing is playing."""
    if _AUDIO_INITIALIZED:
        pygame.mixer.stop()
    global _SOUND
    _SOUND = None


def audio_busy():
    return _AUDIO_INITIALIZED and pygame.mixer.get_busy()


def load_image(path, max_size=(240, 150)):
    """Return a cached :class:`PhotoImage` for ``path``.

    The shared display mode decides how the image relates to ``max_size``:
    ``fit`` keeps its aspect ratio, ``stretch`` fills the slot, and ``original``
    leaves small images alone while centre-cropping larger ones to the slot.
    A global max-image preference can only shrink the slot size.
    """
    if not path or Image is None or ImageTk is None:
        return None
    size = _effective_size(max_size)
    key = (str(path), size, _IMAGE_MODE, _IMAGE_MAX)
    if key in _IMAGE_CACHE:
        return _IMAGE_CACHE[key]
    try:
        with Image.open(path) as source:
            image = source.convert("RGBA")
            if _IMAGE_MODE == "stretch":
                image = image.resize(size, Image.Resampling.LANCZOS)
            elif _IMAGE_MODE == "fit":
                image.thumbnail(size, Image.Resampling.LANCZOS)
            else:  # original: keep native size, honour global cap, crop to slot
                cap_width, cap_height = _IMAGE_MAX
                cap = (cap_width or image.width, cap_height or image.height)
                if cap != (image.width, image.height):
                    image.thumbnail(cap, Image.Resampling.LANCZOS)
                if image.width > size[0] or image.height > size[1]:
                    left = max(0, (image.width - size[0]) // 2)
                    top = max(0, (image.height - size[1]) // 2)
                    image = image.crop((
                        left, top,
                        min(image.width, left + size[0]),
                        min(image.height, top + size[1]),
                    ))
            photo = ImageTk.PhotoImage(image)
    except (OSError, ValueError):
        return None
    _IMAGE_CACHE[key] = photo
    return photo


def image_frame(parent, path, width=240, height=150, max_size=(240, 150),
                bg="#2a2a2a", font=None):
    """Build a bordered frame holding a photo, or a dark "image" placeholder."""
    frame = tk.Frame(
        parent, bg=bg, width=width, height=height,
        highlightthickness=1, highlightbackground="#4f4f4f",
    )
    frame.pack_propagate(False)
    photo = load_image(path, max_size)
    if photo is None:
        label = tk.Label(frame, text="image", bg=bg, fg="#666666", font=font)
    else:
        label = tk.Label(frame, image=photo, bg=bg)
        label.image = photo
    label.place(relx=0.5, rely=0.5, anchor="center")
    return frame
