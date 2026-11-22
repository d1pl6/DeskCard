# Testing

## Rule

Tests run headlessly: no real Tk windows and no display server. Test plain-Python
functions (session engine, parsers, preference logic, pure UI helpers). Where a
UI helper's logic must be exercised, use simple stand-ins for widgets. Reproduce
a reported issue in a test before digging into the implementation.

## Running

From the repository root:

```sh
python -m pytest
```

`pyproject.toml` sets `testpaths = ["tests"]`. Tests in `tests/` use `unittest`
classes and can also be run with `python -m unittest discover -s tests`.

## Fixtures

- `tests/test_session.py` writes a small temporary deck and drives `Session`
  with explicit settings; it covers parsing, card pools, ordering, direction
  counters, delays, results and write-back.
- Deck-loading tests use **`example.json`** in the repository root: two valid
  cards in two categories, plus the broken `new category/category` card whose
  missing `front` and `back` blocks produce two warnings. The two valid cards
  also reference missing media files, so a full load reports six warnings in
  total. `unsorted.json` is not a test fixture.
- `tests/test_media.py` sets dummy audio environment variables before importing
  `src.ui.media`, so playback tests do not need an audio device.
- Preferences, tooltip and Anki/Connect settings tests assert behavior through
  plain data or lightweight stand-ins; they never open a Tk window.

## What to assert

- Session and parser behavior: `SettingsError` for malformed values, event order
  (`Delay` before each batch), lowest-score ordering, score clamping and
  write-back, and direction counters only for presented cards.
- Deck-loading behavior: warnings and skipped cards rather than a failed file,
  and disabled-category cards retained in `Config.cards` but absent from
  `active_cards()`.
- Keep assertions about behavior, not implementation logs. Guides describe how
  things are; investigation notes do not belong in `docs/`.
