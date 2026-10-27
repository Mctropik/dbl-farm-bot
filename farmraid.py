"""
BOT DE FARM - MODE RAID - Dragon Ball Legends (Google Play Games PC)
====================================================================
(Story mode lives in the other file: farm.py. Both share the "templates" folder.)

HOW TO RUN IT (game open in windowed mode, on the main menu):
    python farmraid.py               -> raids with your current team, endless
    python farmraid.py --rate         -> first builds the team on the "item drop rate" criterion, then raids
    python farmraid.py --quantity     -> same with the "item drop quantity" criterion
    python farmraid.py -n 3          -> stops after 3 finished raids (can be combined with the options above)
    python farmraid.py diag          -> does not click, shows what the bot sees
                                        (during a battle: also creates diag_raid.png)

HOW TO STOP IT:
    - move the mouse to the TOP-LEFT corner of the screen (emergency stop), or
    - press Ctrl+C in the black console window.

HOW IT WORKS (in 3 lines):
    1. The bot takes a screenshot of the game window.
    2. It looks for small images (the "templates" folder) to find out which
       screen we are on: menu, fight, end of fight...
    3. It performs the click planned for that screen. The fight itself is handled by the
       game's AUTO button.

The file is organised in 6 parts:
    1. SETTINGS           -> what you can change
    2. SCREEN MAP          -> "on this screen, click here" (the heart of the bot)
    3. RECOGNITION         -> finds an image inside the screenshot
    4. WINDOW AND MOUSE   -> capture and clicks
    5. THE BOT            -> the main loop
    6. LAUNCH             -> the commands (raid / diag)
"""
import argparse
import csv
import ctypes
import sys
import time
from pathlib import Path

import cv2
import numpy as np


# =============================================================================
# 1. SETTINGS
# =============================================================================
WINDOW_TITLE = "Dragon Ball Legends"   # title text of the game window

# After a fight: False = go on to the next story (OK, OK, Play next)
#                   True  = replay the same level ("New fight" button)
REJOUER_MEME_NIVEAU = False

# "fewer than three characters" warning: "oui" (yes) = start anyway, "non" (no) = go back
SI_MOINS_DE_3_PERSOS = "oui"

# If the AUTO button does not respond, the bot taps the 4 cards instead
TAPER_CARTES_SI_AUTO_ECHOUE = True

# Safety: the bot stops if no known screen is seen for this long (seconds)
STOP_APRES = 450                        # 7 min 30

# When the bot is lost, it saves a screenshot in the "perdu" (lost) folder.
# Use these images: they show the screens it does not know yet.
SAUVER_ECRANS_PERDUS = False
MAX_CAPTURES_PERDU = 40                 # so your disk does not fill up

# --- Advanced settings (only change them if you know what you are doing) ---
SEUIL = 0.88            # minimum similarity (0 to 1) to recognise an image
SEUIL_DIALOGUE = 0.75   # minimum similarity for dialogue buttons (top zone only)
SEUIL_INDULGENT = 0.68  # ... when the bot is lost: look for Skip more loosely
INDULGENT_APRES = 4     # seconds of being "lost" before the lenient search for Skip
MAX_CLICS_INDULGENTS = 8  # max lenient clicks per "lost" episode (avoids looping)
SEUIL_COCHE = 15        # minimum yellow pixels to say the "Watch" checkbox is ticked
SEUIL_AUTO_ON = 300     # minimum yellow pixels (top-left corner) to say AUTO is on
PAUSE_BOUCLE = 1.0      # secondes entre deux captures
PAUSE_CLIC = 0.5        # seconds between two clicks of the same action
TEMPLATES = Path(__file__).parent / "templates"
DOSSIER_PERDU = Path(__file__).parent / "perdu_raid"
ZONE_HAUT = 0.18        # "top zone" = the upper 18% of the window (Skip, pause, AUTO buttons)

# Log: everything shown in the black console window is also written to journal_raid.txt
# (next to farmraid.py). Beyond 2 MB, the old log becomes journal_raid_ancien.txt.
JOURNAL_ACTIF = True
JOURNAL = Path(__file__).parent / "journal_raid.txt"
JOURNAL_MAX = 2_000_000


# =============================================================================
# 1 bis. RAID MODE SETTINGS
# =============================================================================
# Navigation safeguards
RAID_ESSAIS_COMBATTRE_MAX = 30   # clicks on "Fight" in a row without a battle starting -> the bot stops
                                 # (daily limit reached, no opponent left...)
ATTENTE_APRES_ECHEC = 6          # seconds to wait after "Player search failed" before searching again
RAID_BALAYAGES_MAX = 15          # max swipes to find the "Raid Boss Assault" banner
SEUIL_LOGO_RAID = 0.75           # minimum similarity for the raid banner (very colourful image)

# Raid battle (no AUTO button: the bot taps the cards itself)
PAUSE_COMBAT = 0.12              # seconds between two actions during a raid battle
CLIC_RAPIDE = True               # faster clicks in battle (0.05 s instead of 0.15 s of mouse travel)
SEUIL_ENCHAINEMENT = 0.60        # minimum similarity of the "Rising Rush" (team attack) logo
ECART_ENCHAINEMENT = 0.8         # minimum seconds between two clicks on this logo
IMAGES_ENCHAINEMENT = ["rising_rush", "rising_rush_equipe"]   # player's logo, team logo

# Priority to the cards that carry a Dragon Ball (small orange ball in the top-left corner).
# The bot looks for the image templates/bille_dragon_ball.png near that corner, on each card.
PRIORITE_BILLES = True
BILLE_IMAGE = "bille_dragon_ball"
# Where the ball is, relative to the centre of each card (measured on screenshots; the cards are fanned out)
BILLE_DECALAGES = [(-29, -40), (-30, -45), (-32, -53), (-31, -62)]
BILLE_DEMI = 16                  # half-side of the search zone around this position (original pixels)
SEUIL_BILLE = 0.60               # minimum similarity (measured: 0.83 to 0.94 with a ball, 0.27 at most without)

# QTE after a Rising Rush (team attack): a ring with a gauge that moves along an arc towards a small
# light-blue zone; you must tap when the gauge is full. The bot reads the colours of the ring.
QTE_ACTIF = True
QTE_CENTRE = (255, 672)          # centre of the ring, relative to the battle "list" icon (top left)
QTE_RAYONS = (125, 135, 145, 155)  # radii (original pixels) at which the ring is read
QTE_PAS = 2                      # reading precision (degrees)
QTE_LATENCE = 0.10               # seconds between "the bot decides" and "the game receives the tap": STARTING value only,
                                 # the bot tunes it by itself after each QTE (see QTE_AUTO_REGLAGE), no need to touch it
QTE_AUTO_REGLAGE = True          # True = after each tap, the bot looks where the gauge stopped and corrects QTE_LATENCE
QTE_RESTE_PLEIN = 6              # degrees: the gauge is "full" when less than this is left to fill (dark-blue path + light-blue zone)
QTE_REGLES_ANCIENNES = False     # old rules (yellow bar only: zone, peak, yellow gone...): useless on the real game
QTE_LATENCE_MIN = 0.0            # limits of the automatic tuning (seconds)
QTE_LATENCE_MAX = 0.60
QTE_REGLAGE_GAIN = 0.5           # share of the error corrected at each QTE (0.5 = cautious, avoids over-correcting)
QTE_REGLAGE_PAS_MAX = 0.08       # maximum correction per QTE (seconds)
QTE_REGLAGE_FICHIER = Path(__file__).parent / "qte_reglage.json"   # the setting is kept from one run to the next
QTE_APPUI = (-150, -300)         # where the bot taps, relative to the centre of the ring (top left of the ring:
                                 # anywhere except the central disc)
QTE_TOL_HAUT = 4                 # degrees: the gauge is "full" when the bar gets within this distance of the top of the arc
QTE_UN_SEUL_APPUI = True         # True = a single tap per QTE (a tap stops the gauge in the game)
QTE_SECOURS_APRES = 3.2          # seconds: if no tap happened, tap anyway (the timer lasts ~4 s)
QTE_ENREGISTRER_MAX = 3          # number of QTEs recorded (images + measurements) in qte_enregistrement/ so that
                                 # the tuning can be refined (0 = record nothing)
QTE_DOSSIER = Path(__file__).parent / "qte_enregistrement"
QTE_ATTENTE = 1.0                # minimum seconds between two bot taps on a QTE
QTE_ATTENTE_PAS = 0.08           # during raid pauses, the bot looks at the screen every 0.08 s so it does not miss a QTE
QTE_PAUSE = 0.02                 # pause between two readings during a QTE

# Green dialogue bubbles, green tutorial arrows, TAP / Next / Close anywhere:
DIALOGUE_BULLE = True
PAUSE_BULLE = 1.5       # minimum seconds between two clicks on a bubble
# Tutorials with a GREEN ARROW (e.g. "Press Awakening", "choose Memories"):
# True = the bot clicks what the arrow points at (just below it), BEFORE skipping the bubble.
DIALOGUE_FLECHE = True
PAUSE_FLECHE = 1.2      # minimum seconds between two clicks on an arrow's target
FLECHE_DECALAGE = 40    # pixels below the arrow tip where the bot clicks (measured on 8 tutorials)

# "Anywhere" recognition of TAP, Next and Close (cross): the bot looks for these words/buttons by their
# OUTLINES, whatever the background or colour, even on a screen it does not know. True = enabled.
GENERIQUE = True
PAUSE_GENERIQUE = 1.5   # minimum seconds between two clicks of this kind
SEUIL_GENERIQUE = 0.72  # minimum similarity (screenshots without these words stay below 0.60)
# (displayed name, images, start of the searched zone as a fraction of the screen height)
GENERIQUES = [
    ("APPUYEZ", ["gen_appuyez_barre", "gen_appuyez_novice", "gen_appuyez_niveau", "gen_appuyez_raid",
                 "gen_appuyez_eveil"], 0.50),
    ("Suivant", ["gen_suivant_sombre", "gen_suivant_ultra"], 0.75),
    ("Fermer", ["gen_fermer_x"], 0.75),
]

# Ki recharge by holding a finger on the screen: 0 = disabled (enable only after testing)
KI_RECHARGE_TOUTES_LES = 6       # secondes entre deux recharges (0 = jamais)
KI_RECHARGE_DUREE = 2          # hold duration (seconds)

# "Priority criteria" window: the selected option has a light-yellow background.
OPTION_DEMI = (90, 20)           # half-width / half-height of the zone read around each option
SEUIL_OPTION = 300               # minimum yellow pixels to say "this option is selected"


# =============================================================================
# 2. SCREEN MAP
# =============================================================================
# Each screen is described by:
#   nom     : a name for the messages
#   tpl     : the image that proves we are on this screen (templates/<tpl>.png)
#   clics   : list of (dx, dy) = where to click, relative to the CENTRE of the recognised image
#             (measured in pixels on the original screenshots; the bot adapts to your window)
#   pause   : minimum seconds before clicking again on this same screen
# Options facultatives :
#   seuil   : minimum similarity specific to this screen
#   apres   : ("other_screen", seconds) -> wait this delay after a click on the other screen
#   sauf_si : image that, when visible, stops this screen from acting
#   zone    : "haut" (top) = search the image only in the top of the window (faster, safer)
#   groupe  : screens that share the same delay between two clicks
#   bloque  : True for a pop-up displayed ON TOP of another screen: during its delay,
#             the bot acts on nothing else (otherwise it would click the buttons hidden behind it)
#   special : action coded separately ("visionner" or "auto")
#   compte  : True if this screen marks the end of a fight
# ORDER MATTERS: the bot tests the screens from top to bottom and takes the first one recognised.
# A dialogue shows 3 buttons at the top: "Auto / OFF", "Log" and "Skip".
# The bot recognises ANY of the three (more reliable than one) and always clicks Skip.
# (name, image of the button text, offset to Skip from the centre of that image)
ANCRES_DIALOGUE = [
    ("dialogue_passer", "passer", (0, 0)),
    ("dialogue_via_journal", "dialogue_journal", (177, 0)),
    ("dialogue_via_auto", "dialogue_auto", (354, 0)),
]
ECRANS_DIALOGUE = [
    {"nom": nom, "tpl": tpl, "clics": [decalage], "pause": 1.2, "seuil": SEUIL_DIALOGUE,
     "zone": "haut", "groupe": "dialogue", "bloque": True}   # the 3 landmarks share the same delay
    for nom, tpl, decalage in ANCRES_DIALOGUE
]

ECRANS_HISTOIRE = [
    # Pop-up "Data update finished. Return to the title screen." -> Title button.
    # It is at the TOP of the list because it is displayed over another screen (the Ready button
    # stays visible behind it): without that, the bot would click Ready.
    {"nom": "popup_titre", "tpl": "popup_titre", "clics": [(0, 0)], "pause": 5, "bloque": True,
     "groupe": "popup_titre"},

    # Another return-to-title pop-up: "Refreshing data - The data update
    # is finished. Return to the title screen." with an OK button. The landmark is the line
    # "Return to the title screen.", common to both pop-ups (the button is at the same place:
    # so one click works for Title or OK). Same group = same delay.
    {"nom": "popup_retour_titre", "tpl": "retour_titre_texte", "clics": [(147, 389)], "pause": 5,
     "bloque": True, "groupe": "popup_titre"},

    # Title screen "Touch the screen" -> we touch the screen, then the game loads (we wait 12 s
    # before touching again). Two landmarks that never change, even when the artwork changes:
    # the "Touch the screen" text or the Bandai Namco logo (then we touch the "Touch the screen" bar).
    {"nom": "ecran_titre", "tpl": "touchez_ecran", "clics": [(0, 0)], "pause": 12, "groupe": "titre",
     "bloque": True},
    {"nom": "ecran_titre_logo", "tpl": "logo_bandai", "clics": [(-235, 829)], "pause": 12,
     "groupe": "titre", "zone": "haut", "bloque": True},

    # Warning "You selected fewer than three characters..." -> Yes (or No)
    {"nom": "avertissement_moins_de_3", "tpl": "popup_moins_trois", "pause": 3, "bloque": True,
     "clics": [(134, 390) if SI_MOINS_DE_3_PERSOS == "oui" else (-98, 390)]},

    # Dialogue / cutscene -> Skip (see ANCRES_DIALOGUE above)
    *ECRANS_DIALOGUE,

    # Window "Continue to the next story?" -> Yes
    {"nom": "popup_suite", "tpl": "popup_suite", "clics": [(205, 159)], "pause": 3, "bloque": True},

    # Team selection: fighters are still to be chosen -> the first 3
    {"nom": "equipe_a_choisir", "tpl": "encore", "pause": 5,
     "clics": [(-125, -205), (-6, -205), (120, -205)]},

    # Team complete -> Ready (3 s after clicking the characters, to let
    # the game register the selection)
    {"nom": "equipe_prete", "tpl": "pret", "clics": [(0, 0)], "pause": 3, "seuil": 0.9,
     "apres": ("equipe_a_choisir", 3)},

    # Challenges screen after the fight -> OK (or "New fight"). Marks a finished fight.
    {"nom": "fin_defis", "tpl": "nv_combat", "pause": 3, "compte": True,
     "clics": [(0, 0)] if REJOUER_MEME_NIVEAU else [(232, 0)]},

    # Result screen (SUCCESS) -> OK
    {"nom": "fin_resultat", "tpl": "ok", "clics": [(0, 0)], "pause": 3},

    # Level details: the bot READS the "Watch" checkbox.
    #   ticked -> it unticks it; unticked -> it clicks Fight.
    {"nom": "details_niveau", "tpl": "visionner_texte", "special": "visionner", "pause": 0.8},

    # Same screen, but without the "Watch" checkbox -> Fight directly
    {"nom": "combattre", "tpl": "combattre", "clics": [(0, 0)], "pause": 3,
     "sauf_si": "visionner_texte"},

    # "Success conditions" banner at the start of the fight -> tap
    {"nom": "intro_combat", "tpl": "appuyez", "clics": [(0, 0)], "pause": 2},

    # In a fight with AUTO off -> switch it on
    {"nom": "combat_auto", "tpl": "auto_off", "special": "auto", "pause": 6},

    # Game menu open -> Story tile
    {"nom": "menu_ouvert", "tpl": "menu_tuile_histoire", "clics": [(0, 0)], "pause": 3},

    # Story list -> Play next
    {"nom": "liste_histoire", "tpl": "jouer_suite", "clics": [(0, 0)], "pause": 3},

    # Menu principal -> Histoire
    {"nom": "menu_principal", "tpl": "menu_histoire", "clics": [(0, 0)], "pause": 3},
]

# -----------------------------------------------------------------------------
# MODE RAID
# -----------------------------------------------------------------------------
# Extra options used here (in addition to those described above):
#   si   : {"key": value} -> the screen only acts if the bot state matches (see Bot.etat)
#   pose : {"key": value} -> changes the bot state after the click
# Reminder: the bot state (dictionary Bot.etat) holds 3 flags for the team:
#   crit_ok     the criterion (rate / quantity) was chosen and the window closed
#   compose_ok  the "Compose" button was clicked
#   equipe_ok   the "Set" button was clicked (team confirmed). Without --rate / --quantity,
#               it is True from the start: the bot keeps the current team.
# The offsets (dx, dy) were measured on screenshots (about 556 x 992) from the centre of the recognised image.
_MSG_TITRE = {"popup_titre": "Return to title screen: Title", "popup_retour_titre": "Data refresh: OK",
              "ecran_titre": "Title screen: touching the screen", "ecran_titre_logo": "Title screen: touching the screen"}
RECUP_TITRE = [dict(e, msg=_MSG_TITRE[e["nom"]]) for e in ECRANS_HISTOIRE if e["nom"] in _MSG_TITRE]

# "msg" = what is written to the log when the screen is handled ("" = nothing written).
ECRANS_RAID = [
    # Pop-up "Player search interrupted (Disbanded)": tick "Do not show again", then OK.
    # The bot then goes back to the raid screen and clicks Fight again.
    {"nom": "popup_dissolution", "tpl": "dissolution_titre", "clics": [(-228, 370), (0, 462)],
     "pause": 4, "bloque": True, "msg": "Dissolution : OK"},

    # Pop-up "Player search failed: No opponent found. Try again later."
    # -> OK (the game goes back to the raid screen, where the bot clicks Fight again after a short wait)
    {"nom": "popup_echec_recherche", "tpl": "popup_echec_titre", "special": "echec_recherche",
     "pause": 4, "bloque": True},

    # Return to the title screen (data update...): same reactions as story mode
    *RECUP_TITRE,

    # Pop-up "Error - A communication error occurred." -> Title button
    {"nom": "popup_erreur", "tpl": "erreur_texte", "clics": [(49, 414)], "pause": 5, "bloque": True,
     "groupe": "popup_titre", "msg": "Communication error: Title"},

    # Pop-up "Use Multi Z Power" (and other "Use now?") -> Later
    {"nom": "popup_plus_tard", "tpl": "btn_plus_tard", "clics": [(0, 0)], "pause": 3, "bloque": True,
     "msg": "Pop-up : Plus tard"},
    # Information pop-up (e.g. "Add bonus characters...") -> Close.
    # (The Close button of the criteria window is handled further below, with verification.)
    {"nom": "popup_fermer", "tpl": "btn_fermer", "clics": [(0, 0)], "pause": 3, "bloque": True,
     "sauf_si": "criteres_titre", "msg": "Pop-up : Fermer"},

    # "Priority criteria" window: picks rate or quantity, VERIFIES by colour, then Close
    {"nom": "criteres", "tpl": "criteres_titre", "special": "critere", "pause": 2.5, "bloque": True},

    # "Auto select" window (over the Teams screen):
    #   criterion not chosen yet -> Edit; criterion chosen -> Compose
    {"nom": "autoselect_modifier", "tpl": "autoselect_texte", "clics": [(299, 571)], "pause": 3,
     "bloque": True, "si": {"crit_ok": False}, "msg": "Team: Edit the criterion"},
    {"nom": "autoselect_composer", "tpl": "autoselect_texte", "clics": [(228, 778)], "pause": 3,
     "bloque": True, "si": {"crit_ok": True, "compose_ok": False}, "apres": ("criteres", 1.5),
     "pose": {"compose_ok": True}, "msg": "Team: Compose"},

    # Game menu open -> EVENTS tab
    {"nom": "menu_ouvert", "tpl": "menu_tuile_histoire", "clics": [(88, 129)], "pause": 3,
     "msg": "Menu: Events"},

    # --- End of raid ---
    # "Challenges" screen: "Play again" (takes priority over OK). Marks a finished raid.
    # At the last requested raid (-n), the bot clicks OK instead and stops.
    {"nom": "fin_jouer_encore", "tpl": "jouer_encore", "special": "rejouer", "pause": 4, "bloque": True},
    # Results ("damage dealt", "Bravery points") -> OK
    {"nom": "fin_ok", "tpl": "ok_raid", "clics": [(0, 0)], "pause": 3, "msg": ""},
    # "Challenge cleared!" -> one click on the screen
    {"nom": "fin_defi_reussi", "tpl": "appuyez_centre", "clics": [(0, 0)], "pause": 2, "msg": ""},
    # "Special reward gained" -> one click on the screen
    {"nom": "fin_gain", "tpl": "gain_recomp_titre", "clics": [(0, 0)], "pause": 2, "msg": ""},

    # --- Battle lobby ---
    # Ready right away (if the button is already greyed out, the click does nothing: harmless)
    {"nom": "salon_pret", "tpl": "raid_pret", "clics": [(0, 0)], "pause": 2, "msg": "Ready"},
    # "Searching" and the lobby title: we know where we are, nothing to click
    {"nom": "recherche", "tpl": "recherche_texte", "clics": [], "pause": 8, "msg": ""},
    {"nom": "salon_titre", "tpl": "salon_raid_titre", "clics": [], "pause": 8, "msg": ""},

    # --- "Teams" screen ---
    # Team composed -> Set (Set is what confirms, not the back arrow)
    {"nom": "equipe_regler_apres_composer", "tpl": "btn_regler", "clics": [(0, 0)], "pause": 4,
     "groupe": "regler", "si": {"compose_ok": True}, "sauf_si": "autoselect_texte",
     "pose": {"equipe_ok": True}, "msg": "Team: Set"},
    # Team already confirmed but we are here anyway (unexpected screen) -> Set to leave
    {"nom": "equipe_regler_sortie", "tpl": "btn_regler", "clics": [(0, 0)], "pause": 4,
     "groupe": "regler", "si": {"equipe_ok": True}, "sauf_si": "autoselect_texte",
     "msg": "Team: Set"},
    # Team not composed yet -> Auto select
    {"nom": "equipe_auto_select", "tpl": "btn_auto_select", "clics": [(0, 0)], "pause": 4,
     "si": {"compose_ok": False, "equipe_ok": False}, "sauf_si": "autoselect_texte",
     "msg": "Team: Auto select"},

    # --- Main raid screen: team (if a criterion is requested) or Fight ---
    {"nom": "raid_accueil", "tpl": "raid_code_invit", "special": "raid_accueil", "pause": 5},

    # --- Events list: find the raid banner (scrolling if needed) ---
    {"nom": "liste_evenements", "tpl": "evenements_titre", "special": "trouver_raid", "pause": 2.5,
     "zone": "haut"},

    # "Edit character" screen (reached by mistake) -> back arrow at the bottom left
    {"nom": "modif_perso", "tpl": "modif_perso_titre", "clics": [(-60, 924)], "pause": 4, "zone": "haut",
     "msg": "Modif. perso. : retour"},

    # --- Main menu -> EVENTS tab ---
    {"nom": "menu_principal", "tpl": "menu_histoire", "clics": [(68, 105)], "pause": 3,
     "msg": "Menu: Events"},
]

# Raid-specific offsets (from the centre of the recognised image, on the original screenshots)
COMBATTRE_DECALAGE = (-182, 0)          # from "Use a code / Invitation"
EQUIPE_ICONE_DECALAGE = (-32, -252)     # from "Use a code / Invitation" ("3 characters" icon)
OK_DEPUIS_REJOUER = (203, -1)           # from "Play again" to OK (same Challenges screen)
# "Priority criteria" window: offsets from its header (277, 246)
OPTIONS_CRITERE = {"capacite": (-125, 68), "puissance": (125, 68),
                   "taux": (-125, 136), "quantite": (125, 136)}
FERMER_CRITERE = (1, 462)
OK_ECHEC_RECHERCHE = (0, 460)           # from the title of the "Player search failed" pop-up
# The 4 raid battle cards: offsets from the "list" icon at the top left (23, 73)
CARTES_RAID = [(189, 724), (283, 709), (377, 698), (469, 687)]

# Les modes disponibles
MODES = {"raid": ECRANS_RAID}

# Special images (not screens to click)
IMAGES_EN_COMBAT = ["pause", "auto_mot", "auto_on"]   # any of them = a fight is in progress
IMAGES_COMBAT_PAR_MODE = {"histoire": IMAGES_EN_COMBAT, "raid": ["raid_combat_icone"]}
IMAGES_EN_PLUS = {"raid": ["logo_assaut_raid", "raid_equipe_icone", "bille_dragon_ball"] + IMAGES_ENCHAINEMENT}
IMAGE_RETOUR = "retour"              # back arrow (bottom left)
IMAGE_BOUTON_MENU = "menu_hamburger" # menu button (bottom right)
IMAGE_CROIX = "croix"                # cross that closes a menu or a pop-up (bottom right of the menu)

# Position of the 4 battle cards, relative to the centre of the "AUTO OFF" button
CARTES_COMBAT = [(126, 714), (219, 709), (313, 704), (404, 699)]

# When the bot recognises NO screen, it acts at these moments (seconds without recognising anything):
#   centre : taps the window centre at 10 s, then every 30 s (advances dialogues)
#   croix  : clicks the cross (bottom right) at 20 s, 90 s and 210 s, if visible:
#            closes an unknown menu or pop-up. It is used ONLY when the bot is lost: if the menu
#            is recognised, the Story tile takes priority, never the cross.
#   retour : clicks the back arrow at 45 s, 150 s and 330 s (if visible)
#   menu   : opens the game menu at 180 s and 300 s; the bot then recognises the menu,
#            clicks "Story" and restarts from the story page
# Then it stops at STOP_APRES.
SI_PERDU = sorted(
    [(t, "centre") for t in range(10, STOP_APRES + 1, 30)]
    + [(20, "croix"), (90, "croix"), (210, "croix")]
    + [(45, "retour"), (150, "retour"), (330, "retour"), (180, "menu"), (300, "menu")]
)

# Window sizes tried (1.0 = size of the original screenshots), 1.0 first
ECHELLES = sorted(np.arange(0.6, 1.61, 0.05).round(2).tolist(), key=lambda s: abs(s - 1.0))


def log(message):
    """Print a message with the time (and also write it to journal.txt)."""
    ligne = f"[{time.strftime('%H:%M:%S')}] {message}"
    print(ligne)
    if JOURNAL_ACTIF:
        try:
            with open(JOURNAL, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d')} {ligne}\n")
        except Exception:
            pass                       # the log must never crash the bot


def preparer_journal(mode):
    """At startup: archive the log if it is too big, then mark the start of the session."""
    if not JOURNAL_ACTIF:
        return
    try:
        if JOURNAL.exists() and JOURNAL.stat().st_size > JOURNAL_MAX:
            JOURNAL.replace(JOURNAL.with_name("journal_raid_ancien.txt"))
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(f"\n===== Nouvelle session ({mode}) - {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    except Exception:
        pass


def images_necessaires(ecrans, mode="histoire"):
    """List of the images (templates) the bot needs for this mode."""
    noms = {e["tpl"] for e in ecrans} | {e["sauf_si"] for e in ecrans if "sauf_si" in e}
    noms |= set(IMAGES_COMBAT_PAR_MODE[mode]) | set(IMAGES_EN_PLUS.get(mode, []))
    return sorted(noms | {IMAGE_RETOUR, IMAGE_BOUTON_MENU, IMAGE_CROIX})


def verifier_images(ecrans, mode="histoire"):
    """Stop with a clear message if images are missing from templates/."""
    manquantes = [n for n in images_necessaires(ecrans, mode) if not (TEMPLATES / f"{n}.png").exists()]
    if manquantes:
        sys.exit("Images are missing from the 'templates' folder (run create_images.py):\n  - "
                 + "\n  - ".join(f"{n}.png" for n in manquantes))


# =============================================================================
# 3. RECONNAISSANCE D'IMAGE
# =============================================================================
class Reconnaisseur:
    """Look for a small image (template) in a screenshot, at any size."""

    def __init__(self):
        self.echelle = None      # window size, found at the first recognised screen
        self._images = {}        # cache of the loaded templates

    def _template(self, nom):
        if nom not in self._images:
            img = cv2.imread(str(TEMPLATES / f"{nom}.png"), cv2.IMREAD_GRAYSCALE)
            if img is None:
                sys.exit(f"Missing image: {nom}.png. Run create_images.py first (double-click create_images_raid.bat or create_images_story.bat): "
                         f"it guides you through making the images from your own copy of the game.")
            self._images[nom] = img
        return self._images[nom]

    @staticmethod
    def _en_gris(ecran, zone=None):
        gris = ecran if ecran.ndim == 2 else cv2.cvtColor(ecran, cv2.COLOR_BGR2GRAY)
        if zone == "haut":
            gris = gris[:int(gris.shape[0] * ZONE_HAUT)]
        return gris

    @staticmethod
    def _essai(gris, template, echelle):
        """Look for the template at a given size. Returns (score, centre_x, centre_y, scale)."""
        t = template if abs(echelle - 1) < 1e-6 else cv2.resize(
            template, None, fx=echelle, fy=echelle, interpolation=cv2.INTER_AREA)
        if t.shape[0] >= gris.shape[0] or t.shape[1] >= gris.shape[1]:
            return None
        resultat = cv2.matchTemplate(gris, t, cv2.TM_CCOEFF_NORMED)
        _, score, _, pos = cv2.minMaxLoc(resultat)
        return float(score), pos[0] + t.shape[1] / 2, pos[1] + t.shape[0] / 2, echelle

    def meilleur(self, ecran, nom, zone=None):
        """Best result, even a weak one: (score, centre_x, centre_y, scale). Used by the diagnostic."""
        gris, template = self._en_gris(ecran, zone), self._template(nom)
        meilleur = (0.0, 0, 0, 1.0)
        for echelle in ([self.echelle] if self.echelle else ECHELLES):
            essai = self._essai(gris, template, echelle)
            if essai and essai[0] > meilleur[0]:
                meilleur = essai
        return meilleur

    def trouve(self, ecran, nom, seuil=SEUIL, zone=None):
        """Return (centre_x, centre_y, scale) if the image is recognised, otherwise None."""
        meilleur = self.meilleur(ecran, nom, zone)
        if meilleur[0] < seuil:
            return None
        if self.echelle is None and meilleur[0] >= 0.9:
            # First solid recognition: we refine the window size (steps of 0.01)
            gris, template = self._en_gris(ecran, zone), self._template(nom)
            for k in range(-5, 6):
                essai = self._essai(gris, template, round(meilleur[3] + k * 0.01, 2))
                if essai and essai[0] > meilleur[0]:
                    meilleur = essai
            self.echelle = meilleur[3]
        return meilleur[1], meilleur[2], meilleur[3]


def analyser_ecran(ecran, reco, ecrans, derniers_clics, maintenant, etat=None):
    """
    Look at the screenshot and decide what to do.
    Returns (screen_to_handle, position, recognised):
      - screen_to_handle / position: the screen to act on (or None, None)
      - recognised: True if a known screen is visible, even if there is nothing to click
                  for now (pause between two clicks...)
    """
    reconnu = False
    for e in ecrans:
        position = reco.trouve(ecran, e["tpl"], e.get("seuil", SEUIL), e.get("zone"))
        if not position:
            continue
        reconnu = True
        if "si" in e and any((etat or {}).get(k) != v for k, v in e["si"].items()):
            continue                                   # the bot state does not match: not now
        if maintenant - derniers_clics.get(cle_pause(e), -1e9) < e["pause"]:
            if e.get("bloque"):
                return None, None, True                # pop-up is closing: we wait
            continue                                   # we just clicked here
        if "sauf_si" in e and reco.trouve(ecran, e["sauf_si"]):
            continue                                   # a more precise screen handles it
        if "apres" in e:
            autre, delai = e["apres"]
            if maintenant - derniers_clics.get(autre, -1e9) < delai:
                if e.get("bloque"):
                    return None, None, True            # pop-up: we wait, without clicking behind it
                continue                               # too soon after the previous action
        return e, position, True
    return None, None, reconnu


def cle_pause(e):
    """Name under which the time of the last click is remembered (shared by the screens of a group)."""
    return e.get("groupe", e["nom"])


# =============================================================================
# 4. WINDOW AND MOUSE
# =============================================================================
def configurer_souris():
    """Enable the emergency stop (mouse in the top-left corner) and Windows precision."""
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # avoids offsets with Windows zoom
    except Exception:
        pass


def trouver_fenetre():
    import pygetwindow as gw
    fenetres = gw.getWindowsWithTitle(WINDOW_TITLE)
    if not fenetres:
        sys.exit(f"Window '{WINDOW_TITLE}' not found. Start the game (windowed mode) and try again.")
    fenetre = fenetres[0]
    if fenetre.isMinimized:
        fenetre.restore()
        time.sleep(0.5)
    return fenetre


def mettre_au_premier_plan(fenetre):
    try:
        fenetre.activate()
    except Exception:
        pass                      # Windows sometimes refuses, this is not blocking


def capture(fenetre):
    import pyautogui
    image = pyautogui.screenshot(region=(fenetre.left, fenetre.top, fenetre.width, fenetre.height))
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def cliquer(fenetre, x, y, rapide=False):
    """'Human' click: the mouse arrives, pauses for a moment, presses, then releases.
    (Some games ignore clicks that are too fast.)  x and y are relative to the window.
    rapide=True: same thing, snappier (raid battle)."""
    import pyautogui
    duree, pause = (0.05, 0.04) if rapide else (0.15, 0.1)
    pyautogui.moveTo(int(fenetre.left + x), int(fenetre.top + y), duration=duree)
    time.sleep(pause)
    pyautogui.mouseDown()
    time.sleep(pause)
    pyautogui.mouseUp()


def glisser(fenetre, x1, y1, x2, y2, duree=0.6):
    """Drag the finger from (x1, y1) to (x2, y2) (to scroll a list)."""
    import pyautogui
    pyautogui.moveTo(int(fenetre.left + x1), int(fenetre.top + y1), duration=0.15)
    time.sleep(0.1)
    pyautogui.mouseDown()
    pyautogui.moveTo(int(fenetre.left + x2), int(fenetre.top + y2), duration=duree)
    time.sleep(0.15)
    pyautogui.mouseUp()


def maintenir(fenetre, x, y, duree):
    """Press the screen for 'duree' seconds (Ki recharge)."""
    import pyautogui
    pyautogui.moveTo(int(fenetre.left + x), int(fenetre.top + y), duration=0.1)
    pyautogui.mouseDown()
    time.sleep(duree)
    pyautogui.mouseUp()


# --- Reading the "Watch" checkbox ------------------------------------------
def compter_pixels_jaunes(ecran, x, y, echelle):
    """Count the yellow pixels (the tick) inside the box around (x, y)."""
    r = int(round(5.5 * echelle))
    x0, y0 = int(round(x)) - r, int(round(y)) - r
    zone = ecran[max(y0, 0):y0 + 2 * r, max(x0, 0):x0 + 2 * r]
    if zone.size == 0:
        return 0
    hsv = cv2.cvtColor(zone, cv2.COLOR_BGR2HSV)
    return int(cv2.countNonZero(cv2.inRange(hsv, (15, 120, 170), (35, 255, 255))))


def compter_jaune_auto(ecran):
    """
    Count the yellow pixels of the top-left corner. The AUTO button is YELLOW when it is on
    and GREY when it is off: the most reliable method (the colour does not depend on the scenery).
    """
    h, w = ecran.shape[:2]
    zone = ecran[:int(h * 0.14), :int(w * 0.25)]
    hsv = cv2.cvtColor(zone, cv2.COLOR_BGR2HSV)
    return int(cv2.countNonZero(cv2.inRange(hsv, (22, 170, 180), (36, 255, 255))))


def lire_case_visionner(ecran, cx, cy, echelle):
    """
    (cx, cy) = centre of the word "Watch". The checkbox is just to its left.
    Renvoie (action, x, y, nb_pixels_jaunes) :
      "decocher"  -> the box is ticked, we must click it at (x, y)
      "combattre" -> the box is unticked, we must click Fight at (x, y)
    """
    case_x, case_y = cx - 63 * echelle, cy - 1.5 * echelle
    n = compter_pixels_jaunes(ecran, case_x, case_y, echelle)
    if n >= SEUIL_COCHE * echelle * echelle:
        return "decocher", case_x, case_y, n
    return "combattre", cx - 19 * echelle, cy + 92 * echelle, n


# --- Colour readings for raid mode ----------------------------------------
def compter_jaune_option(ecran, x, y, echelle):
    """Count the light-yellow pixels in the zone of a 'Priority criteria' option."""
    demi_l, demi_h = int(round(OPTION_DEMI[0] * echelle)), int(round(OPTION_DEMI[1] * echelle))
    x0, y0 = int(round(x)) - demi_l, int(round(y)) - demi_h
    zone = ecran[max(y0, 0):y0 + 2 * demi_h, max(x0, 0):x0 + 2 * demi_l]
    if zone.size == 0:
        return 0
    hsv = cv2.cvtColor(zone, cv2.COLOR_BGR2HSV)
    return int(cv2.countNonZero(cv2.inRange(hsv, (15, 35, 190), (38, 255, 255))))


def lire_options_critere(ecran, cx, cy, echelle):
    """(cx, cy) = centre of the 'Priority criteria' header. Returns {option: yellow pixels}."""
    return {nom: compter_jaune_option(ecran, cx + dx * echelle, cy + dy * echelle, echelle)
            for nom, (dx, dy) in OPTIONS_CRITERE.items()}


def option_choisie(scores):
    """The selected option = the one with clearly the most yellow. None if it cannot be decided."""
    classement = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (nom, meilleur), (_, second) = classement[0], classement[1]
    if meilleur >= SEUIL_OPTION and meilleur >= 1.5 * second:
        return nom
    return None


def trouver_bulle(ecran, echelle=1.0):
    """Look for a dialogue bubble (light-green frame, white background, portrait on the left), wherever it is.
    Returns the centre (x, y) of the bubble, or None. A very large empty frame is not a flat green area."""
    hsv = cv2.cvtColor(ecran, cv2.COLOR_BGR2HSV)
    vert = cv2.inRange(hsv, (28, 120, 120), (48, 255, 255))
    vert = cv2.morphologyEx(vert, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(vert)
    for j in range(1, n):
        x, y, w, h, aire = (int(v) for v in stats[j])
        if w < 400 * echelle or not (90 * echelle <= h <= 200 * echelle):
            continue
        if aire / float(w * h) > 0.25:                      # too full: a flat green area, not a frame
            continue
        marge = int(8 * echelle)
        dedans = hsv[y + marge:y + h - marge, x + int(60 * echelle):x + w - marge]   # to the right of the portrait
        if dedans.size == 0:
            continue
        blanc = np.count_nonzero((dedans[..., 1] < 60) & (dedans[..., 2] > 190)) / float(dedans.shape[0] * dedans.shape[1])
        if blanc >= 0.35:
            return x + w / 2.0, y + h / 2.0
    return None


def trouver_fleche(ecran, echelle=1.0):
    """Look for the tutorials' green arrow (yellow -> green gradient, black edge, white outline), pointing
    down. Returns (x, y) = the spot it points at (just under its tip), or None."""
    hsv = cv2.cvtColor(ecran, cv2.COLOR_BGR2HSV)
    vert = cv2.inRange(hsv, (22, 140, 150), (70, 255, 255))
    vert = cv2.morphologyEx(vert, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(vert)
    e2 = echelle * echelle
    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(round(7 * echelle)) | 1,) * 2)
    k9 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(round(21 * echelle)) | 1,) * 2)
    for j in range(1, n):
        x, y, w, h, aire = (int(v) for v in stats[j])
        if not (600 * e2 <= aire <= 1500 * e2 and 36 * echelle <= w <= 75 * echelle
                and 24 * echelle <= h <= 56 * echelle):
            continue
        m = int(14 * echelle)
        x0, y0 = max(x - m, 0), max(y - m, 0)
        sous = lab[y0:y + h + m, x0:x + w + m] == j
        zone = hsv[y0:y + h + m, x0:x + w + m]
        s8 = sous.astype(np.uint8)
        anneau_noir = (cv2.dilate(s8, k3) - s8).astype(bool)
        anneau_blanc = (cv2.dilate(s8, k9) - cv2.dilate(s8, k3)).astype(bool)
        if not anneau_noir.any() or not anneau_blanc.any():
            continue
        noir = float((zone[..., 2][anneau_noir] < 80).mean())
        blanc = float(((zone[..., 2][anneau_blanc] > 215) & (zone[..., 1][anneau_blanc] < 60)).mean())
        haut_, bas_ = sous[:max(1, int(sous.shape[0] * 0.35))], sous[int(sous.shape[0] * 0.65):]
        teintes = zone[..., 0].astype(float)
        if not haut_.any() or not bas_.any():
            continue
        degrade = teintes[int(sous.shape[0] * 0.65):][bas_].mean() - teintes[:haut_.shape[0]][haut_].mean()
        if noir >= 0.70 and blanc >= 0.25 and degrade >= 10:
            return x + w / 2.0, y + h + FLECHE_DECALAGE * echelle
    return None


_GEN = {}


def carte_contours(im):
    """Edge image (intensity of the brightness change): independent of colours and background."""
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32), (3, 3), 0)
    return cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))


def modele_contours(nom, echelle):
    """Edges of an image from templates/ (saved with a 2-pixel margin), at the window scale."""
    cle = (nom, round(echelle, 2))
    if cle not in _GEN:
        im = cv2.imread(str(TEMPLATES / f"{nom}.png"))
        if im is None:
            _GEN[cle] = None
        else:
            if echelle != 1.0:
                im = cv2.resize(im, None, fx=echelle, fy=echelle, interpolation=cv2.INTER_AREA)
            marge = max(1, int(round(2 * echelle)))
            _GEN[cle] = carte_contours(im)[marge:-marge, marge:-marge]
    return _GEN[cle]


def trouver_generique(ecran, echelle=1.0):
    """Look for TAP / Next / Close anywhere in the planned zone. Returns (name, x, y) or None."""
    contours = carte_contours(ecran)
    meilleur = None
    for nom, images, debut in GENERIQUES:
        haut = int(contours.shape[0] * debut)
        zone = contours[haut:]
        for image in images:
            t = modele_contours(image, echelle)
            if t is None or zone.shape[0] < t.shape[0] or zone.shape[1] < t.shape[1]:
                continue
            h, w = t.shape
            r = cv2.matchTemplate(zone, t, cv2.TM_CCOEFF_NORMED)
            energie = cv2.boxFilter(zone, -1, (w, h), normalize=True)[h // 2:h // 2 + r.shape[0], w // 2:w // 2 + r.shape[1]]
            r[energie < 0.5 * float(t.mean())] = -1            # zone too flat (black screen...): ignored
            _, score, _, pt = cv2.minMaxLoc(r)
            if score >= SEUIL_GENERIQUE and (meilleur is None or score > meilleur[0]):
                meilleur = (score, nom, pt[0] + w / 2.0, haut + pt[1] + h / 2.0)
    return None if meilleur is None else meilleur[1:]


_BILLES = {}

def score_bille(ecran, x, y, echelle, decalage):
    """Look for the Dragon Ball near the top-left corner of the card centred at (x, y).
    Returns the best similarity (0 to 1)."""
    if "image" not in _BILLES:
        _BILLES["image"] = cv2.imread(str(TEMPLATES / f"{BILLE_IMAGE}.png"))
    modele = _BILLES["image"]
    if echelle != 1.0:
        modele = cv2.resize(modele, None, fx=echelle, fy=echelle, interpolation=cv2.INTER_AREA)
    bx, by = int(round(x + decalage[0] * echelle)), int(round(y + decalage[1] * echelle))
    m = int(round(BILLE_DEMI * echelle))
    zone = ecran[max(by - m, 0):by + m, max(bx - m, 0):bx + m]
    if zone.shape[0] < modele.shape[0] or zone.shape[1] < modele.shape[1]:
        return 0.0
    return float(cv2.matchTemplate(zone, modele, cv2.TM_CCOEFF_NORMED).max())


# --- Reading the QTE ring --------------------------------------------------
_QTE_ANGLES = np.arange(0, 360, QTE_PAS)


def lire_anneau(ecran, centre, echelle):
    """Read the colours of the QTE ring. Angles in degrees: 0 = 12 o'clock, clockwise.
    Returns 5 boolean arrays (one per angle): jaune (the bar), azur (the target zone),
    marine (the remaining path), brun (the opponent), chaud (the bar turned orange/red as it rises).
    None if the ring is outside the image."""
    cx, cy = centre
    haut, large = ecran.shape[:2]
    rayons = np.array(QTE_RAYONS, dtype=float) * echelle
    a = np.radians(_QTE_ANGLES)
    xs = np.rint(cx + np.outer(rayons, np.sin(a))).astype(int)
    ys = np.rint(cy - np.outer(rayons, np.cos(a))).astype(int)
    if xs.min() < 0 or ys.min() < 0 or xs.max() >= large or ys.max() >= haut:
        return None
    px = np.ascontiguousarray(ecran[ys, xs]).reshape(-1, 1, 3)
    hsv = cv2.cvtColor(px, cv2.COLOR_BGR2HSV).reshape(len(rayons), len(a), 3).astype(int)
    h, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    masques = (
        (h >= 18) & (h <= 36) & (sat >= 110) & (val >= 170),            # jaune
        (h >= 98) & (h <= 122) & (sat >= 80) & (sat <= 215) & (val >= 200),   # bleu clair
        (h >= 100) & (h <= 125) & (sat >= 200) & (val >= 40) & (val <= 150),  # bleu marine
        (h <= 32) & (sat >= 180) & (val >= 25) & (val <= 140),          # brun
        ((h <= 14) | (h >= 172)) & (sat >= 200) & (val >= 150),         # orange / red (the bar while it fills up)
    )
    seuil = len(rayons) - 1                                             # at least 3 radii out of 4
    return tuple(m.sum(axis=0) >= seuil for m in masques)


def centre_angulaire(masque):
    """Mean angle (degrees) of the positions marked True (circular mean: 359° and 1° give 0°)."""
    a = np.radians(_QTE_ANGLES[masque])
    return float(np.degrees(np.arctan2(np.sin(a).mean(), np.cos(a).mean())) % 360)


def ecart_signe(depart, arrivee):
    """Signed difference (-180 to +180) to go from 'depart' to 'arrivee': positive = clockwise."""
    return (arrivee - depart + 180) % 360 - 180


def decision_reste(reste, v_reste, marge_temps):
    """Tap decision based on what is left to fill on the arc (degrees, 0 = full gauge).
    v_reste = change of the remainder in degrees per second (negative: the gauge is filling).
    Returns "jauge-pleine" (full), "jauge-prevue" (it will be full when the game receives the tap) or None."""
    if reste is None:
        return None
    if reste <= QTE_RESTE_PLEIN:
        return "jauge-pleine"
    if v_reste is not None and v_reste < -60 and reste / -v_reste <= marge_temps:
        return "jauge-prevue"
    return None


def regler_latence(latence, reste_arret, v_reste, vitesse_defaut=400.0):
    """Automatic tuning of the tap delay. 'reste_arret' = what was left to fill (degrees) when the gauge
    stopped after the tap, 'v_reste' = speed of the remainder (degrees/s) at the time of the tap (negative: it was filling).
    Returns (new_latency, verdict) or None. Gauge still filling and not yet full = tap too early (we
    decrease the latency); gauge already coming down = tap too late (we increase it)."""
    if reste_arret is None:
        return None
    if reste_arret <= 2 * QTE_RESTE_PLEIN:
        return latence, "ok"
    v = abs(v_reste) if v_reste is not None and abs(v_reste) >= 100 else vitesse_defaut
    dt = min(reste_arret / v, 1.0)
    pas = min(QTE_REGLAGE_GAIN * dt, QTE_REGLAGE_PAS_MAX)
    if v_reste is not None and v_reste < -100:                       # it was still filling: too early
        nouvelle, verdict = latence - pas, "too early"
    else:                                                            # peak passed or plateau: too late
        nouvelle, verdict = latence + pas, "too late"
    return min(max(nouvelle, QTE_LATENCE_MIN), QTE_LATENCE_MAX), verdict


def placer_souris(fenetre, x, y):
    """Place the mouse without clicking (to be ready to tap as soon as the bar arrives)."""
    import pyautogui
    pyautogui.moveTo(int(fenetre.left + x), int(fenetre.top + y), duration=0, _pause=False)


def taper_vite(fenetre, x, y):
    """Immediate tap (no pause) for QTEs: the mouse is already in place."""
    import pyautogui
    pyautogui.mouseDown(_pause=False)
    time.sleep(0.05)
    pyautogui.mouseUp(_pause=False)


# =============================================================================
# 5. LE BOT
# =============================================================================
class Bot:
    def __init__(self, mode, max_combats=0, critere=None):
        self.mode = mode
        self.ecrans = MODES[mode]
        self.max_combats = max_combats          # 0 = no limit (in raid mode: number of raids)
        self.critere = critere                  # raid only: "taux" (rate), "quantite" (quantity) or None
        self.unite = "raid" if mode == "raid" else "combat"
        self.reco = Reconnaisseur()
        self.fenetre = None

        self.derniers_clics = {}                # screen name -> time of the last click
        self.combats = 0                        # finished fights
        self.essais_auto = 0                    # clicks on AUTO for the current fight
        self.auto_etat = None                   # last state seen: "on", "off" or None
        self.vu_a = time.time()                 # last time a known screen was seen
        self.actions_perdu_faites = set()       # "lost" actions already done (see SI_PERDU)
        self.echelle_reinitialisee = False
        self.clics_indulgents = 0               # "lenient" clicks on Skip during the lost episode
        self.captures_perdu = 0                 # screenshots saved in the "perdu" folder
        self.debut = time.time()
        self.arret = False                      # becomes True when the bot decides to stop by itself

        # --- raid ---
        self.etat = {"crit_ok": False, "compose_ok": False, "equipe_ok": critere is None}
        self.derniere_accueil = -1e9            # last action on the main raid screen
        self.essais_combattre = 0               # clicks on Fight from the main screen
        self.echecs_recherche = 0               # "No opponent found" since the last battle
        self.dernier_echec = -1e9
        self.balayages = 0                      # swipes made in the events list
        self.dernier_compte = -1e9              # time of the last counted raid (avoids counting twice)
        self.dans_combat = False                # raid battle in progress
        self.derniere_vue_combat = 0            # last time the battle icon was seen
        self.debut_combat = 0
        self.cartes_tapees = 0                  # cards tapped in this battle
        self.enchainements = 0                  # Rising Rush logos clicked in this battle
        self.dernier_enchainement = -1e9
        self.derniere_carte = None              # index of the last tapped card
        self.repetition_carte = 0               # how many times in a row
        self.carte_suivante = 0                 # rotation over the cards
        self.dernier_ki = time.time()
        self.derniere_bulle = -1e9              # last click on a dialogue bubble
        self.derniere_fleche = -1e9             # last click on a green arrow's target
        self.derniere_generique = -1e9          # last click on TAP / Next / Close
        self.icone_ref = None                   # last position of the "list" icon seen in battle (QTE reference point)
        self.qte_depuis = None                  # start of the current QTE (None = no QTE)
        self.qte_vu = 0                         # last time the ring was seen
        self.qte_azur = None                    # angles of the light-blue zone (remembered during the QTE)
        self.qte_mesures = []                   # recent (time, yellow/azure gap) values
        self.qte_dernier_appui = -1e9
        self.qte_total = 0                      # QTEs played in this battle
        self.qte_session = 0                    # QTEs seen since launch (for recording)
        self.qte_a_tape = False
        self.qte_latence = self.charger_latence()   # tap delay, tuned automatically after each QTE
        self.qte_calib = None                       # measurement in progress after a tap (automatic tuning)
        self.qte_sans_jaune = 0
        self.qte_pointe_max = None
        self.qte_csv = None
        self.qte_dossier = None

    # ---------- lancement ----------
    def lancer(self):
        verifier_images(self.ecrans, self.mode)
        preparer_journal(self.mode)
        configurer_souris()
        self.fenetre = trouver_fenetre()
        mettre_au_premier_plan(self.fenetre)
        log("Starting in 3 seconds...")
        time.sleep(3)
        log("Bot started (stop: mouse in the top-left corner or Ctrl+C)")
        if self.mode == "raid":
            log(f"Raid - criterion: {self.critere or 'none (current team)'}"
                + (f" - stopping after {self.max_combats} raid(s)" if self.max_combats else ""))
        self.vu_a = self.debut = time.time()
        try:
            self.boucle()
        finally:
            minutes = (time.time() - self.debut) / 60
            log(f"Finished: {self.combats} {self.unite}(s) in {minutes:.1f} min")

    def attente(self, duree):
        """Pause that keeps watching for the QTE: in raids the ring can appear during a one-second pause
        (and it only lasts a second or two). We look at the screen every ~0.08 s; if a QTE starts, we play it
        to the end before resuming the rest of the pause."""
        fin = time.time() + duree
        while time.time() < fin or self.qte_depuis is not None:
            if self.mode == "raid" and QTE_ACTIF and self.icone_ref is not None:
                try:
                    ecran = capture(self.fenetre)
                    maintenant = time.time()
                    if self.gerer_qte(ecran, maintenant):
                        self.vu_a = maintenant
                        time.sleep(QTE_PAUSE)
                        continue
                except Exception:
                    pass
            if time.time() >= fin:
                break
            time.sleep(min(QTE_ATTENTE_PAS, max(0.0, fin - time.time())))

    def boucle(self):
        """One screenshot per second: recognise the screen, act, repeat."""
        while True:
            self.fenetre = trouver_fenetre()
            ecran = capture(self.fenetre)
            maintenant = time.time()

            if self.mode == "raid":
                # QTE (ring with a gauge): very fast reading, takes priority over everything else
                if self.gerer_qte(ecran, maintenant):
                    self.vu_a = maintenant
                    time.sleep(QTE_PAUSE)
                    continue
                # Raid battle: fast loop, no AUTO button, we tap the cards ourselves
                icone = self.reco.trouve(ecran, "raid_combat_icone", 0.8, "haut")
                if icone:
                    self.icone_ref = icone
                    self.vu_a = self.derniere_vue_combat = maintenant
                    self.actions_perdu_faites.clear()
                    self.echelle_reinitialisee = False
                    self.clics_indulgents = 0
                    self.combat_raid(ecran, icone, maintenant)
                    time.sleep(PAUSE_COMBAT)
                    continue
                if self.dans_combat and maintenant - self.derniere_vue_combat > 3:
                    self.fin_combat_raid(maintenant)
                # Outside battle: green arrow, dialogue bubble, then TAP / Next / Close wherever they are
                if DIALOGUE_FLECHE and self.cliquer_fleche(ecran, maintenant):
                    self.attente(PAUSE_BOUCLE)
                    continue
                if DIALOGUE_BULLE and self.sauter_bulle(ecran, maintenant):
                    self.attente(PAUSE_BOUCLE)
                    continue
                if GENERIQUE and self.cliquer_generique(ecran, maintenant):
                    self.attente(PAUSE_BOUCLE)
                    continue

            e, position, reconnu = analyser_ecran(
                ecran, self.reco, self.ecrans, self.derniers_clics, maintenant, self.etat)
            if self.mode == "histoire" and self.en_combat(ecran):
                reconnu = True                          # fight in progress: we are not lost
                self.suivre_auto(ecran)

            if e:
                self.agir(e, position, ecran, maintenant)
                if self.objectif_atteint():
                    return

            if e or reconnu:
                self.vu_a = maintenant                  # we know where we are: counter back to zero
                self.actions_perdu_faites.clear()
                self.echelle_reinitialisee = False
                self.clics_indulgents = 0
            elif not self.gerer_perdu(ecran, maintenant):
                return
            self.attente(PAUSE_BOUCLE)

    # ---------- actions on a recognised screen ----------
    def clic_decale(self, position, dx, dy):
        """Click at (dx, dy) from the centre of the recognised image, at the window scale."""
        cx, cy, echelle = position
        cliquer(self.fenetre, cx + dx * echelle, cy + dy * echelle)

    def agir(self, e, position, ecran, maintenant):
        if e.get("special") == "visionner":
            self.agir_visionner(ecran, position, maintenant)
        elif e.get("special") == "auto":
            self.agir_auto(position, ecran)
        elif e.get("special") == "critere":
            self.agir_critere(ecran, position)
        elif e.get("special") == "raid_accueil":
            self.agir_raid_accueil(ecran, position, maintenant)
        elif e.get("special") == "trouver_raid":
            self.agir_trouver_raid(ecran, position)
        elif e.get("special") == "rejouer":
            self.agir_rejouer(position, maintenant)
        elif e.get("special") == "echec_recherche":
            self.agir_echec_recherche(position)
        else:
            for dx, dy in e["clics"]:
                self.clic_decale(position, dx, dy)
                self.attente(PAUSE_CLIC)
            message = e.get("msg", f"[{e['nom']}]")
            if message:
                log(message)
        self.derniers_clics[cle_pause(e)] = time.time()
        self.etat.update(e.get("pose", {}))

        if e.get("compte"):
            self.combats += 1
            self.essais_auto = 0
            self.auto_etat = None
            log(f"=== Fight {self.combats} finished ===")

    def agir_visionner(self, ecran, position, maintenant):
        """Read the 'Watch' checkbox before clicking (so we never tick it again)."""
        cx, cy, echelle = position
        action, x, y, n = lire_case_visionner(ecran, cx, cy, echelle)
        if action == "decocher":
            cliquer(self.fenetre, x, y)
            log(f"[watch] box ticked ({n} yellow px) -> unticking it")
        elif maintenant - self.derniers_clics.get("combattre_special", -1e9) > 4:
            cliquer(self.fenetre, x, y)
            self.derniers_clics["combattre_special"] = time.time()
            log(f"[watch] box unticked ({n} yellow px) -> Fight")

    def auto_allume(self, ecran):
        """True if the AUTO button is on (yellow)."""
        echelle = self.reco.echelle or 1.0
        return compter_jaune_auto(ecran) >= SEUIL_AUTO_ON * echelle * echelle

    def suivre_auto(self, ecran):
        """During a fight, note whether AUTO is on or off (and say it only once)."""
        if self.auto_allume(ecran):
            if self.auto_etat != "on":
                log("[fight] AUTO is on, the game fights by itself")
            self.auto_etat = "on"
            self.essais_auto = 0                        # ready for a possible new click later
        elif self.auto_etat == "on":
            log("[fight] AUTO was switched off")
            self.auto_etat = "off"

    def agir_auto(self, position, ecran):
        """Switch on the game's AUTO button. If it does not respond after 2 tries, tap the cards."""
        if self.auto_allume(ecran):
            return                                      # already on: do NOT click (it would switch it off)
        if self.essais_auto < 2:
            self.clic_decale(position, 0, 0)
            self.essais_auto += 1
            log("[fight] clicking AUTO")
        elif TAPER_CARTES_SI_AUTO_ECHOUE:
            for dx, dy in CARTES_COMBAT:
                self.clic_decale(position, dx, dy)
                time.sleep(0.4)
            log("[fight] AUTO does not respond, tapping the cards")

    # ---------- raid: navigation and team ----------
    def agir_trouver_raid(self, ecran, position):
        """Events list: click the raid banner, otherwise scroll the list."""
        logo = self.reco.trouve(ecran, "logo_assaut_raid", SEUIL_LOGO_RAID)
        if logo:
            cliquer(self.fenetre, logo[0], logo[1])
            self.balayages = 0
            log("Raid found in the list")
            return
        self.balayages += 1
        if self.balayages > RAID_BALAYAGES_MAX:
            log("Raid not found in the list, stopping.")
            self.sauver_capture(ecran)
            self.arret = True
            return
        # 8 swipes down the list, then 8 up, and so on
        vers_le_bas = ((self.balayages - 1) // 8) % 2 == 0
        w, h = self.fenetre.width, self.fenetre.height
        y1, y2 = (h * 0.70, h * 0.35) if vers_le_bas else (h * 0.35, h * 0.70)
        glisser(self.fenetre, w * 0.5, y1, w * 0.5, y2)
        log(f"Looking for the raid in the list ({self.balayages})")

    def agir_raid_accueil(self, ecran, position, maintenant):
        """Main raid screen: open the team (if a criterion is requested), otherwise click Fight."""
        if maintenant - self.derniere_accueil > 20:
            self.essais_combattre = 0                   # we had gone elsewhere: fresh start
        self.derniere_accueil = maintenant
        if maintenant - self.dernier_echec < ATTENTE_APRES_ECHEC:
            return                                      # we let some time pass after a failure
        if not self.etat["equipe_ok"]:
            icone = self.reco.trouve(ecran, "raid_equipe_icone")
            if icone:
                cliquer(self.fenetre, icone[0], icone[1])
            else:
                self.clic_decale(position, *EQUIPE_ICONE_DECALAGE)
            self.etat.update(crit_ok=False, compose_ok=False)   # we redo the whole team procedure
            log(f"Team: opening (criterion {self.critere})")
            return
        self.essais_combattre += 1
        if self.essais_combattre > RAID_ESSAIS_COMBATTRE_MAX:
            log(f"No battle after {RAID_ESSAIS_COMBATTRE_MAX} tries (daily limit?), stopping.")
            self.sauver_capture(ecran)
            self.arret = True
            return
        self.clic_decale(position, *COMBATTRE_DECALAGE)
        log("Combattre" if self.essais_combattre == 1 else f"Combattre (essai {self.essais_combattre})")

    def agir_critere(self, ecran, position):
        """'Priority criteria' window: pick the wanted option, verify by colour, close."""
        cx, cy, echelle = position
        voulu = self.critere or "taux"
        ok = False
        for essai in range(4):
            lues = lire_options_critere(ecran, cx, cy, echelle)
            choisie = option_choisie(lues)
            if choisie == voulu:
                ok = True
                break
            if essai == 3:
                break                                   # 3 clicks done and still not verified
            self.clic_decale(position, *OPTIONS_CRITERE[voulu])
            if essai > 0:
                log(f"Criterion « {voulu} »: trying again (read: {choisie or 'unreadable'})")
            time.sleep(1.0)
            ecran = capture(self.fenetre)
        if ok:
            log(f"Criterion « {voulu} »: OK")
        else:
            log(f"Criterion « {voulu} »: NOT VERIFIED ({lues}), continuing. Check the screen.")
            self.sauver_capture(ecran)
        self.clic_decale(position, *FERMER_CRITERE)
        self.etat["crit_ok"] = True

    def agir_echec_recherche(self, position):
        """'No opponent found' pop-up: OK, then the bot retries after a short wait."""
        self.clic_decale(position, *OK_ECHEC_RECHERCHE)
        self.echecs_recherche += 1
        self.dernier_echec = time.time()
        log(f"No opponent ({self.echecs_recherche}), retrying in {ATTENTE_APRES_ECHEC} s")

    def agir_rejouer(self, position, maintenant):
        """End-of-raid 'Challenges' screen: 'Play again', or OK if it was the last one requested."""
        dernier = bool(self.max_combats) and self.combats + 1 >= self.max_combats
        if dernier:
            self.clic_decale(position, *OK_DEPUIS_REJOUER)
            log("Last raid: OK (not replaying)")
        else:
            self.clic_decale(position, 0, 0)
            log("Nouveau raid")
        if maintenant - self.dernier_compte > 30:       # a raid lasts far more than 30 s: no double counting
            self.combats += 1
            self.dernier_compte = maintenant
            log(f"=== Raid {self.combats} finished ===")
        else:
            pass                                        # repeated click: this raid is already counted

    def cliquer_fleche(self, ecran, maintenant):
        """Tutorial green arrow on screen: click what it points at (every PAUSE_FLECHE s).
        Returns True while an arrow is visible: the bot then skips neither the bubble nor the rest."""
        cible = trouver_fleche(ecran, self.reco.echelle or 1.0)
        if cible is None:
            return False
        self.vu_a = maintenant                          # we know where we are: not lost
        self.actions_perdu_faites.clear()
        if maintenant - self.derniere_fleche >= PAUSE_FLECHE:
            cliquer(self.fenetre, cible[0], cible[1])
            self.derniere_fleche = time.time()
            log("[tutorial] green arrow: clicking its target")
        return True

    def sauter_bulle(self, ecran, maintenant):
        """Click a green dialogue bubble (top or bottom) to skip it. True if a click was made."""
        if maintenant - self.derniere_bulle < PAUSE_BULLE:
            return False
        centre = trouver_bulle(ecran, self.reco.echelle or 1.0)
        if centre is None:
            return False
        cliquer(self.fenetre, centre[0], centre[1])
        self.derniere_bulle = time.time()
        self.vu_a = maintenant                          # we know where we are: not lost
        self.actions_perdu_faites.clear()
        log("[dialogue] bubble skipped")
        return True

    def cliquer_generique(self, ecran, maintenant):
        """TAP / Next / Close (cross) seen somewhere: click it, even on an unknown screen."""
        if maintenant - self.derniere_generique < PAUSE_GENERIQUE:
            return False
        trouve = trouver_generique(ecran, self.reco.echelle or 1.0)
        if trouve is None:
            return False
        nom, x, y = trouve
        cliquer(self.fenetre, x, y)
        self.derniere_generique = time.time()
        self.vu_a = maintenant
        self.actions_perdu_faites.clear()
        log(f"[generic] {nom}: click")
        return True

    # ---------- raid : QTE ----------
    def gerer_qte(self, ecran, maintenant):
        """QTE ring on screen: a gauge rises and falls along the left arc; you must tap
        ONCE, when it is full (bar at the very top of the arc). The bot does not depend on a single model:
        it taps as soon as the bar reaches the top, or is about to, or covers the light-blue
        zone, or the yellow has vanished (arc completely filled), or just after the peak, and as
        a last resort before the timer ends. Returns True while a QTE is in progress."""
        if not QTE_ACTIF or self.icone_ref is None:
            return False
        ix, iy, ech = self.icone_ref
        centre = (ix + QTE_CENTRE[0] * ech, iy + QTE_CENTRE[1] * ech)
        appui = (centre[0] + QTE_APPUI[0] * ech, centre[1] + QTE_APPUI[1] * ech)   # never on the central disc
        lu = lire_anneau(ecran, centre, ech)
        en_cours = self.qte_depuis is not None
        anneau = False
        if lu is not None:
            jaune, azur, marine, brun, chaud = lu
            decor = (marine.sum() + brun.sum()) * QTE_PAS >= 120
            # gauge full on both sides: no dark-blue path or brown left, but both halves are lit
            allume = (jaune | chaud)
            deux_pleins = (allume[_QTE_ANGLES >= 180].sum() * QTE_PAS >= 120) and (allume[_QTE_ANGLES < 180].sum() * QTE_PAS >= 120)
            anneau = (decor or deux_pleins) if en_cours else (jaune.sum() >= 2 and azur.sum() >= 2 and decor)
        if not anneau:
            if en_cours and maintenant - self.qte_vu > 0.7:        # the ring has disappeared: end of the QTE
                self.fin_qte()
                return False
            return en_cours                                         # very brief gap: we wait
        self.qte_vu = maintenant
        if not en_cours:                                            # start of a QTE
            self.debut_qte(maintenant, appui)
        angles = _QTE_ANGLES
        gauche = angles >= 150                                      # the gauge arc (left side, "YOU")
        barre = jaune & gauche
        pointe = float(angles[barre].max()) if barre.any() else None    # tip of the yellow bar (the highest)
        taille = int(barre.sum()) * QTE_PAS
        if azur.sum() >= 2 and (self.qte_azur is None or azur.sum() >= self.qte_azur.sum()):
            self.qte_azur = azur                                    # (the bar may hide part of it: we keep the whole zone)
        haut_fin = float(angles[self.qte_azur].max()) if self.qte_azur is not None else 356.0
        haut_debut = float(angles[self.qte_azur].min()) if self.qte_azur is not None else 340.0
        # what is left to fill on the left arc: dark-blue path + light-blue zone still visible (0 = full gauge)
        reste = float(marine[gauche].sum() + azur[gauche].sum()) * QTE_PAS
        self.qte_mesures = [m for m in self.qte_mesures if maintenant - m[0] < 0.35] + [(maintenant, pointe, taille, reste)]
        self.qte_sans_jaune = 0 if barre.sum() >= 2 else self.qte_sans_jaune + 1
        if pointe is not None:
            self.qte_pointe_max = pointe if self.qte_pointe_max is None else max(self.qte_pointe_max, pointe)
        # speeds (degrees per second) over the last 0.35 s
        v_monte = v_taille = None
        valides = [m for m in self.qte_mesures if m[1] is not None]
        if len(valides) >= 2 and valides[-1][0] - valides[0][0] >= 0.04:
            dt = valides[-1][0] - valides[0][0]
            v_monte = (valides[-1][1] - valides[0][1]) / dt          # > 0: the bar is rising
            v_taille = (valides[0][2] - valides[-1][2]) / dt         # > 0: the bar is shrinking
        v_reste = None
        if len(self.qte_mesures) >= 2 and self.qte_mesures[-1][0] - self.qte_mesures[0][0] >= 0.04:
            v_reste = (self.qte_mesures[-1][3] - self.qte_mesures[0][3]) / (self.qte_mesures[-1][0] - self.qte_mesures[0][0])
        pas_de_temps = (self.qte_mesures[-1][0] - self.qte_mesures[-2][0]) if len(self.qte_mesures) >= 2 else 0.05
        marge_temps = self.qte_latence + 0.5 * pas_de_temps

        self.suivre_reglage(maintenant, reste)

        decision = decision_reste(reste, v_reste, marge_temps)
        if decision is not None or not QTE_REGLES_ANCIENNES:
            if decision is None and maintenant - self.qte_depuis >= QTE_SECOURS_APRES:
                decision = "secours"                                # last resort before the timer ends
        elif pointe is not None and pointe >= haut_fin - QTE_TOL_HAUT:
            decision = "haut"                                       # the bar is at the very top: gauge full
        elif barre.any() and self.qte_azur is not None and (jaune & self.qte_azur).sum() >= 0.6 * self.qte_azur.sum():
            decision = "zone"                                       # it covers most of the light-blue zone
        elif self.qte_sans_jaune >= 2 and maintenant - self.qte_depuis > 0.3:
            decision = "plein"                                      # no more yellow: the arc is completely filled
        elif pointe is not None and v_monte is not None and v_monte > 3 \
                and (haut_fin - QTE_TOL_HAUT - pointe) / v_monte <= marge_temps:
            decision = "prevu"                                      # it is rising and will be at the very top when the tap lands
        elif taille and v_taille is not None and v_taille > 5 and taille / v_taille <= marge_temps:
            decision = "prevu-plein"                                # the yellow disappears when the tap lands
        elif (self.qte_pointe_max is not None and pointe is not None and self.qte_pointe_max - pointe >= 6
              and self.qte_pointe_max >= haut_debut - 10):
            decision = "sommet"                                     # the peak has just been passed: tap fast
        elif maintenant - self.qte_depuis >= QTE_SECOURS_APRES:
            decision = "secours"                                    # last resort before the timer ends

        if decision and not (QTE_UN_SEUL_APPUI and self.qte_a_tape) and maintenant - self.qte_dernier_appui > QTE_ATTENTE:
            self.qte_dernier_appui = maintenant
            self.qte_a_tape = True
            taper_vite(self.fenetre, appui[0], appui[1])
            log(f"QTE: tap ({decision})")
            self.qte_calib = {"t": maintenant, "v": v_reste, "lectures": []} if QTE_AUTO_REGLAGE else None
        self.enregistrer_qte(ecran, centre, ech, maintenant, barre, azur, marine, brun, pointe, taille, v_monte, decision)
        return True

    def charger_latence(self):
        try:
            import json
            v = float(json.loads(QTE_REGLAGE_FICHIER.read_text(encoding="utf-8"))["latence"])
            return min(max(v, QTE_LATENCE_MIN), QTE_LATENCE_MAX)
        except Exception:
            return QTE_LATENCE

    def sauver_latence(self):
        try:
            import json
            QTE_REGLAGE_FICHIER.write_text(json.dumps({"latence": round(self.qte_latence, 3)}), encoding="utf-8")
        except Exception:
            pass

    def suivre_reglage(self, maintenant, reste):
        """After the tap the gauge stops: we re-read what was left to fill and correct the latency."""
        c = self.qte_calib
        if not c or maintenant - c["t"] < 0.15 or reste is None:
            return
        c["lectures"].append(reste)
        if len(c["lectures"]) < 3:
            return
        l = c["lectures"][-3:]
        if max(l) - min(l) > 8:                                      # it is still moving: unreliable measurement
            if maintenant - c["t"] > 0.8:
                log("QTE: the gauge does not stop after the tap, automatic tuning ignored")
                self.qte_calib = None
            return
        res = regler_latence(self.qte_latence, sorted(l)[1], c["v"])
        self.qte_calib = None
        if res is None:
            return
        nouvelle, verdict = res
        if verdict == "ok":
            log(f"QTE: gauge stopped at the top, latency {self.qte_latence:.2f} s kept")
        else:
            log(f"QTE: tap {verdict}, latency {self.qte_latence:.2f} -> {nouvelle:.2f} s")
            self.qte_latence = nouvelle
            self.sauver_latence()

    def debut_qte(self, maintenant, appui):
        self.qte_calib = None
        self.qte_depuis = maintenant
        self.qte_mesures = []
        self.qte_azur = None
        self.qte_a_tape = False
        self.qte_sans_jaune = 0
        self.qte_pointe_max = None
        self.qte_total += 1
        self.qte_session += 1
        self.qte_csv = None
        log("QTE")
        placer_souris(self.fenetre, *appui)                         # mouse placed in advance
        if self.qte_session <= QTE_ENREGISTRER_MAX:
            try:
                self.qte_dossier = QTE_DOSSIER / f"qte_{time.strftime('%Y%m%d_%H%M%S')}_{self.qte_session}"
                self.qte_dossier.mkdir(parents=True, exist_ok=True)
                fichier = open(self.qte_dossier / "mesures.csv", "w", newline="", encoding="utf-8")
                self.qte_csv = (fichier, csv.writer(fichier), 0)
                self.qte_csv[1].writerow(["t", "jaune_deg", "pointe_deg", "azur_deg", "marine_deg", "brun_deg",
                                          "v_monte", "decision"])
            except Exception:
                self.qte_csv = None

    def enregistrer_qte(self, ecran, centre, ech, maintenant, barre, azur, marine, brun, pointe, taille, v_monte, decision):
        """Keep images and measurements of the first QTEs, so the tuning can be refined afterwards."""
        if self.qte_csv is None:
            return
        try:
            fichier, ecrivain, n = self.qte_csv
            ecrivain.writerow([f"{maintenant - self.qte_depuis:.2f}", taille, "" if pointe is None else int(pointe),
                               int(azur.sum()) * QTE_PAS, int(marine.sum()) * QTE_PAS, int(brun.sum()) * QTE_PAS,
                               "" if v_monte is None else int(v_monte), decision or ""])
            r = int(200 * ech)
            x0, y0 = max(int(centre[0]) - r, 0), max(int(centre[1]) - r, 0)
            cv2.imwrite(str(self.qte_dossier / f"img_{n:03d}.jpg"), ecran[y0:int(centre[1]) + r, x0:int(centre[0]) + r],
                        [cv2.IMWRITE_JPEG_QUALITY, 80])
            self.qte_csv = (fichier, ecrivain, n + 1)
        except Exception:
            self.qte_csv = None

    def fin_qte(self):
        if not self.qte_a_tape:
            log("QTE finished without a tap")
        elif self.qte_calib is not None:
            log("QTE: the ring disappeared right after the tap, no tuning this time")
            self.qte_calib = None
        if self.qte_csv is not None:
            try:
                self.qte_csv[0].close()
            except Exception:
                pass
            self.qte_csv = None
        self.qte_depuis = None
        self.qte_azur = None

    # ---------- raid : combat ----------
    def combat_raid(self, ecran, icone, maintenant):
        """One battle action: the Rising Rush logo first, otherwise a card."""
        cx, cy, echelle = icone
        if not self.dans_combat:
            self.dans_combat = True
            self.debut_combat = maintenant
            self.cartes_tapees = 0
            self.enchainements = 0
            self.dernier_ki = maintenant
            self.essais_combattre = 0                   # a battle has started: the series of tries restarts from zero
            self.echecs_recherche = 0
            self.qte_total = 0
            log("Battle started")
        rapide = CLIC_RAPIDE

        # 1. Rising Rush (yours or the team's): as fast as possible
        if maintenant - self.dernier_enchainement > ECART_ENCHAINEMENT:
            for nom in IMAGES_ENCHAINEMENT:
                logo = self.reco.trouve(ecran, nom, SEUIL_ENCHAINEMENT)
                if logo:
                    cliquer(self.fenetre, logo[0], logo[1], rapide)
                    self.dernier_enchainement = time.time()
                    self.enchainements += 1
                    return

        # 2. Ki recharge (disabled by default)
        if KI_RECHARGE_TOUTES_LES and maintenant - self.dernier_ki > KI_RECHARGE_TOUTES_LES:
            self.dernier_ki = maintenant
            maintenir(self.fenetre, self.fenetre.width / 2, self.fenetre.height * 0.45, KI_RECHARGE_DUREE)
            pass
            return

        # 3. Une carte
        positions = [(cx + dx * echelle, cy + dy * echelle) for dx, dy in CARTES_RAID]
        index = self.choisir_carte(ecran, positions, echelle)
        cliquer(self.fenetre, positions[index][0], positions[index][1], rapide)
        self.cartes_tapees += 1

    def choisir_carte(self, ecran, positions, echelle):
        """Card with a Dragon Ball if one is visible, otherwise rotate over the 4 cards."""
        index = None
        if PRIORITE_BILLES:
            billes = [score_bille(ecran, x, y, echelle, BILLE_DECALAGES[k])
                      for k, (x, y) in enumerate(positions)]
            meilleur = max(range(len(billes)), key=lambda i: billes[i])
            # we avoid tapping the same card 3 times in a row if it does not go off
            if billes[meilleur] >= SEUIL_BILLE and not (
                    meilleur == self.derniere_carte and self.repetition_carte >= 2):
                index = meilleur
        if index is None:
            self.carte_suivante = (self.carte_suivante + 1) % len(positions)
            index = self.carte_suivante
        self.repetition_carte = self.repetition_carte + 1 if index == self.derniere_carte else 1
        self.derniere_carte = index
        return index

    def fin_combat_raid(self, maintenant):
        self.dans_combat = False
        duree = maintenant - self.debut_combat
        log(f"Battle finished ({duree:.0f} s)")

    def en_combat(self, ecran):
        """True if the pause button or the word AUTO is visible at the top left (AUTO on or off)."""
        return any(self.reco.trouve(ecran, nom, 0.8, "haut") for nom in IMAGES_EN_COMBAT)

    def objectif_atteint(self):
        if self.arret:
            return True
        if self.max_combats and self.combats >= self.max_combats:
            log(f"{self.combats} {self.unite}(s) finished, stopping.")
            return True
        return False

    # ---------- when the bot recognises nothing ----------
    def gerer_perdu(self, ecran, maintenant):
        """Apply the SI_PERDU schedule. Returns False if the bot must stop."""
        perdu = maintenant - self.vu_a
        if perdu > STOP_APRES:
            log("Unknown screen for too long, safety stop.")
            return False
        if perdu >= 10 and "capture" not in self.actions_perdu_faites:
            self.actions_perdu_faites.add("capture")
            self.sauver_capture(ecran)
        if perdu >= INDULGENT_APRES and self.mode == "histoire":
            self.chercher_passer_indulgent(ecran, maintenant)
        for seuil, action in SI_PERDU:
            if perdu >= seuil and seuil not in self.actions_perdu_faites:
                self.actions_perdu_faites.add(seuil)
                self.agir_perdu(action, ecran)
                if perdu > 120 and not self.echelle_reinitialisee:
                    self.reco.echelle = None            # in case the window changed size
                    self.echelle_reinitialisee = True
                break                                   # one action per screenshot
        return True

    def chercher_passer_indulgent(self, ecran, maintenant):
        """
        When the bot is lost, it may be a dialogue whose Skip button appears
        little by little. We look for it with a more tolerant threshold and click it.
        """
        if self.clics_indulgents >= MAX_CLICS_INDULGENTS:
            return
        if maintenant - self.derniers_clics.get("dialogue", -1e9) < 1.2:
            return
        for nom, tpl, (dx, dy) in ANCRES_DIALOGUE:
            position = self.reco.trouve(ecran, tpl, SEUIL_INDULGENT, "haut")
            if position:
                self.clic_decale(position, dx, dy)
                self.derniers_clics["dialogue"] = time.time()
                self.clics_indulgents += 1
                log(f"[lost] dialogue button spotted ({tpl}) -> clicking Skip")
                return

    def sauver_capture(self, ecran):
        """Save the unknown screen in the 'perdu' folder so it can be taught to the bot."""
        if not SAUVER_ECRANS_PERDUS or self.captures_perdu >= MAX_CAPTURES_PERDU:
            return
        try:
            DOSSIER_PERDU.mkdir(exist_ok=True)
            chemin = DOSSIER_PERDU / f"perdu_{time.strftime('%H%M%S')}.png"
            cv2.imwrite(str(chemin), ecran)
            self.captures_perdu += 1
            log(f"Unknown screen saved: {chemin.name}")
        except Exception:
            pass

    def agir_perdu(self, action, ecran):
        if action == "centre":
            log("Unknown screen: tapping the centre")
            cliquer(self.fenetre, self.fenetre.width / 2, self.fenetre.height / 2)
        elif action == "croix":
            bouton = self.reco.trouve(ecran, IMAGE_CROIX)
            log("Unknown screen: cross" if bouton else "Unknown screen: no cross")
            if bouton:
                cliquer(self.fenetre, bouton[0], bouton[1])
        elif action == "menu":
            bouton = self.reco.trouve(ecran, IMAGE_BOUTON_MENU)
            log("Unknown screen: menu" if bouton else "Unknown screen: no menu button")
            if bouton:
                cliquer(self.fenetre, bouton[0] + 3.5 * bouton[2], bouton[1] - 4 * bouton[2])
        else:  # "retour"
            bouton = self.reco.trouve(ecran, IMAGE_RETOUR)
            log("Unknown screen: back" if bouton else "Unknown screen: no back button")
            if bouton:
                cliquer(self.fenetre, bouton[0], bouton[1])


# =============================================================================
# 6. LANCEMENT
# =============================================================================
ZONES_HAUT = {"passer", "dialogue_journal", "dialogue_auto", "pause", "auto_mot",
              "raid_combat_icone", "evenements_titre"}


def diagnostic(mode="raid"):
    """Does not click: print the score of each image on the current game screen."""
    ecrans = MODES[mode]
    verifier_images(ecrans, mode)
    configurer_souris()
    fenetre = trouver_fenetre()
    log("Bringing the game to the front, looking in 3 seconds... do not touch anything.")
    mettre_au_premier_plan(fenetre)
    time.sleep(3)
    fenetre = trouver_fenetre()
    ecran, reco = capture(fenetre), Reconnaisseur()
    print(f"Window: {fenetre.width}x{fenetre.height}")
    for nom in images_necessaires(ecrans, mode):
        score, _, _, echelle = reco.meilleur(ecran, nom, "haut" if nom in ZONES_HAUT else None)
        print(f"  {nom:<22} score {score:.2f}  (scale {echelle:.2f})"
              f"  {'<- reconnu' if score >= SEUIL else ''}")
    if mode == "raid":
        diagnostic_raid(ecran, reco)


def diagnostic_raid(ecran, reco):
    """Raid-specific readings: criteria window and battle cards (nothing is clicked)."""
    titre = reco.trouve(ecran, "criteres_titre")
    if titre:
        cx, cy, echelle = titre
        lues = lire_options_critere(ecran, cx, cy, echelle)
        print(f"\nWindow « Priority criteria » seen. Yellow pixels per option: {lues}")
        print(f"  -> option selected as read by the bot: {option_choisie(lues) or 'unreadable'}")
    icone = reco.trouve(ecran, "raid_combat_icone", 0.8, "haut")
    ref = icone or (23, 73, getattr(reco, "echelle", None) or 1.0)       # without icon (QTE): usual position
    lu = lire_anneau(ecran, (ref[0] + QTE_CENTRE[0] * ref[2], ref[1] + QTE_CENTRE[1] * ref[2]), ref[2])
    if lu is not None and lu[0].sum() >= 2 and lu[1].sum() >= 2:
        jaune, azur = lu[0], lu[1]
        print(f"\nQTE seen: yellow bar around {centre_angulaire(jaune):.0f}° ({int(jaune.sum()) * QTE_PAS}° wide), "
              f"light-blue zone around {centre_angulaire(azur):.0f}° ({int(azur.sum()) * QTE_PAS}° wide) "
              f"(0° = 12 o'clock, clockwise). Gap: {ecart_signe(centre_angulaire(jaune), centre_angulaire(azur)):+.0f}°")
    if icone:
        cx, cy, echelle = icone
        image = ecran.copy()
        print("\nRaid battle seen. Cards (the bot taps the centre of each card):")
        for i, (dx, dy) in enumerate(CARTES_RAID, start=1):
            x, y = cx + dx * echelle, cy + dy * echelle
            n = score_bille(ecran, x, y, echelle, BILLE_DECALAGES[i - 1])
            print(f"  card {i}: ball similarity {n:.2f}  {'<- Dragon Ball detected' if n >= SEUIL_BILLE else ''}")
            bx, by = x + BILLE_DECALAGES[i - 1][0] * echelle, y + BILLE_DECALAGES[i - 1][1] * echelle
            r = int(round(BILLE_DEMI * echelle))
            cv2.circle(image, (int(x), int(y)), 8, (0, 0, 255), 2)
            cv2.rectangle(image, (int(bx) - r, int(by) - r), (int(bx) + r, int(by) + r), (0, 255, 255), 2)
            cv2.putText(image, f"{i}: {n:.2f}", (int(x) - 25, int(y) - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        chemin = Path(__file__).parent / "diag_raid.png"
        cv2.imwrite(str(chemin), image)
        print(f"  Image saved: {chemin.name} (red circle = where the bot taps, yellow square = zone "
              f"where it looks for the ball). Check it: if the circles are not on the cards, adjust CARTES_RAID.")


def main():
    parseur = argparse.ArgumentParser(description="Dragon Ball Legends farm bot - mode raid")
    parseur.add_argument("mode", nargs="?", choices=list(MODES) + ["diag"], default="raid",
                         help="raid (default) or diag")
    parseur.add_argument("-n", type=int, default=0, help="stop after N raids (0 = endless)")
    choix = parseur.add_mutually_exclusive_group()
    choix.add_argument("--rate", "--taux", dest="taux", action="store_true",
                       help="build the team on the item drop RATE criterion")
    choix.add_argument("--quantity", "--quantite", dest="quantite", action="store_true",
                       help="build the team on the item drop QUANTITY criterion")
    args = parseur.parse_args()

    if args.mode == "diag":
        diagnostic("raid")
        return
    critere = "taux" if args.taux else "quantite" if args.quantite else None
    import pyautogui
    try:
        Bot(args.mode, args.n, critere).lancer()
    except KeyboardInterrupt:
        log("Stopped (Ctrl+C).")
    except pyautogui.FailSafeException:
        log("Emergency stop (mouse in the top-left corner).")


if __name__ == "__main__":
    main()
