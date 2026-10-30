"""The axolotl rig, props and base poses.

Character space: origin = ground point between the feet, y down. Drawn at 100% and placed on the
canvas by `world` at (256, 470) with 80% scale.
"""
import math
from core import *

# ---------------------------------------------------------------- palette
OUT = '#4A2C3A'        # plum-brown outline
PINK = '#FFC4D6'       # body
BELLY = '#FFE7EA'      # cream-pink belly
GILL = '#F2719F'       # coral-magenta gills
GILL_BLUSH = '#DA407C'
GILL_LINE = '#D9507F'
CHEEK = '#FF93B3'
EYE = '#3A2130'
WHITE = '#FFFFFF'
MOUTH = '#9E3A60'
TONGUE = '#FF8FAE'
FIN = '#FFE0EA'
FIN_LINE = '#F5A9C2'
LILAC = '#C9A8F0'
LILAC_DARK = '#A585D6'
YELLOW = '#FFDD73'
BUBBLE = '#CDEEFF'
HEART = '#FF6F96'
TEAR = '#A3D9F5'
ANGER = '#FF5C7C'
SHRIMP = '#FFA08C'
SHRIMP_DARK = '#EE7C6C'

SW = 7.5    # main outline (x0.8 world scale = 6px)
SWS = 5.5   # small details


def S(name, subs, **kw):
    return Shape(name, subs, **kw)


# ---------------------------------------------------------------- parts
def frond_subs(L, w):
    top = [(-18, -9), (L * 0.2, -w * 0.72), (L * 0.42, -w), (L * 0.64, -w * 0.97), (L * 0.84, -w * 0.68)]
    pts = top + [(L + 2, 0)] + [(x, -y) for x, y in reversed(top)]
    return scallop(pts, lambda k: 0 if k == len(pts) - 1 else (7.5 if k in (len(top) - 1, len(top)) else 6.5))


def frond(name, base, ang, L, w):
    body = S(name + '_shape', frond_subs(L, w), fill=GILL, stroke=OUT, sw=SW - 0.5, cid='gill')
    vein = S(name + '_vein', P(f'M 2 0 C {L*.3} -3 {L*.55} -3 {L*.78} 0'), stroke=GILL_LINE, sw=3.6)
    barbs = S(name + '_barbs', P(f'M {L*.34} -2 L {L*.42} -{w*.5} M {L*.56} -2 L {L*.64} -{w*.48} '
                                 f'M {L*.34} 0 L {L*.42} {w*.5} M {L*.56} 0 L {L*.64} {w*.48}'), stroke=GILL_LINE, sw=3)
    return Node(name, [body, vein, barbs], a=(0, 0), p=base, r=ang)


def leg_subs(sx=1.0, sy=1.0):
    leg = P('M -15 0 C -15 -13 15 -13 15 0 L 16 33 C 16 50 -16 50 -16 33 Z')
    toes = circle(-11, 43, 6.8) + circle(0, 47, 6.8) + circle(11, 43, 6.8)
    m = m_s(sx, sy)
    return xf(toes, m), xf(leg, m)


def leg(name, hip, ang, sx=1.0, sy=1.0):
    toes, body = leg_subs(sx, sy)
    return Node(name, [S(name + '_toes', toes, fill=PINK, stroke=OUT, sw=SW - 1.5),
                       S(name + '_leg', body, fill=PINK, stroke=OUT, sw=SW)], a=(0, 0), p=hip, r=ang)


TAIL = [  # (length, start half-width, end half-width, top fin heights, bottom fin heights)
    (70, 28, 22, (8, 13), (0, 4)),
    (62, 22, 16, (13, 16), (5, 9)),
    (58, 16, 5, (16, 9), (9, 6)),
]
TAIL_BASE = (52, -50)
TAIL_R = (-12, -30, -42)


def seg_subs(L, wa, wb):
    return P(f'M 0 {-wa} L {L} {-wb} C {L + wb * 1.35} {-wb} {L + wb * 1.35} {wb} {L} {wb} '
             f'L 0 {wa} C {-wa * 1.35} {wa} {-wa * 1.35} {-wa} 0 {-wa} Z')


def fin_subs(L, wa, wb, h, sign):
    """A scalloped fin band riding the top (sign=-1) or bottom (sign=+1) edge."""
    h0, h1 = h
    if h0 == 0 and h1 == 0:
        return []
    n = 3
    pts_out = []
    for j in range(n + 1):
        t = j / n
        x = -6 + (L + 10) * t
        w = wa + (wb - wa) * t
        hh = h0 + (h1 - h0) * t
        pts_out.append((x, sign * (w + hh)))
    inner = [(L + 6, sign * (wb - 7)), (-6, sign * (wa - 7))]
    pts = pts_out + inner
    if sign > 0:
        pts = list(reversed(pts_out)) + list(reversed(inner))
    bumps = [5] * (len(pts_out) - 1) + [0, 0, 0]
    return scallop(pts, lambda k: bumps[k] if k < len(bumps) else 0)


def tail_chain(suffix, mode):
    """mode: 'out' = silhouette outline pass, 'fin' = fin fill, 'body' = body fill."""
    nxt = None
    for idx in (2, 1, 0):
        L, wa, wb, ft, fb = TAIL[idx]
        name = f'tail{idx + 1}{suffix}'
        seg = seg_subs(L, wa, wb)
        fins = fin_subs(L, wa, wb, ft, -1) + fin_subs(L, wa, wb, fb, +1)
        kids = []
        if mode == 'out':
            kids.append(S(name + '_o', fins + seg, fill=OUT, stroke=OUT, sw=SW * 2))
        elif mode == 'fin':
            if fins:
                kids.append(S(name + '_fin', fins, fill=FIN))
                rays = []
                for j in (0.25, 0.55, 0.85):
                    x = L * j
                    w = wa + (wb - wa) * j
                    h = ft[0] + (ft[1] - ft[0]) * j
                    rays.append(f'M {x} {-w + 2} L {x + 3} {-w - h + 4}')
                kids.append(S(name + '_rays', P(' '.join(rays)), stroke=FIN_LINE, sw=2.6))
        else:
            kids.append(S(name + '_fill', seg, fill=PINK))
        if nxt is not None:
            kids.append(nxt)
        pos = TAIL_BASE if idx == 0 else (TAIL[idx - 1][0], 0)
        nxt = Node(name, kids, a=(0, 0), p=pos, r=TAIL_R[idx], alias=f'tail{idx + 1}' if suffix else None)
    return nxt


def heart_subs(sc=1.0):
    h = P('M 0 13 C -6 8 -17 1 -17 -6 C -17 -12 -12.5 -16 -8 -16 C -4 -16 -1 -13.5 0 -10 '
          'C 1 -13.5 4 -16 8 -16 C 12.5 -16 17 -12 17 -6 C 17 1 6 8 0 13 Z')
    return xf(h, m_s(sc))


def eye(name, x, y, side):
    kids = [
        Node(name + '_open', [
            S(name + '_iris', ellipse(0, 0, 23, 27), fill=EYE, stroke=EYE, sw=2),
            S(name + '_hl1', circle(7.5, -10, 8.5), fill=WHITE),
            S(name + '_hl2', circle(-8, 9.5, 4.2), fill=WHITE)]),
        Node(name + '_sleepy', [S(name + '_sleepy_l', P('M -20 -3 C -12 13 12 13 20 -3'), stroke=OUT, sw=7)], o=0),
        Node(name + '_happy', [S(name + '_happy_l', P('M -20 7 C -12 -13 12 -13 20 7'), stroke=OUT, sw=7)], o=0),
        Node(name + '_squint', [S(name + '_squint_l', xf(P('M -15 -14 L 13 0 L -15 14'), m_s(-side, 1)), stroke=OUT, sw=7)], o=0),
        Node(name + '_wink', [S(name + '_wink_l', xf(P('M -20 4 C -10 -9 10 -9 20 4 M 20 4 L 28 -2'), m_s(side, 1)), stroke=OUT, sw=7)], o=0),
        Node(name + '_heart', [S(name + '_heart_s', heart_subs(1.45), fill=HEART, stroke=OUT, sw=SWS),
                               S(name + '_heart_hl', ellipse(-11, -11, 4.5, 3.2), fill=WHITE)], o=0),
    ]
    return Node(name, kids, a=(0, 0), p=(x, y))


def mouths():
    def fill_stroke(name, subs, extra=()):
        return [S(name + '_f', subs, fill=MOUTH)] + list(extra) + [S(name + '_s', subs, stroke=OUT, sw=6)]
    open_ = P('M -24 -6 C -10 -2 10 -2 24 -6 C 22 22 -22 22 -24 -6 Z')
    yawn = ellipse(0, 10, 20, 28)
    kids = [
        Node('mouth_smile', [S('mouth_smile_l', P('M -34 -5 C -18 9 18 9 34 -5'), stroke=OUT, sw=6.5)]),
        Node('mouth_open', fill_stroke('mouth_open', open_, [S('mouth_open_t', ellipse(0, 13, 12, 6.5), fill=TONGUE)]), o=0),
        Node('mouth_o', fill_stroke('mouth_o', ellipse(0, 3, 10, 12)), o=0),
        Node('mouth_yawn', fill_stroke('mouth_yawn', yawn, [S('mouth_yawn_t', ellipse(0, 27, 12, 8), fill=TONGUE)]), o=0),
        Node('mouth_frown', [S('mouth_frown_l', P('M -20 8 C -10 -5 10 -5 20 8'), stroke=OUT, sw=6.5)], o=0),
        Node('mouth_wobbly', [S('mouth_wobbly_l', P('M -30 -5 C -24 10 -6 10 0 0 C 6 10 24 10 30 -5'), stroke=OUT, sw=6.5)], o=0),
        Node('mouth_tight', [S('mouth_tight_l', P('M -11 3 C -4 -1 4 -1 11 3'), stroke=OUT, sw=6)], o=0),
    ]
    # yawn grows from its top edge
    kids[3].a = (0, -18); kids[3].p = (0, -18)
    return Node('mouth', kids, a=(0, 0), p=(0, -229))


def flower(x, y):
    petals = []
    for j in range(5):
        a = math.radians(-90 + j * 72)
        petals += circle(10.5 * math.cos(a), 10.5 * math.sin(a), 9.5)
    return Node('flower', [S('flower_petals', petals, fill=LILAC, stroke=OUT, sw=5),
                           S('flower_center', circle(0, 0, 6.5), fill=YELLOW, stroke=OUT, sw=4)],
                a=(0, 0), p=(x, y), r=12)


# ---------------------------------------------------------------- props / effects
def bubble(name, r, fo=0.55, sw=None, o=0.0, center=(0, 0)):
    cx, cy = center
    sw = sw if sw is not None else max(3.6, min(6.5, r * 0.16))
    hl = xf(ellipse(0, 0, r * 0.26, r * 0.15), m_t(cx - r * 0.42, cy - r * 0.42), m_r(-45))
    kids = [S(name + '_b', circle(cx, cy, r), fill=BUBBLE, fo=fo, stroke=OUT, sw=sw),
            S(name + '_hl', hl, fill=WHITE, fo=0.95),
            S(name + '_hl2', circle(cx + r * 0.42, cy + r * 0.38, max(1.6, r * 0.08)), fill=WHITE, fo=0.9)]
    return Node(name, kids, o=o)


BUBBLE_R = {'s': 10, 'm': 17, 'l': 27}


def heart(name, sc=1.0, o=0.0):
    return Node(name, [S(name + '_s', heart_subs(sc), fill=HEART, stroke=OUT, sw=4.5),
                       S(name + '_hl', ellipse(-8 * sc, -8 * sc, 3.2 * sc, 2.2 * sc), fill=WHITE)], o=o)


def sparkle(name, sc=1.0, o=0.0, color=YELLOW):
    p = P('M 0 -15 C 2 -4 4 -2 15 0 C 4 2 2 4 0 15 C -2 4 -4 2 -15 0 C -4 -2 -2 -4 0 -15 Z')
    return Node(name, [S(name + '_s', xf(p, m_s(sc)), fill=color, stroke=OUT, sw=4)], o=o)


def star5(name, sc=1.0, o=0.0):
    pts = []
    for j in range(10):
        a = math.radians(-90 + j * 36)
        rr = 13 if j % 2 == 0 else 6
        pts.append((rr * math.cos(a) * sc, rr * math.sin(a) * sc))
    return Node(name, [S(name + '_s', scallop(pts, 0.8), fill=YELLOW, stroke=OUT, sw=4)], o=o)


def glyph(name, d, color=LILAC, w_out=11, w_in=4.8, dots=(), o=0.0):
    kids = [S(name + '_o', P(d), stroke=OUT, sw=w_out), S(name + '_i', P(d), stroke=color, sw=w_in)]
    for (x, y, r) in dots:
        kids.append(S(name + '_dot', circle(x, y, r), fill=color, stroke=OUT, sw=3.8))
    return Node(name, kids, o=o)


def letter_z(name, sc=1.0, o=0.0):
    s = sc
    return glyph(name, f'M {-9*s} {-9*s} L {9*s} {-9*s} L {-9*s} {9*s} L {9*s} {9*s}', w_out=10 * s, w_in=4.4 * s, o=o)


def bang(name, color=HEART, o=0.0):
    bar = P('M -6.5 -19 C -6.5 -26 6.5 -26 6.5 -19 L 4 3 C 3.5 7.5 -3.5 7.5 -4 3 Z')
    return Node(name, [S(name + '_bar', bar, fill=color, stroke=OUT, sw=4.5),
                       S(name + '_dot', circle(0, 15, 5.5), fill=color, stroke=OUT, sw=4.5)], o=o)


def question(name, o=0.0):
    return glyph(name, 'M -9 -9 C -9 -22 12 -22 12 -9 C 12 -1 1 -1 1 8', color=LILAC, dots=[(1, 19, 4.8)], o=o)


def anger(name, o=0.0):
    arcs = []
    for k in range(4):
        arcs.append(xf(P('M 4 -15 C 4 -7 7 -4 15 -4'), m_r(90 * k)))
    d_subs = [s for a in arcs for s in a]
    return Node(name, [S(name + '_o', d_subs, stroke=OUT, sw=10), S(name + '_i', d_subs, stroke=ANGER, sw=4.6)], o=o)


def burst(name, r1=1.0, r2=1.45, n=8, base_r=20, o=0.0):
    subs = []
    for k in range(n):
        a = math.radians(k * 360 / n + 22.5)
        subs += P(f'M {base_r*r1*math.cos(a)} {base_r*r1*math.sin(a)} L {base_r*r2*math.cos(a)} {base_r*r2*math.sin(a)}')
    return Node(name, [S(name + '_l', subs, stroke=OUT, sw=4.2)], o=o)


def teardrop(name, o=0.0):
    d = P('M 0 -15 C 4 -7 10 -1 10 6 C 10 12 5.5 16 0 16 C -5.5 16 -10 12 -10 6 C -10 -1 -4 -7 0 -15 Z')
    return Node(name, [S(name + '_s', d, fill=TEAR, stroke=OUT, sw=4.2),
                       S(name + '_hl', ellipse(-3.5, 6, 2.2, 3.5), fill=WHITE)], o=o)


def shrimp(name, sc=1.0, o=1.0):
    # curled body as a tapered band along an arc
    outer, inner = [], []
    cx, cy, R = 0, 4, 19
    a0, a1 = 200, -35
    n = 9
    for j in range(n + 1):
        t = j / n
        a = math.radians(a0 + (a1 - a0) * t)
        w = 7 + 6 * (1 - abs(t - 0.62) / 0.62) if t < 0.62 else 7 + 6 * (1 - (t - 0.62) / 0.38 * 0.6)
        outer.append((cx + (R + w) * math.cos(a), cy + (R + w) * math.sin(a)))
        inner.append((cx + (R - w * 0.75) * math.cos(a), cy + (R - w * 0.75) * math.sin(a)))
    body = smooth(outer + list(reversed(inner)), closed=True, t=0.16)
    tailx, taily = outer[0][0] - 2, outer[0][1] + 6
    fan = P(f'M {tailx+6} {taily-6} C {tailx-8} {taily-2} {tailx-10} {taily+8} {tailx-2} {taily+12} '
            f'C {tailx+2} {taily+8} {tailx+6} {taily+10} {tailx+10} {taily+14} '
            f'C {tailx+14} {taily+6} {tailx+12} {taily-2} {tailx+6} {taily-6} Z')
    hx, hy = outer[-1][0], outer[-1][1]
    segs = []
    for j in (3, 5, 7):
        segs += P(f'M {outer[j][0]} {outer[j][1]} Q {cx + R*math.cos(math.radians(a0+(a1-a0)*j/n))} '
                  f'{cy + R*math.sin(math.radians(a0+(a1-a0)*j/n))} {inner[j][0]} {inner[j][1]}')
    ant = P(f'M {hx-2} {hy+2} C {hx+10} {hy-6} {hx+16} {hy-14} {hx+12} {hy-24} '
            f'M {hx-4} {hy+4} C {hx+14} {hy+2} {hx+22} {hy-6} {hx+24} {hy-14}')
    legs = P(' '.join(f'M {inner[j][0]} {inner[j][1]} L {inner[j][0]*0.7} {inner[j][1]*0.7+4}' for j in (3, 4, 5, 6)))
    m = m_s(sc)
    kids = [S(name + '_ant', xf(ant, m), stroke=OUT, sw=2.6),
            S(name + '_legs', xf(legs, m), stroke=OUT, sw=2.6),
            S(name + '_fan', xf(fan, m), fill=SHRIMP_DARK, stroke=OUT, sw=3.6),
            S(name + '_body', xf(body, m), fill=SHRIMP, stroke=OUT, sw=3.8),
            S(name + '_segs', xf(segs, m), stroke=SHRIMP_DARK, sw=2.4),
            S(name + '_eye', xf(circle(outer[-2][0] * 0.82, outer[-2][1] * 0.82 + 1, 2.6), m), fill=OUT)]
    return Node(name, kids, o=o)


def cloud(name, rx=56, ry=42, o=0.0):
    pts = []
    n = 9
    for j in range(n):
        a = 2 * math.pi * j / n - math.pi / 2
        pts.append((rx * math.cos(a), ry * math.sin(a)))
    return Node(name, [S(name + '_c', scallop(pts, 11), fill=WHITE, stroke=OUT, sw=5)], o=o)


def badge(name, o=1.0):
    bar = P('M -5 -15 C -5 -20 5 -20 5 -15 L 3 3 C 2.6 6.5 -2.6 6.5 -3 3 Z')
    return Node(name, [S(name + '_c', circle(0, 0, 28), fill=YELLOW, stroke=OUT, sw=5),
                       S(name + '_hl', xf(ellipse(0, 0, 7, 4), m_t(-12, -14), m_r(-40)), fill=WHITE, fo=0.85),
                       S(name + '_bar', xf(bar, m_t(0, -2)), fill=OUT),
                       S(name + '_dot', circle(0, 13, 4.6), fill=OUT)], o=o)


# ---------------------------------------------------------------- character
GILLS = [('gR1', (118, -340), -40, 84, 20), ('gR2', (138, -300), -9, 94, 22), ('gR3', (140, -258), 21, 80, 19)]
GILL_NAMES = ['gR1', 'gR2', 'gR3', 'gL1', 'gL2', 'gL3']
EYE_POS = 64, -270
LEG_F = (40, -54)
LEG_B = (76, -34)


def build_rig():
    head_path = P('M 0 -392 C 96 -392 151 -347 151 -280 C 151 -214 96 -179 0 -179 '
                  'C -96 -179 -151 -214 -151 -280 C -151 -347 -96 -392 0 -392 Z')
    gR = [frond(n, b, a, L, w) for n, b, a, L, w in GILLS]
    gL = [frond(n.replace('R', 'L'), b, a, L, w) for n, b, a, L, w in GILLS]
    gillsR = Node('gillsR', list(reversed(gR)))
    gillsL = Node('gillsL', list(reversed(gL)), s=(-1, 1))
    ex, ey = EYE_POS
    face = Node('face', [
        Node('cheekL', [S('cheekL_s', ellipse(0, 0, 21, 12), fill=CHEEK, fo=0.92)], p=(-101, -235)),
        Node('cheekR', [S('cheekR_s', ellipse(0, 0, 21, 12), fill=CHEEK, fo=0.92)], p=(101, -235)),
        S('nostrils', circle(-11, -251, 2.6) + circle(11, -251, 2.6), fill=OUT),
        Node('eyes', [eye('eyeL', -ex, ey, -1), eye('eyeR', ex, ey, 1)]),
        Node('brows', [
            Node('brow_worried', [S('brow_worried_l', P('M -90 -309 L -50 -322 M 90 -309 L 50 -322'), stroke=OUT, sw=6.5)], o=0),
            Node('brow_angry', [S('brow_angry_l', P('M -90 -326 L -48 -308 M 90 -326 L 48 -308'), stroke=OUT, sw=7)], o=0),
        ]),
        mouths(),
    ])
    nose_bub = bubble('noseBubble', 13, fo=0.6, sw=4, center=(11, -11))
    nose_bub.a = (0, 0); nose_bub.p = (14, -248); nose_bub.s = (0.4, 0.4)
    head = Node('headRig', [
        gillsL, gillsR,
        S('head', head_path, fill=PINK, stroke=OUT, sw=SW),
        S('head_hl', xf(ellipse(0, 0, 26, 9), m_t(-62, -362), m_r(-14)), fill=WHITE, fo=0.55),
        flower(106, -360),
        face,
        nose_bub,
    ], a=(0, -182))
    body = Node('body', [
        S('body_s', P('M 0 -188 C 54 -188 93 -150 93 -96 C 93 -40 58 -12 0 -12 C -58 -12 -93 -40 -93 -96 C -93 -150 -54 -188 0 -188 Z'),
          fill=PINK, stroke=OUT, sw=SW),
        S('belly', ellipse(0, -84, 59, 55), fill=BELLY),
    ], a=(0, -12))
    char = Node('char', [
        tail_chain('', 'out'), tail_chain('f', 'fin'), tail_chain('b', 'body'),
        Node('backL', [leg('legBL', LEG_B, -58, 1.12, 0.86)], s=(-1, 1)),
        Node('backR', [leg('legBR', LEG_B, -58, 1.12, 0.86)]),
        body,
        Node('frontL', [leg('legFL', LEG_F, -6)], s=(-1, 1)),
        Node('frontR', [leg('legFR', LEG_F, -6)]),
        head,
    ])
    squash = Node('squash', [char])
    pose = Node('pose', [squash], a=(0, -200))
    move = Node('move', [pose])
    world = Node('world', [move, Node('fxWorld', [])], p=(256, 470), s=(0.8, 0.8))
    root = Node('root', [
        Node('shadow', [S('shadow_s', ellipse(0, 0, 112, 13), fill=OUT, fo=0.16)], p=(256, 472)),
        Node('fxBack', [], p=(256, 470), s=(0.8, 0.8)),
        world,
        Node('fxFront', []),
    ])
    return root


# ---------------------------------------------------------------- poses
# Values are pose-slot (p/r/s/o) settings; anything missing = rig default (the sitting pose).
POSES = {
    'sit': {},
    'swim': {
        'move': {'p': (40, -14)},
        'pose': {'r': 84},
        'headRig': {'r': -52},
        'legFL': {'r': 34, 's': (0.82, 0.78)}, 'legFR': {'r': 34, 's': (0.82, 0.78)},
        'legBL': {'r': 8, 's': (0.82, 0.8)}, 'legBR': {'r': 8, 's': (0.82, 0.8)},
        'tail1': {'p': (22, -44), 'r': 92}, 'tail2': {'r': -24}, 'tail3': {'r': -36},
        'gR1': {'r': 44}, 'gR2': {'r': 68}, 'gR3': {'r': 92},
        'gL1': {'r': -38}, 'gL2': {'r': -12}, 'gL3': {'r': 14},
        'shadow': {'s': (0.6, 0.6), 'o': 0.55},
    },
    'lie': {
        'headRig': {'p': (0, -78)},
        'body': {'s': (1.14, 0.6)},
        'legFL': {'p': (52, -30), 'r': 62}, 'legFR': {'p': (52, -30), 'r': 62},
        'legBL': {'p': (84, -22), 'r': -84}, 'legBR': {'p': (84, -22), 'r': -84},
        'tail1': {'p': (60, -30), 'r': 4}, 'tail2': {'r': -12}, 'tail3': {'r': -22},
        'gR1': {'r': 14}, 'gR2': {'r': 36}, 'gR3': {'r': 56},
        'gL1': {'r': 14}, 'gL2': {'r': 36}, 'gL3': {'r': 56},
        'shadow': {'s': (1.18, 1.0)},
    },
    'drag': {
        'move': {'p': (0, -112)},
        'body': {'p': (0, 46), 's': (0.82, 1.34)},
        'legBL': {'p': (60, 26), 'r': 8}, 'legBR': {'p': (60, 26), 'r': 8},
        'tail1': {'p': (38, 12), 'r': 40}, 'tail2': {'r': -48}, 'tail3': {'r': -58},
        'legFL': {'p': (96, -168), 'r': -128}, 'legFR': {'p': (96, -168), 'r': -128},
        'gR1': {'r': -66}, 'gR2': {'r': -44}, 'gR3': {'r': -22},
        'gL1': {'r': -66}, 'gL2': {'r': -44}, 'gL3': {'r': -22},
        'shadow': {'s': (0.62, 0.62), 'o': 0.5},
    },
    'hidden': {
        'move': {'p': (0, 560)},
        'shadow': {'o': 0},
    },
}
# eye/mouth variant opacities carried by poses
POSE_VARIANTS = {'lie': {'eyeL': 'sleepy', 'eyeR': 'sleepy'}, 'drag': {'mouth': 'o', 'brows': 'worried'}}
POSE_STATICS = {'lie': {'noseBubble': {'o': 1.0}}}


def default_val(rig, key, prop):
    n = rig.find_key(key)[0]
    return getattr(n, prop)


def pose_val(rig, pose, key, prop):
    return POSES[pose].get(key, {}).get(prop, None) if pose in POSES else None


def apply_pose(rig, pose):
    for n in rig.walk():
        for src in (POSES.get(pose, {}), POSE_STATICS.get(pose, {})):
            if n.key in src:
                for prop, v in src[n.key].items():
                    setattr(n, prop, v)
    for group, var in POSE_VARIANTS.get(pose, {}).items():
        set_variant_static(rig, group, var)


VARIANTS = {
    'eyeL': ['open', 'sleepy', 'happy', 'squint', 'wink', 'heart'],
    'eyeR': ['open', 'sleepy', 'happy', 'squint', 'wink', 'heart'],
    'mouth': ['smile', 'open', 'o', 'yawn', 'frown', 'wobbly', 'tight'],
    'brows': ['none', 'worried', 'angry'],
}
VARIANT_DEFAULT = {'eyeL': 'open', 'eyeR': 'open', 'mouth': 'smile', 'brows': 'none'}


def vnode(group, var):
    if group == 'brows':
        return f'brow_{var}'
    return f'{group}_{var}'


def set_variant_static(rig, group, var):
    for v in VARIANTS[group]:
        if group == 'brows' and v == 'none':
            continue
        rig.find(vnode(group, v)).o = 1.0 if v == var else 0.0
