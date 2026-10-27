# User guide

Two **separate** bots share the `templates/` folder (recognition images):

- `farm.py` = **Story** mode (`run_story.bat`)
- `farmraid.py` = **Raid** mode (`run_raid.bat`)

Run only one of them at a time. Create the images each one needs with `create_images_story.bat` /
`create_images_raid.bat` (see README). File names inside `templates/` are historical French names; the
tool's prompts and `image_descriptions.json` explain what each one is.

## Common rules

- Open the game in a **windowed** emulator window (not full screen) and do not resize it afterwards.
- Stop: mouse to the **top-left corner**, or `Ctrl+C` in the black console window.
- The raid bot writes its log to `journal_raid.txt` (rotated at 2 MB, disable with `JOURNAL_ACTIF = False`).
- When no known screen is seen for 10 s, a screenshot is saved to `perdu/` (story) or `perdu_raid/` (raid),
  40 per run at most (`SAUVER_ECRANS_PERDUS`).

## Story mode (`farm.py`)

Handled in addition to the basic loop (menu → fight with the game's AUTO button → results → next story):

- "Confirm story challenge" / "Check Leader Bonuses" pop-ups: ticks "do not show again" (verifies the box
  changed, 2 tries), then clicks Yes. Setting: `COCHER_NE_PLUS_AFFICHER = False` to only click Yes.
- Full-screen tutorials: clicks Next then Close.
- Communication error pop-up: clicks Title, then resumes as usual.
- Green dialogue bubbles (top or bottom): clicks them. `DIALOGUE_BULLE = False` disables it.
- Tutorials with a **green arrow** pointing down: clicks 40 px under the arrow tip before skipping the bubble.
  `DIALOGUE_FLECHE = False` disables it.
- "TAP", "Next" and the close cross are detected **by their outlines** (any background or colour), even on
  screens the bot does not know. `GENERIQUE = False` disables it.
- Character-edit screen reached by mistake: clicks the back arrow. Equipment awakening: clicks Finish after TAP.

## Raid mode (`farmraid.py`)

Flow: main menu → Events → "Raid Boss Assault" banner (scrolls the list if needed) → Fight → Ready → battle →
rewards → "Play again" → repeat.

- `--rate` / `--quantity`: first builds the team: 3-characters icon → Auto select → Edit → picks the option,
  **verifies by colour** that it is selected → Close → Compose → Set. The team is not rebuilt afterwards.
- `-n 3`: stops after 3 raids. On the last one the bot clicks OK instead of replaying.
- There is no AUTO button in raids: the bot taps the 4 battle cards itself, cards with a Dragon Ball first
  (`templates/bille_dragon_ball.png`), and clicks the team-attack logos as fast as possible.

### The Rising Rush QTE

After the team attack, a ring appears with a gauge that fills and empties. The player taps **once** when the
gauge is **full**. The bot reads how much of the left arc is **still empty** (dark-blue path + light-blue
target zone), and taps when it is full or about to be full when the tap reaches the game. It taps beside the
ring, never on the central disc, and polls the screen every 0.08 s even while it waits between actions.

- The tap delay (`QTE_LATENCE`, default 0.10 s) is only a starting value. After every tap the gauge freezes;
  the bot reads where it stopped and corrects the delay by itself (log: `QTE: tap too late, latency 0.10 -> 0.15 s`).
  The value is saved in `qte_reglage.json`. If the gauge does not freeze, the bot says so and changes nothing.
- Log reasons: `jauge-pleine` (already full), `jauge-prevue` (will be full on arrival), `secours` (last resort at 3.2 s).
- The first 3 QTEs are recorded in `qte_enregistrement/` (images + measurements) for debugging.
- Old gauge rules for other gauge shapes are kept but disabled (`QTE_REGLES_ANCIENNES = False`).

### Safety nets

- "Use Z Power now?" pop-ups: clicks Later. Information pop-ups with a Close button: clicks Close.
- Data-update pop-ups (Title / OK): clicks, touches the title screen, the raid resumes by itself.
- "Player search failed": clicks OK, waits (`ATTENTE_APRES_ECHEC`), clicks Fight again.
- "Player search interrupted (disbanded)": ticks "do not show again", OK, Fight again.
- 30 Fight clicks in a row without a battle starting (daily limit?): stops with a message.
- Raid banner not found after `RAID_BALAYAGES_MAX` swipes: stops.
- Lost on an unknown screen: taps the centre, the close cross, the back arrow, the menu… then stops after 7.5 min.

### First-run checklist

1. On the main menu, run `diagnose_raid.bat`: the menu images should be "recognised".
2. Run `test_one_raid.bat` and watch one complete raid.
3. During a raid battle run `diagnose_raid.bat`: it writes `diag_raid.png` (red circles = where the bot taps,
   yellow squares = where it looks for the Dragon Ball icon).

### Not validated on every setup

Click positions were computed on one machine; check `CARTES_RAID`, `BILLE_DECALAGES`, `SEUIL_BILLE`,
`SEUIL_ENCHAINEMENT`. The Ki-recharge by holding the screen exists but is off by default
(`KI_RECHARGE_TOUTES_LES = 0`). The team criterion is chosen by command-line flag, not compared automatically.

## Warning

This bot automates the game. Terms of service generally forbid such tools: your account may be sanctioned.
Raids are played online with another player, so the risk is higher than in story mode. Use at your own risk.
