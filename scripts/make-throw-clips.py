#!/usr/bin/env python3
"""Throw reactions for the bundled pets, made from each pet's own clips.

Run after prepare-pets.py (which calls it at the end, since it rebuilds the
Ember and Mochi folders from scratch):

    python3 scripts/make-throw-clips.py

The packs come from different generators (and some are finished art), so
instead of redrawing each pet this wraps one of its existing clips in extra
motion and draws a few effects on top, in the clip's own viewBox:

* throw_tumble   flung sideways: rolls head over heels (loops, faces right)
* throw_whee     flung up: sways and stretches, rushing air, sparkles (loops)
* throw_panic    flung up or down: shakes in panic, sweat drop (loops)
* throw_dive     flung down: upside down, head first, rushing air (loops)
* land_splat     squashed flat, pops back up with a boing, shakes it off
* land_dizzy     crash-lands, wobbles around with stars circling its head
* land_grumpy    lands with a bump, then plays its annoyed clip

The Chibi Ninja has hand-made versions from its own rig and is skipped.
Every file is regenerated each run, so edit this script, not the output.
"""

import math
import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FPS = 30
OUT_COL = "#2b2533"
STAR_COL = "#ffd84a"
DUST_COL = "#eceaf2"
SWEAT_COL = "#dff1ff"

# Per pack: the folder holding the clips, the resting pose's bounding box in
# viewBox units (x0, y0, x1, y1; measured once from the idle frame's alpha),
# and which clip plays each part. `head_x` moves the dizzy stars for a side
# view (fraction of the box width; default the middle); `shadow` matches the
# ground shadow, if it isn't the usual faint path.
PACKS = {
    "axolotl_pet": dict(box=(67, 146, 445, 485), sit="idle_breathe", tumble="int_poked", happy="mood_happy", scared="mood_surprised", annoyed="int_poked"),
    "chibi_cat_reactions": dict(box=(125, 178, 387, 475), sit="idle_breathe", tumble="mood_surprised", happy="mood_happy", scared="mood_surprised", annoyed="int_poked"),
    "dragon": dict(dir="", box=(131, 122, 669, 750), shadow=r'<ellipse[^>]*rx="140"[^>]*/>', sit="happy", tumble="fly", happy="fly", scared="sad", annoyed="flame"),
    "dragon_pet_sprites": dict(box=(120, 173, 392, 493), shadow=r'<ellipse[^>]*rx="150"[^>]*/>', sit="idle_breathe", tumble="mood_surprised", happy="mood_happy", scared="mood_surprised", annoyed="int_poked"),
    "ember_dragon_sprites": dict(box=(29, 89, 204, 193), head_x=0.82, sit="sit_idle", tumble="tumble", happy="happy_hop", scared="fall", annoyed="shake_off"),
    "fox-desktop-pet": dict(box=(134, 137, 378, 498), sit="idle_breathe", tumble="mood_surprised", happy="mood_happy", scared="mood_surprised", annoyed="int_poked"),
    "ghost-pet": dict(box=(100, 136, 412, 485), sit="idle_breathe", tumble="mood_scared", happy="mood_happy", scared="mood_scared", annoyed="int_poked"),
    "mochi_pet": dict(box=(62, 112, 271, 303), sit="breathe", tumble="surprised", happy="happy", scared="surprised", annoyed="poked"),
    "monkey-pet": dict(box=(109, 136, 403, 474), sit="idle_breathe", tumble="mood_surprised", happy="mood_happy", scared="mood_surprised", annoyed="mood_angry"),
    "otter-pet": dict(box=(149, 116, 387, 482), sit="idle_breathe", tumble="mood_surprised", happy="mood_happy", scared="mood_surprised", annoyed="int_poked"),
    "penguin-pet": dict(box=(139, 86, 373, 487), sit="idle_breathe", tumble="mood_surprised", happy="mood_happy", scared="mood_surprised", annoyed="int_poked"),
    "red_panda_pet": dict(box=(134, 161, 436, 482), sit="idle_breathe", tumble="mood_surprised", happy="mood_smile_wink", scared="mood_surprised", annoyed="mood_angry"),
}

SPLINES = {"io": "0.42 0 0.58 1", "sine": "0.37 0 0.63 1", "in": "0.42 0 1 1", "out": "0 0 0.58 1", "lin": "0 0 1 1", "snap": "0.12 0.85 0.25 1"}


def num(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def anim(kind: str, keys: list, n: int, loop: bool) -> str:
    """keys: [(frame, value, ease)] with value a number or tuple; kind is a
    transform type (translate / rotate / scale) or "opacity"."""
    if keys[0][0] > 0:
        keys = [(0, keys[0][1], "lin")] + keys
    if keys[-1][0] < n:
        keys = keys + [(n, keys[-1][1], "lin")]
    fmt = lambda v: " ".join(num(c) for c in v) if isinstance(v, tuple) else num(v)
    vals = ";".join(fmt(v) for _, v, _ in keys)
    times = ";".join(f"{f / n:.4f}" for f, _, _ in keys)
    splines = ";".join(SPLINES[e] for _, _, e in keys[:-1])
    repeat = 'repeatCount="indefinite"' if loop else 'fill="freeze"'
    timing = f'dur="{num(n / FPS)}s" {repeat} calcMode="spline" values="{vals}" keyTimes="{times}" keySplines="{splines}"'
    if kind == "opacity":
        return f'<animate attributeName="opacity" {timing}/>'
    return f'<animateTransform attributeName="transform" type="{kind}" {timing}/>'


class Clip:
    def __init__(self, n: int, loop: bool):
        self.n, self.loop = n, loop

    def a(self, kind: str, keys: list) -> str:
        return anim(kind, keys, self.n, self.loop)

    def g(self, kind: str, keys: list, inner: str) -> str:
        return f"<g>{self.a(kind, keys)}{inner}</g>"

    def about(self, kind: str, keys: list, x: float, y: float, inner: str) -> str:
        """Scale (or rotate) around the point (x, y)."""
        back = f'<g transform="translate({num(-x)} {num(-y)})">{inner}</g>'
        return f'<g transform="translate({num(x)} {num(y)})">{self.g(kind, keys, back)}</g>'

    def show(self, f0: float, f1: float, inner: str) -> str:
        """Visible from frame f0 to f1 only (within the clip)."""
        f1 = min(f1, self.n - 0.02)
        keys = [(0, 0, "lin"), (max(f0 - 0.01, 0), 0, "lin"), (f0, 1, "lin"), (f1, 1, "lin"), (min(f1 + 0.01, self.n), 0, "lin")]
        return f'<g opacity="0">{self.a("opacity", keys)}{inner}</g>'


def wiggle(f0: float, f1: float, amp, period: float, center=0.0, ease: str = "sine") -> list:
    """Sine wiggle from f0 to f1 that fades in and out, ending on center."""
    keys = [(f0, center, ease)]
    k = 1
    while f0 + k * period / 2 < f1 - period / 4:
        f = f0 + k * period / 2 - period / 4
        env = math.sin(math.pi * (f - f0) / (f1 - f0)) * (1 if k % 2 else -1)
        keys.append((f, tuple(c + a * env for c, a in zip(center, amp)) if isinstance(center, tuple) else center + amp * env, ease))
        k += 1
    return keys + [(f1, center, "lin")]


# ---------------------------------------------------------------- effects (u = size unit)
def star5(x: float, y: float, r: float) -> str:
    pts = " ".join(f"{num(x + (r if k % 2 == 0 else r * 0.45) * math.cos(math.radians(-90 + 36 * k)))},{num(y + (r if k % 2 == 0 else r * 0.45) * math.sin(math.radians(-90 + 36 * k)))}" for k in range(10))
    return f'<polygon points="{pts}" fill="{STAR_COL}" stroke="{OUT_COL}" stroke-width="{num(r * 0.22)}" stroke-linejoin="round"/>'


def sparkle(x: float, y: float, r: float) -> str:
    w = r * 0.3
    d = f"M{num(x)} {num(y - r)}Q{num(x + w * 0.4)} {num(y - w * 0.4)} {num(x + r)} {num(y)}Q{num(x + w * 0.4)} {num(y + w * 0.4)} {num(x)} {num(y + r)}Q{num(x - w * 0.4)} {num(y + w * 0.4)} {num(x - r)} {num(y)}Q{num(x - w * 0.4)} {num(y - w * 0.4)} {num(x)} {num(y - r)}Z"
    return f'<path d="{d}" fill="#ffffff" stroke="{OUT_COL}" stroke-width="{num(r * 0.2)}" stroke-linejoin="round"/>'


def lines(x: float, y: float, u: float, angle: float) -> str:
    """Four speed lines starting at (x, y), pointing along `angle` (deg)."""
    out = []
    for dy, dx, length in ((-30, 0, 40), (-10, 14, 54), (10, 4, 36), (30, 18, 48)):
        x0, x1 = x + dx * u, x + (dx + length) * u
        seg = f'x1="{num(x0)}" y1="{num(y + dy * u)}" x2="{num(x1)}" y2="{num(y + dy * u)}"'
        out.append(f'<line {seg} stroke="{OUT_COL}" stroke-width="{num(9 * u)}" stroke-linecap="round"/><line {seg} stroke="#ffffff" stroke-width="{num(3.5 * u)}" stroke-linecap="round"/>')
    return f'<g transform="rotate({num(angle)} {num(x)} {num(y)})">{"".join(out)}</g>'


def puff(c: Clip, f0: float, f1: float, x: float, y: float, u: float) -> str:
    blobs = ((0, -4, 20), (-20, 6, 15), (20, 6, 16), (-9, 14, 13), (10, 15, 13))
    shape = "".join(f'<circle cx="{num(bx * u)}" cy="{num(by * u)}" r="{num((r + 4) * u)}" fill="{OUT_COL}"/>' for bx, by, r in blobs)
    shape += "".join(f'<circle cx="{num(bx * u)}" cy="{num(by * u)}" r="{num(r * u)}" fill="{DUST_COL}"/>' for bx, by, r in blobs)
    grow = c.g("scale", [(f0, (0.2, 0.2), "snap"), (f0 + 5, (1.0, 1.0), "io"), (f1 - 4, (1.06, 1.06), "in"), (f1, (0.01, 0.01), "lin")], shape)
    drift = c.g("translate", [(f0, (x, y), "out"), (f1, (x, y - 10 * u), "lin")], grow)
    return c.show(f0, f1, drift)


def sweat(x: float, y: float, u: float) -> str:
    d = f"M{num(x)} {num(y - 16 * u)}Q{num(x + 11 * u)} {num(y)} {num(x + 9 * u)} {num(y + 6 * u)}A{num(9 * u)} {num(9 * u)} 0 1 1 {num(x - 9 * u)} {num(y + 6 * u)}Q{num(x - 11 * u)} {num(y)} {num(x)} {num(y - 16 * u)}Z"
    return f'<path d="{d}" fill="{SWEAT_COL}" stroke="{OUT_COL}" stroke-width="{num(3.5 * u)}"/>'


# ---------------------------------------------------------------- source clips
def load(path: Path) -> tuple[str, str, float]:
    """Root attributes (minus size/timing), inner markup, length in frames."""
    text = path.read_text()
    m = re.search(r"<svg\b([^>]*)>", text)
    attrs = m.group(1)
    frames = float(re.search(r'data-frames="([^"]+)"', attrs).group(1)) if "data-frames" in attrs else 90.0
    fps = float(re.search(r'data-fps="([^"]+)"', attrs).group(1)) if "data-fps" in attrs else FPS
    attrs = re.sub(r'\s(data-[\w-]+|width|height)="[^"]*"', "", attrs)
    body = re.sub(r"<title>.*?</title>", "", text[m.end(): text.rindex("</svg>")], flags=re.S)
    return attrs, body, frames / fps * FPS


FAINT_PATH = r'<path[^>]*fill-opacity="0?\.(?:[01]\d*|2)"[^>]*/>'


def airborne(body: str, shadow: str = FAINT_PATH) -> str:
    """Without its ground shadow (one faint path in most packs): it's in the air."""
    return re.sub(shadow, "", body, count=1)


def save(path: Path, name: str, attrs: str, c: Clip, inner: str):
    path.write_text(
        f'<svg data-clip="{name}" data-frames="{c.n}" data-fps="{FPS}" data-loop="{str(c.loop).lower()}"{attrs} width="512" height="512">{inner}</svg>\n'
    )


# ---------------------------------------------------------------- the clips
def build(pack: str, cfg: dict) -> int:
    folder = ASSETS / pack / cfg.get("dir", "svg")
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', (folder / f"{cfg['sit']}.svg").read_text()).group(1).split()]
    x0, y0, x1, y1 = cfg["box"]
    w, h = x1 - x0, y1 - y0
    cx, cy, ground = (x0 + x1) / 2, (y0 + y1) / 2, y1
    vcx, vcy = vb[0] + vb[2] / 2, vb[1] + vb[3] / 2
    u = h / 300  # effects are drawn for a ~300 px tall pet
    hx = x0 + w * cfg.get("head_x", 0.5)
    src = {role: load(folder / f"{cfg[role]}.svg") for role in ("sit", "tumble", "happy", "scared", "annoyed")}
    attrs = src["sit"][0]
    # Fit a rotating pet inside the canvas.
    spin_fit = min(1.0, 0.48 * min(vb[2], vb[3]) / math.hypot(w / 2, h / 2))
    flip_fit = min(1.0, 0.47 * vb[3] / (h / 2))
    wide = min(1.45, 0.98 * vb[2] / w)
    out = []
    lift = lambda body: airborne(body, cfg.get("shadow", FAINT_PATH))

    def centred(body: str, fit: float) -> str:
        return f'<g transform="scale({num(fit)}) translate({num(-cx)} {num(-cy)})">{body}</g>'

    # Sideways: rolls head over heels, speed lines trailing behind (left).
    c = Clip(24, True)
    roll = c.g("rotate", [(0, 0, "lin"), (24, 360, "lin")], centred(lift(src["tumble"][1]), spin_fit * 0.92))
    trail = c.g("scale", wiggle(0, 24, (0.12, 0), 6, (1.0, 1.0)), lines(vb[0] + 0.03 * vb[2], vcy, u * spin_fit, 0))
    out.append(("throw_tumble", c, f'{trail}<g transform="translate({num(vcx)} {num(vcy)})">{roll}</g>'))

    # Up: sways and stretches with joy, rushing air on both sides, sparkles.
    c = Clip(30, True)
    body = c.about("scale", wiggle(0, 30, (-0.03, 0.05), 15, (1.0, 1.0)), cx, ground, lift(src["happy"][1]))
    body = c.about("rotate", [(0, 0, "sine"), (7.5, 6, "sine"), (22.5, -6, "sine"), (30, 0, "lin")], cx, ground, body)
    air = lines(x0 - 6 * u, y0 + 0.35 * h, u * 0.8, 90) + lines(x1 + 6 * u, y0 + 0.35 * h, u * 0.8, 90)
    sparks = "".join(c.show(f, f + 12, sparkle(x, y, 11 * u)) for f, x, y in ((2, x0 + 0.05 * w, y0 + 0.15 * h), (12, x1 - 0.02 * w, y0 + 0.05 * h), (17, x1, y0 + 0.5 * h)))
    out.append(("throw_whee", c, f"{air}{body}{sparks}"))

    # Up or down: shakes in panic, sweat drop bobbing by its head.
    c = Clip(24, True)
    shake = [(f, 0 if f in (0, 24) else (6 if f % 6 else -6), "lin") for f in range(0, 25, 3)]
    body = c.about("rotate", shake, cx, cy, lift(src["scared"][1]))
    body = c.g("translate", [(f, (0 if f in (0, 24) else (3 * u if f % 4 else -3 * u), 0), "lin") for f in range(0, 25, 2)], body)
    drop = c.g("translate", [(0, (0, 0), "sine"), (12, (0, 6 * u), "sine"), (24, (0, 0), "lin")], sweat(x1 - 0.12 * w, y0 + 0.2 * h, u))
    air = lines(x0 - 6 * u, y0 + 0.35 * h, u * 0.8, 90) + lines(x1 + 6 * u, y0 + 0.35 * h, u * 0.8, 90)
    out.append(("throw_panic", c, f"{air}{body}{drop}"))

    # Down: upside down, head first, wobbling, rushing air above.
    c = Clip(20, True)
    dive = c.g("rotate", [(0, 180, "sine"), (5, 185, "sine"), (15, 175, "sine"), (20, 180, "lin")], centred(lift(src["scared"][1]), flip_fit))
    air = "".join(lines(vcx + dx * w * flip_fit, vb[1] + 0.04 * vb[3], u * 0.8, 90) for dx in (-0.3, 0, 0.3))
    out.append(("throw_dive", c, f'{air}<g transform="translate({num(vcx)} {num(vcy)})">{dive}</g>'))

    # Splat: lands flat as a pancake, quivers, pops up with a boing, shakes it off.
    c = Clip(90, False)
    squash = [(0, (0.9, 1.12), "in"), (3, (wide, 0.48), "sine")]
    squash += [(3 + k * 3, (wide * (0.98 if k % 2 else 1.0), 0.48 if k % 2 else 0.5), "sine") for k in range(1, 9)]
    squash += [(30, (wide, 0.48), "in"), (34, (wide * 1.03, 0.42), "out"), (40, (0.84, 1.22), "io"), (47, (1.08, 0.93), "io"), (53, (0.97, 1.03), "io"), (58, (1.0, 1.0), "lin")]
    body = c.about("scale", squash, cx, ground, src["sit"][1])
    body = c.g("translate", [(0, (0, -0.15 * h), "in"), (3, (0, 0), "lin"), (34, (0, 0), "out"), (40, (0, -0.12 * h), "in"), (47, (0, 0), "lin")], body)
    body = c.about("rotate", wiggle(60, 82, 9, 5), cx, ground, body)
    dust = puff(c, 3, 22, x0 - 0.02 * w, ground - 8 * u, u * 1.1) + puff(c, 3, 22, x1 + 0.02 * w, ground - 8 * u, u * 1.1)
    out.append(("land_splat", c, f"{body}{dust}"))

    # Dizzy: crash-lands, wobbles in circles under circling stars, shakes its head.
    c = Clip(110, False)
    body = c.about("scale", [(0, (0.92, 1.1), "in"), (4, (1.25, 0.78), "snap"), (10, (0.95, 1.07), "io"), (16, (1.0, 1.0), "lin")], cx, ground, src["sit"][1])
    body = c.g("translate", [(0, (0, -0.12 * h), "in"), (4, (0, 0), "lin")] + [(f, (v[0], 0), e) for f, v, e in wiggle(16, 88, (0.035 * w, 0), 24, (0.0, 0.0))], body)
    body = c.about("rotate", wiggle(14, 86, 7, 24) + [(90, -9, "io"), (94, 9, "io"), (98, -5, "io"), (102, 2, "io"), (106, 0, "lin")], cx, ground, body)
    stars = []
    period, rx, ry, sy = 24, 0.36 * w, 0.06 * h, y0 + 0.02 * h
    for j in range(3):
        frames = [14 + k * period / 12 for k in range(int((88 - 14) / (period / 12)) + 1)] + [88]
        ang = lambda f: 2 * math.pi * ((f - 14) / period + j / 3)
        path = [(f, (hx + rx * math.cos(ang(f)), sy + ry * math.sin(ang(f))), "lin") for f in frames]
        depth = [(f, (0.8 + 0.25 * math.sin(ang(f)),) * 2, "lin") for f in frames]
        stars.append(c.show(14, 88, c.g("translate", path, c.g("scale", depth, star5(0, 0, 21 * u)))))
    dust = puff(c, 4, 22, x0 + 0.05 * w, ground - 6 * u, u) + puff(c, 5, 23, x1 - 0.05 * w, ground - 6 * u, u)
    out.append(("land_dizzy", c, f"{body}{''.join(stars)}{dust}"))

    # Grumpy: a bump on landing, then its annoyed clip, once.
    c = Clip(int(min(150, max(60, round(src["annoyed"][2])))), False)
    body = c.about("scale", [(0, (0.92, 1.1), "in"), (4, (1.18, 0.84), "snap"), (10, (0.97, 1.04), "io"), (15, (1.0, 1.0), "lin")], cx, ground, src["annoyed"][1])
    body = c.g("translate", [(0, (0, -0.1 * h), "in"), (4, (0, 0), "lin")], body)
    out.append(("land_grumpy", c, body + puff(c, 4, 18, cx, ground - 6 * u, u * 0.9)))

    for name, clip, inner in out:
        save(folder / f"{name}.svg", name, attrs, clip, inner)
    return len(out)


def main():
    for pack, cfg in PACKS.items():
        print(f"{pack}: made {build(pack, cfg)} throw clips")


if __name__ == "__main__":
    main()
