# Media

Audio and images are optional. `pygame-ce` provides audio, Pillow provides
images; without a library, that medium is unavailable but the rest of the app
keeps working.

## Availability and content choices

`src/ui/media.py` exposes `audio_available()` and `image_available()`. The main
window checks them together with the loaded deck's warnings: a prompt/answer
content choice is unchecked and disabled when the deck reports errors for that
medium or its backend is missing. The tooltip states the reason. Loading a clean
deck or installing the library restores the choice.

Content modes select and filter at the same time:

- A single mode (`text_only`, `audio_only`, `image_only`) requires that medium.
  A card without it is skipped for that exercise.
- A combined mode (`text_audio`, `text_image`, `audio_image`, `all`) renders the
  requested parts that exist and shows a footer warning naming the missing ones.
  If none exist, the card is skipped.
- Extra parts present on the card are not rendered unless requested.
- A missing media file counts as missing content. Media paths are resolved
  against the deck file's directory; see `docs/DECK_FORMAT.md`.

## Audio

- Prompt audio plays automatically once when a card opens. `prompt_listens`
  is the number of extra replays the ▶ button allows (`0` = none). In Connect
  this budget is **per pair**, not shared across the card.
- Answer audio plays only when clicked.
- Playback stops when the card window is destroyed and when a retry starts.
- Decode failures and missing audio devices are raised as readable errors by
  `play_audio()` and shown as footer warnings instead of crashing the screen.
- Tests set `SDL_AUDIODRIVER=dummy` and `PYGAME_HIDE_SUPPORT_PROMPT=1` before
  importing the media helpers.

## Images

- `fit` (default) keeps the aspect ratio inside the slot, `stretch` fills it,
  and `original` keeps the native size, honouring the global cap and
  centre-cropping larger images to the slot.
- The global max-image preference can only shrink the screen's slot size; a
  larger value never enlarges it.
- `PhotoImage` objects are cached by path, size, display mode and cap, so
  repeated cards do not reload the file, and Tk never garbage-collects an image
  still shown in a label. The cache is a bounded LRU (32 entries); changing the
  image preferences clears it.
- A file that cannot be decoded, or no Pillow at all, shows a dark placeholder.
