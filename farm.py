"""
FARM BOT - STORY MODE - Dragon Ball Legends (Google Play Games PC)
========================================================================

HOW TO RUN IT (game open in windowed mode, on the main menu):
    python farm.py histoire          -> runs until you stop it
    python farm.py histoire -n 3     -> stops after 3 finished fights
    python farm.py diag              -> does not click, shows what the bot sees

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
    6. LAUNCH             -> the commands (story / diag)
"""
import argparse
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
SAUVER_ECRANS_PERDUS = True
MAX_CAPTURES_PERDU = 40                 # so your disk does not fill up

# --- Advanced settings (only change them if you know what you are doing) ---
SEUIL = 0.88            # minimum similarity (0 to 1) to recognise an image
SEUIL_DIALOGUE = 0.75   # minimum similarity for dialogue buttons (top zone only)
SEUIL_INDULGENT = 0.68  # ... when the bot is lost: look for Skip more loosely
INDULGENT_APRES = 4     # seconds of being "lost" before the lenient search for Skip
MAX_CLICS_INDULGENTS = 8  # max lenient clicks per "lost" episode (avoids looping)
SEUIL_COCHE = 15        # minimum yellow pixels to say the "Watch" checkbox is ticked

# Pop-ups with the "Do not show this dialog again" checkbox ("Confirm story
# challenge", "Check Leader Bonuses"):
#   True  = the bot ticks the box, then clicks Yes (the pop-up no longer comes back)
#   False = it only clicks Yes (the pop-up will come back every time)
COCHER_NE_PLUS_AFFICHER = True
# Green dialogue bubbles (e.g. a master in "Edit character", at the top or bottom of the screen):
# True = the bot clicks them to skip the dialogue.
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
SEUIL_AUTO_ON = 300     # minimum yellow pixels (top-left corner) to say AUTO is on
PAUSE_BOUCLE = 1.0      # secondes entre deux captures
PAUSE_CLIC = 0.5        # seconds between two clicks of the same action
TEMPLATES = Path(__file__).parent / "templates"
DOSSIER_PERDU = Path(__file__).parent / "perdu"
ZONE_HAUT = 0.18        # "top zone" = the upper 18% of the window (Skip, pause, AUTO buttons)


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
#   special : action coded separately ("visionner", "auto" or "coche_oui")
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

    # Pop-ups with the "Do not show this dialog again" checkbox: we tick the box
    # (COCHER_NE_PLUS_AFFICHER setting) then click Yes. Same layout for both.
    {"nom": "popup_defi_histoire", "tpl": "popup_defi_histoire_titre", "special": "coche_oui",
     "pause": 4, "bloque": True},
    {"nom": "popup_bonus_leader", "tpl": "popup_bonus_leader_titre", "special": "coche_oui",
     "pause": 4, "bloque": True},

    # Pop-up "Error - A communication error occurred." -> Title button (back to the title screen)
    {"nom": "popup_erreur", "tpl": "erreur_texte", "clics": [(49, 414)], "pause": 5,
     "bloque": True, "groupe": "popup_titre"},

    # Full-screen tutorials (e.g. "Customise your character"): Next button, then Close.
    # They may be somewhere unexpected: we click the button image wherever it is.
    {"nom": "tuto_suivant", "tpl": "tuto_suivant", "clics": [(0, 0)], "pause": 2, "bloque": True},
    {"nom": "tuto_fermer", "tpl": "tuto_fermer", "clics": [(0, 0)], "pause": 2, "bloque": True},

    # "TAP" bar / button (rewards, equipment awakening...) -> one click on it
    {"nom": "appuyez_barre", "tpl": "appuyez_barre", "clics": [(0, 0)], "pause": 2, "bloque": True,
     "groupe": "appuyez"},
    {"nom": "appuyez_centre", "tpl": "appuyez_centre", "clics": [(0, 0)], "pause": 2, "bloque": True,
     "groupe": "appuyez"},

    # End of an equipment awakening: Finish button. Placed AFTER "TAP": during the reward animation
    # Finish is greyed out and we must tap first.
    {"nom": "bouton_terminer", "tpl": "btn_terminer", "clics": [(0, 0)], "pause": 3, "bloque": True},

    # "Edit character" screen (reached by mistake) -> back arrow at the bottom left
    {"nom": "modif_perso", "tpl": "modif_perso_titre", "clics": [(-60, 924)], "pause": 4,
     "zone": "haut"},

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

# The available modes. To add another mode later: create its screen list and add it here.
MODES = {"histoire": ECRANS_HISTOIRE}

# Special images (not screens to click)
IMAGES_EN_COMBAT = ["pause", "auto_mot", "auto_on"]   # any of them = a fight is in progress
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
    """Print a message with the time."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")


def images_necessaires(ecrans):
    """List of the images (templates) the bot needs for this mode."""
    noms = {e["tpl"] for e in ecrans} | {e["sauf_si"] for e in ecrans if "sauf_si" in e}
    return sorted(noms | set(IMAGES_EN_COMBAT) | {IMAGE_RETOUR, IMAGE_BOUTON_MENU, IMAGE_CROIX})


def verifier_images(ecrans):
    """Stop with a clear message if images are missing from templates/."""
    manquantes = [n for n in images_necessaires(ecrans) if not (TEMPLATES / f"{n}.png").exists()]
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
                sys.exit(f"Image manquante : {TEMPLATES / (nom + '.png')}")
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


def analyser_ecran(ecran, reco, ecrans, derniers_clics, maintenant):
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
        if maintenant - derniers_clics.get(cle_pause(e), -1e9) < e["pause"]:
            if e.get("bloque"):
                return None, None, True                # pop-up is closing: we wait
            continue                                   # we just clicked here
        if "sauf_si" in e and reco.trouve(ecran, e["sauf_si"]):
            continue                                   # a more precise screen handles it
        if "apres" in e:
            autre, delai = e["apres"]
            if maintenant - derniers_clics.get(autre, -1e9) < delai:
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


def cliquer(fenetre, x, y):
    """'Human' click: the mouse arrives, pauses for a moment, presses, then releases.
    (Some games ignore clicks that are too fast.)  x and y are relative to the window."""
    import pyautogui
    pyautogui.moveTo(int(fenetre.left + x), int(fenetre.top + y), duration=0.15)
    time.sleep(0.1)
    pyautogui.mouseDown()
    time.sleep(0.1)
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


# --- Green dialogue bubbles and "Do not show again" checkboxes ------------
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


def extrait_case(ecran, x, y, echelle, demi=9):
    """Small square of the screen around (x, y): used to see whether a click changed the box."""
    r = int(round(demi * echelle))
    return ecran[max(int(y) - r, 0):int(y) + r, max(int(x) - r, 0):int(x) + r].astype(np.int16)


def case_a_change(avant, apres, seuil=8.0):
    if avant.shape != apres.shape or avant.size == 0:
        return False
    return float(np.abs(avant - apres).mean()) >= seuil


# =============================================================================
# 5. LE BOT
# =============================================================================
class Bot:
    def __init__(self, mode, max_combats=0):
        self.ecrans = MODES[mode]
        self.max_combats = max_combats          # 0 = no limit
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
        self.derniere_bulle = -1e9              # last click on a dialogue bubble
        self.derniere_fleche = -1e9             # last click on a green arrow's target
        self.derniere_generique = -1e9          # last click on TAP / Next / Close

    # ---------- lancement ----------
    def lancer(self):
        verifier_images(self.ecrans)
        configurer_souris()
        self.fenetre = trouver_fenetre()
        mettre_au_premier_plan(self.fenetre)
        log("Bring the game to the front, starting in 3 seconds...")
        time.sleep(3)
        log("Bot started. Mouse in the top-left corner (or Ctrl+C) to stop.")
        self.vu_a = self.debut = time.time()
        try:
            self.boucle()
        finally:
            minutes = (time.time() - self.debut) / 60
            log(f"Finished: {self.combats} fight(s) in {minutes:.1f} min.")

    def boucle(self):
        """One screenshot per second: recognise the screen, act, repeat."""
        while True:
            self.fenetre = trouver_fenetre()
            ecran = capture(self.fenetre)
            maintenant = time.time()

            if DIALOGUE_FLECHE and self.cliquer_fleche(ecran, maintenant):
                time.sleep(PAUSE_BOUCLE)
                continue
            if DIALOGUE_BULLE and self.sauter_bulle(ecran, maintenant):
                time.sleep(PAUSE_BOUCLE)
                continue
            if GENERIQUE and self.cliquer_generique(ecran, maintenant):
                time.sleep(PAUSE_BOUCLE)
                continue

            e, position, reconnu = analyser_ecran(
                ecran, self.reco, self.ecrans, self.derniers_clics, maintenant)
            if self.en_combat(ecran):
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
            time.sleep(PAUSE_BOUCLE)

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
        elif e.get("special") == "coche_oui":
            self.agir_coche_oui(e, ecran, position)
        else:
            for dx, dy in e["clics"]:
                self.clic_decale(position, dx, dy)
                time.sleep(PAUSE_CLIC)
            log(f"[{e['nom']}]")
        self.derniers_clics[cle_pause(e)] = time.time()

        if e.get("compte"):
            self.combats += 1
            self.essais_auto = 0
            self.auto_etat = None
            log(f"=== Fight {self.combats} finished ===")

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

    def agir_coche_oui(self, e, ecran, position):
        """Pop-up with the "Do not show again..." checkbox: tick the box (if enabled), then click Yes."""
        cx, cy, echelle = position
        case_x, case_y = cx - 230 * echelle, cy + 373 * echelle
        if COCHER_NE_PLUS_AFFICHER:
            avant = extrait_case(ecran, case_x, case_y, echelle)
            for essai in (1, 2):
                cliquer(self.fenetre, case_x, case_y)
                time.sleep(0.6)
                if case_a_change(avant, extrait_case(capture(self.fenetre), case_x, case_y, echelle)):
                    break                               # the box did change: it is ticked
            else:
                log(f"[{e['nom']}] WARNING: I did not see the box change, clicking Yes anyway")
        self.clic_decale(position, 116, 463)            # bouton Oui
        log(f"[{e['nom']}] " + ("box ticked, Yes" if COCHER_NE_PLUS_AFFICHER else "Oui"))

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

    def en_combat(self, ecran):
        """True if the pause button or the word AUTO is visible at the top left (AUTO on or off)."""
        return any(self.reco.trouve(ecran, nom, 0.8, "haut") for nom in IMAGES_EN_COMBAT)

    def objectif_atteint(self):
        if self.max_combats and self.combats >= self.max_combats:
            log("Requested number of fights reached, stopping.")
            return True
        return False

    # ---------- when the bot recognises nothing ----------
    def gerer_perdu(self, ecran, maintenant):
        """Apply the SI_PERDU schedule. Returns False if the bot must stop."""
        perdu = maintenant - self.vu_a
        if perdu > STOP_APRES:
            log("Lost for too long, safety stop.")
            return False
        if perdu >= 10 and "capture" not in self.actions_perdu_faites:
            self.actions_perdu_faites.add("capture")
            self.sauver_capture(ecran)
        if perdu >= INDULGENT_APRES:
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
            log(f"[lost] unknown screen saved: {chemin.name}")
        except Exception:
            pass

    def agir_perdu(self, action, ecran):
        if action == "centre":
            log("[lost] tapping the centre")
            cliquer(self.fenetre, self.fenetre.width / 2, self.fenetre.height / 2)
        elif action == "croix":
            bouton = self.reco.trouve(ecran, IMAGE_CROIX)
            log("[lost] closing with the cross" if bouton else "[lost] no cross visible")
            if bouton:
                cliquer(self.fenetre, bouton[0], bouton[1])
        elif action == "menu":
            bouton = self.reco.trouve(ecran, IMAGE_BOUTON_MENU)
            log("[lost] opening the game menu" if bouton else "[lost] menu button not visible")
            if bouton:
                cliquer(self.fenetre, bouton[0] + 3.5 * bouton[2], bouton[1] - 4 * bouton[2])
        else:  # "retour"
            bouton = self.reco.trouve(ecran, IMAGE_RETOUR)
            log("[lost] trying the back button" if bouton else "[lost] no back button visible")
            if bouton:
                cliquer(self.fenetre, bouton[0], bouton[1])


# =============================================================================
# 6. LANCEMENT
# =============================================================================
ZONES_HAUT = {"passer", "dialogue_journal", "dialogue_auto", "pause", "auto_mot", "modif_perso_titre"}


def diagnostic(mode="histoire"):
    """Does not click: print the score of each image on the current game screen."""
    ecrans = MODES[mode]
    verifier_images(ecrans)
    configurer_souris()
    fenetre = trouver_fenetre()
    log("Bringing the game to the front, looking in 3 seconds... do not touch anything.")
    mettre_au_premier_plan(fenetre)
    time.sleep(3)
    fenetre = trouver_fenetre()
    ecran, reco = capture(fenetre), Reconnaisseur()
    print(f"Window: {fenetre.width}x{fenetre.height}")
    for nom in images_necessaires(ecrans):
        score, _, _, echelle = reco.meilleur(ecran, nom, "haut" if nom in ZONES_HAUT else None)
        print(f"  {nom:<22} score {score:.2f}  (scale {echelle:.2f})"
              f"  {'<- reconnu' if score >= SEUIL else ''}")
    bulle = trouver_bulle(ecran, reco.echelle or 1.0)
    print(f"  green dialogue bubble: {'SEEN at centre ' + str(tuple(round(v) for v in bulle)) if bulle else 'not seen'}")


def main():
    parseur = argparse.ArgumentParser(description="Dragon Ball Legends farm bot")
    parseur.add_argument("mode", choices=list(MODES) + ["diag"])
    parseur.add_argument("-n", type=int, default=0, help="stop after N fights (0 = endless)")
    args = parseur.parse_args()

    if args.mode == "diag":
        diagnostic()
        return
    import pyautogui
    try:
        Bot(args.mode, args.n).lancer()
    except KeyboardInterrupt:
        log("Stopped (Ctrl+C).")
    except pyautogui.FailSafeException:
        log("Emergency stop (mouse in the top-left corner).")


if __name__ == "__main__":
    main()
