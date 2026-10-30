"""All clip definitions."""
import math
from core import *
from rig import *

DEF = build_rig()
GS = {  # gill states: dr offsets for fronds 1..3 (top..bottom), ds
    'base': ([0, 0, 0], (1, 1)),
    'fan': ([-18, -4, 14], (1.12, 1.12)),
    'spike': ([-26, -3, 22], (1.24, 0.82)),
    'droop': ([56, 46, 36], (0.95, 0.95)),
    'back': ([-30, -36, -42], (1.04, 0.92)),
}
ORDER = {'gR1': 0, 'gR2': 2, 'gR3': 4, 'gL1': 1, 'gL2': 3, 'gL3': 5}
EYES_OPEN = ('eyeL_open', 'eyeR_open')
LEGS_F = ('legFL', 'legFR')
LEGS_B = ('legBL', 'legBR')
CLIPS = []


def clip(fn):
    CLIPS.append(fn)
    return fn


# ------------------------------------------------------------------ helpers
def new(name, cat, N, loop=True, pose='sit', start=None, end=None, desc=''):
    rig = build_rig()
    apply_pose(rig, start or pose)
    return Clip(name, cat, N, loop, rig, base_pose=pose, start_pose=start or pose, end_pose=end, desc=desc)


def add(a, b, sgn=1):
    if isinstance(a, tuple):
        return tuple(x + sgn * y for x, y in zip(a, b))
    return a + sgn * b


def osc(t0, t1, base, amp, half=None, M=None):
    if M is None:
        M = max(2, round((t1 - t0) / half))
    out = []
    for m in range(M + 1):
        t = t0 + (t1 - t0) * m / M
        if m in (0, M):
            v = base
        else:
            v = add(base, amp, 1 if m % 2 else -1)
        out.append((round(t, 3), v))
    return out


def ks(c, names, prop, kv, **kw):
    for n in (names if isinstance(names, (list, tuple)) else [names]):
        c.k(n, prop, kv, **kw)


def wave(c, key, prop, amp, cycles, delay=0.0, base=0.0):
    N = c.frames
    q = N / (4 * cycles)
    rel = [(0, base)]
    for j in range(2 * cycles):
        rel.append((q * (2 * j + 1), add(base, amp, 1 if j % 2 == 0 else -1)))
    rel.append((N, base))
    if delay:
        c.life(key, delay, {prop: rel})
    else:
        c.k(key, prop, rel)


def gill(c, t, state, names=GILL_NAMES, scale=True):
    drs, ds = GS[state]
    for n in names:
        c.k(n, 'dr', [(t, drs[int(n[2]) - 1])])
        if scale:
            c.k(n, 'ds', [(t, ds)])


def flutter(c, t0, t1, amp, half, stagger=2, state='base', names=GILL_NAMES):
    D = stagger * 5
    for n in names:
        d = stagger * ORDER[n]
        base = GS[state][0][int(n[2]) - 1]
        c.k(n, 'dr', osc(t0 + d, t1 - D + d, base, amp, half))


def blink(c, t, d=6, eyes=EYES_OPEN, sx=1.0, s0=1.0):
    for e in eyes:
        c.k(e, 'ds', [(t, (s0, s0)), (t + d / 2, (sx, 0.1)), (t + d, (s0, s0))])


def var(c, group, kv):
    init = None
    for v in VARIANTS[group]:
        if group == 'brows' and v == 'none':
            continue
        if c.rig.find(vnode(group, v)).o > 0.5:
            init = v
    init = init or 'none'
    seq = ([(0, init)] if kv[0][0] > 0 else []) + list(kv)
    for v in VARIANTS[group]:
        if group == 'brows' and v == 'none':
            continue
        c.k(vnode(group, v), 'o', [(t, 1.0 if x == v else 0.0) for t, x in seq], hold=True)


def eyes_var(c, kv):
    var(c, 'eyeL', kv); var(c, 'eyeR', kv)


def transition(c, A, B, t0, t1, ease=EIO):
    keys = set()
    for pz in (A, B):
        for k_, props in POSES[pz].items():
            for pr in props:
                keys.add((k_, pr))
    for k_, pr in sorted(keys):
        va = POSES[A].get(k_, {}).get(pr, default_val(DEF, k_, pr))
        vb = POSES[B].get(k_, {}).get(pr, default_val(DEF, k_, pr))
        c.k(k_, pr, [(t0, va), (t1, vb)], ease=ease)


def fx(c, parent, node, index=None):
    p = c.rig.find(parent)
    if index is None:
        p.children.append(node)
    else:
        p.children.insert(index, node)
    return node


def floater(c, parent, node, start, dur, p0, p1, s0=0.3, s1=1.0, fade_in=5, fade_out=8, sway=0, spin=0):
    fx(c, parent, node)
    node.p = p0
    rel = {'p': [(0, p0), (dur, p1)],
           'o': [(0, 0.0), (fade_in, 1.0), (dur - fade_out, 1.0), (dur, 0.0)],
           's': [(0, (s0, s0)), (min(8, dur / 2), (s1, s1)), (dur, (s1, s1))]}
    if sway:
        rel['dp'] = [(0, (0, 0)), (dur * 0.3, (sway, 0)), (dur * 0.7, (-sway, 0)), (dur, (0, 0))]
    if spin:
        rel['dr'] = [(0, 0), (dur, spin)]
    c.life(node.name, start, rel)
    return node


def bub(name, size):
    return bubble(name, BUBBLE_R.get(size, size) if isinstance(size, str) else size)


def dizzy(c, center, t0, t1, n=3, rx=82, ry=26):
    sq = ry / rx
    holders = []
    for j in range(n):
        a = 2 * math.pi * j / n
        st = star5(f'dz{j}_star', 1.0, o=1.0)
        un = Node(f'dz{j}_un', [st], s=(1, 1 / sq))
        cr = Node(f'dz{j}_cr', [un])
        holders.append(Node(f'dz{j}_h', [cr], p=(rx * math.cos(a), rx * math.sin(a))))
    rot = Node('dz_rot', holders)
    sqn = Node('dz_sq', [rot], s=(1, sq))
    top = Node('dizzy', [sqn], p=center, o=0.0)
    fx(c, 'fxWorld', top)
    c.k('dz_rot', 'dr', [(t0, 0), (t1, 720)])
    for j in range(n):
        c.k(f'dz{j}_cr', 'dr', [(t0, 0), (t1, -720)])
    c.k('dizzy', 'o', [(t0, 0.0), (t0 + 4, 1.0), (t1 - 6, 1.0), (t1, 0.0)])
    return top


def breathe(c, t0, t1, n, amt=(0.985, 1.025), node='squash'):
    step = (t1 - t0) / (2 * n)
    kv = []
    for j in range(2 * n + 1):
        kv.append((t0 + j * step, amt if j % 2 else (1, 1)))
    c.k(node, 'ds', kv)


# ================================================================== IDLE
@clip
def idle_breathe():
    c = new('idle_breathe', 'idle', 120, desc='Default loop: slow breathing, rippling gills, one blink, lazy tail swish.')
    breathe(c, 0, 120, 2)
    c.k('headRig', 'dp', [(0, (0, 0)), (30, (0, -4)), (60, (0, 0)), (90, (0, -4)), (120, (0, 0))])
    flutter(c, 0, 120, 6, 12, stagger=4)
    blink(c, 70)
    c.k('tail1', 'dr', [(0, 0), (40, 6), (80, -4), (120, 0)])
    c.k('tail2', 'dr', [(0, 0), (50, 8), (92, -6), (120, 0)])
    c.k('tail3', 'dr', [(0, 0), (60, 11), (102, -8), (120, 0)])
    return c


@clip
def idle_gill_wiggle():
    c = new('idle_gill_wiggle', 'idle', 75, desc='All six gills fan out wide, ripple twice, then settle.')
    gill(c, 0, 'base'); gill(c, 14, 'fan'); gill(c, 58, 'fan'); gill(c, 72, 'base')
    for n in GILL_NAMES:
        d = 1.5 * ORDER[n]
        base = GS['fan'][0][int(n[2]) - 1]
        c.k(n, 'dr', osc(14 + d, 58 - 7.5 + d, base, 11, M=5))
    c.k('squash', 'ds', [(0, (1, 1)), (10, (0.97, 1.03)), (16, (1.03, 0.97)), (24, (1, 1)), (58, (1, 1)), (66, (1.02, 0.98)), (75, (1, 1))])
    var(c, 'mouth', [(15, 'wobbly'), (58, 'smile')])
    c.k('headRig', 'dr', [(14, 0), (26, 3), (40, -3), (54, 0)])
    blink(c, 63)
    return c


@clip
def idle_look_left_right():
    c = new('idle_look_left_right', 'idle', 120, desc='Glances left, holds, then right; head and gills follow. A tiny "?" pops up.')
    c.k('eyes', 'dp', [(0, (0, 0)), (10, (-13, 0)), (42, (-13, 0)), (56, (13, 0)), (86, (13, 0)), (100, (0, 0))])
    c.k('face', 'dp', [(0, (0, 0)), (12, (-6, 0)), (42, (-6, 0)), (58, (6, 0)), (86, (6, 0)), (102, (0, 0))])
    c.k('headRig', 'dr', [(0, 0), (12, -4), (42, -4), (58, 4), (86, 4), (102, 0)])
    c.k('headRig', 'dp', [(0, (0, 0)), (12, (-5, 0)), (42, (-5, 0)), (58, (5, 0)), (86, (5, 0)), (102, (0, 0))])
    for n in GILL_NAMES:
        side = 1 if 'R' in n else -1
        lag = ORDER[n] * 0.6
        c.k(n, 'dr', [(0, 0), (8 + lag, 0), (18 + lag, 7 * side), (32 + lag, 0), (48 + lag, 0), (62 + lag, -7 * side),
                      (76 + lag, 0), (94 + lag, 0), (106 + lag, 4 * side), (117, 0)])
    blink(c, 47)
    q = fx(c, 'fxWorld', question('qmark'))
    q.p = (150, -425)
    c.k('qmark', 'o', [(88, 0.0), (92, 1.0), (108, 1.0), (115, 0.0)])
    c.k('qmark', 's', [(88, (0.2, 0.2)), (95, (1.15, 1.15)), (100, (1, 1)), (115, (0.8, 0.8))])
    c.k('qmark', 'dr', [(88, -20), (96, 8), (104, 0)])
    return c


@clip
def idle_yawn():
    c = new('idle_yawn', 'idle', 105, desc='Big yawn with squinting eyes; a small bubble floats out of its mouth.')
    c.k('headRig', 'dp', [(0, (0, 0)), (16, (0, -8)), (50, (0, -8)), (64, (0, 0))])
    c.k('headRig', 'dr', [(0, 0), (16, -3), (50, -3), (64, 0)])
    var(c, 'mouth', [(12, 'yawn'), (58, 'smile')])
    c.k('mouth_yawn', 'ds', [(12, (0.4, 0.3)), (26, (1, 1)), (46, (1.05, 1.05)), (57, (0.4, 0.3))])
    eyes_var(c, [(12, 'squint'), (58, 'open')])
    c.k('squash', 'ds', [(0, (1, 1)), (18, (0.97, 1.05)), (46, (0.97, 1.05)), (60, (1.02, 0.98)), (70, (1, 1))])
    ks(c, LEGS_F, 'dr', [(0, 0), (18, -28), (46, -28), (60, 0)])
    gill(c, 0, 'base'); gill(c, 18, 'fan'); gill(c, 46, 'fan'); gill(c, 64, 'base')
    floater(c, 'fxWorld', bub('yawnBubble', 13), 40, 56, (4, -212), (78, -425), s0=0.2, sway=10)
    blink(c, 84)
    return c


@clip
def idle_stretch():
    c = new('idle_stretch', 'idle', 90, desc='Front legs stretch out, back arches, tail goes straight up, gills spread.')
    ks(c, LEGS_F, 'dr', [(0, 0), (20, -78), (52, -78), (68, 0)])
    ks(c, LEGS_F, 'ds', [(0, (1, 1)), (20, (1, 1.28)), (52, (1, 1.28)), (68, (1, 1))])
    c.k('squash', 'ds', [(0, (1, 1)), (20, (1.06, 0.9)), (52, (1.06, 0.9)), (64, (0.97, 1.04)), (74, (1, 1))])
    c.k('headRig', 'dp', [(0, (0, 0)), (20, (0, 12)), (52, (0, 12)), (64, (0, -4)), (74, (0, 0))])
    c.k('tail1', 'dp', [(0, (0, 0)), (22, (42, 2)), (52, (42, 2)), (70, (0, 0))])
    c.k('tail1', 'dr', [(0, 0), (22, -44), (52, -44), (70, 0)])
    c.k('tail2', 'dr', [(0, 0), (24, 24), (52, 24), (70, 0)])
    c.k('tail3', 'dr', [(0, 0), (26, 38), (36, 34), (44, 40), (52, 38), (72, 0)])
    gill(c, 0, 'base'); gill(c, 20, 'fan'); gill(c, 52, 'fan'); gill(c, 66, 'base')
    eyes_var(c, [(14, 'squint'), (58, 'open')])
    var(c, 'mouth', [(14, 'o'), (58, 'smile')])
    c.k('mouth_o', 'ds', [(14, (0.6, 0.6)), (22, (1.15, 1.25)), (52, (1.15, 1.25)), (58, (1, 1))])
    blink(c, 78)
    return c


@clip
def idle_blow_bubbles():
    c = new('idle_blow_bubbles', 'idle', 150, desc='Blows three bubbles, then boops the last one with its snout and it pops.')
    var(c, 'mouth', [(8, 'o'), (98, 'smile'), (118, 'o'), (134, 'smile')])
    for t in (6, 36, 66):
        ks(c, ['cheekL', 'cheekR'], 'ds', [(t, (1, 1)), (t + 6, (1.32, 1.3)), (t + 11, (1, 1))])
        c.k('mouth_o', 'ds', [(t, (1, 1)), (t + 6, (0.7, 0.7)), (t + 11, (1.15, 1.15)), (t + 16, (1, 1))])
    floater(c, 'fxWorld', bub('b1', 's'), 16, 50, (0, -214), (-70, -430), s0=0.2, sway=8)
    floater(c, 'fxWorld', bub('b2', 'm'), 46, 54, (0, -214), (60, -440), s0=0.2, sway=10)
    b3 = fx(c, 'fxWorld', bub('b3', 'l'))
    b3.p = (0, -214)
    c.k('b3', 'p', [(76, (0, -214)), (98, (190, -250)), (150, (190, -250))])
    c.k('b3', 's', [(76, (0.2, 0.2)), (88, (1, 1)), (116, (1, 1)), (120, (1.4, 1.4))])
    c.k('b3', 'o', [(76, 0.0), (80, 1.0), (116, 1.0), (119, 0.0)])
    c.k('b3', 'dp', [(98, (0, 0)), (105, (0, -6)), (112, (0, 0))])
    bb = fx(c, 'fxWorld', burst('pop3', base_r=27))
    bb.p = (190, -250)
    c.k('pop3', 'o', [(116, 0.0), (118, 1.0), (126, 0.0)])
    c.k('pop3', 's', [(116, (0.8, 0.8)), (126, (1.35, 1.35))])
    c.k('eyes', 'dp', [(84, (0, 0)), (94, (12, 0)), (124, (12, 0)), (136, (0, 0))])
    c.k('headRig', 'dr', [(100, 0), (114, 11), (118, 12), (130, 0)])
    c.k('headRig', 'dp', [(100, (0, 0)), (114, (17, -4)), (118, (18, -4)), (130, (0, 0))])
    c.k('squash', 'ds', [(100, (1, 1)), (112, (0.98, 1.03)), (120, (1.03, 0.97)), (130, (1, 1))])
    eyes_var(c, [(117, 'squint'), (125, 'happy'), (140, 'open')])
    gill(c, 0, 'base'); gill(c, 116, 'base'); gill(c, 120, 'spike'); gill(c, 130, 'spike'); gill(c, 142, 'base')
    flutter(c, 0, 110, 5, 14, stagger=4)
    return c


# ================================================================== SWIM
SWIM_HEAD = (98, -232)    # approximate mouth/nose point in swim pose (character space)


@clip
def swim_idle():
    c = new('swim_idle', 'swim', 90, pose='swim', desc='Swims in place with slow tail strokes, gills streaming back, small bubbles rising.')
    wave(c, 'tail1', 'dr', 12, 2)
    wave(c, 'tail2', 'dr', 15, 2, delay=5)
    wave(c, 'tail3', 'dr', 19, 2, delay=10)
    wave(c, 'pose', 'dr', -2.5, 2)
    c.k('move', 'dp', [(0, (0, 0)), (45, (0, -9)), (90, (0, 0))])
    ks(c, LEGS_F + LEGS_B, 'dr', [(0, 0), (22, 8), (45, 0), (67, 8), (90, 0)])
    flutter(c, 0, 90, 5, 15, stagger=2)
    blink(c, 58)
    for j, (st, sz, dx) in enumerate([(0, 9, -20), (30, 7, 25), (60, 11, 0)]):
        floater(c, 'fxWorld', bub(f'sb{j}', sz), st, 52, (SWIM_HEAD[0] + 30, SWIM_HEAD[1] - 10),
                (SWIM_HEAD[0] + 40 + dx, SWIM_HEAD[1] - 200), s0=0.3, sway=8)
    c.k('shadow', 's', [(0, (0.6, 0.6)), (45, (0.56, 0.56)), (90, (0.6, 0.6))])
    return c


@clip
def sit_to_swim():
    c = new('sit_to_swim', 'swim', 45, loop=False, pose='sit', start='sit', end='swim',
            desc='Wiggles, floats up off the ground and rolls into the swimming pose.')
    c.k('pose', 'dr', [(0, 0), (3, 6), (6, -6), (9, 5), (12, 0)])
    flutter(c, 0, 14, 8, 3, stagger=0.5)
    c.k('squash', 'ds', [(0, (1, 1)), (8, (1.06, 0.94)), (14, (0.95, 1.06)), (22, (1, 1))])
    transition(c, 'sit', 'swim', 10, 36)
    ks(c, ['tail1', 'tail2', 'tail3'], 'dr', [(10, 0), (24, -32), (36, 0)])
    return c


@clip
def swim_to_sit():
    c = new('swim_to_sit', 'swim', 45, loop=False, pose='sit', start='swim', end='sit',
            desc='Drifts down and lands sitting with a soft squash.')
    transition(c, 'swim', 'sit', 0, 24)
    ks(c, ['tail1', 'tail2', 'tail3'], 'dr', [(0, 0), (12, -32), (24, 0)])
    c.k('squash', 'ds', [(0, (1, 1)), (24, (1, 1)), (28, (1.12, 0.88)), (34, (0.97, 1.03)), (39, (1, 1))])
    flutter(c, 24, 39, 7, 4, stagger=0.5)
    return c


# ================================================================== SLEEP
@clip
def sleep_fall_asleep():
    c = new('sleep_fall_asleep', 'sleep', 75, loop=False, pose='sit', start='sit', end='lie',
            desc='Eyes droop, lies down on its belly with its chin on its front feet, gills droop flat.')
    ks(c, EYES_OPEN, 'ds', [(0, (1, 1)), (12, (1, 0.5)), (18, (1, 0.66)), (26, (1, 0.12))])
    eyes_var(c, [(26, 'sleepy')])
    c.k('headRig', 'dp', [(6, (0, 0)), (13, (0, 9)), (20, (0, 0))])
    transition(c, 'sit', 'lie', 26, 56)
    c.k('noseBubble', 'o', [(56, 0.0), (64, 1.0)])
    c.k('squash', 'ds', [(56, (1, 1)), (60, (1.04, 0.96)), (66, (1, 1))])
    return c


@clip
def sleep_loop():
    c = new('sleep_loop', 'sleep', 120, pose='lie', desc='Asleep on its belly: slow breathing, gills rise and fall, rising "z z z", a nose bubble.')
    breathe(c, 0, 120, 2, amt=(1.02, 1.035))
    c.k('headRig', 'dp', [(0, (0, 0)), (30, (0, -4)), (60, (0, 0)), (90, (0, -4)), (120, (0, 0))])
    ks(c, GILL_NAMES, 'dr', [(0, 0), (30, -8), (60, 0), (90, -8), (120, 0)])
    c.k('noseBubble', 'ds', [(0, (1, 1)), (30, (2.2, 2.2)), (60, (1, 1)), (90, (2.2, 2.2)), (120, (1, 1))])
    for j, (st, sc) in enumerate([(4, 0.9), (44, 1.1), (84, 1.3)]):
        floater(c, 'fxWorld', letter_z(f'z{j}', sc), st, 62, (120, -268), (195, -430), s0=0.4, s1=1.0,
                fade_in=8, fade_out=14, sway=10)
    return c


@clip
def sleep_wake_up():
    c = new('sleep_wake_up', 'sleep', 75, loop=False, pose='sit', start='lie', end='sit',
            desc='Nose bubble pops, gills spike out startled, two quick blinks, stretch, back to sitting.')
    c.k('noseBubble', 'ds', [(0, (1, 1)), (6, (2.6, 2.6)), (9, (3.1, 3.1))])
    c.k('noseBubble', 'o', [(0, 1.0), (7, 1.0), (9, 0.0)])
    b = fx(c, 'fxWorld', burst('popNose', base_r=18))
    b.p = (28, -158)
    c.k('popNose', 'o', [(7, 0.0), (9, 1.0), (16, 0.0)])
    c.k('popNose', 's', [(7, (0.7, 0.7)), (16, (1.4, 1.4))])
    eyes_var(c, [(9, 'open')])
    ks(c, EYES_OPEN, 'ds', [(9, (1.22, 1.22)), (15, (1.22, 1.22)), (17, (1.22, 0.12)), (19, (1.15, 1.15)),
                            (22, (1.1, 0.12)), (25, (1, 1))])
    gill(c, 0, 'base'); gill(c, 9, 'spike'); gill(c, 20, 'spike'); gill(c, 30, 'fan'); gill(c, 46, 'fan'); gill(c, 60, 'base')
    var(c, 'mouth', [(9, 'o'), (30, 'wobbly'), (56, 'smile')])
    c.k('move', 'dp', [(8, (0, 0)), (11, (0, -18)), (16, (0, 0))])
    transition(c, 'lie', 'sit', 26, 50)
    ks(c, LEGS_F, 'dr', [(30, 0), (42, -55), (50, -55), (60, 0)])
    c.k('squash', 'ds', [(40, (1, 1)), (48, (0.95, 1.06)), (56, (1.02, 0.98)), (62, (1, 1))])
    c.k('tail1', 'dr', [(30, 0), (44, -40), (60, 0)])
    return c


# ================================================================== MOVEMENT
@clip
def move_walk():
    c = new('move_walk', 'movement', 40, desc='Wiggly lizard walk in place, body curving in an S, gills bobbing. The app moves the window.')
    c.k('pose', 'dr', [(0, 0), (10, 7), (20, 0), (30, -7), (40, 0)])
    c.k('headRig', 'dr', [(0, 0), (10, -7), (20, 0), (30, 7), (40, 0)])
    c.k('tail1', 'dr', [(0, 0), (10, -14), (20, 0), (30, 14), (40, 0)])
    wave(c, 'tail2', 'dr', -16, 1, delay=3)
    wave(c, 'tail3', 'dr', -20, 1, delay=6)
    c.k('move', 'dp', [(t, (0, -6 if t % 10 == 5 else 0)) for t in range(0, 41, 5)])
    for pair, t0 in ((('legFR', 'legBL'), 0), (('legFL', 'legBR'), 10), (('legFR', 'legBL'), 20), (('legFL', 'legBR'), 30)):
        ks(c, pair, 'dp', [(t0, (0, 0)), (t0 + 5, (0, -13)), (t0 + 10, (0, 0))])
        ks(c, pair, 'dr', [(t0, 0), (t0 + 5, -14), (t0 + 10, 0)])
    flutter(c, 0, 40, 7, 5, stagger=1)
    c.k('squash', 'ds', [(t, (1.025, 0.975) if t % 10 == 0 and t not in (0, 40) else (1, 1)) for t in range(0, 41, 5)])
    return c


@clip
def move_hop():
    c = new('move_hop', 'movement', 36, desc='Crouch, jump with gills flared at the top, squash on landing.')
    c.k('squash', 'ds', [(0, (1, 1)), (7, (1.16, 0.82)), (11, (0.88, 1.16)), (17, (1, 1)), (24, (1, 1)), (27, (0.94, 1.07)),
                         (30, (1.2, 0.8)), (33, (0.97, 1.03)), (36, (1, 1))])
    c.k('move', 'dp', [(0, (0, 0)), (9, (0, 0)), (18, (0, -95)), (28, (0, 0))])
    c.k('headRig', 'dp', [(0, (0, 0)), (7, (0, 10)), (11, (0, -6)), (17, (0, 0)), (28, (0, 0)), (30, (0, 10)), (36, (0, 0))])
    gill(c, 0, 'base'); gill(c, 8, 'back'); gill(c, 18, 'spike'); gill(c, 26, 'back'); gill(c, 31, 'droop'); gill(c, 36, 'base')
    ks(c, LEGS_F, 'dr', [(9, 0), (18, 22), (27, 0)])
    ks(c, LEGS_B, 'dr', [(9, 0), (18, 28), (27, 0)])
    c.k('tail1', 'dr', [(0, 0), (7, 15), (18, -25), (28, 10), (36, 0)])
    c.k('tail3', 'dr', [(0, 0), (9, 10), (20, -20), (30, 12), (36, 0)])
    c.k('shadow', 's', [(0, (1, 1)), (9, (1, 1)), (18, (0.6, 0.6)), (28, (1, 1))])
    c.k('shadow', 'o', [(0, 1.0), (9, 1.0), (18, 0.5), (28, 1.0)])
    eyes_var(c, [(11, 'happy'), (28, 'squint'), (33, 'open')])
    var(c, 'mouth', [(11, 'open'), (30, 'smile')])
    return c


@clip
def move_swim():
    c = new('move_swim', 'movement', 30, pose='swim', desc='Fast swim in place, tail kicking hard, legs tucked, a stream of bubbles behind. The app moves the window.')
    wave(c, 'tail1', 'dr', 22, 2)
    wave(c, 'tail2', 'dr', 26, 2, delay=2)
    wave(c, 'tail3', 'dr', 32, 2, delay=4)
    wave(c, 'pose', 'dr', -4, 2)
    c.k('move', 'dp', [(0, (0, 0)), (15, (0, -5)), (30, (0, 0))])
    ks(c, LEGS_F + LEGS_B, 'ds', [(0, (0.9, 0.9))])
    flutter(c, 0, 30, 6, 3.75, stagger=0.5)
    for j in range(4):
        y = -150 - 28 * (j % 2)
        floater(c, 'fxWorld', bub(f'trail{j}', 10 if j % 2 else 7), j * 7.5, 24, (-70, y - 150), (-240, y - 230),
                s0=0.4, fade_in=3, fade_out=6, sway=5)
    return c


@clip
def move_fall_land():
    c = new('move_fall_land', 'movement', 75, loop=False, pose='sit', start='sit', end='sit',
            desc='Drops in from above with gills flapping, belly-flops with a big squash, dizzy stars, then sits up.')
    c.k('move', 'dp', [(0, (0, -640), (0.5, 0, 0.8, 0.8)), (16, (0, 0))])
    ks(c, LEGS_F, 'dr', [(0, -120), (13, -120), (18, 0)])
    for n in GILL_NAMES:
        base = GS['back'][0][int(n[2]) - 1]
        c.k(n, 'dr', osc(0, 16, base, 24, M=6) + [(22, GS['spike'][0][int(n[2]) - 1]), (32, 0)])
    ks(c, GILL_NAMES, 'ds', [(0, (1.04, 0.92)), (16, (1.04, 0.92)), (22, (1.24, 0.82)), (32, (1, 1))])
    transition(c, 'sit', 'lie', 16, 21)
    c.k('squash', 'ds', [(16, (1, 1)), (19, (1.28, 0.68)), (26, (0.95, 1.05)), (32, (1, 1))])
    c.k('shadow', 's', [(0, (0.3, 0.3)), (16, (1.0, 1.0)), (19, (1.25, 1.1)), (21, (1.18, 1.0))])
    c.k('shadow', 'o', [(0, 0.15), (16, 1.0)])
    dizzy(c, (0, -300), 22, 66)
    c.k('dizzy', 'dp', [(44, (0, 0)), (60, (0, -104))])
    eyes_var(c, [(0, 'squint'), (30, 'open')])
    blink(c, 52)
    var(c, 'mouth', [(0, 'open'), (18, 'wobbly'), (62, 'smile')])
    transition(c, 'lie', 'sit', 44, 60)
    c.k('squash', 'ds', [(56, (1, 1)), (60, (1.05, 0.95)), (65, (1, 1))])
    return c


# ================================================================== INTERACTION
@clip
def int_dragged():
    c = new('int_dragged', 'interaction', 60, pose='drag', desc='Held under the arms, dangling long like a noodle, tail swinging, gills swept back, surprised face.')
    wave(c, 'pose', 'dr', 6, 1)
    wave(c, 'tail1', 'dr', 14, 1, delay=5)
    wave(c, 'tail2', 'dr', 16, 1, delay=9)
    wave(c, 'tail3', 'dr', 20, 1, delay=13)
    wave(c, 'legBL', 'dr', 9, 2, delay=3)
    wave(c, 'legBR', 'dr', -9, 2, delay=3)
    wave(c, 'legFL', 'dr', 5, 2)
    wave(c, 'legFR', 'dr', 5, 2)
    flutter(c, 0, 60, 5, 7.5, stagger=1)
    ks(c, EYES_OPEN, 'ds', [(0, (1.12, 1.12)), (35, (1.12, 1.12)), (38, (1.12, 0.12)), (41, (1.12, 1.12)), (60, (1.12, 1.12))])
    c.k('body', 'ds', [(0, (1, 1)), (15, (0.97, 1.03)), (45, (1.02, 0.98)), (60, (1, 1))])
    return c


@clip
def int_petted():
    c = new('int_petted', 'interaction', 60, desc='Happy ^ ^ eyes, gills flutter fast and blush darker pink, hearts pop up.')
    eyes_var(c, [(4, 'happy'), (54, 'open')])
    var(c, 'mouth', [(4, 'wobbly'), (54, 'smile')])
    c.k('gill', 'fill', [(0, GILL), (10, GILL_BLUSH), (46, GILL_BLUSH), (56, GILL)])
    flutter(c, 4, 56, 9, 3, stagger=1)
    c.k('headRig', 'dr', [(0, 0), (12, 6), (24, -4), (36, 6), (48, -4), (58, 0)])
    c.k('squash', 'ds', [(0, (1, 1)), (10, (1.04, 0.96)), (50, (1.04, 0.96)), (58, (1, 1))])
    ks(c, ['cheekL', 'cheekR'], 'ds', [(4, (1, 1)), (12, (1.25, 1.25)), (48, (1.25, 1.25)), (56, (1, 1))])
    for j, (st, p0) in enumerate([(8, (-120, -360)), (20, (125, -375)), (32, (-30, -420))]):
        floater(c, 'fxWorld', heart(f'h{j}', 1.0), st, 24, p0, (p0[0] * 1.15, p0[1] - 60), s0=0.3, s1=1.0, sway=6)
    return c


@clip
def int_poked():
    c = new('int_poked', 'interaction', 45, desc='Puffs up round like a ball, gills spike out, puffed cheeks, angry brows, anger mark.')
    c.k('squash', 'ds', [(0, (1, 1)), (5, (1.18, 1.06)), (34, (1.18, 1.06)), (42, (1, 1))])
    c.k('body', 'ds', [(0, (1, 1)), (5, (1.3, 1.22)), (34, (1.3, 1.22)), (42, (1, 1))])
    ks(c, LEGS_F, 'dr', [(0, 0), (5, -24), (34, -24), (42, 0)])
    c.k('pose', 'dr', osc(5, 34, 0, 2, M=14))
    gill(c, 0, 'base'); gill(c, 5, 'spike'); gill(c, 34, 'spike'); gill(c, 42, 'base')
    ks(c, ['cheekL', 'cheekR'], 'ds', [(0, (1, 1)), (5, (1.45, 1.45)), (34, (1.45, 1.45)), (42, (1, 1))])
    var(c, 'brows', [(5, 'angry'), (38, 'none')])
    var(c, 'mouth', [(5, 'tight'), (38, 'smile')])
    ks(c, EYES_OPEN, 'ds', [(0, (1, 1)), (5, (1, 0.84)), (34, (1, 0.84)), (40, (1, 1))])
    a = fx(c, 'headRig', anger('angerMark'))
    a.p = (-74, -376)
    c.k('angerMark', 'o', [(4, 0.0), (7, 1.0), (32, 1.0), (36, 0.0)])
    c.k('angerMark', 'ds', [(4, (0.3, 0.3)), (8, (1.15, 1.15)), (12, (0.95, 0.95)), (16, (1.15, 1.15)), (20, (0.95, 0.95)),
                            (24, (1.15, 1.15)), (28, (1, 1)), (36, (0.6, 0.6))])
    return c


@clip
def int_tickled():
    c = new('int_tickled', 'interaction', 48, desc='Wriggles and laughs with eyes squeezed shut, legs kicking, gills wiggling.')
    eyes_var(c, [(3, 'squint'), (44, 'open')])
    var(c, 'mouth', [(3, 'open'), (44, 'smile')])
    c.k('pose', 'dr', osc(3, 45, 0, 8, 6))
    c.k('headRig', 'dr', osc(3, 45, 0, -5, 6))
    c.k('move', 'dp', [(t, (0, -8 if t % 12 == 6 else 0)) for t in range(0, 49, 6)])
    c.k('legFL', 'dr', osc(3, 45, 0, 26, 4)); c.k('legFR', 'dr', osc(3, 45, 0, -26, 4))
    c.k('legBL', 'dr', osc(3, 45, 0, -20, 4)); c.k('legBR', 'dr', osc(3, 45, 0, 20, 4))
    flutter(c, 3, 47, 14, 3, stagger=0.8)
    c.k('tail1', 'dr', osc(3, 45, 0, 16, 4))
    c.k('tail3', 'dr', osc(5, 45, 0, 20, 4))
    c.k('squash', 'ds', [(t, (1.04, 0.96) if t % 12 == 0 and t not in (0, 48) else (1, 1)) for t in range(0, 49, 6)])
    return c


LOOK_DIRS = [('up', 0, -1), ('up_right', 0.71, -0.71), ('right', 1, 0), ('down_right', 0.71, 0.71),
             ('down', 0, 1), ('down_left', -0.71, 0.71), ('left', -1, 0), ('up_left', -0.71, -0.71)]


def make_look(d, dx, dy):
    def f():
        c = new(f'int_look_{d}', 'interaction', 60, desc=f'Eyes held looking {d.replace("_", "-")} with light breathing (cursor follow).')
        c.rig.find('eyes').dp = (dx * 16, dy * 13)
        c.rig.find('face').dp = (dx * 7, dy * 5)
        hr = c.rig.find('headRig')
        hr.dr = dx * 4
        hr.dp = (dx * 5, dy * 5)
        breathe(c, 0, 60, 1, amt=(0.99, 1.02))
        flutter(c, 0, 60, 4, 15, stagger=3)
        return c
    f.__name__ = f'int_look_{d}'
    return f


for _d, _x, _y in LOOK_DIRS:
    clip(make_look(_d, _x, _y))


# ================================================================== MOODS
@clip
def mood_happy():
    c = new('mood_happy', 'mood', 60, desc='Bouncy wiggle dance with gills fanned wide and sparkles.')
    c.k('move', 'dp', [(t, (0, -22 if t % 15 == 7 else 0)) for t in (0, 7, 15, 22, 30, 37, 45, 52, 60)])
    sq = [(0, (1, 1))]
    for b in range(4):
        tb = 15 * b
        if b:
            sq.append((tb, (1.07, 0.93)))
        sq.append((tb + 7, (0.96, 1.05)))
    sq.append((60, (1, 1)))
    c.k('squash', 'ds', sq)
    c.k('pose', 'dr', [(0, 0), (15, 8), (30, 0), (45, -8), (60, 0)])
    c.k('headRig', 'dr', [(0, 0), (15, -4), (30, 0), (45, 4), (60, 0)])
    gill(c, 0, 'base'); gill(c, 4, 'fan'); gill(c, 56, 'fan'); gill(c, 60, 'base')
    for n in GILL_NAMES:
        base = GS['fan'][0][int(n[2]) - 1]
        c.k(n, 'dr', osc(4 + ORDER[n], 56 - 5 + ORDER[n], base, 8, 5))
    eyes_var(c, [(4, 'happy'), (56, 'open')])
    var(c, 'mouth', [(4, 'open'), (56, 'smile')])
    ks(c, LEGS_F, 'dr', [(0, 0), (6, -70), (13, -40), (21, -70), (28, -40), (36, -70), (43, -40), (51, -70), (58, 0)])
    c.k('tail1', 'dr', osc(2, 58, 0, 14, 7))
    spots = [(-175, -360), (180, -330), (-185, -170), (190, -190)]
    for j, p in enumerate(spots):
        s = fx(c, 'fxWorld', sparkle(f'sp{j}', 1.1))
        s.p = p
        c.life(f'sp{j}', 4 + 14 * j, {'o': [(0, 0.0), (3, 1.0), (13, 1.0), (16, 0.0)],
                                       's': [(0, (0.2, 0.2)), (8, (1.2, 1.2)), (16, (0.3, 0.3))],
                                       'r': [(0, 0), (16, 90)]})
    return c


@clip
def mood_sad():
    c = new('mood_sad', 'mood', 120, desc='Gills droop, sad brows and frown; a teardrop turns into a bubble and floats away.')
    gill(c, 0, 'base'); gill(c, 16, 'droop'); gill(c, 100, 'droop'); gill(c, 116, 'base')
    var(c, 'brows', [(6, 'worried'), (108, 'none')])
    var(c, 'mouth', [(8, 'frown'), (108, 'smile')])
    c.k('headRig', 'dp', [(0, (0, 0)), (16, (0, 10)), (100, (0, 10)), (114, (0, 0))])
    c.k('headRig', 'dr', [(0, 0), (16, -3), (100, -3), (114, 0)])
    c.k('squash', 'ds', [(0, (1, 1)), (16, (1.03, 0.96)), (60, (1.02, 0.965)), (100, (1.03, 0.96)), (114, (1, 1))])
    c.k('eyes', 'dp', [(0, (0, 0)), (16, (0, 5)), (100, (0, 5)), (112, (0, 0))])
    blink(c, 70)
    t = fx(c, 'headRig', teardrop('tear'))
    t.p = (-82, -246)
    c.k('tear', 'o', [(20, 0.0), (24, 1.0), (50, 1.0), (54, 0.0)])
    c.k('tear', 's', [(20, (0.2, 0.2)), (28, (1, 1))])
    c.k('tear', 'p', [(20, (-82, -246)), (30, (-84, -242)), (50, (-98, -206))])
    floater(c, 'fxWorld', bub('tearBubble', 12), 48, 56, (-98, -197), (-180, -430), s0=0.6, fade_in=6, fade_out=12, sway=9)
    return c


@clip
def mood_surprised():
    c = new('mood_surprised', 'mood', 54, desc='Gills shoot straight out, big round eyes, "o" mouth, "!" mark.')
    c.k('move', 'dp', [(0, (0, 0)), (4, (0, -16)), (10, (0, 0))])
    c.k('squash', 'ds', [(0, (1, 1)), (4, (0.92, 1.1)), (10, (1.06, 0.95)), (15, (1, 1))])
    gill(c, 0, 'base'); gill(c, 5, 'spike'); gill(c, 38, 'spike'); gill(c, 50, 'base')
    ks(c, EYES_OPEN, 'ds', [(0, (1, 1)), (5, (1.25, 1.25)), (38, (1.25, 1.25)), (48, (1, 1))])
    var(c, 'mouth', [(4, 'o'), (42, 'smile')])
    c.k('mouth_o', 'ds', [(4, (0.5, 0.5)), (8, (1.2, 1.2)), (12, (1.05, 1.05)), (38, (1.05, 1.05)), (42, (1, 1))])
    b = fx(c, 'fxWorld', bang('bang'))
    b.p = (160, -430)
    c.k('bang', 'o', [(4, 0.0), (7, 1.0), (38, 1.0), (44, 0.0)])
    c.k('bang', 's', [(4, (0.2, 0.2)), (9, (1.3, 1.3)), (13, (1, 1))])
    c.k('bang', 'dr', [(9, 0), (13, 12), (17, -8), (21, 0)])
    return c


@clip
def mood_hungry():
    c = new('mood_hungry', 'mood', 90, desc='Rubs its belly, with a thought bubble showing a little shrimp.')
    ks(c, LEGS_F, 'dr', [(0, 0), (10, 40), (18, 26), (26, 46), (34, 26), (42, 46), (50, 26), (58, 46), (66, 26), (74, 40), (82, 0)])
    ks(c, LEGS_F, 'dp', [(0, (0, 0)), (10, (0, -14)), (18, (0, -4)), (26, (0, -14)), (34, (0, -4)), (42, (0, -14)),
                         (50, (0, -4)), (58, (0, -14)), (66, (0, -4)), (74, (0, -14)), (82, (0, 0))])
    for nm, pos, r, t0 in (('dot1', (112, -372), 6, 8), ('dot2', (136, -400), 9, 12)):
        d = fx(c, 'fxWorld', Node(nm, [S(nm + '_c', circle(0, 0, r), fill=WHITE, stroke=OUT, sw=4.2)], p=pos, o=0.0))
        c.k(nm, 'o', [(t0, 0.0), (t0 + 3, 1.0), (72, 1.0), (80, 0.0)])
        c.k(nm, 's', [(t0, (0.3, 0.3)), (t0 + 5, (1, 1))])
    cl = fx(c, 'fxWorld', cloud('thought', 54, 40))
    cl.p = (178, -448)
    sh = shrimp('shrimp', 1.1)
    sh.p = (0, 0)
    cl.children.append(sh)
    c.k('thought', 'o', [(16, 0.0), (20, 1.0), (72, 1.0), (80, 0.0)])
    c.k('thought', 's', [(16, (0.4, 0.4)), (22, (1.06, 1.06)), (26, (1, 1)), (80, (0.8, 0.8))])
    c.k('shrimp', 'dr', osc(22, 72, 0, 8, 8))
    c.k('eyes', 'dp', [(0, (0, 0)), (10, (9, -8)), (76, (9, -8)), (84, (0, 0))])
    var(c, 'mouth', [(10, 'open'), (78, 'smile')])
    ks(c, GILL_NAMES, 'dr', [(0, 0), (14, 14), (76, 14), (86, 0)])
    c.k('headRig', 'dr', [(0, 0), (12, 5), (78, 5), (86, 0)])
    blink(c, 46)
    return c


@clip
def mood_love():
    c = new('mood_love', 'mood', 90, desc='Heart eyes; the top gill fronds curve inward to frame a floating heart; more hearts drift up.')
    eyes_var(c, [(4, 'heart'), (84, 'open')])
    pulse = [(4, (1, 1))] + [(4 + 7.5 * j, (1.15, 1.15) if j % 2 else (1, 1)) for j in range(1, 11)]
    ks(c, ['eyeL_heart', 'eyeR_heart'], 'ds', pulse)
    ks(c, ['gR1', 'gL1'], 'dr', [(0, 0), (16, -80), (74, -80), (86, 0)])
    ks(c, ['gR1', 'gL1'], 'ds', [(0, (1, 1)), (16, (1.05, 1.1)), (74, (1.05, 1.1)), (86, (1, 1))])
    flutter(c, 4, 84, 6, 10, stagger=2, names=['gR2', 'gR3', 'gL2', 'gL3'])
    h = fx(c, 'fxWorld', heart('bigHeart', 1.0))
    h.p = (0, -436)
    c.k('bigHeart', 'o', [(14, 0.0), (20, 1.0), (76, 1.0), (82, 0.0)])
    c.k('bigHeart', 's', [(14, (0.3, 0.3)), (22, (1.75, 1.75))] + [(22 + 8 * j, (1.5, 1.5) if j % 2 else (1.75, 1.75)) for j in range(1, 7)] + [(82, (1, 1))])
    c.k('bigHeart', 'dp', [(14, (0, 0)), (34, (0, -6)), (54, (0, 0)), (74, (0, -6)), (82, (0, 0))])
    for j, (st, p0, p1) in enumerate([(20, (-150, -300), (-190, -430)), (38, (150, -300), (192, -440)), (56, (-120, -330), (-150, -455))]):
        floater(c, 'fxWorld', heart(f'lh{j}', 0.8), st, 26, p0, p1, s0=0.3, sway=6)
    ks(c, ['cheekL', 'cheekR'], 'ds', [(4, (1, 1)), (12, (1.25, 1.25)), (80, (1.25, 1.25)), (88, (1, 1))])
    var(c, 'mouth', [(4, 'wobbly'), (84, 'smile')])
    c.k('pose', 'dr', [(0, 0), (22, 4), (45, 0), (67, -4), (90, 0)])
    c.k('headRig', 'dr', [(0, 0), (22, 3), (45, 0), (67, -3), (90, 0)])
    return c


@clip
def mood_smile_wink():
    c = new('mood_smile_wink', 'mood', 60, desc='Big open smile with tongue, playful wink with a sparkle, excited tail wag.')
    var(c, 'mouth', [(4, 'open'), (52, 'smile')])
    c.k('mouth_open', 'ds', [(4, (0.6, 0.6)), (10, (1.12, 1.12)), (14, (1, 1))])
    var(c, 'eyeR', [(14, 'wink'), (36, 'open')])
    c.k('headRig', 'dr', [(0, 0), (10, 0), (16, 7), (36, 7), (44, 0)])
    sp = fx(c, 'headRig', sparkle('winkSparkle', 1.0))
    sp.p = (118, -306)
    c.k('winkSparkle', 'o', [(14, 0.0), (17, 1.0), (32, 1.0), (36, 0.0)])
    c.k('winkSparkle', 'ds', [(14, (0.2, 0.2)), (19, (1.25, 1.25)), (24, (0.9, 0.9)), (28, (1.1, 1.1)), (36, (0.4, 0.4))])
    c.k('winkSparkle', 'dr', [(14, 0), (36, 90)])
    c.k('tail1', 'dr', osc(6, 54, 0, 20, 4))
    c.k('tail2', 'dr', osc(7, 54, 0, 14, 4))
    c.k('tail3', 'dr', osc(8, 54, 0, 18, 4))
    c.k('squash', 'ds', [(0, (1, 1)), (4, (1.05, 0.95)), (10, (0.97, 1.03)), (14, (1, 1))])
    flutter(c, 4, 56, 8, 4, stagger=1)
    return c


# ================================================================== FUN
@clip
def fun_spin():
    c = new('fun_spin', 'fun', 60, desc='Rolls into the swim pose, spins with a ring of bubbles, then lands back sitting with a squash.')
    transition(c, 'sit', 'swim', 0, 12)
    transition(c, 'swim', 'sit', 36, 48)
    c.k('pose', 'r', [(0, 0), (12, 84), (36, 444), (48, 360)])
    c.k('pose', 's', [(12, (1, 1)), (18, (0.74, 0.74)), (32, (0.74, 0.74)), (40, (1, 1))])
    c.k('move', 'dp', [(12, (0, 0)), (24, (-30, -30)), (36, (0, 0))])
    c.k('squash', 'ds', [(0, (1, 1)), (48, (1, 1)), (51, (1.14, 0.86)), (55, (0.97, 1.03)), (60, (1, 1))])
    eyes_var(c, [(12, 'happy'), (46, 'open')])
    var(c, 'mouth', [(10, 'open'), (50, 'smile')])
    cx, cy = 40, -214
    for j in range(8):
        a = math.radians(j * 45 + 22.5)
        b = fx(c, 'fxWorld', bub(f'ring{j}', 11 if j % 2 else 8))
        p0 = (cx + 70 * math.cos(a), cy + 70 * math.sin(a))
        p1 = (cx + 215 * math.cos(a), cy + 200 * math.sin(a))
        b.p = p0
        c.k(b.name, 'p', [(18, p0), (42, p1)])
        c.k(b.name, 'o', [(18, 0.0), (22, 1.0), (36, 1.0), (42, 0.0)])
        c.k(b.name, 's', [(18, (0.4, 0.4)), (28, (1, 1))])
    flutter(c, 48, 60, 7, 3, stagger=0.5)
    return c


@clip
def fun_peek():
    c = new('fun_peek', 'fun', 90, pose='hidden', desc='Rises from the bottom edge so only gills and eyes show, blinks, then sinks back with bubbles.')
    c.k('move', 'p', [(0, (0, 560)), (10, (0, 560)), (28, (0, 282)), (60, (0, 282)), (78, (0, 560)), (90, (0, 560))])
    flutter(c, 24, 64, 7, 6, stagger=1)
    c.k('eyes', 'dp', [(28, (0, 0)), (32, (-12, 0)), (40, (-12, 0)), (46, (12, 0)), (52, (12, 0)), (56, (0, 0))])
    blink(c, 41)
    blink(c, 53)
    for j, (st, x) in enumerate([(10, -60), (15, 70), (20, -10), (60, 90), (64, -80), (68, 20)]):
        floater(c, 'fxWorld', bub(f'pb{j}', 8 + 3 * (j % 3)), st, 22, (x, 60), (x + 15, -150), s0=0.4, fade_in=3, fade_out=7, sway=6)
    return c


@clip
def fun_notify():
    c = new('fun_notify', 'fun', 60, desc='Holds up a big bubble with a round yellow "!" badge inside it, happy open mouth.')
    nb = bubble('notifyBubble', 66, fo=0.45, sw=6, center=(0, -118))
    nb.children.append(Node('badgeRig', [badge('badge')], a=(0, 0), p=(0, -118)))
    nb.a = (0, -60); nb.p = (0, -60)
    char = c.rig.find('char')
    idx = [i for i, ch in enumerate(char.children) if isinstance(ch, Node) and ch.name == 'frontL'][0]
    char.children.insert(idx, nb)
    c.k('notifyBubble', 's', [(0, (0.1, 0.1)), (10, (1.08, 1.08)), (14, (1, 1)), (48, (1, 1)), (56, (0.1, 0.1))])
    c.k('notifyBubble', 'o', [(0, 0.0), (4, 1.0), (52, 1.0), (56, 0.0)])
    c.k('notifyBubble', 'dp', [(0, (0, 30)), (12, (0, -14)), (31, (0, -8)), (48, (0, -14)), (56, (0, 30))])
    c.k('badge', 'ds', [(14, (1, 1)), (20, (1.14, 1.14)), (26, (1, 1)), (32, (1.14, 1.14)), (38, (1, 1))])
    c.k('badge', 'dr', [(14, 0), (20, -8), (26, 6), (32, -8), (38, 0)])
    ks(c, LEGS_F, 'dr', [(0, 0), (12, 34), (48, 34), (56, 0)])
    ks(c, LEGS_F, 'dp', [(0, (0, 0)), (12, (14, -40)), (31, (14, -34)), (48, (14, -40)), (56, (0, 0))])
    var(c, 'mouth', [(6, 'open'), (54, 'smile')])
    c.k('squash', 'ds', [(0, (1, 1)), (12, (0.98, 1.03)), (31, (1.01, 0.99)), (48, (0.98, 1.03)), (58, (1, 1))])
    gill(c, 0, 'base'); gill(c, 10, 'fan'); gill(c, 50, 'fan'); gill(c, 58, 'base')
    blink(c, 34)
    return c


@clip
def fun_bubble_ride():
    c = new('fun_bubble_ride', 'fun', 120, desc='Hops into a big bubble, floats up, the bubble pops and it drops back to sitting with a squash.')
    rb = bubble('rideBubble', 232, fo=0.2, sw=7, center=(0, -200))
    rb.a = (0, 30); rb.p = (0, 30)
    c.rig.find('move').children.append(rb)
    c.k('rideBubble', 's', [(0, (0.05, 0.05)), (10, (0.05, 0.05)), (26, (1.04, 1.04)), (30, (1, 1)), (84, (1, 1)), (88, (1.15, 1.15))])
    c.k('rideBubble', 'o', [(8, 0.0), (12, 1.0), (85, 1.0), (88, 0.0)])
    c.k('squash', 'ds', [(0, (1, 1)), (8, (1.12, 0.86)), (13, (0.92, 1.1)), (22, (0.9, 0.9)), (84, (0.9, 0.9)),
                         (90, (0.96, 1.05)), (98, (1, 1)), (101, (1.18, 0.84)), (106, (0.97, 1.03)), (112, (1, 1))])
    c.k('move', 'dp', [(0, (0, 0)), (8, (0, 0)), (18, (0, -60)), (26, (0, -34)), (44, (-12, -56)), (62, (12, -74)),
                       (80, (0, -84)), (86, (0, -84)), (98, (0, 0))])
    ks(c, LEGS_F + LEGS_B, 'dr', [(10, 0), (22, 24), (84, 24), (94, 0)])
    eyes_var(c, [(20, 'happy'), (86, 'open')])
    ks(c, EYES_OPEN, 'ds', [(0, (1, 1)), (85, (1, 1)), (86, (1.22, 1.22)), (96, (1.22, 1.22)), (104, (1, 1))])
    var(c, 'mouth', [(18, 'open'), (86, 'o'), (106, 'smile')])
    gill(c, 0, 'base'); gill(c, 86, 'base'); gill(c, 88, 'spike'); gill(c, 98, 'spike'); gill(c, 110, 'base')
    flutter(c, 24, 84, 7, 8, stagger=2)
    b = fx(c, 'move', burst('rideBurst', r1=1.04, r2=1.15, n=12, base_r=232))
    b.p = (0, -200)
    c.k('rideBurst', 'o', [(85, 0.0), (87, 1.0), (95, 0.0)])
    c.k('rideBurst', 's', [(85, (1, 1)), (95, (1.12, 1.12))])
    c.k('shadow', 's', [(8, (1, 1)), (18, (0.7, 0.7)), (80, (0.6, 0.6)), (98, (1, 1))])
    c.k('shadow', 'o', [(8, 1.0), (18, 0.6), (80, 0.5), (98, 1.0)])
    return c
