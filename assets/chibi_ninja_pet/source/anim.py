"""Authoring helpers on top of core.Clip"""
import math
from core import Clip, EASE
from rig import build_scene

_SCENE = build_scene(clones=True)
NODES = {n.name: n for n in _SCENE.walk()}

EYES = ['open', 'sleepy', 'happy', 'sharp', 'squint', 'wink', 'heart', 'big', 'dot', 'spiral', 'meh']
BROWS = ['det', 'angry', 'sad', 'worried', 'up', 'calm']
MOUTHS = ['smile', 'grin', 'frown', 'o', 'shout', 'yawn', 'pout', 'flat', 'wavy']
HANDS = ['fist', 'open', 'peace', 'point']

def _zero(prop):
    return {'p': (0.0, 0.0), 'r': 0.0, 's': (100.0, 100.0), 'o': 100.0, 'p2': (0.0, 0.0), 'r2': 0.0, 's2': (100.0, 100.0)}[prop]

class A(Clip):
    def __init__(s, name, cat, N, loop, desc='', pre=''):
        super().__init__(name, cat, N, loop, desc); s.pre = pre
    # ---- poses: dict keys "node.prop"; prop R = absolute rotation (deg) converted to offset from rest
    def seq(s, poses, pre=None):
        pre = s.pre if pre is None else pre
        props = []
        for _, pd, _ in poses:
            for k in pd:
                if k not in props: props.append(k)
        state = {}
        for t, pd, e in poses:
            for k in props:
                if k in pd: state[k] = pd[k]
                node, prop = k.split('.')
                if k not in state:
                    state[k] = (NODES[pre + node].r0 if prop == 'R' else _zero(prop))
                v = state[k]
                if prop == 'R': s.k(pre + node, 'r', [(t, v - NODES[pre + node].r0, e)])
                else: s.k(pre + node, prop, [(t, tuple(v) if isinstance(v, (list, tuple)) else v, e)])
        return s
    # ---- switch helpers (hold keys on opacity)
    def _switch(s, group, choices, timeline, default, pre=None):
        pre = s.pre if pre is None else pre
        used = {default} | {v for _, v in timeline}
        for c in choices:
            if c not in used: continue
            node = pre + group.format(c)
            keys = [(0, 100 if c == default else 0, 'hold')]
            for t, v in timeline: keys.append((t, 100 if v == c else 0, 'hold'))
            s.k(node, 'o', keys)
    def face(s, timeline, pre=None):
        """timeline: [(t, dict(eyes=, brows=, mouth=, blush=))] - only given fields change"""
        ev, bv, mv, blv = [], [], [], []
        for t, d in timeline:
            if 'eyes' in d: ev.append((t, d['eyes']))
            if 'brows' in d: bv.append((t, d['brows']))
            if 'mouth' in d: mv.append((t, d['mouth'] or 'none'))
            if 'blush' in d: blv.append((t, d['blush']))
        if ev: s._switch('eyes_{}', EYES, ev, 'open', pre)
        if bv: s._switch('brows_{}', BROWS, bv, 'det', pre)
        if mv: s._switch('mouth_{}', MOUTHS, mv, 'none', pre)
        if blv:
            p = s.pre if pre is None else pre
            s.k(p + 'blush', 'o', [(0, 0, 'hold')] + [(t, 100 if b else 0, 'hold') for t, b in blv])
        return s
    def hands(s, timeline, pre=None):
        for side in 'LR':
            tl = [(t, d[side]) for t, d in timeline if side in d]
            if tl: s._switch('hand' + side + '_{}', HANDS, tl, 'fist', pre)
        return s
    def vis(s, node, timeline, start=0):
        s.k(node, 'o', [(0, start, 'hold')] + [(t, 100 if on else 0, 'hold') for t, on in timeline])
        return s
    def blink(s, t, pre=None):
        p = s.pre if pre is None else pre
        s.k(p + 'eyes_open', 's2', [(t, (100, 100), 'in'), (t + 2, (100, 8), 'out'), (t + 5, (100, 100), 'io')])
        return s
    # ---- oscillation over the whole clip (keys at extremes, sine-like easing)
    def osc(s, node, prop, amp, period, phase=0.0, center=None, t0=None, t1=None):
        center = _zero(prop) if center is None else center
        N = s.N
        keys = []
        k0 = math.floor((-period) / (period / 2)) - 2
        k = k0
        while True:
            t = (phase + 0.25 + k * 0.5) * period
            if t > N + period: break
            sign = 1 if k % 2 == 0 else -1
            if isinstance(center, tuple):
                v = tuple(c + sign * a for c, a in zip(center, amp))
            else: v = center + sign * amp
            keys.append((t, v, 'sine'))
            k += 1
        s.k(node, prop, keys)
        return s
    def wave(s, nodes, amp, period, lag=0.12, prop='r2', base_phase=0.0):
        for j, nd in enumerate(nodes):
            s.osc(nd, prop, amp * (1 + 0.35 * j), period, base_phase + lag * j)
        return s
    # ---- effect pop: visible [t0,t1), scale pops in and shrinks out
    def pop(s, node, t0, t1, pos=None, peak=100, inn=5, outt=5, rot=None, pos_keys=None, scale=None):
        s.k(node, 'o', [(0, 0, 'hold'), (t0, 100, 'hold'), (t1, 0, 'hold')])
        if scale is not None:
            s.k(node, 's', scale)
        else:
            pk = peak if isinstance(peak, tuple) else (peak, peak)
            s.k(node, 's', [(0, (0, 0), 'hold'), (t0, (0, 0), 'out'), (t0 + inn, (pk[0] * 1.15, pk[1] * 1.15), 'io'), (t0 + inn + 3, pk, 'hold'),
                            (t1 - outt, pk, 'in'), (t1, (0, 0), 'hold')])
        if pos_keys: s.k(node, 'p', pos_keys)
        elif pos is not None: s.k(node, 'p', [(t0, tuple(pos), 'hold'), (t1, tuple(pos), 'hold')])
        if rot: s.k(node, 'r', rot)
        return s
    def puff(s, node, t0, t1, pos, size=100):
        """smoke puff: burst in, expand, fade by shrinking"""
        s.k(node, 'o', [(0, 0, 'hold'), (t0, 100, 'hold'), (t1, 0, 'hold')])
        s.k(node, 's', [(0, (0, 0), 'hold'), (t0, (20, 20), 'snap'), (t0 + 5, (size, size), 'io'), (t0 + (t1 - t0) * 0.55, (size * 1.08, size * 1.08), 'in'), (t1, (0, 0), 'hold')])
        s.k(node, 'p', [(t0, tuple(pos), 'out'), (t1, (pos[0], pos[1] - 14), 'hold')])
        s.k(node, 'r', [(t0, -8, 'out'), (t1, 10, 'hold')])
        return s
    # ---- standard life: breathing + scarf/headband breeze
    def breathe(s, period, amp=1.0, pre=None):
        p = s.pre if pre is None else pre
        s.osc(p + 'torso', 's2', (0.8 * amp, -2.6 * amp), period, 0.5, (100, 100))
        s.osc(p + 'head', 'p2', (0, 1.6 * amp), period, 0.5)
        s.osc(p + 'armL', 'r2', -2.5 * amp, period, 0.5)
        s.osc(p + 'armR', 'r2', 2.5 * amp, period, 0.5)
        return s
    def breeze(s, period, amp=6, pre=None, droop=False):
        p = s.pre if pre is None else pre
        s.wave([p + 'scarf1', p + 'scarf2', p + 'scarf3'], amp, period, 0.14)
        s.wave([p + 'htailA1', p + 'htailA2'], amp * 1.1, period, 0.16, base_phase=0.3)
        s.wave([p + 'htailB1', p + 'htailB2'], amp * 1.1, period, 0.16, base_phase=0.45)
        return s
