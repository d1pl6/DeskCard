DeskCard - flashcard app that overlays on top of your screen until you finish the exercise

## Table of Contents
- [Exercises](#exercises)
    - [Anki](#anki)
    - [Choose](#choose)
    - [Connect](#connect)
    - [Write](#write)
- [Global settings](#global-settings)
- [Install](#install)
- [Usage](#usage)
- [Uninstall](#uninstall)
- [License](#license)

## Exercises
### Anki
Classic (almost) Anki.
Answer in your head, click **Show answer**, then choose how difficult it was to answer.

| Button      | Score change |
| ----------- | ------------ |
| Impossible  | -5           |
| Hard        | 0            |
| Medium      | +2           |
| Light       | +5           |
| Easy        | +10          |

### Choose
Pick the answer from the choices, then click **Confirm** (or press Enter).

*Can't be less than 2 choices

### Connect
Connect left side with right one, then click **Confirm** (or press Enter).

*Can't be less than 2 connections

### Write
Write answer, then click **Confirm** (or press Enter).

*An empty answer counts as wrong.
*In answer settings is for what you will see after writing answer

#### Settings
- Enabled -                     Run this exercise in the session.                                       TOOLTIP
- Advanced -                    Show experimental and fine-tuning options.                              TOOLTIP
- Show Sub -                    Show "sub" from deck                                                    TOOLTIP
- Difficulty -                  Controls how hard a card is: re-listens, choice count, time limit.      TOOLTIP
- Re-listens allowed -          How many times the prompt can be replayed before answering.             TOOLTIP
- Answer choices -              How many options to show. Minimum 2.                                    TOOLTIP
- Number of connections	-       How many pairs to connect. From 2 to 10.                                TOOLTIP
- Answer time limit -           Seconds to answer before the card counts as wrong. Empty = no limit.    TOOLTIP
- Highlight wrong characters -  Mark mismatched characters after answering.                             TOOLTIP, SHOWCASE
- Highlight wrong words	-       Mark mismatched words after answering.                                  TOOLTIP, SHOWCASE
- Delay before window closes -  Seconds the answer stays on screen after a mistake.                     TOOLTIP
- Repeat until correct -        The card is not dismissed until the answer has no mistakes.             TOOLTIP
- Max attempts -                Tries before the card is scored as wrong.                               TOOLTIP
- Prompt content -              What is shown before you answer: text, audio, image, or a combination.  TOOLTIP
- Score -                       Points (0–100).                                                         TOOLTIP
- Direction -                   Normal: prompt→answer. Reverse: answer→prompt. Random: per card.        TOOLTIP, SHOWCASE

## Global settings
- Delay (Delay between cards) {T} - Time between cards, e.g. 30s, 1m30s, 3h.
- Cards in session {N} - Total cards shown in the session.
- Cards in batch {N} - Cards shown before the delay is applied again.
- Delay Jitter {N} - % randomness added to the delay, e.g. 50% of 100s → 50–150s.

## Install
Python 3.10+

For audio install `pygame-ce` (`python-pygame`, `python-pygame-ce`, depends on your distro)

On linux install `tkinter` if it doesn't come with python.

```sh
pip install pygame-ce
```

## Usage
```sh
python -m app
```

Use `python tools/validator.py` to see missing lines in .json.
```bash
python tools/validator.py all example.json

# Output:
example.json: greetings/1/back/audio: error: no such file: desks/audio/es/greetings/hola.mp3
example.json: greetings/1/back/image: error: no such file: desks/image/greetings/hello.png
example.json: greetings/2/front/audio: error: no such file: adios.mp3 file not found - error
example.json: greetings/2/back/image: error: no such file: image not found - error
example.json: new category/category: error: missing front block, the app would skip the card
example.json: new category/category: error: missing back block, the app would skip the card
example.json: 6 error(s), 0 warning(s), 3 cards in 2 categories
FAILED: 6 error(s), 0 warning(s) in 1 file(s)
```

## Uninstall
Saved configs, desks, DeskCard folder.

`pygame-ce`, `python`.

## License
DeskCard is licensed under the GPL-2.0-or-later. If you did not get a copy, please see https://www.gnu.org/licenses/.