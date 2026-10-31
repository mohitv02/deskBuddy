"""All reactions for the chibi cat."""
import math
from rig import Clip, dflt, norm

CLIPS = []


def clip(name, T, cat, desc, once=False):
    c = Clip(name, T, cat, desc, once)
    CLIPS.append(c)
    return c


# ------------------------------------------------------------ helpers
def show(c, part, *ranges):
    ranges = ranges or ((0, None),)
    keys = [(0, 0, 'h')]
    for a, b in ranges:
        keys.append((a, 100, 'h'))
        if b is not None and b < c.T:
            keys.append((b, 0, 'h'))
    c.k(part, 'o', *keys)


def hide(c, part, *ranges):
    ranges = ranges or ((0, None),)
    keys = [(0, 100, 'h')]
    for a, b in ranges:
        keys.append((a, 0, 'h'))
        if b is not None and b < c.T:
            keys.append((b, 100, 'h'))
    c.k(part, 'o', *keys)


ALL = [(0, None)]


def breathe(c, a, b, period=45, head=True, body_base=(100, 100), amp=(1, 3), head_base=(0, 0), head_amp=4):
    t = a
    h = period / 2
    while t < b - 1e-6:
        c.k('Body', 's', (t, body_base), (t + h, (body_base[0] + amp[0], body_base[1] + amp[1])))
        if head:
            c.k('Head', 'p', (t, head_base), (t + h, (head_base[0], head_base[1] - head_amp)))
        t += period
    c.k('Body', 's', (b, body_base))
    if head:
        c.k('Head', 'p', (b, head_base))


def blink(c, t, base=(100, 100), parts=('EyeL', 'EyeR')):
    for p in parts:
        c.k(p, 's', (t, base), (t + 3, (base[0], 10)), (t + 6, base))


def osc(c, part, prop, a, b, period, lo, hi):
    """Smooth back-and-forth lo->hi->lo every period, from a to b."""
    t = a
    while t < b - 1e-6:
        c.k(part, prop, (t, lo), (t + period / 2, hi))
        t += period
    c.k(part, prop, (b, lo))


def floater(c, part, start, L, p0, p1, smax=100, r0=0, r1=0, step=3):
    T = c.T
    ts = list(range(0, T, step)) + [T]
    for t in ts:
        u = ((t - start) % T) / L
        if u <= 1:
            x = p0[0] + (p1[0] - p0[0]) * u
            y = p0[1] + (p1[1] - p0[1]) * u
            s = smax * (u / 0.15) if u < 0.15 else smax * (1 - 0.2 * (u - 0.15) / 0.85)
            o = 100 if u < 0.65 else 100 * max(0.0, 1 - (u - 0.65) / 0.35)
            r = r0 + (r1 - r0) * u
        else:
            x, y = p0; s = 0; o = 0; r = r0
        c.k(part, 'p', (t, (round(x, 2), round(y, 2)), 'l'))
        c.k(part, 's', (t, round(s, 2), 'l'))
        c.k(part, 'o', (t, round(o, 1), 'l'))
        c.k(part, 'r', (t, round(r, 2), 'l'))


def pop(c, part, t_in, t_out, peak=125, settle=100, r=None):
    """Scale an effect in with overshoot at t_in, out at t_out."""
    c.k(part, 's', (0, 0), (t_in, 0), (t_in + 5, peak), (t_in + 9, settle), (t_out - 4, settle), (t_out, 0))
    show(c, part, (t_in, t_out + 1))
    if r:
        c.k(part, 'r', (t_in, r[0]), (t_out, r[1]))


LOAF = {('Body', 's'): (118, 72), ('Head', 'p'): (0, 54), ('Head', 'r'): -5,
        ('PawL', 'p'): (-4, 0), ('PawR', 'p'): (4, 0), ('PawL', 's'): (100, 76), ('PawR', 's'): (100, 76),
        ('FootL', 'p'): (-15, 3), ('FootR', 'p'): (15, 3), ('FootL', 's'): (110, 75), ('FootR', 's'): (110, 75),
        ('Tail', 'r'): 24, ('EarL', 'r'): -12, ('EarR', 'r'): 12, ('Shadow', 's'): (115, 100)}


def loaf(c, a, b, mode, skip=()):
    for (pt, pr), v in LOAF.items():
        if (pt, pr) in skip:
            continue
        d = dflt(pt, pr)
        if mode == 'to':
            c.k(pt, pr, (a, d), (b, v))
        elif mode == 'from':
            c.k(pt, pr, (a, v), (b, d))
        else:
            c.k(pt, pr, (a, v), (b, v))


def sleepy_face(c, ranges=ALL):
    hide(c, 'EyeL', *ranges); hide(c, 'EyeR', *ranges); show(c, 'LidsSleep', *ranges)


def happy_eyes(c, ranges=ALL):
    hide(c, 'EyeL', *ranges); hide(c, 'EyeR', *ranges); show(c, 'LidsHappy', *ranges)


def mouth(c, name, ranges=ALL):
    hide(c, 'MouthCat', *ranges); show(c, name, *ranges)


# ============================================================ IDLE
c = clip('idle_breathe', 90, 'Idle', 'Default loop: slow squash-and-stretch breathing, one blink')
breathe(c, 0, 90, 45)
blink(c, 62)
c.k('Tail', 'r', (0, -6), (45, 6), (90, -6))

c = clip('idle_ear_twitch', 90, 'Idle', 'One ear flicks quickly, twice')
breathe(c, 0, 90, 45)
c.k('EarL', 'r', (0, 0), (20, 0), (23, -24), (26, -4), (29, -18), (33, 0))
c.k('Tail', 'r', (0, -6), (45, 6), (90, -6))
blink(c, 70)

c = clip('idle_look_left_right', 120, 'Idle', 'Glances left, then right')
breathe(c, 0, 120, 40)
for e in ('EyeL', 'EyeR'):
    c.k(e, 'p', (0, (0, 0)), (10, (-13, 0)), (40, (-13, 0)), (50, (0, 0)), (62, (0, 0)), (72, (13, 0)),
        (102, (13, 0)), (112, (0, 0)))
c.k('Head', 'r', (0, 0), (10, -4), (40, -4), (50, 0), (62, 0), (72, 4), (102, 4), (112, 0))
blink(c, 53)
c.k('Tail', 'r', (0, -6), (60, 6), (120, -6))

c = clip('idle_yawn', 90, 'Idle', 'Big yawn: mouth opens wide, eyes squint')
c.k('Head', 'p', (0, (0, 0)), (18, (0, -8)), (55, (0, -8)), (68, (0, 0)))
c.k('Head', 'r', (0, 0), (18, -6), (55, -6), (68, 0))
c.k('Body', 's', (0, 100), (18, (98, 106)), (55, (98, 106)), (68, 100))
hide(c, 'EyeL', (14, 60)); hide(c, 'EyeR', (14, 60)); show(c, 'LidsSquint', (14, 60))
hide(c, 'MouthCat', (14, 62)); show(c, 'MouthYawn', (14, 62))
c.k('MouthYawn', 's', (0, (60, 5)), (14, (60, 5)), (26, (100, 100)), (50, (100, 108)), (58, (80, 20)), (62, (60, 5)))
c.k('EarL', 'r', (0, 0), (18, -14), (55, -14), (68, 0))
c.k('EarR', 'r', (0, 0), (18, 14), (55, 14), (68, 0))
c.k('Tail', 'r', (0, -6), (45, 8), (90, -6))
blink(c, 76)

c = clip('idle_stretch', 90, 'Idle', 'Leans forward, front paws stretch out, tail goes straight up')
c.k('Body', 's', (0, 100), (20, (112, 82)), (60, (112, 82)), (75, 100))
c.k('Head', 'p', (0, (0, 0)), (20, (0, 30)), (60, (0, 30)), (75, (0, 0)))
c.k('Head', 'r', (0, 0), (20, -3), (60, -3), (75, 0))
c.k('PawL', 'p', (0, (0, 0)), (20, (-40, 6)), (60, (-40, 6)), (75, (0, 0)))
c.k('PawR', 'p', (0, (0, 0)), (20, (40, 6)), (60, (40, 6)), (75, (0, 0)))
c.k('PawL', 's', (0, 100), (20, (140, 72)), (60, (140, 72)), (75, 100))
c.k('PawR', 's', (0, 100), (20, (140, 72)), (60, (140, 72)), (75, 100))
c.k('Tail', 'r', (0, 0), (20, -8), (40, -3), (60, -8), (75, 0))
c.k('Tail', 'p', (0, (0, 0)), (20, (30, 0)), (60, (30, 0)), (75, (0, 0)))
c.k('Tail', 's', (0, 100), (20, (96, 130)), (60, (96, 130)), (75, 100))
c.k('EarL', 'r', (0, 0), (20, -10), (60, -10), (75, 0))
c.k('EarR', 'r', (0, 0), (20, 10), (60, 10), (75, 0))
happy_eyes(c, [(16, 64)]); mouth(c, 'MouthO', [(18, 62)])
c.k('Shadow', 's', (0, 100), (20, (112, 100)), (60, (112, 100)), (75, 100))

c = clip('idle_groom', 120, 'Idle', 'Licks a paw')
breathe(c, 0, 120, 60, head=False)
c.k('PawR', 'p', (0, (0, 0)), (15, (4, -150)), (35, (4, -158)), (45, (4, -150)), (55, (4, -158)), (65, (4, -150)),
    (75, (4, -158)), (85, (4, -150)), (95, (4, -150)), (110, (0, 0)))
c.k('Head', 'r', (0, 0), (15, 6), (95, 6), (110, 0))
happy_eyes(c, [(14, 100)])
show(c, 'Tongue', (28, 84))
c.k('Tongue', 's', (0, 0), (30, 0), (35, 100), (40, 0), (50, 0), (55, 100), (60, 0), (70, 0), (75, 100), (80, 0))
c.k('Tail', 'r', (0, -6), (60, 6), (120, -6))

# ============================================================ SLEEP
c = clip('sleep_fall_asleep', 75, 'Sleep', 'Eyes droop, head sinks, curls into a loaf (play once, then sleep_loop)',
         once=True)
for e in ('EyeL', 'EyeR'):
    c.k(e, 's', (0, 100), (10, (100, 60)), (18, (100, 90)), (28, (100, 40)), (34, (100, 75)), (44, (100, 15)))
hide(c, 'EyeL', (44, None)); hide(c, 'EyeR', (44, None)); show(c, 'LidsSleep', (44, None))
c.k('Head', 'p', (0, (0, 0)), (28, (0, 8)), (34, (0, 4)), (44, (0, 14)))
c.k('Head', 'r', (44, 0))
c.k('EarL', 'r', (0, 0), (30, -6))
c.k('EarR', 'r', (0, 0), (30, 6))
loaf(c, 44, 70, 'to', skip={('Head', 'p'), ('EarL', 'r'), ('EarR', 'r')})
c.k('Head', 'p', (70, (0, 54)))
c.k('EarL', 'r', (60, -12)); c.k('EarR', 'r', (60, 12))

c = clip('sleep_loop', 90, 'Sleep', 'Loaf pose, slow deep breathing, floating z z z and a snot bubble')
loaf(c, 0, 90, 'hold', skip={('Body', 's'), ('Head', 'p')})
c.k('Body', 's', (0, (118, 72)), (45, (121, 78)), (90, (118, 72)))
c.k('Head', 'p', (0, (0, 54)), (45, (0, 50)), (90, (0, 54)))
sleepy_face(c)
for i, (s0, sm) in enumerate(((0, 100), (30, 125), (60, 90)), 1):
    floater(c, f'Z{i}', s0, 60, (350, 214), (412, 110), smax=sm, r0=-12, r1=12)
show(c, 'Bubble', (0, 62), (70, None))
c.k('Bubble', 's', (0, 20), (60, 110), (62, 132), (70, 10), (90, 20))

c = clip('sleep_wake_up', 75, 'Sleep', 'Ears twitch, startled blink, stretches, shakes it off (play once)', once=True)
c.k('EarL', 'r', (0, -12), (4, -28), (7, -8), (10, -22), (14, -12), (38, -12), (55, 0))
c.k('EarR', 'r', (6, 12), (9, 26), (12, 8), (15, 12), (38, 12), (55, 0))
hide(c, 'EyeL', (0, 18)); hide(c, 'EyeR', (0, 18)); show(c, 'LidsSleep', (0, 18))
for e in ('EyeL', 'EyeR'):
    c.k(e, 's', (0, 120), (18, (122, 122)), (24, (110, 110)), (26, (110, 110)), (29, (110, 10)), (32, (110, 110)),
        (34, (110, 110)), (37, (110, 10)), (40, (110, 110)), (48, 100))
for pw, sx, sx2 in (('PawL', -44, -30), ('PawR', 44, 30)):
    lp = LOAF[(pw, 'p')]
    c.k(pw, 'p', (0, lp), (20, lp), (30, (sx, 4)), (38, (sx2, 0)), (55, (0, 0)))
    c.k(pw, 's', (0, (100, 76)), (20, (100, 76)), (30, (140, 68)), (38, (120, 72)), (55, 100))
c.k('Body', 's', (0, (118, 72)), (20, (118, 72)), (30, (126, 66)), (38, (120, 70)), (55, 100))
c.k('Head', 'p', (0, (0, 54)), (20, (0, 54)), (30, (0, 64)), (38, (0, 56)), (55, (0, 0)))
c.k('Head', 'r', (0, -5), (38, -5), (55, 0), (58, -10), (61, 10), (64, -6), (67, 0))
for key in (('FootL', 'p'), ('FootR', 'p'), ('FootL', 's'), ('FootR', 's'), ('Tail', 'r'), ('Shadow', 's')):
    c.k(*key, (0, LOAF[key]), (38, LOAF[key]), (55, dflt(*key)))
blink(c, 66)

# ============================================================ MOVEMENT
c = clip('move_walk', 48, 'Movement', 'Waddle in place: feet step, body rocks side to side')
for cy in (0, 24):
    c.k('Spin', 'r', (cy, -5), (cy + 12, 5), (cy + 24, -5))
    c.k('Root', 'p', (cy, (0, -6)), (cy + 6, (0, 0)), (cy + 12, (0, -6)), (cy + 18, (0, 0)), (cy + 24, (0, -6)))
    c.k('FootL', 'p', (cy, (0, 0)), (cy + 6, (0, 0)), (cy + 12, (0, -14)), (cy + 18, (0, 0)), (cy + 24, (0, 0)))
    c.k('FootR', 'p', (cy, (0, -14)), (cy + 6, (0, 0)), (cy + 18, (0, 0)), (cy + 24, (0, -14)))
    c.k('PawR', 'p', (cy, (0, 0)), (cy + 6, (0, 0)), (cy + 12, (0, -12)), (cy + 18, (0, 0)), (cy + 24, (0, 0)))
    c.k('PawL', 'p', (cy, (0, -12)), (cy + 6, (0, 0)), (cy + 18, (0, 0)), (cy + 24, (0, -12)))
    c.k('EarL', 'r', (cy, 5), (cy + 12, -5), (cy + 24, 5))
    c.k('EarR', 'r', (cy, 5), (cy + 12, -5), (cy + 24, 5))
    c.k('Shadow', 's', (cy, 96), (cy + 6, 100), (cy + 12, 96), (cy + 18, 100), (cy + 24, 96))
c.k('Tail', 'r', (0, -12), (24, 12), (48, -12))
blink(c, 30)

c = clip('move_hop', 45, 'Movement', 'Hop: crouch, jump, squash on landing')
c.k('Root', 's', (0, 100), (7, (112, 88)), (12, (92, 110)), (20, (98, 102)), (26, 100), (31, (116, 84)),
    (36, (96, 104)), (41, 100))
c.k('Root', 'p', (0, (0, 0)), (9, (0, 0), 'o'), (20, (0, -90), 'i'), (31, (0, 0)))
for f in ('FootL', 'FootR', 'PawL', 'PawR'):
    c.k(f, 'p', (0, (0, 0)), (9, (0, 0)), (16, (0, 8)), (27, (0, 8)), (31, (0, 0)))
c.k('EarL', 'r', (0, 0), (7, 8), (16, -14), (26, -4), (32, 14), (38, 0))
c.k('EarR', 'r', (0, 0), (7, -8), (16, 14), (26, 4), (32, -14), (38, 0))
c.k('Shadow', 's', (0, 100), (9, 100, 'o'), (20, 60, 'i'), (31, 100))
c.k('Shadow', 'o', (0, 100), (9, 100, 'o'), (20, 50, 'i'), (31, 100))
mouth(c, 'MouthOpen', [(11, 31)])
c.k('Tail', 'r', (0, 0), (7, -10), (20, 20), (32, -14), (41, 0))

c = clip('move_fall_land', 60, 'Movement', 'Dropped: falls in, squashes on landing, shakes off the dizziness (play once)',
         once=True)
c.k('Root', 'p', (0, (0, -560), 'i'), (14, (0, 0)))
c.k('Root', 's', (0, (94, 108)), (14, (94, 108), 'o'), (17, (126, 70)), (23, (92, 110)), (28, (105, 95)), (33, 100))
c.k('Spin', 'r', (0, -8), (7, 8), (14, 0))
c.k('Shadow', 's', (0, 20, 'i'), (14, 100), (17, (122, 100)), (28, 100))
c.k('Shadow', 'o', (0, 20, 'i'), (14, 100))
for e in ('EyeL', 'EyeR'):
    c.k(e, 's', (0, 125), (14, 125), (15, 100))
hide(c, 'EyeL', (15, 30)); hide(c, 'EyeR', (15, 30)); show(c, 'LidsSquint', (15, 30))
hide(c, 'MouthCat', (0, 30)); show(c, 'MouthO', (0, 15)); show(c, 'MouthFrown', (15, 30))
c.k('PawL', 'p', (0, (-14, -40)), (14, (-14, -40)), (17, (0, 0)))
c.k('PawR', 'p', (0, (14, -40)), (14, (14, -40)), (17, (0, 0)))
c.k('FootL', 'p', (0, (-6, 10)), (14, (-6, 10)), (17, (0, 0)))
c.k('FootR', 'p', (0, (6, 10)), (14, (6, 10)), (17, (0, 0)))
c.k('EarL', 'r', (0, 0), (14, 0), (17, -24), (28, 0))
c.k('EarR', 'r', (0, 0), (14, 0), (17, 24), (28, 0))
c.k('Head', 'r', (0, 0), (32, 0), (35, -7), (38, 7), (41, -4), (44, 0))
c.k('Tail', 'r', (0, -40), (14, -40), (17, 20), (30, 0))
blink(c, 48)

# ============================================================ INTERACTION
c = clip('int_dragged', 40, 'Interaction', 'Being dragged: dangling legs, surprised face')
c.k('Spin', 'r', (0, -7), (20, 7), (40, -7))
c.k('Root', 'p', (0, (0, -24)))
c.k('Shadow', 'o', (0, 30)); c.k('Shadow', 's', (0, 70))
c.k('Body', 's', (0, (96, 106)))
c.k('FootL', 'p', (0, (6, 22))); c.k('FootR', 'p', (0, (-6, 22)))
c.k('FootL', 'r', (0, 10), (20, -10), (40, 10)); c.k('FootR', 'r', (0, 10), (20, -10), (40, 10))
c.k('PawL', 'p', (0, (-6, 16))); c.k('PawR', 'p', (0, (6, 16)))
c.k('PawL', 'r', (0, 8), (20, -8), (40, 8)); c.k('PawR', 'r', (0, 8), (20, -8), (40, 8))
c.k('Tail', 'r', (0, 62), (20, 72), (40, 62))
for e in ('EyeL', 'EyeR'):
    c.k(e, 's', (0, 122))
mouth(c, 'MouthO')
c.k('EarL', 's', (0, (100, 112))); c.k('EarR', 's', (0, (100, 112)))
c.k('EarL', 'r', (0, -4), (20, 4), (40, -4)); c.k('EarR', 'r', (0, -4), (20, 4), (40, -4))

c = clip('int_petted', 60, 'Interaction', 'Petted: happy ^ ^ eyes, hearts pop up')
happy_eyes(c)
c.k('Cheeks', 's', (0, (115, 125)))
c.k('Head', 'r', (0, -5), (30, 5), (60, -5))
c.k('Head', 'p', (0, (0, 6)), (30, (0, 3)), (60, (0, 6)))
c.k('Body', 's', (0, (104, 96)), (30, (106, 94)), (60, (104, 96)))
c.k('EarL', 'r', (0, -16), (30, -10), (60, -16)); c.k('EarR', 'r', (0, 10), (30, 16), (60, 10))
c.k('Tail', 'r', (0, -10), (30, 14), (60, -10))
for i, (s0, a, b) in enumerate(((0, (196, 118), (170, 28)), (20, (306, 108), (334, 22)), (40, (252, 92), (252, 0))), 1):
    floater(c, f'Heart{i}', s0, 40, a, b, smax=100, r0=-12, r1=12)

c = clip('int_poked', 60, 'Interaction', 'Poked too much: puffed cheeks, annoyed face')
show(c, 'PuffL'); show(c, 'PuffR')
c.k('PuffL', 's', (0, 100), (30, 108), (60, 100)); c.k('PuffR', 's', (0, 100), (30, 108), (60, 100))
for e in ('EyeL', 'EyeR'):
    c.k(e, 's', (0, (100, 52))); c.k(e, 'p', (0, (0, 6)))
show(c, 'BrowsAngry')
c.k('Cheeks', 's', (0, (122, 135)))
mouth(c, 'MouthFrown')
show(c, 'Anger')
osc(c, 'Anger', 's', 0, 60, 20, 90, 118)
c.k('Head', 'r', (0, 0), (36, 0), (39, -6), (42, 6), (45, -4), (48, 0))
c.k('EarL', 'r', (0, -24)); c.k('EarR', 'r', (0, 24))
c.k('Tail', 'r', (0, -10), (6, 20), (12, -10), (30, -10), (36, 20), (42, -10), (60, -10))
c.k('Body', 's', (0, (103, 100)))

c = clip('mood_angry', 60, 'Moods', 'Angry: hisses with ears pinned back, fur and tail puffed up, tail lashing, anger mark')
show(c, 'PuffL'); show(c, 'PuffR')
c.k('PuffL', 's', (0, 104), (15, 112), (30, 104), (45, 112), (60, 104))
c.k('PuffR', 's', (0, 104), (15, 112), (30, 104), (45, 112), (60, 104))
for e in ('EyeL', 'EyeR'):
    c.k(e, 's', (0, (100, 48))); c.k(e, 'p', (0, (0, 8)))
show(c, 'BrowsAngry')
c.k('BrowsAngry', 'p', (0, (0, 4)))
c.k('Cheeks', 's', (0, (125, 140)))
mouth(c, 'MouthHiss')
c.k('MouthHiss', 's', (0, (100, 92)), (15, (108, 106)), (30, (100, 92)), (45, (108, 106)), (60, (100, 92)))
show(c, 'Anger')
osc(c, 'Anger', 's', 0, 60, 15, 92, 122)
c.k('EarL', 'r', (0, -40)); c.k('EarR', 'r', (0, 40))
c.k('EarL', 's', (0, (100, 82))); c.k('EarR', 's', (0, (100, 82)))
c.k('Tail', 's', (0, (118, 118)))
osc(c, 'Tail', 'r', 0, 60, 10, -18, 24)
c.k('Body', 's', (0, (106, 102)), (30, (108, 104)), (60, (106, 102)))
c.k('Head', 'r', (0, 0), (5, -3), (10, 3), (15, 0), (60, 0))
c.k('Spin', 'p', (0, (0, 0)), (2, (2, 0)), (4, (-2, 0)), (6, (0, 0)), (30, (0, 0)), (32, (2, 0)), (34, (-2, 0)), (36, (0, 0)), (60, (0, 0)))

c = clip('int_poke_friend', 90, 'Interaction', 'Poked by a friend from chat: startled jump with a "!", then looks left and right for who did it')
c.k('Root', 'p', (0, (0, 0)), (4, (0, 0), 'o'), (9, (0, -22), 'i'), (14, (0, 0)))
c.k('Root', 's', (0, 100), (4, 100), (9, (94, 108)), (14, (106, 94)), (18, 100))
for e in ('EyeL', 'EyeR'):
    c.k(e, 's', (0, 100), (4, 100), (9, 126), (28, 126), (34, 100), (80, 100), (82, (100, 10)), (85, 100))
    c.k(e, 'p', (0, (0, 0)), (30, (0, 0)), (36, (-13, 0)), (48, (-13, 0)), (54, (13, 0)), (66, (13, 0)), (72, (0, 0)))
c.k('Head', 'r', (0, 0), (30, 0), (36, -6), (48, -6), (54, 6), (66, 6), (72, 0))
for ear, r in (('EarL', 8), ('EarR', -8)):
    c.k(ear, 'r', (0, 0), (4, 0), (9, r), (28, r), (34, 0), (74, 0), (76, -r), (78, 0))
mouth(c, 'MouthO', [(6, 30)])
c.k('MouthO', 's', (0, 0), (6, 0), (10, 112), (14, 100), (26, 100), (30, 0))
pop(c, 'Exclaim', 6, 32)
c.k('Exclaim', 'r', (0, 0), (11, -8), (16, 0))
c.k('Tail', 'r', (0, 0), (4, 0), (9, -30), (30, -30), (40, 0), (90, 0))

DIRS = [('up', 0, -10), ('up_right', 9, -8), ('right', 13, 0), ('down_right', 9, 8),
        ('down', 0, 10), ('down_left', -9, 8), ('left', -13, 0), ('up_left', -9, -8)]
for dn, dx, dy in DIRS:
    c = clip(f'int_look_{dn}', 60, 'Interaction', f'Follow cursor: eyes look {dn.replace("_", "-")}')
    breathe(c, 0, 60, 60, head_base=(dx * 0.3, dy * 0.4))
    for e in ('EyeL', 'EyeR'):
        c.k(e, 'p', (0, (dx, dy)))
    c.k('Head', 'r', (0, dx * 0.3))
    blink(c, 40)

# ============================================================ MOODS
c = clip('mood_happy', 50, 'Moods', 'Happy: a little jump with sparkles')
c.k('Root', 's', (0, 100), (6, (110, 90)), (12, (94, 106)), (20, 100), (27, (112, 88)), (33, 100))
c.k('Root', 'p', (0, (0, 0)), (6, (0, 0), 'o'), (16, (0, -50), 'i'), (26, (0, 0)))
happy_eyes(c); mouth(c, 'MouthOpen')
c.k('Cheeks', 's', (0, 115))
c.k('Shadow', 's', (0, 100), (6, 100, 'o'), (16, 75, 'i'), (26, 100))
for i in (1, 2, 3):
    t0 = 10 + (i - 1) * 3
    show(c, f'Spark{i}', (t0, t0 + 20))
    c.k(f'Spark{i}', 's', (0, 0), (t0, 0), (t0 + 6, 125), (t0 + 12, 85), (t0 + 20, 0))
    c.k(f'Spark{i}', 'r', (0, 0), (t0, 0), (t0 + 20, 90))
osc(c, 'Tail', 'r', 0, 50, 10, -14, 14)
c.k('EarL', 'r', (0, 0), (6, 6), (16, -10), (27, 6), (34, 0))
c.k('EarR', 'r', (0, 0), (6, -6), (16, 10), (27, -6), (34, 0))

c = clip('mood_sad', 60, 'Moods', 'Sad: droopy ears, a teardrop')
c.k('EarL', 'r', (0, -32)); c.k('EarR', 'r', (0, 32))
c.k('EarL', 's', (0, (100, 92))); c.k('EarR', 's', (0, (100, 92)))
c.k('Head', 'p', (0, (0, 8)), (30, (0, 12)), (60, (0, 8)))
c.k('Head', 'r', (0, -3))
show(c, 'BrowsSad')
for e in ('EyeL', 'EyeR'):
    c.k(e, 'p', (0, (0, 4))); c.k(e, 's', (0, (96, 92)))
mouth(c, 'MouthFrown')
c.k('Cheeks', 's', (0, 85))
c.k('Body', 's', (0, (101, 96)), (30, (102, 98)), (60, (101, 96)))
c.k('Tail', 'r', (0, 30), (30, 34), (60, 30))
show(c, 'Tear')
c.k('Tear', 's', (0, 0), (2, 0), (10, 100), (40, 100), (41, 0))
c.k('Tear', 'p', (0, (0, 0)), (12, (0, 0), 'i'), (40, (-4, 46)), (41, (0, 0)))
c.k('Tear', 'o', (0, 100), (32, 100), (40, 0), (41, 0, 'h'), (59, 0), (60, 100))

c = clip('mood_surprised', 60, 'Moods', 'Surprised: ears up, big round eyes, "!" mark')
c.k('Root', 'p', (0, (0, 0)), (4, (0, 0), 'o'), (9, (0, -18), 'i'), (14, (0, 0)))
c.k('Root', 's', (0, 100), (4, 100), (9, (94, 108)), (14, (106, 94)), (18, 100))
for ear, r in (('EarL', 6), ('EarR', -6)):
    c.k(ear, 's', (0, 100), (4, 100), (9, (100, 118)), (44, (100, 118)), (52, 100))
    c.k(ear, 'r', (0, 0), (4, 0), (9, r), (44, r), (52, 0))
for e in ('EyeL', 'EyeR'):
    c.k(e, 's', (0, 100), (4, 100), (9, 128), (44, 128), (52, 100))
mouth(c, 'MouthO', [(6, 46)])
c.k('MouthO', 's', (0, 0), (6, 0), (10, 112), (14, 100), (42, 100), (46, 0))
pop(c, 'Exclaim', 6, 46)
c.k('Exclaim', 'r', (0, 0), (11, -8), (16, 0))
c.k('Tail', 'r', (0, 0), (4, 0), (9, -30), (44, -30), (52, 0))

c = clip('mood_hungry', 60, 'Moods', 'Hungry: rubs its belly, dreaming of fish')
c.k('PawL', 'p', (0, (12, -56)), (15, (16, -48)), (30, (12, -56)), (45, (16, -48)), (60, (12, -56)))
c.k('PawR', 'p', (0, (-12, -48)), (15, (-16, -56)), (30, (-12, -48)), (45, (-16, -56)), (60, (-12, -48)))
show(c, 'Speech'); show(c, 'Fish')
c.k('Speech', 's', (0, 100), (30, 105), (60, 100))
osc(c, 'Fish', 'r', 0, 60, 15, -8, 8)
for e in ('EyeL', 'EyeR'):
    c.k(e, 'p', (0, (8, -8)))
blink(c, 40)
c.k('Head', 'r', (0, 4))
breathe(c, 0, 60, 60, head_base=(0, 0))
c.k('EarL', 'r', (0, -8)); c.k('EarR', 'r', (0, 8))
show(c, 'Tongue', (16, 32))
c.k('Tongue', 's', (0, 0), (18, 0), (22, 100), (28, 0))

c = clip('mood_love', 60, 'Moods', 'Love: heart eyes, floating hearts')
hide(c, 'EyeL'); hide(c, 'EyeR'); show(c, 'HeartEyeL'); show(c, 'HeartEyeR')
for h in ('HeartEyeL', 'HeartEyeR'):
    c.k(h, 's', (0, 100), (6, 124), (12, 100), (18, 118), (26, 100), (60, 100))
c.k('Cheeks', 's', (0, (125, 130)))
c.k('Head', 'r', (0, -4), (30, 4), (60, -4))
breathe(c, 0, 60, 60)
c.k('Tail', 'r', (0, -8), (30, 10), (60, -8))
for i, (s0, a, b) in enumerate(((0, (110, 160), (80, 70)), (20, (404, 150), (436, 60)), (40, (360, 80), (380, -10))), 1):
    floater(c, f'Heart{i}', s0, 40, a, b, smax=110, r0=10, r1=-10)

c = clip('mood_smile_wink', 75, 'Moods', 'Big smile with tongue, playful wink and sparkle, excited tail wag')
mouth(c, 'MouthOpen', [(6, 62)])
c.k('MouthOpen', 's', (0, 20), (6, 20), (12, 100), (24, (106, 110)), (30, 100), (56, 100), (62, 20))
c.k('Head', 'p', (0, (0, 0)), (6, (0, 0)), (12, (0, -8)), (18, (0, 0)))
c.k('Body', 's', (0, 100), (6, 100), (12, (99, 104)), (18, 100))
c.k('Head', 'r', (0, 0), (14, 0), (24, 6), (46, 6), (56, 0))
hide(c, 'EyeR', (20, 42)); show(c, 'WinkR', (20, 42))
c.k('EyeR', 's', (0, 100), (16, 100), (20, (100, 10)), (42, (100, 10)), (46, 100))
pop(c, 'WinkSpark', 20, 42, peak=130, settle=90, r=(0, 90))
osc(c, 'Tail', 'r', 6, 62, 12, -14, 16)
blink(c, 66)

# ============================================================ FUN
c = clip('fun_spin', 50, 'Fun', 'Spin / roll: a jumping 360')
c.k('Root', 's', (0, 100), (6, (110, 90)), (12, (96, 104)), (34, (96, 104)), (38, (114, 86)), (44, 100))
c.k('Root', 'p', (0, (0, 0)), (8, (0, 0), 'o'), (22, (0, -60), 'i'), (37, (0, 0)))
c.k('Spin', 'r', (0, 0), (8, 0), (37, 360))
hide(c, 'EyeL', (8, 38)); hide(c, 'EyeR', (8, 38)); show(c, 'LidsSquint', (8, 38))
mouth(c, 'MouthO', [(8, 38)])
c.k('Shadow', 's', (0, 100), (8, 100, 'o'), (22, 60, 'i'), (37, 100))
c.k('EarL', 'r', (0, 0), (37, 0), (40, -14), (46, 0)); c.k('EarR', 'r', (0, 0), (37, 0), (40, 14), (46, 0))

c = clip('fun_peek', 100, 'Fun', 'Peeking: hides past the right screen edge and peeks out')
for part in ('Root', 'Shadow'):
    c.k(part, 'p', (0, (420, 0)), (10, (420, 0), 'o'), (26, (250, 0)), (70, (250, 0)), (86, (420, 0)))
c.k('Spin', 'r', (0, 0), (10, 0), (26, -16), (70, -16), (86, 0))
for e in ('EyeL', 'EyeR'):
    c.k(e, 'p', (0, (-13, 0)))
blink(c, 46)
c.k('EarL', 'r', (0, 0), (34, 0), (37, -20), (40, -2), (43, -14), (47, 0))
c.k('Tail', 'r', (0, -6), (50, 6), (100, -6))

c = clip('fun_notify', 60, 'Fun', 'Notification alert: waves its paw under a "!" badge')
hide(c, 'PawR'); show(c, 'ArmR')
osc(c, 'ArmR', 'r', 0, 60, 20, -14, 14)
show(c, 'Badge')
c.k('Badge', 's', (0, 100), (5, 114), (10, 100), (30, 100), (35, 114), (40, 100), (60, 100))
osc(c, 'Badge', 'r', 0, 60, 20, -8, 8)
mouth(c, 'MouthOpen'); c.k('MouthOpen', 's', (0, 80))
c.k('Root', 'p', (0, (0, 0)), (15, (0, -6)), (30, (0, 0)), (45, (0, -6)), (60, (0, 0)))
c.k('EarL', 's', (0, (100, 108))); c.k('EarR', 's', (0, (100, 108)))
c.k('Head', 'r', (0, -3))
osc(c, 'Tail', 'r', 0, 60, 15, -12, 12)
blink(c, 44)


# ============================================================ FULL SEQUENCE (original)
def concat(name, cat, desc, parts):
    T = sum(p.T for p in parts)
    out = Clip(name, T, cat, desc)
    keys = set()
    for p in parts:
        keys |= set(p.tr)
    off = 0
    for p in parts:
        for tk in keys:
            for (t, v, e) in norm(p.tr.get(tk, []), p.T, dflt(*tk), tk[1]):
                out.tr.setdefault(tk, []).append((t + off, v, e))
        out.markers.append((off, p.name, p.T))
        off += p.T
    CLIPS.append(out)
    return out


_by = {c.name: c for c in CLIPS}
concat('full_loop', 'Sequence', 'Idle -> fall asleep -> sleep -> wake up -> smile, as one seamless loop (with markers)',
       [_by['idle_breathe'], _by['sleep_fall_asleep'], _by['sleep_loop'], _by['sleep_wake_up'],
        _by['mood_smile_wink']])
