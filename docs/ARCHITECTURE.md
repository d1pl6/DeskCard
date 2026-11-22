# Architecture

DeskCard has three distinct data stores and four layers. The study rules live in
one plain-Python module; tkinter code only renders and reports results.

## Layers and modules

| Layer | Modules | Responsibility |
| --- | --- | --- |
| Entry / main window | `app.py`, `src/ui/loader.py` | Collect the deck, settings and category checkboxes; start a session. |
| Deck data | `src/config/loader.py`, `src/errors.py` | Parse, validate and atomically write back deck JSON. |
| Session engine | `src/session.py` | Own all study rules. Plain Python: **no tkinter**, so it is testable headlessly. |
| Session runner | `src/ui/runner.py` | Turn engine events into windows and user actions. Owns no study rules. |
| Exercise screens | `src/ui/anki.py`, `choose.py`, `connect.py`, `write.py`, `media.py` | Render one card, report a grade or a binary result. |
| UI and preferences helpers | `src/ui/helpers/blocks.py`, `src/ui/helpers/theme.py`, `src/ui/helpers/tooltips.py`, `src/ui/preferences.py`, `src/ui/about.py`, `src/app_preferences.py`, `src/debug_log.py` | Shared controls, tooltips, theme, app preferences and optional logging. |

`docs/DECK_FORMAT.md`, `docs/SETTINGS.md` and `docs/MEDIA.md` describe the data
and media rules these layers implement.

## Flow

```text
Main window (Start)
   |  settings + category checkboxes
   v
Session(config, settings)          src/session.py
   |  Delay | Presentation events
   v
SessionRunner                      src/ui/runner.py
   |  one exercise window per card
   v
Anki / Choose / Connect / Write
   |  grade or correct/wrong
   v
Session.record() -> save_config() -> next card / delay / quit
```

A presentation carries a typed spec (`AnkiCardSpec`, `ChooseCardSpec`,
`ConnectCardSpec`, `WriteCardSpec`), the card ids it uses and any warnings.
`SessionRunner` materializes the event list once (`events = list(session)`) and
reads `session.warnings` afterwards, because warnings are added while the
generator runs.

## Running

Entry points: `python -m app`, `python app.py`, `python -m src.ui.loader`,
`python src/ui/loader.py`, and the `deskcard` console script. Individual
exercise screens can also be run directly for UI work.

UI modules support both package imports and bare-script execution with:

```python
try:
    from .helpers.theme import ui
except ImportError:  # started as a script from src/ui
    from helpers.theme import ui
```

Keep this fallback when editing UI modules; the direct-script entry points
depend on it. Deck-related code uses the equivalent `src.config` / `config`
fallback.

## Session rules

### Settings and card pools

- `normalize_settings()` validates every raw setting and raises `SettingsError`
  on a malformed value; the main window blocks Start instead of guessing.
- `Config.cards` keeps **all** valid cards, including cards in disabled
  categories. `active_cards()` filters them; the session filters again by
  category state and by the exercise's score range.
- Category states from a settings file override the deck's `enabled` flags.
  Clicking a checkbox changes only the UI; pressing Start writes the resulting
  checkbox states back into the deck JSON.
- Cards are shuffled before a stable sort by score, so the lowest-score cards
  come first in **all four** exercises and equal scores are not in file order.
  `random_score` adds `0..N` to the ordering score only.
- Direction is `normal`, `reverse` or `random`. In `random`, equal counters give
  a 50/50 choice; otherwise a zero counter is excluded and the smaller counter
  wins (`1/2` → normal, `2/1` → reverse). `normal=50, reverse=0` therefore
  forces normal. Counters increment only for cards that reach a presentation;
  forced modes count too when the "Increase direction counter in
  normal/reverse modes" preference is on.
- Content modes filter both selection and rendering. A single mode requires
  that medium; a combined mode needs at least one requested part and reports
  the missing ones as warnings. Choose and Write additionally need text in
  `answer_prompt`. A missing media file counts as missing content.
- Choose needs at least two distinct answer texts and Connect at least two
  cards; otherwise that exercise is skipped with a warning.
- A delay comes before the first card and before every new batch. Jitter
  applies only to these delays, never to the close delay after a result.
  `session` counts batches and `batch` counts cards; an empty session is
  unlimited. If the deck cannot fill the session, it ends early with a warning,
  and finishing the session quits the app.

### Results

- `Session.record()` applies **one** delta per card, clamps the score to 0–100,
  increments that grade's counter, writes a UTC `last-reviewed` stamp and saves
  the deck. Custom deltas come from app preferences.
- Choose, Connect and Write report binary results: correct = Easy (+10), wrong
  = Impossible (-5). Partial success (three of four pairs, one wrong character)
  counts as wrong.
- Wrong answers retry without a score change until Max attempts is exhausted.
  With Repeat until correct on, retries continue indefinitely and no -5 is
  applied.
- Answer time expiry counts as wrong: Anki grades Impossible; the other screens
  reveal the answer and report a wrong result.
- `commit_visible()` keeps direction-counter changes only for presentations the
  runner actually displayed, then `finish()` persists them.

## Runner and shared exercise flow

- Delays are silent: they are scheduled with `after()` on the owner window.
- After a recorded result the screen locks, the configured close delay runs,
  and the runner advances. An intermediate wrong answer stays on screen for
  `RETRY_FEEDBACK_SECONDS` (0.7 s) before a retry.
- Exercise windows are non-transient: the owner is withdrawn during a session,
  and a transient child of a withdrawn window never becomes viewable.
- Restrict closing exercise disables Quit, makes its callback inert and ignores
  window-manager close requests. The main window is unaffected; the session
  ends only by finishing the deck.
- "Always on top", opacity, geometry and position come from app preferences.
- The status row is assembled from three independent toggles and one
  top/bottom placement. `time passed:` measures the current card, so it resets
  for each new card and aligns with the answer time limit.

## Exercises

- **Anki**: show front, reveal back, then self-grade with Impossible, Hard,
  Medium, Light or Easy. Prompt and answer content and Show Sub are
  configurable. With `Show Sub = after`, a prompt-side sub appears only after
  reveal; an answer-side sub appears with the answer, because the answer itself
  is already post-reveal.
- **Choose**: prompt above, choices below. Distractors are the answer texts of
  other enabled cards; the correct answer is shuffled in.
- **Connect**: 2–10 pairs from the pool. All pairs correct applies Easy to every
  card used in that round; any pair wrong applies Impossible to every card used.
  The delta is applied once per card, not per pair. There is no user-facing
  scoring-mode setting.
- **Write**: exact string equality, including capitalization. Wrong-character
  and wrong-word highlighting is visual feedback only (word mode takes visual
  precedence when both are on); grading stays exact.

## Extension points

- **New setting control**: add a `Block` subclass and a `BLOCK_TYPES` entry in
  `src/ui/helpers/blocks.py`, a schema entry in one of the section lists in
  `src/ui/loader.py`, a tooltip, and validation/defaults in
  `normalize_settings()` (`src/session.py`).
- **New exercise**: add its name to `EXERCISE_ORDER`, a spec dataclass and a
  `_build_spec()` branch in `src/session.py`, a screen module, its schema in
  `src/ui/loader.py`, and a branch in `SessionRunner._show()`.
- **New deck field**: extend the typed views in `src/config/loader.py` and the
  checks in `tools/validator.py`.
