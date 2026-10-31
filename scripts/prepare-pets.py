#!/usr/bin/env python3
"""Make the bundled pet packs in assets/ playable by the state-set mascot.

Run once after adding or regenerating a pack (it is idempotent):

    python3 scripts/prepare-pets.py

* SVG packs: copies each clip's timing from the pack's index.json onto the
  <svg> root as data-frames / data-fps / data-loop. svgstates.ts uses these to
  play reactions for whole cycles and to replay one-shot clips that are held
  (hover, alarm, sleep).
* Ember (PNG strips): builds one SVG per clip under
  assets/ember_dragon_sprites/svg/, each a frame strip stepped by a discrete
  SMIL animation, so the same player drives it. Clips can chain several
  strips, e.g. fall -> land for the intro.
* Mochi (one spritesheet): the same, from assets/mochi_pet/spritesheet.png
  into assets/mochi_pet/svg/.

Needs Pillow (pip install pillow).
"""

import base64
import io
import json
import re
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "assets"

SVG_PACKS = ["axolotl_pet", "chibi_cat_reactions", "chibi_ninja_pet", "dragon_pet_sprites", "ghost-pet", "monkey-pet", "penguin-pet", "fox-desktop-pet", "otter-pet", "red_panda_pet"]


def tag_svg_pack(pack: str) -> int:
    index = json.loads((ASSETS / pack / "index.json").read_text())
    clips = index["clips"] if isinstance(index, dict) else index
    default_fps = index.get("fps", 30) if isinstance(index, dict) else 30
    changed = 0
    for clip in clips:
        path = ASSETS / pack / "svg" / f"{clip['name']}.svg"
        text = path.read_text()
        if "data-frames=" in text[:2000]:
            continue
        fps = clip.get("fps", default_fps)
        attrs = f' data-clip="{clip["name"]}" data-frames="{clip["frames"]}" data-fps="{fps}" data-loop="{str(clip["loop"]).lower()}"'
        text, n = re.subn(r"<svg\b", "<svg" + attrs, text, count=1)
        if n != 1:
            raise SystemExit(f"{path}: no <svg> root")
        path.write_text(text)
        changed += 1
    return changed


def strip_svg(prefix: str, name: str, loop: bool, cells: list, order: list[int], durations: list[float], view_box: str) -> str:
    """One clip as an SVG: the distinct frames side by side in one WebP strip,
    stepped through `order` (indices into `cells`) by a discrete SMIL animation."""
    fw, fh = cells[0].size
    strip = Image.new("RGBA", (fw * len(cells), fh))
    for n, cell in enumerate(cells):
        strip.paste(cell, (n * fw, 0))
    buf = io.BytesIO()
    # WebP keeps the alpha edges clean at about a fifth of the PNG size, which
    # matters: every clip travels to the mascot page as text.
    strip.save(buf, "WEBP", quality=90, method=6)
    png = base64.b64encode(buf.getvalue()).decode()

    total = sum(durations)
    fps = max(1 / d for d in durations)
    key_times, t = [], 0.0
    for d in durations:
        key_times.append(f"{t / total:.5f}")
        t += d
    values = ";".join(str(-n * fw) for n in order)
    repeat = 'repeatCount="indefinite"' if loop else 'fill="freeze"'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" width="512" height="512" '
        f'data-clip="{name}" data-frames="{total * fps:.3f}" data-fps="{fps:g}" data-loop="{str(loop).lower()}">\n'
        f'<defs><clipPath id="{prefix}-{name}-frame"><rect width="{fw}" height="{fh}"/></clipPath></defs>\n'
        f'<g clip-path="url(#{prefix}-{name}-frame)"><image width="{fw * len(cells)}" height="{fh}" href="data:image/webp;base64,{png}">'
        f'<animate attributeName="x" calcMode="discrete" values="{values}" keyTimes="{";".join(key_times)}" dur="{total:.4f}s" {repeat}/>'
        f"</image></g>\n</svg>\n"
    )


# --- Ember ------------------------------------------------------------------

EMBER = ASSETS / "ember_dragon_sprites"
FW, FH = 320, 200
# The dragon's body spans x 29..204 with feet on y = 188: centre it in a square
# view with the ground near the bottom, like the SVG packs (ground ~ 92%).
# Flames and the fireball run past the right edge; the alarm overlay carries on.
VIEW_BOX = "-4 -33 240 240"

# The front view (dragon facing you) is centred on x = 160 instead of the side
# view's ~116: shift it so the dragon stays put when the clip turns to you.
FRONT_DX = -52

ALL = None
# clip name -> (loop, [(animation, (first, end) frame range or ALL, repeat, reverse)])
EMBER_CLIPS = {
    # side view: everyday life
    "idle": (True, [("idle", ALL, 1, False)]),
    "idle_blink": (True, [("idle_blink", ALL, 1, False)]),
    "sniff": (False, [("sniff", ALL, 2, False)]),
    "sit_idle": (False, [("sit", ALL, 1, False), ("sit_idle", ALL, 3, False), ("sit", ALL, 1, True)]),
    "stretch_yawn": (False, [("stretch_yawn", ALL, 1, False)]),
    "fireball": (False, [("fireball", ALL, 1, False)]),
    "play_bow": (True, [("play_bow", ALL, 1, False)]),
    "belly_up": (False, [("roll_over", ALL, 1, False), ("belly_up", ALL, 2, False), ("roll_back", ALL, 1, False)]),
    "pounce": (False, [("pounce", ALL, 1, False)]),
    "happy_hop": (True, [("happy_hop", ALL, 1, False)]),
    "fire": (True, [("fire", ALL, 1, False)]),
    "shake_off": (False, [("shake_off", ALL, 1, False)]),
    "walk": (False, [("walk", ALL, 3, False)]),
    "barrel_roll": (False, [("takeoff", ALL, 1, False), ("fly", ALL, 1, False), ("barrel_roll", ALL, 1, False), ("fly", ALL, 1, False), ("land", ALL, 1, False)]),
    "dragged": (True, [("dragged", ALL, 1, False)]),
    "drop_in": (False, [("fall", ALL, 3, False), ("land", ALL, 1, False)]),
    "fall": (True, [("fall", ALL, 1, False)]),
    "land": (False, [("land", ALL, 1, False)]),
    # thrown sideways: tumbles while sliding, then gets up and breathes fire
    # (wind-up, hold frames 6-11, cool down); window.rs times its flames to this
    "tumble": (True, [("roll_over", ALL, 1, False), ("roll_back", ALL, 1, False)]),
    "thrown_fire": (False, [("shake_off", ALL, 1, False), ("fire", (0, 6), 1, False), ("fire", (6, 12), 2, False), ("fire", (12, 15), 1, False)]),
    # sleep
    "snooze": (False, [("lie_down", ALL, 1, False), ("sleep", ALL, 1, False), ("lie_down", ALL, 1, True)]),
    "lie_down": (False, [("lie_down", ALL, 1, False)]),
    "sleep": (True, [("sleep", ALL, 1, False)]),
    "wake_up": (False, [("lie_down", ALL, 1, True), ("stretch_yawn", ALL, 1, False)]),
    # front view: coming towards you
    "intro_walk": (False, [("approach_walk", ALL, 1, False), ("front_idle", ALL, 1, False)]),
    "intro_fly": (False, [("approach_fly", ALL, 1, False), ("front_idle_blink", ALL, 1, False)]),
    "head_tilt": (True, [("head_tilt", ALL, 1, False), ("front_idle_blink", ALL, 1, False)]),
    "boop": (False, [("boop", ALL, 1, False)]),
    "front_walk": (False, [("front_walk", ALL, 3, False)]),
    "front_moment": (False, [("front_idle_blink", ALL, 1, False), ("head_tilt", ALL, 1, False), ("front_idle", ALL, 1, False)]),
    "fly_front": (False, [("takeoff", ALL, 1, False), ("fly_front", ALL, 3, False), ("land", ALL, 1, False)]),
    "front_fire": (False, [("front_fire", ALL, 1, False)]),
    # wind-up, hold the flame (frames 6-11), cool down: fire straight at you
    "front_fire_alarm": (True, [("front_fire", (0, 6), 1, False), ("front_fire", (6, 12), 4, False), ("front_fire", (12, 16), 1, False)]),
}


def ember_clip(name: str, loop: bool, parts) -> str:
    meta = json.loads((EMBER / "dragon.json").read_text())["animations"]
    # Each distinct frame is stored once; `order` plays them, repeats included.
    cells: dict[tuple[str, int], Image.Image] = {}
    order: list[tuple[str, int]] = []
    durations: list[float] = []
    for anim, span, repeat, reverse in parts:
        folder = meta[anim]["folders"][0]  # "right", or "front" for the front view
        dx = FRONT_DX if folder == "front" else 0
        sheet = Image.open(EMBER / "1x" / folder / meta[anim]["file"])
        first, end = span or (0, meta[anim]["frames"])
        seq = list(range(first, end))
        if reverse:
            seq.reverse()
        for i in seq:
            if (anim, i) not in cells:
                cell = Image.new("RGBA", (FW, FH))
                cell.paste(sheet.crop((i * FW, 0, (i + 1) * FW, FH)), (dx, 0))
                cells[(anim, i)] = cell
        order += [(anim, i) for i in seq] * repeat
        durations += [1 / meta[anim]["fps"]] * len(seq) * repeat
    slot = {key: n for n, key in enumerate(cells)}
    return strip_svg("ember", name, loop, list(cells.values()), [slot[key] for key in order], durations, VIEW_BOX)


def build_ember() -> int:
    out = EMBER / "svg"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.svg"):
        old.unlink()
    for name, (loop, parts) in EMBER_CLIPS.items():
        (out / f"{name}.svg").write_text(ember_clip(name, loop, parts))
    return len(EMBER_CLIPS)


# --- Mochi ------------------------------------------------------------------

MOCHI = ASSETS / "mochi_pet"
# spritesheet.png: one 320x320 frame per cell, one animation per row. The cat
# sits with its feet on y ~ 305, so the square frame is used as is.
MOCHI_VIEW_BOX = "0 0 320 320"
# follow_cursor is a still per direction, in the order C, N, NE, E, SE, S, SW, W, NW.
MOCHI_LOOKS = ["look_n", "look_ne", "look_e", "look_se", "look_s", "look_sw", "look_w", "look_nw"]

# clip name -> (loop, [(animation, (first, end) frame range or ALL, repeat)]);
# every other animation in spritesheet.json becomes a clip of the same name.
MOCHI_CLIPS = {
    "drop_in": (False, [("fall", ALL, 3), ("land", ALL, 1)]),
    "tumble": (True, [("spin", ALL, 1)]),
    "look_around": (False, [("look_left", ALL, 1), ("look_right", ALL, 1)]),
    **{name: (True, [("follow_cursor", (i + 1, i + 2), 1)]) for i, name in enumerate(MOCHI_LOOKS)},
}


def mochi_clip(sheet: Image.Image, meta: dict, name: str, loop: bool, parts) -> str:
    fw, fh = meta["frame_size"]
    anims = meta["animations"]
    cells: dict[tuple[str, int], Image.Image] = {}
    order: list[tuple[str, int]] = []
    durations: list[float] = []
    for anim, span, repeat in parts:
        a = anims[anim]
        first, end = span or (0, a["frames"])
        seq = list(range(first, end))
        for i in seq:
            if (anim, i) not in cells:
                cells[(anim, i)] = sheet.crop((i * fw, a["row"] * fh, (i + 1) * fw, (a["row"] + 1) * fh))
        order += [(anim, i) for i in seq] * repeat
        # Stills (fps 0) are held; one second is just the loop length.
        durations += [1 / a["fps"] if a["fps"] else 1.0] * len(seq) * repeat
    slot = {key: n for n, key in enumerate(cells)}
    return strip_svg("mochi", name, loop, list(cells.values()), [slot[key] for key in order], durations, MOCHI_VIEW_BOX)


def build_mochi() -> int:
    meta = json.loads((MOCHI / "spritesheet.json").read_text())
    sheet = Image.open(MOCHI / "spritesheet.png").convert("RGBA")
    clips = {name: (a["loop"], [(name, ALL, 1)]) for name, a in meta["animations"].items() if a["fps"]}
    clips.update(MOCHI_CLIPS)
    out = MOCHI / "svg"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.svg"):
        old.unlink()
    for name, (loop, parts) in clips.items():
        (out / f"{name}.svg").write_text(mochi_clip(sheet, meta, name, loop, parts))
    return len(clips)


if __name__ == "__main__":
    for pack in SVG_PACKS:
        print(f"{pack}: tagged {tag_svg_pack(pack)} clips")
    print(f"ember_dragon_sprites: built {build_ember()} clips")
    print(f"mochi_pet: built {build_mochi()} clips")
    # After the rebuilds above, which clear the Ember and Mochi folders.
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_throw_clips", Path(__file__).with_name("make-throw-clips.py"))
    throws = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(throws)
    throws.main()
