"""Shared media helpers for the exercise screens.

Audio uses pygame's mixer; images use Pillow when available. The helpers keep
PhotoImage objects alive in a cache so Tk never garbage-collects them while a
label is still displaying them.
"""

import os
import tkinter as tk

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

try:  # Pillow is optional; image-only cards degrade to a placeholder.
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - exercised only on minimal installs
    Image = None
    ImageTk = None


_AUDIO_INITIALIZED = False
_SOUND = None
_IMAGE_CACHE = {}


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
    """Return a cached :class:`PhotoImage` scaled to fit ``max_size``.

    Returns ``None`` when Pillow is unavailable or the file cannot be opened.
    Callers keep the returned object referenced by the label; the module cache
    also protects it from garbage collection.
    """
    if not path or Image is None or ImageTk is None:
        return None
    key = (str(path), tuple(max_size))
    if key in _IMAGE_CACHE:
        return _IMAGE_CACHE[key]
    try:
        with Image.open(path) as source:
            image = source.convert("RGBA")
            image.thumbnail(tuple(max_size), Image.Resampling.LANCZOS)
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
