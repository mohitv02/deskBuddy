"""Ghost rig: geometry, parts, props, effects and the scene builder."""
import math
from engine import (Path, PB, ellipse, poly, split_bez, Shape, Group, Layer, Track, S, wave, steps,
                    EASE, HOLD, lerp)

# ---------------------------------------------------------------- palette
INK = '#4b3f63'        # deep purple-grey outline
WHITE = '#fffdfa'      # marshmallow white
LAV = '#d9cdf5'        # pale lavender underside
BOW = '#cbb8f4'
BOW_KNOT = '#b7a0ee'
CHEEK = '#ffb6c9'
CHEEK_ROSY = '#ff97b4'
EYE = '#3f3554'
MOUTH = '#7b4a72'
TONGUE = '#ff9fba'
HL = '#ffffff'
YELLOW = '#ffd95a'
YELLOW_PALE = '#fff3b0'
PEACH = '#ffc8a2'
PINK = '#ffb3c8'
HEART = '#ff8fae'
MINT = '#bdeedd'
SKY = '#c4e6ff'
LANTERN = '#a897cc'
GLASS = '#fff5d2'
ANGER = '#f47b9b'
TINT_LOVE = '#ffe3ee'
TINT_WARM = '#fff0cf'
STICK = '#dcae80'
MALLOW = '#fffaf2'
TOAST = '#e9a868'

W = 7.5        # outline width in design units (x0.8 = 6px)
WE = 4.5       # effect outline width (world px)

BASE = (256.0, 291.0)  # body centre in canvas px at 80% scale
SC = 80.0
GROUND = 470.0


def pt(p):
    return (p[0], p[1])


# ---------------------------------------------------------------- helpers
def smooth(points, closed=False, tension=1.0):
    """Catmull-Rom through points -> cubic Path"""
    n = len(points)
    v, ii, oo = [], [], []
    for k in range(n):
        p = points[k]
        if closed:
            a, b = points[(k - 1) % n], points[(k + 1) % n]
        else:
            a = points[max(k - 1, 0)]
            b = points[min(k + 1, n - 1)]
        tx, ty = (b[0] - a[0]) / 6 * tension, (b[1] - a[1]) / 6 * tension
        v.append(p)
        ii.append((-tx, -ty))
        oo.append((tx, ty))
    if not closed:
        ii[0] = (0, 0)
        oo[-1] = (0, 0)
    return Path(v, ii, oo, closed)


def heart_path(s=1.0, cx=0, cy=0):
    b = PB(0, 10)
    b.C(-4, 6, -14, 0, -14, -6).C(-14, -12, -6, -15, 0, -8).C(6, -15, 14, -12, 14, -6).C(14, 0, 4, 6, 0, 10)
    return b.Z().map(lambda p: (cx + p[0] * s, cy + p[1] * s))


def star4(s, cx=0, cy=0):
    k = 0.14 * s
    b = PB(cx, cy - s)
    b.C(cx + k, cy - k, cx + k, cy - k, cx + s, cy)
    b.C(cx + k, cy + k, cx + k, cy + k, cx, cy + s)
    b.C(cx - k, cy + k, cx - k, cy + k, cx - s, cy)
    b.C(cx - k, cy - k, cx - k, cy - k, cx, cy - s)
    return b.Z()


def star5(r, cx=0, cy=0):
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.48
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return poly(pts, closed=True)


def drop_path(s=1.0, cx=0, cy=0):
    b = PB(0, -12)
    b.C(4, -4, 9, 1, 9, 6).C(9, 12, 5, 15, 0, 15).C(-5, 15, -9, 12, -9, 6).C(-9, 1, -4, -4, 0, -12)
    return b.Z().map(lambda p: (cx + p[0] * s, cy + p[1] * s))


def outlined(paths, fill, name, w=W, fo=1.0):
    return Shape(paths, fill=fill, stroke=INK, width=w, name=name, fill_opacity=fo)


def stroke(paths, name, w=W, color=INK):
    return Shape(paths, stroke=color, width=w, name=name)


def glyph(paths, color, name, w_in=7.0, w_out=13.0):
    """letters / symbols drawn as centre-line strokes: dark outline stroke under a pastel stroke"""
    return [Shape(paths, stroke=INK, width=w_out, name=name + '_o'),
            Shape(paths, stroke=color, width=w_in, name=name + '_i')]


# ---------------------------------------------------------------- glyphs (centred, ~24px tall)
def g_z(s=1.0):
    return [poly([(-8 * s, -9 * s), (8 * s, -9 * s), (-8 * s, 9 * s), (8 * s, 9 * s)])]


def g_excl(s=1.0):
    return [poly([(0, -13 * s), (0, 3 * s)]), poly([(0, 11 * s), (0, 11.4 * s)])]


def g_q(s=1.0):
    b = PB(-8 * s, -6 * s).C(-8 * s, -15 * s, 8 * s, -15 * s, 8 * s, -6 * s).C(8 * s, 0, 0, -1 * s, 0, 5 * s)
    return [b.open(), poly([(0, 12 * s), (0, 12.4 * s)])]


def g_B(s=1.0, x=0):
    f = lambda p: (x + p[0] * s, p[1] * s)
    stem = poly([(-7, -13), (-7, 13)]).map(f)
    top = PB(-7, -13).C(4, -13, 7, -11, 7, -6.5).C(7, -2, 4, 0, -7, 0).open().map(f)
    bot = PB(-7, 0).C(6, 0, 9, 2.5, 9, 6.5).C(9, 11, 5, 13, -7, 13).open().map(f)
    return [stem, top, bot]


def g_O(s=1.0, x=0):
    return [ellipse(x, 0, 9 * s, 13 * s)]


def g_note(s=1.0):
    stem = PB(4 * s, 6 * s).L(4 * s, -12 * s).C(8 * s, -9 * s, 12 * s, -8 * s, 12 * s, -3 * s).open()
    return stem


# ---------------------------------------------------------------- body
BODY_SIDE_R = ((150, -40), (150, 0), (144, 40), (142, 80))


def body_fill():
    b = PB(-142, 80)
    b.C(-144, 40, -150, 0, -150, -40)
    b.C(-150, -122.8, -82.8, -190, 0, -190)
    b.C(82.8, -190, 150, -122.8, 150, -40)
    b.C(150, 0, 144, 40, 142, 80)
    b.C(125, 102, 64, 100, 47, 82)
    b.C(32, 104, -32, 104, -47, 82)
    b.C(-64, 100, -125, 102, -142, 80)
    return b.Z()


def body_outline():
    b = PB(-142, 80)
    b.C(-144, 40, -150, 0, -150, -40)
    b.C(-150, -122.8, -82.8, -190, 0, -190)
    b.C(82.8, -190, 150, -122.8, 150, -40)
    b.C(150, 0, 144, 40, 142, 80)
    return b.open()


# ---------------------------------------------------------------- tail wisps
WISP = {
    'L': dict(A=(-142, 80), Aside=True, B=(-47, 82), Bside=False, tip=(-132, 156),
              tin=(-3, -24), tout=(34, 2), aout=(2, 40), bin=(-8, 34)),
    'M': dict(A=(-47, 82), Aside=False, B=(47, 82), Bside=False, tip=(10, 170),
              tin=(-34, 2), tout=(6, -26), aout=(4, 46), bin=(-8, 34)),
    'R': dict(A=(47, 82), Aside=False, B=(142, 80), Bside=True, tip=(132, 156),
              tin=(-34, 2), tout=(3, -24), aout=(8, 34), bin=(-2, 40)),
}
WISP_DEFAULT = dict(sway=0.0, len=1.0, curl=0.0, lift=0.0)


def WP(**kw):
    d = dict(WISP_DEFAULT)
    d.update(kw)
    return d


RIPPLE_PH = {'L': 0.0, 'M': 1 / 3, 'R': 2 / 3}


def ripple0(key):
    """wisp params of the base pose (frame 0 of every default ripple)"""
    return wave(90, 2, WP(sway=-6, curl=-0.25), WP(sway=6, curl=0.25), RIPPLE_PH[key]).kfs[0][1]


def wisp_geom(key, prm):
    d = WISP[key]
    p = dict(WISP_DEFAULT)
    p.update(prm)
    A, B = d['A'], d['B']
    tx = d['tip'][0] + p['sway']
    top = (A[1] + B[1]) / 2
    ty = top + (d['tip'][1] - top) * p['len'] - p['lift']
    c = p['curl']
    # curl bends the tip tangents sideways (outward for side wisps, rightward for middle)
    side = {'L': -1, 'M': 1, 'R': 1}[key]
    tin = (d['tin'][0] + c * side * 10, d['tin'][1] + c * 10)
    tout = (d['tout'][0] + c * side * 14, d['tout'][1] - c * 12)
    aout = d['aout']
    bin_ = d['bin']
    HA = (A[0] + (3 if d['Aside'] else 0), 30 if d['Aside'] else 40)
    HB = (B[0] - (3 if d['Bside'] else 0), 30 if d['Bside'] else 40)
    TIP = (tx, ty)
    outline = Path([A, TIP, B, HB, HA],
                   [(0, 0), tin, bin_, (0, 0), (0, 0)],
                   [aout, tout, (0, 0), (0, 0), (0, 0)], True)
    # shade: flat lavender underside = lower part of both edges + a soft inner curve
    segL = (A, (A[0] + aout[0], A[1] + aout[1]), (TIP[0] + tin[0], TIP[1] + tin[1]), TIP)
    segR = (TIP, (TIP[0] + tout[0], TIP[1] + tout[1]), (B[0] + bin_[0], B[1] + bin_[1]), B)
    _, l2 = split_bez(*segL, 0.42)
    r1, _ = split_bez(*segR, 0.5)
    P1, P2 = l2[0], r1[3]
    c1 = (P2[0] + (P1[0] - P2[0]) * 0.33, P2[1] + (P1[1] - P2[1]) * 0.33 + 12)
    c2 = (P2[0] + (P1[0] - P2[0]) * 0.67, P2[1] + (P1[1] - P2[1]) * 0.67 + 12)
    shade = Path([P1, TIP, P2],
                 [(c2[0] - P1[0], c2[1] - P1[1]), (l2[2][0] - TIP[0], l2[2][1] - TIP[1]), (r1[2][0] - P2[0], r1[2][1] - P2[1])],
                 [(l2[1][0] - P1[0], l2[1][1] - P1[1]), (r1[1][0] - TIP[0], r1[1][1] - TIP[1]), (c1[0] - P2[0], c1[1] - P2[1])],
                 True)
    return outline, shade


def c2_rel(v, c):
    return (c[0] - v[0], c[1] - v[1])


# ---------------------------------------------------------------- tail wrap (blanket / face cover)
_r = split_bez(*BODY_SIDE_R, 0.5)[1]  # second half of right side: (146.75,20)->(142,80)
WR1, WR_c1, WR_c2, WR2 = _r
WRAP_POSES = {
    #          outer c1      outer c2       TIP           inner c1       inner c2
    'tucked': ((146, 74), (150, 60), (149, 50), (147, 42), (149, 30)),
    'blanket': ((150, 150), (-70, 158), (-162, 40), (-104, 96), (96, 96)),
    'face': ((168, 0), (60, -20), (-132, -50), (-104, -118), (128, -128)),
}


def wrap_pose(name):
    pts = WRAP_POSES[name]
    return {'p%d%s' % (k, c): pts[k][j] for k in range(5) for j, c in enumerate('xy')}


def wrap_geom(pose):
    if isinstance(pose, str):
        pose = wrap_pose(pose)
    oc1, oc2, T, ic1, ic2 = [(pose['p%dx' % k], pose['p%dy' % k]) for k in range(5)]
    fill = Path([WR1, WR2, T],
                [(-60 + 60, 0) if False else (0, 0), (WR_c2[0] - WR2[0], WR_c2[1] - WR2[1]), (oc2[0] - T[0], oc2[1] - T[1])],
                [(WR_c1[0] - WR1[0], WR_c1[1] - WR1[1]), (oc1[0] - WR2[0], oc1[1] - WR2[1]), (ic1[0] - T[0], ic1[1] - T[1])],
                True)
    # in-tangent of R1 (end of inner edge)
    fill.i[0] = (ic2[0] - WR1[0], ic2[1] - WR1[1])
    line = Path([WR2, T, WR1],
                [(0, 0), (oc2[0] - T[0], oc2[1] - T[1]), (ic2[0] - WR1[0], ic2[1] - WR1[1])],
                [(oc1[0] - WR2[0], oc1[1] - WR2[1]), (ic1[0] - T[0], ic1[1] - T[1]), (0, 0)], False)
    # shade along the outer edge
    seg = (WR2, oc1, oc2, T)
    _, second = split_bez(*seg, 0.12)
    P = second[0]
    c1 = (second[2][0] * 0.7 + ic1[0] * 0.3, second[2][1] * 0.7 + ic1[1] * 0.3)
    c2 = (P[0] * 0.6 + ic2[0] * 0.4, P[1] * 0.6 + ic2[1] * 0.4 + 10)
    shade = Path([P, T],
                 [(c2[0] - P[0], c2[1] - P[1]), (second[2][0] - T[0], second[2][1] - T[1])],
                 [(second[1][0] - P[0], second[1][1] - P[1]), ((T[0] + (c1[0] - T[0]) * 0.5) - T[0], (T[1] + (c1[1] - T[1]) * 0.5) - T[1])],
                 True)
    return fill, line, shade


# ---------------------------------------------------------------- face parts
def eye_variants(side):
    """returns dict variant -> list of shapes (eye drawn around 0,0)"""
    m = -1 if side == 'L' else 1
    v = {}
    v['open'] = [Shape(ellipse(0, 0, 25, 31), fill=EYE, name='eye'),
                 Shape(ellipse(8, -12, 9, 9.5), fill=HL, name='hl1'),
                 Shape(ellipse(-9, 11, 4.5, 4.5), fill=HL, name='hl2')]
    v['sleepy'] = [stroke(PB(-21, -2).C(-13, 13, 13, 13, 21, -2).open(), 'sleepy')]
    v['happy'] = [stroke(PB(-21, 7).C(-13, -13, 13, -13, 21, 7).open(), 'happy')]
    lash = poly([(20 * m, 3), (28 * m, -3)])
    v['wink'] = [stroke([PB(-20, 4).C(-10, -10, 10, -10, 20, 4).open(), lash], 'wink')]
    if side == 'L':
        v['squint'] = [stroke(poly([(-14, -15), (15, 0), (-14, 15)]), 'squint')]
    else:
        v['squint'] = [stroke(poly([(14, -15), (-15, 0), (14, 15)]), 'squint')]
    v['heart'] = [outlined(heart_path(2.1, 0, 0), HEART, 'hearteye', w=6),
                  Shape(ellipse(-12, -9, 5, 5), fill=HL, name='hl')]
    v['round'] = [outlined(ellipse(0, 0, 25, 27), HL, 'white', w=6),
                  Shape(ellipse(0, 2, 10, 11), fill=EYE, name='pupil'),
                  Shape(ellipse(3.5, -2.5, 3.5, 3.5), fill=HL, name='hl')]
    pts = []
    for k in range(26):
        a = k * 0.62 * (1 if side == 'R' else -1)
        r = 2 + k * 0.95
        pts.append((r * math.cos(a), r * math.sin(a)))
    v['dizzy'] = [stroke(smooth(pts), 'spiral', w=6)]
    v['halflid'] = [Shape(PB(-25, -3).L(25, -3).C(25, 18, 13, 31, 0, 31).C(-13, 31, -25, 18, -25, -3).Z(), fill=EYE, name='half'),
                    Shape(ellipse(7, 9, 6, 6), fill=HL, name='hl'),
                    stroke(poly([(-29, -4), (29, -4)]), 'lid')]
    return v


def mouth_variants():
    v = {}
    v['smile'] = [stroke(PB(-11, -3).C(-6, 5, 6, 5, 11, -3).open(), 'smile', w=6.5)]
    om = PB(-17, -5).L(17, -5).C(17, 11, 9, 19, 0, 19).C(-9, 19, -17, 11, -17, -5).Z()
    v['open'] = [Shape(om, fill=MOUTH, name='m'),
                 Shape(PB(-9, 13).C(-7, 6, 7, 6, 9, 13).C(6, 18.5, -6, 18.5, -9, 13).Z(), fill=TONGUE, name='tongue'),
                 stroke(om, 'mo', w=6.5)]
    v['o'] = [outlined(ellipse(0, 2, 8, 10), MOUTH, 'o', w=6.5)]
    ym = ellipse(0, 6, 18, 26)
    v['yawn'] = [Shape(ym, fill=MOUTH, name='m'),
                 Shape(PB(-11, 22).C(-8, 13, 8, 13, 11, 22).C(7, 30, -7, 30, -11, 22).Z(), fill=TONGUE, name='tongue'),
                 stroke(ym, 'mo', w=6.5)]
    v['frown'] = [stroke(PB(-11, 4).C(-6, -4, 6, -4, 11, 4).open(), 'frown', w=6.5)]
    v['wobble'] = [stroke(wobble_path(0), 'wobble', w=6)]
    bm = PB(-28, -14).C(-10, -20, 10, -20, 28, -14).C(32, 8, 18, 30, 0, 30).C(-18, 30, -32, 8, -28, -14).Z()
    v['boo'] = [Shape(bm, fill=MOUTH, name='m'),
                Shape(PB(-14, 24).C(-10, 12, 10, 12, 14, 24).C(9, 31, -9, 31, -14, 24).Z(), fill=TONGUE, name='tongue'),
                stroke(bm, 'mo', w=6.5)]
    v['pout'] = [stroke(PB(-8, 1).C(-6, -5, -2, -5, 0, 0).C(2, -5, 6, -5, 8, 1).open(), 'pout', w=6)]
    v['smirk'] = [stroke(PB(-11, 1).C(-4, 5, 5, 3, 11, -5).open(), 'smirk', w=6.5)]
    return v


def wobble_path(ph):
    s = 1 - 2 * ph
    return PB(-18, 0).C(-15, -6 * s, -9, -6 * s, -6, 0).C(-3, 6 * s, 3, 6 * s, 6, 0).C(9, -6 * s, 15, -6 * s, 18, 0).open()


BROWS = {
    'worried': lambda: [stroke([PB(-80, -100).C(-68, -102, -54, -108, -44, -115).open(),
                                PB(80, -100).C(68, -102, 54, -108, 44, -115).open()], 'worried', w=7)],
    'angry': lambda: [stroke([PB(-82, -116).C(-70, -112, -56, -105, -44, -98).open(),
                              PB(82, -116).C(70, -112, 56, -105, 44, -98).open()], 'angry', w=7)],
}


# ---------------------------------------------------------------- props
def lantern(T):
    handle = stroke(PB(-12, 16).C(-12, -4, 12, -4, 12, 16).open(), 'handle', w=6)
    cap = outlined(poly([(-11, 13), (11, 13), (21, 25), (-21, 25)], closed=True), LANTERN, 'cap', w=6)
    glass_p = PB(-17, 25).L(17, 25).C(19, 38, 19, 50, 17, 62).L(-17, 62).C(-19, 50, -19, 38, -17, 25).Z()
    glass = Shape(glass_p, fill=GLASS, name='glass')
    glow = Group('lit', [Shape(ellipse(0, 46, 14, 14), fill=YELLOW_PALE, name='inner')], o=T('flame.o', 0))
    flame_shape = PB(0, -16).C(5, -8, 9, -3, 9, 3).C(9, 9, 5, 12, 0, 12).C(-5, 12, -9, 9, -9, 3).C(-9, -3, -5, -8, 0, -16).Z()
    flame = Group('flame', [outlined(flame_shape, YELLOW, 'fl', w=4),
                            Shape(ellipse(0, 5, 4, 5.5), fill=YELLOW_PALE, name='core')],
                  p=(0, 56), a=(0, 10), s=T('flame.s', (100, 100)), r=T('flame.r', 0))
    flame_g = Group('flame_on', [flame], o=T('flame.o', 0))
    bars = stroke([poly([(-7, 27), (-7, 60)]), poly([(7, 27), (7, 60)])], 'bars', w=3, color=LANTERN)
    glass_o = stroke(glass_p, 'glass_o', w=6)
    base = outlined(PB(-21, 61).L(21, 61).C(21, 66, 19, 70, 15, 70).L(-15, 70).C(-19, 70, -21, 66, -21, 61).Z(),
                    LANTERN, 'base', w=6)
    return [handle, glass, glow, flame_g, bars, glass_o, cap, base]


def marshmallow(s=1.0):
    f = lambda p: (p[0] * s, p[1] * s)
    stick = glyph([poly([(-22, 26), (6, -2)]).map(f)], STICK, 'stick', w_in=5, w_out=10)
    body = PB(-2, -22).C(8, -32, 22, -24, 26, -14).L(14, 8).C(10, 16, -6, 12, -10, 2).Z().map(f)
    toast = PB(-2, -22).C(8, -32, 22, -24, 26, -14).C(20, -6, 8, -12, -2, -22).Z().map(f)
    return stick + [Shape(body, fill=MALLOW, name='mallow'), Shape(toast, fill=TOAST, name='toast'),
                    stroke(body, 'mallow_o', w=4.5 * s)]


def mitten(side):
    m = -1 if side == 'L' else 1
    thumb = outlined(ellipse(-13 * m, -12, 9, 10), None, 'thumb')
    return [Shape(ellipse(-13 * m, -12, 9, 10), fill=None, name='thumbfill'), thumb]


# ---------------------------------------------------------------- the character
class Clip:
    def __init__(self, name, cat, frames, loop=True, desc=''):
        self.name, self.cat, self.N, self.loop, self.desc = name, cat, frames, loop, desc
        self.t = {}
        self.effects = []      # Layer objects drawn above the character
        self.under = []        # Layers drawn under the character (glow halos)
        self.no_bob = False
        self.no_ripple = False
        self.no_arm_drift = False
        self.anchor = (0, 0)   # squash pivot (local units)

    def k(self, key, kfs):
        if key.startswith('wisp') and not isinstance(kfs, Track):
            kfs = [(x[0], ripple0(key[-1]) if not x[1] else WP(**x[1])) + tuple(x[2:]) for x in kfs]
        if key == 'wrap.w' and not isinstance(kfs, Track):
            kfs = [(x[0], wrap_pose(x[1]) if isinstance(x[1], str) else x[1]) + tuple(x[2:]) for x in kfs]
        self.t[key] = kfs if isinstance(kfs, Track) else Track(kfs)
        return self

    def st(self, key, kfs):
        """step (hold) track"""
        self.t[key] = steps(kfs)
        return self


def build(clip):
    N = clip.N
    t = clip.t
    cyc = max(1, round(N / 90))

    def T(key, default):
        if key in t:
            return t[key]
        return S(default)

    # -------- defaults that run through every clip
    if 'bob.p' not in t and not clip.no_bob:
        t['bob.p'] = wave(N, cyc, [0, 0], [0, -5])
    if not clip.no_ripple:
        rc = max(1, round(N / 45))
        for key, ph in RIPPLE_PH.items():
            wk = 'wisp' + key
            if wk not in t:
                lo = WP(sway=-6, curl=-0.25)
                hi = WP(sway=6, curl=0.25)
                t[wk] = wave(N, rc, lo, hi, ph)
    if not clip.no_arm_drift:
        for side, x, ph in (('L', -170, 0.0), ('R', 170, 0.0)):
            if 'arm%s.p' % side not in t:
                t['arm%s.p' % side] = wave(N, cyc, [x, 24], [x * 1.01, 18], ph)
            if 'arm%s.r' % side not in t:
                base = 16 if side == 'L' else -16
                t['arm%s.r' % side] = wave(N, cyc, base, base + (5 if side == 'L' else -5), ph)

    tint = T('tint', WHITE)

    # -------- tail
    wisps = []
    for key in ('M', 'L', 'R'):
        tr = t.get('wisp' + key)
        if tr is None:
            o, sh = wisp_geom(key, {})
            pt_o, pt_s = S(o), S(sh)
        else:
            tr.fit(N)
            pt_o = Track([(a, wisp_geom(key, v)[0], e) for a, v, e in tr.kfs])
            pt_s = Track([(a, wisp_geom(key, v)[1], e) for a, v, e in tr.kfs])
        wisps.append(Group('wisp' + key, [Shape(pt_o, fill=tint, name='wfill'),
                                          Shape(pt_s, fill=LAV, name='wshade'),
                                          Shape(pt_o, stroke=INK, width=W, name='wline')]))
    tail = Group('tail', wisps, p=(0, 82), a=(0, 82), s=T('tail.s', (100, 100)))

    body = Group('body', [Shape(body_fill(), fill=tint, name='bfill'),
                          Shape(body_outline(), stroke=INK, width=W, name='bline')])

    # -------- face
    def variant_groups(prefix, variants, default):
        vt = t.get(prefix + '.v')
        gs = []
        for name, shapes in variants.items():
            if vt is None:
                o = S(100 if name == default else 0)
            else:
                vt.fit(N)
                o = steps([(a, 100 if v == name else 0) for a, v, e in vt.kfs])
                if o.static() and o.kfs[0][1] == 0:
                    continue
            if vt is None and name != default:
                continue
            gs.append(Group(prefix + '_' + name, shapes, o=o))
        return gs

    eyes = []
    for side, x in (('L', -58), ('R', 58)):
        ev = eye_variants(side)
        key = 'eye' + side
        vkey = key if key + '.v' in t else 'eyes'
        if vkey == 'eyes' and 'eyes.v' in t:
            t[key + '.v'] = t['eyes.v']
        gs = variant_groups(key, ev, 'open')
        sk = key + '.s' if key + '.s' in t else 'eyes.s'
        eyes.append(Group(key, gs, p=(x, -58), s=T(sk, (100, 100)), r=T(key + '.r', 0)))
    gaze = Group('gaze', eyes, p=T('gaze.p', (0, 0)))

    cheeks = []
    for side, x in (('L', -96), ('R', 96)):
        cheeks.append(Group('cheek' + side, [Shape(ellipse(0, 0, 21, 12), fill=T('cheek.c', CHEEK), name='ch')],
                            p=T('cheek%s.p' % side, (x, -16)), s=T('cheeks.s', (100, 100))))

    mv = mouth_variants()
    if 'mouth.wob' in t:
        tr = t['mouth.wob']
        tr.fit(N)
        mv['wobble'] = [stroke(Track([(a, wobble_path(v), e) for a, v, e in tr.kfs]), 'wobble', w=6)]
    mouth = Group('mouth', variant_groups('mouth', mv, 'smile'), p=T('mouth.p', (0, -6)),
                  s=T('mouth.s', (100, 100)), r=T('mouth.r', 0))

    brow_groups = []
    if 'brows.v' in t:
        bt = t['brows.v']
        bt.fit(N)
        for name, fn in BROWS.items():
            o = steps([(a, 100 if v == name else 0) for a, v, e in bt.kfs])
            if o.static() and o.kfs[0][1] == 0:
                continue
            brow_groups.append(Group('brow_' + name, fn(), o=o))
    brows = Group('brows', brow_groups, p=T('brows.p', (0, 0)))

    extras = []
    if 'snot.o' in t:
        extras.append(Group('snot', [outlined(ellipse(0, 0, 14, 14), '#e3f3ff', 'b', w=4.5),
                                     Shape(ellipse(-4.5, -4.5, 4, 4), fill=HL, name='hl')],
                            p=(30, -24), a=(-6, 6), s=T('snot.s', (100, 100)), o=t['snot.o']))
    if 'tear.o' in t:
        extras.append(Group('tear', [outlined(drop_path(1.35), SKY, 'tear', w=4.5)],
                            p=T('tear.p', (-70, -28)), s=T('tear.s', (100, 100)), o=t['tear.o']))
    face = Group('face', cheeks + [gaze, mouth, brows] + extras, p=T('face.p', (0, 0)))

    # -------- bow
    loopL = PB(0, 0).C(-10, -22, -34, -26, -34, -6).C(-34, 10, -12, 10, 0, 0).Z()
    loopR = loopL.map(lambda p: (-p[0], p[1]))
    tails = [PB(-3, 3).L(-14, 22).L(-6, 22).L(0, 6).Z(), PB(3, 3).L(13, 23).L(5, 24).L(0, 6).Z()]
    bow = Group('bow', [outlined(tails, BOW_KNOT, 'tails', w=6), outlined(loopL, BOW, 'loopL', w=6),
                        outlined(loopR, BOW, 'loopR', w=6), outlined(ellipse(0, 0, 9, 8.5), BOW_KNOT, 'knot', w=6)],
                p=T('bow.p', (98, -150)), r=T('bow.r', 28), s=T('bow.s', (100, 100)))

    # -------- wrap (tail curled in front)
    parts_top = []
    if 'wrap.w' in t:
        tr = t['wrap.w']
        tr.fit(N)
        geo = [(a, wrap_geom(v), e) for a, v, e in tr.kfs]
        wf = Track([(a, g[0], e) for a, g, e in geo])
        wl = Track([(a, g[1], e) for a, g, e in geo])
        ws = Track([(a, g[2], e) for a, g, e in geo])
        parts_top.append(Group('wrap', [Shape(wf, fill=tint, name='wrapfill'), Shape(ws, fill=LAV, name='wrapshade'),
                                        Shape(wl, stroke=INK, width=W, name='wrapline')], o=T('wrap.o', 100)))

    if 'anger.o' in t:
        q = 1.5
        arcs = [PB(-22 * q / 1.5, -7).C(-9, -7, -7, -9, -7, -22 * q / 1.5).open(), PB(7, -22).C(7, -9, 9, -7, 22, -7).open(),
                PB(22, 7).C(9, 7, 7, 9, 7, 22).open(), PB(-7, 22).C(-7, 9, -9, 7, -22, 7).open()]
        parts_top.append(Group('anger', [Shape(arcs, stroke=INK, width=13, name='a_o'),
                                         Shape(arcs, stroke=ANGER, width=6.5, name='a_i')],
                               p=(-112, -146), s=T('anger.s', (100, 100)), r=T('anger.r', 0), o=t['anger.o']))

    # -------- arms
    arms = []
    for side, x, r0 in (('L', -170, 16), ('R', 170, -16)):
        m = -1 if side == 'L' else 1
        thumb_p = ellipse(-13 * m, -17, 8, 9)
        main_p = ellipse(0, 0, 21, 26)
        kids = []
        if side == 'R' and 'lantern.o' in t:
            kids.append(Group('lantern', lantern(T), p=T('lantern.p', (0, 8)), a=(0, 0), r=T('lantern.r', 16),
                              s=T('lantern.s', (100, 100)), o=t['lantern.o']))
        kids += [outlined(thumb_p, tint, 'thumb'), outlined(main_p, tint, 'mitt')]
        arms.append(Group('arm' + side, kids, p=T('arm%s.p' % side, (x, 24)), r=T('arm%s.r' % side, r0),
                          s=T('arm%s.s' % side, (100, 100))))

    ax, ay = clip.anchor
    squash = Group('squash', [tail, body, face, bow] + parts_top + arms,
                   p=(ax, ay), a=(ax, ay), s=T('squash.s', (100, 100)), r=T('squash.r', 0))
    move = Group('move', [squash], p=T('move.p', BASE), r=T('move.r', 0), s=T('move.s', (SC, SC)))
    bob = Group('bob', [move], p=T('bob.p', (0, 0)))
    char = Layer('ghost', bob, o=T('char.o', 100))

    # -------- ground shadow (derived from height unless overridden)
    def lift_scale(lift, k=0.55):
        s = max(30.0, min(125.0, 100 - lift * k))
        return [s, s]
    bt = T('bob.p', [0, 0]).fit(N)
    sh_bob = Track([(a, lift_scale(-v[1], 1.0), e) for a, v, e in bt.kfs])
    mt = T('move.p', BASE).fit(N)
    sh_mp = Track([(a, [v[0], GROUND], e) for a, v, e in mt.kfs])
    sh_ms = Track([(a, lift_scale(BASE[1] - v[1]), e) for a, v, e in mt.kfs])
    if 'shadow.s' in t:
        sh_ms = t['shadow.s']
    sh = Group('shadow', [Group('sb', [Shape(ellipse(0, 0, 92, 15), fill=INK, fill_opacity=0.16, name='shadow')],
                                s=sh_bob)], p=sh_mp, s=sh_ms)
    shadow = Layer('shadow', sh, o=T('shadow.o', None) if 'shadow.o' in t else T('char.o', 100))

    return [shadow] + clip.under + [char] + clip.effects


# ---------------------------------------------------------------- world-space effects
_fx = [0]


def fx(name, shapes, p, s=(100, 100), r=0, o=100):
    _fx[0] += 1
    return Layer('%s%d' % (name, _fx[0]), Group(name, shapes, p=p, s=s, r=r), o=o)


def fx_sparkle(size, color=YELLOW):
    return [outlined(star4(size * 1.25), color, 'sparkle', w=max(2.5, min(WE, size * 0.32)))]


def fx_heart(size=1.0, color=HEART):
    return [outlined(heart_path(size), color, 'heart', w=WE)]


def fx_star(r=9, color=YELLOW):
    return [outlined(star5(r), color, 'star', w=WE)]


def fx_z(s=1.0):
    return glyph(g_z(s), LAV, 'z', w_in=6, w_out=12)


def fx_excl(s=1.0, color=YELLOW):
    return glyph(g_excl(s), color, 'excl', w_in=7, w_out=13)


def fx_q(s=1.0, color=SKY):
    return glyph(g_q(s), color, 'q', w_in=6.5, w_out=12.5)


def fx_note(s=1.0, color=MINT):
    head = outlined(ellipse(-1 * s, 6 * s, 6 * s, 5 * s), color, 'nh', w=WE)
    return glyph([g_note(s)], color, 'ns', w_in=4, w_out=9) + [head]


def fx_boo():
    paths = g_B(1.0, -26) + g_O(1.0, 0) + g_O(1.0, 24)
    return glyph(paths, PEACH, 'boo', w_in=6.5, w_out=13)


def fx_puff(r, color='#f3eeff'):
    return [outlined(ellipse(0, 0, r, r * 0.9), color, 'puff', w=WE)]
