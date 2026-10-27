# Legends Farm Bot

A small Windows bot that farms **Raids** and the **Story mode** of a mobile fighting game played on a PC
emulator. It "looks" at the game window with OpenCV (screen recognition) and clicks like a person would.
Nothing is injected into the game.

> ⚠️ **Disclaimer** – unofficial project, not affiliated with the game's publisher. Automating a game is
> usually forbidden by its terms of service and **can get your account banned**. Use it at your own risk.

## Two separate bots

| Bot | Script | What it does | Launch with |
|---|---|---|---|
| **Story** | `farm.py` | Plays the story mode: skips dialogues, handles pop-ups, lets the game's AUTO button fight | `run_story.bat` |
| **Raid** | `farmraid.py` | Runs raids back to back, taps the battle cards, plays the Rising Rush QTE (reads the gauge and taps when it is full, auto-tuning its own tap delay) | `run_raid.bat` |

Run **only one at a time**. They are independent files that merely share the `templates/` folder.
**You do not need all the images for both:** each bot needs its own set (see below), so if you only want
raids, you only create the raid images.

## Installation (Windows)

1. Install [Python 3.10+](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"**.
2. Double-click `install.bat` (or run `pip install -r requirements.txt`).
3. Open the game in a **normal window** (not full screen) inside your emulator and do not resize it afterwards.
4. **Create your recognition images, once:**
   - story bot → double-click `create_images_story.bat` (about 43 images)
   - raid bot → double-click `create_images_raid.bat` (about 42 images)
   - 20 images are shared by both, so creating the second set is faster. About 20–30 minutes per bot.
   For each image the tool says what to crop and on which screen; you draw a rectangle with the mouse.
   You can stop and resume later, or skip an image with `s`.
5. Double-click one of the `run_*.bat` files.

Emergency stop: move the mouse to the **top-left corner** of the screen, or press `Ctrl+C` in the console.

## Launch files

| File | Command |
|---|---|
| `run_story.bat` | `python farm.py histoire` (story, endless) |
| `test_one_fight.bat` | `python farm.py histoire -n 1` (stops after one fight) |
| `diagnose_story.bat` | `python farm.py diag` (does not click, shows what the bot sees) |
| `run_raid.bat` | `python farmraid.py` (raid with your current team, endless) |
| `run_raid_rate.bat` | `python farmraid.py --rate` (builds the team on the item **rate** criterion first) |
| `run_raid_quantity.bat` | `python farmraid.py --quantity` (same with the **quantity** criterion) |
| `test_one_raid.bat` / `test_one_raid_rate.bat` | stops after one raid |
| `diagnose_raid.bat` | `python farmraid.py diag` (does not click, writes `diag_raid.png`) |

## Settings

Open `farm.py` (story) or `farmraid.py` (raid) in a text editor: the `SETTINGS` block at the top lists every
option with a comment. The QTE tap delay tunes itself and is stored in `qte_reglage.json`
(delete that file to start over).

## Tests

`python tests/test_raid.py` runs a full simulation against a fake game (no real game involved).
It needs the `templates/` folder to be filled in.

## More documentation

See [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) for every handled screen, safety nets, the QTE logic and the
first-run checklist.

## Images and license

Code: MIT (see `LICENSE`). The recognition images (`templates/`) are **not included**: they are crops of the
game's interface, which belongs to its owners. Create them from your own copy of the game with the tools above,
and please do not publish them. The folder `templates/` is git-ignored for that reason.

## Notes for developers

Comments, docstrings, log messages and documentation are in English. Some **identifiers and file names are
historical French** and were kept so existing setups keep working: `histoire` (= story), `perdu/` and
`perdu_raid/` (= lost-screen screenshots), `journal_raid.txt` (= log), `qte_enregistrement/` (= QTE recordings),
`qte_reglage.json` (= QTE tuning), and the screen/image names used in `ECRANS_*` and `templates/`.
`image_descriptions.json` explains what every image is.
