"""All 36 clips. Every clip is authored once and exported to Lottie + SMIL from the same keys."""
import math
from anim import Clip, EASE, SOFT, EOUT, EIN, world, apply, place
from poses import (SIT, STAND, stand, DRAPED, HUG, hug_pose, merge, tail, tail_offset, TAIL_UP,
                   TAIL_STRAIGHT_UP)
import rig
from rig import (fx_heart, fx_sparkle, fx_star, fx_z, fx_exclaim, fx_question, fx_drop, fx_puff, fx_crumb,
                 fx_thought, fx_badge, fx_leaf)

LIN = (0.33, 0.33, 0.67, 0.67)
LIN_IN = (0.42, 0.0, 0.67, 0.67)
LIN_OUT = (0.33, 0.33, 0.58, 1.0)

CLIPS = []


def clip(fn):
    CLIPS.append(fn)
    return fn


# ---------------------------------------------------------------- helpers
def addv(a, b, sign=1):
    if isinstance(a, tuple):
        return tuple(x + sign * y for x, y in zip(a, b))
    return a + sign * b


def osc(c, node, prop, f0, f1, base, amp, period, phase=0.0, ease=SOFT, end=None):
    """Eased oscillation around `base` from f0 to f1 (starts at base, ends at `end` or base)."""
    c.k(node, prop, f0, base, ease)
    t = f0 + period / 4 + phase
    sign = 1
    while t < f1 - period / 4 + 0.5:
        c.k(node, prop, t, addv(base, amp, sign), ease)
        t += period / 2
        sign = -sign
    c.k(node, prop, f1, base if end is None else end, ease)


def blink(c, f, after="open", group="eyes"):
    c.v(group, f, "closed")
    c.v(group, f + 4, after)


def breathe(c, f0, f1, cycles=1, amp=0.025, node="torso", base=(1.0, 1.0)):
    span = (f1 - f0) / cycles
    for k in range(cycles):
        a = f0 + k * span
        c.k(node, "s", a, base, SOFT)
        c.k(node, "s", a + span / 2, (base[0] * (1 - amp * 0.4), base[1] * (1 + amp)), SOFT)
    c.k(node, "s", f1, base, SOFT)


def tail_pose(c, f, P, ease=EASE):
    for k in range(4):
        n = f"tail{k}"
        c.k(n, "r", f, P.get(n, {}).get("r", 0.0), ease)


def tail_swish(c, f0, f1, base=None, amps=(3, 5, 7, 10), period=60, lag=5, ease=SOFT):
    base = base or {}
    for k in range(4):
        n = f"tail{k}"
        b = base.get(n, {}).get("r", 0.0)
        osc(c, n, "r", f0, f1, b, amps[k], period, phase=lag * k, ease=ease)


def rise(c, node, f0, f1, d, ease=SOFT, wobble=0):
    c.k(node, "p", f0, (0, 0), ease)
    if wobble:
        mid = (f0 + f1) / 2
        c.k(node, "p", (f0 + mid) / 2, (d[0] * 0.25 + wobble, d[1] * 0.25), ease)
        c.k(node, "p", mid, (d[0] * 0.5, d[1] * 0.5), ease)
        c.k(node, "p", (mid + f1) / 2, (d[0] * 0.75 - wobble, d[1] * 0.75), ease)
    c.k(node, "p", f1, d, ease)


def pop(c, node, f_in, f_out, size=1.0, dur=6):
    c.k(node, "s", f_in, 0)
    c.k(node, "s", f_in + round(dur * 0.6), size * 1.25)
    c.k(node, "s", f_in + dur, size)
    c.k(node, "s", f_out - round(dur * 0.6), size * 1.1)
    c.k(node, "s", f_out, 0)


def orbit(c, node, at, f0, f1, center, rx, ry, turns, a0=0.0, steps_per_turn=12, s_front=1.0, s_back=0.7,
          spin=True, ease_ends=True):
    steps = int(round(turns * steps_per_turn))
    for k in range(steps + 1):
        t = f0 + (f1 - f0) * k / steps
        a = a0 + 2 * math.pi * turns * k / steps
        x = center[0] + rx * math.cos(a) - at[0]
        y = center[1] + ry * math.sin(a) - at[1]
        e = LIN_IN if k == 0 else (LIN_OUT if k == steps - 1 else LIN)
        if not ease_ends:
            e = LIN
        c.k(node, "p", t, (x, y), e)
        depth = (math.sin(a) + 1) / 2  # 1 front, 0 back
        sc = s_back + (s_front - s_back) * depth
        c.k(node, "s", t, sc, e)
        if spin:
            c.k(node, "r", t, 360 * turns * k / steps, e)


def full(P, nodes):
    """Expand pose P to explicitly include rest values for nodes (so transitions return to rest)."""
    out = merge({n: {} for n in nodes}, P)
    return out


def key_pose(c, f, P, nodes=None, ease=EASE):
    """Key every prop present in P; nodes listed in `nodes` but absent get rest values."""
    if nodes:
        for n in nodes:
            P.setdefault(n, {})
    for n, props in P.items():
        if not props:
            c.k(n, "p", f, (0, 0), ease)
            c.k(n, "r", f, 0, ease)
            continue
        for prop, val in props.items():
            c.k(n, prop, f, val, ease)


def rest_of(P):
    """Rest values for all node/props present in P."""
    out = {}
    for n, props in P.items():
        out[n] = {}
        for prop in props:
            out[n][prop] = (0, 0) if prop == "p" else (0 if prop == "r" else 1.0)
    return out


def lerp_pose(A, B, t):
    out = {}
    for n in set(A) | set(B):
        out[n] = {}
        for prop in set(A.get(n, {})) | set(B.get(n, {})):
            dflt = (0, 0) if prop == "p" else (0.0 if prop == "r" else (1.0, 1.0))
            a = A.get(n, {}).get(prop, dflt)
            b = B.get(n, {}).get(prop, dflt)
            if prop == "s":
                a = a if isinstance(a, tuple) else (a, a)
                b = b if isinstance(b, tuple) else (b, b)
            if isinstance(a, tuple):
                out[n][prop] = tuple(x + (y - x) * t for x, y in zip(a, b))
            else:
                out[n][prop] = a + (b - a) * t
    return out


# ================================================================ IDLE
@clip
def idle_breathe():
    c = Clip("idle_breathe", "idle", 120, desc="Default loop: slow breathing, one blink, lazy tail swish.")
    breathe(c, 0, 120, cycles=2, amp=0.028)
    osc(c, "head", "p", 0, 120, (0, 0), (0, -3), 60, phase=-15 + 15)
    blink(c, 72)
    c.k("eyeL", "s", 69, 1); c.k("eyeL", "s", 72, (1, 0.7)); c.k("eyeL", "s", 76, 1)
    c.k("eyeR", "s", 69, 1); c.k("eyeR", "s", 72, (1, 0.7)); c.k("eyeR", "s", 76, 1)
    tail_swish(c, 0, 120, amps=(3, 5, 7, 10), period=120, lag=6)
    for f, r in [(0, 0), (20, 0), (23, -12), (27, 4), (31, 0)]:
        c.k("earR", "r", f, r)
    return c


@clip
def idle_tail_hug():
    c = Clip("idle_tail_hug", "idle", 150, desc="Wraps its tail around its front and nuzzles it, content smile.")
    c.v("tail", 2, "front")
    c.v("tail", 147, "back")
    tail_pose(c, 4, SIT)
    tail_pose(c, 18, tail([-40, -120, -150, -120]))
    tail_pose(c, 30, HUG)
    for f in (40, 58, 76, 94):
        tail_pose(c, f + 9, tail_offset(HUG, [0, 2, 4, 8]))
        tail_pose(c, f + 18, HUG)
    tail_pose(c, 116, HUG)
    tail_pose(c, 134, tail([-40, -120, -150, -120]))
    tail_pose(c, 145, SIT)
    for n in ("armL", "armR"):
        c.k(n, "r", 18, 0); c.k(n, "p", 18, (0, 0))
        c.k(n, "r", 32, HUG[n]["r"]); c.k(n, "p", 32, HUG[n]["p"])
        c.k(n, "r", 116, HUG[n]["r"]); c.k(n, "p", 116, HUG[n]["p"])
        c.k(n, "r", 132, 0); c.k(n, "p", 132, (0, 0))
    c.k("head", "r", 22, 0); c.k("head", "p", 22, (0, 0))
    for f, r, p in [(36, -9, (-4, 6)), (46, -14, (-7, 8)), (56, -8, (-3, 6)), (66, -14, (-7, 8)), (76, -8, (-3, 6)),
                    (86, -14, (-7, 8)), (96, -8, (-3, 6)), (106, -12, (-6, 7)), (118, -9, (-4, 6))]:
        c.k("head", "r", f, r); c.k("head", "p", f, p)
    c.k("head", "r", 134, 0); c.k("head", "p", 134, (0, 0))
    breathe(c, 0, 150, cycles=3, amp=0.02)
    c.vseq("eyes", [(36, "happy"), (124, "open")])
    for n in ("cheekL", "cheekR"):
        c.k(n, "s", 30, 1); c.k(n, "s", 42, 1.3); c.k(n, "s", 114, 1.3); c.k(n, "s", 128, 1)
    return c


@clip
def idle_look_left_right():
    c = Clip("idle_look_left_right", "idle", 120, desc="Eyes glance left, hold, then right; head follows slightly.")
    seq = [(0, 0), (12, -1), (44, -1), (60, 1), (92, 1), (108, 0), (120, 0)]
    for f, d in seq:
        c.k("eyes", "p", f, (10 * d, 1 * abs(d)))
    for f, d in [(0, 0), (16, -1), (46, -1), (64, 1), (94, 1), (112, 0)]:
        c.k("head", "r", f, 4 * d)
        c.k("head", "p", f, (5 * d, 0))
        c.k("earL", "r", f, 5 * d)
        c.k("earR", "r", f, 5 * d)
    blink(c, 51)
    breathe(c, 0, 120, cycles=2, amp=0.015)
    return c


@clip
def idle_yawn():
    c = Clip("idle_yawn", "idle", 110, desc="Big yawn with tiny fangs, eyes squint, ears flatten.")
    c.vseq("mouth", [(14, "yawn"), (70, "smile")])
    c.vseq("eyes", [(16, "squint"), (60, "closed"), (86, "open")])
    for f, s in [(0, 1), (13, 1), (14, 0.35), (28, 1.0), (56, 1.05), (69, 0.45), (70, 0.6), (76, 1)]:
        c.k("mouth", "s", f, s)
    for f, l in [(0, 0), (12, 0), (26, -38), (58, -38), (80, 0)]:
        c.k("earL", "r", f, l); c.k("earR", "r", f, -l)
    for f, p, r in [(0, (0, 0), 0), (14, (0, -5), -3), (30, (0, -11), -4), (56, (0, -9), 2), (70, (0, 3), 3),
                    (88, (0, 0), 0)]:
        c.k("head", "p", f, p); c.k("head", "r", f, r)
    for f, s in [(0, 1), (14, (0.99, 1.02)), (30, (0.96, 1.06)), (56, (0.97, 1.04)), (72, (1.02, 0.97)),
                 (90, 1)]:
        c.k("torso", "s", f, s)
    for f, r in [(0, 0), (14, 0), (30, 22), (56, 20), (76, 0)]:
        c.k("armL", "r", f, r); c.k("armR", "r", f, -r)
    tail_swish(c, 0, 110, amps=(2, 4, 6, 9), period=110, lag=5)
    return c


@clip
def idle_stretch():
    c = Clip("idle_stretch", "idle", 120, desc="Arms up overhead, back arched, tail straight up.")
    up = {"torso": {"p": (0, -8), "s": (0.95, 1.1)}, "head": {"p": (0, -24), "r": 0},
          "armL": {"r": 134, "p": (-14, -10), "s": (1, 1.36)}, "armR": {"r": -134, "p": (14, -10), "s": (1, 1.36)},
          "earL": {"r": 10}, "earR": {"r": -10}}
    up.update(TAIL_STRAIGHT_UP)
    crouch = {"torso": {"p": (0, 0), "s": (1.04, 0.95)}, "head": {"p": (0, 4), "r": 0},
              "armL": {"r": -6, "p": (0, 0), "s": (1, 1)}, "armR": {"r": 6, "p": (0, 0), "s": (1, 1)},
              "earL": {"r": 0}, "earR": {"r": 0}}
    crouch.update(tail([6, -15, -63, -87]))
    rest = rest_of(up)
    key_pose(c, 0, rest)
    key_pose(c, 10, crouch)
    key_pose(c, 32, up)
    trem = merge(up, {"torso": {"s": (0.955, 1.115)}, "armL": {"r": 139}, "armR": {"r": -139}})
    key_pose(c, 44, trem)
    key_pose(c, 56, up)
    key_pose(c, 66, trem)
    key_pose(c, 76, merge(up, {"head": {"p": (0, -20), "r": 0}}))
    key_pose(c, 92, merge(crouch, {"torso": {"s": (1.02, 0.98)}}))
    key_pose(c, 108, rest)
    c.vseq("eyes", [(12, "squint"), (84, "happy"), (100, "open")])
    c.vseq("mouth", [(14, "o"), (80, "smile")])
    for f, s in [(12, 1), (24, 1.15), (76, 1.15), (86, 1)]:
        c.k("mouth", "s", f, s)
    return c


@clip
def idle_groom():
    c = Clip("idle_groom", "idle", 150, desc="Licks a paw and washes its face like a cat, ears flicking.")
    lick = {"armR": {"r": 136, "p": (-8, -18), "s": (1, 1.18)}, "head": {"r": 6, "p": (2, 6)}}
    lick2 = {"armR": {"r": 128, "p": (-6, -10), "s": (1, 1.1)}, "head": {"r": 8, "p": (2, 8)}}
    wash1 = {"armR": {"r": 176, "p": (14, -30), "s": (1, 1.3)}, "head": {"r": 12, "p": (4, 6)}}
    wash2 = {"armR": {"r": 162, "p": (8, -38), "s": (1, 1.3)}, "head": {"r": 8, "p": (2, 4)}}
    rest = rest_of(merge(lick, wash1))
    key_pose(c, 0, rest)
    key_pose(c, 6, rest)
    key_pose(c, 20, lick)
    for i, f in enumerate(range(26, 58, 8)):
        key_pose(c, f, lick2 if i % 2 == 0 else lick)
    key_pose(c, 64, lick)
    seq = [wash1, wash2, wash1, wash2, wash1, wash2]
    for i, f in enumerate(range(74, 122, 9)):
        key_pose(c, f, seq[i])
    key_pose(c, 136, rest)
    c.vseq("mouth", [(18, "tongue"), (60, "smile")])
    c.vseq("eyes", [(18, "closed"), (68, "happy"), (132, "open")])
    for f, r in [(0, 0), (80, 0), (83, 18), (86, -4), (89, 0), (104, 0), (107, 16), (110, -3), (113, 0)]:
        c.k("earR", "r", f, r)
    for f, r in [(0, 0), (40, 0), (43, -12), (46, 3), (49, 0)]:
        c.k("earL", "r", f, r)
    tail_swish(c, 0, 150, amps=(2, 4, 6, 9), period=75, lag=6)
    return c


# ================================================================ SLEEP
def zz(c, f0, life, at, size, d=(34, -86), name="z"):
    n = c.fx(name, fx_z(size), at=at)
    pop(c, n, f0, f0 + life, 1.0, dur=8)
    rise(c, n, f0, f0 + life, d, wobble=8)
    c.k(n, "r", f0, -12, SOFT); c.k(n, "r", f0 + life, 10, SOFT)
    return n


def sit_on_branch(y=-131):
    return {"char": {"p": (0, y)}}


@clip
def sleep_fall_asleep():
    c = Clip("sleep_fall_asleep", "sleep", 170, loop=False, base="sitting",
             desc="Yawns, climbs onto the branch and flops over it into the draped pose.")
    # yawn
    c.vseq("mouth", [(6, "yawn"), (34, "smile")])
    c.vseq("eyes", [(8, "squint"), (32, "closed"), (44, "open"), (52, "happy"), (104, "closed")])
    for f, s in [(0, 1), (5, 1), (6, 0.35), (16, 1.0), (30, 1.0), (33, 0.45), (34, 0.6), (40, 1)]:
        c.k("mouth", "s", f, s)
    for f, l in [(0, 0), (6, 0), (16, -34), (30, -34), (44, 0)]:
        c.k("earL", "r", f, l); c.k("earR", "r", f, -l)
    # branch grows in behind
    c.vseq("branch", [(36, "back"), (74, "front")])
    for f, s in [(0, (0, 1)), (36, (0, 1)), (48, (1.06, 1)), (54, (1, 1))]:
        c.k("branch", "s", f, s)
    # climb: crouch, reach, hop
    D = DRAPED
    for f, P in [
        (0, {"head": {"p": (0, 0), "r": 0}, "torso": {"p": (0, 0), "s": (1, 1), "r": 0}}),
        (16, {"head": {"p": (0, -9), "r": -4}, "torso": {"p": (0, 0), "s": (0.97, 1.05), "r": 0}}),
        (34, {"head": {"p": (0, 2), "r": 2}, "torso": {"p": (0, 0), "s": (1, 1), "r": 0}}),
        (52, {"head": {"p": (0, -4), "r": 0}, "torso": {"p": (0, 0), "s": (1, 1), "r": 0}}),
    ]:
        key_pose(c, f, P)
    for f, s in [(0, 1), (54, 1), (62, (1.1, 0.88)), (67, (0.92, 1.1)), (76, 1), (86, (1.08, 0.92)), (92, 1),
                 (130, 1)]:
        c.k("squash", "s", f, s)
    for f, p in [(0, (0, 0)), (62, (0, 0)), (74, (0, -190)), (86, (0, -131)), (96, (0, -131))]:
        c.k("char", "p", f, p, EOUT if f == 74 else EASE)
    for f, r in [(0, 0), (52, 0), (60, 150), (70, 160), (82, 40), (96, 30)]:
        c.k("armL", "r", f, r); c.k("armR", "r", f, -r)
    for n in ("armL", "armR"):
        c.k(n, "p", 0, (0, 0)); c.k(n, "p", 96, (0, 0))
        c.k(n, "s", 0, 1); c.k(n, "s", 52, 1); c.k(n, "s", 62, (1, 1.2)); c.k(n, "s", 82, 1)
    for f, s in [(0, (1, 1)), (62, (1, 1)), (74, (0.6, 0.7)), (86, (0.9, 1)), (130, D["shadow"]["s"])]:
        c.k("shadow", "s", f, s)
    c.k("shadow", "p", 86, (0, 0)); c.k("shadow", "p", 130, D["shadow"]["p"])
    # flop into the draped pose
    sitb = {"char": {"p": (0, -131)}}
    mid = lerp_pose(merge(rest_of(D), sitb, {"armL": {"r": 30}, "armR": {"r": -30}}), merge(D, {"char": {"p": (0, 0)}}), 0.45)
    mid = merge(mid, {"char": {"p": (0, -96)}, "head": {"r": -20}})
    key_pose(c, 96, merge(rest_of(D), sitb, {"armL": {"r": 30}, "armR": {"r": -30}}))
    key_pose(c, 110, mid)
    key_pose(c, 124, merge(D, {"char": {"p": (0, 0)}, "torso": {"s": (1.05, 0.95)}}))
    key_pose(c, 134, merge(D, {"char": {"p": (0, 0)}, "torso": {"s": (0.98, 1.02)}}))
    key_pose(c, 146, merge(D, {"char": {"p": (0, 0)}, "torso": {"s": (1, 1)}}))
    key_pose(c, 170, merge(D, {"char": {"p": (0, 0)}, "torso": {"s": (1, 1)}}))
    return c


@clip
def sleep_loop():
    c = Clip("sleep_loop", "sleep", 150, base="draped",
             desc="Draped over the branch, slow breathing, tail sway, hind-leg twitch, rising z z z.")
    D = DRAPED
    breathe(c, 0, 150, cycles=2, amp=0.035, node="body")
    osc(c, "head", "r", 0, 150, D["head"]["r"], 1.6, 75, phase=4)
    tail_swish(c, 0, 150, base=D, amps=(3, 5, 7, 10), period=150, lag=8)
    lr = D["legR"]["r"]
    for f, d in [(0, 0), (92, 0), (95, -14), (98, 3), (101, -10), (106, 0)]:
        c.k("legR", "r", f, lr + d)
    for f, d in [(0, 0), (40, 0), (43, 9), (47, -3), (51, 0)]:
        c.k("earR", "r", f, D["earR"]["r"] + d)
    zz(c, 6, 54, (-34, -262), 1.2, name="z1")
    zz(c, 50, 54, (-28, -262), 1.5, name="z2")
    zz(c, 94, 54, (-22, -262), 1.85, name="z3")
    return c


@clip
def sleep_wake_up():
    c = Clip("sleep_wake_up", "sleep", 150, loop=False, base="draped",
             desc="Startled blink, nearly slides off, hugs the branch tight, then climbs down and sits.")
    D = DRAPED
    c.vseq("eyes", [(10, "shock"), (16, "closed"), (19, "shock"), (40, "squint"), (70, "open"), (118, "closed"),
                    (121, "open")])
    c.vseq("mouth", [(10, "o"), (40, "frown"), (72, "smile")])
    c.vseq("brows", [(40, "worried"), (110, "none")])
    for f, d in [(0, 0), (10, 0), (13, 22), (30, 18), (40, -10), (70, -6), (90, 0)]:
        c.k("earL", "r", f, D["earL"]["r"] + d)
        c.k("earR", "r", f, D["earR"]["r"] - d * 0.6)
    # jolt + slide
    for f, p, r in [(0, (0, 0), 0), (10, (0, 0), 0), (13, (0, -12), 0), (18, (0, 0), 0), (24, (-6, 6), -5),
                    (34, (-18, 22), -16), (40, (-4, 4), -2), (44, (0, 0), 0)]:
        c.k("char", "p", f, p, EASE)
        c.k("char", "r", f, r, EASE)
    # arms flail then hug the branch
    aL, aR = D["armL"]["r"], D["armR"]["r"]
    for f, a, b in [(0, 0, 0), (22, 0, 0), (26, 40, -30), (30, -20, 40), (34, 35, -25), (40, -70, 62),
                    (70, -70, 62)]:
        c.k("armL", "r", f, aL + a); c.k("armR", "r", f, aR + b)
    for f, s in [(0, 1), (38, 1), (42, (1.06, 0.93)), (46, (1.04, 0.95)), (70, (1.04, 0.95))]:
        c.k("squash", "s", f, s)
    for f in range(46, 70, 4):
        c.k("squash", "p", f, ((-1.5 if (f // 4) % 2 else 1.5), 0))
    c.k("squash", "p", 0, (0, 0)); c.k("squash", "p", 70, (0, 0))
    # falling leaf
    lf = c.fx("leaf", fx_leaf(1.0), at=(150, -150))
    pop(c, lf, 24, 70, 1.0, dur=4)
    for f, p, r in [(24, (0, 0), 0), (36, (-20, 40), 30), (48, (10, 80), -20), (60, (-14, 118), 25),
                    (70, (0, 140), 0)]:
        c.k(lf, "p", f, p, SOFT); c.k(lf, "r", f, r, SOFT)
    # "?" after the scare
    q = c.fx("question", fx_question(1.8), at=(46, -398), parent="head")
    pop(c, q, 52, 84, 1.0, dur=6)
    osc(c, q, "r", 52, 84, 0, 10, 16)
    # climb down to the ground and sit
    key_pose(c, 70, merge(D, {"armL": {"r": aL - 70}, "armR": {"r": aR + 62}, "char": {"p": (0, 0), "r": 0},
                              "squash": {"s": (1.04, 0.95)}}))
    mid = lerp_pose(D, rest_of(D), 0.55)
    key_pose(c, 86, merge(mid, {"char": {"p": (-10, -40), "r": -6}, "squash": {"s": (0.95, 1.06)},
                                "armL": {"r": 120}, "armR": {"r": -120}}))
    key_pose(c, 100, merge(rest_of(D), {"char": {"p": (0, 0), "r": 0}, "squash": {"s": (1.14, 0.86)},
                                        "armL": {"r": 18}, "armR": {"r": -18}}))
    key_pose(c, 108, merge(rest_of(D), {"char": {"p": (0, 0), "r": 0}, "squash": {"s": (0.97, 1.03)},
                                        "armL": {"r": 0}, "armR": {"r": 0}}))
    key_pose(c, 116, merge(rest_of(D), {"char": {"p": (0, 0), "r": 0}, "squash": {"s": (1, 1)}}))
    # head shake once seated
    for f, r in [(108, 0), (112, -8), (116, 8), (120, -6), (124, 4), (128, 0)]:
        c.k("head", "r", f, r)
    # branch shrinks away
    c.k("branch", "s", 0, 1); c.k("branch", "s", 96, 1); c.k("branch", "s", 112, (0, 1))
    c.v("branch", 113, "none")
    return c


# ================================================================ MOVEMENT
@clip
def move_walk():
    c = Clip("move_walk", "movement", 32, desc="Plodding waddle in place; body rocks, tail bobs. App moves the window.")
    for f, r, y in [(0, 0, 0), (8, 5, -7), (16, 0, 0), (24, -5, -7), (32, 0, 0)]:
        c.k("torso", "r", f, r)
        c.k("char", "p", f, (0, y))
        c.k("head", "r", f, -r * 0.6)
    for f, l, rr in [(0, 0, 0), (8, -15, 7), (16, 0, 0), (24, 7, -15), (32, 0, 0)]:
        c.k("legL", "p", f, (0, l))
        c.k("legR", "p", f, (0, rr))
    for f, a in [(0, 0), (8, 14), (16, 0), (24, -14), (32, 0)]:
        c.k("armL", "r", f, a); c.k("armR", "r", f, a)
    for k, (amp, lag) in enumerate([(5, 0), (6, 2), (7, 4), (9, 6)]):
        n = f"tail{k}"
        c.k(n, "r", 0, 0)
        for j, f in enumerate([8, 16, 24]):
            t = f + lag
            if t < 32:
                c.k(n, "r", t, -amp if j % 2 == 0 else amp * 0.4)
        c.k(n, "r", 32, 0)
    for f, r in [(0, 0), (8, -6), (16, 0), (24, 6), (32, 0)]:
        c.k("earL", "r", f, r); c.k("earR", "r", f, r)
    for f, s in [(0, 1), (8, (0.94, 1)), (16, 1), (24, (0.94, 1)), (32, 1)]:
        c.k("shadow", "s", f, s)
    return c


@clip
def move_hop():
    c = Clip("move_hop", "movement", 45, desc="Crouch, jump with arms up, squash on landing.")
    for f, s in [(0, 1), (9, (1.12, 0.86)), (14, (0.9, 1.12)), (22, (0.98, 1.03)), (32, (0.95, 1.06)),
                 (35, (1.15, 0.85)), (40, (0.98, 1.02)), (45, 1)]:
        c.k("squash", "s", f, s)
    c.k("char", "p", 0, (0, 0)); c.k("char", "p", 10, (0, 0))
    c.k("char", "p", 22, (0, -100), EIN)
    c.k("char", "p", 33, (0, 0))
    for f, r, s in [(0, 0, 1), (9, -16, 1), (16, 140, (1, 1.15)), (26, 125, (1, 1.15)), (34, 30, 1), (40, -4, 1),
                    (45, 0, 1)]:
        c.k("armL", "r", f, r); c.k("armR", "r", f, -r)
        c.k("armL", "s", f, s); c.k("armR", "s", f, s)
    for f, p in [(0, (0, 0)), (12, (0, 0)), (20, (0, 10)), (30, (0, 4)), (34, (0, 0))]:
        c.k("legL", "p", f, p); c.k("legR", "p", f, p)
    for f, r in [(0, 0), (9, 8), (16, 14), (24, -10), (33, 4), (38, 6), (45, 0)]:
        for k in range(4):
            c.k(f"tail{k}", "r", f + k, r * (1 + 0.3 * k) if f + k < 45 else 0)
    for f, s in [(0, 1), (10, (1.05, 1)), (22, (0.55, 0.6)), (33, 1), (36, (1.08, 1)), (45, 1)]:
        c.k("shadow", "s", f, s)
    for f, l in [(0, 0), (9, -8), (16, 14), (26, 10), (35, -14), (42, 0)]:
        c.k("earL", "r", f, l); c.k("earR", "r", f, -l)
    c.vseq("mouth", [(12, "tongue"), (38, "smile")])
    c.vseq("eyes", [(12, "happy"), (36, "open")])
    return c


@clip
def move_climb():
    c = Clip("move_climb", "movement", 40, seam="held",
             desc="Climbs hand over hand in place (tree trunk). App moves the window upward.")
    for f in (0, 40):
        c.k("char", "p", f, (0, -40)); c.k("shadow", "s", f, (0.45, 0.5))
    tl = tail([20, 60, 0, -50])
    up_r, dn_r = 168, 74
    frames = [(0, "L"), (10, "Lp"), (20, "R"), (30, "Rp"), (40, "L")]
    for f, ph in frames:
        if ph == "L":
            aL, aR, lL, lR, ty = up_r, -dn_r, -34, 0, 0
        elif ph == "Lp":
            aL, aR, lL, lR, ty = 120, -120, -16, -16, -14
        elif ph == "R":
            aL, aR, lL, lR, ty = dn_r, -up_r, 0, -34, 0
        else:
            aL, aR, lL, lR, ty = 120, -120, -16, -16, -14
        c.k("armL", "r", f, aL); c.k("armR", "r", f, aR)
        c.k("armL", "s", f, (1, 1.25 if aL > 140 else 1.1)); c.k("armR", "s", f, (1, 1.25 if aR < -140 else 1.1))
        c.k("armL", "p", f, (-4, -10)); c.k("armR", "p", f, (4, -10))
        c.k("legL", "p", f, (-6, lL)); c.k("legR", "p", f, (6, lR))
        c.k("torso", "p", f, (0, ty - 14))
        side = {"L": 1, "Lp": 0, "R": -1, "Rp": 0}[ph]
        c.k("torso", "r", f, -3 * side)
        c.k("head", "r", f, 3 * side)
        c.k("head", "p", f, (0, -6))
    for k in range(4):
        n = f"tail{k}"
        b = tl[n]["r"]
        m = 1 + 0.4 * k
        c.k(n, "r", 0, b + 6 * m); c.k(n, "r", 20 + 2 * k, b - 6 * m); c.k(n, "r", 40, b + 6 * m)
    c.k("eyes", "p", 0, (0, -7)); c.k("eyes", "p", 40, (0, -7))
    c.v("mouth", 0, "smile")
    return c


@clip
def move_fall_land():
    c = Clip("move_fall_land", "movement", 120, loop=False,
             desc="Drops in from above flailing, lands on its bottom, tail flops over its head, dizzy stars.")
    c.k("char", "p", 0, (0, -600))
    c.k("char", "p", 22, (0, 0), EIN)
    for f, s in [(0, (0.2, 0.2)), (22, (1, 1)), (25, (1.15, 1)), (36, (1, 1))]:
        c.k("shadow", "s", f, s)
    for f, s in [(0, (0.94, 1.08)), (21, (0.94, 1.08)), (25, (1.24, 0.76)), (30, (0.94, 1.07)), (35, (1.03, 0.97)),
                 (40, 1)]:
        c.k("squash", "s", f, s)
    flail = [(0, 150, 100), (4, 100, 160), (8, 160, 105), (12, 105, 160), (16, 155, 110), (20, 110, 150),
             (25, 40, 40), (32, 10, 10), (40, 0, 0)]
    for f, a, b in flail:
        c.k("armL", "r", f, a); c.k("armR", "r", f, -b)
    for f, a, b in [(0, -20, -6), (5, -6, -22), (10, -22, -8), (15, -8, -24), (20, -14, -10), (24, 0, 0)]:
        c.k("legL", "p", f, (-6, a)); c.k("legR", "p", f, (6, b))
    c.k("legL", "p", 120, (0, 0)); c.k("legR", "p", 120, (0, 0))
    up = tail([-80, -95, -88, -100])
    flop = tail([-34, -76, -122, -168])
    flop2 = tail([-30, -72, -118, -160])
    wide = tail([-10, -40, -70, -90])
    tail_pose(c, 0, up)
    tail_pose(c, 18, up)
    tail_pose(c, 24, wide)
    tail_pose(c, 26, wide)
    tail_pose(c, 34, flop)
    tail_pose(c, 38, flop2)
    tail_pose(c, 74, flop2)
    tail_pose(c, 84, tail([-20, -50, -80, -96]))
    tail_pose(c, 96, SIT)
    c.vseq("tail", [(25, "top"), (100, "back")])
    c.vseq("eyes", [(0, "shock"), (25, "squint"), (32, "swirl"), (82, "closed"), (86, "open")])
    c.vseq("mouth", [(0, "o"), (25, "frown"), (34, "o"), (88, "smile")])
    for f, r in [(30, 0), (38, -7), (46, 7), (54, -6), (62, 6), (70, -5), (78, 3), (86, -8), (90, 8), (94, -5),
                 (98, 0)]:
        c.k("head", "r", f, r)
    for f, r in [(0, 0), (22, 0), (26, -30), (36, -20), (80, -20), (92, 0)]:
        c.k("earL", "r", f, r); c.k("earR", "r", f, -r)
    # dust puffs
    for i, s in enumerate((-1, 1)):
        n = c.fx(f"dust{i}", fx_puff(1.4), at=(80 * s, -8))
        pop(c, n, 22, 44, 1.0, dur=5)
        c.k(n, "p", 22, (0, 0)); c.k(n, "p", 44, (40 * s, -14), SOFT)
    # dizzy stars orbit the head
    for i in range(3):
        at = (0, -380)
        n = c.fx(f"star{i}", fx_star(1.6), at=at, parent="head")
        orbit(c, n, at, 36, 84, (0, -372), 96, 26, 2, a0=i * 2 * math.pi / 3, steps_per_turn=12, s_front=1.1, s_back=0.75)
        c.k(n, "s", 33, 0); c.k(n, "s", 87, 0)
    return c


# ================================================================ INTERACTION
@clip
def int_dragged():
    c = Clip("int_dragged", "interaction", 60, seam="held",
             desc="Held by the scruff: tail curled around its body, paws tucked, sheepish face.")
    hold = {"lift": {"p": (0, -64)}, "squash": {"s": (0.93, 1.1)}, "torso": {"p": (0, 8)},
            "armL": {"r": -34, "p": (10, -14)}, "armR": {"r": 34, "p": (-10, -14)},
            "legL": {"p": (8, 30), "r": 10}, "legR": {"p": (-8, 30), "r": -10},
            "eyes": {"p": (8, 5)}, "cheekL": {"s": 1.35}, "cheekR": {"s": 1.35},
            "earL": {"r": -24}, "earR": {"r": 24}, "shadow": {"s": (0.55, 0.6)}, "head": {"r": -4}}
    tl = tail([-70, -165, 172, 120])
    for f, sw in [(0, 1), (30, -1), (60, 1)]:
        key_pose(c, f, merge(hold, tl))
        c.k("lift", "r", f, 7 * sw)
        c.k("legL", "r", f, 10 - 6 * sw); c.k("legR", "r", f, -10 - 6 * sw)
        c.k("head", "r", f, -4 - 2 * sw)
        c.k("tail3", "r", f, tl["tail3"]["r"] + 6 * sw)
    c.v("tail", 0, "front")
    c.v("brows", 0, "worried")
    c.v("mouth", 0, "smile")
    return c


@clip
def int_petted():
    c = Clip("int_petted", "interaction", 90, desc="Leans into the hand, happy ^ ^ eyes, tail swishing, hearts.")
    lean = {"head": {"r": 12, "p": (6, -4)}, "torso": {"r": 4}, "earL": {"r": -6}, "earR": {"r": 22},
            "cheekL": {"s": 1.3}, "cheekR": {"s": 1.3}}
    lean2 = merge(lean, {"head": {"r": 6, "p": (4, -2)}, "torso": {"r": 2}})
    key_pose(c, 0, rest_of(lean))
    key_pose(c, 12, lean)
    for i, f in enumerate(range(22, 72, 10)):
        key_pose(c, f, lean2 if i % 2 == 0 else lean)
    key_pose(c, 72, lean)
    key_pose(c, 86, rest_of(lean))
    c.vseq("eyes", [(6, "happy"), (80, "open")])
    tail_swish(c, 0, 90, amps=(6, 9, 12, 15), period=30, lag=3)
    for i, (f, at) in enumerate([(14, (84, -350)), (32, (128, -300)), (50, (40, -380))]):
        n = c.fx(f"heart{i}", fx_heart(1.3 + 0.2 * (i % 2)), at=at)
        pop(c, n, f, f + 28, 1.0, dur=6)
        rise(c, n, f, f + 28, (10, -46), wobble=6)
    return c


@clip
def int_poked():
    c = Clip("int_poked", "interaction", 110,
             desc="Surprise stand (hind legs, arms high, tiny rawr), holds, realises, sits back embarrassed.")
    S = STAND
    shy = {"armL": {"r": -24, "p": (6, -8), "s": (1, 1)}, "armR": {"r": 24, "p": (-6, -8), "s": (1, 1)},
           "head": {"r": -6, "p": (0, 4)}, "torso": {"p": (0, 0), "s": (1, 1)}, "earL": {"r": -16},
           "earR": {"r": 16}, "shadow": {"s": (1, 1)}}
    shy.update(tail([4, -16, -66, -90]))
    rest = rest_of(merge(S, shy))
    key_pose(c, 0, rest)
    key_pose(c, 5, merge(rest, {"torso": {"s": (1.06, 0.94)}}))
    key_pose(c, 13, S, ease=EOUT)
    t1 = merge(S, {"torso": {"p": (1.5, -56)}, "armL": {"r": 120}, "armR": {"r": -112}})
    t2 = merge(S, {"torso": {"p": (-1.5, -57)}, "armL": {"r": 112}, "armR": {"r": -120}})
    for i, f in enumerate(range(18, 46, 5)):
        key_pose(c, f, t1 if i % 2 == 0 else t2)
    key_pose(c, 48, S)
    key_pose(c, 66, shy)
    key_pose(c, 92, shy)
    key_pose(c, 106, rest)
    c.vseq("eyes", [(5, "shock"), (48, "closed"), (51, "open"), (100, "open")])
    c.vseq("mouth", [(6, "rawr"), (52, "o"), (70, "smile")])
    c.vseq("brows", [(52, "worried"), (100, "none")])
    for f, p in [(0, (0, 0)), (54, (0, 0)), (64, (-9, 5)), (94, (-9, 5)), (104, (0, 0))]:
        c.k("eyes", "p", f, p)
    for n in ("cheekL", "cheekR"):
        for f, s in [(0, 1), (54, 1), (62, 1.45), (94, 1.45), (104, 1)]:
            c.k(n, "s", f, s)
    sd = c.fx("sweat", fx_drop(1.7, rot=-20), at=(124, -310), parent="head")
    pop(c, sd, 58, 94, 1.0, dur=6)
    c.k(sd, "p", 58, (0, 0)); c.k(sd, "p", 94, (4, 18), SOFT)
    return c


@clip
def int_tickled():
    c = Clip("int_tickled", "interaction", 120, desc="Rolls onto its back, legs kicking, laughing, eyes squeezed shut.")
    lie = {"char": {"r": -76, "p": (-14, 50)}, "head": {"r": 24, "p": (0, 0)},
           "legL": {"r": 20, "p": (26, -8)}, "legR": {"r": -10, "p": (44, 10)},
           "armL": {"r": 50}, "armR": {"r": -30}, "shadow": {"s": (1.15, 1), "p": (-50, 0)}}
    lie.update(tail([10, -30, -70, -110], torso_rot=-76))
    rest = rest_of(lie)
    key_pose(c, 0, rest)
    key_pose(c, 8, merge(rest, {"squash": {"s": (1.05, 0.95)}, "head": {"r": -6}}))
    c.k("squash", "s", 0, 1); c.k("squash", "s", 20, 1); c.k("squash", "s", 100, 1); c.k("squash", "s", 108, (1.06, 0.94))
    c.k("squash", "s", 114, 1)
    key_pose(c, 22, lie)
    for i, f in enumerate(range(26, 94, 6)):
        s = 1 if i % 2 == 0 else -1
        c.k("legL", "p", f, addv(lie["legL"]["p"], (14 * s, -6 * s)))
        c.k("legR", "p", f, addv(lie["legR"]["p"], (-14 * s, 6 * s)))
        c.k("legL", "r", f, lie["legL"]["r"] + 12 * s)
        c.k("legR", "r", f, lie["legR"]["r"] - 12 * s)
        c.k("armL", "r", f, lie["armL"]["r"] - 18 * s)
        c.k("armR", "r", f, lie["armR"]["r"] + 18 * s)
        c.k("char", "r", f, lie["char"]["r"] + 4 * s)
        c.k("head", "r", f, lie["head"]["r"] + 5 * s)
        for k in range(4):
            c.k(f"tail{k}", "r", f, lie[f"tail{k}"]["r"] + (6 + 3 * k) * s)
    key_pose(c, 96, lie)
    key_pose(c, 110, rest)
    c.vseq("eyes", [(4, "squint"), (106, "happy"), (114, "open")])
    c.vseq("mouth", [(4, "tongue"), (112, "smile")])
    for n in ("cheekL", "cheekR"):
        for f, s in [(0, 1), (10, 1.35), (100, 1.35), (112, 1)]:
            c.k(n, "s", f, s)
    return c


LOOK_DIRS = {
    "up": (0, -1), "up_right": (1, -1), "right": (1, 0), "down_right": (1, 1),
    "down": (0, 1), "down_left": (-1, 1), "left": (-1, 0), "up_left": (-1, -1),
}


def make_look(name, d):
    def fn():
        dx, dy = d
        k = 0.78 if dx and dy else 1.0
        c = Clip(f"int_look_{name}", "interaction", 60, seam="held",
                 desc=f"Eyes and head held looking {name.replace('_', '-')}, light breathing (cursor follow).")
        hold = {"eyes": {"p": (11 * dx * k, 9 * dy * k)}, "head": {"p": (6 * dx * k, 6 * dy * k), "r": 5 * dx * k},
                "earL": {"r": 4 * dx - 3 * dy}, "earR": {"r": 4 * dx + 3 * dy}}
        key_pose(c, 0, hold)
        key_pose(c, 60, hold)
        breathe(c, 0, 60, cycles=1, amp=0.015)
        return c
    fn.__name__ = f"int_look_{name}"
    return fn


for _n, _d in LOOK_DIRS.items():
    clip(make_look(_n, _d))


# ================================================================ MOODS
@clip
def mood_happy():
    c = Clip("mood_happy", "moods", 80, desc="Bouncy hop with a little spin, happy ^ ^ eyes, sparkles.")
    for f, s in [(0, 1), (8, (1.1, 0.88)), (12, (0.92, 1.1)), (20, 1), (29, (0.95, 1.05)), (32, (1.12, 0.88)),
                 (37, 1), (42, (0.97, 1.03)), (46, (1.06, 0.94)), (52, 1)]:
        c.k("squash", "s", f, s)
    for f, p, e in [(0, (0, 0), EASE), (9, (0, 0), EASE), (20, (0, -84), EOUT), (31, (0, 0), EIN),
                    (39, (0, -18), EOUT), (46, (0, 0), EIN)]:
        c.k("char", "p", f, p, e)
    for f, sx in [(0, 1), (11, 1), (18, -1), (26, 1)]:
        c.k("char", "s", f, (sx, 1), SOFT)
    for f, r in [(0, 0), (8, -12), (16, 140), (26, 130), (33, 30), (40, 60), (48, 0)]:
        c.k("armL", "r", f, r); c.k("armR", "r", f, -r)
    for f, s in [(0, 1), (10, (1.05, 1)), (20, (0.55, 0.6)), (31, 1), (39, (0.9, 0.9)), (46, 1)]:
        c.k("shadow", "s", f, s)
    osc(c, "head", "r", 50, 72, 0, 6, 11)
    tail_swish(c, 44, 76, amps=(6, 9, 12, 15), period=12, lag=2)
    c.vseq("eyes", [(2, "happy"), (72, "open")])
    c.vseq("mouth", [(2, "tongue"), (72, "smile")])
    for i, (f, at, sz) in enumerate([(14, (-160, -320), 1.2), (20, (160, -300), 1.0), (30, (-130, -150), 0.9),
                                     (40, (150, -140), 1.1), (48, (-60, -420), 0.9)]):
        n = c.fx(f"spark{i}", fx_sparkle(sz * 1.45), at=at)
        pop(c, n, f, f + 20, 1.0, dur=6)
        c.k(n, "r", f, 0); c.k(n, "r", f + 20, 90)
    return c


@clip
def mood_sad():
    c = Clip("mood_sad", "moods", 120, desc="Ears flat, hugs its tail, sad brows, a teardrop.")
    c.v("tail", 2, "front"); c.v("tail", 117, "back")
    sad = merge(hug_pose(head_tilt=-6), {"head": {"p": (-2, 12)}, "earL": {"r": -42}, "earR": {"r": 42},
                                         "eyes": {"p": (0, 5)}, "torso": {"s": (1.02, 0.97)}})
    rest = rest_of(sad)
    key_pose(c, 0, rest)
    key_pose(c, 4, rest)
    key_pose(c, 18, merge(lerp_pose(rest, sad, 0.5), tail([-40, -120, -150, -120])))
    key_pose(c, 30, sad)
    key_pose(c, 78, sad)
    key_pose(c, 82, merge(sad, {"torso": {"s": (1.04, 0.95)}, "head": {"p": (-2, 14)}}))
    key_pose(c, 86, sad)
    key_pose(c, 90, merge(sad, {"torso": {"s": (1.04, 0.95)}, "head": {"p": (-2, 14)}}))
    key_pose(c, 96, sad)
    key_pose(c, 104, merge(lerp_pose(rest, sad, 0.5), tail([-40, -120, -150, -120])))
    key_pose(c, 114, rest)
    c.vseq("brows", [(10, "worried"), (106, "none")])
    c.vseq("mouth", [(10, "frown"), (106, "smile")])
    t = c.fx("tear", fx_drop(1.35), at=(-70, -234), parent="head", z="armL")
    pop(c, t, 34, 74, 1.0, dur=6)
    for f, p in [(34, (0, 0)), (58, (-6, 32)), (68, (-8, 60)), (74, (-8, 72))]:
        c.k(t, "p", f, p, SOFT if f < 60 else EIN)
    return c


@clip
def mood_surprised():
    c = Clip("mood_surprised", "moods", 90, desc='Surprise stand with big round eyes, "o" mouth and a "!" mark.')
    S = STAND
    rest = rest_of(S)
    key_pose(c, 0, rest)
    key_pose(c, 4, merge(rest, {"torso": {"s": (1.06, 0.94)}}))
    key_pose(c, 12, S, ease=EOUT)
    key_pose(c, 18, merge(S, {"torso": {"s": (0.96, 1.1)}}))
    key_pose(c, 24, S)
    key_pose(c, 56, S)
    key_pose(c, 74, rest)
    c.vseq("eyes", [(4, "shock"), (44, "closed"), (47, "shock"), (68, "open")])
    c.vseq("mouth", [(4, "o"), (68, "smile")])
    for f, s in [(0, 1), (4, 1), (14, 1.3), (56, 1.3), (68, 1)]:
        c.k("mouth", "s", f, s)
    ex = c.fx("exclaim", fx_exclaim(2.0), at=(0, -410), parent="head")
    pop(c, ex, 8, 60, 1.0, dur=7)
    osc(c, ex, "r", 8, 60, 0, 8, 10)
    return c


@clip
def mood_hungry():
    c = Clip("mood_hungry", "moods", 120, desc="Rubs its belly; thought bubble with a bamboo stalk.")
    rub1 = {"armL": {"r": -34, "p": (10, -2)}, "armR": {"r": 26, "p": (-4, 4)}}
    rub2 = {"armL": {"r": -26, "p": (6, 4)}, "armR": {"r": 34, "p": (-10, -2)}}
    rest = rest_of(rub1)
    key_pose(c, 0, rest)
    key_pose(c, 14, rub1)
    for i, f in enumerate(range(24, 96, 10)):
        key_pose(c, f, rub2 if i % 2 == 0 else rub1)
    key_pose(c, 108, rest)
    for f, p, r in [(0, (0, 0), 0), (14, (9, -8), 0), (96, (9, -8), 0), (108, (0, 0), 0)]:
        c.k("eyes", "p", f, p)
    for f, r in [(0, 0), (16, 6), (96, 6), (108, 0)]:
        c.k("head", "r", f, r)
    c.vseq("brows", [(12, "worried"), (104, "none")])
    c.vseq("mouth", [(16, "o"), (44, "tongue"), (54, "o"), (98, "smile")])
    for f, s in [(0, 1), (66, 1), (68, (1.03, 0.97)), (70, (0.98, 1.02)), (72, (1.03, 0.97)), (74, (0.99, 1.01)),
                 (76, 1)]:
        c.k("body", "s", f, s)
    b = c.fx("bubble", fx_thought(), at=(150, -404))
    pop(c, b, 16, 98, 1.25, dur=8)
    osc(c, b, "p", 16, 98, (0, 0), (0, -5), 30)
    tail_swish(c, 0, 120, amps=(2, 4, 6, 8), period=60, lag=5)
    return c


@clip
def mood_love():
    c = Clip("mood_love", "moods", 120, desc="Heart eyes, hugs its tail like a pillow, floating hearts.")
    c.v("tail", 2, "front"); c.v("tail", 117, "back")
    H = merge(hug_pose(head_tilt=-10), {"cheekL": {"s": 1.4}, "cheekR": {"s": 1.4}})
    rest = rest_of(merge(H, {"torso": {"r": 0}}))
    key_pose(c, 0, rest)
    key_pose(c, 4, rest)
    key_pose(c, 16, merge(lerp_pose(rest, H, 0.5), tail([-40, -120, -150, -120])))
    key_pose(c, 28, merge(H, {"torso": {"r": 0}}))
    for i, f in enumerate(range(40, 100, 15)):
        s = 1 if i % 2 == 0 else -1
        key_pose(c, f, merge(H, {"torso": {"r": 4 * s}, "head": {"r": -10 + 4 * s}}))
    key_pose(c, 100, merge(H, {"torso": {"r": 0}}))
    key_pose(c, 106, merge(lerp_pose(rest, H, 0.5), tail([-40, -120, -150, -120])))
    key_pose(c, 114, rest)
    c.vseq("eyes", [(8, "heart"), (106, "open")])
    for i, (f, at) in enumerate([(16, (-128, -260)), (32, (130, -300)), (48, (-80, -390)), (64, (96, -410)),
                                 (78, (-140, -330))]):
        n = c.fx(f"heart{i}", fx_heart(1.2 + 0.25 * (i % 2)), at=at)
        pop(c, n, f, f + 30, 1.0, dur=6)
        rise(c, n, f, f + 30, (0, -50), wobble=8)
    return c


@clip
def mood_angry():
    c = Clip("mood_angry", "moods", 100, desc="Rears up and stomps both front paws, angry brows, tiny rawr, steam.")
    up = stand(h=50, arms=140, head_up=20)
    down = {"torso": {"p": (0, 0), "s": (1.04, 0.95)}, "head": {"p": (0, 6)},
            "armL": {"r": -14, "p": (4, 8), "s": (1, 1)}, "armR": {"r": 14, "p": (-4, 8), "s": (1, 1)},
            "earL": {"r": -20}, "earR": {"r": 20}, "shadow": {"s": (1.05, 1)}}
    down.update(tail([0, -24, -72, -96]))
    rest = rest_of(merge(up, down))
    key_pose(c, 0, rest)
    for f0 in (0, 20, 40):
        key_pose(c, f0 + 10, up, ease=EOUT)
        key_pose(c, f0 + 18, down, ease=EIN)
    key_pose(c, 66, merge(down, {"torso": {"s": (1.06, 0.95)}}))
    key_pose(c, 74, merge(down, {"torso": {"s": (1.02, 0.98)}}))
    key_pose(c, 92, rest)
    for f in (18, 38, 58):
        c.k("char", "p", f - 1, (0, 0)); c.k("char", "p", f + 1, (-3, 0)); c.k("char", "p", f + 3, (3, 0))
        c.k("char", "p", f + 5, (0, 0))
    c.k("char", "p", 0, (0, 0))
    c.vseq("brows", [(2, "angry"), (90, "none")])
    c.vseq("mouth", [(2, "rawr"), (90, "smile")])
    for i, (f, s) in enumerate([(18, -1), (38, 1), (58, -1), (66, 1)]):
        n = c.fx(f"steam{i}", fx_puff(1.5), at=(96 * s, -360), parent="head")
        pop(c, n, f, f + 18, 1.0, dur=5)
        rise(c, n, f, f + 18, (20 * s, -34))
    return c


@clip
def mood_smile_wink():
    c = Clip("mood_smile_wink", "moods", 75, desc="Big open smile with tongue, playful wink with a sparkle, tail wag.")
    for f, r, p in [(0, 0, (0, 0)), (10, 8, (4, -2)), (50, 8, (4, -2)), (64, 0, (0, 0))]:
        c.k("head", "r", f, r); c.k("head", "p", f, p)
    c.vseq("mouth", [(4, "tongue"), (62, "smile")])
    c.vseq("eyes", [(10, "wink"), (44, "open")])
    for f, s in [(0, 1), (8, 1), (11, (1, 0.6)), (14, 1)]:
        c.k("eyeR", "s", f, s)
    sp = c.fx("sparkle", fx_sparkle(1.7), at=(118, -300), parent="head")
    pop(c, sp, 12, 38, 1.0, dur=6)
    c.k(sp, "r", 12, 0); c.k(sp, "r", 38, 90)
    sp2 = c.fx("sparkle2", fx_sparkle(1.0), at=(150, -258), parent="head")
    pop(c, sp2, 16, 36, 1.0, dur=5)
    tail_swish(c, 6, 62, amps=(8, 10, 12, 14), period=12, lag=1.5)
    for n in ("cheekL", "cheekR"):
        for f, s in [(0, 1), (10, 1.3), (54, 1.3), (64, 1)]:
            c.k(n, "s", f, s)
    return c


# ================================================================ FUN
@clip
def fun_spin():
    c = Clip("fun_spin", "fun", 130, desc="Chases its own tail around in a full circle, then sits down dizzy.")
    notice = {"eyes": {"p": (10, 7)}, "head": {"r": 10, "p": (6, 2)}}
    for f, P in [(0, rest_of(notice)), (12, notice), (16, notice), (56, notice), (62, rest_of(notice))]:
        key_pose(c, f, P)
    tail_pose(c, 0, SIT)
    tail_pose(c, 12, tail([-10, -30, -80, -130]))
    tail_pose(c, 18, tail([-10, -30, -80, -130]))
    tail_pose(c, 60, tail([-10, -30, -80, -130]))
    tail_pose(c, 70, SIT)
    for f, sx in [(0, 1), (18, 1), (32, -1), (46, 1)]:
        c.k("char", "s", f, (sx, 1), SOFT)
    for f, y in [(0, 0), (18, 0), (23, -16), (28, 0), (33, -16), (38, 0), (43, -16), (48, 0)]:
        c.k("char", "p", f, (0, y))
    for f, r in [(0, 0), (18, 0), (22, 60), (40, 60), (48, 0)]:
        c.k("armL", "r", f, r); c.k("armR", "r", f, -r)
    for f, s in [(0, 1), (46, 1), (52, (1.12, 0.88)), (58, 1)]:
        c.k("squash", "s", f, s)
    for f, r in [(0, 0), (58, 0), (64, 3), (72, -3), (80, 3), (88, -3), (96, 2), (102, 0)]:
        c.k("char", "r", f, r)
    for f, r in [(62, 0), (68, -6), (76, 6), (84, -6), (92, 5), (100, -2), (104, -9), (108, 9), (112, -7),
                 (116, 4), (120, 0)]:
        c.k("head", "r", f, r)
    c.vseq("eyes", [(18, "squint"), (50, "swirl"), (106, "closed"), (110, "open")])
    c.vseq("mouth", [(18, "tongue"), (50, "o"), (112, "smile")])
    for i in range(2):
        at = (0, -380)
        n = c.fx(f"star{i}", fx_star(1.5), at=at, parent="head")
        orbit(c, n, at, 58, 102, (0, -372), 90, 24, 2, a0=i * math.pi, steps_per_turn=11, s_front=1.05,
              s_back=0.7)
        c.k(n, "s", 56, 0); c.k(n, "s", 104, 0)
    return c


def _peek_x(r, target_x, point=(104 + 44, -336)):
    """char p.x so that rest `point` (head-space) lands at target_x with char rotated r."""
    pose = {"char": {"r": r, "p": (0, -60)}}
    m = world(pose, "head")
    x = apply(m, point)[0]
    return target_x - x


@clip
def fun_peek():
    c = Clip("fun_peek", "fun", 110, seam="held",
             desc="Peeks in from the left edge: ears first, then eyes, blinks, pulls back. Hidden at the loop seam.")
    r = 36
    edge = -320
    hidden = _peek_x(r, edge - 30, (150, -320))
    ears = _peek_x(r, edge + 56, (150, -330))
    eyes = _peek_x(r, edge + 200, (150, -330))
    for f, x, e in [(0, hidden, EASE), (8, hidden, EASE), (22, ears, EOUT), (34, ears, EASE), (48, eyes, EOUT),
                    (80, eyes, EASE), (94, hidden, EIN), (110, hidden, EASE)]:
        c.k("char", "p", f, (x, -60), e)
    c.k("char", "r", 0, r); c.k("char", "r", 110, r)
    tp = tail([150, 175, 195, 210], torso_rot=r)
    tail_pose(c, 0, tp); tail_pose(c, 110, tp)
    for n in ("armL", "armR"):
        c.k(n, "r", 0, 0); c.k(n, "r", 110, 0)
    c.k("shadow", "s", 0, 0); c.k("shadow", "s", 110, 0)
    for f, rr in [(0, 0), (24, 0), (27, -16), (30, 6), (33, 0), (62, 0), (65, -12), (68, 4), (71, 0)]:
        c.k("earR", "r", f, rr)
    for f, p in [(0, (0, 0)), (54, (0, 0)), (60, (8, -4)), (70, (8, -4)), (76, (2, 2)), (110, (0, 0))]:
        c.k("eyes", "p", f, p)
    c.vseq("eyes", [(52, "closed"), (55, "open")])
    return c


@clip
def fun_notify():
    c = Clip("fun_notify", "fun", 90, desc='Waves a bamboo leaf like a flag under a round yellow "!" badge.')
    c.vseq("flag", [(2, "held"), (86, "none")])
    for f, s in [(0, 1), (1, 0), (2, 0), (8, 1.15), (11, 1), (80, 1), (85, 0), (86, 0)]:
        c.k("flag", "s", f, s)
    c.k("armR", "r", 0, 0); c.k("armR", "s", 0, 1); c.k("armR", "p", 0, (0, 0))
    for i, f in enumerate(range(10, 78, 7)):
        c.k("armR", "r", f, -126 if i % 2 == 0 else -100)
        c.k("armR", "s", f, (1, 1.25)); c.k("armR", "p", f, (16, -8))
        c.k("flag", "r", f + 2, 16 if i % 2 == 0 else -18)
    c.k("flag", "r", 0, 0); c.k("flag", "r", 84, 0)
    c.k("armR", "r", 84, 0); c.k("armR", "s", 84, 1); c.k("armR", "p", 84, (0, 0))
    osc(c, "head", "r", 6, 80, 0, 5, 14)
    c.k("armL", "r", 0, 0); c.k("armL", "r", 14, -12); c.k("armL", "r", 76, -12); c.k("armL", "r", 86, 0)
    c.vseq("eyes", [(6, "happy"), (80, "open")])
    c.vseq("mouth", [(6, "tongue"), (80, "smile")])
    b = c.fx("badge", fx_badge(), at=(0, -414), parent="head")
    pop(c, b, 4, 84, 1.0, dur=8)
    osc(c, b, "p", 4, 84, (0, 0), (0, -5), 20)
    osc(c, b, "r", 12, 76, 0, 6, 20)
    tail_swish(c, 0, 90, amps=(4, 6, 8, 10), period=30, lag=3)
    return c


@clip
def fun_bamboo_munch():
    c = Clip("fun_bamboo_munch", "fun", 120, desc="Holds a bamboo stalk in both paws and crunches it; cheeks puff, crumbs fall.")
    c.vseq("bamboo", [(1, "held"), (114, "none")])
    hold = {"armL": {"r": -30, "p": (12, -14)}, "armR": {"r": 30, "p": (-12, -14)},
            "bamboo": {"p": (14, 40), "r": 14, "s": 1}}
    bite = merge(hold, {"bamboo": {"p": (10, 28), "r": 10}, "armL": {"p": (12, -24)}, "armR": {"p": (-12, -24)},
                        "head": {"p": (0, 4), "r": 0}})
    chew = merge(hold, {"head": {"p": (0, 0), "r": 0}})
    rest = rest_of(merge(hold, {"head": {"p": (0, 0), "r": 0}}))
    key_pose(c, 0, rest)
    key_pose(c, 10, merge(hold, {"head": {"p": (0, 0), "r": 0}}))
    times = list(range(18, 98, 10))
    for i, f in enumerate(times):
        key_pose(c, f, bite)
        key_pose(c, f + 5, merge(chew, {"head": {"r": 3 if i % 2 else -3}}))
    key_pose(c, 102, merge(hold, {"head": {"p": (0, 0), "r": 0}}))
    key_pose(c, 113, rest)
    c.k("bamboo", "s", 1, 0); c.k("bamboo", "s", 6, 1.15); c.k("bamboo", "s", 10, 1)
    c.k("bamboo", "s", 102, 1); c.k("bamboo", "s", 106, 1.1); c.k("bamboo", "s", 113, 0)
    mseq = []
    for f in times:
        mseq += [(f - 2, "o"), (f + 2, "smile")]
    c.vseq("mouth", mseq)
    for n in ("cheekL", "cheekR"):
        c.k(n, "s", 0, 1); c.k(n, "s", 14, 1)
        for f in times:
            c.k(n, "s", f + 1, 1.0); c.k(n, "s", f + 6, 1.4)
        c.k(n, "s", 104, 1)
    c.vseq("eyes", [(12, "happy"), (104, "open")])
    for i, (f, dx) in enumerate([(20, -30), (32, 24), (44, -14), (56, 36), (68, -36), (80, 10), (90, -22)]):
        n = c.fx(f"crumb{i}", fx_crumb(1.9 + 0.4 * (i % 3), rig.BAMBOO if i % 2 else rig.BAMBOO_D), at=(12, -182))
        c.k(n, "s", f, 0); c.k(n, "s", f + 3, 1); c.k(n, "s", f + 17, 1); c.k(n, "s", f + 20, 0)
        c.k(n, "p", f, (0, 0)); c.k(n, "p", f + 4, (dx * 0.3, -6), EOUT); c.k(n, "p", f + 18, (dx, 176), EIN)
        c.k(n, "p", f + 20, (dx, 176))
        c.k(n, "r", f, 0); c.k(n, "r", f + 18, 200 * (1 if dx > 0 else -1))
    return c


def build_all():
    return [fn() for fn in CLIPS]
