# AGENTS.md

DeskCard is a flashcard app for desktops built with tkinter.

## Autonomy

- Complete implementation, verification and review before returning the work. Make routine implementation decisions yourself; do not make the developer supervise steps already authorized by the task or this file
- Ask only when missing information materially changes the result and cannot reasonably be resolved from the project or conversation. Continue independent work while waiting

## Architecture

- Keep study rules in `src/session.py`: it is plain Python and must not import tkinter. UI code renders cards and reports results; it does not decide session rules
- UI helpers live in `src/ui/helpers/` (`blocks.py`, `theme.py`, `tooltips.py`). See `docs/ARCHITECTURE.md` for the module map, data flow and extension points
- UI modules support both package imports and bare-script execution; keep the `try/except ImportError` import fallback when editing them
- Read the matching guide before touching data or media behavior: `docs/DECK_FORMAT.md`, `docs/SETTINGS.md`, `docs/MEDIA.md`

## Testing

- Run headless tests for non-UI functions; keep real Tk windows out of tests where possible. Tk-dependent tests are skipped without `DISPLAY`
- Try to reproduce described issue before looking inside the code
- Use `python -m pytest` from the repository root. Deck-loading tests use `example.json` (see `docs/TESTING.md`), not `unsorted.json`; loader tests inject preferences so they do not read the machine's saved settings

## Comments

- Don't mention any files or previous issues
- Mention library or platform-specific cases only

## Docs

Read the matching guide before starting:

- `docs/UI.md` basic UI rules
- Reference: `docs/ARCHITECTURE.md`, `docs/SETTINGS.md`, `docs/DECK_FORMAT.md`, `docs/TESTING.md`

Docs describe how things are and how to do them, not how they got there: git keeps the history. Update a guide when you change what it describes, and don't add investigation logs
