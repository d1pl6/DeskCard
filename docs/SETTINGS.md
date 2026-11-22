# Settings and preferences

Three stores hold different kinds of state. Keep them separate.

| Store | Written by | Holds |
| --- | --- | --- |
| Deck JSON | `save_config()` | Cards, scores, grade and direction counters, category `enabled` flags. See `docs/DECK_FORMAT.md`. |
| Settings file | main window **Save settings** | Global fields, per-exercise settings, category checkboxes, optional deck path. |
| `preferences.json` | Preferences dialog and runner | Global UI preferences, remembered files and window state, score deltas, debug-log toggle. Lives in the platform config dir, not beside the deck. |

## Settings file

```json
{
  "deck": "decks/demo.json",
  "categories": {"greetings": true},
  "global": {"delay": "30s", "session": "2", "batch": "10", "jitter": "50"},
  "exercises": {
    "anki": {
      "enabled": true,
      "advanced": false,
      "settings": {"prompt_type": ["text_only"], "other_score": "0-99"}
    }
  }
}
```

`exercises` may contain `anki`, `choose`, `connect` and `write`. Missing keys fall
back to the defaults below. `advanced` only controls which blocks are visible;
`enabled` decides whether the exercise runs. A relative `deck` path resolves
against the settings file. `normalize_settings()` validates the whole structure
and raises `SettingsError` for a malformed value; Start is blocked with the error
message.

### Global fields

| Key | Default | Meaning |
| --- | --- | --- |
| `delay` | `1m` | Wait before each batch, including the first. `0`/empty = immediate. Jitter applies here. |
| `session` | `""` | Number of **batches**, not cards. Empty = unlimited. |
| `batch` | `1` | Cards per batch. Empty = `1`. |
| `jitter` | `0` | Percent randomness on the pre-batch delay (`50` → ±50%). Empty = `0`, max 100. |

### Per-exercise fields

| Key | Default | Rules |
| --- | --- | --- |
| `prompt_type` | `["text_only"]` | List of content modes shown before answering. |
| `answer_prompt` | `["text_only"]` | List of content modes shown after answering. |
| `prompt_sub` / `answer_sub` | `always` / `after` | `always`, `after`, `never`. |
| `prompt_listens` | `0` | Number of extra prompt replays, not a duration. |
| `answer_choices` | `5` | Minimum 2. |
| `answer_connections` | `5` | 2–10. |
| `answer_time` | `0` | Answer time limit; `0`/empty = no limit. |
| `other_direction` | `normal` | `normal`, `reverse`, `random`. |
| `other_score` | `0-99` | Card-selection filter, not points. |
| `random_score` | `10` | Adds `0..N` to the ordering score; `0` = exact lowest-score order. Max 100. |
| `other_close_time` | `3s` | Delay before the window closes after a result; never jittered. `0` = immediate. |
| `other_repeat` | `false` | Repeat until correct; blocks `other_attempts`. |
| `other_attempts` | `1` | Attempts before a wrong result; empty means `1` and is required when `other_repeat` is on. |

Content modes: `text_only`, `audio_only`, `image_only`, `text_audio`,
`text_image`, `audio_image`, `all`. See `docs/MEDIA.md` for selection and
rendering rules.

### Value syntax

- **Time**: `1h5m30s`, `61m30s`, `90s` or bare `90` (seconds). Units are
  lowercase `h`, `m`, `s`, in that order; spaces, uppercase and repeated units
  are invalid. Components may exceed 60. Empty means `0`/unlimited/immediate
  depending on the field.
- **Score filter**: `N` or `N-M` with inclusive bounds 0–100. Examples: `55`,
  `55-55`, `55-60`, `0-99`. Lists, open ends (`55-*`), reversed ranges and
  out-of-range values are rejected; an empty field blocks Start. A card at 100
  is not permanently learned: if its score drops into the range it appears
  again.
- **Integers**: non-negative digits only, with per-field minimums and maximums.
- **Booleans**: JSON `true`/`false`.

### Grades

Canonical keys and deltas (`src/config/loader.py`):

| Key | Delta |
| --- | --- |
| impossible | -5 |
| hard | 0 |
| medium | +2 |
| light | +5 |
| easy | +10 |

UI labels use the same names. Deltas are applied once per card per result and
the resulting score is clamped to 0–100. Non-Anki exercises use Easy for correct
and Impossible for wrong; partial success counts as wrong. The **Score change**
preference overrides the per-grade deltas; it does not change the 0–100 score
range.

## App preferences

`src/app_preferences.py` stores these in `preferences.json`:

- Linux: `$XDG_CONFIG_HOME/DeskCard/preferences.json`, otherwise
  `~/.config/DeskCard/preferences.json`
- Windows: `%APPDATA%\DeskCard\preferences.json`
- macOS: `~/Library/Application Support/DeskCard/preferences.json`

An existing `~/.deskcard/preferences.json` is copied to the new location on
first load. The dialog has **Exercise**, **Window**, **Startup**, **Images** and
**Advanced** tabs; every control has a tooltip, and Save and Reset are available
on every tab. Reset restores all fields, including score deltas, remembered files
and remembered window state; press Save to persist it. Changes such as the font
scale and debug-log toggle take effect when Save is pressed.

| Preference | Default | Notes |
| --- | --- | --- |
| Exercise opacity | 100% | Range 10–100, applied after the exercise window is mapped. |
| Show Skip / Quit | on | Keyboard shortcuts still work when hidden. |
| Restrict closing exercise | off | Quit is disabled and window-manager close requests are ignored during exercises. |
| Confirm on quit/reset | on | Applies to main-window Quit/Reset and early exercise exit; natural session end does not ask. |
| Status toggles | off | `time passed:`, `cards in batch:`, `session batches:`; one shared `top`/`bottom` placement. |
| Remember geometry / position | off / off | Window sizes and virtual-desktop x/y positions. |
| Always on top during exercises | on | Preserves the previous topmost behavior. |
| Auto-load last deck / settings | off / off | Settings are applied first; the deck loads only if the settings file did not supply one. Missing files are skipped with a status note. |
| Image display mode | `fit` | `fit`, `stretch` or `original`. |
| Max image size | `0` × `0` | Width/height cap; `0` = no cap. Can only shrink a screen's slot. |
| Font scale | 100% | 50–200%; scales fonts, padding, wrapping, slider lengths and window sizing. Saved changes apply immediately in already-open windows. |
| Enable debug log | off | Appends to `debug.log` beside `preferences.json`, rotating after ~1 MB. |
| Increase direction counter in normal/reverse modes | on | Otherwise only `random` increments the counters. |
| Default global settings | `1m` / `""` / `1` / `0` | Initial Delay, Batches, Cards and Jitter, validated with the same parser as settings files. |
| Score change | -5 / 0 / +2 / +5 / +10 | Per-grade deltas shown on Anki's grade buttons. |
| Remembered files | empty | Last deck, last settings file and up to 10 recent decks, shown and clearable in Preferences. The main window offers the recent decks as a read-only drop-down that loads the selected one. |
