"""All animated clips. Every clip is authored once against the rig; both exporters read the same tracks."""
import math
from core import *
from rig import *

# ------------------------------------------------------------ helpers
def new(name, cat, N, loop=True, holds=False, note=''):
    c = Clip(name, cat, N, loop, build_rig(), holds, note)
    c._z = 5000
    return c

def M(*ds):
    out = {}
    for d in ds:
        out.update(d)
    return out

def cyc(f0, f1, n, a, b, e='sin'):
    """a -> b -> a, n times between f0 and f1"""
    h = (f1 - f0) / n
    ks = []
    for k in range(n):
        ks += [(f0 + h * k, a, e), (f0 + h * (k + 0.5), b, e)]
    ks.append((f1, a, e))
    return ks

def wave(f0, f1, n, amp, base=0.0, e='sin'):
    """base -> +amp -> -amp ... -> base with n peaks"""
    h = (f1 - f0) / n
    if isinstance(amp, tuple) and not isinstance(base, tuple):
        base = tuple(base for _ in amp)
    ks = [(f0, base, e)]
    for k in range(n):
        sgn = 1 if k % 2 == 0 else -1
        ks.append((f0 + h * (k + 0.5), vadd(base, vmul(amp, sgn)), e))
    ks.append((f1, base, e))
    return ks

def spring(f0, target, kick, n=4, period=8, decay=0.5, e='sin'):
    ks = []
    for i in range(n):
        ks.append((f0 + (i + 1) * period / 2, vadd(target, vmul(kick, (-decay) ** i)), e))
    ks.append((f0 + (n + 1) * period / 2, target, e))
    return ks

def cat(*lists):
    out = []
    for l in lists:
        out += l
    return out

def blink(f, s=(1, 1)):
    return [(f, s, 'lin'), (f + 3, (s[0], s[1] * 0.08), 'in'), (f + 7, s, 'out')]

def jitter(f0, f1, amp, step=2):
    ks, i = [(f0, (0, 0), 'lin')], 0
    f = f0 + step
    while f < f1 - step / 2:
        ks.append((f, (amp if i % 2 == 0 else -amp, 0), 'lin')); i += 1; f += step
    ks.append((f1, (0, 0), 'lin'))
    return ks

def look(dx, dy):
    return {'face.p': (20 * dx, 14 * dy), 'patch.p': (10 * dx, 7 * dy),
            'eyeL.p': (7 * dx, 5 * dy), 'eyeR.p': (7 * dx, 5 * dy),
            'tuft.r': -6 * dx, 'head.r': 4 * dx, 'head.p': (3 * dx, 4 * dy)}

def z(c):
    c._z += 10
    return c._z

def fx(c, name, shapes, x, y, parent=None, scale=1.0, op=0.0, zz=None):
    lay = Layer(name, parent, (0, 0), pos=(x, y), shapes=shapes, op=op,
                scale=(scale, scale), z=zz if zz is not None else z(c))
    return c.add(lay)

def pop(c, name, shapes, x, y, f0, f1, rise=(0, -30), s=1.0, spin=0.0, e='out'):
    fx(c, name, shapes, x, y)
    c.k(name, 'o', [(f0, 0, 'lin'), (f0 + 3, 1, 'lin'), (f1 - 7, 1, 'lin'), (f1, 0, 'lin')])
    c.k(name, 's', [(f0, s * 0.15, 'lin'), (f0 + 6, s * 1.2, 'outq'), (f0 + 10, s, 'sin'), (f1, s * 0.85, 'lin')])
    c.k(name, 'p', [(f0, (0, 0)), (f1, rise, e)])
    if spin:
        c.k(name, 'r', [(f0, 0), (f1, spin, 'lin')])

def twinkle(c, name, x, y, times, s=1.0, col=SPARK, size=15):
    """sparkle that flashes at each start frame in `times` (10 frames each)"""
    fx(c, name, e_sparkle(size, col), x, y)
    sk, ok, rk = [], [], []
    for t in times:
        sk += [(t, 0.1, 'lin'), (t + 5, s * 1.15, 'outq'), (t + 10, 0.1, 'in')]
        ok += [(t, 0, 'lin'), (t + 1, 1, 'lin'), (t + 9, 1, 'lin'), (t + 10, 0, 'lin')]
        rk += [(t, 0, 'lin'), (t + 10, 45, 'lin')]
    c.k(name, 's', sk); c.k(name, 'o', ok); c.k(name, 'r', rk)

def wrap(keys, N):
    """keys: unwrapped piecewise-linear (f, v) that may run past N; folds to [0,N] for a seamless loop."""
    k0, k1 = keys[0][0], keys[-1][0]
    bps = sorted(set([0.0, float(N)] + [round(f % N, 6) for f, _ in keys]))
    out = []
    for t in bps:
        val = None
        for m in (0, 1, -1):
            tt = t + m * N
            if k0 - 1e-6 <= tt <= k1 + 1e-6:
                val = sample([(f, v, 'lin') for f, v in keys], tt)
                break
        out.append((t, val))
    for i, (t, v) in enumerate(out):  # fill hidden gaps with neighbour values
        if v is None:
            out[i] = (t, next((vv for _, vv in out[i + 1:] if vv is not None), keys[0][1]))
    # a breakpoint at N that falls exactly on a particle boundary may read the end; force seam equality
    if out[0][1] != out[-1][1]:
        out[-1] = (out[-1][0], out[0][1])
    return [(t, v, 'lin') for t, v in out]

def particle(c, name, shapes, x, y, f0, life, d, N=None, s0=1.0, s1=1.0, spin=0.0, sway=0.0, fade=6, scale=1.0):
    """linear-moving particle from (x,y) by d over life frames; if N given it wraps for seamless loops."""
    fx(c, name, shapes, x, y, scale=scale)
    pk = [(f0, (0.0, 0.0))]
    if sway:
        for i in range(1, 4):
            t = i / 4
            pk.append((f0 + life * t, (d[0] * t + sway * (1 if i % 2 else -1), d[1] * t)))
    pk.append((f0 + life, d))
    ok = [(f0, 0.0), (f0 + fade, 1.0), (f0 + life - fade, 1.0), (f0 + life, 0.0)]
    sk = [(f0, (s0 * scale, s0 * scale)), (f0 + life, (s1 * scale, s1 * scale))]
    rk = [(f0, 0.0), (f0 + life, spin)]
    if N is not None and f0 + life > N:
        c.k(name, 'p', wrap(pk, N)); c.k(name, 'o', wrap(ok, N)); c.k(name, 's', wrap(sk, N))
        if spin:
            c.k(name, 'r', wrap(rk, N))
    else:
        c.k(name, 'p', [(f, v, 'lin') for f, v in pk])
        c.k(name, 'o', [(f, v, 'lin') for f, v in ok])
        c.k(name, 's', [(f, v, 'lin') for f, v in sk])
        if spin:
            c.k(name, 'r', [(f, v, 'lin') for f, v in rk])

def orbit(c, name, cx, cy, rx, ry, f0, f1, period, phase, size=10):
    """dizzy star circling an ellipse; scale larger at the front of the orbit."""
    fx(c, name, e_star(size), cx, cy)
    pk, sk = [], []
    steps = int(round((f1 - f0) / period * 12))
    for i in range(steps + 1):
        f = f0 + (f1 - f0) * i / steps
        a = phase + 2 * math.pi * (f - f0) / period
        pk.append((f, (rx * math.cos(a), ry * math.sin(a)), 'lin'))
        sc = 0.8 + 0.25 * math.sin(a)
        sk.append((f, (sc, sc), 'lin'))
    c.k(name, 'p', pk); c.k(name, 's', sk)
    c.k(name, 'o', [(f0, 0, 'lin'), (f0 + 4, 1, 'lin'), (f1, 1, 'lin')])
    c.k(name, 'r', [(f0, 0, 'lin'), (f1, 360 * (f1 - f0) / period, 'lin')])

def eyes(c, default='open', segs=()):
    c.swap(EYES_L, 'eyeL_' + default, [(f, 'eyeL_' + n if n else None) for f, n in segs])
    c.swap(EYES_R, 'eyeR_' + default, [(f, 'eyeR_' + n if n else None) for f, n in segs])

def eyes2(c, segsL, segsR):
    c.swap(EYES_L, 'eyeL_open', [(f, 'eyeL_' + n if n else None) for f, n in segsL])
    c.swap(EYES_R, 'eyeR_open', [(f, 'eyeR_' + n if n else None) for f, n in segsR])

def beak(c, segs, default='smile'):
    c.swap(BEAKS, 'beak_' + default, [(f, 'beak_' + n if n else None) for f, n in segs])

def brows(c, kind, f0, f1):
    for s in 'LR':
        c.show(f'brow{s}_{kind}', [(0, 0), (f0, 1)] + ([(f1, 0)] if f1 < c.N else []))

def cheeks(c, kind, f0, f1):
    for s in 'LR':
        c.swap([f'cheek{s}_pink', f'cheek{s}_cold', f'cheek{s}_blush'], f'cheek{s}_pink',
               [(f0, f'cheek{s}_{kind}'), (f1, f'cheek{s}_pink')])

def front_flippers(c, f0, f1, sides='LR'):
    for s in sides:
        c.show(f'flip{s}_front', [(0, 0), (f0, 1), (f1, 0)])
        c.show(f'flip{s}_back', [(0, 1), (f0, 0), (f1, 1)])

def X(lx, ly):
    return to_canvas(lx, ly)

BREATH = (0.982, 1.03)
SLEEP = {'head.p': (0, 18), 'head.r': 4, 'face.p': (0, 40), 'patch.p': (0, 18), 'beak.s': (0.8, 0.45),
         'scarf.s': (1.06, 1.2), 'scarf.p': (0, -4), 'body.s': (1.03, 0.97),
         'flipL.r': -4, 'flipR.r': 4, 'tuft.r': 12, 'tuft.s': (1.05, 0.8),
         'scarf_tailA.r': -4, 'scarf_tailB.r': 4}
LIE = {'rock.r': 82, 'root.p': (-168, -76), 'face.p': (0, -10), 'patch.p': (0, -5),
       'flipL.r': 12, 'flipR.r': -12, 'footL.r': 18, 'footR.r': -10,
       'scarf_tailA.r': -18, 'scarf_tailB.r': -10, 'tuft.r': -14,
       'shadow.p': (-70, 0), 'shadow.s': (1.75, 1)}

CLIPS = []
def clip(fn):
    CLIPS.append(fn)
    return fn

# ============================================================ IDLE
@clip
def idle_breathe():
    c = new('idle_breathe', 'idle', 120)
    c.k('breath', 's', cyc(0, 120, 2, (1, 1), BREATH))
    c.k('eyeL', 's', blink(80)); c.k('eyeR', 's', blink(80))
    c.k('scarf_tailA', 'r', wave(0, 120, 2, 5))
    c.k('scarf_tailB', 'r', wave(0, 120, 4, -4))
    c.k('tuft', 'r', wave(0, 120, 4, 6))
    c.k('tuft', 's', cyc(0, 120, 2, (1, 1), (0.95, 1.08)))
    c.k('flipLx', 'r', cyc(0, 120, 2, 0, 4)); c.k('flipRx', 'r', cyc(0, 120, 2, 0, -4))
    c.k('shadow', 's', cyc(0, 120, 2, (1, 1), (0.98, 1)))
    return c

@clip
def idle_look_left_right():
    c = new('idle_look_left_right', 'idle', 120)
    Lk, Rk = look(-1, 0), look(1, 0)
    c.poses([(0, {}), (12, Lk), (46, Lk), (60, Rk), (96, Rk), (110, {}), (120, {})])
    c.k('breath', 's', cyc(0, 120, 2, (1, 1), BREATH))
    c.k('eyeL', 's', blink(30)); c.k('eyeR', 's', blink(30))
    pop(c, 'question', e_question(), 372, 118, 70, 100, rise=(4, -14))
    return c

@clip
def idle_yawn():
    c = new('idle_yawn', 'idle', 120)
    IN = {'body.s': (0.97, 1.05), 'head.p': (0, -8), 'head.r': -3, 'face.p': (0, -6),
          'flipL.r': 22, 'flipR.r': -22}
    Y = {'body.s': (0.96, 1.07), 'head.p': (0, -12), 'head.r': -4, 'face.p': (0, -8), 'beak.s': (1.15, 1.2),
         'flipL.r': 38, 'flipR.r': -38, 'tuft.s': (1.15, 0.5), 'tuft.r': 4}
    c.poses([(0, {}), (14, IN), (26, Y), (62, M(Y, {'beak.s': (1.1, 1.12)})),
             (76, {'body.s': (1.02, 0.98), 'beak.s': (0.9, 0.9), 'tuft.s': (1.1, 0.7)}),
             (92, {'tuft.s': (1.05, 0.85)}), (106, {}), (120, {})])
    beak(c, [(16, 'yawn'), (70, 'smile')])
    eyes(c, segs=[(16, 'squint'), (72, 'sleepy'), (86, 'open')])
    c.k('scarf_tailA', 'r', wave(20, 80, 2, 4))
    return c

@clip
def idle_stretch():
    c = new('idle_stretch', 'idle', 120)
    UP = {'root.p': (0, -12), 'footL.p': (0, 15), 'footR.p': (0, 15), 'footL.s': (1, 0.8), 'footR.s': (1, 0.8),
          'body.s': (0.95, 1.07), 'flipL.r': 100, 'flipR.r': -100, 'tail.r': -40, 'head.p': (0, -6), 'face.p': (0, -4),
          'shadow.s': (0.92, 1)}
    c.poses([(0, {}), (14, {'body.s': (1.04, 0.94), 'flipL.r': -6, 'flipR.r': 6}),
             (30, UP, 'outq'), (70, M(UP, {'flipL.r': 106, 'flipR.r': -106})),
             (82, {'body.s': (1.05, 0.95), 'tail.r': 12}, 'in'),
             (88, {'body.s': (0.98, 1.02), 'tail.r': -5}), (95, {'body.s': (1.01, 0.99), 'tail.r': 2}),
             (104, {}), (120, {})])
    eyes(c, segs=[(22, 'happy'), (84, 'open')])
    beak(c, [(24, 'o'), (80, 'smile')])
    c.k('tuft', 'r', cat([(0, 0), (30, -6), (70, -6)], spring(82, 0, 10, 4, 6)))
    return c

@clip
def idle_groom():
    c = new('idle_groom', 'idle', 150)
    D = {'head.p': (0, 46), 'head.r': 12, 'face.p': (-8, 24), 'patch.p': (-4, 10), 'body.s': (1.04, 0.92),
         'flipL.r': 50, 'tuft.r': 10}
    c.poses([(0, {}), (16, {'head.p': (0, 24), 'head.r': 8, 'face.p': (-6, 14), 'patch.p': (-3, 6),
                            'body.s': (1.03, 0.95), 'flipL.r': 30, 'tuft.r': 6}),
             (26, D), (88, D), (104, {'body.s': (0.98, 1.03), 'head.p': (0, -4)}),
             (112, {'body.s': (1.01, 0.99)}), (122, {}), (150, {})])
    c.k('headx', 'r', wave(26, 88, 8, 4))
    c.k('headx', 'p', cyc(26, 88, 8, (0, 0), (0, 5)))
    eyes(c, segs=[(18, 'happy'), (100, 'open')])
    c.k('eyeL', 's', blink(130)); c.k('eyeR', 's', blink(130))
    x, y = 236, 318
    fx(c, 'feather', e_feather(), x, y)
    c.k('feather', 'o', [(0, 0), (62, 0, 'lin'), (65, 1, 'lin'), (126, 1, 'lin'), (142, 0, 'lin')])
    c.k('feather', 's', [(0, 0.2), (62, 0.2, 'lin'), (70, 1.1, 'outq'), (76, 1.0)])
    c.k('feather', 'p', [(0, (0, 0)), (62, (0, 0), 'lin'), (76, (-16, -26), 'out'), (92, (-34, -14)),
                         (108, (-50, -30)), (124, (-66, -12)), (142, (-78, 0))])
    c.k('feather', 'r', [(0, 0), (62, 0, 'lin'), (76, -30), (92, 25), (108, -30), (124, 25), (142, -15)])
    return c

@clip
def idle_flap():
    c = new('idle_flap', 'idle', 120)
    up = {'flipL.r': 45, 'flipR.r': -45}
    c.poses([(0, {}), (8, M(up, {'body.s': (1.05, 0.94)})),
             (18, M(up, {'root.p': (0, -24), 'body.s': (0.97, 1.04), 'shadow.s': (0.8, 0.8)}), 'out'),
             (28, M(up, {'root.p': (0, -16), 'shadow.s': (0.86, 0.86)})),
             (38, M(up, {'root.p': (0, -30), 'shadow.s': (0.78, 0.78)})),
             (48, M(up, {'root.p': (0, -20), 'shadow.s': (0.85, 0.85)})),
             (58, M(up, {'root.p': (0, 0)}), 'in'),
             (63, {'body.s': (1.1, 0.88), 'flipL.r': 20, 'flipR.r': -20}, 'out'),
             (68, {'body.s': (0.97, 1.03)}),
             (78, {'flipL.r': 38, 'flipR.r': -38, 'body.s': (0.98, 1.04), 'head.r': 8, 'head.p': (0, 6)}),
             (98, {'flipL.r': 38, 'flipR.r': -38, 'body.s': (0.98, 1.04), 'head.r': 8, 'head.p': (0, 6)}),
             (110, {}), (120, {})])
    c.k('flipLx', 'r', cyc(8, 58, 10, 0, 60, 'sin'))
    c.k('flipRx', 'r', cyc(8, 58, 10, 0, -60, 'sin'))
    c.k('footL', 'r', cyc(16, 56, 5, 0, 16)); c.k('footR', 'r', cyc(16, 56, 5, 0, -16))
    c.k('rock', 'r', cat([(0, 0), (58, 0)], spring(58, 0, -4, 3, 8)))
    brows(c, 'angry', 8, 60)
    beak(c, [(10, 'squawk'), (60, 'o'), (76, 'frown'), (104, 'smile')])
    eyes(c, segs=[(76, 'sleepy'), (102, 'open')])
    c.k('scarf_tailA', 'r', cyc(10, 58, 5, 0, 12)); c.k('scarf_tailB', 'r', cyc(10, 58, 5, 0, 10))
    return c

# ============================================================ SLEEP
@clip
def sleep_fall_asleep():
    c = new('sleep_fall_asleep', 'sleep', 90, loop=False)
    c.poses([(0, {}), (20, {'head.p': (0, 12), 'face.p': (0, 6), 'patch.p': (0, 3), 'tuft.r': 4}),
             (30, {'head.p': (0, 4), 'face.p': (0, 2)}),
             (56, SLEEP), (64, M(SLEEP, {'head.p': (0, 22)})), (72, SLEEP), (89, SLEEP)])
    beak(c, [(52, None)])
    c.k('eyeL', 's', [(0, (1, 1)), (14, (1, 0.5)), (24, (1, 0.75)), (32, (1, 0.35), 'in'), (33, (1, 1), 'lin')])
    c.k('eyeR', 's', [(0, (1, 1)), (14, (1, 0.5)), (24, (1, 0.75)), (32, (1, 0.35), 'in'), (33, (1, 1), 'lin')])
    eyes(c, segs=[(33, 'sleepy')])
    c.k('breath', 's', [(0, (1, 1)), (40, (0.99, 1.02)), (70, (1, 1))])
    return c

@clip
def sleep_loop():
    c = new('sleep_loop', 'sleep', 120, holds=True, note='holds the asleep pose (follows sleep_fall_asleep)')
    c.poses([(0, SLEEP), (120, SLEEP)])
    eyes(c, 'sleepy')
    beak(c, [(0, None)])
    c.k('rock', 'r', wave(0, 120, 2, 3))
    c.k('breath', 's', cyc(0, 120, 2, (1, 1), (0.975, 1.035)))
    fx(c, 'bubble', e_snot(15), 20, -274, parent='face', op=1)
    c.k('bubble', 's', cyc(0, 120, 2, (0.35, 0.35), (1, 1)))
    for i, (f0, sz) in enumerate([(0, 8), (40, 10), (80, 12)]):
        particle(c, f'z{i}', e_z(sz), 318, 172, f0, 78, (48, -96), N=120, s0=0.5, s1=1.15, sway=8)
    return c

@clip
def sleep_wake_up():
    c = new('sleep_wake_up', 'sleep', 100, loop=False)
    c.poses([(0, SLEEP), (10, M(SLEEP, {'body.s': (1.02, 0.98)})),
             (18, {'root.p': (0, -16), 'body.s': (0.94, 1.08), 'flipL.r': 80, 'flipR.r': -80, 'tuft.s': (1.1, 1.35)}, 'outq'),
             (24, {'root.p': (0, 0), 'body.s': (1.06, 0.94), 'flipL.r': 60, 'flipR.r': -60, 'tuft.s': (1.1, 1.25)}, 'in'),
             (40, {'flipL.r': 22, 'flipR.r': -22, 'tuft.s': (1.05, 1.1)}),
             (62, {}), (99, {})])
    c.k('flipLx', 'r', cyc(16, 40, 4, 0, 40)); c.k('flipRx', 'r', cyc(16, 40, 4, 0, -40))
    c.k('rock', 'r', [(0, 0), (24, 0), (30, 11, 'outq'), (37, -9), (44, 6), (51, -3.5), (58, 1.5), (64, 0)])
    c.k('headx', 'r', wave(70, 92, 6, 9))
    c.k('eyeL', 's', [(0, (1, 1)), (12, (1, 1)), (15, (1.3, 1.3), 'outq'), (34, (1, 1))])
    c.k('eyeR', 's', [(0, (1, 1)), (12, (1, 1)), (15, (1.3, 1.3), 'outq'), (34, (1, 1))])
    eyes(c, 'sleepy', [(12, 'open'), (68, 'squint'), (93, 'open')])
    beak(c, [(0, None), (14, 'o'), (44, 'smile'), (68, 'frown'), (93, 'smile')])
    fx(c, 'bubble', e_snot(15), 20, -274, parent='face', op=1)
    c.k('bubble', 's', [(0, (0.4, 0.4)), (11, (1.55, 1.55), 'in')])
    c.show('bubble', [(0, 1), (12, 0)])
    fx(c, 'pop', e_burst(18), *X(30, -222))
    c.k('pop', 'o', [(0, 0, 'lin'), (11.9, 0, 'lin'), (12, 1, 'lin'), (17, 1, 'lin'), (20, 0, 'lin')])
    c.k('pop', 's', [(0, 0.6, 'lin'), (12, 0.6, 'lin'), (20, 1.5, 'out')])
    pop(c, 'bang', e_bang(), 352, 118, 14, 40, rise=(0, -8))
    return c

# ============================================================ MOVEMENT
@clip
def move_walk():
    c = new('move_walk', 'movement', 40, note='waddle in place; the app moves the window')
    c.k('rock', 'r', wave(0, 40, 2, 6))
    c.k('root', 'p', cyc(0, 40, 2, (0, 0), (0, -6)))
    c.k('footL', 'p', [(0, (0, 0)), (10, (0, -13)), (20, (0, 0)), (40, (0, 0))])
    c.k('footL', 'r', [(0, 0), (10, -12), (20, 0), (40, 0)])
    c.k('footR', 'p', [(0, (0, 0)), (20, (0, 0)), (30, (0, -13)), (40, (0, 0))])
    c.k('footR', 'r', [(0, 0), (20, 0), (30, 12), (40, 0)])
    c.k('flipL', 'r', [(0, 0), (10, 42), (20, 14), (30, 28), (40, 0)])
    c.k('flipR', 'r', [(0, 0), (10, -28), (20, -14), (30, -42), (40, 0)])
    c.k('head', 'r', wave(0, 40, 2, -3))
    c.k('tuft', 'r', [(0, 0), (13, -8), (33, 8), (40, 0)])
    c.k('scarf_tailA', 'r', [(0, 0), (13, -9), (33, 9), (40, 0)])
    c.k('scarf_tailB', 'r', [(0, 0), (14, -7), (34, 7), (40, 0)])
    c.k('shadow', 'p', wave(0, 40, 2, (4, 0)))
    return c

@clip
def move_hop():
    c = new('move_hop', 'movement', 50)
    c.poses([(0, {}),
             (8, {'body.s': (1.08, 0.88), 'head.p': (0, 4), 'flipL.r': -8, 'flipR.r': 8, 'shadow.s': (1.05, 1)}),
             (18, {'root.p': (0, -50), 'body.s': (0.94, 1.06), 'flipL.r': 150, 'flipR.r': -150, 'footL.r': 14,
                   'footR.r': -14, 'tuft.s': (0.9, 1.2), 'scarf_tailA.r': 20, 'scarf_tailB.r': 16,
                   'shadow.s': (0.62, 0.62)}, 'outq'),
             (23, {'root.p': (0, -56), 'flipL.r': 140, 'flipR.r': -140, 'footL.r': 8, 'footR.r': -8,
                   'scarf_tailA.r': 6, 'scarf_tailB.r': 4, 'shadow.s': (0.58, 0.58)}, 'out'),
             (32, {'root.p': (0, 0), 'body.s': (0.96, 1.05), 'flipL.r': 110, 'flipR.r': -110,
                   'scarf_tailA.r': -16, 'scarf_tailB.r': -12, 'tuft.s': (1.05, 0.9)}, 'in'),
             (36, {'body.s': (1.13, 0.86), 'flipL.r': 55, 'flipR.r': -55, 'tuft.s': (1.1, 0.75),
                   'shadow.s': (1.08, 1)}, 'out'),
             (40, {'body.s': (0.96, 1.05), 'flipL.r': 6, 'flipR.r': -6, 'scarf_tailA.r': 6}),
             (44, {'body.s': (1.03, 0.97), 'scarf_tailA.r': -3}), (50, {})])
    c.k('rock', 'r', [(0, 0), (32, 0), (37, -5), (42, 3), (46, -1), (50, 0)])
    eyes(c, segs=[(12, 'happy'), (40, 'open')])
    beak(c, [(12, 'tongue'), (42, 'smile')])
    return c

@clip
def move_belly_slide():
    c = new('move_belly_slide', 'movement', 90, note='slides toward the right; the app moves the window')
    LIE = {k: v for k, v in globals()['LIE'].items() if not k.startswith('scarf_tail')}
    LS = M(LIE, {'body.s': (1.06, 0.95)})
    c.poses([(0, {}),
             (8, {'body.s': (1.06, 0.92), 'rock.r': -6, 'flipL.r': 40, 'flipR.r': -40, 'head.p': (0, 4)}),
             (16, {'rock.r': 42, 'root.p': (-70, -40), 'flipL.r': 60, 'flipR.r': -60, 'body.s': (0.96, 1.05),
                   'shadow.p': (-30, 0), 'shadow.s': (1.3, 1)}, 'in'),
             (22, LS, 'out'), (27, LIE), (68, LIE),
             (75, {'rock.r': 28, 'root.p': (-40, -46), 'body.s': (0.95, 1.05), 'flipL.r': 70, 'flipR.r': -70,
                   'shadow.p': (-20, 0), 'shadow.s': (1.2, 1)}, 'outq'),
             (80, {'rock.r': -5, 'root.p': (0, -8), 'flipL.r': 20, 'flipR.r': -20}, 'io'),
             (84, {'rock.r': 3, 'body.s': (1.05, 0.95)}), (87, {'body.s': (0.99, 1.01)}), (90, {})])
    c.k('body', 'p', cat([(0, (0, 0)), (27, (0, 0))], cyc(27, 68, 6, (0, 0), (2.5, 0)), [(90, (0, 0))]))
    eyes(c, segs=[(14, 'happy'), (76, 'open')])
    beak(c, [(14, 'tongue'), (76, 'smile')])
    c.k('scarf_tailA', 'r', cat([(0, 0), (22, -18)], cyc(27, 68, 8, -18, -30), [(76, 0)]))
    c.k('scarf_tailB', 'r', cat([(0, 0), (22, -10)], cyc(27, 68, 7, -10, -22), [(76, 0)]))
    for i, (yy, ln) in enumerate([(402, 30), (424, 40), (446, 26)]):
        fk_o, fk_p = [(0, 0, 'lin')], [(0, (0, 0), 'lin')]
        t = 26 + i * 4
        while t + 12 <= 70:
            fk_o += [(t, 0, 'lin'), (t + 2, 1, 'lin'), (t + 10, 1, 'lin'), (t + 12, 0, 'lin')]
            fk_p += [(t, (0, 0), 'lin'), (t + 12, (-44, 0), 'lin')]
            t += 14
        fx(c, f'speed{i}', e_speedline(ln), 70, yy)
        c.k(f'speed{i}', 'o', fk_o); c.k(f'speed{i}', 'p', fk_p)
    for i, (dx, dy, f0) in enumerate([(-30, -34, 26), (-12, -44, 31), (-40, -22, 36), (-22, -40, 44),
                                      (-34, -30, 50), (-16, -42, 56), (-38, -26, 61)]):
        particle(c, f'spray{i}', e_puff(5 + (i % 3)), 418, 462, f0, 12, (dx, dy), s0=0.6, s1=1.1, fade=3)
    return c

@clip
def move_fall_land():
    c = new('move_fall_land', 'movement', 75, loop=False)
    SIT = {'root.p': (-44, 6), 'body.s': (1.06, 0.92), 'footL.r': -24, 'footR.r': 24,
           'footL.p': (-8, -4), 'footR.p': (8, -4), 'flipL.r': 22, 'flipR.r': -22, 'head.r': -5,
           'shadow.p': (-36, 0), 'shadow.s': (1.1, 1)}
    LAND = M(LIE, {'root.p': (-150, -76), 'shadow.p': (-52, 0)})
    c.poses([(0, {'root.p': (0, -480), 'flipL.r': 100, 'flipR.r': -100, 'body.s': (0.94, 1.06),
                  'shadow.s': (0.3, 0.3)}),
             (14, {'root.p': (-50, -260), 'rock.r': 20, 'flipL.r': 100, 'flipR.r': -100, 'body.s': (0.94, 1.06),
                   'shadow.s': (0.8, 0.8)}, 'in'),
             (24, M(LAND, {'body.s': (1.08, 0.9)}), 'in'),
             (29, M(LAND, {'body.s': (0.98, 1.02)})),
             (42, M(LAND, {'root.p': (-120, -76), 'shadow.p': (-24, 0)}), 'outq'),
             (46, M(LAND, {'root.p': (-120, -76), 'shadow.p': (-24, 0)})),
             (56, SIT, 'io'), (60, M(SIT, {'body.s': (1.03, 0.95)})), (64, SIT), (74, SIT)])
    c.k('flipLx', 'r', cat(cyc(0, 22, 5, 0, 45), [(24, 0)]))
    c.k('flipRx', 'r', cat(cyc(0, 22, 5, 0, -45), [(24, 0)]))
    c.k('footL', 's', [(0, (1, 1)), (74, (1, 1))])
    c.k('eyeL', 's', [(0, (1.25, 1.25)), (22, (1.25, 1.25)), (26, (1, 1))])
    c.k('eyeR', 's', [(0, (1.25, 1.25)), (22, (1.25, 1.25)), (26, (1, 1))])
    eyes(c, segs=[(24, 'squint'), (50, 'dizzy')])
    beak(c, [(0, 'squawk'), (24, 'o')], default='squawk')
    c.k('headx', 'r', cat([(0, 0), (56, 0)], wave(56, 74, 3, 6)))
    sx = 256 - 44 * 1 + 4
    for i in range(3):
        orbit(c, f'star{i}', sx, 128, 66, 16, 54, 74, 24, i * 2 * math.pi / 3, size=13)
    for i, (dx, dy) in enumerate([(-34, -30), (-8, -42), (22, -36), (40, -18), (-46, -12)]):
        particle(c, f'puff{i}', e_puff(6), 300, 462, 24, 14, (dx, dy), s0=0.5, s1=1.15, fade=3)
    return c

# ============================================================ INTERACTION
@clip
def int_dragged():
    c = new('int_dragged', 'interaction', 60, holds=True, note='held pose while dragged; pivots at the scarf')
    r = c['root']
    r.anchor, r.pos = (0, -190), (256, 470 - 190 * 0.8)
    HOLD = {'root.p': (0, -34), 'body.s': (0.95, 1.06), 'footL.p': (0, 8), 'footR.p': (0, 8),
            'scarf.s': (1.04, 1.12), 'flipL.r': 50, 'flipR.r': -50, 'eyeL.s': (1.22, 1.22), 'eyeR.s': (1.22, 1.22),
            'shadow.s': (0.72, 0.72), 'tuft.s': (1.1, 1.2)}
    c.poses([(0, HOLD), (60, HOLD)])
    c.k('root', 'r', wave(0, 60, 2, 5))
    c.k('flipLx', 'r', cyc(0, 60, 10, 0, 50)); c.k('flipRx', 'r', cyc(0, 60, 10, 0, -50))
    c.k('footL', 'r', cyc(0, 60, 6, -18, 18)); c.k('footR', 'r', cyc(0, 60, 6, 18, -18))
    c.k('scarf_tailA', 'r', wave(0, 60, 2, -6)); c.k('scarf_tailB', 'r', wave(0, 60, 2, -4))
    c.k('shadow', 'o', [(0, 0.7), (60, 0.7)])
    beak(c, [], 'o')
    brows(c, 'worried', 0, 61)
    return c

@clip
def int_petted():
    c = new('int_petted', 'interaction', 90)
    MELT = {'body.s': (1.08, 0.9), 'head.p': (0, 12), 'face.p': (0, 4), 'flipL.r': 22, 'flipR.r': -22,
            'tuft.s': (1.12, 0.75), 'cheekL.s': (1.3, 1.3), 'cheekR.s': (1.3, 1.3)}
    c.poses([(0, {}), (14, MELT), (72, MELT), (82, {'body.s': (0.98, 1.02)}), (90, {})])
    c.k('rock', 'r', wave(14, 72, 4, 4))
    c.k('flipLx', 'r', cyc(18, 70, 5, 0, 30)); c.k('flipRx', 'r', cyc(18, 70, 5, 0, -30))
    eyes(c, segs=[(8, 'happy'), (80, 'open')])
    beak(c, [(10, 'tongue'), (78, 'smile')])
    for i, (x, y, f0) in enumerate([(196, 150, 16), (318, 136, 30), (252, 108, 44)]):
        pop(c, f'heart{i}', e_heart(17 - i), x, y, f0, f0 + 34, rise=(6 * (1 if i % 2 else -1), -36))
    return c

@clip
def int_poked():
    c = new('int_poked', 'interaction', 100)
    c.k('rock', 'r', [(0, 0), (4, 14, 'outq'), (11, -11), (18, 8), (25, -5), (32, 3), (38, 0), (100, 0)])
    PUFF = {'body.s': (1.06, 1.02), 'cheekL.s': (1.6, 1.6), 'cheekR.s': (1.6, 1.6), 'head.r': -3,
            'face.p': (0, -2)}
    c.poses([(0, {}), (36, {}), (44, PUFF), (80, PUFF), (92, {}), (100, {})])
    c.k('flipR', 'r', [(0, 0), (46, 0), (50, -120, 'outq'), (56, -30), (60, -112, 'outq'), (67, -20),
                       (80, -15), (92, 0)])
    eyes(c, segs=[(2, 'squint'), (30, 'open')])
    beak(c, [(2, 'o'), (30, 'smile'), (40, 'frown'), (90, 'smile')])
    brows(c, 'angry', 40, 90)
    pop(c, 'anger', e_anger(1.3), 344, 128, 44, 90, rise=(0, -4))
    fx(c, 'swish', [L(path('M0 -14 Q10 0 0 14') + path('M10 -10 Q18 0 10 10'), '#b9c6f0', 4.5)], 392, 260)
    c.k('swish', 'o', [(0, 0, 'lin'), (50, 0, 'lin'), (51, 1, 'lin'), (56, 0, 'lin'), (60, 0, 'lin'),
                       (61, 1, 'lin'), (67, 0, 'lin')])
    return c

@clip
def int_tickled():
    c = new('int_tickled', 'interaction', 90)
    c.k('rock', 'r', wave(4, 84, 10, 6))
    c.k('body', 's', cat([(0, (1, 1))], cyc(4, 84, 10, (1, 1), (1.04, 0.95)), [(90, (1, 1))]))
    c.k('beak', 's', cyc(4, 84, 10, (1, 1), (1.08, 1.18)))
    c.k('head', 'r', wave(4, 84, 5, 5))
    def taps(off):
        ks = [(0, (0, 0))]
        t = 4 + off
        while t + 8 <= 84:
            ks += [(t, (0, 0)), (t + 4, (0, -10)), (t + 8, (0, 0))]
            t += 16
        return ks + [(90, (0, 0))]
    c.k('footL', 'p', taps(0)); c.k('footR', 'p', taps(8))
    c.k('flipLx', 'r', cyc(4, 84, 10, 0, 26)); c.k('flipRx', 'r', cyc(4, 84, 10, 0, -26))
    eyes(c, segs=[(4, 'squint'), (84, 'open')])
    beak(c, [(4, 'squawk'), (84, 'smile')])
    twinkle(c, 'spk0', 178, 168, [10, 34, 58], size=10)
    twinkle(c, 'spk1', 338, 160, [22, 46, 70], size=10)
    return c

def make_look(name, dx, dy):
    def f():
        c = new(name, 'interaction', 60, holds=True, note='holds the look direction (cursor follow)')
        n = math.hypot(dx, dy)
        lk = look(dx / n, dy / n)
        c.poses([(0, lk), (60, lk)])
        c.k('breath', 's', cyc(0, 60, 1, (1, 1), (0.988, 1.02)))
        return c
    f.__name__ = name
    return f

for _n, _d in [('up', (0, -1)), ('up_right', (1, -1)), ('right', (1, 0)), ('down_right', (1, 1)),
               ('down', (0, 1)), ('down_left', (-1, 1)), ('left', (-1, 0)), ('up_left', (-1, -1))]:
    clip(make_look('int_look_' + _n, *_d))

# ============================================================ MOODS
@clip
def mood_happy():
    c = new('mood_happy', 'mood', 120)
    c.poses([(0, {}), (10, {'flipL.r': 50, 'flipR.r': -50, 'cheekL.s': (1.2, 1.2), 'cheekR.s': (1.2, 1.2)}),
             (108, {'flipL.r': 50, 'flipR.r': -50, 'cheekL.s': (1.2, 1.2), 'cheekR.s': (1.2, 1.2)}), (118, {}), (120, {})])
    c.k('flipLx', 'r', cyc(10, 108, 7, 0, 42)); c.k('flipRx', 'r', cyc(10, 108, 7, 0, -42))
    c.k('root', 'p', cyc(4, 108, 8, (0, 0), (0, -12)))
    c.k('rock', 'r', wave(4, 108, 4, 6))
    def taps(off):
        ks = [(0, (0, 0))]
        t = 4 + off
        while t + 13 <= 108:
            ks += [(t, (0, 0)), (t + 6, (0, -12)), (t + 13, (0, 0))]
            t += 26
        return ks + [(120, (0, 0))]
    def tapr(off, s):
        ks = [(0, 0)]
        t = 4 + off
        while t + 13 <= 108:
            ks += [(t, 0), (t + 6, -14 * s), (t + 13, 0)]
            t += 26
        return ks + [(120, 0)]
    c.k('footL', 'p', taps(0)); c.k('footR', 'p', taps(13))
    c.k('footL', 'r', tapr(0, 1)); c.k('footR', 'r', tapr(13, -1))
    c.k('scarf_tailA', 'r', wave(4, 108, 8, 8)); c.k('tuft', 'r', wave(4, 108, 8, -8))
    eyes(c, segs=[(6, 'happy'), (112, 'open')])
    beak(c, [(6, 'tongue'), (112, 'smile')])
    twinkle(c, 'spk0', 124, 170, [12, 52, 88])
    twinkle(c, 'spk1', 392, 150, [26, 66, 96])
    twinkle(c, 'spk2', 138, 330, [40, 78], size=9)
    twinkle(c, 'spk3', 378, 318, [18, 58], size=9)
    return c

@clip
def mood_sad():
    c = new('mood_sad', 'mood', 120)
    SAD = {'body.s': (1.02, 0.95), 'head.p': (0, 12), 'head.r': 4, 'face.p': (0, 10), 'patch.p': (0, 5),
           'flipL.r': -6, 'flipR.r': 6, 'tuft.s': (1.25, 0.45), 'scarf.p': (0, 4), 'scarf.s': (0.98, 0.96),
           'scarf_tailA.r': -8, 'scarf_tailB.r': 6, 'eyeL.s': (1, 0.86), 'eyeR.s': (1, 0.86),
           'eyeL.p': (0, 4), 'eyeR.p': (0, 4)}
    c.poses([(0, {}), (20, SAD), (96, SAD), (112, {}), (120, {})])
    c.k('breath', 's', cyc(20, 96, 2, (1, 1), (0.99, 1.025)))
    brows(c, 'worried', 12, 108)
    beak(c, [(12, 'frown'), (108, 'smile')])
    ex, ey = X(-48 + 12, -318 + 12 + 10 + 4 + 22)
    fx(c, 'tear', e_tear(), ex, ey)
    c.k('tear', 'o', [(0, 0, 'lin'), (30, 0, 'lin'), (32, 1, 'lin'), (70, 1, 'lin'), (78, 0, 'lin')])
    c.k('tear', 's', [(0, 0.1), (30, 0.1, 'lin'), (40, 1, 'outq')])
    c.k('tear', 'p', [(0, (0, 0)), (40, (0, 0)), (76, (-4, 46), 'in')])
    ex2, ey2 = X(48 - 10, -318 + 12 + 10 + 4 + 24)
    fx(c, 'tear2', e_tear(), ex2, ey2, scale=0.8)
    c.k('tear2', 'o', [(0, 0, 'lin'), (58, 0, 'lin'), (60, 1, 'lin'), (90, 1, 'lin'), (96, 0, 'lin')])
    c.k('tear2', 's', [(0, 0.1), (58, 0.1, 'lin'), (66, 0.8, 'outq')])
    c.k('tear2', 'p', [(0, (0, 0)), (66, (0, 0)), (94, (3, 38), 'in')])
    return c

@clip
def mood_surprised():
    c = new('mood_surprised', 'mood', 90)
    P = {'body.s': (1.1, 1.03), 'root.p': (0, -6), 'tuft.s': (1.3, 1.45), 'flipL.r': 55, 'flipR.r': -55,
         'eyeL.s': (1.3, 1.3), 'eyeR.s': (1.3, 1.3), 'head.p': (0, -4),
         'scarf.s': (1.08, 1), 'scarf_tailA.r': 14, 'scarf_tailB.r': 10, 'shadow.s': (1.1, 1)}
    c.poses([(0, {}), (5, {'body.s': (1.04, 0.95)}), (11, M(P, {'root.p': (0, -16), 'body.s': (1.13, 1.05)}), 'outq'), (16, P),
             (60, P), (68, {'body.s': (0.96, 1.03), 'eyeL.s': (0.95, 0.95), 'eyeR.s': (0.95, 0.95)}),
             (75, {'body.s': (1.02, 0.98)}), (82, {}), (90, {})])
    beak(c, [(8, 'o'), (70, 'smile')])
    fx(c, 'bang', e_bang(), 356, 124)
    c.k('bang', 'o', [(0, 0, 'lin'), (9, 0, 'lin'), (11, 1, 'lin'), (64, 1, 'lin'), (72, 0, 'lin')])
    c.k('bang', 's', cat([(0, 0.2), (9, 0.2, 'lin'), (14, 1.25, 'outq')], spring(14, 1.0, 0.25, 3, 6)))
    c.k('bang', 'r', cat([(0, 0), (14, 0)], wave(14, 40, 4, 8)))
    return c

@clip
def mood_hungry():
    c = new('mood_hungry', 'mood', 120)
    LK = M(look(0.55, -0.7), {'head.r': -5})
    c.poses([(0, {}), (14, M(LK, {'flipR.r': 48})), (104, M(LK, {'flipR.r': 48})), (116, {}), (120, {})])
    front_flippers(c, 10, 112, 'R')
    c.k('flipRx', 'r', cyc(14, 104, 6, 0, 22))
    c.k('flipRx', 'p', cyc(14, 104, 6, (0, 0), (-4, 8)))
    c.k('breath', 's', cat([(0, (1, 1)), (40, (1, 1))], cyc(40, 52, 3, (1, 1), (1.03, 0.97)), [(120, (1, 1))]))
    beak(c, [(16, 'tongue'), (104, 'smile')])
    c.k('eyeL', 's', blink(60)); c.k('eyeR', 's', blink(60))
    for i, (x, y, r, f0) in enumerate([(326, 178, 4.5, 14), (350, 150, 7, 20)]):
        fx(c, f'bead{i}', e_bead(r), x, y)
        c.k(f'bead{i}', 'o', [(0, 0, 'lin'), (f0, 0, 'lin'), (f0 + 2, 1, 'lin'), (100, 1, 'lin'), (108, 0, 'lin')])
        c.k(f'bead{i}', 's', [(0, 0.1), (f0, 0.1, 'lin'), (f0 + 6, 1, 'outq')])
    fx(c, 'cloud', e_cloud(), 412, 96)
    c.k('cloud', 'o', [(0, 0, 'lin'), (26, 0, 'lin'), (28, 1, 'lin'), (100, 1, 'lin'), (108, 0, 'lin')])
    c.k('cloud', 's', cat([(0, 0.1), (26, 0.1, 'lin'), (34, 1.08, 'outq'), (38, 1)]))
    c.k('cloud', 'p', cat([(0, (0, 0)), (38, (0, 0))], cyc(38, 100, 2, (0, 0), (0, -5))))
    fx(c, 'fishthought', p_fish(), 412, 96, scale=0.55)
    c.k('fishthought', 'o', [(0, 0, 'lin'), (30, 0, 'lin'), (32, 1, 'lin'), (100, 1, 'lin'), (106, 0, 'lin')])
    c.k('fishthought', 's', [(0, 0.1), (30, 0.1, 'lin'), (38, 0.6, 'outq'), (42, 0.55)])
    c.k('fishthought', 'p', cat([(0, (0, 0)), (38, (0, 0))], cyc(38, 100, 2, (0, 0), (0, -5))))
    c.k('fishthought', 'r', cat([(0, 0), (42, 0)], wave(42, 100, 6, 8)))
    return c

@clip
def mood_love():
    c = new('mood_love', 'mood', 120)
    H = {'flipL.r': -38, 'flipR.r': 38, 'head.r': -6, 'face.p': (0, 4), 'body.s': (1.02, 0.98)}
    c.poses([(0, {}), (16, H), (40, H), (50, M(H, {'flipL.r': -42, 'flipR.r': 42, 'body.s': (1.0, 1.01)})),
             (96, M(H, {'flipL.r': -42, 'flipR.r': 42, 'body.s': (1.0, 1.01)})), (110, {}), (120, {})])
    front_flippers(c, 12, 104)
    c.k('rock', 'r', wave(20, 100, 4, 4))
    eyes(c, segs=[(10, 'heart'), (106, 'open')])
    c.k('eyeL', 's', cat([(0, (1, 1)), (10, (1, 1))], cyc(14, 98, 6, (1, 1), (1.15, 1.15)), [(120, (1, 1))]))
    c.k('eyeR', 's', cat([(0, (1, 1)), (10, (1, 1))], cyc(14, 98, 6, (1, 1), (1.15, 1.15)), [(120, (1, 1))]))
    cheeks(c, 'blush', 10, 106)
    beak(c, [(12, 'tongue'), (104, 'smile')])
    fx(c, 'pebble', p_pebble(), 0, -104, parent='body', zz=c['flipL_front'].z - 5)
    c.k('pebble', 'o', [(0, 0, 'lin'), (13, 0, 'lin'), (14, 1, 'lin'), (104, 1, 'lin'), (106, 0, 'lin')])
    c.k('pebble', 's', [(0, 0.1), (13, 0.1, 'lin'), (22, 1.15, 'outq'), (28, 1.0), (40, 1.0),
                        (50, 1.12), (96, 1.12), (105, 0.2, 'in')])
    hx, hy = X(0, -104)
    fx(c, 'loveheart', e_heart(15), hx, hy - 30)
    c.k('loveheart', 'o', [(0, 0, 'lin'), (30, 0, 'lin'), (33, 1, 'lin'), (94, 1, 'lin'), (102, 0, 'lin')])
    c.k('loveheart', 's', cat([(0, 0.1), (30, 0.1, 'lin'), (40, 1.1, 'outq')], cyc(44, 94, 5, 1.0, 1.2)))
    c.k('loveheart', 'p', [(0, (0, 0)), (30, (0, 0)), (54, (0, -26)), (94, (0, -34)), (102, (0, -44))])
    return c

@clip
def mood_cold():
    c = new('mood_cold', 'mood', 120)
    COLD = {'body.s': (0.95, 0.97), 'scarf.s': (0.93, 1.2), 'scarf.p': (0, -2), 'scarf_tailA.r': -14,
            'scarf_tailB.r': -10, 'flipL.r': -30, 'flipR.r': 30, 'head.p': (0, 8), 'tuft.s': (0.9, 0.85),
            'face.p': (0, 4)}
    c.poses([(0, {}), (16, COLD), (100, COLD), (114, {}), (120, {})])
    front_flippers(c, 10, 108)
    c.k('root', 'p', cat([(0, (0, 0))], jitter(16, 100, 2.4, 2), [(120, (0, 0))]))
    c.k('tuft', 'r', cat([(0, 0)], jitter_r(16, 100, 4), [(120, 0)]))
    cheeks(c, 'cold', 14, 106)
    eyes(c, segs=[(16, 'squint'), (102, 'open')])
    brows(c, 'worried', 14, 104)
    beak(c, [(14, 'frown'), (104, 'smile')])
    for i, (x, f0, sz) in enumerate([(92, 4, 9), (178, 22, 7), (360, 10, 9), (430, 34, 7), (128, 50, 8),
                                     (402, 62, 8), (290, 44, 6)]):
        particle(c, f'flake{i}', e_snowflake(sz + 3), x, 36 + (i % 3) * 12, f0, 56, (0, 150), sway=10,
                 spin=120 if i % 2 else -120, fade=6)
    return c

def jitter_r(f0, f1, amp, step=2):
    return [(f, amp if i % 2 == 0 else -amp, 'lin') for i, f in enumerate(range(f0 + step, f1 - 1, step))] + [(f1, 0, 'lin')]

@clip
def mood_smile_wink():
    c = new('mood_smile_wink', 'mood', 90)
    T = {'head.r': -8, 'head.p': (-4, 0), 'body.s': (1.02, 0.98), 'flipR.r': -40,
         'cheekL.s': (1.15, 1.15), 'cheekR.s': (1.15, 1.15)}
    c.poses([(0, {}), (12, T), (64, T), (78, {}), (90, {})])
    c.k('flipRx', 'r', cat([(0, 0), (16, 0)], wave(16, 60, 4, -14), [(90, 0)]))
    beak(c, [(8, 'tongue'), (76, 'smile')])
    eyes2(c, [], [(20, 'wink'), (58, 'open')])
    twinkle(c, 'spk0', 330, 186, [22, 38], s=1.0, size=13)
    return c

# ============================================================ FUN
@clip
def fun_spin():
    c = new('fun_spin', 'fun', 90)
    s0 = ROOT_S
    sk = [(0, (s0, s0)), (14, (s0, s0))]
    back = []
    for t0 in (14, 29):
        q = 15 / 4
        sk += [(t0 + q, (0.001, s0), 'in'), (t0 + 2 * q, (-s0, s0), 'out'), (t0 + 3 * q, (-0.001, s0), 'in'),
               (t0 + 4 * q, (s0, s0), 'out')]
        back.append((t0 + q, t0 + 3 * q))
    sk.append((90, (s0, s0)))
    c.k('root', 's', sk)
    SP = {'flipL.r': 72, 'flipR.r': -72, 'footL.p': (0, -18), 'footL.r': -18, 'scarf_tailA.r': 62,
          'scarf_tailB.r': 50, 'tuft.r': -12, 'body.s': (0.97, 1.03)}
    c.poses([(0, {}), (10, {'body.s': (1.04, 0.95), 'flipL.r': 30, 'flipR.r': -30,
                            'footL.p': (0, -12), 'footL.r': -12}),
             (16, SP), (42, SP), (50, {'flipL.r': 30, 'flipR.r': -30}), (60, {}), (90, {})])
    c.k('rock', 'r', [(0, 0), (10, -6), (16, 0), (44, 0), (50, 8), (57, -7), (64, 5), (71, -3), (78, 1.5), (84, 0)])
    c.k('headx', 'r', cat([(0, 0), (46, 0)], wave(46, 84, 4, 6)))
    # back view: hide the front-facing parts while the character faces away
    segs = []
    for a, b in back:
        segs += [(a, 0), (b, 1)]
    for nm in ['belly', 'patch_shape', 'cheekL_pink', 'cheekR_pink', 'scarf_tailA', 'scarf_tailB']:
        c.show(nm, [(0, 1)] + segs)
    c.show('back_shape', [(0, 0)] + [(f, 1 - v) for f, v in segs])
    ev = [(12, 'happy')]
    for a, b in back:
        ev += [(a, None), (b, 'happy')]
    ev += [(46, 'dizzy'), (82, 'open')]
    eyes(c, segs=ev)
    bv = [(12, 'tongue')]
    for a, b in back:
        bv += [(a, None), (b, 'tongue')]
    bv += [(46, 'o'), (82, 'smile')]
    beak(c, bv)
    return c

@clip
def fun_peek():
    c = new('fun_peek', 'fun', 120, holds=True, note='starts and ends off-canvas (empty frame)')
    c.k('root', 's', [(0, (-ROOT_S, ROOT_S)), (120, (-ROOT_S, ROOT_S))])
    OFF = M(LIE, {'root.p': (640, -76), 'shadow.p': (640 - 95 - 2, 0), 'face.p': (0, 0), 'patch.p': (0, 0)})
    IN = M(LIE, {'root.p': (392, -76), 'shadow.p': (392 - 95, 0), 'face.p': (0, 0), 'patch.p': (0, 0)})
    def at(d, **kw):
        out = dict(d)
        for k, v in kw.items():
            out[k.replace('_', '.', 1)] = v
        return out
    c.poses([(0, OFF), (20, at(IN, root_p=(376, -76), shadow_p=(376 - 95, 0)), 'outq'),
             (26, at(IN, root_p=(394, -76), shadow_p=(394 - 95, 0))), (31, IN),
             (40, M(IN, look(0, -1))), (52, M(IN, look(0, -1))),
             (60, M(IN, look(0.8, 0.6))), (72, M(IN, look(0.8, 0.6))),
             (80, M(IN, look(-0.8, 0.6))), (88, M(IN, look(-0.8, 0.6))),
             (94, IN), (100, at(IN, root_p=(404, -76), shadow_p=(404 - 95, 0))),
             (116, OFF, 'in'), (120, OFF)])
    c.k('eyeL', 's', blink(54)); c.k('eyeR', 's', blink(54))
    eyes(c, segs=[(96, 'happy'), (119, 'open')])
    beak(c, [(4, 'tongue'), (28, 'smile'), (96, 'tongue'), (119, 'smile')])
    for i, (yy, ln) in enumerate([(404, 30), (428, 40), (450, 26)]):
        fx(c, f'speed{i}', e_speedline(ln), 470 - i * 6, yy)
        c.k(f'speed{i}', 'o', [(0, 0, 'lin'), (4 + i * 2, 0, 'lin'), (6 + i * 2, 1, 'lin'), (16 + i * 2, 1, 'lin'),
                               (20 + i * 2, 0, 'lin')])
        c.k(f'speed{i}', 'p', [(0, (0, 0), 'lin'), (4 + i * 2, (0, 0), 'lin'), (20 + i * 2, (34, 0), 'lin')])
    return c

@clip
def fun_notify():
    c = new('fun_notify', 'fun', 60, holds=True, note='notification pose; loop while the alert is active')
    fl = Layer('floe', None, (0, 0), pos=(256, 474), shapes=p_floe(), scale=(ROOT_S, ROOT_S),
               z=c['shadow'].z - 5)
    c.add(fl)
    c.k('floe', 'p', cyc(0, 60, 2, (0, 0), (0, 3)))
    N = {'root.p': (0, -16), 'flipR.r': -128, 'flipL.r': 28, 'shadow.p': (0, -16), 'shadow.s': (0.8, 0.85)}
    c.poses([(0, N), (60, N)])
    c.k('rock', 'r', wave(0, 60, 2, 3))
    c.k('breath', 's', cyc(0, 60, 2, (1, 1), (0.99, 1.02)))
    c.k('flipRx', 'r', wave(0, 60, 2, 10))
    c.k('flipLx', 'r', cyc(0, 60, 4, 0, 18))
    fish = tx_shapes(p_fish(), rot=-90, dx=128, dy=-40)
    c.add(Layer('fish', 'flipRx', (128, -80), shapes=fish, scale=(1.3, 1.3), z=c['flipR_front'].z + 5))
    c.k('fish', 'r', wave(0, 60, 2, -16))
    c.show('flipR_front', [(0, 1)]); c.show('flipR_back', [(0, 0)])
    beak(c, [], 'tongue')
    fx(c, 'badge', e_badge(), 392, 104, op=1)
    c.k('badge', 's', cyc(0, 60, 4, 1.0, 1.1))
    c.k('badge', 'p', cyc(0, 60, 2, (0, 0), (0, -5)))
    c.k('badge', 'r', wave(0, 60, 2, 6))
    return c

def tx_shapes(shapes, rot=0, dx=0, dy=0, s=1):
    return [Shape(tx(sh.cons, dx, dy, s, s, rot), sh.fill, sh.stroke, sh.sw, sh.fo, sh.so, sh.nm) for sh in shapes]

@clip
def fun_snowball():
    c = new('fun_snowball', 'fun', 150)
    PACK = M(look(0, 0.9), {'flipL.r': -40, 'flipR.r': 40, 'head.p': (0, 10), 'body.s': (1.03, 0.97)})
    WIND = {'flipR.r': -150, 'flipL.r': 30, 'body.s': (0.98, 1.03), 'head.r': -4}
    THROW = {'flipR.r': 15, 'flipL.r': 20, 'body.s': (1.03, 0.97), 'head.r': 3}
    LAUGH = {'flipL.r': 30, 'flipR.r': -30}
    c.poses([(0, {}), (8, PACK), (42, PACK), (54, WIND, 'io'), (60, THROW, 'inq'), (68, THROW),
             (76, LAUGH), (124, LAUGH), (138, {}), (150, {})])
    front_flippers(c, 6, 46, 'LR')
    c.k('flipLx', 'r', cat(cyc(10, 40, 5, 0, -16), cyc(76, 124, 8, 0, 34), [(150, 0)]))
    c.k('flipRx', 'r', cat(cyc(10, 40, 5, 0, 16), cyc(76, 124, 8, 0, -34), [(150, 0)]))
    fx(c, 'ballA', p_snowball(), 0, -104, parent='body', zz=c['flipL_front'].z - 5)
    c.k('ballA', 'o', [(0, 0, 'lin'), (8, 0, 'lin'), (9, 1, 'lin'), (45, 1, 'lin'), (46, 0, 'lin')])
    c.k('ballA', 's', cat([(0, (0.3, 0.3)), (8, (0.3, 0.3), 'lin')], [(f, (v, v * 0.92)) for f, v in
                          [(14, 0.5), (20, 0.62), (26, 0.78), (32, 0.86), (40, 1.0)]]))
    fx(c, 'ballB', p_snowball(), 124, -76, parent='flipRx', zz=c['flipR_front'].z + 5)
    c.k('ballB', 'o', [(0, 0, 'lin'), (45, 0, 'lin'), (46, 1, 'lin'), (59, 1, 'lin'), (60, 0, 'lin')])
    bx, by = 336, 236
    fx(c, 'ballC', p_snowball(), bx, by, scale=ROOT_S)
    c.k('ballC', 'o', [(0, 0, 'lin'), (59.9, 0, 'lin'), (60, 1, 'lin'), (74, 1, 'lin'), (74.1, 0, 'lin')])
    c.k('ballC', 's', [(0, 0.8), (60, 0.8, 'lin'), (74, 3.6, 'in')])
    c.k('ballC', 'p', [(0, (0, 0)), (60, (0, 0), 'lin'), (74, (256 - bx, 250 - by), 'out')])
    c.k('ballC', 'r', [(0, 0), (60, 0, 'lin'), (74, 160, 'lin')])
    for i in range(9):
        a = math.radians(i * 40 + 10)
        d = 86 + (i % 3) * 18
        nm = f'flake{i}'
        if i % 3 == 0:
            particle(c, nm, e_snowflake(9), 256, 250, 74, 22, (math.cos(a) * d, math.sin(a) * d), s0=0.6, s1=1.3,
                     spin=90, fade=2)
        else:
            particle(c, nm, e_puff(9 if i % 2 else 7), 256, 250, 74, 20, (math.cos(a) * d, math.sin(a) * d),
                     s0=1.4, s1=0.6, fade=2)
    c.k('rock', 'r', cat([(0, 0), (42, 0), (54, -5), (60, 6, 'inq'), (68, 0)], wave(76, 124, 6, 5)))
    c.k('breath', 's', cat([(0, (1, 1)), (76, (1, 1))], cyc(76, 124, 6, (1, 1), (1.04, 0.95)), [(150, (1, 1))]))
    eyes(c, segs=[(76, 'squint'), (126, 'open')])
    beak(c, [(4, 'o'), (44, 'smile'), (58, 'squawk'), (66, 'o'), (76, 'squawk'), (126, 'smile')])
    return c

@clip
def fun_fish_catch():
    c = new('fun_fish_catch', 'fun', 120)
    UP = M(look(0.15, -1), {'head.p': (0, -6), 'head.r': -3})
    GULP = {'head.p': (0, -10), 'head.r': 2, 'face.p': (0, -10), 'patch.p': (0, -5), 'body.s': (1.02, 0.98)}
    HAPPY = {'cheekL.s': (1.25, 1.25), 'cheekR.s': (1.25, 1.25), 'flipL.r': 26, 'flipR.r': -26}
    c.poses([(0, {}), (14, UP), (30, UP), (34, M(UP, {'body.s': (1.05, 0.95)})), (44, {}),
             (50, GULP), (56, M(GULP, {'body.s': (1.08, 0.94)})), (62, HAPPY), (96, HAPPY), (110, {}), (120, {})])
    c.k('root', 'p', cat([(0, (0, 0)), (62, (0, 0))], jitter(62, 96, 2.2, 2), [(120, (0, 0))]))
    c.k('flipLx', 'r', cat([(0, 0)], cyc(64, 96, 4, 0, 24), [(120, 0)]))
    c.k('flipRx', 'r', cat([(0, 0)], cyc(64, 96, 4, 0, -24), [(120, 0)]))
    beak(c, [(18, 'squawk'), (31, 'smile'), (62, 'tongue'), (106, 'smile')])
    eyes(c, segs=[(46, 'happy'), (104, 'open')])
    tx_, ty_ = 258, 236
    fx(c, 'fishA', p_fish(), tx_, ty_, scale=ROOT_S)
    c.k('fishA', 'o', [(0, 0, 'lin'), (6, 0, 'lin'), (7, 1, 'lin'), (30, 1, 'lin'), (30.5, 0, 'lin')])
    c.k('fishA', 'p', [(0, (170, -300)), (6, (170, -300), 'lin'), (16, (110, -170), 'out'), (24, (46, -64), 'in'),
                       (30, (0, 0), 'in')])
    c.k('fishA', 'r', [(0, -120), (6, -120, 'lin'), (30, -360, 'lin')])
    fx(c, 'fishB', p_fish(), 0, -276, parent='face', zz=c['beak_smile'].z + 5, op=0)
    c.k('fishB', 'o', [(0, 0, 'lin'), (30.4, 0, 'lin'), (30.5, 1, 'lin'), (50, 1, 'lin'), (50.5, 0, 'lin')])
    c.k('fishB', 'r', cat([(0, 0), (30, 0)], wave(30, 46, 4, 12), [(50, 0)]))
    c.k('fishB', 's', [(0, (1, 1)), (44, (1, 1)), (50, (0.2, 0.6), 'in')])
    c.k('fishB', 'p', [(0, (0, 0)), (44, (0, 0)), (50, (0, 6), 'in')])
    twinkle(c, 'spk0', 170, 180, [64, 84], size=11)
    twinkle(c, 'spk1', 346, 166, [72, 90], size=11)
    return c
