"""Create YOUR OWN recognition images (the `templates` folder) from YOUR copy of the game.

Why: the game's artwork belongs to its owners, so these images are not shipped with the bot.
How: open the game in a normal window (not full screen). For each image, this tool tells you what to crop
and on which screen. Show that screen in the game, come back here, press Enter, draw a rectangle around
the element with the mouse and confirm with Enter (or Space). Type "s" to skip an image, "q" to quit.
You can run it as many times as you like: images that already exist are not asked again.

  python create_images.py story          # images needed by the story bot (farm.py)
  python create_images.py raid           # images needed by the raid bot (farmraid.py)
  python create_images.py all            # both
  python create_images.py raid pret ok   # only those images (delete templates/<name>.png first to redo one)
"""
import json
import sys
from pathlib import Path

import cv2

import farmraid as bot

HERE = Path(__file__).parent
DESCRIPTIONS = json.loads((HERE / "image_descriptions.json").read_text(encoding="utf-8"))
SETS = json.loads((HERE / "image_sets.json").read_text(encoding="utf-8"))


def crop(name, description, screen):
    title = f"{name}: {description}  (Enter = confirm, c = cancel)"
    x, y, w, h = cv2.selectROI(title, screen, showCrosshair=False)
    cv2.destroyAllWindows()
    if w < 4 or h < 4:
        return None
    return screen[y:y + h, x:x + w]


def main(names):
    bot.TEMPLATES.mkdir(exist_ok=True)
    todo = [n for n in names if not (bot.TEMPLATES / f"{n}.png").exists()]
    if not todo:
        print("All images already exist. Nothing to do.")
        return
    print(f"{len(todo)} image(s) to create out of {len(names)}.\n")
    for i, name in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {name}: {DESCRIPTIONS.get(name, 'a game element')}")
        answer = input("   Show this screen in the game, then press Enter (s = skip, q = quit): ").strip().lower()
        if answer == "q":
            break
        if answer == "s":
            continue
        screen = bot.capture(bot.trouver_fenetre())
        piece = crop(name, DESCRIPTIONS.get(name, ""), screen)
        if piece is None:
            print("   -> nothing selected, image skipped.")
            continue
        cv2.imwrite(str(bot.TEMPLATES / f"{name}.png"), piece)
        print(f"   -> saved {name}.png ({piece.shape[1]}x{piece.shape[0]})")
    left = [n for n in names if not (bot.TEMPLATES / f"{n}.png").exists()]
    print(f"\nDone. {len(left)} image(s) still missing." if left else "\nDone: all images are ready.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] in ("story", "raid", "all"):
        mode, args = args[0], args[1:]
        names = args or (sorted(set(SETS["story"]) | set(SETS["raid"])) if mode == "all" else SETS[mode])
    else:
        names = args or sorted(set(SETS["story"]) | set(SETS["raid"]))
    main(names)
