"""Choreography for every clip."""
from engine import Track, wave, steps, S, EASE, Layer, Group, Shape
from rig import *

BX, BY = BASE
OPEN = [100, 100]


def loc(x, y, cx=BX, cy=BY):
    return [cx + x * 0.8, cy + y * 0.8]


def blink(at, closed=8):
    return [(at, OPEN), (at + 2.5, [100, closed]), (at + 5, OPEN)]


def osc(t0, t1, n, a, b, rest):
    """n alternations a/b between t0 and t1, resting at both ends"""
    out = [(t0, rest)]
    step = (t1 - t0) / (n + 1)
    for k in range(n):
        out.append((t0 + step * (k + 1), a if k % 2 == 0 else b))
    out.append((t1, rest))
    return out


def base_arms(c, side, kfs_p, kfs_r):
    c.k('arm%s.p' % side, kfs_p)
    c.k('arm%s.r' % side, kfs_r)


ARM_L, ARM_R = [-170, 24], [170, 24]


# ------------------------------------------------------------- effect helpers
def pop(c, shapes, t0, t1, p0, p1=None, size=100, r0=0, r1=0, fade=False, ein=5, under=False):
    p1 = p1 or p0
    if fade:
        s = [(t0, [0, 0]), (t0 + ein, [size * 1.12] * 2), (t0 + ein + 4, [size] * 2)]
        o = [(t0, 100), (max(t0 + ein + 5, t1 - 12), 100), (t1, 0)]
    else:
        s = [(0, [0, 0]), (t0, [0, 0]), (t0 + ein, [size * 1.15] * 2), (t0 + ein + 4, [size] * 2),
             (t1 - ein, [size] * 2), (t1, [0, 0])]
        o = 100
    L = fx('fx', shapes, Track([(t0, p0), (t1, p1)]), s=Track(s), r=Track([(t0, r0), (t1, r1)]),
           o=Track(o) if fade else o)
    (c.under if under else c.effects).append(L)
    return L


def sparkle(c, t0, x, y, size=10, color=YELLOW, dur=22, spin=90):
    return pop(c, fx_sparkle(size, color), t0, t0 + dur, [x, y], [x, y - 4], r0=0, r1=spin, ein=6)


def rise(c, shapes, t0, t1, p0, dx, dy, size=100, r0=0, r1=0):
    return pop(c, shapes, t0, t1, p0, [p0[0] + dx, p0[1] - dy], size=size, r0=r0, r1=r1, fade=True, ein=7)


def orbit_stars(c, t0, t1, cx, cy, rx=46, ry=12, n=3, color=YELLOW):
    """small stars circling (dizzy) — each star moves on an ellipse via kfs every quarter turn"""
    import math
    turns = (t1 - t0) / 30.0
    for k in range(n):
        ph = k / n
        kfs = []
        steps_n = int(turns * 8) + 1
        for j in range(steps_n + 1):
            tt = t0 + (t1 - t0) * j / steps_n
            a = 2 * math.pi * (ph + turns * j / steps_n)
            kfs.append((tt, [cx + rx * math.cos(a), cy + ry * math.sin(a)], (0.33, 0.33, 0.67, 0.67)))
        s = [(0, [0, 0]), (t0, [0, 0]), (t0 + 6, [100, 100]), (t1 - 6, [100, 100]), (t1, [0, 0])]
        c.effects.append(fx('dizzy', fx_star(8, [YELLOW, PEACH, PINK][k % 3]), Track(kfs), s=Track(s),
                            r=Track([(t0, 0), (t1, 360)])))


CLIPS = []


def clip(name, cat, N, loop=True, desc=''):
    c = Clip(name, cat, N, loop, desc)
    CLIPS.append(c)
    return c


# =================================================================== IDLE
def idle_breathe():
    c = clip('idle_breathe', 'idle', 90, desc='Default loop: slow float bob, rippling tail, drifting arms, one blink.')
    c.k('squash.s', wave(90, 1, [100, 100], [101.5, 103]))
    c.k('eyes.s', blink(52))
    c.k('bow.r', wave(90, 1, 28, 33))


def idle_look_left_right():
    N = 120
    c = clip('idle_look_left_right', 'idle', N, desc='Eyes glance left, hold, then right; body leans with them.')
    L, R = [-15, 2], [15, 2]
    c.k('gaze.p', [(0, [0, 0]), (12, L), (44, L), (60, R), (94, R), (108, [0, 0])])
    c.k('face.p', [(0, [0, 0]), (12, [-8, 0]), (44, [-8, 0]), (60, [8, 0]), (94, [8, 0]), (108, [0, 0])])
    c.k('move.r', [(0, 0), (14, -3.5), (44, -3.5), (62, 3.5), (94, 3.5), (110, 0)])
    c.k('eyes.s', blink(50))
    c.k('bow.r', [(0, 28), (16, 24), (44, 24), (64, 33), (94, 33), (112, 28)])


def idle_yawn():
    N = 105
    c = clip('idle_yawn', 'idle', N, desc='Big yawn: stretches tall, then squishes back.')
    c.anchor = (0, 120)
    c.k('squash.s', [(0, OPEN), (14, [104, 96]), (34, [92, 113]), (60, [93, 112]), (72, [108, 92]), (84, [98, 102]), (96, OPEN)])
    c.st('mouth.v', [(0, 'smile'), (16, 'yawn'), (72, 'smile')])
    c.k('mouth.s', [(0, OPEN), (16, [55, 35]), (34, [100, 100]), (60, [104, 104]), (71, [55, 30]), (72, OPEN)])
    c.st('eyes.v', [(0, 'open'), (20, 'sleepy'), (70, 'open')])
    c.k('eyes.s', [(0, OPEN), (69, OPEN), (71, [100, 60]), (75, OPEN)] + blink(84))
    c.k('armL.p', [(0, ARM_L), (32, [-182, -6]), (60, [-182, -8]), (78, ARM_L)])
    c.k('armL.r', [(0, 16), (32, 40), (60, 40), (78, 16)])
    c.k('armR.p', [(0, ARM_R), (32, [182, -6]), (60, [182, -8]), (78, ARM_R)])
    c.k('armR.r', [(0, -16), (32, -40), (60, -40), (78, -16)])
    c.k('cheeks.s', [(0, OPEN), (34, [80, 80]), (60, [80, 80]), (74, OPEN)])
    sparkle(c, 58, *loc(-96, -84), size=6, color=SKY, dur=20)


def idle_stretch():
    N = 105
    c = clip('idle_stretch', 'idle', N, desc='Nub arms up overhead, body stretches taller, tail wisps fan out.')
    c.anchor = (0, 120)
    c.k('squash.s', [(0, OPEN), (12, [104, 96]), (30, [93, 111]), (66, [94, 110]), (80, [105, 95]), (92, OPEN)])
    up_l, up_r = [-158, -196], [158, -196]
    c.k('armL.p', [(0, ARM_L), (28, up_l), (48, [-150, -206]), (66, up_l), (86, ARM_L)])
    c.k('armL.r', [(0, 16), (28, -40), (66, -40), (86, 16)])
    c.k('armR.p', [(0, ARM_R), (28, up_r), (48, [150, -206]), (66, up_r), (86, ARM_R)])
    c.k('armR.r', [(0, -16), (28, 40), (66, 40), (86, -16)])
    c.k('armL.s', [(0, OPEN), (28, [92, 112]), (66, [92, 112]), (86, OPEN)])
    c.k('armR.s', [(0, OPEN), (28, [92, 112]), (66, [92, 112]), (86, OPEN)])
    fan = [(0, {}), (28, dict(sway=-22, curl=0.7, len=0.95)), (48, dict(sway=-18, curl=0.5)), (66, dict(sway=-22, curl=0.7, len=0.95)), (86, {})]
    c.k('wispL', fan)
    c.k('wispR', [(t, dict(v, sway=-v.get('sway', 0)) if v else {}) for t, v in fan])
    c.k('wispM', [(0, {}), (28, dict(len=1.12)), (48, dict(len=1.08, sway=3)), (66, dict(len=1.12)), (86, {})])
    c.st('eyes.v', [(0, 'open'), (24, 'happy'), (70, 'open')])
    c.st('mouth.v', [(0, 'smile'), (24, 'o'), (70, 'smile')])
    c.k('bow.r', [(0, 28), (30, 18), (66, 18), (86, 28)])


def idle_fade_blink():
    N = 120
    c = clip('idle_fade_blink', 'idle', N, desc='Slowly fades to ~40%, notices, pops back to full with a startled blink.')
    c.k('char.o', [(0, 100), (44, 40), (60, 40), (66, 100)])
    c.st('eyes.v', [(0, 'open'), (14, 'halflid'), (46, 'open'), (64, 'round'), (82, 'open')])
    c.k('gaze.p', [(0, [0, 0]), (48, [0, 0]), (54, [-10, 10]), (62, [-10, 10]), (64, [0, 0])])
    c.k('eyes.s', [(0, OPEN), (88, OPEN), (90.5, [100, 8]), (93, OPEN), (97, OPEN), (99.5, [100, 8]), (102, OPEN)])
    c.st('mouth.v', [(0, 'smile'), (50, 'o'), (88, 'smile')])
    c.k('mouth.s', [(0, OPEN), (50, [60, 60]), (64, [60, 60]), (68, [110, 110]), (86, [110, 110]), (88, OPEN)])
    c.k('squash.s', [(0, OPEN), (62, OPEN), (67, [110, 108]), (74, [96, 103]), (82, OPEN)])
    c.k('armL.p', [(0, ARM_L), (62, ARM_L), (67, [-190, -6]), (84, ARM_L)])
    c.k('armR.p', [(0, ARM_R), (62, ARM_R), (67, [190, -6]), (84, ARM_R)])
    pop(c, fx_q(1.0), 50, 66, loc(110, -200), loc(116, -208), r0=-10, r1=8)
    pop(c, fx_excl(1.0), 65, 86, loc(124, -206), loc(124, -214), r0=10, r1=0)


def idle_lazy_drift():
    N = 120
    c = clip('idle_lazy_drift', 'idle', N, desc='Lazy figure-eight drift while humming with a small smile.')
    c.k('move.p', wave(N, 1, [BX - 18, BY], [BX + 18, BY], 0.25))
    c.k('bob.p', wave(N, 2, [0, 5], [0, -5], 0.25))
    c.k('move.r', wave(N, 1, -4, 4, 0.25))
    c.st('eyes.v', [(0, 'open'), (24, 'happy'), (96, 'open')])
    c.k('mouth.s', wave(N, 4, [100, 100], [118, 90]))
    c.k('bow.r', wave(N, 2, 26, 32, 0.25))
    for k, t0 in enumerate((14, 52, 86)):
        x = [372, 386, 366][k]
        rise(c, fx_note(1.5, [MINT, PINK, SKY][k]), t0, t0 + 30, [x + 6, 176], 14, 36, r0=-8, r1=10)


# =================================================================== SLEEP
SLEEP_Y = BY + 26
SLEEP_ARM_L, SLEEP_ARM_R = [-122, 70], [118, 66]
SLEEP_TAIL = [100, 55]


def sleep_pose_tracks(c):
    pass


def sleep_fall_asleep():
    N = 90
    c = clip('sleep_fall_asleep', 'sleep', N, loop=False, desc='Eyes droop, sinks lower, curls its tail around itself like a blanket.')
    c.anchor = (0, 120)
    c.st('eyes.v', [(0, 'open'), (16, 'halflid'), (40, 'sleepy')])
    c.k('eyes.s', [(0, OPEN), (14, OPEN), (16, [100, 70]), (22, OPEN), (36, OPEN), (38, [100, 50]), (42, OPEN)])
    c.st('mouth.v', [(0, 'smile'), (50, 'o')])
    c.k('mouth.s', [(0, OPEN), (50, [45, 40]), (60, [60, 55])])
    c.k('move.p', [(0, list(BASE)), (72, [BX, SLEEP_Y])])
    c.k('bob.p', [(0, [0, 0]), (24, [0, -4]), (50, [0, 0])])
    c.k('wrap.w', [(0, 'tucked'), (44, 'tucked'), (76, 'blanket')])
    c.st('wrap.o', [(0, 0), (44, 100)])
    c.k('tail.s', [(0, OPEN), (44, OPEN), (74, SLEEP_TAIL)])
    c.k('armL.p', [(0, ARM_L), (40, ARM_L), (78, SLEEP_ARM_L)])
    c.k('armL.r', [(0, 16), (40, 16), (78, 50)])
    c.k('armR.p', [(0, ARM_R), (40, ARM_R), (78, SLEEP_ARM_R)])
    c.k('armR.r', [(0, -16), (40, -16), (78, -40)])
    c.k('squash.s', [(0, OPEN), (60, [104, 97])])
    c.k('bow.r', [(0, 28), (60, 40)])
    c.st('snot.o', [(0, 0), (80, 100)])
    c.k('snot.s', [(0, [0, 0]), (80, [0, 0]), (90, [20, 20])])
    rise(c, fx_z(0.8), 58, 88, loc(160, -176, BX, SLEEP_Y), 14, 30, r0=-6, r1=8)


def sleep_loop():
    N = 120
    c = clip('sleep_loop', 'sleep', N, desc='Floats low, slow breathing, glow pulse 85-100%, rising z z z, snot bubble.')
    c.anchor = (0, 120)
    c.no_arm_drift = True
    c.k('move.p', [(0, [BX, SLEEP_Y])])
    c.k('bob.p', wave(N, 1, [0, 0], [0, -3]))
    c.k('char.o', wave(N, 1, 100, 85))
    c.st('eyes.v', [(0, 'sleepy')])
    c.st('mouth.v', [(0, 'o')])
    c.k('mouth.s', wave(N, 1, [60, 55], [72, 72]))
    c.k('wrap.w', [(0, 'blanket')])
    c.st('wrap.o', [(0, 100)])
    c.k('tail.s', [(0, SLEEP_TAIL)])
    c.k('squash.s', wave(N, 1, [104, 97], [106, 101]))
    c.k('armL.p', wave(N, 1, SLEEP_ARM_L, [SLEEP_ARM_L[0], SLEEP_ARM_L[1] - 4]))
    c.k('armR.p', wave(N, 1, SLEEP_ARM_R, [SLEEP_ARM_R[0], SLEEP_ARM_R[1] - 4]))
    c.k('armL.r', [(0, 50)])
    c.k('armR.r', [(0, -40)])
    c.k('bow.r', [(0, 40)])
    c.st('snot.o', [(0, 100)])
    c.k('snot.s', wave(N, 1, [20, 20], [130, 130]))
    for k, t0 in enumerate((0, 40, 80)):
        x, y = loc(160, -176, BX, SLEEP_Y)
        rise(c, fx_z([0.8, 0.95, 1.1][k]), t0, t0 + 40, [x, y], 18, 56, r0=-8, r1=10)


def sleep_wake_up():
    N = 75
    c = clip('sleep_wake_up', 'sleep', N, loop=False, desc='Bubble pops, shoots upward startled, two quick blinks, settles into the float.')
    c.st('snot.o', [(0, 100), (9, 0)])
    c.k('snot.s', [(0, [20, 20]), (8, [150, 150])])
    bx, by = loc(30, -24, BX, SLEEP_Y)
    for k, (dx, dy) in enumerate(((-18, -14), (18, -16), (20, 12), (-16, 14))):
        pop(c, fx_sparkle(5, SKY), 9, 21, [bx, by], [bx + dx, by + dy], ein=3, r1=60)
    c.st('eyes.v', [(0, 'sleepy'), (9, 'round'), (36, 'open')])
    c.k('eyes.s', [(0, OPEN), (40, OPEN)] + blink(42) + blink(50))
    c.st('mouth.v', [(0, 'o'), (34, 'smile')])
    c.k('mouth.s', [(0, [60, 55]), (9, [60, 55]), (12, [120, 130]), (30, [110, 120]), (34, OPEN)])
    c.k('move.p', [(0, [BX, SLEEP_Y]), (10, [BX, SLEEP_Y]), (19, [BX, BY - 46]), (40, list(BASE))])
    c.k('bob.p', [(0, [0, 0]), (42, [0, 0]), (58, [0, -4]), (75, [0, 0])])
    c.anchor = (0, 120)
    c.k('squash.s', [(0, [104, 97]), (10, [104, 97]), (16, [90, 116]), (27, [107, 94]), (36, OPEN)])
    c.k('wrap.w', [(0, 'blanket'), (10, 'blanket'), (22, 'tucked')])
    c.st('wrap.o', [(0, 100), (22, 0)])
    c.k('tail.s', [(0, SLEEP_TAIL), (10, SLEEP_TAIL), (24, OPEN)])
    c.k('armL.p', [(0, SLEEP_ARM_L), (10, SLEEP_ARM_L), (17, [-176, -40]), (40, ARM_L)])
    c.k('armL.r', [(0, 50), (10, 50), (17, -10), (40, 16)])
    c.k('armR.p', [(0, SLEEP_ARM_R), (10, SLEEP_ARM_R), (17, [176, -40]), (40, ARM_R)])
    c.k('armR.r', [(0, -40), (10, -40), (17, 10), (40, -16)])
    c.k('bow.r', [(0, 40), (10, 40), (18, 14), (32, 32), (42, 28)])
    pop(c, fx_excl(1.0), 12, 34, loc(126, -210, BX, BY - 46), loc(126, -214, BX, BY - 30), r0=12, r1=4)


# =================================================================== MOVEMENT
def move_walk():
    N = 60
    c = clip('move_walk', 'movement', N, desc='Glides forward in place (facing right), leaning in, tail streaming behind.')
    c.k('move.r', wave(N, 2, 7, 9.5))
    c.k('bob.p', wave(N, 2, [0, 0], [0, -6]))
    c.k('gaze.p', [(0, [8, 0])])
    c.k('face.p', [(0, [7, 0])])
    for key, ph in (('L', 0.0), ('M', 0.2), ('R', 0.4)):
        c.k('wisp' + key, wave(N, 2, WP(sway=-20, curl=-0.6, len=0.92), WP(sway=-32, curl=-0.1, len=0.88), ph))
    c.k('armL.p', wave(N, 2, [-174, 24], [-160, 14], 0.0))
    c.k('armL.r', wave(N, 2, 10, 34, 0.0))
    c.k('armR.p', wave(N, 2, [176, 26], [164, 14], 0.5))
    c.k('armR.r', wave(N, 2, -6, -30, 0.5))
    c.k('bow.r', wave(N, 2, 24, 32, 0.3))
    for t0, y in ((0, 300), (30, 340)):
        line = Shape(PB(0, 0).C(-10, -6, -22, -6, -32, 0).open(), stroke=LAV, width=6, name='wind')
        L = fx('wind', [Shape(PB(0, 0).C(-10, -6, -22, -6, -32, 0).open(), stroke=INK, width=11, name='wo'), line],
               Track([(t0, [138, y]), (t0 + 30, [98, y])]), o=Track([(t0, 0), (t0 + 8, 100), (t0 + 22, 100), (t0 + 30, 0)]))
        c.effects.append(L)


def move_hop():
    N = 60
    c = clip('move_hop', 'movement', N, desc='Dips down, zooms up with arms raised, squashes softly back into the float.')
    c.anchor = (0, 120)
    c.k('bob.p', [(0, [0, 0])])
    c.k('move.p', [(0, list(BASE)), (9, [BX, BY + 14]), (22, [BX, BY - 62]), (32, [BX, BY - 66]), (46, [BX, BY + 6]), (54, [BX, BY - 2]), (60, list(BASE))])
    c.k('squash.s', [(0, OPEN), (9, [112, 89]), (18, [90, 115]), (28, [98, 103]), (36, OPEN), (46, [109, 92]), (53, [97, 103]), (60, OPEN)])
    c.k('armL.p', [(0, ARM_L), (9, [-176, 36]), (20, [-182, -128]), (34, [-186, -134]), (48, ARM_L)])
    c.k('armL.r', [(0, 16), (20, -34), (34, -38), (48, 16)])
    c.k('armR.p', [(0, ARM_R), (9, [176, 36]), (20, [182, -128]), (34, [186, -134]), (48, ARM_R)])
    c.k('armR.r', [(0, -16), (20, 34), (34, 38), (48, -16)])
    c.st('eyes.v', [(0, 'open'), (12, 'happy'), (44, 'open')])
    c.st('mouth.v', [(0, 'smile'), (12, 'open'), (46, 'smile')])
    for key, sw in (('L', -8), ('M', 0), ('R', 8)):
        c.k('wisp' + key, [(0, {}), (9, dict(len=0.85, sway=sw * 0.5)), (20, dict(len=1.22, sway=-sw * 0.5, curl=0.4)),
                           (34, dict(len=1.0, sway=sw, curl=-0.3)), (46, dict(len=0.9)), (60, {})])
    c.k('bow.r', [(0, 28), (9, 34), (20, 16), (36, 30), (46, 36), (60, 28)])
    sparkle(c, 22, *loc(-150, -220, BX, BY - 62), size=8, dur=18)
    sparkle(c, 26, *loc(160, -190, BX, BY - 62), size=6, color=PINK, dur=18)


def move_phase():
    N = 75
    c = clip('move_phase', 'movement', N, desc='Fades out completely, reappears in the same spot with a sparkle puff.')
    c.k('char.o', [(0, 100), (24, 0), (40, 0), (52, 100)])
    c.k('squash.s', [(0, OPEN), (20, [94, 106]), (24, [86, 112]), (40, [86, 112]), (50, [108, 95]), (58, [98, 102]), (66, OPEN)])
    c.st('eyes.v', [(0, 'open'), (8, 'happy'), (46, 'open')])
    c.st('mouth.v', [(0, 'smile'), (8, 'o'), (46, 'open'), (64, 'smile')])
    c.k('mouth.s', [(0, OPEN), (8, [70, 70]), (46, [80, 80]), (64, OPEN)])
    cx, cy = BX, BY - 10
    for k, (dx, dy, r) in enumerate(((-70, -40, 16), (64, -56, 13), (80, 40, 15), (-76, 46, 13), (0, -96, 12), (4, 86, 14))):
        L = fx('puff', fx_puff(r, ['#efe8ff', '#fff3e6', '#eaf6ff'][k % 3]),
               Track([(40, [cx + dx * 1.2, cy + dy * 1.1]), (64, [cx + dx * 1.6, cy + dy * 1.35])]),
               s=Track([(0, [0, 0]), (40, [0, 0]), (48, [110, 110]), (64, [40, 40])]),
               o=Track([(40, 100), (54, 100), (64, 0)]))
        c.under.append(L)
    for k, (dx, dy) in enumerate(((-150, -96), (150, -104), (160, 70), (-156, 80))):
        sparkle(c, 44 + k * 2, cx + dx, cy + dy, size=[10, 8, 9, 7][k], color=[YELLOW, PINK, SKY, YELLOW][k], dur=22)


def move_fall_land():
    N = 90
    c = clip('move_fall_land', 'movement', N, loop=False, desc='Drops in from above flailing, balloon-bounces twice, settles with dizzy stars.')
    c.anchor = (0, 170)
    GY = GROUND - 170 * 0.8 - 4  # tail tip touches the ground line
    c.k('bob.p', [(0, [0, 0]), (70, [0, 0]), (80, [0, -4]), (90, [0, 0])])
    c.k('move.p', [(0, [BX, -170]), (16, [BX, GY]), (30, [BX, BY - 70]), (42, [BX, GY]), (52, [BX, BY - 18]), (60, [BX, GY - 10]), (72, list(BASE))])
    c.k('squash.s', [(0, [90, 114]), (14, [92, 112]), (17, [122, 80]), (24, [94, 108]), (30, OPEN), (42, [112, 90]),
                     (47, [96, 105]), (52, OPEN), (60, [106, 95]), (66, OPEN)])
    c.st('eyes.v', [(0, 'round'), (16, 'squint'), (22, 'round'), (42, 'dizzy'), (80, 'open')])
    c.st('mouth.v', [(0, 'wobble'), (16, 'o'), (22, 'wobble'), (42, 'wobble'), (80, 'smile')])
    c.k('mouth.wob', osc(0, 80, 14, 1, 0, 0))
    flail_l = osc(0, 30, 6, [-176, -110], [-190, -70], [-180, -90])
    flail_r = osc(0, 30, 6, [190, -70], [176, -110], [180, -90])
    c.k('armL.p', flail_l + [(42, [-182, 0]), (60, ARM_L)])
    c.k('armR.p', flail_r + [(42, [182, 0]), (60, ARM_R)])
    c.k('armL.r', osc(0, 30, 6, -30, 30, 0) + [(60, 16)])
    c.k('armR.r', osc(0, 30, 6, 30, -30, 0) + [(60, -16)])
    for key, sw in (('L', -10), ('M', 2), ('R', 10)):
        c.k('wisp' + key, [(0, dict(len=0.82, sway=sw, curl=0.8)), (16, dict(len=0.8, sway=sw * 2, curl=-0.5)),
                           (30, dict(len=1.15, sway=-sw, curl=0.3)), (42, dict(len=0.85, sway=sw * 1.5)),
                           (52, dict(len=1.05)), (60, dict(len=0.95, sway=sw * 0.6)), (72, {})])
    c.k('bow.r', [(0, 10), (16, 44), (30, 20), (42, 38), (60, 26), (72, 28)])
    orbit_stars(c, 44, 86, BX, BY - 162, rx=50, ry=13)


# =================================================================== INTERACTION
def int_dragged():
    N = 60
    c = clip('int_dragged', 'interaction', N,
             desc='Held by the tail tip (grab point 264,427): stretched like taffy, wobbly scared mouth, arms flailing.')
    c.no_bob = True
    c.anchor = (10, 170)
    c.k('squash.s', wave(N, 2, [86, 126], [82, 133]))
    c.k('squash.r', wave(N, 1, -7, 7, 0.25))
    c.st('eyes.v', [(0, 'round')])
    c.st('brows.v', [(0, 'worried')])
    c.st('mouth.v', [(0, 'wobble')])
    c.k('mouth.wob', wave(N, 6, 0, 1))
    c.k('armL.p', wave(N, 4, [-178, -40], [-188, -6], 0.0))
    c.k('armL.r', wave(N, 4, -30, 30, 0.0))
    c.k('armR.p', wave(N, 4, [188, -6], [178, -40], 0.0))
    c.k('armR.r', wave(N, 4, 30, -30, 0.0))
    c.k('wispM', [(0, dict(len=1.15, sway=-10, curl=-0.2))])
    c.k('wispL', wave(N, 3, WP(sway=4, curl=0.8, len=0.9), WP(sway=-6, curl=0.2, len=0.95), 0.1))
    c.k('wispR', wave(N, 3, WP(sway=-4, curl=0.8, len=0.9), WP(sway=6, curl=0.2, len=0.95), 0.4))
    c.k('bow.r', wave(N, 2, 20, 38, 0.25))
    c.k('cheeks.s', [(0, [110, 110])])


def int_petted():
    N = 90
    c = clip('int_petted', 'interaction', N, desc='Happy ^ ^ eyes, rosier cheeks, wiggles into the hand, hearts pop up.')
    c.anchor = (0, 120)
    c.st('eyes.v', [(0, 'open'), (6, 'happy'), (82, 'open')])
    c.k('cheeks.s', [(0, OPEN), (12, [126, 122]), (76, [126, 122]), (86, OPEN)])
    c.k('cheek.c', [(0, CHEEK), (12, CHEEK_ROSY), (76, CHEEK_ROSY), (86, CHEEK)])
    c.st('mouth.v', [(0, 'smile'), (8, 'open'), (80, 'smile')])
    c.k('mouth.s', [(0, OPEN), (8, [70, 70]), (80, [70, 70]), (81, OPEN)])
    c.k('squash.s', osc(4, 82, 7, [97, 104], [104, 96], OPEN))
    c.k('move.r', osc(4, 82, 5, -5, 5, 0))
    c.k('bow.r', osc(4, 82, 5, 22, 34, 28))
    for k, (t0, x) in enumerate(((10, 196), (30, 322), (52, 238))):
        rise(c, fx_heart(1.45 - k * 0.12), t0, t0 + 32, [x, 136], [-6, 8, 4][k], 42, r0=-10 + k * 8, r1=8 - k * 6)


def int_poked():
    N = 105
    c = clip('int_poked', 'interaction', N,
             desc='Jelly wobble, puffed cheeks, angry brows, anger mark, then half see-through with a smug look.')
    c.k('squash.s', [(0, OPEN), (3, [120, 82]), (9, [88, 113]), (15, [110, 92]), (21, [94, 106]), (27, [104, 97]), (34, OPEN)])
    c.st('eyes.v', [(0, 'open'), (2, 'squint'), (14, 'open'), (62, 'halflid'), (98, 'open')])
    c.st('brows.v', [(0, None), (14, 'angry'), (62, None)])
    c.st('mouth.v', [(0, 'smile'), (8, 'pout'), (62, 'smirk'), (98, 'smile')])
    c.k('cheeks.s', [(0, OPEN), (8, OPEN), (14, [148, 140]), (58, [148, 140]), (64, OPEN)])
    c.k('cheekL.p', [(0, [-96, -16]), (8, [-96, -16]), (14, [-104, -12]), (58, [-104, -12]), (64, [-96, -16])])
    c.k('cheekR.p', [(0, [96, -16]), (8, [96, -16]), (14, [104, -12]), (58, [104, -12]), (64, [96, -16])])
    c.st('anger.o', [(0, 0), (12, 100), (62, 0)])
    c.k('anger.s', [(0, [0, 0]), (12, [0, 0]), (17, [125, 125]), (21, [100, 100]), (30, [115, 115]), (38, [100, 100]),
                    (46, [115, 115]), (54, [100, 100]), (61, [0, 0])])
    c.k('char.o', [(0, 100), (62, 100), (72, 50), (92, 50), (102, 100)])
    c.k('face.p', [(0, [0, 0]), (62, [0, 0]), (70, [10, 0]), (94, [10, 0]), (100, [0, 0])])
    c.k('gaze.p', [(0, [0, 0]), (62, [0, 0]), (70, [8, 2]), (94, [8, 2]), (100, [0, 0])])
    c.k('move.r', [(0, 0), (16, 0), (22, -3), (40, 3), (58, 0), (70, -5), (94, -5), (102, 0)])
    c.k('armL.p', [(0, ARM_L), (14, [-160, 40]), (58, [-160, 40]), (66, [-176, 30]), (94, [-176, 30]), (102, ARM_L)])
    c.k('armR.p', [(0, ARM_R), (14, [160, 40]), (58, [160, 40]), (66, [176, 30]), (94, [176, 30]), (102, ARM_R)])


def int_tickled():
    N = 75
    c = clip('int_tickled', 'interaction', N, desc='Giggles and wriggles, eyes squeezed shut, tail wisps curling.')
    c.st('eyes.v', [(0, 'open'), (3, 'squint'), (70, 'open')])
    c.st('mouth.v', [(0, 'smile'), (3, 'open'), (70, 'smile')])
    c.k('mouth.s', osc(3, 70, 11, [104, 110], [86, 74], [90, 90]))
    c.k('squash.s', osc(2, 72, 9, [95, 105], [105, 95], OPEN))
    c.k('move.r', osc(2, 72, 7, -6, 6, 0))
    c.k('cheeks.s', [(0, OPEN), (6, [118, 118]), (66, [118, 118]), (72, OPEN)])
    c.k('cheek.c', [(0, CHEEK), (6, CHEEK_ROSY), (66, CHEEK_ROSY), (72, CHEEK)])
    for key, d in (('L', 0), ('M', 3), ('R', 6)):
        kf = [(0, {})]
        n = 8
        for j in range(n):
            t = 4 + d + j * 7.5
            kf.append((t, dict(curl=1.2 if j % 2 == 0 else -0.6, sway=(-10 if j % 2 == 0 else 8) * (1 if key != 'R' else -1), len=0.9)))
        kf.append((N, {}))
        c.k('wisp' + key, kf)
    c.k('armL.p', osc(2, 72, 9, [-150, 40], [-164, 10], ARM_L))
    c.k('armR.p', osc(2, 72, 9, [164, 10], [150, 40], ARM_R))
    c.k('armL.r', osc(2, 72, 9, 50, 0, 16))
    c.k('armR.r', osc(2, 72, 9, 0, -50, -16))
    for k, (t0, x, y) in enumerate(((8, 150, 200), (22, 366, 186), (38, 140, 236), (50, 372, 230))):
        sparkle(c, t0, x, y, size=[8, 7, 6, 8][k], color=[YELLOW, PINK, SKY, PEACH][k], dur=18)


LOOKS = {'up': (0, -1), 'up_right': (0.72, -0.72), 'right': (1, 0), 'down_right': (0.72, 0.72),
         'down': (0, 1), 'down_left': (-0.72, 0.72), 'left': (-1, 0), 'up_left': (-0.72, -0.72)}


def int_looks():
    for name, (dx, dy) in LOOKS.items():
        c = clip('int_look_' + name, 'interaction', 60,
                 desc='Eyes held looking %s with the float bob (cursor following).' % name.replace('_', '-'))
        c.k('gaze.p', [(0, [dx * 16, dy * 13])])
        c.k('face.p', [(0, [dx * 10, dy * 9])])
        c.k('move.r', [(0, dx * 2.5)])
        c.k('eyes.s', blink(38))


# =================================================================== MOODS
def mood_happy():
    N = 90
    c = clip('mood_happy', 'moods', N, desc='Twirls in a little circle with sparkles, happy ^ ^ eyes.')
    R = 16
    c.k('move.p', wave(N, 1, [BX - R, BY], [BX + R, BY], 0.25))
    c.k('bob.p', wave(N, 1, [0, 0], [0, -2 * R]))
    c.k('squash.s', [(0, OPEN), (26, OPEN), (41, [-100, 100]), (56, OPEN)])
    c.st('eyes.v', [(0, 'open'), (5, 'happy'), (84, 'open')])
    c.st('mouth.v', [(0, 'smile'), (5, 'open'), (84, 'smile')])
    c.k('cheeks.s', [(0, OPEN), (8, [115, 115]), (80, [115, 115]), (86, OPEN)])
    c.k('armL.p', [(0, ARM_L), (12, [-186, -30]), (70, [-186, -30]), (84, ARM_L)])
    c.k('armL.r', [(0, 16), (12, -10), (70, -10), (84, 16)])
    c.k('armR.p', [(0, ARM_R), (12, [186, -30]), (70, [186, -30]), (84, ARM_R)])
    c.k('armR.r', [(0, -16), (12, 10), (70, 10), (84, -16)])
    for k, (t0, x, y) in enumerate(((6, 120, 170), (18, 392, 150), (32, 150, 300), (46, 380, 290), (58, 250, 92), (64, 112, 236))):
        sparkle(c, t0, x, y, size=[10, 9, 7, 8, 9, 6][k], color=[YELLOW, PINK, SKY, PEACH, YELLOW, MINT][k], dur=22)


def mood_sad():
    N = 120
    c = clip('mood_sad', 'moods', N, desc='Sinks low, droopy tail, fades to 70%, teardrop.')
    c.k('move.p', [(0, list(BASE)), (30, [BX, BY + 26]), (90, [BX, BY + 26]), (114, list(BASE))])
    c.k('char.o', [(0, 100), (30, 70), (90, 70), (114, 100)])
    c.k('bob.p', [(0, [0, 0]), (30, [0, 0]), (60, [0, -3]), (90, [0, 0])])
    c.st('brows.v', [(0, None), (10, 'worried'), (100, None)])
    c.st('mouth.v', [(0, 'smile'), (10, 'frown'), (100, 'smile')])
    c.k('gaze.p', [(0, [0, 0]), (24, [0, 7]), (94, [0, 7]), (108, [0, 0])])
    c.k('face.p', [(0, [0, 0]), (24, [0, 6]), (94, [0, 6]), (108, [0, 0])])
    c.k('eyes.s', [(0, OPEN), (24, [100, 88]), (94, [100, 88]), (108, OPEN)])
    for key in 'LMR':
        sw = {'L': 6, 'M': 0, 'R': -6}[key]
        c.k('wisp' + key, [(0, {}), (30, dict(len=1.14, sway=sw, curl=-0.4)), (60, dict(len=1.16, sway=sw * 1.3, curl=-0.5)),
                           (90, dict(len=1.14, sway=sw, curl=-0.4)), (114, {})])
    c.k('armL.p', [(0, ARM_L), (30, [-162, 58]), (90, [-162, 58]), (114, ARM_L)])
    c.k('armL.r', [(0, 16), (30, -8), (90, -8), (114, 16)])
    c.k('armR.p', [(0, ARM_R), (30, [162, 58]), (90, [162, 58]), (114, ARM_R)])
    c.k('armR.r', [(0, -16), (30, 8), (90, 8), (114, -16)])
    c.k('bow.r', [(0, 28), (30, 52), (90, 52), (114, 28)])
    c.k('bow.p', [(0, [98, -150]), (30, [104, -140]), (90, [104, -140]), (114, [98, -150])])
    c.st('tear.o', [(0, 0), (36, 100), (76, 0)])
    c.k('tear.p', [(36, [-66, -26]), (74, [-76, 34])])
    c.k('tear.s', [(0, [0, 0]), (36, [0, 0]), (44, [110, 110]), (66, [100, 100]), (75, [0, 0])])


def mood_surprised():
    N = 75
    c = clip('mood_surprised', 'moods', N, desc='Puffs up bigger, round eyes, "o" mouth, "!" mark.')
    c.k('squash.s', [(0, OPEN), (6, [119, 119]), (10, [123, 121]), (15, [116, 117]), (50, [116, 117]), (62, OPEN)])
    c.st('eyes.v', [(0, 'open'), (5, 'round'), (56, 'open')])
    c.st('mouth.v', [(0, 'smile'), (5, 'o'), (56, 'smile')])
    c.k('mouth.s', [(0, OPEN), (5, [100, 100]), (10, [140, 145]), (50, [130, 135]), (56, OPEN)])
    c.k('armL.p', [(0, ARM_L), (7, [-192, -24]), (50, [-188, -20]), (62, ARM_L)])
    c.k('armL.r', [(0, 16), (7, 60), (50, 56), (62, 16)])
    c.k('armR.p', [(0, ARM_R), (7, [192, -24]), (50, [188, -20]), (62, ARM_R)])
    c.k('armR.r', [(0, -16), (7, -60), (50, -56), (62, -16)])
    c.k('bow.r', [(0, 28), (6, 12), (12, 34), (18, 24), (24, 28)])
    c.k('bow.s', [(0, OPEN), (6, [120, 120]), (14, OPEN)])
    pop(c, fx_excl(1.25), 7, 54, [384, 108], [388, 104], r0=14, r1=6)


def mood_scared():
    N = 120
    c = clip('mood_scared', 'moods', N, desc='Shivers, wobbly mouth, worried brows, then hides its face behind its tail.')
    c.st('eyes.v', [(0, 'open'), (4, 'round'), (100, 'open')])
    c.st('brows.v', [(0, None), (4, 'worried'), (104, None)])
    c.st('mouth.v', [(0, 'smile'), (4, 'wobble'), (104, 'smile')])
    c.k('mouth.wob', osc(4, 104, 16, 1, 0, 0))
    c.k('move.p', osc(2, 108, 26, [BX - 3, BY], [BX + 3, BY], list(BASE)))
    c.k('squash.s', [(0, OPEN), (6, [96, 98]), (100, [96, 98]), (108, OPEN)])
    c.k('wrap.w', [(0, 'tucked'), (42, 'tucked'), (58, 'face'), (88, 'face'), (104, 'tucked')])
    c.st('wrap.o', [(0, 0), (42, 100), (104, 0)])
    c.k('tail.s', [(0, OPEN), (42, OPEN), (56, [100, 62]), (90, [100, 62]), (104, OPEN)])
    c.k('armL.p', [(0, ARM_L), (8, [-150, 50]), (44, [-150, 50]), (58, [-150, -40]), (88, [-150, -40]), (104, ARM_L)])
    c.k('armL.r', [(0, 16), (8, 30), (44, 30), (58, 0), (88, 0), (104, 16)])
    c.k('armR.p', [(0, ARM_R), (8, [150, 50]), (44, [150, 50]), (58, [176, -20]), (88, [176, -20]), (104, ARM_R)])
    c.k('armR.r', [(0, -16), (8, -30), (44, -30), (58, -10), (88, -10), (104, -16)])
    c.k('bow.r', osc(4, 104, 20, 24, 32, 28))
    c.k('gaze.p', [(0, [0, 0]), (8, [-6, 0]), (20, [6, 0]), (32, [-6, 0]), (44, [0, 0])])
    sw = osc(4, 104, 10, (240, 240), (240, 240), (0, 0))
    drop = pop(c, [outlined(drop_path(0.8), SKY, 'sweat', w=WE)], 10, 40, loc(-118, -140), loc(-122, -110), r0=-20, r1=-20)


def mood_hungry():
    N = 120
    c = clip('mood_hungry', 'moods', N, desc='Rubs its tummy, thought bubble with a toasted marshmallow.')
    rub = [(0, ARM_R), (14, [44, 54]), (24, [84, 60]), (34, [36, 50]), (44, [84, 60]), (54, [36, 50]), (64, [84, 60]),
           (74, [36, 50]), (84, [70, 58]), (100, ARM_R)]
    c.k('armR.p', rub)
    c.k('armR.r', [(0, -16), (14, -60), (84, -60), (100, -16)])
    c.k('gaze.p', [(0, [0, 0]), (14, [-12, -9]), (90, [-12, -9]), (104, [0, 0])])
    c.k('face.p', [(0, [0, 0]), (14, [-6, -4]), (90, [-6, -4]), (104, [0, 0])])
    c.st('mouth.v', [(0, 'smile'), (16, 'open'), (96, 'smile')])
    c.k('mouth.s', [(0, OPEN), (16, [60, 60]), (40, [70, 80]), (64, [60, 60]), (90, [70, 80]), (96, OPEN)])
    c.k('squash.s', [(0, OPEN), (24, [102, 98]), (44, [100, 100]), (64, [102, 98]), (84, OPEN)])
    c.st('tear.o', [(0, 0), (40, 100), (70, 0)])
    c.k('tear.p', [(40, [-14, 10]), (68, [-14, 26])])
    c.k('tear.s', [(0, [0, 0]), (40, [0, 0]), (46, [55, 55]), (62, [60, 60]), (69, [0, 0])])
    pop(c, fx_puff(7, HL), 10, 104, [168, 182], size=100, ein=4)
    pop(c, fx_puff(11, HL), 15, 102, [140, 152], size=100, ein=4)
    cloud_pts = [(-44, 6), (-40, -18), (-18, -34), (8, -36), (32, -26), (46, -4), (40, 20), (16, 32), (-12, 32), (-36, 24)]
    import math
    b = PB(*cloud_pts[0])
    for k in range(len(cloud_pts)):
        a, z = cloud_pts[k], cloud_pts[(k + 1) % len(cloud_pts)]
        mx, my = (a[0] + z[0]) / 2, (a[1] + z[1]) / 2
        nx, ny = mx * 0.32, my * 0.32
        b.C(a[0] + nx, a[1] + ny, z[0] + nx, z[1] + ny, z[0], z[1])
    cloud = b.Z()
    bubble = [outlined(cloud, HL, 'cloud', w=WE)] + [Group('mm', marshmallow(0.95), p=(2, 2), r=-6)]
    pop(c, bubble, 20, 100, [98, 102], [98, 98], r0=-4, r1=4, ein=6)


def mood_love():
    N = 105
    c = clip('mood_love', 'moods', N, desc='Heart eyes, body tints pale pink (flat colour swap), floating hearts.')
    c.st('eyes.v', [(0, 'open'), (6, 'heart'), (96, 'open')])
    beat = [(0, OPEN)]
    for t in range(10, 90, 16):
        beat += [(t, OPEN), (t + 3, [118, 118]), (t + 6, [100, 100]), (t + 8, [110, 110]), (t + 12, OPEN)]
    c.k('eyes.s', beat)
    c.k('tint', [(0, WHITE), (8, TINT_LOVE), (90, TINT_LOVE), (100, WHITE)])
    c.k('cheek.c', [(0, CHEEK), (8, CHEEK_ROSY), (90, CHEEK_ROSY), (100, CHEEK)])
    c.k('cheeks.s', [(0, OPEN), (8, [120, 116]), (90, [120, 116]), (100, OPEN)])
    c.st('mouth.v', [(0, 'smile'), (8, 'open'), (94, 'smile')])
    c.k('mouth.s', [(0, OPEN), (8, [70, 70]), (94, [70, 70]), (95, OPEN)])
    c.k('move.r', osc(4, 100, 3, -4, 4, 0))
    c.k('armL.p', [(0, ARM_L), (10, [-150, 0]), (92, [-150, 0]), (102, ARM_L)])
    c.k('armL.r', [(0, 16), (10, 40), (92, 40), (102, 16)])
    c.k('armR.p', [(0, ARM_R), (10, [150, 0]), (92, [150, 0]), (102, ARM_R)])
    c.k('armR.r', [(0, -16), (10, -40), (92, -40), (102, -16)])
    for k, (t0, x, y) in enumerate(((8, 130, 230), (22, 388, 210), (40, 160, 160), (56, 360, 140), (68, 250, 110))):
        rise(c, fx_heart([1.3, 1.4, 1.15, 1.3, 1.1][k], [HEART, PINK, HEART, PINK, HEART][k]), t0, t0 + 32, [x, y],
             [-6, 6, -4, 8, 0][k], 40, r0=[-12, 10, -6, 12, 0][k], r1=[8, -8, 6, -6, 0][k])


def mood_smile_wink():
    N = 75
    c = clip('mood_smile_wink', 'moods', N, desc='Big open smile with tongue, playful wink with a sparkle.')
    c.st('mouth.v', [(0, 'smile'), (4, 'open'), (68, 'smile')])
    c.k('mouth.s', [(0, OPEN), (4, [100, 100]), (10, [126, 122]), (62, [126, 122]), (68, OPEN)])
    c.st('eyeR.v', [(0, 'open'), (20, 'wink'), (50, 'open')])
    c.k('eyeR.s', [(0, OPEN), (18, OPEN), (20, [100, 40]), (22, OPEN), (48, OPEN), (50, [100, 50]), (53, OPEN)])
    c.k('move.r', [(0, 0), (16, 0), (22, -7), (48, -7), (56, 0)])
    c.k('squash.s', [(0, OPEN), (18, OPEN), (22, [106, 95]), (28, [98, 102]), (34, OPEN)])
    c.k('armR.p', [(0, ARM_R), (16, [176, -40]), (52, [176, -40]), (64, ARM_R)])
    c.k('armR.r', [(0, -16), (16, -60), (24, -40), (32, -60), (40, -40), (52, -60), (64, -16)])
    c.k('cheeks.s', [(0, OPEN), (10, [114, 114]), (62, [114, 114]), (68, OPEN)])
    sparkle(c, 21, 352, 196, size=11, dur=26)
    sparkle(c, 25, 374, 222, size=6, color=PINK, dur=22)


# =================================================================== FUN
def fun_boo():
    N = 105
    c = clip('fun_boo', 'fun', N, desc='Dips out of view at the bottom, pops up with arms raised and a big BOO, then giggles.')
    c.anchor = (0, 120)
    c.k('bob.p', [(0, [0, 0])])
    DOWN = 690
    c.k('move.p', [(0, list(BASE)), (6, [BX, BY - 10]), (24, [BX, DOWN]), (36, [BX, DOWN]), (46, [BX, BY - 46]), (52, [BX, BY - 40]),
                   (62, [BX, BY - 40]), (74, list(BASE))])
    c.k('shadow.s', [(0, OPEN), (6, [96, 96]), (18, [0, 0]), (38, [0, 0]), (46, [80, 80]), (74, OPEN)])
    c.k('squash.s', [(0, OPEN), (6, [104, 97]), (14, [92, 112]), (24, [92, 112]), (36, [92, 112]), (44, [90, 118]), (50, [116, 110]),
                     (58, [112, 108]), (70, OPEN), (76, [106, 95]), (82, [97, 103]), (88, [104, 97]), (94, OPEN)])
    c.st('eyes.v', [(0, 'open'), (8, 'happy'), (38, 'squint'), (64, 'happy'), (98, 'open')])
    c.st('mouth.v', [(0, 'smile'), (38, 'boo'), (64, 'open'), (98, 'smile')])
    c.k('mouth.s', [(0, OPEN), (38, [60, 60]), (48, [118, 118]), (60, [110, 110]), (64, [70, 70]), (70, [80, 70]), (76, [64, 74]),
                    (82, [80, 70]), (88, [64, 74]), (96, [70, 70]), (98, OPEN)])
    up_l, up_r = [-186, -132], [186, -132]
    c.k('armL.p', [(0, ARM_L), (36, ARM_L), (46, up_l), (60, [-190, -140]), (72, ARM_L)])
    c.k('armL.r', [(0, 16), (36, 16), (46, -38), (60, -44), (72, 16)])
    c.k('armR.p', [(0, ARM_R), (36, ARM_R), (46, up_r), (60, [190, -140]), (72, ARM_R)])
    c.k('armR.r', [(0, -16), (36, -16), (46, 38), (60, 44), (72, -16)])
    c.k('cheeks.s', [(0, OPEN), (64, OPEN), (70, [118, 118]), (94, [118, 118]), (100, OPEN)])
    c.k('bow.r', [(0, 28), (40, 28), (48, 10), (56, 34), (64, 26), (72, 28)])
    for key, sw in (('L', -12), ('M', 0), ('R', 12)):
        c.k('wisp' + key, [(0, {}), (24, dict(len=0.8, sway=sw * 0.5)), (44, dict(len=1.2, curl=0.5)), (52, dict(sway=sw, curl=-0.3)),
                           (66, {}), (105, {})])
    pop(c, fx_boo(), 46, 72, [256, 66], [256, 60], size=110, r0=-6, r1=4, ein=4)
    for k, (t0, x, y) in enumerate(((68, 388, 210), (78, 130, 196))):
        sparkle(c, t0, x, y, size=7, color=[PINK, YELLOW][k], dur=18)


def fun_spin():
    N = 90
    c = clip('fun_spin', 'fun', N, desc='Fast corkscrew spin with the tail whipping around, then a dizzy wobble.')
    flip = [(0, OPEN), (6, OPEN)]
    for k, t in enumerate(range(12, 55, 6)):
        flip.append((t, [-100 if k % 2 == 0 else 100, 100]))
    c.k('squash.s', flip)
    c.k('squash.r', [(0, 0), (6, 0)] + [(t, (8 if k % 2 == 0 else -8)) for k, t in enumerate(range(12, 49, 6))] + [(56, 0)])
    c.k('move.p', [(0, list(BASE)), (8, [BX, BY + 6]), (30, [BX, BY - 36]), (54, [BX, BY - 4]), (60, list(BASE))])
    c.k('bob.p', [(0, [0, 0])])
    c.k('move.r', [(0, 0), (56, 0), (61, -9), (66, 8), (71, -6), (76, 4), (82, -2), (88, 0)])
    c.st('eyes.v', [(0, 'open'), (6, 'squint'), (55, 'dizzy'), (84, 'open')])
    c.st('mouth.v', [(0, 'smile'), (6, 'open'), (55, 'wobble'), (84, 'smile')])
    c.k('mouth.wob', osc(55, 84, 6, 1, 0, 0))
    for key, ph in (('L', 0), ('M', 1), ('R', 2)):
        kf = [(0, {}), (6, {})]
        for k, t in enumerate(range(12, 49, 6)):
            s = 30 if (k + ph) % 2 == 0 else -30
            kf.append((t + ph, dict(sway=s, curl=0.9 if s > 0 else -0.9, len=0.9)))
        kf += [(58, dict(sway=-8)), (66, dict(sway=8)), (76, {})]
        c.k('wisp' + key, kf)
    c.k('armL.p', [(0, ARM_L), (8, [-150, -60]), (54, [-150, -60]), (62, ARM_L)])
    c.k('armR.p', [(0, ARM_R), (8, [150, -60]), (54, [150, -60]), (62, ARM_R)])
    c.k('armL.r', [(0, 16), (8, -20), (54, -20), (62, 16)])
    c.k('armR.r', [(0, -16), (8, 20), (54, 20), (62, -16)])
    for k, (t0, y) in enumerate(((12, 380), (24, 340), (36, 360))):
        L = fx('swirl', [Shape(PB(-24, 0).C(-12, 8, 12, 8, 24, 0).open(), stroke=INK, width=11, name='so'),
                         Shape(PB(-24, 0).C(-12, 8, 12, 8, 24, 0).open(), stroke=LAV, width=6, name='si')],
               Track([(t0, [256 + (-110 if k % 2 else 110), y]), (t0 + 14, [256 + (-130 if k % 2 else 130), y - 12])]),
               o=Track([(t0, 0), (t0 + 4, 100), (t0 + 10, 100), (t0 + 14, 0)]))
        c.effects.append(L)
    orbit_stars(c, 56, 88, BX, BY - 160, rx=48, ry=12)


def fun_peek():
    N = 120
    c = clip('fun_peek', 'fun', N, desc='Fades in halfway through the right edge, peeks, blinks, fades out.')
    X_IN, X_OUT = 506, 548
    c.k('move.p', [(0, [X_OUT, BY]), (22, [X_IN, BY]), (92, [X_IN, BY]), (114, [X_OUT, BY])])
    c.k('char.o', [(0, 0), (20, 100), (94, 100), (114, 0)])
    c.k('move.r', [(0, 0), (24, -14), (60, -16), (90, -14), (110, 0)])
    c.k('gaze.p', [(0, [-14, 0]), (64, [-14, 0]), (72, [-6, 4]), (90, [-6, 4]), (100, [-14, 0])])
    c.k('face.p', [(0, [-10, 0])])
    c.k('eyes.s', [(0, OPEN)] + blink(44) + blink(52))
    c.st('mouth.v', [(0, 'o'), (66, 'smile')])
    c.k('mouth.s', [(0, [70, 70]), (66, [70, 70]), (67, OPEN)])
    c.k('armL.p', [(0, [-178, 30]), (26, [-180, -40]), (40, [-176, -50]), (60, [-180, -40]), (92, [-180, -40]), (110, [-178, 30])])
    c.k('armL.r', [(0, 16), (26, 40), (40, 20), (60, 40), (92, 40), (110, 16)])
    pop(c, fx_q(0.9), 30, 60, [388, 150], [384, 144], r0=-12, r1=8)


def fun_notify():
    N = 90
    c = clip('fun_notify', 'fun', N, desc='Holds up the lantern under a round yellow "!" badge, flame flickering, happy open mouth.')
    c.st('lantern.o', [(0, 0), (4, 100), (86, 0)])
    c.k('lantern.s', [(4, [0, 0]), (12, [148, 148]), (16, [135, 135]), (78, [135, 135]), (86, [0, 0])])
    c.k('lantern.r', [(0, 16), (12, -6)] + osc(14, 76, 4, 10, -8, -2) + [(86, 16)])
    c.k('armR.p', [(0, ARM_R), (12, [190, -96]), (76, [190, -96]), (86, ARM_R)])
    c.k('armR.r', [(0, -16), (12, 12), (76, 12), (86, -16)])
    c.st('flame.o', [(0, 0), (12, 100), (82, 0)])
    c.k('flame.s', osc(12, 82, 13, [86, 116], [110, 92], [100, 100]))
    c.k('flame.r', osc(12, 82, 9, -7, 7, 0))
    c.st('mouth.v', [(0, 'smile'), (10, 'open'), (80, 'smile')])
    c.k('mouth.s', [(0, OPEN), (10, [100, 100]), (80, [100, 100]), (81, OPEN)])
    c.k('gaze.p', [(0, [0, 0]), (14, [8, -6]), (30, [8, -6]), (38, [0, 0])])
    c.k('move.r', [(0, 0), (12, -4), (76, -4), (86, 0)])
    c.k('bow.r', [(0, 28), (12, 22), (76, 22), (86, 28)])
    badge = [outlined(ellipse(0, 0, 25, 25), YELLOW, 'badge', w=WE)] + glyph(g_excl(1.0), HL, 'bx', w_in=6.5, w_out=12.5)
    bx, by = loc(196, -176)
    bounce = [(10, [0, 0]), (16, [118, 118]), (21, [100, 100])] + [(t, [108, 108] if k % 2 == 0 else [100, 100]) for k, t in enumerate(range(30, 72, 7))] + [(76, [100, 100]), (84, [0, 0])]
    c.effects.append(fx('badge', badge, Track([(10, [bx, by]), (84, [bx, by])]), s=Track([(0, [0, 0])] + bounce),
                        r=Track([(10, -16), (21, 0)] + osc(24, 76, 5, 6, -6, 0))))


def fun_lantern_glow():
    N = 150
    c = clip('fun_lantern_glow', 'fun', N,
             desc='Lights the lantern, face glows warm, looks around, then blows the flame out.')
    hold = [120, -18]
    c.st('lantern.o', [(0, 0), (4, 100), (146, 0)])
    c.k('lantern.s', [(4, [0, 0]), (12, [148, 148]), (16, [135, 135]), (136, [135, 135]), (146, [0, 0])])
    c.k('lantern.r', [(0, 16), (14, 0)] + osc(30, 100, 4, 6, -6, 0) + [(130, 0), (146, 16)])
    c.k('armR.p', [(0, ARM_R), (14, hold), (134, hold), (146, ARM_R)])
    c.k('armR.r', [(0, -16), (14, -4), (134, -4), (146, -16)])
    c.st('flame.o', [(0, 0), (26, 100), (114, 0)])
    c.k('flame.s', [(26, [0, 0]), (31, [130, 130]), (35, [100, 100])] + osc(36, 104, 11, [88, 114], [110, 92], [100, 100]) +
        [(106, [90, 70]), (110, [60, 30]), (113, [20, 10])])
    c.k('flame.r', [(0, 0), (36, 0)] + osc(36, 104, 7, -7, 7, 0) + [(106, -25), (113, -40)])
    sparkle(c, 24, *loc(120 + 0, -18 + 84), size=9, dur=16)
    c.k('tint', [(0, WHITE), (28, WHITE), (40, TINT_WARM), (110, TINT_WARM), (124, WHITE)])
    c.k('cheek.c', [(0, CHEEK), (28, CHEEK), (40, PEACH), (110, PEACH), (124, CHEEK)])
    c.k('gaze.p', [(0, [0, 0]), (16, [10, 8]), (34, [10, 8]), (44, [-14, 0]), (62, [-14, 0]), (72, [14, -2]), (88, [14, -2]),
                   (96, [8, 6]), (116, [8, 6]), (124, [0, 0])])
    c.k('face.p', [(0, [0, 0]), (16, [4, 4]), (34, [4, 4]), (44, [-8, 0]), (62, [-8, 0]), (72, [8, 0]), (88, [8, 0]),
                   (96, [8, 4]), (116, [8, 4]), (124, [0, 0])])
    c.k('move.r', [(0, 0), (44, -3), (62, -3), (72, 3), (88, 3), (96, 0)])
    c.st('mouth.v', [(0, 'smile'), (30, 'open'), (58, 'smile'), (100, 'o'), (118, 'smile')])
    c.k('mouth.s', [(0, OPEN), (30, [80, 80]), (57, [80, 80]), (58, OPEN), (100, [60, 60]), (106, [55, 50]), (114, [70, 70]), (117, OPEN)])
    c.k('cheeks.s', [(0, OPEN), (96, OPEN), (102, [135, 125]), (108, [140, 128]), (113, OPEN)])
    c.k('eyes.s', [(0, OPEN)] + blink(66) + [(100, OPEN), (104, [100, 60]), (114, [100, 60]), (118, OPEN)])
    hx, hy = loc(120, 54)
    c.under.append(fx('halo', [Shape(ellipse(0, 0, 74, 74), fill=YELLOW_PALE, name='h1'),
                               Shape(ellipse(0, 0, 46, 46), fill='#fff6c8', name='h2')],
                      [hx, hy], s=Track([(0, [0, 0]), (26, [0, 0]), (38, [100, 100]), (66, [92, 92]), (86, [100, 100]), (112, [96, 96]), (124, [70, 70])]),
                      o=Track([(0, 0), (26, 0), (36, 60), (66, 48), (86, 60), (112, 55), (124, 0)])))
    for k, t0 in enumerate((114, 122)):
        L = fx('smoke', glyph([PB(0, 10).C(-8, 4, 8, -4, 0, -10).open()], '#efe8ff', 'sm', w_in=6, w_out=11),
               Track([(t0, [hx + 2, hy - 20]), (t0 + 22, [hx + 8 + k * 6, hy - 60])]),
               s=Track([(t0, [60, 60]), (t0 + 22, [110, 110])]), o=Track([(0, 0), (t0, 0), (t0 + 4, 100), (t0 + 14, 100), (t0 + 22, 0)]))
        c.effects.append(L)


for f in (idle_breathe, idle_look_left_right, idle_yawn, idle_stretch, idle_fade_blink, idle_lazy_drift,
          sleep_fall_asleep, sleep_loop, sleep_wake_up,
          move_walk, move_hop, move_phase, move_fall_land,
          int_dragged, int_petted, int_poked, int_tickled, int_looks,
          mood_happy, mood_sad, mood_surprised, mood_scared, mood_hungry, mood_love, mood_smile_wink,
          fun_boo, fun_spin, fun_peek, fun_notify, fun_lantern_glow):
    f()
