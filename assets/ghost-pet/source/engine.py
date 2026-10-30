"""Tiny shared scene model that exports the *same* keyframes to
Lottie (bodymovin 5.7 JSON) and to self-contained SMIL SVG.

Model
  Scene  -> layers (bottom..top), each Layer has an opacity track + root Group
  Group  -> transform tracks p,a,s,r,o and children (bottom..top)
  Shape  -> one or more Path tracks, optional fill colour track, optional stroke

A track is a list of keyframes (t, value, ease) where ease is a cubic-bezier
tuple (x1,y1,x2,y2) for the segment *leaving* that key, or HOLD.
Transform order is Lottie's:  T(p) . R(r) . S(s) . T(-a)
"""
import math

EASE = (0.42, 0.0, 0.58, 1.0)  # ease-in-out (CSS "ease-in-out")
HOLD = 'hold'
FPS = 30


# ----------------------------------------------------------------- paths
class Path:
    __slots__ = ('v', 'i', 'o', 'c')

    def __init__(self, v, i, o, c):
        self.v, self.i, self.o, self.c = v, i, o, c

    def ctrl(self):
        """absolute control points per segment: list of (p0,c1,c2,p3)"""
        n = len(self.v)
        segs = []
        rng = range(n) if self.c else range(n - 1)
        for k in rng:
            a, b = k, (k + 1) % n
            p0 = self.v[a]
            c1 = (p0[0] + self.o[a][0], p0[1] + self.o[a][1])
            p3 = self.v[b]
            c2 = (p3[0] + self.i[b][0], p3[1] + self.i[b][1])
            segs.append((p0, c1, c2, p3))
        return segs

    def svg(self):
        f = fmt2
        s = 'M%s %s' % (f(self.v[0][0]), f(self.v[0][1]))
        for p0, c1, c2, p3 in self.ctrl():
            s += 'C%s %s %s %s %s %s' % (f(c1[0]), f(c1[1]), f(c2[0]), f(c2[1]), f(p3[0]), f(p3[1]))
        if self.c:
            s += 'Z'
        return s

    def lottie(self):
        r = lambda pts: [[round(x, 2), round(y, 2)] for x, y in pts]
        return {'i': r(self.i), 'o': r(self.o), 'v': r(self.v), 'c': self.c}

    def map(self, fn):
        """apply affine-ish point function fn to all points (tangents via ctrl)"""
        v = [fn(p) for p in self.v]
        i = []
        o = []
        for k, p in enumerate(self.v):
            ia = fn((p[0] + self.i[k][0], p[1] + self.i[k][1]))
            oa = fn((p[0] + self.o[k][0], p[1] + self.o[k][1]))
            i.append((ia[0] - v[k][0], ia[1] - v[k][1]))
            o.append((oa[0] - v[k][0], oa[1] - v[k][1]))
        return Path(v, i, o, self.c)

    def lerp(self, other, u):
        assert len(self.v) == len(other.v), 'path vertex count mismatch'
        L = lambda A, B: [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u) for a, b in zip(A, B)]
        return Path(L(self.v, other.v), L(self.i, other.i), L(self.o, other.o), self.c)


class PB:
    """path builder with absolute coordinates, every segment stored as cubic"""

    def __init__(self, x, y):
        self.v = [(x, y)]
        self.i = [(0, 0)]
        self.o = [(0, 0)]

    def C(self, x1, y1, x2, y2, x, y):
        lx, ly = self.v[-1]
        self.o[-1] = (x1 - lx, y1 - ly)
        self.v.append((x, y))
        self.i.append((x2 - x, y2 - y))
        self.o.append((0, 0))
        return self

    def L(self, x, y):
        lx, ly = self.v[-1]
        return self.C(lx, ly, x, y, x, y)

    def Z(self):
        (fx, fy), (lx, ly) = self.v[0], self.v[-1]
        if abs(fx - lx) < 1e-6 and abs(fy - ly) < 1e-6 and len(self.v) > 1:
            self.i[0] = self.i[-1]
            self.v.pop(); self.i.pop(); self.o.pop()
        return Path(self.v, self.i, self.o, True)

    def open(self):
        return Path(self.v, self.i, self.o, False)


K = 0.5523


def ellipse(cx, cy, rx, ry):
    return Path([(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)],
                [(-rx * K, 0), (0, -ry * K), (rx * K, 0), (0, ry * K)],
                [(rx * K, 0), (0, ry * K), (-rx * K, 0), (0, -ry * K)], True)


def poly(pts, closed=False):
    b = PB(*pts[0])
    for p in pts[1:]:
        b.L(*p)
    if closed:
        b.L(*pts[0])
        return b.Z()
    return b.open()


def bez(p0, c1, c2, p3, t):
    mt = 1 - t
    return (mt ** 3 * p0[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p3[0],
            mt ** 3 * p0[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p3[1])


def split_bez(p0, c1, c2, p3, t):
    L = lambda a, b: (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    a, b, c = L(p0, c1), L(c1, c2), L(c2, p3)
    d, e = L(a, b), L(b, c)
    f = L(d, e)
    return (p0, a, d, f), (f, e, c, p3)


def fmt2(x):
    s = ('%.2f' % x).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def fmt4(x):
    s = ('%.4f' % x).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


# ----------------------------------------------------------------- values
def hex2rgb(h):
    h = h.lstrip('#')
    return [int(h[k:k + 2], 16) / 255 for k in (0, 2, 4)]


def rgb2hex(c):
    return '#%02x%02x%02x' % tuple(max(0, min(255, round(x * 255))) for x in c)


def kind(v):
    if v is None:
        return 'other'
    if hasattr(v, 'svg'):
        return 'path'
    if isinstance(v, str):
        return 'color'
    if isinstance(v, (list, tuple)):
        return 'vec'
    if isinstance(v, dict):
        return 'dict'
    return 'num'


def lerp(a, b, u):
    k = kind(a)
    if k == 'path':
        return a.lerp(b, u)
    if k == 'color':
        A, B = hex2rgb(a), hex2rgb(b)
        return rgb2hex([x + (y - x) * u for x, y in zip(A, B)])
    if k == 'vec':
        return [x + (y - x) * u for x, y in zip(a, b)]
    if k == 'dict':
        keys = set(a) | set(b)
        return {q: lerp(a.get(q, b.get(q)), b.get(q, a.get(q)), u) for q in keys}
    return a + (b - a) * u


def eq(a, b):
    k = kind(a)
    if k == 'path':
        return a.svg() == b.svg()
    if k == 'vec':
        return all(abs(x - y) < 1e-6 for x, y in zip(a, b))
    if k == 'num':
        return abs(a - b) < 1e-6
    if k == 'dict':
        return set(a) == set(b) and all(eq(a[q], b[q]) for q in a)
    return a == b


# ----------------------------------------------------------------- tracks
def bez1(e, s):
    """timing curve point at curve parameter s"""
    x1, y1, x2, y2 = e
    p = bez((0, 0), (x1, y1), (x2, y2), (1, 1), s)
    return p


def solve_s(e, x):
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        if bez1(e, m)[0] < x:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def split_ease(e, u):
    """split timing curve e at time fraction u -> (progress, eL, eR)"""
    s = solve_s(e, u)
    x1, y1, x2, y2 = e
    A, B = split_bez((0, 0), (x1, y1), (x2, y2), (1, 1), s)
    xs, ys = A[3]

    def norm(seg, ox, oy, sx, sy):
        return tuple(round(v, 5) for v in (
            (seg[1][0] - ox) / sx, (seg[1][1] - oy) / sy, (seg[2][0] - ox) / sx, (seg[2][1] - oy) / sy))
    eL = norm(A, 0, 0, xs, ys if ys > 1e-9 else 1)
    eR = norm(B, xs, ys, 1 - xs, (1 - ys) if 1 - ys > 1e-9 else 1)
    clamp = lambda t: tuple(min(1.0, max(0.0, v)) if k % 2 == 0 else v for k, v in enumerate(t))
    return ys, clamp(eL), clamp(eR)


def ease_value(e, u):
    if e == HOLD:
        return 0.0
    return bez1(e, solve_s(e, u))[1]


class Track:
    def __init__(self, kfs):
        # kfs: list of (t, value) or (t, value, ease)
        out = []
        for k in kfs:
            if len(k) == 2:
                out.append((float(k[0]), k[1], EASE))
            else:
                out.append((float(k[0]), k[1], k[2]))
        out.sort(key=lambda k: k[0])
        self.kfs = out

    def at(self, t):
        k = self.kfs
        if t <= k[0][0]:
            return k[0][1]
        for a, b in zip(k, k[1:]):
            if a[0] <= t <= b[0]:
                if b[0] == a[0]:
                    return b[1]
                if a[2] == HOLD:
                    return a[1] if t < b[0] else b[1]
                return lerp(a[1], b[1], ease_value(a[2], (t - a[0]) / (b[0] - a[0])))
        return k[-1][1]

    def fit(self, N):
        """split at 0 and N, drop outside keys, pad ends"""
        k = list(self.kfs)
        for B in (0.0, float(N)):
            for j in range(len(k) - 1):
                a, b = k[j], k[j + 1]
                if a[0] < B < b[0]:
                    u = (B - a[0]) / (b[0] - a[0])
                    if a[2] == HOLD:
                        k[j:j + 2] = [a, (B, a[1], HOLD), b]
                    else:
                        prog, eL, eR = split_ease(a[2], u)
                        mid = lerp(a[1], b[1], prog)
                        k[j:j + 2] = [(a[0], a[1], eL), (B, mid, eR), b]
                    break
        k = [x for x in k if -1e-9 <= x[0] <= N + 1e-9]
        hold = all(x[2] == HOLD for x in k[:-1]) if len(k) > 1 else (k and k[0][2] == HOLD)
        if k[0][0] > 0:
            k.insert(0, (0.0, k[0][1], HOLD if hold else EASE))
        if k[-1][0] < N:
            k.append((float(N), k[-1][1], k[-1][2]))
        # merge duplicate times (keep the later one)
        out = []
        for x in k:
            if out and abs(out[-1][0] - x[0]) < 1e-6:
                out[-1] = x
            else:
                out.append(x)
        self.kfs = out
        return self

    def static(self):
        return all(eq(self.kfs[0][1], x[1]) for x in self.kfs)

    def mode(self):
        segs = [x[2] for x in self.kfs[:-1]]
        if all(s == HOLD for s in segs):
            return 'hold'
        if any(s == HOLD for s in segs):
            raise ValueError('mixed hold/ease track')
        return 'ease'


def S(v):
    return Track([(0, v)])


def as_track(v):
    if isinstance(v, Track):
        return v
    return S(v)


def wave(N, cycles, lo, hi, phase=0.0):
    """sinusoid-like oscillation from lo (at u=k) to hi (at u=k+.5), eased
    between extremes, split exactly at 0 and N so the loop is seamless"""
    period = N / cycles
    kfs = []
    k = math.floor((-phase) * 2) - 2
    while True:
        t = (k / 2 - phase) * period
        if t > N + period:
            break
        kfs.append((t, lo if k % 2 == 0 else hi))
        k += 1
    return Track(kfs).fit(N)


def steps(kfs):
    return Track([(t, v, HOLD) for t, v in kfs])


# ----------------------------------------------------------------- scene
class Shape:
    def __init__(self, paths, fill=None, stroke=None, width=0, fill_opacity=1.0, name='shape', cap='round'):
        self.paths = [as_track(p) for p in (paths if isinstance(paths, list) else [paths])]
        self.fill = as_track(fill) if fill is not None else None
        self.stroke = stroke
        self.width = width
        self.fo = fill_opacity
        self.name = name
        self.cap = cap


class Group:
    def __init__(self, name, children=None, p=(0, 0), a=(0, 0), s=(100, 100), r=0, o=100):
        self.name = name
        self.children = children or []
        self.p, self.a, self.s, self.r, self.o = (as_track(x) for x in (p, a, s, r, o))


class Layer:
    def __init__(self, name, group, o=100):
        self.name, self.group, self.o = name, group, as_track(o)


# ----------------------------------------------------------------- lottie
def lval(v):
    k = kind(v)
    if k == 'path':
        return v.lottie()
    if k == 'color':
        return hex2rgb(v) + [1]
    if k == 'vec':
        return [round(x, 3) for x in v]
    return round(v, 3)


def lprop(tr, N, scale=1.0):
    tr.fit(N)
    conv = (lambda v: v * scale) if scale != 1.0 else (lambda v: v)
    if tr.static():
        return {'a': 0, 'k': lval(conv(tr.kfs[0][1]))}
    ks = []
    for j, (t, v, e) in enumerate(tr.kfs):
        val = lval(conv(v))
        if kind(v) == 'path':
            val = [val]
        elif not isinstance(val, list):
            val = [val]
        kf = {'t': round(t, 4), 's': val}
        if j < len(tr.kfs) - 1:
            if e == HOLD:
                kf['h'] = 1
            else:
                kf['o'] = {'x': e[0], 'y': e[1]}
                kf['i'] = {'x': e[2], 'y': e[3]}
        ks.append(kf)
    return {'a': 1, 'k': ks}


def lottie_item(node, N, ix):
    if isinstance(node, Shape):
        it = []
        for p in node.paths:
            it.append({'ty': 'sh', 'nm': 'Path', 'ks': lprop(p, N), 'hd': False})
        if node.stroke:
            it.append({'ty': 'st', 'nm': 'Stroke', 'c': lprop(S(node.stroke), N), 'o': {'a': 0, 'k': 100},
                       'w': {'a': 0, 'k': node.width}, 'lc': 2 if node.cap == 'round' else 1, 'lj': 2,
                       'bm': 0, 'hd': False})
        if node.fill is not None:
            it.append({'ty': 'fl', 'nm': 'Fill', 'c': lprop(node.fill, N), 'o': {'a': 0, 'k': round(node.fo * 100, 2)},
                       'r': 1, 'bm': 0, 'hd': False})
        it.append(ltr(Group('t'), N))
        return {'ty': 'gr', 'nm': node.name, 'it': it, 'np': len(it) - 1, 'cix': 2, 'bm': 0, 'ix': ix, 'hd': False}
    it = [lottie_item(c, N, k + 1) for k, c in enumerate(reversed(node.children))]
    it.append(ltr(node, N))
    return {'ty': 'gr', 'nm': node.name, 'it': it, 'np': len(it) - 1, 'cix': 2, 'bm': 0, 'ix': ix, 'hd': False}


def ltr(g, N):
    return {'ty': 'tr', 'nm': 'Transform', 'p': lprop(g.p, N), 'a': lprop(g.a, N), 's': lprop(g.s, N),
            'r': lprop(g.r, N), 'o': lprop(g.o, N), 'sk': {'a': 0, 'k': 0}, 'sa': {'a': 0, 'k': 0}}


def to_lottie(name, N, layers):
    out = []
    for idx, L in enumerate(reversed(layers)):
        out.append({'ddd': 0, 'ind': idx + 1, 'ty': 4, 'nm': L.name, 'sr': 1,
                    'ks': {'o': lprop(L.o, N), 'r': {'a': 0, 'k': 0}, 'p': {'a': 0, 'k': [0, 0, 0]},
                           'a': {'a': 0, 'k': [0, 0, 0]}, 's': {'a': 0, 'k': [100, 100, 100]}},
                    'ao': 0, 'shapes': [lottie_item(L.group, N, 1)], 'ip': 0, 'op': N, 'st': 0, 'bm': 0})
    return {'v': '5.7.0', 'fr': FPS, 'ip': 0, 'op': N, 'w': 512, 'h': 512, 'nm': name, 'ddd': 0,
            'assets': [], 'layers': out, 'markers': []}


# ----------------------------------------------------------------- svg
class SvgCtx:
    def __init__(self, N, loop):
        self.N, self.loop = N, loop
        self.timing = 'dur="%ss" begin="0s" %s' % (fmt4(N / FPS), 'repeatCount="indefinite"' if loop else 'fill="freeze"')


def sval(v, how):
    if how == 'translate':
        return '%s %s' % (fmt2(v[0]), fmt2(v[1]))
    if how == 'neg':
        return '%s %s' % (fmt2(-v[0]), fmt2(-v[1]))
    if how == 'scale':
        return '%s %s' % (fmt4(v[0] / 100), fmt4(v[1] / 100))
    if how == 'rotate':
        return fmt2(v)
    if how == 'opacity':
        return fmt4(v / 100)
    if how == 'path':
        return v.svg()
    return str(v)


def sanim(tr, ctx, attr, how, ttype=None):
    tr.fit(ctx.N)
    times = ';'.join(fmt4(t / ctx.N) for t, _, _ in tr.kfs)
    vals = ';'.join(sval(v, how) for _, v, _ in tr.kfs)
    if tr.mode() == 'hold':
        mode = 'calcMode="discrete"'
    else:
        mode = 'calcMode="spline" keySplines="%s"' % ';'.join(
            ' '.join(fmt4(x) for x in e) for _, _, e in tr.kfs[:-1])
    if ttype:
        return '<animateTransform attributeName="transform" type="%s" values="%s" keyTimes="%s" %s %s/>' % (
            ttype, vals, times, mode, ctx.timing)
    return '<animate attributeName="%s" values="%s" keyTimes="%s" %s %s/>' % (attr, vals, times, mode, ctx.timing)


def svg_node(node, ctx, ind=''):
    if isinstance(node, Shape):
        attrs = []
        anims = []
        dtracks = node.paths
        for t in dtracks:
            t.fit(ctx.N)
        if all(t.static() for t in dtracks):
            attrs.append('d="%s"' % ''.join(t.kfs[0][1].svg() for t in dtracks))
        else:
            times = [x[0] for x in dtracks[0].kfs]
            for t in dtracks:
                assert [x[0] for x in t.kfs] == times or t.static(), 'subpaths must share key times'
            merged = []
            for j, (tm, _, e) in enumerate(dtracks[0].kfs):
                merged.append((tm, MultiPath([t.kfs[j][1] if not t.static() else t.kfs[0][1] for t in dtracks]), e))
            mt = Track(merged)
            attrs.append('d="%s"' % merged[0][1].svg())
            anims.append(sanim(mt, ctx, 'd', 'path'))
        if node.fill is not None:
            node.fill.fit(ctx.N)
            attrs.append('fill="%s"' % node.fill.kfs[0][1])
            if not node.fill.static():
                anims.append(sanim(node.fill, ctx, 'fill', 'color'))
            if node.fo != 1:
                attrs.append('fill-opacity="%s"' % fmt4(node.fo))
        else:
            attrs.append('fill="none"')
        if node.stroke:
            attrs.append('stroke="%s" stroke-width="%s" stroke-linecap="%s" stroke-linejoin="round"' % (
                node.stroke, fmt2(node.width), 'round' if node.cap == 'round' else 'butt'))
        if anims:
            return '%s<path %s>%s</path>\n' % (ind, ' '.join(attrs), ''.join(anims))
        return '%s<path %s/>\n' % (ind, ' '.join(attrs))

    g = node
    for t in (g.p, g.a, g.s, g.r, g.o):
        t.fit(ctx.N)
    parts = [('translate', g.p, 'translate'), ('rotate', g.r, 'rotate'), ('scale', g.s, 'scale'),
             ('translate', g.a, 'neg')]
    ident = {'translate': lambda v: abs(v[0]) < 1e-9 and abs(v[1]) < 1e-9,
             'neg': lambda v: abs(v[0]) < 1e-9 and abs(v[1]) < 1e-9,
             'rotate': lambda v: abs(v) < 1e-9,
             'scale': lambda v: abs(v[0] - 100) < 1e-9 and abs(v[1] - 100) < 1e-9}
    wrappers = []  # list of (static_transform_str or None, anim_str or None)
    pending = []
    for ttype, tr, how in parts:
        if tr.static():
            v = tr.kfs[0][1]
            if not ident[how](v):
                if ttype == 'rotate':
                    pending.append('rotate(%s)' % fmt2(v))
                elif ttype == 'scale':
                    pending.append('scale(%s %s)' % (fmt4(v[0] / 100), fmt4(v[1] / 100)))
                else:
                    pending.append('translate(%s)' % sval(v, how))
        else:
            if pending:
                wrappers.append(('transform="%s"' % ' '.join(pending), ''))
                pending = []
            wrappers.append(('', sanim(tr, ctx, None, how, ttype)))
    if pending:
        wrappers.append(('transform="%s"' % ' '.join(pending), ''))
    op_attr, op_anim = '', ''
    if g.o.static():
        if abs(g.o.kfs[0][1] - 100) > 1e-9:
            op_attr = 'opacity="%s"' % fmt4(g.o.kfs[0][1] / 100)
    else:
        op_attr = 'opacity="%s"' % fmt4(g.o.kfs[0][1] / 100)
        op_anim = sanim(g.o, ctx, 'opacity', 'opacity')
    # first wrapper carries the id + opacity
    out = ''
    opens = []
    first = True
    if not wrappers:
        wrappers = [('', '')]
    for attr, anim in wrappers:
        a = []
        if first:
            a.append('class="%s"' % g.name)
            if op_attr:
                a.append(op_attr)
        if attr:
            a.append(attr)
        out += '%s<g %s>%s%s\n' % (ind, ' '.join(a), op_anim if first else '', anim)
        first = False
        opens.append('</g>')
    for c in g.children:
        out += svg_node(c, ctx, ind + ' ')
    out += ind + ''.join(opens) + '\n'
    return out


class MultiPath:
    def __init__(self, paths):
        self.paths = paths

    def svg(self):
        return ''.join(p.svg() for p in self.paths)

    def lerp(self, other, u):
        return MultiPath([a.lerp(b, u) for a, b in zip(self.paths, other.paths)])


def to_svg(name, N, layers, loop):
    ctx = SvgCtx(N, loop)
    body = ''
    for L in layers:
        L.o.fit(N)
        attr = ''
        anim = ''
        if L.o.static():
            if abs(L.o.kfs[0][1] - 100) > 1e-9:
                attr = ' opacity="%s"' % fmt4(L.o.kfs[0][1] / 100)
        else:
            attr = ' opacity="%s"' % fmt4(L.o.kfs[0][1] / 100)
            anim = sanim(L.o, ctx, 'opacity', 'opacity')
        body += '<g id="L_%s"%s>%s\n%s</g>\n' % (L.name, attr, anim, svg_node(L.group, ctx, ' '))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">\n'
            '<title>%s</title>\n%s</svg>\n' % (name, body))
