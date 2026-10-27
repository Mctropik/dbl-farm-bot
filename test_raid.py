"""
SIMULATION of raid mode (this is NOT a test on the real game).
We build fake screens (556 x 992) by pasting the cropped images at the measured positions,
then let the bot play against a fake game that reacts to clicks.
Run: python tests/test_raid.py   (takes 3 to 5 minutes; needs a filled templates/ folder)
"""
import sys, types
from pathlib import Path
import cv2, numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import farmraid as farm

T = farm.TEMPLATES
W, H = 556, 992
_cache = {}
def tpl(n):
    if n not in _cache:
        _cache[n] = cv2.imread(str(T / f"{n}.png"))
    return _cache[n]

def coller(img, nom, cx, cy, dim=1.0):
    t = tpl(nom)
    h, w = t.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    patch = (t * dim).astype(np.uint8)
    img[y0:y0 + h, x0:x0 + w] = patch

def fond(seed=0):
    rng = np.random.default_rng(seed)
    img = np.zeros((H, W, 3), np.uint8)
    base = np.linspace(50, 90, H).astype(np.uint8)[:, None, None]
    img[:] = base
    img += rng.integers(0, 12, (H, W, 3), dtype=np.uint8)
    return img

# Centres measured on the report screenshots
POS = dict(
    menu_histoire=(110, 805), menu_tuile=(90, 780), evenements_titre=(93.5, 84), logo=(364, 429),
    invit=(460, 842), equipe_icone=(427.5, 589.5), auto_select=(463.5, 589.5), regler=(278, 954),
    autosel_txt=(166.5, 131.5), modifier=(465.5, 702.5), composer=(395, 909.5),
    crit_titre=(277, 246), recherche=(277.5, 813.5), salon_titre=(107, 60), pret=(278, 957.5),
    icone_combat=(23, 73), rr=(445, 548.5), gain=(277.5, 380), appuyez=(277.5, 901),
    ok=(274, 915), jouer_encore=(176, 914.5), ok_defis=(379, 913), dissol=(277.5, 246),
)
OPT = {"capacite": (152, 314), "puissance": (402, 314), "taux": (152, 382), "quantite": (402, 382)}
CARTES = [(212, 797), (306, 782), (400, 771), (492, 760)]
FERMER = (278, 708)

def dans(pt, cible, rx=45, ry=25):
    return abs(pt[0] - cible[0]) <= rx and abs(pt[1] - cible[1]) <= ry


class FauxJeu:
    """A fake game: one screen at a time, which changes when you click in the right place."""
    def __init__(self, depart="menu", logo_apres=2, bille=True):
        self.ecran = depart
        self.clics = []
        self.logo_apres = logo_apres      # number of swipes before the banner appears
        self.glissements = 0
        self.critere = "capacite"         # criterion currently selected in the game
        self.composer_fait = False
        self.equipe = "defaut"
        self.cartes = 0
        self.par_carte = [0, 0, 0, 0]
        self.enchainements = 0
        self.rr_visible = False
        self.t_combat = 0
        self.raids = 0
        self.prets = 0
        self.dissolution = False
        self.echecs_a_faire = 0
        self.qte_modele = "A"         # A: bar that goes up and down; B: yellow gauge that fills; C: yellow that disappears when full
        self.qte_periode = 2.0        # seconds for a round trip
        self.qte_resultats = []       # one item per QTE: success or not
        self.t_qte0 = 0
        self.t_tap = None
        self.qte_ok = False
        self.bille = bille
        self.rejouer_va_vers = "accueil"
        self.dernier_clic = None
        self.erreurs = []

    # ---- images ----
    def image(self, now):
        img = fond(hash(self.ecran) % 100)
        e = self.ecran
        if e == "menu":
            coller(img, "menu_histoire", *POS["menu_histoire"])
        elif e == "menu_ouvert":
            coller(img, "menu_tuile_histoire", *POS["menu_tuile"])
        elif e == "evenements":
            coller(img, "evenements_titre", *POS["evenements_titre"])
            if self.glissements >= self.logo_apres:
                coller(img, "logo_assaut_raid", *POS["logo"])
        elif e == "accueil":
            coller(img, "raid_code_invit", *POS["invit"])
            coller(img, "raid_equipe_icone", *POS["equipe_icone"])
        elif e in ("equipes", "popup_autosel", "criteres"):
            dim = 1.0 if e == "equipes" else 0.5
            coller(img, "btn_auto_select", *POS["auto_select"], dim)
            coller(img, "btn_regler", *POS["regler"], dim)
            if e in ("popup_autosel", "criteres"):
                dim2 = 1.0 if e == "popup_autosel" else 0.5
                coller(img, "autoselect_texte", *POS["autosel_txt"], dim2)
                coller(img, "btn_modifier", *POS["modifier"], dim2)
                coller(img, "btn_composer", *POS["composer"], dim2)
            if e == "criteres":
                coller(img, "criteres_titre", *POS["crit_titre"])
                coller(img, "btn_fermer", 278, 708)
                for nom, (x, y) in OPT.items():
                    couleur = (170, 230, 250) if nom == self.critere else (225, 225, 225)  # BGR : jaune clair / gris clair
                    cv2.rectangle(img, (x - 85, y - 18), (x + 85, y + 18), couleur, -1)
        elif e == "recherche":
            coller(img, "recherche_texte", *POS["recherche"])
        elif e == "salon":
            coller(img, "salon_raid_titre", *POS["salon_titre"])
            coller(img, "raid_pret", *POS["pret"])
        elif e == "qte":
            haut, bas = self.qte_jaune(now)                          # interval of the yellow bar (degrees)
            yy, xx = np.mgrid[0:H, 0:W]
            dx, dy = xx - 278, 745 - yy
            ang = (np.degrees(np.arctan2(dx, dy)) + 360) % 360
            rad = np.hypot(dx, dy)
            anneau = (rad >= 118) & (rad <= 162)
            if self.qte_modele == "D":                                   # the real game: gauge that fills up (yellow then red)
                n = self.niveau_d(now)
                img[anneau & (ang >= 39) & (ang < 180)] = (0, 40, 47)                       # brun (adversaire)
                if getattr(self, "qte_droite_pleine", False):                               # the ally is already full
                    img[anneau & (ang >= 4) & (ang < 100)] = (0, 40, 230)
                    img[anneau & (ang >= 100) & (ang < 180)] = (90, 243, 233)
                img[anneau & (ang >= 180) & (ang < 340)] = (70, 22, 2)                      # remaining path (dark blue)
                img[anneau & (ang >= 340) & (ang <= 356)] = (255, 150, 99)                  # light-blue zone at the top
                fin = 183 + n * (356 - 183)
                img[anneau & (ang >= 183) & (ang <= min(fin, 275))] = (90, 243, 233)        # yellow at the bottom
                img[anneau & (ang > 275) & (ang <= fin)] = (0, 40, 230)                     # red above
            else:
                img[anneau & (ang >= 39) & (ang < 180)] = (0, 40, 47)         # brun (adversaire)
                img[anneau & (ang >= 180) & (ang < 340)] = (70, 22, 2)        # marine (chemin)
                img[anneau & (ang >= 340) & (ang <= 356)] = (255, 150, 99)    # light blue (zone at the top)
                if haut - bas >= 1:
                    img[anneau & (ang >= bas) & (ang <= haut)] = (90, 243, 233)   # barre jaune
        elif e == "plus_tard":
            coller(img, "btn_plus_tard", 162, 709.5)
            cv2.rectangle(img, (296, 685), (493, 735), (20, 160, 250), -1)    # the "Use" button
        elif e == "fermer":
            coller(img, "btn_fermer", 279, 930)
        elif e == "echec":
            coller(img, "salon_raid_titre", *POS["salon_titre"], 0.5)
            coller(img, "popup_echec_titre", 277.5, 354)
        elif e == "dissolution":
            coller(img, "dissolution_titre", *POS["dissol"])
            coller(img, "raid_pret", *POS["pret"], 0.5)
        elif e == "combat":
            coller(img, "raid_combat_icone", *POS["icone_combat"])
            for i, (x, y) in enumerate(CARTES):
                cv2.rectangle(img, (x - 40, y - 55), (x + 40, y + 55), (90, 60, 40), -1)
                if self.bille and i == 2:   # a Dragon Ball on the 3rd card
                    dx, dy = farm.BILLE_DECALAGES[i]
                    coller(img, "bille_dragon_ball", x + dx, y + dy)
            if self.rr_visible:
                coller(img, "rising_rush", *POS["rr"])
        elif e == "gain":
            coller(img, "gain_recomp_titre", *POS["gain"])
        elif e == "defi":
            coller(img, "appuyez_centre", *POS["appuyez"])
        elif e in ("resultats", "bravoure"):
            coller(img, "ok_raid", *POS["ok"])
        elif e == "defis":
            coller(img, "jouer_encore", *POS["jouer_encore"])
            coller(img, "ok_raid", *POS["ok_defis"])
        return img

    # ---- actions ----
    def niveau_d(self, now):
        """Model D (real game, measured on recordings): the gauge fills in 0.3 s, stays full 0.4 s,
        comes down in 0.5 s, then stays empty 0.3 s (period adjustable via qte_periode / 1.5)."""
        k = self.qte_periode / 1.5
        if getattr(self, "t_tap", None) is not None and now > self.t_tap:      # a tap freezes the gauge (as in the real game)
            now = self.t_tap
        t = ((now - self.t_qte0) % self.qte_periode) / k
        if t < 0.3:
            return t / 0.3
        if t < 0.7:
            return 1.0
        if t < 1.2:
            return 1 - (t - 0.7) / 0.5
        return 0.0

    def qte_jaune(self, now):
        """Interval (top, bottom) in degrees of the yellow bar, depending on the simulated gauge model."""
        phase = ((now - self.t_qte0) % self.qte_periode) / self.qte_periode
        niveau = 1 - abs(2 * phase - 1)                              # 0 -> 1 -> 0: the gauge rises then comes down
        if self.qte_modele == "A":                                   # 27-degree bar that goes up and down
            haut = 210 + niveau * (356 - 210)
            return haut, haut - 27
        if self.qte_modele == "B":                                   # yellow = filled part, from the bottom
            return 215 + niveau * (356 - 215), 183
        return 183 + (1 - niveau) * 140, 183                          # C: the yellow disappears when the gauge is full

    def tap_qte(self, now):
        """Bot tap during a QTE: successful if the gauge is (almost) full at that moment."""
        if self.ecran != "qte" or self.t_tap is not None:
            return
        if self.qte_modele == "D":
            recu = now + getattr(self, "latence_tap", 0.10)                      # the game receives the tap a little after the bot's click
            self.qte_niveau_au_tap = self.niveau_d(recu)
            self.t_tap = recu
            self.qte_ok = self.qte_niveau_au_tap >= 0.97
            return
        haut, bas = self.qte_jaune(now)
        self.t_tap = now
        self.qte_niveau_au_tap = haut if self.qte_modele in ("A", "B") else (haut - 183)
        self.qte_ok = (haut >= 346) if self.qte_modele in ("A", "B") else (haut - 183 <= 14)

    def glisser(self):
        self.glissements += 1

    def clic(self, x, y, now):
        self.clics.append((self.ecran, round(x), round(y), now))
        p, e = (x, y), self.ecran
        if e == "menu" and dans(p, (178, 910), 50, 30):
            self.ecran = "evenements"
        elif e == "menu_ouvert" and dans(p, (178, 910), 50, 30):
            self.ecran = "evenements"
        elif e == "evenements" and self.glissements >= self.logo_apres and dans(p, POS["logo"], 80, 39):
            self.ecran = "accueil"
        elif e == "accueil":
            if dans(p, POS["equipe_icone"], 25, 25):
                self.ecran = "equipes"
            elif dans(p, (278, 842), 70, 25) and not getattr(self, "limite", False):
                self.ecran = "recherche"; self.t = now
        elif e == "equipes":
            if dans(p, POS["auto_select"], 70, 18):
                self.ecran = "popup_autosel"
            elif dans(p, POS["regler"], 100, 24):
                self.equipe = self.critere if self.composer_fait else "defaut"
                self.ecran = "accueil"
        elif e == "popup_autosel":
            if dans(p, POS["modifier"], 37, 17):
                self.ecran = "criteres"
            elif dans(p, POS["composer"], 100, 27):
                self.composer_fait = True
                self.ecran = "equipes"
        elif e == "criteres":
            for nom, (ox, oy) in OPT.items():
                if dans(p, (ox, oy), 85, 18):
                    self.critere = nom
            if dans(p, FERMER, 90, 25):
                self.ecran = "popup_autosel"
        elif e == "salon" and dans(p, POS["pret"], 98, 20):
            self.prets += 1
            self.ecran = "combat"; self.t_combat = now; self.cartes = 0
        elif e == "dissolution":
            if dans(p, (278, 708), 60, 25):
                self.ecran = "accueil"
        elif e == "echec":
            if dans(p, (278, 813), 60, 25):
                self.ecran = "accueil"
        elif e == "plus_tard":
            if dans(p, (162, 710), 90, 22):
                self.ecran = "accueil"
        elif e == "fermer":
            if dans(p, (279, 930), 90, 22):
                self.ecran = "accueil"
        elif e == "combat":
            if self.rr_visible and dans(p, POS["rr"], 60, 36):
                self.rr_visible = False; self.enchainements += 1
                self.ecran = "qte"; self.t_qte0 = now; self.t_tap = None; self.qte_ok = False
            else:
                for i, c in enumerate(CARTES):
                    if dans(p, c, 40, 55):
                        self.cartes += 1; self.par_carte[i] += 1
        elif e == "gain" and True:
            self.ecran = "defi"
        elif e == "defi":
            self.ecran = "resultats"
        elif e == "resultats":
            self.ecran = "bravoure"
        elif e == "bravoure":
            self.ecran = "defis"
        elif e == "defis":
            if dans(p, POS["jouer_encore"], 94, 25):
                self.raids += 1
                self.ecran = "salon" if self.rejouer_va_vers == "salon" else "accueil"
            elif dans(p, POS["ok_defis"], 94, 25):
                self.raids_ok = getattr(self, "raids_ok", 0) + 1
                self.ecran = "accueil"

    def avancer(self, now):
        """Evolution of the fake game over time."""
        if self.ecran == "recherche" and now - self.t > 6:
            if self.echecs_a_faire > 0:
                self.echecs_a_faire -= 1
                self.ecran = "echec"
            else:
                self.ecran = "salon"; self.t_salon = now
        if self.ecran == "qte":
            if (self.t_tap is not None and now - self.t_tap > 0.6) or now - self.t_qte0 > 4.2:
                self.qte_resultats.append(self.qte_ok)
                self.ecran = "combat"
        if self.ecran == "combat":
            duree = now - self.t_combat
            if duree > 3 and self.cartes >= 3 and int(duree) % 7 == 0:
                self.rr_visible = True
            if duree > 40 and self.cartes >= 20:
                self.ecran = "gain"


def lancer_simulation(mode="raid", critere=None, n=0, depart="menu", jeu=None, duree_max=3000, ech=1.0, **kw):
    jeu = jeu or FauxJeu(depart, **kw)
    horloge = types.SimpleNamespace(t=1000.0)
    faux_time = types.SimpleNamespace(
        time=lambda: horloge.t,
        sleep=lambda dt: setattr(horloge, "t", horloge.t + dt),
        strftime=__import__("time").strftime)
    farm.time = faux_time
    fenetre = types.SimpleNamespace(left=0, top=0, width=int(W * ech), height=int(H * ech), isMinimized=False)
    farm.configurer_souris = lambda: None
    farm.trouver_fenetre = lambda: fenetre
    farm.mettre_au_premier_plan = lambda f: None
    def capture(f):
        jeu.avancer(horloge.t)
        img = jeu.image(horloge.t)
        return img if ech == 1.0 else cv2.resize(img, None, fx=ech, fy=ech, interpolation=cv2.INTER_AREA)
    def cliquer(f, x, y, rapide=False):
        horloge.t += 0.3 if not rapide else 0.18
        jeu.clic(x / ech, y / ech, horloge.t)
    def glisser(f, x1, y1, x2, y2, duree=0.6):
        horloge.t += 0.9
        jeu.glisser()
    def capture_qte(f):
        if jeu.ecran == "qte":
            horloge.t += 0.05                       # cost of a screenshot
        return capture(f)
    def taper_vite(f, x, y):
        horloge.t += 0.10                           # assumed delay between the bot's tap and it being registered (= QTE_LATENCE)
        jeu.positions_qte = getattr(jeu, "positions_qte", []) + [(x, y)]
        jeu.tap_qte(horloge.t)
    farm.capture, farm.cliquer, farm.glisser = capture_qte, cliquer, glisser
    farm.taper_vite, farm.placer_souris = taper_vite, (lambda f, x, y: None)
    farm.maintenir = lambda f, x, y, d: setattr(horloge, "t", horloge.t + d)
    farm.JOURNAL_ACTIF = False
    farm.QTE_ENREGISTRER_MAX = 0                    # no writing to disk during the tests
    farm.SAUVER_ECRANS_PERDUS = False
    sorties = []
    farm.log = lambda m: sorties.append(f"[{horloge.t - 1000:7.1f}s] {m}")
    bot = farm.Bot(mode, n, critere)
    bot.vu_a = bot.debut = horloge.t
    # we cap the simulated duration to never loop forever
    original = bot.boucle
    def boucle_bornee():
        import itertools
        farm_sleep = farm.time.sleep
        def sleep(dt):
            farm_sleep(dt)
            if horloge.t - 1000 > duree_max:
                raise TimeoutError("simulated duration exceeded")
        farm.time.sleep = sleep
        original()
    bot.boucle = boucle_bornee
    try:
        bot.boucle()
        fin = "normal stop"
    except TimeoutError:
        fin = "TIMEOUT"
    return bot, jeu, sorties, fin, horloge.t - 1000


def verifier(nom, condition, detail=""):
    print(f"  [{'OK' if condition else 'FAIL'}] {nom} {detail}")
    return condition


if __name__ == "__main__":
    tout_ok = True
    print("=== 1. Direct raid (no criterion), 2 raids, from the main menu ===")
    bot, jeu, sortie, fin, duree = lancer_simulation(n=2)
    tout_ok &= verifier("stop after 2 raids", fin == "normal stop" and bot.combats == 2, f"({fin}, {bot.combats} raids, {duree:.0f} s simulated)")
    tout_ok &= verifier("list scrolled until the banner is found", jeu.glissements == 2, f"({jeu.glissements} swipes)")
    tout_ok &= verifier("2nd raid finished with OK (no replay)", getattr(jeu, "raids_ok", 0) == 1 and jeu.raids == 1)
    tout_ok &= verifier("Ready clicked in every lobby", jeu.prets == 2, f"({jeu.prets})")
    tout_ok &= verifier("Rising Rush clicked", jeu.enchainements >= 1, f"({jeu.enchainements})")
    tout_ok &= verifier("no detour through the team screen", not any(c[0] in ("equipes", "criteres") for c in jeu.clics))
    print("\n".join(sortie[:60]))

    print("\n=== 2. Raid --rate (starting criterion: capacity), 1 raid ===")
    bot, jeu, sortie, fin, duree = lancer_simulation(critere="taux", n=1)
    tout_ok &= verifier("rate criterion selected in the game", jeu.critere == "taux", f"({jeu.critere})")
    tout_ok &= verifier("team composed then confirmed with Set", jeu.composer_fait and jeu.equipe == "taux", f"(team={jeu.equipe})")
    tout_ok &= verifier("1 raid done then stop", bot.combats == 1 and fin == "normal stop", f"({fin})")
    print("\n".join(sortie[:45]))

    print("\n=== 3. Raid --quantity, criterion already right: no useless click on the option ===")
    jeu = FauxJeu("accueil"); jeu.critere = "quantite"
    bot, jeu, sortie, fin, duree = lancer_simulation(critere="quantite", n=1, jeu=jeu)
    clics_options = [c for c in jeu.clics if c[0] == "criteres" and dans((c[1], c[2]), OPT["quantite"], 85, 18)]
    tout_ok &= verifier("team confirmed with quantity", jeu.equipe == "quantite" and bot.combats == 1)
    tout_ok &= verifier("option already selected: no click on it", len(clics_options) == 0, f"({len(clics_options)})")

    print("\n=== 4. Disbanded pop-up: box ticked, OK, then Fight ===")
    jeu = FauxJeu("dissolution")
    bot, jeu, sortie, fin, duree = lancer_simulation(n=1, jeu=jeu, duree_max=400)
    clics_diss = [c for c in jeu.clics if c[0] == "dissolution"]
    tout_ok &= verifier("box + OK clicked", len(clics_diss) >= 2 and dans(clics_diss[0][1:], (49, 616), 20, 20) and dans(clics_diss[1][1:], (278, 708), 20, 20), f"({clics_diss[:2]})")
    tout_ok &= verifier("then Fight again", any(c[0] == "accueil" for c in jeu.clics))

    print("\n=== 5. 'Play again' goes straight back to the lobby ===")
    jeu = FauxJeu("accueil"); jeu.rejouer_va_vers = "salon"
    bot, jeu, sortie, fin, duree = lancer_simulation(n=2, jeu=jeu)
    tout_ok &= verifier("2 raids, stop", bot.combats == 2 and fin == "normal stop", f"({fin})")

    print("\n=== 6. Teams screen shown with no criterion requested: the bot leaves it with Set ===")
    jeu = FauxJeu("equipes")
    bot, jeu, sortie, fin, duree = lancer_simulation(n=1, jeu=jeu, duree_max=120)
    tout_ok &= verifier("leaves the Teams screen", any(c[0] == "accueil" for c in jeu.clics))

    print("\n=== 7. 'No opponent found' pop-up (twice), then a raid ===")
    jeu = FauxJeu("accueil"); jeu.echecs_a_faire = 2
    bot, jeu, sortie, fin, duree = lancer_simulation(n=1, jeu=jeu)
    oks = [c for c in jeu.clics if c[0] == "echec"]
    combattres = [c for c in jeu.clics if c[0] == "accueil" and dans((c[1], c[2]), (278, 842), 70, 25)]
    tout_ok &= verifier("OK clicked on the pop-up at every failure", len(oks) == 2 and all(dans((c[1], c[2]), (278, 813), 15, 15) for c in oks), f"({[c[1:3] for c in oks]})")
    attentes = [combattres[k + 1][3] - oks[k][3] for k in range(1) if len(combattres) > 1]
    tout_ok &= verifier("wait before searching again", all(a >= farm.ATTENTE_APRES_ECHEC for a in attentes), f"({[round(a) for a in attentes]} s)")
    tout_ok &= verifier("then the raid goes normally", bot.combats == 1 and fin == "normal stop", f"({fin})")
    tout_ok &= verifier("the tries counter resets at the battle", bot.essais_combattre == 0 and bot.echecs_recherche == 0)

    print("\n=== 8. Dragon Ball: card 3 is tapped first ===")
    bot, jeu, sortie, fin, duree = lancer_simulation(n=1, depart="accueil")
    tout_ok &= verifier("card with the ball is tapped the most", jeu.par_carte[2] == max(jeu.par_carte) and jeu.par_carte[2] > jeu.par_carte[0], f"(taps per card: {jeu.par_carte})")
    tout_ok &= verifier("the other cards are tapped too (rotation)", min(jeu.par_carte) > 0, f"({jeu.par_carte})")
    bot, jeu, sortie, fin, duree = lancer_simulation(n=1, depart="accueil", bille=False)
    tout_ok &= verifier("no ball: regular rotation", max(jeu.par_carte) - min(jeu.par_carte) <= 3, f"({jeu.par_carte})")

    print("\n=== 9. Different window size (x0.85 and x1.25) ===")
    for ech in (0.85, 1.25):
        bot, jeu, sortie, fin, duree = lancer_simulation(critere="taux", n=1, ech=ech)
        tout_ok &= verifier(f"scale {ech}: full run", fin == "normal stop" and jeu.critere == "taux" and jeu.equipe == "taux" and bot.combats == 1, f"({fin}, scale found {bot.reco.echelle})")

    print("\n=== 10. Daily limit: Fight starts nothing -> clean stop ===")
    jeu = FauxJeu("accueil"); jeu.limite = True
    bot, jeu, sortie, fin, duree = lancer_simulation(n=0, jeu=jeu, duree_max=600)
    tout_ok &= verifier("stop after too many tries without a battle", fin == "normal stop" and bot.essais_combattre > farm.RAID_ESSAIS_COMBATTRE_MAX, f"({fin}, {bot.essais_combattre} tries, {duree:.0f} s)")

    print("\n=== 11. Unknown screen (black): the bot does not crash ===")
    jeu = FauxJeu("inconnu")
    bot, jeu, sortie, fin, duree = lancer_simulation(n=0, jeu=jeu, duree_max=22)   # short: each turn is slow on an unknown screen
    tout_ok &= verifier("the bot taps the centre when lost, without crashing", any("tapping the centre" in l for l in sortie), f"({duree:.0f} s simulated)")
    tout_ok &= verifier("no lenient click on a dialogue (raid)", not any("dialogue button" in l for l in sortie))

    print("\n=== 12. Banner not found: the bot stops after the swipes ===")
    jeu = FauxJeu("evenements", logo_apres=10**6)
    bot, jeu, sortie, fin, duree = lancer_simulation(n=0, jeu=jeu, duree_max=2000)
    tout_ok &= verifier("clean stop", fin == "normal stop" and jeu.glissements == farm.RAID_BALAYAGES_MAX, f"({jeu.glissements} swipes)")
    print("\n=== 13. QTE: the gauge rises and falls, the bot taps when it is full (5 behaviours) ===")
    for modele, texte in (("A", "yellow bar going up/down"), ("B", "yellow = filled part"), ("C", "yellow that disappears when full"),
                          ("D", "real game: gauge that fills up in red"), ("D2", "real game, ally already full (ring without dark blue)")):
        for periode in (1.4, 2.4):
            jeu = FauxJeu("accueil"); jeu.qte_modele = modele[0]; jeu.qte_periode = periode
            jeu.qte_droite_pleine = (modele == "D2")
            farm.QTE_REGLES_ANCIENNES = modele[0] in "ABC"
            farm.QTE_AUTO_REGLAGE = False
            farm.QTE_REGLAGE_FICHIER = Path("/inexistant/qte_reglage.json")          # the test does not touch the real setting
            bot, jeu, sortie, fin, duree = lancer_simulation(n=1, jeu=jeu)
            ok = len(jeu.qte_resultats) >= 1 and all(jeu.qte_resultats)
            tout_ok &= verifier(f"{texte}, round trip {periode} s: taps on a full gauge", ok and fin == "normal stop", f"({sum(jeu.qte_resultats)}/{len(jeu.qte_resultats)} succeeded,  {fin})")
    pos = getattr(jeu, "positions_qte", [])
    tout_ok &= verifier("the QTE is never tapped on the central disc", pos and all(((x - 278) ** 2 + (y - 745) ** 2) ** 0.5 > 150 for x, y in pos), f"(taps at {pos[:1]})")
    tout_ok &= verifier("a single tap per QTE", len(pos) == len(jeu.qte_resultats), f"({len(pos)} taps for {len(jeu.qte_resultats)} QTE)")

    print("\n=== 13b. Automatic latency tuning (simulated real game, deliberately starting too high then too low) ===")
    for depart in (0.40, 0.0):
        jeu = FauxJeu("accueil"); jeu.qte_modele = "D"; jeu.qte_periode = 2.4; jeu.qte_droite_pleine = True
        farm.QTE_REGLES_ANCIENNES = False; farm.QTE_AUTO_REGLAGE = True; farm.QTE_LATENCE = depart
        farm.QTE_REGLAGE_FICHIER = Path("/inexistant/qte_reglage.json")
        bot, jeu, sortie, fin, duree = lancer_simulation(n=1, jeu=jeu)
        fin_ok = len(jeu.qte_resultats) >= 3 and all(jeu.qte_resultats[-2:])
        tout_ok &= verifier(f"start at {depart:.2f} s: the last QTEs succeed", fin_ok, f"({jeu.qte_resultats}, final latency {bot.qte_latence:.2f} s)")
    farm.QTE_LATENCE = 0.10; farm.QTE_AUTO_REGLAGE = True

    print("\n=== 14. 'Multi Z Power' pop-up -> Later; information pop-up -> Close ===")
    for depart, nom in (("plus_tard", "Plus tard"), ("fermer", "Fermer")):
        jeu = FauxJeu(depart)
        bot, jeu, sortie, fin, duree = lancer_simulation(n=1, jeu=jeu, duree_max=60)
        tout_ok &= verifier(f"{nom} clicked in the right place then the raid continues", jeu.clics[0][0] == depart and any(c[0] == "accueil" for c in jeu.clics), f"({jeu.clics[0][:3]})")

    print("\nOVERALL RESULT:", "ALL GOOD" if tout_ok else "THERE ARE FAILURES")
