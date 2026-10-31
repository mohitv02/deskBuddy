"""Chibi cat rig: parts, shapes and exporters (Lottie JSON + SMIL animated SVG).
Everything is drawn in a 512x512 'base' space; the Root null scales it to 80%
and stands it on the ground so there is headroom for hops and effects."""
import json

FR = 30
W = H = 512

COL = dict(
    OUT='#4A3530', WHITE='#FFF9F2', PEACH='#FFC08F', PEACH_D='#FFAA6E', PINK='#FFB3C1',
    BEAN='#FF9FB2', CHEEK='#FF9AAE', EYE='#3B2420', IRIS='#8A5235', HL='#FFFFFF',
    MOUTH='#A8434A', TONGUE='#FF8A9A', SPARK='#FFD34D', BUBBLE='#BFE6FF', Z='#8FA6D8',
    SHADOW='#000000', HEART='#FF6F91', TEAR='#8FD3FF', ANGER='#FF5A5F', FISH='#7EC3F5',
    BADGE='#FFD34D', BANG='#FF6B5B')


def rgba(h, a=1):
    h = h.lstrip('#')
    return [round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)] + [a]


# ------------------------------------------------------------------ shapes
class P:
    def __init__(s, x, y):
        s.v = [[x, y]]; s.i = [[0, 0]]; s.o = [[0, 0]]

    def L(s, x, y):
        s.v.append([x, y]); s.i.append([0, 0]); s.o.append([0, 0]); return s

    def Q(s, cx, cy, x, y):
        px, py = s.v[-1]
        s.o[-1] = [2 / 3 * (cx - px), 2 / 3 * (cy - py)]
        s.v.append([x, y]); s.i.append([2 / 3 * (cx - x), 2 / 3 * (cy - y)]); s.o.append([0, 0]); return s

    def C(s, ax, ay, bx, by, x, y):
        px, py = s.v[-1]
        s.o[-1] = [ax - px, ay - py]
        s.v.append([x, y]); s.i.append([bx - x, by - y]); s.o.append([0, 0]); return s

    def done(s, closed=False):
        v = [p[:] for p in s.v]; i = [p[:] for p in s.i]; o = [p[:] for p in s.o]
        if closed and len(v) > 1 and v[-1] == v[0]:
            i[0] = i[-1]; v.pop(); i.pop(); o.pop()
        return {'k': 'path', 'v': v, 'i': i, 'o': o, 'c': closed}


def E(cx, cy, w, h): return {'k': 'ell', 'cx': cx, 'cy': cy, 'w': w, 'h': h}
def F(col, o=100): return {'k': 'fill', 'c': col, 'o': o}
def S(col, w, o=100): return {'k': 'stroke', 'c': col, 'w': w, 'o': o}
def G(*items): return {'k': 'grp', 'it': list(items)}
def OL(shape, col, w=6): return G(shape, S(COL['OUT'], w), F(col))


def heart_path(cx, cy, k=1.0):
    return (P(cx, cy + 20 * k).C(cx - 34 * k, cy - 2 * k, cx - 24 * k, cy - 30 * k, cx, cy - 12 * k)
            .C(cx + 24 * k, cy - 30 * k, cx + 34 * k, cy - 2 * k, cx, cy + 20 * k).done(True))


def star_path(cx, cy, r):
    q = r * 0.15
    return (P(cx, cy - r).Q(cx + q, cy - q, cx + r, cy).Q(cx + q, cy + q, cx, cy + r)
            .Q(cx - q, cy + q, cx - r, cy).Q(cx - q, cy - q, cx, cy - r).done(True))


# ------------------------------------------------------------------ rig
PARTS = {}
CHILDREN = {}


class Part:
    def __init__(s, name, parent, items=(), anchor=(0, 0), pos=None, scale=100, op=100, null=False):
        s.name, s.parent, s.items = name, parent, list(items)
        s.anchor, s.pos, s.scale, s.op, s.null = anchor, pos or anchor, scale, op, null
        PARTS[name] = s


C_ = COL
OUT = C_['OUT']

Part('Shadow', 'COMP', [G(E(256, 470, 196, 22), F(C_['SHADOW'], 10))], anchor=(256, 470))
Part('Root', 'COMP', anchor=(256, 450), pos=(256, 470), scale=80, null=True)
Part('Spin', 'Root', anchor=(256, 310), null=True)

# body & limbs
_tail = lambda: P(318, 420).C(378, 428, 412, 392, 398, 334).done()
Part('Tail', 'Spin', [G(_tail(), S(C_['PEACH'], 30)), G(_tail(), S(OUT, 42))], anchor=(318, 420))
Part('Body', 'Spin', [G(E(196, 398, 44, 40), E(318, 392, 40, 50), F(C_['PEACH'])),
                      OL(E(256, 365, 214, 168), C_['WHITE'])], anchor=(256, 446))


def _foot(cx):
    return [G(E(cx - 14, 428, 9, 9), E(cx, 425, 9, 9), E(cx + 14, 428, 9, 9), E(cx, 441, 22, 14), F(C_['BEAN'])),
            OL(E(cx, 436, 64, 34), C_['WHITE'])]


Part('FootL', 'Spin', _foot(172), anchor=(172, 436))
Part('FootR', 'Spin', _foot(340), anchor=(340, 436))


def _paw(cx):
    return [G(P(cx - 6, 440).L(cx - 6, 448).done(), P(cx + 6, 440).L(cx + 6, 448).done(), S(OUT, 3.5)),
            OL(E(cx, 428, 40, 44), C_['WHITE'])]


Part('PawL', 'Spin', _paw(230), anchor=(230, 448))
Part('PawR', 'Spin', _paw(282), anchor=(282, 448))
_arm = lambda: P(336, 356).L(400, 294).done()
Part('ArmR', 'Spin', [
    G(E(396, 276, 8, 8), E(408, 271, 8, 8), E(420, 276, 8, 8), E(408, 292, 20, 13), F(C_['BEAN'])),
    OL(E(408, 286, 46, 46), C_['WHITE']),
    G(_arm(), S(C_['WHITE'], 30)), G(_arm(), S(OUT, 42))], anchor=(336, 356), op=0)

# head
Part('Head', 'Spin', [
    G(P(249, 252).L(263, 252).L(256, 260).L(249, 252).done(True), S(OUT, 3), F(C_['PINK'])),
    G(P(124, 250).L(96, 244).done(), P(124, 262).L(94, 264).done(),
      P(388, 250).L(416, 244).done(), P(388, 262).L(418, 264).done(), S(OUT, 3)),
    G(P(236, 124).L(245, 103).L(253, 117).L(262, 100).L(270, 116).L(278, 124).done(), S(OUT, 5), F(C_['WHITE'])),
    G(P(238, 134).L(242, 156).done(), P(256, 130).L(256, 156).done(), P(274, 134).L(270, 156).done(),
      S(C_['PEACH_D'], 11)),
    G(E(322, 190, 76, 64), F(C_['PEACH'])),
    OL(E(256, 232, 270, 232), C_['WHITE']),
], anchor=(256, 330))


def _ear(mirror):
    m = (lambda x: 512 - x) if mirror else (lambda x: x)
    outer = P(m(148), 185).Q(m(150), 120, m(168), 88).Q(m(200), 100, m(232), 128).L(m(148), 185).done(True)
    inner = P(m(166), 165).Q(m(166), 125, m(174), 110).Q(m(195), 118, m(212), 134).L(m(166), 165).done(True)
    return [G(inner, F(C_['PINK'])), OL(outer, C_['WHITE'])]


Part('EarL', 'Head', _ear(False), anchor=(190, 156))
Part('EarR', 'Head', _ear(True), anchor=(322, 156))
Part('PuffL', 'Head', [OL(E(132, 268, 70, 64), C_['WHITE'])], anchor=(150, 268), op=0)
Part('PuffR', 'Head', [OL(E(380, 268, 70, 64), C_['WHITE'])], anchor=(362, 268), op=0)
Part('Cheeks', 'Head', [G(E(178, 266, 44, 24), E(334, 266, 44, 24), F(C_['CHEEK'], 75))], anchor=(256, 266))


def _eye(cx):
    return [G(E(cx - 9, 216, 18, 18), E(cx + 9, 246, 8, 8), F(C_['HL'])),
            G(E(cx, 244, 30, 24), F(C_['IRIS'])),
            G(E(cx, 232, 46, 56), F(C_['EYE']))]


Part('EyeL', 'Head', _eye(204), anchor=(204, 232))
Part('EyeR', 'Head', _eye(308), anchor=(308, 232))
Part('LidsSleep', 'Head', [G(P(184, 232).Q(204, 246, 224, 232).done(), P(288, 232).Q(308, 246, 328, 232).done(),
                             S(OUT, 6))], anchor=(256, 232), op=0)
Part('LidsHappy', 'Head', [G(P(184, 240).Q(204, 214, 224, 240).done(), P(288, 240).Q(308, 214, 328, 240).done(),
                             S(OUT, 6))], anchor=(256, 232), op=0)
Part('LidsSquint', 'Head', [G(P(188, 220).L(220, 232).L(188, 244).done(), P(324, 220).L(292, 232).L(324, 244).done(),
                              S(OUT, 6))], anchor=(256, 232), op=0)
Part('WinkR', 'Head', [G(P(286, 238).Q(308, 212, 330, 238).done(), S(OUT, 6))], anchor=(308, 232), op=0)
for _n, _cx in (('HeartEyeL', 204), ('HeartEyeR', 308)):
    Part(_n, 'Head', [G(E(_cx - 11, 224, 10, 9), F(C_['HL'])), OL(heart_path(_cx, 236, 1.0), C_['HEART'], 5)],
         anchor=(_cx, 232), op=0)
Part('BrowsSad', 'Head', [G(P(184, 196).L(220, 182).done(), P(328, 196).L(292, 182).done(), S(OUT, 5))],
     anchor=(256, 190), op=0)
Part('BrowsAngry', 'Head', [G(P(186, 182).L(222, 198).done(), P(326, 182).L(290, 198).done(), S(OUT, 5))],
     anchor=(256, 190), op=0)
Part('MouthCat', 'Head', [G(P(256, 259).L(256, 264).done(),
                            P(240, 262).Q(248, 274, 256, 264).Q(264, 274, 272, 262).done(), S(OUT, 4))],
     anchor=(256, 264))
Part('MouthOpen', 'Head', [G(E(256, 288, 24, 12), F(C_['TONGUE'])),
                           G(P(232, 262).C(232, 308, 280, 308, 280, 262).L(232, 262).done(True), S(OUT, 4.5),
                             F(C_['MOUTH']))], anchor=(256, 262), op=0)
Part('MouthO', 'Head', [OL(E(256, 276, 20, 22), C_['MOUTH'], 4)], anchor=(256, 268), op=0)
Part('MouthYawn', 'Head', [
    G(P(242, 266).L(247, 277).L(252, 266).done(True), P(260, 266).L(265, 277).L(270, 266).done(True), F(C_['HL'])),
    G(E(256, 304, 28, 14), F(C_['TONGUE'])),
    OL(E(256, 290, 50, 56), C_['MOUTH'], 4.5)], anchor=(256, 262), op=0)
Part('MouthHiss', 'Head', [
    G(P(241, 264).L(246, 277).L(251, 264).done(True), P(261, 264).L(266, 277).L(271, 264).done(True), F(C_['HL'])),
    G(P(232, 262).L(280, 262).Q(272, 292, 256, 292).Q(240, 292, 232, 262).done(True), S(OUT, 4.5), F(C_['MOUTH']))],
     anchor=(256, 264), op=0)
Part('MouthFrown', 'Head', [G(P(242, 276).Q(256, 262, 270, 276).done(), S(OUT, 4))], anchor=(256, 270), op=0)
Part('Tongue', 'Head', [OL(E(266, 280, 16, 20), C_['TONGUE'], 3.5)], anchor=(266, 270), op=0)
Part('Bubble', 'Head', [G(E(274, 249, 6, 6), F(C_['HL'])), G(E(279, 256, 26, 26), S(OUT, 2.5), F(C_['BUBBLE'], 75))],
     anchor=(266, 258), op=0)
Part('Tear', 'Head', [G(E(185, 266, 5, 7), F(C_['HL'])),
                      OL(P(188, 252).C(178, 264, 178, 276, 188, 276).C(198, 276, 198, 264, 188, 252).done(True),
                         C_['TEAR'], 3.5)], anchor=(188, 252), op=0)
Part('WinkSpark', 'Head', [G(E(422, 160, 7, 7), F(C_['SPARK'])), G(star_path(404, 176, 15), F(C_['SPARK']))],
     anchor=(404, 176), op=0)

# effects (children of Root, base coords)
for _i in (1, 2, 3):
    Part(f'Z{_i}', 'Root', [G(P(-9, -10).L(9, -10).L(-9, 10).L(9, 10).done(), S(C_['Z'], 5))], op=0)
    Part(f'Heart{_i}', 'Root', [G(E(-7, -4, 6, 5), F(C_['HL'])), OL(heart_path(0, 0, 0.6), C_['HEART'], 4)], op=0)
for _i, _xy in enumerate([(96, 150), (420, 150), (372, 34)], 1):
    Part(f'Spark{_i}', 'Root', [G(E(16, -14, 7, 7), F(C_['SPARK'])), G(star_path(0, 0, 17), F(C_['SPARK']))],
         anchor=(0, 0), pos=_xy, op=0)
Part('Exclaim', 'Root', [G(P(380, 40).L(371, 30).done(), P(428, 40).L(437, 30).done(), S(C_['BANG'], 5)),
                         G(P(404, 28).L(404, 60).done(), S(C_['BANG'], 13)),
                         G(E(404, 82, 14, 14), F(C_['BANG']))], anchor=(404, 92), op=0)
Part('Anger', 'Root', [G(P(384, 154).Q(396, 154, 396, 142).done(), P(408, 142).Q(408, 154, 420, 154).done(),
                         P(420, 166).Q(408, 166, 408, 178).done(), P(396, 178).Q(396, 166, 384, 166).done(),
                         S(C_['ANGER'], 6))], anchor=(402, 160), op=0)
Part('Speech', 'Root', [OL(E(372, 112, 18, 18), C_['WHITE'], 4), OL(E(356, 132, 11, 11), C_['WHITE'], 4),
                        OL(E(430, 56, 132, 96), C_['WHITE'], 5)], anchor=(372, 112), op=0)
Part('Fish', 'Speech', [G(E(404, 52, 6, 6), F(OUT)),
                        OL(E(420, 56, 56, 30), C_['FISH'], 4),
                        OL(P(446, 56).L(468, 40).L(468, 72).done(True), C_['FISH'], 4)], anchor=(430, 56), op=0)
Part('Badge', 'Root', [G(P(430, 42).L(430, 64).done(), S(OUT, 9)), G(E(430, 80, 10, 10), F(OUT)),
                       OL(E(430, 62, 74, 74), C_['BADGE'], 5)], anchor=(430, 99), op=0)

# draw order, bottom -> top ('SELF' = the part's own shapes)
CHILDREN['COMP'] = ['Shadow', 'Root']
CHILDREN['Root'] = ['Spin', 'Z1', 'Z2', 'Z3', 'Heart1', 'Heart2', 'Heart3', 'Spark1', 'Spark2', 'Spark3',
                    'Exclaim', 'Anger', 'Speech', 'Badge']
CHILDREN['Spin'] = ['Tail', 'Body', 'FootL', 'FootR', 'Head', 'PawL', 'PawR', 'ArmR']
CHILDREN['Head'] = ['EarL', 'EarR', 'PuffL', 'PuffR', 'SELF', 'Cheeks', 'EyeL', 'EyeR', 'LidsSleep', 'LidsHappy',
                    'LidsSquint', 'WinkR', 'HeartEyeL', 'HeartEyeR', 'BrowsSad', 'BrowsAngry', 'MouthCat',
                    'MouthOpen', 'MouthO', 'MouthYawn', 'MouthHiss', 'MouthFrown', 'Tongue', 'Bubble', 'Tear', 'WinkSpark']
CHILDREN['Speech'] = ['SELF', 'Fish']


def flatten(n):
    order = CHILDREN.get(n, ['SELF'])
    out = []
    for c in order:
        out += [n] if c == 'SELF' else flatten(c)
    if 'SELF' not in order and n != 'COMP':
        out.append(n)
    return out


DRAW_ORDER = flatten('COMP')  # bottom -> top

# ------------------------------------------------------------------ clips
EASE = {'e': (0.42, 0, 0.58, 1), 'i': (0.42, 0, 1, 1), 'o': (0, 0, 0.58, 1), 'l': (0, 0, 1, 1)}


def dflt(part, prop):
    return {'p': (0, 0), 'r': 0, 's': (100, 100), 'o': PARTS[part].op}[prop]


def nv(prop, v):
    if prop == 's' and not isinstance(v, (tuple, list)):
        return (v, v)
    return tuple(v) if isinstance(v, (tuple, list)) else v


def norm(keys, T, dv, prop):
    ks = [(k[0], nv(prop, k[1]), k[2] if len(k) > 2 else 'e') for k in keys]
    ks = [k for k in ks if 0 <= k[0] <= T]
    ks.sort(key=lambda k: k[0])
    out = []
    for k in ks:
        if out and abs(out[-1][0] - k[0]) < 1e-6:
            out[-1] = k
        else:
            out.append(k)
    if not out:
        return [(0, nv(prop, dv), 'e')]
    if out[0][0] > 0:
        out.insert(0, (0, out[0][1], 'e'))
    if out[-1][0] < T:
        out.append((T, out[-1][1], 'e'))
    return out


class Clip:
    def __init__(s, name, T, cat, desc='', once=False):
        s.name, s.T, s.cat, s.desc, s.once = name, T, cat, desc, once
        s.tr = {}
        s.markers = []

    def k(s, part, prop, *keys):
        assert part in PARTS, part
        s.tr.setdefault((part, prop), []).extend(keys)
        return s

    def track(s, part, prop):
        return norm(s.tr.get((part, prop), []), s.T, dflt(part, prop), prop)

    def included(s):
        inc = set()
        for n, p in PARTS.items():
            if p.null or p.op > 0 or (n, 'o') in s.tr:
                while n != 'COMP':
                    inc.add(n); n = PARTS[n].parent
        return inc


def static(keys):
    return all(k[1] == keys[0][1] for k in keys)


# ------------------------------------------------------------------ Lottie
def st(v): return {'a': 0, 'k': v}


TR = {'ty': 'tr', 'p': st([0, 0]), 'a': st([0, 0]), 's': st([100, 100]), 'r': st(0), 'o': st(100),
      'sk': st(0), 'sa': st(0)}


def lot_item(it):
    k = it['k']
    if k == 'path':
        r = lambda a: [[round(x, 2) for x in p] for p in a]
        return {'ty': 'sh', 'ks': st({'i': r(it['i']), 'o': r(it['o']), 'v': r(it['v']), 'c': it['c']})}
    if k == 'ell':
        return {'ty': 'el', 'p': st([it['cx'], it['cy']]), 's': st([it['w'], it['h']]), 'd': 1}
    if k == 'fill':
        return {'ty': 'fl', 'c': st(rgba(it['c'])), 'o': st(it['o']), 'r': 1}
    if k == 'stroke':
        return {'ty': 'st', 'c': st(rgba(it['c'])), 'o': st(it['o']), 'w': st(it['w']), 'lc': 2, 'lj': 2, 'ml': 4}
    return {'ty': 'gr', 'it': [lot_item(x) for x in it['it']] + [TR]}


def lconv(part, prop, v):
    p = PARTS[part]
    if prop == 'p':
        return [round(p.pos[0] + v[0], 2), round(p.pos[1] + v[1], 2), 0]
    if prop == 's':
        return [round(v[0] * p.scale / 100, 3), round(v[1] * p.scale / 100, 3), 100]
    return [round(v, 3)]


def lot_prop(part, prop, keys):
    if static(keys):
        v = lconv(part, prop, keys[0][1])
        return st(v[0] if prop in 'ro' else v)
    out = []
    for j, (t, v, e) in enumerate(keys):
        sv = lconv(part, prop, v)
        d = {'t': round(t, 3), 's': sv}
        if j < len(keys) - 1:
            if e == 'h':
                d['h'] = 1
            else:
                x1, y1, x2, y2 = EASE[e]; n = len(sv)
                d['o'] = {'x': [x1] * n, 'y': [y1] * n}
                d['i'] = {'x': [x2] * n, 'y': [y2] * n}
        out.append(d)
    return {'a': 1, 'k': out}


def to_lottie(c):
    inc = c.included()
    top = [n for n in reversed(DRAW_ORDER) if n in inc]
    ind = {n: i + 1 for i, n in enumerate(top)}
    layers = []
    for n in top:
        p = PARTS[n]
        ks = {pr: lot_prop(n, pr, c.track(n, pr)) for pr in ('o', 'r', 'p', 's')}
        ks['a'] = st([p.anchor[0], p.anchor[1], 0])
        L = {'ddd': 0, 'ind': ind[n], 'ty': 3 if p.null else 4, 'nm': n, 'sr': 1, 'ks': ks, 'ao': 0,
             'ip': 0, 'op': c.T, 'st': 0, 'bm': 0}
        if not p.null:
            L['shapes'] = [lot_item(g) for g in p.items]
        if p.parent != 'COMP':
            L['parent'] = ind[p.parent]
        layers.append(L)
    return {'v': '5.7.4', 'fr': FR, 'ip': 0, 'op': c.T, 'w': W, 'h': H, 'nm': c.name, 'ddd': 0,
            'assets': [], 'layers': layers,
            'markers': [{'tm': t, 'cm': m, 'dr': d} for t, m, d in c.markers]}


# ------------------------------------------------------------------ SVG
def f2(x):
    s = f'{x:.2f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def d_of(it):
    if it['k'] == 'ell':
        cx, cy, rx, ry = it['cx'], it['cy'], it['w'] / 2, it['h'] / 2
        return (f"M{f2(cx - rx)} {f2(cy)}A{f2(rx)} {f2(ry)} 0 1 0 {f2(cx + rx)} {f2(cy)}"
                f"A{f2(rx)} {f2(ry)} 0 1 0 {f2(cx - rx)} {f2(cy)}Z")
    v, i, o = it['v'], it['i'], it['o']
    n = len(v)
    out = [f"M{f2(v[0][0])} {f2(v[0][1])}"]
    for a in list(range(n - 1)) + ([n - 1] if it['c'] else []):
        b = (a + 1) % n
        if o[a] == [0, 0] and i[b] == [0, 0]:
            out.append(f"L{f2(v[b][0])} {f2(v[b][1])}")
        else:
            out.append('C' + ' '.join(f2(x) for x in (v[a][0] + o[a][0], v[a][1] + o[a][1],
                                                       v[b][0] + i[b][0], v[b][1] + i[b][1], v[b][0], v[b][1])))
    if it['c']:
        out.append('Z')
    return ''.join(out)


def path_el(d, fill=None, stroke=None):
    a = [f'd="{d}"']
    if fill:
        a.append(f'fill="{fill["c"]}"')
        if fill['o'] < 100:
            a.append(f'fill-opacity="{f2(fill["o"] / 100)}"')
    else:
        a.append('fill="none"')
    if stroke:
        a.append(f'stroke="{stroke["c"]}" stroke-width="{f2(stroke["w"])}" '
                 f'stroke-linecap="round" stroke-linejoin="round"')
        if stroke['o'] < 100:
            a.append(f'stroke-opacity="{f2(stroke["o"] / 100)}"')
    return f'<path {" ".join(a)}/>'


def svg_item(it):
    subs = [x for x in it['it'] if x['k'] == 'grp']
    shapes = [x for x in it['it'] if x['k'] in ('path', 'ell')]
    styles = [x for x in it['it'] if x['k'] in ('fill', 'stroke')]
    out = [svg_item(g) for g in reversed(subs)]
    if shapes and styles:
        d = ''.join(d_of(s) for s in shapes)
        sty = list(reversed(styles))
        j = 0
        while j < len(sty):
            a = sty[j]
            if a['k'] == 'fill' and j + 1 < len(sty) and sty[j + 1]['k'] == 'stroke':
                out.append(path_el(d, a, sty[j + 1])); j += 2
            else:
                out.append(path_el(d, a if a['k'] == 'fill' else None, a if a['k'] == 'stroke' else None)); j += 1
    return ''.join(out)


def sval(part, prop, v):
    p = PARTS[part]
    if prop == 'p':
        return f'{f2(p.pos[0] + v[0])} {f2(p.pos[1] + v[1])}'
    if prop == 's':
        return f'{f2(v[0] * p.scale / 10000)} {f2(v[1] * p.scale / 10000)}'
    if prop == 'o':
        return f2(v / 100)
    return f2(v)


def svg_anim(part, prop, keys, c):
    T = c.T
    times, vals, spl = [], [], []
    for j, (t, v, e) in enumerate(keys):
        times.append(t); vals.append(v)
        if j < len(keys) - 1:
            t2 = keys[j + 1][0]
            if e == 'h':
                times.append(max(t + (t2 - t) * 0.5, t2 - 0.4)); vals.append(v)
                spl += [EASE['l'], EASE['l']]
            else:
                spl.append(EASE[e])
    kt = ';'.join(f'{t / T:.5f}' for t in times)
    vs = ';'.join(sval(part, prop, v) for v in vals)
    ks = ';'.join(' '.join(f2(x) for x in s) for s in spl)
    rep = 'repeatCount="1" fill="freeze"' if c.once else 'repeatCount="indefinite"'
    timing = f'values="{vs}" keyTimes="{kt}" calcMode="spline" keySplines="{ks}" dur="{f2(T / FR)}s" {rep}'
    if prop == 'o':
        return f'<animate attributeName="opacity" {timing}/>'
    typ = {'p': 'translate', 'r': 'rotate', 's': 'scale'}[prop]
    return f'<animateTransform attributeName="transform" type="{typ}" {timing}/>'


def svg_part(n, c, inc):
    p = PARTS[n]
    inner = ''
    for ch in CHILDREN.get(n, ['SELF']):
        if ch == 'SELF':
            inner += ''.join(svg_item(g) for g in reversed(p.items))
        elif ch in inc:
            inner += svg_part(ch, c, inc)
    ax, ay = p.anchor
    tr = {pr: c.track(n, pr) for pr in ('s', 'r', 'p', 'o')}
    s_st, r_st, p_st = static(tr['s']), static(tr['r']), static(tr['p'])
    sv, rv, pv = tr['s'][0][1], tr['r'][0][1], tr['p'][0][1]
    if s_st and r_st and p_st and rv == 0 and sv[0] * p.scale == 10000 and sv[1] * p.scale == 10000:
        dx, dy = p.pos[0] + pv[0] - ax, p.pos[1] + pv[1] - ay
        if (round(dx, 2), round(dy, 2)) != (0, 0):
            inner = f'<g transform="translate({f2(dx)} {f2(dy)})">{inner}</g>'
    else:
        if (ax, ay) != (0, 0):
            inner = f'<g transform="translate({f2(-ax)} {f2(-ay)})">{inner}</g>'
        for pr in ('s', 'r', 'p'):
            keys = tr[pr]
            if static(keys):
                v = keys[0][1]
                if pr == 's':
                    tf = f'scale({sval(n, "s", v)})'
                elif pr == 'r':
                    tf = f'rotate({f2(v)})'
                else:
                    tf = f'translate({sval(n, "p", v)})'
                if tf not in ('scale(1 1)', 'rotate(0)', 'translate(0 0)'):
                    inner = f'<g transform="{tf}">{inner}</g>'
            else:
                inner = f'<g>{svg_anim(n, pr, keys, c)}{inner}</g>'
    o = tr['o']
    if static(o):
        if o[0][1] < 100:
            inner = f'<g opacity="{f2(o[0][1] / 100)}">{inner}</g>'
    else:
        inner = f'<g opacity="{f2(o[0][1] / 100)}">{svg_anim(n, "o", o, c)}{inner}</g>'
    return f'<g data-part="{n}">{inner}</g>'


def to_svg(c):
    inc = c.included()
    body = ''.join(svg_part(ch, c, inc) for ch in CHILDREN['COMP'] if ch in inc)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
            f'<title>{c.name}</title>{body}</svg>')
