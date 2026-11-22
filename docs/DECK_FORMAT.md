# Deck format

A deck is a UTF-8 JSON file. The repository's `example.json` is a small sample.

## Shape

```json
{
  "$version": 1,
  "greetings": {
    "enabled": true,
    "$version": 1,
    "1": {
      "front": {"text": "Hello", "sub": "/hɛˈloʊ/", "audio": "hello.mp3"},
      "back":  {"text": "Hola", "image": "images/hello.png"},
      "score": 100,
      "easy": 21, "light": 0, "medium": 0, "hard": 0, "impossible": 0,
      "last-reviewed": "2026-11-18T03:50:24Z",
      "normal": 5, "reverse": 5
    }
  }
}
```

- Top level: an object of categories. `$version` at this level is a memo and is
  not a category.
- Category: `enabled` is a boolean (absent means enabled) and `$version` is an
  integer. Every other key is a card id.
- Card ids must be unique across the whole deck. The second occurrence is
  skipped with a warning.
- Card: `front` and `back` objects are required. Optional card fields are
  `last-reviewed` (ISO 8601, a trailing `Z` is accepted), the grade counters
  `easy`, `light`, `medium`, `hard`, `impossible`, `score`, and the direction
  counters `normal` and `reverse`.
- Face: `text`, `sub`, `audio` and `image` are optional strings. A present but
  empty string counts as absent. Each face needs at least one of `text`,
  `audio` or `image`; otherwise the card is skipped with a warning.
- A face without `text` stays valid but warns, because exercises that request
  text will skip that card. Audio/image content modes can still use it. Choose
  and Write always need text in the answer face.
- `audio` and `image` are paths. Relative paths resolve against the **deck
  file's directory**, not the working directory; absolute paths work too. A
  missing file or a directory produces a warning and counts as missing content.
- `#` comments outside JSON strings are stripped on load. They are not written
  back.

## Validation and write-back

`load_config()` collects warnings instead of failing on bad cards: wrong field
types are reported, negative counters are zeroed and out-of-range scores are
clamped. An invalid `last-reviewed` value is reported but kept, so write-back
never silently loses data. Structurally broken cards (missing faces, no content,
duplicate ids) are skipped. Only an unreadable file, invalid JSON or a non-object
top level raises `ConfigError`.

`Config.cards` holds every valid card in file order, including cards in disabled
categories; `Config.active_cards()` returns only enabled-category cards. The
parsed tree is the source of truth: `CardRecord` objects are typed views over it,
so unknown fields and key order survive a re-dump. `save_config()` writes to a
`.tmp` file beside the target and renames it over the original, so an interrupted
write cannot corrupt the deck.

## Checking a deck

```sh
python tools/validator.py [all|text|sub|audio|image|other] FILE...
```

`all` is the default. The check word selects which fields are verified; deck
structure is always checked, because broken structure makes the app silently
drop cards. A present-but-empty string and text missing while audio or image
covers the face are tolerated warnings. Disabled categories are verified too.
The exit code is 1 if any file has an error, 0 with warnings alone. See
`python tools/validator.py --help` for details.
