"""All 37 clips. Values are absolute; anything not keyed stays in the base pose."""
from model import Clip
from fox import rel, TAIL_BASE

# ------------------------------------------------------------------ tail poses (absolute segment angles)
WRAP = TAIL_BASE
SIDE = (-10, -18, -28, -40)
UP = (-40, -54, -66, -78)
UPCURL = (-40, -58, -84, -122)
MID = (16, 112, 172, 198)
FLOAT = (-14, -8, 2, 12)
GROOM = (-46, -170, 178, 196)
HIDE = (-86, -160, 176, 150)
BLANKET = (-12, -172, 180, 168)
HUG = (34, 152, 204, 246)
FLAG = (-84, -70, -60, -50)


def tail(c, t, ang, e='io', _raw=False):
    if not _raw:
        c.__dict__.setdefault('_tp', []).append((t, ang, e))
    r = rel(ang)
    for i in range(4):
        c.k('tail%d.r' % (i + 1), (t, r[i], e))


def tail_hold(c, t0, t1, ang, e='io'):
    tail(c, t0, ang, e)
    tail(c, t1, ang, e)


def eyes(c, *keys):
    c.st('eyeL', *keys)
    c.st('eyeR', *keys)


def blink(c, t, d=3):
    c.k('eyes.sy', (t, 1, 'i'), (t + d, 0.08, 'o'), (t + 2 * d + 1, 1))


def breathe(c, t0, t1, n=1, amp=0.022, node='char'):
    step = (t1 - t0) / (2 * n)
    for j in range(2 * n + 1):
        t = t0 + j * step
        c.k(node + '.sy', (t, 1 + (amp if j % 2 else 0), 'sine'))
        c.k(node + '.sx', (t, 1 - (amp * 0.45 if j % 2 else 0), 'sine'))


def ears(c, t, l, r, e='io'):
    c.k('earL.r', (t, l, e))
    c.k('earR.r', (t, r, e))


def ear_hold(c, t0, t1, l, r):
    ears(c, t0, l, r)
    ears(c, t1, l, r)


def look(c, t, dx, dy, e='io', head=1.0):
    c.k('eyes.x', (t, 13 * dx, e)); c.k('eyes.y', (t, 9 * dy, e))
    c.k('muzzle.x', (t, 13 * dx, e)); c.k('muzzle.y', (t, 5 * dy, e))
    c.k('head.x', (t, 7 * dx * head, e)); c.k('head.y', (t, 6 * dy * head, e))
    c.k('head.r', (t, 5 * dx * head, e))
    c.k('cheeks.x', (t, 5 * dx, e))


def appear(c, n, t0, t1, rise=0.0, scale=1.0, drift=0.0, fade=6):
    c.k(n + '.o', (t0, 0, 'lin'), (t0 + 3, 1, 'lin'), (t1 - fade, 1, 'lin'), (t1, 0, 'lin'))
    for p in ('sx', 'sy'):
        c.k(n + '.' + p, (t0, 0.2 * scale, 'pop'), (t0 + 7, 1.15 * scale), (t0 + 11, scale, 'io'), (t1, scale * 0.9))
    if rise:
        c.k(n + '.y', (t0, 0, 'o'), (t1, -rise))
    if drift:
        c.k(n + '.x', (t0, 0, 'sine'), (t1, drift))


def pose(c, t, d, e='io'):
    c.pose(t, d, e)


CLIPS = []


def clip(name, cat, frames, loop=True, note='', autobase=True, settle=None):
    c = Clip(name, cat, frames, loop, note, autobase, settle)
    CLIPS.append(c)
    return c


# ================================================================== IDLE
c = clip('idle_breathe', 'idle', 120, note='Default loop.')
breathe(c, 0, 120, 1, 0.026)
c.k('head.y', (0, 0, 'sine'), (64, -2.5, 'sine'), (120, 0))
blink(c, 72)
c.k('tail4.r', (0, rel(WRAP)[3], 'sine'), (40, -14, 'sine'), (84, 24, 'sine'), (120, rel(WRAP)[3]))
c.k('tail3.r', (0, rel(WRAP)[2], 'sine'), (50, 6, 'sine'), (120, rel(WRAP)[2]))

c = clip('idle_ear_twitch', 'idle', 96)
breathe(c, 0, 96, 1, 0.015)
# left ear: swivel out + flick, twice
for t0 in (6, 50):
    c.k('earL.r', (t0, 0, 'io'), (t0 + 6, -16, 'io'), (t0 + 12, -16, 'snap'), (t0 + 14, -32, 'snap'), (t0 + 17, 6, 'snap'), (t0 + 21, 0))
    c.k('earL.sx', (t0, 1, 'io'), (t0 + 6, 0.82, 'io'), (t0 + 14, 0.82, 'snap'), (t0 + 21, 1))
for t0 in (26, 70):
    c.k('earR.r', (t0, 0, 'io'), (t0 + 6, 16, 'io'), (t0 + 12, 16, 'snap'), (t0 + 14, 32, 'snap'), (t0 + 17, -6, 'snap'), (t0 + 21, 0))
    c.k('earR.sx', (t0, 1, 'io'), (t0 + 6, 0.82, 'io'), (t0 + 14, 0.82, 'snap'), (t0 + 21, 1))
c.k('eyes.x', (8, 0), (14, -4), (40, -4), (46, 4), (66, 4), (76, 0))
blink(c, 40)

c = clip('idle_head_tilt', 'idle', 100)
ears(c, 4, 0, 0, 'snap'); ears(c, 7, -8, 8, 'snap'); ears(c, 11, 0, 0)
c.k('head.r', (12, 0), (26, -14), (72, -14), (90, 0))
c.k('head.x', (12, 0), (26, -6), (72, -6), (90, 0))
c.k('earL.r', (14, 0), (26, 12), (72, 12), (88, 0))
c.k('earR.r', (14, 0), (26, -12), (72, -12), (88, 0))
for e in ('earL', 'earR'):
    c.k(e + '.sx', (14, 1), (26, 0.86), (72, 0.86), (88, 1))
    c.k(e + '.sy', (14, 1), (26, 1.06), (72, 1.06), (88, 1))
c.st('brows', (18, 'curious'), (80, 'none'))
c.k('eyes.y', (14, 0), (26, -3), (72, -3), (86, 0))
c.st('mouth', (24, 'o'), (76, 'smile'))
appear(c, 'qmark', 28, 74, rise=10)
c.k('qmark.r', (28, -14, 'sine'), (50, 10, 'sine'), (74, -6))
blink(c, 54)

c = clip('idle_look_left_right', 'idle', 120)
look(c, 0, 0, 0); look(c, 10, -1, 0); look(c, 40, -1, 0); look(c, 52, 1, 0); look(c, 84, 1, 0); look(c, 98, 0, 0)
ears(c, 10, 0, 0); ears(c, 18, -8, -8); ears(c, 40, -8, -8); ears(c, 54, 8, 8); ears(c, 84, 8, 8); ears(c, 98, 0, 0)
blink(c, 64)
breathe(c, 0, 120, 1, 0.015)

c = clip('idle_yawn', 'idle', 100)
c.k('head.r', (6, 0), (22, -6), (58, -6), (72, 0))
c.k('head.y', (6, 0), (22, -8), (58, -8), (72, 0))
c.k('char.sy', (6, 1), (26, 1.045), (56, 1.045), (72, 0.985), (82, 1))
c.k('char.sx', (6, 1), (26, 0.98), (56, 0.98), (72, 1.01), (82, 1))
c.st('mouth', (10, 'o'), (18, 'yawn'), (62, 'o'), (68, 'smile'))
c.k('muzzle.sy', (18, 0.9, 'pop'), (26, 1.12), (56, 1.12), (64, 1))
eyes(c, (16, 'squint'), (64, 'closed'), (72, 'open'))
ears(c, 14, 0, 0); ears(c, 26, -46, 46); ears(c, 58, -46, 46); ears(c, 70, 0, 0, 'snap'); ears(c, 74, 4, -4); ears(c, 78, 0, 0)
for e in ('earL', 'earR'):
    c.k(e + '.sy', (14, 1), (26, 0.86), (58, 0.86), (70, 1))
c.k('tail4.r', (20, rel(WRAP)[3]), (40, -10), (64, rel(WRAP)[3]))
blink(c, 86)

c = clip('idle_stretch', 'idle', 120)
BOW = {'head.y': 66, 'head.r': -4, 'body.sy': 0.72, 'body.sx': 1.1, 'frontL.r': 70, 'frontR.r': -70,
       'frontL.y': 30, 'frontR.y': 30, 'frontL.x': -18, 'frontR.x': 18, 'frontL.sy': 0.9, 'frontR.sy': 0.9,
       'hindL.y': -6, 'hindR.y': -6, 'char.sx': 1.06}
NB = {k: (1 if k.endswith(('.sx', '.sy')) else 0) for k in BOW}
pose(c, 8, NB); pose(c, 28, BOW); pose(c, 76, BOW); pose(c, 96, NB)
c.k('roll.y', (28, 0, 'sine'), (52, 6, 'sine'), (76, 0))
c.st('tail', (16, 'back'), (98, 'mid'))
tail(c, 6, WRAP); tail(c, 16, SIDE); tail(c, 28, UP); tail(c, 44, (-82, -94, -96, -110)); tail(c, 60, UP); tail(c, 76, UP)
tail(c, 88, SIDE); tail(c, 104, WRAP)
eyes(c, (26, 'happy'), (82, 'open'))
c.st('mouth', (30, 'yawn'), (60, 'open'), (80, 'smile'))
ears(c, 24, 0, 0); ears(c, 34, -30, 30); ears(c, 76, -30, 30); ears(c, 92, 0, 0)

c = clip('idle_groom', 'idle', 150)
tail(c, 4, WRAP); tail(c, 14, SIDE); tail(c, 28, GROOM); tail(c, 104, GROOM); tail(c, 118, SIDE); tail(c, 132, WRAP)
for k, t in enumerate((40, 60, 80)):           # fluff
    c.k('tail2.sy', (t, 1, 'pop'), (t + 4, 1.14), (t + 10, 1))
c.k('head.r', (20, 0), (34, 14), (100, 14), (114, 0))
c.k('head.y', (20, 0), (34, 8), (100, 8), (114, 0))
c.k('head.x', (20, 0), (34, -6), (100, -6), (114, 0))
for t in (44, 58, 72, 86):                     # licks: head dips
    c.k('head.y', (t, 8, 'io'), (t + 5, 15, 'io'), (t + 10, 8))
c.st('mouth', (40, 'lick'), (96, 'smile'))
eyes(c, (36, 'closed'), (100, 'open'))
ears(c, 30, 0, 0); ears(c, 40, -10, 10); ears(c, 96, -10, 10); ears(c, 108, 0, 0)
c.k('eyes.x', (28, 0), (36, -4), (100, -4), (110, 0))

# ================================================================== SLEEP
CURL = {'head.y': 70, 'head.r': -10, 'head.x': 6, 'body.sy': 0.74, 'body.sx': 1.16,
        'frontL.y': 34, 'frontR.y': 34, 'frontL.sy': 0.6, 'frontR.sy': 0.6, 'hindL.x': -6, 'hindR.x': 6,
        'char.y': 4, 'earL.r': -24, 'earR.r': 28, 'shadow.sx': 1.12}


def curl_static(c, t0, t1):
    pose(c, t0, CURL); pose(c, t1, CURL)
    tail_hold(c, t0, t1, BLANKET)


c = clip('sleep_fall_asleep', 'sleep', 150, loop=False)
c.k('char.sx', (10, 1, 'io'), (26, -1, 'io'), (42, 1))
c.k('char.y', (10, 0, 'o'), (18, -14, 'i'), (26, 0, 'o'), (34, -14, 'i'), (42, 0))
c.k('char.x', (10, 0, 'sine'), (26, 12, 'sine'), (42, 0))
eyes(c, (6, 'half'), (52, 'half'), (62, 'closed'))
c.st('mouth', (50, 'o'), (56, 'yawn'), (74, 'smile'))
tail(c, 8, WRAP); tail(c, 18, SIDE); tail(c, 34, SIDE); tail(c, 46, WRAP)
pose(c, 52, {k: (1 if k.endswith(('.sx', '.sy')) else 0) for k in CURL})
pose(c, 86, CURL)
c.st('tail', (96, 'top'))
tail(c, 80, WRAP); tail(c, 92, SIDE); tail(c, 112, BLANKET)
curl_static(c, 112, 150)
c.k('body.sy', (112, 0.74, 'sine'), (128, 0.77, 'sine'), (144, 0.74))

c = clip('sleep_loop', 'sleep', 120, note='State loop: starts and ends curled up.', autobase=False)
c.st('tail', (0, 'top'))
eyes(c, (0, 'closed'))
curl_static(c, 0, 120)
c.k('body.sy', (0, 0.74, 'sine'), (60, 0.785, 'sine'), (120, 0.74))
c.k('body.sx', (0, 1.16, 'sine'), (60, 1.14, 'sine'), (120, 1.16))
c.k('head.y', (0, 70, 'sine'), (60, 66, 'sine'), (120, 70))
br = rel(BLANKET)
c.k('tail4.r', (0, br[3]), (34, br[3], 'snap'), (37, br[3] - 22, 'snap'), (41, br[3] + 6), (46, br[3]),
    (88, br[3], 'snap'), (91, br[3] - 18, 'snap'), (95, br[3] + 4), (100, br[3]), (120, br[3]))
c.k('earR.r', (0, 28), (60, 28, 'snap'), (63, 40, 'snap'), (67, 26), (72, 28), (120, 28))
for k, t0 in enumerate((0, 40, 80)):
    n = 'z%d' % (k + 1)
    c.k(n + '.o', (t0, 0, 'lin'), (t0 + 8, 1, 'lin'), (t0 + 30, 1, 'lin'), (t0 + 40, 0))
    c.k(n + '.y', (t0, 30, 'o'), (t0 + 40, -30))
    c.k(n + '.x', (t0, -10, 'sine'), (t0 + 20, 6, 'sine'), (t0 + 40, -4))
    c.k(n + '.sx', (t0, 0.5, 'o'), (t0 + 40, 1.1)); c.k(n + '.sy', (t0, 0.5, 'o'), (t0 + 40, 1.1))

c = clip('sleep_wake_up', 'sleep', 160, loop=False, settle=136)
c.st('tail', (0, 'top'), (66, 'back'), (126, 'mid'))
eyes(c, (0, 'closed'), (34, 'open'), (52, 'happy'), (96, 'squint'), (118, 'open'))
c.st('eyeR', (14, 'open'))
pose(c, 0, CURL); pose(c, 12, CURL)
tail(c, 0, BLANKET); tail(c, 12, BLANKET)
c.k('head.y', (12, 70), (20, 58), (32, 58))
c.k('eyes.x', (14, 0), (18, 6), (30, 6), (36, 0))
tail(c, 18, (-30, -160, 186, 170)); tail(c, 32, (-30, -160, 186, 170))
blink(c, 38)
# rise into a play-bow stretch
pose(c, 54, BOW)
for k in ('char.y', 'earL.r', 'earR.r', 'shadow.sx', 'head.x'):
    c.k(k, (54, {'char.y': 0, 'earL.r': -30, 'earR.r': 30, 'shadow.sx': 1, 'head.x': 0}[k]))
c.k('head.r', (54, -4))
tail(c, 60, SIDE); tail(c, 70, UP); tail(c, 82, UP)
c.st('mouth', (52, 'yawn'), (78, 'smile'), (96, 'open'), (118, 'smile'))
pose(c, 80, BOW)
c.k('earL.r', (80, -30)); c.k('earR.r', (80, 30))
pose(c, 92, {k: (1 if k.endswith(('.sx', '.sy')) else 0) for k in BOW})
# full-body shake
c.st('fur', (94, 'spiky'), (116, 'smooth'))
c.k('roll.r', (90, 0, 'lin'), (94, -9, 'sine'), (98, 9, 'sine'), (102, -9, 'sine'), (106, 9, 'sine'), (110, -6, 'sine'), (114, 3), (120, 0))
c.k('head.r', (90, -4, 'lin'), (95, 12, 'sine'), (99, -12, 'sine'), (103, 12, 'sine'), (107, -12, 'sine'), (111, 8, 'sine'), (115, -3), (121, 0))
c.k('earL.r', (92, -30, 'sine'), (96, 10, 'sine'), (100, -34, 'sine'), (104, 10, 'sine'), (108, -26, 'sine'), (114, 0))
c.k('earR.r', (92, 30, 'sine'), (96, -10, 'sine'), (100, 34, 'sine'), (104, -10, 'sine'), (108, 26, 'sine'), (114, 0))
tail(c, 92, UP); tail(c, 98, (-50, -70, -90, -120)); tail(c, 104, (-100, -100, -96, -80)); tail(c, 110, UP); tail(c, 120, SIDE); tail(c, 134, WRAP)
c.k('char.sy', (114, 1, 'pop'), (118, 0.94), (124, 1))
blink(c, 140)

# ================================================================== MOVEMENT
c = clip('move_walk', 'movement', 32, note='State loop facing left; mirror (scaleX -1) to walk right. Tail floats behind.', autobase=False)
WALK = {'head.x': -8, 'head.r': -3, 'eyes.x': -9, 'muzzle.x': -11, 'cheeks.x': -4, 'roll.r': -3}
for t in (0, 32):
    pose(c, t, WALK)
c.st('tail', (0, 'back'))
for t in (0, 16, 32):
    c.k('char.y', (t, 0, 'o'), (t + 8, -9, 'i')) if t < 32 else c.k('char.y', (t, 0))
c.k('char.sy', (0, 0.97, 'o'), (8, 1.03, 'i'), (16, 0.97, 'o'), (24, 1.03, 'i'), (32, 0.97))
c.k('char.sx', (0, 1.02, 'o'), (8, 0.99, 'i'), (16, 1.02, 'o'), (24, 0.99, 'i'), (32, 1.02))
for leg, ph in (('frontL', 0), ('hindR', 0), ('frontR', 16), ('hindL', 16)):
    ks = [(0, 0), (4, -14), (10, -12), (16, 0), (32, 0)]
    for t, v in ks:
        c.k(leg + '.y', ((t + ph) % 32, v, 'io'))
    c.k(leg + '.y', (32, c.tracks[leg + '.y'][0][1]))
    rk = [(0, 0), (6, -10 if 'L' in leg else -8), (16, 0)]
    for t, v in rk:
        c.k(leg + '.r', ((t + ph) % 32, v))
    c.k(leg + '.r', (32, c.tracks[leg + '.r'][0][1]))
fl = FLOAT
for t, d in ((0, 0), (8, 1), (16, 0), (24, -1), (32, 0)):
    tail(c, t, (fl[0] + 6 * d, fl[1] - 8 * d, fl[2] + 10 * d, fl[3] - 14 * d), 'sine')
for e, s in (('earL', 1), ('earR', 1)):
    c.k(e + '.r', (0, -4, 'sine'), (8, 4, 'sine'), (16, -4, 'sine'), (24, 4, 'sine'), (32, -4))
c.k('shadow.sx', (0, 1, 'o'), (8, 0.94, 'i'), (16, 1, 'o'), (24, 0.94, 'i'), (32, 1))

c = clip('move_hop', 'movement', 48)
c.k('char.sy', (0, 1), (8, 0.82, 'snap'), (12, 1.1, 'o'), (20, 1.0, 'i'), (28, 1.06), (31, 0.8, 'snap'), (36, 1.04), (42, 1))
c.k('char.sx', (0, 1), (8, 1.12, 'snap'), (12, 0.93, 'o'), (20, 1.0, 'i'), (28, 0.96), (31, 1.16, 'snap'), (36, 0.98), (42, 1))
c.k('char.y', (8, 0, 'o'), (19, -120, 'i'), (30, 0))
for leg, s in (('frontL', 1), ('frontR', -1)):
    c.k(leg + '.y', (8, 0), (14, -16), (24, -16), (30, 0))
    c.k(leg + '.r', (8, 0), (14, -16 * s), (24, -16 * s), (30, 0))
for leg in ('hindL', 'hindR'):
    c.k(leg + '.y', (8, 0), (14, -10), (24, -10), (30, 0))
tail(c, 6, WRAP); tail(c, 14, (40, 120, 150, 170)); tail(c, 26, (40, 120, 150, 170)); tail(c, 34, (66, 176, 192, 214)); tail(c, 42, WRAP)
ears(c, 8, 0, 0); ears(c, 14, -14, 14); ears(c, 24, 10, -10); ears(c, 31, -26, 26, 'snap'); ears(c, 38, 4, -4); ears(c, 44, 0, 0)
c.k('shadow.sx', (8, 1), (19, 0.55), (30, 1)); c.k('shadow.o', (8, 1), (19, 0.45), (30, 1))
eyes(c, (8, 'squint'), (12, 'happy'), (30, 'squint'), (36, 'open'))
c.st('mouth', (12, 'open'), (34, 'smile'))

c = clip('move_pounce', 'movement', 170)
# crouch & focus
CROUCH = {'head.y': 34, 'char.sy': 0.86, 'char.sx': 1.06, 'eyes.y': 4, 'earL.r': 10, 'earR.r': -10,
          'frontL.y': -4, 'frontR.y': -4, 'char.x': -28}
pose(c, 4, {k: (1 if k.endswith(('.sx', '.sy')) else 0) for k in CROUCH}); pose(c, 18, CROUCH)
eyes(c, (14, 'round'), (52, 'squint'), (124, 'round'), (132, 'happy'), (146, 'open'))
c.st('brows', (16, 'angry'), (52, 'none'))
c.st('tail', (10, 'back'), (150, 'mid'))
tail(c, 4, WRAP); tail(c, 12, SIDE)
# rear wiggle
for j, t in enumerate(range(20, 44, 4)):
    s = 1 if j % 2 == 0 else -1
    c.k('roll.x', (t, 6 * s, 'sine')); c.k('roll.r', (t, 2.5 * s, 'sine'))
    c.k('hindL.y', (t, -6 if s > 0 else 0, 'sine')); c.k('hindR.y', (t, 0 if s > 0 else -6, 'sine'))
    tail(c, t, (-20 + 14 * s, -30 + 10 * s, -40, -50 - 10 * s), 'sine')
c.k('roll.x', (44, 0)); c.k('roll.r', (44, 0)); c.k('hindL.y', (44, 0)); c.k('hindR.y', (44, 0))
c.k('char.sy', (18, 0.86), (44, 0.86), (50, 0.78, 'snap'), (54, 1.1))
c.k('char.sx', (18, 1.06), (44, 1.06), (50, 1.12, 'snap'), (54, 0.94))
c.k('head.y', (18, 34), (44, 34), (50, 40, 'snap'), (54, 0))
c.k('eyes.y', (18, 4), (54, 0)); c.k('earL.r', (18, 10), (50, 10), (56, -20)); c.k('earR.r', (18, -10), (50, -10), (56, 20))
# leap: high arc, flip nose-first
c.k('char.x', (18, -28), (50, -28, 'io'), (72, 0))
c.k('char.y', (50, 0, 'o'), (61, -170, 'i'), (72, 40))
c.k('roll.r', (52, 0, 'io'), (70, 180))
tail(c, 50, UP); tail(c, 60, (-60, -44, -30, -20)); tail(c, 70, (96, 92, 84, 78))
for leg, s in (('frontL', 1), ('frontR', -1)):
    c.k(leg + '.y', (18, -4), (50, -4), (60, -20), (68, -80), (108, -80), (116, -10), (124, 0))
    c.k(leg + '.r', (50, 0), (60, 20 * s), (108, 20 * s), (118, 0))
c.k('head.y', (54, 0), (66, 0), (70, 20), (108, 20), (114, 0))
c.k('char.sy', (54, 1.1), (62, 1.0), (72, 1.0), (76, 0.9, 'snap'), (80, 1.0), (108, 1.0))
c.k('char.sx', (54, 0.94), (62, 1.0), (72, 1.0), (76, 1.08, 'snap'), (80, 1.0), (108, 1.0))
# snow drift
c.k('tuft.o', (56, 0, 'lin'), (58, 1, 'h'), (140, 1, 'lin'), (150, 0))
c.k('tuft.sy', (56, 0.1, 'pop'), (66, 1.06), (72, 1, 'snap'), (75, 0.92, 'snap'), (80, 1.0), (108, 1, 'snap'), (111, 0.94), (116, 1.04), (124, 1),
    (136, 1, 'i'), (148, 0.1))
c.k('tuft.sx', (56, 0.5, 'pop'), (66, 1.0), (72, 1, 'snap'), (75, 1.05, 'snap'), (80, 1.0), (136, 1, 'i'), (148, 0.6))
for k, (dx, dy) in enumerate([(-50, -40), (-30, -70), (40, -64), (56, -36), (6, -84)]):
    n = 'puff%d' % (k + 1)
    for t0 in (72, 110):
        c.k(n + '.o', (t0, 0, 'lin'), (t0 + 2, 1, 'lin'), (t0 + 12, 1, 'lin'), (t0 + 18, 0))
        c.k(n + '.x', (t0, 0, 'o'), (t0 + 18, dx * (1.2 if t0 > 100 else 1)))
        c.k(n + '.y', (t0, 0, 'o'), (t0 + 10, dy, 'i'), (t0 + 18, dy + 18))
        c.k(n + '.sx', (t0, 0.4, 'o'), (t0 + 18, 1.2)); c.k(n + '.sy', (t0, 0.4, 'o'), (t0 + 18, 1.2))
# stuck: kick
c.k('hindL.r', (76, 0), *[(76 + 4 * j, (-34 if j % 2 else 18), 'sine') for j in range(1, 8)], (108, 0))
c.k('hindR.r', (76, 0), *[(78 + 4 * j, (34 if j % 2 else -18), 'sine') for j in range(1, 7)], (108, 0))
c.k('hindL.y', (66, 0), (74, 40), (104, 40), (112, 0)); c.k('hindR.y', (66, 0), (74, 40), (104, 40), (112, 0))
c.k('hindL.x', (66, 0), (74, -14), (104, -14), (112, 0)); c.k('hindR.x', (66, 0), (74, 14), (104, 14), (112, 0))
tail(c, 74, (96, 92, 84, 78))
for j, t in enumerate(range(78, 106, 5)):
    s = 1 if j % 2 == 0 else -1
    tail(c, t, (90 + 16 * s, 90 + 22 * s, 84 + 26 * s, 78 + 30 * s), 'sine')
tail(c, 106, (96, 92, 84, 78))
# pop out backwards with snow on nose
c.k('char.y', (108, 40, 'o'), (118, -110, 'i'), (128, 0))
c.k('roll.r', (108, 180, 'io'), (124, 0))
c.k('char.sy', (108, 1.0), (128, 1.0, 'snap'), (131, 0.84, 'snap'), (136, 1.04), (142, 1))
c.k('char.sx', (108, 1.0), (128, 1.0, 'snap'), (131, 1.12, 'snap'), (136, 0.98), (142, 1))
tail(c, 112, UP); tail(c, 124, (-40, -30, -30, -40)); tail(c, 136, SIDE); tail(c, 152, WRAP)
c.k('snownose.o', (114, 0, 'lin'), (115, 1, 'h'), (152, 1, 'lin'), (158, 0))
c.k('snownose.y', (152, 0, 'o'), (160, -30))
c.k('snownose.x', (152, 0, 'o'), (160, 24))
c.k('snownose.r', (152, 0), (160, 50))
c.k('head.r', (140, 0, 'sine'), (144, 10, 'sine'), (148, -10, 'sine'), (152, 8, 'sine'), (156, -4), (160, 0))
c.k('shadow.sx', (50, 1), (61, 0.5), (72, 0.9), (108, 0.9), (118, 0.55), (128, 1))
c.k('shadow.o', (50, 1), (61, 0.4), (72, 0, 'h'), (110, 0), (118, 0.4), (128, 1))
c.k('shadow.x', (18, -28), (50, -28), (72, 0))
blink(c, 160, 2)

c = clip('move_fall_land', 'movement', 130, loop=False, note='Ends back in the sitting pose so it chains into idle.', settle=118)
c.k('char.y', (0, -640, 'i'), (16, 0))
c.k('char.sy', (0, 1.12), (16, 1.12, 'snap'), (19, 0.76, 'snap'), (24, 1.05), (30, 1))
c.k('char.sx', (0, 0.92), (16, 0.92, 'snap'), (19, 1.2, 'snap'), (24, 0.97), (30, 1))
for leg, s in (('frontL', 1), ('frontR', -1)):
    c.k(leg + '.r', (0, -24 * s), (14, -24 * s), (19, 16 * s, 'snap'), (26, 0))
    c.k(leg + '.y', (0, -18), (14, -18), (19, 4), (26, 0))
for leg in ('hindL', 'hindR'):
    c.k(leg + '.y', (0, -12), (14, -12), (19, 2), (26, 0))
ears(c, 0, 20, -20); ears(c, 15, 20, -20, 'snap'); ears(c, 19, -40, 40, 'snap'); ears(c, 26, -8, 8); ears(c, 100, -8, 8); ears(c, 110, 0, 0)
eyes(c, (0, 'round'), (17, 'squint'), (24, 'spiral'), (104, 'closed'), (110, 'open'))
c.st('mouth', (0, 'o'), (24, 'frown'), (104, 'smile'))
tail(c, 0, UP); tail(c, 15, UP)
c.st('tail', (0, 'back'), (22, 'top'), (98, 'mid'))
tail(c, 22, (-70, -110, -160, -200)); tail(c, 32, (-74, -160, 170, 120)); tail(c, 40, (-76, -158, 176, 128))
tail(c, 84, (-76, -158, 176, 128)); tail(c, 96, SIDE); tail(c, 110, WRAP)
c.k('head.r', (28, 0, 'sine'), *[(36 + 12 * j, (6 if j % 2 == 0 else -6), 'sine') for j in range(5)], (100, 0, 'snap'),
    (102, -10, 'sine'), (106, 10, 'sine'), (110, -5), (116, 0))
c.k('shadow.sx', (0, 0.2), (16, 1)); c.k('shadow.o', (0, 0), (16, 1))
for k in range(3):
    n = 'dz%d' % (k + 1)
    c.k(n + '.o', (40, 0, 'lin'), (44, 1, 'h'), (96, 1, 'lin'), (102, 0))
    ph = k * 16 / 3.0
    for j in range(7):
        t = 40 + ph + j * 8
        if t > 102:
            break
        c.k(n + '.x', (t, [70, 0, -70, 0][j % 4], 'sine'))
        c.k(n + '.y', (t, [0, 16, 0, -16][j % 4], 'sine'))
    c.k(n + '.sx', (40, 0.9)); c.k(n + '.sy', (40, 0.9))
    c.k(n + '.r', (40, 0, 'lin'), (102, 360))

# ================================================================== INTERACTION
c = clip('int_dragged', 'interaction', 60, note='State loop: held by the scruff for as long as the drag lasts.', autobase=False)
DRAG = {'char.y': -60, 'body.sy': 1.06, 'frontL.y': 10, 'frontR.y': 10, 'frontL.r': -6, 'frontR.r': 6,
        'hindL.y': 14, 'hindR.y': 14, 'hindL.x': 6, 'hindR.x': -6, 'earL.r': -40, 'earR.r': 40, 'earL.sy': 0.9, 'earR.sy': 0.9,
        'eyes.x': 8, 'eyes.y': 2, 'muzzle.x': 4, 'shadow.sx': 0.62, 'shadow.o': 0.5, 'head.y': -4}
pose(c, 0, DRAG); pose(c, 60, DRAG)
c.st('tail', (0, 'top'))
tail_hold(c, 0, 60, HUG)
c.k('swing.r', (0, 0, 'sine'), (15, 6, 'sine'), (45, -6, 'sine'), (60, 0))
c.k('frontL.r', (0, -6, 'sine'), (20, -14, 'sine'), (50, 2, 'sine'), (60, -6))
c.k('frontR.r', (0, 6, 'sine'), (25, 14, 'sine'), (52, -2, 'sine'), (60, 6))
c.k('hindL.r', (0, 0, 'sine'), (18, 8, 'sine'), (48, -6, 'sine'), (60, 0))
c.k('hindR.r', (0, 0, 'sine'), (22, -8, 'sine'), (50, 6, 'sine'), (60, 0))
c.k('shadow.x', (0, 0, 'sine'), (15, 6, 'sine'), (45, -6, 'sine'), (60, 0))
eyes(c, (0, 'happy'))
c.st('mouth', (0, 'smile'))
c.st('brows', (0, 'sad'))
c.k('sweat.o', (0, 1), (60, 1))
c.k('sweat.y', (0, 0, 'sine'), (30, 6, 'sine'), (60, 0))

c = clip('int_petted', 'interaction', 100)
ears(c, 2, 0, 0); ears(c, 12, -48, 48); ears(c, 84, -48, 48); ears(c, 96, 0, 0)
for e in ('earL', 'earR'):
    c.k(e + '.sy', (2, 1), (12, 0.85), (84, 0.85), (96, 1))
eyes(c, (8, 'happy'), (90, 'open'))
c.st('mouth', (10, 'open'), (88, 'smile'))
c.k('cheeks.sx', (6, 1), (14, 1.3), (84, 1.3), (94, 1)); c.k('cheeks.sy', (6, 1), (14, 1.25), (84, 1.25), (94, 1))
c.k('head.y', (2, 0), (12, -6), (84, -6), (94, 0))
c.k('head.r', (12, 0, 'sine'), (24, 5, 'sine'), (38, -5, 'sine'), (52, 5, 'sine'), (66, -5, 'sine'), (80, 0))
c.st('tail', (10, 'back'), (92, 'mid'))
tail(c, 2, WRAP); tail(c, 10, SIDE); tail(c, 16, UPCURL)
for j, t in enumerate(range(20, 82, 5)):
    s = 1 if j % 2 == 0 else -1
    tail(c, t, (UPCURL[0] + 26 * s, UPCURL[1] + 30 * s, UPCURL[2] + 30 * s, UPCURL[3] + 26 * s), 'sine')
tail(c, 84, UPCURL); tail(c, 90, SIDE); tail(c, 98, WRAP)
for k, (t0, dx) in enumerate(((18, -10), (36, 12), (54, -6))):
    appear(c, 'heart%d' % (k + 1), t0, t0 + 32, rise=40, drift=dx)
breathe(c, 0, 100, 1, 0.012)

c = clip('int_poked', 'interaction', 84)
c.k('char.sy', (0, 1, 'snap'), (3, 0.9, 'snap'), (8, 1.04), (13, 1))
c.k('char.sx', (0, 1, 'snap'), (3, 1.08, 'snap'), (8, 0.98), (13, 1))
c.k('head.x', (0, 0, 'snap'), (3, 8, 'snap'), (10, 4), (70, 4), (80, 0))
c.k('head.r', (0, 0, 'snap'), (3, 6), (10, 6), (70, 6), (80, 0))
eyes(c, (2, 'squint'), (8, 'half'), (72, 'open'))
c.st('puff', (8, 'yes'), (70, 'no'))
c.st('mouth', (8, 'pout'), (70, 'smile'))
c.st('brows', (8, 'angry'), (72, 'none'))
c.k('eyes.x', (6, 0), (12, -6), (70, -6), (78, 0))
ears(c, 0, 0, 0, 'snap'); ears(c, 5, -36, 36); ears(c, 70, -36, 36); ears(c, 80, 0, 0)
c.k('puff.sx', (8, 0.6, 'pop'), (14, 1.1), (18, 1), (40, 1, 'sine'), (46, 1.08, 'sine'), (52, 1))
c.k('puff.sy', (8, 0.6, 'pop'), (14, 1.1), (18, 1), (40, 1, 'sine'), (46, 1.08, 'sine'), (52, 1))
# tail flick
r0 = rel(WRAP)
c.k('tail1.r', (10, r0[0], 'snap'), (14, r0[0] - 34, 'snap'), (20, r0[0] + 6), (26, r0[0]))
c.k('tail4.r', (10, r0[3], 'snap'), (14, r0[3] - 30, 'snap'), (20, r0[3] + 10), (26, r0[3]))
appear(c, 'anger', 10, 70, scale=1.0)
c.k('anger.sx', (18, 1, 'sine'), (24, 1.15, 'sine'), (30, 1, 'sine'), (36, 1.15, 'sine'), (42, 1, 'sine'), (48, 1.15, 'sine'), (54, 1))
c.k('anger.sy', (18, 1, 'sine'), (24, 1.15, 'sine'), (30, 1, 'sine'), (36, 1.15, 'sine'), (42, 1, 'sine'), (48, 1.15, 'sine'), (54, 1))

c = clip('int_tickled', 'interaction', 130)
LIE = {'roll.r': -100, 'char.y': -20, 'char.x': 30, 'shadow.sx': 1.3, 'head.r': 10}
pose(c, 4, {k: (1 if k.endswith('.sx') else 0) for k in LIE}); pose(c, 20, LIE); pose(c, 106, LIE)
pose(c, 122, {k: (1 if k.endswith('.sx') else 0) for k in LIE})
c.k('roll.r', (20, -100, 'sine'), (32, -92, 'sine'), (44, -108, 'sine'), (56, -92, 'sine'), (68, -108, 'sine'), (80, -92, 'sine'), (92, -108, 'sine'), (106, -100))
eyes(c, (4, 'squint'), (112, 'happy'), (124, 'open'))
c.st('mouth', (6, 'open'), (118, 'smile'))
c.st('tail', (10, 'back'), (114, 'mid'))
tail(c, 4, WRAP); tail(c, 12, SIDE)
for j, t in enumerate(range(18, 106, 6)):
    s = 1 if j % 2 == 0 else -1
    tail(c, t, (SIDE[0] + 18 * s, SIDE[1] + 26 * s, SIDE[2] + 30 * s, SIDE[3] + 30 * s), 'sine')
tail(c, 108, SIDE); tail(c, 122, WRAP)
for leg, ph, amp in (('frontL', 0, 40), ('frontR', 3, -40), ('hindL', 2, 34), ('hindR', 5, -34)):
    ks = [(14, 0)]
    for j, t in enumerate(range(20 + ph, 102, 6)):
        ks.append((t, amp if j % 2 == 0 else amp * 0.1, 'sine'))
    ks.append((108, 0))
    c.k(leg + '.r', *ks)
    c.k(leg + '.y', (14, 0), (20, -12), (102, -12), (110, 0))
ears(c, 10, 0, 0); ears(c, 20, -30, 30); ears(c, 104, -30, 30); ears(c, 116, 0, 0)
for k, (t0, n) in enumerate(((26, 'spark1'), (50, 'spark2'), (74, 'spark3'))):
    appear(c, n, t0, t0 + 22, rise=10, scale=0.8)

LOOKS = {'up': (0, -1), 'up_right': (0.75, -0.75), 'right': (1, 0), 'down_right': (0.75, 0.75), 'down': (0, 1),
         'down_left': (-0.75, 0.75), 'left': (-1, 0), 'up_left': (-0.75, -0.75)}
for nm, (dx, dy) in LOOKS.items():
    c = clip('int_look_' + nm, 'interaction', 60, note='Held pose for cursor following (loops in place).', autobase=False)
    look(c, 0, dx, dy); look(c, 60, dx, dy)
    ears(c, 0, 12 * dx - 6 * max(dy, 0), 12 * dx + 6 * max(dy, 0)); ears(c, 60, 12 * dx - 6 * max(dy, 0), 12 * dx + 6 * max(dy, 0))
    breathe(c, 0, 60, 1, 0.012)
    c.k('head.y', (0, 5 * dy, 'sine'), (30, 5 * dy - 1.5, 'sine'), (60, 5 * dy))
    blink(c, 38)

# ================================================================== MOODS
c = clip('mood_happy', 'mood', 96)
eyes(c, (4, 'happy'), (88, 'open'))
c.st('mouth', (4, 'open'), (88, 'smile'))
c.st('tail', (8, 'back'), (88, 'mid'))
tail(c, 2, WRAP); tail(c, 8, SIDE); tail(c, 14, UPCURL)
for j, t in enumerate(range(16, 80, 4)):
    s = 1 if j % 2 == 0 else -1
    tail(c, t, (UPCURL[0] + 30 * s, UPCURL[1] + 34 * s, UPCURL[2] + 30 * s, UPCURL[3] + 24 * s), 'sine')
    c.k('roll.r', (t, 3 * s, 'sine')); c.k('roll.x', (t, 5 * s, 'sine'))
    c.k('hindL.y', (t, -5 if s > 0 else 0, 'sine')); c.k('hindR.y', (t, 0 if s > 0 else -5, 'sine'))
    c.k('char.y', (t, -6 if j % 2 == 0 else 0, 'sine'))
c.k('roll.r', (80, 0)); c.k('roll.x', (80, 0)); c.k('hindL.y', (80, 0)); c.k('hindR.y', (80, 0)); c.k('char.y', (80, 0))
tail(c, 82, UPCURL); tail(c, 88, SIDE); tail(c, 94, WRAP)
ears(c, 4, 0, 0); ears(c, 10, 8, -8); ears(c, 80, 8, -8); ears(c, 90, 0, 0)
for k, (t0, n) in enumerate(((10, 'spark1'), (24, 'spark2'), (40, 'spark3'), (54, 'spark4'))):
    appear(c, n, t0, t0 + 26, rise=8)
    c.k(n + '.r', (t0, 0, 'lin'), (t0 + 26, 45))
c.k('cheeks.sx', (4, 1), (10, 1.2), (84, 1.2), (90, 1)); c.k('cheeks.sy', (4, 1), (10, 1.2), (84, 1.2), (90, 1))

c = clip('mood_sad', 'mood', 120)
ears(c, 2, 0, 0); ears(c, 16, -62, 62); ears(c, 100, -62, 62); ears(c, 114, 0, 0)
for e in ('earL', 'earR'):
    c.k(e + '.sy', (2, 1), (16, 0.84), (100, 0.84), (114, 1))
c.st('brows', (8, 'sad'), (106, 'none'))
c.st('mouth', (10, 'frown'), (104, 'smile'))
c.k('head.y', (2, 0), (18, 14), (100, 14), (114, 0))
c.k('head.r', (2, 0), (18, -5), (100, -5), (114, 0))
c.k('eyes.y', (6, 0), (18, 5), (100, 5), (110, 0))
c.k('eyes.x', (6, 0), (18, -4), (100, -4), (110, 0))
c.st('tail', (12, 'top'), (104, 'mid'))
tail(c, 4, WRAP); tail(c, 12, SIDE); tail(c, 28, HIDE); tail(c, 96, HIDE); tail(c, 104, SIDE); tail(c, 116, WRAP)
c.k('tail4.r', (40, rel(HIDE)[3], 'sine'), (60, rel(HIDE)[3] - 10, 'sine'), (80, rel(HIDE)[3]))
c.k('char.sy', (2, 1), (18, 0.96), (100, 0.96), (114, 1))
for t0 in (30, 64):
    c.k('tear.o', (t0, 0, 'lin'), (t0 + 4, 1, 'lin'), (t0 + 24, 1, 'lin'), (t0 + 30, 0))
    c.k('tear.y', (t0, 0, 'i'), (t0 + 30, 28))
    c.k('tear.sy', (t0, 0.5, 'o'), (t0 + 8, 1.0), (t0 + 30, 1.1))
    c.k('tear.sx', (t0, 0.5, 'o'), (t0 + 8, 1.0), (t0 + 30, 0.9))
blink(c, 54)

c = clip('mood_surprised', 'mood', 76)
c.k('char.y', (2, 0, 'snap'), (6, -26, 'o'), (14, 0, 'snap'), (17, 0))
c.k('char.sy', (2, 1, 'snap'), (6, 1.1, 'o'), (14, 0.9, 'snap'), (18, 1.04), (58, 1.04), (68, 1))
c.k('char.sx', (2, 1, 'snap'), (6, 0.94, 'o'), (14, 1.1, 'snap'), (18, 1.04), (58, 1.04), (68, 1))
c.st('fur', (5, 'spiky'), (58, 'smooth'))
eyes(c, (4, 'round'), (58, 'open'))
c.st('mouth', (4, 'o'), (60, 'smile'))
c.st('tail', (6, 'back'), (62, 'mid'))
tail(c, 2, WRAP, 'snap'); tail(c, 6, SIDE, 'snap'); tail(c, 10, UP); tail(c, 54, UP); tail(c, 62, SIDE); tail(c, 72, WRAP)
for p, v in (('tail1.sx', 1.0), ('tail1.sy', 1.18)):
    c.k(p, (6, 1, 'pop'), (12, v * 1.05), (16, v), (54, v), (62, 1))
ears(c, 2, 0, 0, 'snap'); ears(c, 6, 10, -10, 'snap'); ears(c, 10, 4, -4); ears(c, 56, 4, -4); ears(c, 64, 0, 0)
for e in ('earL', 'earR'):
    c.k(e + '.sy', (2, 1, 'snap'), (6, 1.12), (56, 1.1), (64, 1))
appear(c, 'emark', 6, 56)
c.k('emark.r', (6, 16, 'snap'), (12, -8, 'snap'), (18, 0))
c.k('shadow.sx', (2, 1), (6, 0.8), (14, 1))

c = clip('mood_hungry', 'mood', 130)
c.k('frontR.y', (6, 0), (18, -40), (100, -40), (114, 0))
c.k('frontR.r', (6, 0), (18, 20), *[(24 + 8 * j, (34 if j % 2 == 0 else 14), 'sine') for j in range(10)], (104, 20), (114, 0))
c.k('frontR.x', (6, 0), (18, -6), *[(28 + 8 * j, (-14 if j % 2 == 0 else -2), 'sine') for j in range(9)], (104, -6), (114, 0))
c.k('body.sx', (20, 1, 'sine'), (40, 1.04, 'sine'), (60, 1, 'sine'), (80, 1.04, 'sine'), (100, 1))
appear(c, 'thought', 22, 112, scale=1.0, fade=8)
c.k('thought.y', (34, 0, 'sine'), (56, -6, 'sine'), (78, 0, 'sine'), (100, -6))
look(c, 16, 0.6, -0.6); look(c, 104, 0.6, -0.6); look(c, 116, 0, 0)
c.st('mouth', (24, 'o'), (44, 'lick'), (74, 'smile'), (84, 'lick'), (100, 'smile'))
c.st('brows', (12, 'sad'), (110, 'none'))
ears(c, 12, 0, 0); ears(c, 22, -16, 16); ears(c, 104, -16, 16); ears(c, 114, 0, 0)
blink(c, 64)

c = clip('mood_love', 'mood', 136)
c.k('char.x', (4, 0), (20, -40), (116, -40), (130, 0))
c.k('shadow.x', (4, 0), (20, -40), (116, -40), (130, 0))
eyes(c, (8, 'heart'), (122, 'open'))
c.k('eyes.sx', (8, 0.6, 'pop'), (14, 1.2), (18, 1), *[(26 + 10 * j, (1.12 if j % 2 == 0 else 1.0), 'sine') for j in range(9)], (116, 1))
c.k('eyes.sy', (8, 0.6, 'pop'), (14, 1.2), (18, 1), *[(26 + 10 * j, (1.12 if j % 2 == 0 else 1.0), 'sine') for j in range(9)], (116, 1))
c.st('mouth', (8, 'open'), (122, 'smile'))
c.k('cheeks.sx', (6, 1), (14, 1.4), (116, 1.4), (124, 1)); c.k('cheeks.sy', (6, 1), (14, 1.3), (116, 1.3), (124, 1))
c.st('tail', (10, 'back'), (24, 'heart'), (108, 'back'), (124, 'mid'))
tail(c, 4, WRAP); tail(c, 12, SIDE); tail(c, 22, (-30, -50, -80, -110)); tail(c, 108, (-30, -50, -80, -110)); tail(c, 116, SIDE); tail(c, 128, WRAP)
c.k('tailH.sx', (24, 0.5, 'pop'), (32, 1.08), (38, 1), (106, 1)); c.k('tailH.sy', (24, 0.5, 'pop'), (32, 1.08), (38, 1), (106, 1))
c.k('roll.r', (20, 0, 'sine'), *[(32 + 14 * j, (3 if j % 2 == 0 else -3), 'sine') for j in range(6)], (110, 0))
c.k('head.r', (20, 0, 'sine'), *[(32 + 14 * j, (5 if j % 2 == 0 else -5), 'sine') for j in range(6)], (110, 0))
for k, (t0, dx) in enumerate(((20, -6), (40, 10), (60, -8), (80, 8))):
    appear(c, 'heart%d' % (k + 1), t0, t0 + 34, rise=46, drift=dx)
ears(c, 6, 0, 0); ears(c, 16, -14, 14); ears(c, 116, -14, 14); ears(c, 126, 0, 0)

c = clip('mood_mischief', 'mood', 110)
eyes(c, (8, 'half'), (100, 'open'))
c.st('mouth', (10, 'smirk'), (100, 'smile'))
c.k('head.r', (4, 0), (16, -6), (94, -6), (104, 0))
c.k('eyes.x', (6, 0), (16, 6), (94, 6), (102, 0))
c.k('muzzle.x', (6, 0), (16, 3), (94, 3), (102, 0))
for leg, s in (('frontL', 1), ('frontR', -1)):
    c.k(leg + '.y', (6, 0), (18, -40), (90, -40), (102, 0))
    c.k(leg + '.r', (6, 0), (18, -26 * s), (90, -26 * s), (102, 0))
for j, t in enumerate(range(22, 88, 6)):
    s = 1 if j % 2 == 0 else -1
    c.k('frontL.y', (t, -40 + 6 * s, 'sine')); c.k('frontR.y', (t, -40 - 6 * s, 'sine'))
c.k('frontL.y', (90, -40)); c.k('frontR.y', (90, -40))
ears(c, 6, 0, 0); ears(c, 16, -14, 6); ears(c, 94, -14, 6); ears(c, 104, 0, 0)
appear(c, 'spark2', 30, 62, scale=0.65)
c.k('spark2.r', (30, 0, 'lin'), (62, 90))
c.k('tail4.r', (20, rel(WRAP)[3], 'snap'), (24, rel(WRAP)[3] - 26, 'snap'), (30, rel(WRAP)[3] + 6), (36, rel(WRAP)[3]),
    (64, rel(WRAP)[3], 'snap'), (68, rel(WRAP)[3] - 26, 'snap'), (74, rel(WRAP)[3] + 6), (80, rel(WRAP)[3]))

c = clip('mood_smile_wink', 'mood', 80)
c.st('mouth', (6, 'open'), (68, 'smile'))
c.st('eyeR', (12, 'wink'), (62, 'open'))
c.k('head.r', (4, 0), (14, 7), (60, 7), (70, 0))
c.k('head.x', (4, 0), (14, 4), (60, 4), (70, 0))
c.k('char.y', (4, 0, 'o'), (10, -10, 'i'), (16, 0))
c.k('char.sy', (4, 1), (10, 1.04), (16, 0.96, 'snap'), (20, 1))
appear(c, 'spark2', 14, 46, scale=0.8)
c.k('spark2.r', (14, 0, 'lin'), (46, 90))
c.k('spark2.x', (14, -10)); c.k('spark2.y', (14, 40))
c.k('cheeks.sx', (8, 1), (14, 1.2), (60, 1.2), (68, 1)); c.k('cheeks.sy', (8, 1), (14, 1.2), (60, 1.2), (68, 1))
ears(c, 6, 0, 0); ears(c, 14, 4, 12); ears(c, 60, 4, 12); ears(c, 70, 0, 0)

# ================================================================== FUN
c = clip('fun_spin', 'fun', 140)
look(c, 4, 0.9, 0.4); look(c, 14, 0.9, 0.4)
c.st('tail', (8, 'back'), (124, 'mid'))
tail(c, 4, WRAP); tail(c, 12, SIDE)
c.k('char.sx', (16, 1, 'io'), (34, -1, 'io'), (52, 1, 'io'))
c.k('char.x', (16, 0, 'sine'), (25, 22, 'sine'), (34, 0, 'sine'), (43, -22, 'sine'), (52, 0))
c.k('char.y', (16, 0, 'o'), (21, -18, 'i'), (26, 0, 'o'), (31, -18, 'i'), (36, 0, 'o'), (41, -18, 'i'), (46, 0, 'o'), (50, -10, 'i'), (54, 0))
tail(c, 16, SIDE); tail(c, 34, (-30, -50, -70, -90)); tail(c, 52, SIDE)
look(c, 54, 0, 0)
eyes(c, (16, 'squint'), (56, 'spiral'), (120, 'closed'), (126, 'open'))
c.st('mouth', (16, 'open'), (56, 'o'), (120, 'smile'))
c.k('char.sy', (54, 1), (58, 0.88, 'snap'), (64, 1.02), (70, 1))
c.k('char.sx', (54, 1), (58, 1.1, 'snap'), (64, 0.99), (70, 1))
c.k('roll.r', (58, 0, 'sine'), *[(66 + 12 * j, (5 if j % 2 == 0 else -5), 'sine') for j in range(5)], (124, 0))
c.k('head.r', (58, 0, 'sine'), *[(64 + 12 * j, (-8 if j % 2 == 0 else 8), 'sine') for j in range(5)], (120, 0, 'snap'), (123, -8), (128, 6), (134, 0))
tail(c, 60, SIDE); tail(c, 70, WRAP); tail(c, 132, WRAP)
c.st('tail', (64, 'mid'))
for k in range(3):
    n = 'dz%d' % (k + 1)
    c.k(n + '.o', (60, 0, 'lin'), (64, 1, 'h'), (114, 1, 'lin'), (120, 0))
    ph = k * 16 / 3.0
    for j in range(8):
        t = 60 + ph + j * 8
        if t > 120:
            break
        c.k(n + '.x', (t, [70, 0, -70, 0][j % 4], 'sine'))
        c.k(n + '.y', (t, [0, 16, 0, -16][j % 4], 'sine'))
    c.k(n + '.sx', (60, 0.9)); c.k(n + '.sy', (60, 0.9))
    c.k(n + '.r', (60, 0, 'lin'), (120, 300))
ears(c, 54, 0, 0); ears(c, 60, -30, 30, 'snap'); ears(c, 66, -20, 20); ears(c, 118, -20, 20); ears(c, 128, 0, 0)

c = clip('fun_peek', 'fun', 110, note='Starts and ends hidden below the bottom edge.', autobase=False)
c.k('char.y', (0, 500), (6, 500, 'o'), (22, 300, 'io'), (34, 300, 'o'), (48, 200), (82, 200, 'i'), (98, 500), (110, 500))
c.k('shadow.o', (0, 0), (110, 0))
c.k('earL.r', (0, 0), (22, 0, 'snap'), (25, -14, 'snap'), (29, 4), (33, 0), (110, 0))
c.k('earR.r', (0, 0), (26, 0, 'snap'), (29, 14, 'snap'), (33, -4), (37, 0), (110, 0))
look(c, 0, 0, 0); look(c, 48, 0, 0); look(c, 54, -0.8, -0.3); look(c, 62, -0.8, -0.3); look(c, 68, 0.8, -0.3); look(c, 74, 0.8, -0.3)
look(c, 80, 0, 0); look(c, 110, 0, 0)
blink(c, 56)
c.st('mouth', (0, 'o'), (64, 'smile'), (84, 'o'))
eyes(c, (0, 'open'), (86, 'squint'))

c = clip('fun_notify', 'fun', 100)
appear(c, 'badge', 4, 92, scale=1.0, fade=8)
c.k('badge.y', (14, 0, 'sine'), (34, -8, 'sine'), (54, 0, 'sine'), (74, -8, 'sine'), (92, 0))
c.k('badge.r', (4, -20, 'snap'), (12, 10, 'snap'), (18, -4), (22, 0))
c.st('mouth', (6, 'open'), (90, 'smile'))
eyes(c, (6, 'happy'), (16, 'open'), (90, 'open'))
look(c, 8, 0, -0.6); look(c, 86, 0, -0.6); look(c, 94, 0, 0)
ears(c, 4, 0, 0, 'snap'); ears(c, 8, 8, -8); ears(c, 86, 8, -8); ears(c, 94, 0, 0)
c.st('tail', (8, 'back'), (92, 'mid'))
tail(c, 2, WRAP); tail(c, 8, SIDE); tail(c, 16, FLAG)
for j, t in enumerate(range(20, 82, 6)):
    s = 1 if j % 2 == 0 else -1
    tail(c, t, (FLAG[0] + 14 * s, FLAG[1] - 20 * s, FLAG[2] + 28 * s, FLAG[3] - 34 * s), 'sine')
tail(c, 84, FLAG); tail(c, 92, SIDE); tail(c, 98, WRAP)
c.k('char.y', (6, 0, 'o'), (10, -10, 'i'), (14, 0))
breathe(c, 14, 86, 2, 0.015)

c = clip('fun_leaf_catch', 'fun', 160)
# leaf path (home centre 256,300). drifts down from the top, zig-zagging
LX = [(0, -40), (14, 30), (28, -30), (40, 70), (46, 76), (52, 104), (58, 64), (66, 76), (72, 108), (80, 62), (88, 32)]
LY = [(0, -420), (14, -320), (28, -220), (40, -60), (46, 20), (52, -56), (58, -10), (66, 20), (72, -64), (80, -40), (88, -10)]
LR = [(0, -30), (14, 30), (28, -20), (40, 30), (46, 20), (52, 140), (58, 40), (66, 30), (72, 170), (80, 60), (88, 14)]
c.k('leaf.x', *[(t, v, 'sine') for t, v in LX])
c.k('leaf.y', *[(t, v, 'sine') for t, v in LY])
c.k('leaf.r', *[(t, v, 'sine') for t, v in LR])
c.k('leaf.o', (0, 0, 'lin'), (4, 1, 'h'), (88, 1, 'h'), (89, 0))
for t, v in LX[1:9]:
    pass
c.k('eyes.x', (4, 0), (14, 6), (28, -4), (40, 8), (88, 4), (96, 0))
c.k('eyes.y', (4, 0), (14, -8), (40, -8), (50, -6), (88, 0))
c.k('muzzle.x', (40, 0), (50, 6), (88, 6), (96, 0))
c.k('head.r', (4, 0), (20, -6), (40, 6), (50, 6), (80, 4), (90, 0))
# two bats with the right paw
for t0 in (46, 66):
    c.k('frontR.r', (t0 - 6, 0, 'io'), (t0 - 1, -120, 'snap'), (t0 + 2, -150, 'snap'), (t0 + 8, -40), (t0 + 13, 0))
    c.k('frontR.y', (t0 - 6, 0), (t0 - 1, -20), (t0 + 8, -10), (t0 + 13, 0))
c.k('char.y', (40, 0), (46, -10), (52, 0), (66, -10), (72, 0))
c.st('mouth', (30, 'o'), (84, 'open'), (90, 'hold'))
# catch!
c.k('head.y', (82, 0, 'snap'), (88, -14, 'snap'), (92, 2), (96, 0))
c.k('leafm.o', (89, 0, 'lin'), (90, 1, 'h'), (134, 1, 'lin'), (146, 0))
c.k('leafm.y', (134, 0, 'i'), (146, 96))
c.k('leafm.r', (134, 0, 'i'), (146, 70))
c.st('mouth', (134, 'o'), (142, 'smile'))
eyes(c, (96, 'happy'), (136, 'open'))
c.k('head.r', (96, 0), (104, -8), (128, -8), (136, 0))
c.k('char.sy', (96, 1), (104, 1.05), (128, 1.05), (136, 1))
c.k('body.sx', (96, 1), (104, 1.05), (128, 1.05), (136, 1))
appear(c, 'spark1', 100, 128, scale=0.8); appear(c, 'spark2', 106, 132, scale=0.7)
ears(c, 4, 0, 0); ears(c, 14, 8, -8); ears(c, 88, 8, -8, 'snap'); ears(c, 92, -10, 10); ears(c, 100, 4, -4); ears(c, 136, 0, 0)
c.st('tail', (94, 'back'), (134, 'mid'))
tail(c, 88, WRAP); tail(c, 96, SIDE); tail(c, 102, UPCURL)
for j, t in enumerate(range(106, 126, 5)):
    s = 1 if j % 2 == 0 else -1
    tail(c, t, (UPCURL[0] + 20 * s, UPCURL[1] + 24 * s, UPCURL[2] + 20 * s, UPCURL[3] + 16 * s), 'sine')
tail(c, 128, UPCURL); tail(c, 134, SIDE); tail(c, 146, WRAP)


# ---------------------------------------------------------------- post-pass: route SIDE<->WRAP through MID so the tail
# never swings below the ground line
for _c in CLIPS:
    tp = sorted(_c.__dict__.get('_tp', []), key=lambda x: x[0])
    for (t1, a, e1), (t2, b, e2) in zip(tp, tp[1:]):
        if {a, b} == {SIDE, WRAP} and t2 - t1 >= 4:
            # foreshorten while the tail swings toward the viewer
            _c.k('tail2.sx', (t1, 1, 'io'), ((t1 + t2) / 2.0, 0.3, 'io'), (t2, 1))
            _c.k('tail1.sx', (t1, 1, 'io'), ((t1 + t2) / 2.0, 0.75, 'io'), (t2, 1))
