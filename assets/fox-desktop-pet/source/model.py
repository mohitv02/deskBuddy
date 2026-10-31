"""Tiny rig engine: one scene graph -> bodymovin 5.7 Lottie JSON + SMIL SVG.

Every animated property becomes its own nested group level, so both formats
compose transforms identically:  T(pivot+x,0) T(0,y) R(r) S(sx,1) S(1,sy) T(-pivot)
"""
import math, json

FPS = 30
K = 0.5522847498

EASE = {
    'io':   (0.42, 0.0, 0.58, 1.0),   # ease-in-out (default)
    'sine': (0.37, 0.0, 0.63, 1.0),
    'i':    (0.55, 0.0, 1.0, 1.0),    # ease-in (accelerate)
    'o':    (0.0, 0.0, 0.45, 1.0),    # ease-out (decelerate)
    'lin':  (0.0, 0.0, 1.0, 1.0),
    'snap': (0.12, 0.9, 0.3, 1.0),    # springy fast-out
    'pop':  (0.2, 0.75, 0.35, 1.0),
    'h':    None,                      # hold
}


def r2(v):
    v = round(v, 2)
    if v == int(v):
        return int(v)
    return v


def hexrgb(h):
    h = h.lstrip('#')
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


# ----------------------------------------------------------------- geometry
class Path:
    def __init__(self, v, i=None, o=None, closed=True):
        self.v = [tuple(p) for p in v]
        n = len(self.v)
        self.i = [tuple(p) for p in (i or [(0, 0)] * n)]
        self.o = [tuple(p) for p in (o or [(0, 0)] * n)]
        self.closed = closed

    def map(self, f, flip=False):
        """f maps points; tangents are mapped as vectors via f(p+t)-f(p)."""
        v = [f(p) for p in self.v]
        i = []
        o = []
        for p, a, b, q in zip(self.v, self.i, self.o, v):
            fa = f((p[0] + a[0], p[1] + a[1]))
            fb = f((p[0] + b[0], p[1] + b[1]))
            i.append((fa[0] - q[0], fa[1] - q[1]))
            o.append((fb[0] - q[0], fb[1] - q[1]))
        return Path(v, i, o, self.closed)

    def mirror(self, cx=256):
        return self.map(lambda p: (2 * cx - p[0], p[1]))

    def move(self, dx, dy):
        return self.map(lambda p: (p[0] + dx, p[1] + dy))

    def rot(self, deg, cx, cy):
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        return self.map(lambda p: (cx + (p[0] - cx) * c - (p[1] - cy) * s,
                                   cy + (p[0] - cx) * s + (p[1] - cy) * c))

    def scale(self, sx, sy, cx, cy):
        return self.map(lambda p: (cx + (p[0] - cx) * sx, cy + (p[1] - cy) * sy))

    def d(self):
        n = len(self.v)
        f = lambda x: ('%.2f' % x).rstrip('0').rstrip('.')
        out = ['M%s %s' % (f(self.v[0][0]), f(self.v[0][1]))]
        segs = n if self.closed else n - 1
        for k in range(segs):
            a, b = k, (k + 1) % n
            pa, pb = self.v[a], self.v[b]
            c1 = (pa[0] + self.o[a][0], pa[1] + self.o[a][1])
            c2 = (pb[0] + self.i[b][0], pb[1] + self.i[b][1])
            out.append('C%s %s %s %s %s %s' % tuple(f(x) for x in (*c1, *c2, *pb)))
        if self.closed:
            out.append('Z')
        return ''.join(out)

    def lottie(self):
        R = lambda L: [[r2(x), r2(y)] for x, y in L]
        return {"ty": "sh", "ind": 0, "ks": {"a": 0, "k": {
            "i": R(self.i), "o": R(self.o), "v": R(self.v), "c": self.closed}}, "nm": "Path"}


def ellipse(cx, cy, rx, ry=None):
    ry = rx if ry is None else ry
    v = [(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)]
    o = [(rx * K, 0), (0, ry * K), (-rx * K, 0), (0, -ry * K)]
    i = [(-rx * K, 0), (0, -ry * K), (rx * K, 0), (0, ry * K)]
    return Path(v, i, o, True)


def smooth(pts, closed=True, t=1.0):
    """Catmull-Rom through points. A point may be (x, y, s): s scales its
    tangent (0 = sharp corner)."""
    P = [(p[0], p[1]) for p in pts]
    S = [(p[2] if len(p) > 2 else 1.0) for p in pts]
    n = len(P)
    ins, outs = [], []
    for k in range(n):
        if closed:
            a, b = P[(k - 1) % n], P[(k + 1) % n]
        else:
            a = P[k - 1] if k > 0 else P[k]
            b = P[k + 1] if k < n - 1 else P[k]
        tx, ty = (b[0] - a[0]) / 6 * t * S[k], (b[1] - a[1]) / 6 * t * S[k]
        if not closed and (k == 0 or k == n - 1):
            tx, ty = tx * 2, ty * 2
        outs.append((tx, ty))
        ins.append((-tx, -ty))
    if not closed:
        ins[0] = (0, 0)
        outs[-1] = (0, 0)
    return Path(P, ins, outs, closed)


def poly(pts, closed=True):
    return Path(pts, None, None, closed)


class Shape:
    def __init__(self, paths, fill=None, stroke=None, sw=7.5, fo=1.0, so=1.0, cap='round', name='shape'):
        self.paths = paths if isinstance(paths, list) else [paths]
        self.fill, self.stroke, self.sw, self.fo, self.so = fill, stroke, sw, fo, so
        self.cap = cap
        self.name = name


# ----------------------------------------------------------------- scene graph
PROPS = ('x', 'y', 'r', 'sx', 'sy', 'o')
PDEF = {'x': 0, 'y': 0, 'r': 0, 'sx': 1, 'sy': 1, 'o': 1}


class Node:
    def __init__(self, name, pivot=(0, 0), children=(), base=None, track=None, show=None):
        self.name = name
        self.track = track or name
        self.pivot = pivot
        self.children = list(children)
        self.base = dict(base or {})
        self.show = show   # (state_name, set_of_values) -> visibility

    def add(self, *c):
        self.children.extend(c)
        return self


class Rig:
    def __init__(self, root):
        self.root = root
        self.defaults = {}
        self.state_defaults = {}
        self.tracks_known = set()
        self._walk(root)

    def _walk(self, n):
        if isinstance(n, Shape):
            return
        for p in PROPS:
            key = n.track + '.' + p
            v = n.base.get(p, PDEF[p])
            if key in self.defaults and self.defaults[key] != v:
                raise ValueError('conflicting default ' + key)
            self.defaults[key] = v
        for c in n.children:
            self._walk(c)


# ----------------------------------------------------------------- clips
class Clip:
    def __init__(self, name, cat, frames, loop=True, note='', autobase=True, settle=None):
        self.name, self.cat, self.frames, self.loop = name, cat, frames, loop
        self.settle = settle
        self.note = note
        self.autobase = autobase
        self.tracks = {}   # 'node.prop' -> [(t, v, ease)]
        self.states = {}   # state -> [(t, value)]

    # keys: (t, v) or (t, v, ease)  -- ease applies to segment starting at this key
    def k(self, track, *keys):
        L = self.tracks.setdefault(track, [])
        for kk in keys:
            t, v = kk[0], kk[1]
            e = kk[2] if len(kk) > 2 else 'io'
            L[:] = [x for x in L if abs(x[0] - t) > 1e-6]
            L.append((t, v, e))
        L.sort(key=lambda x: x[0])
        return self

    def pose(self, t, d, ease='io'):
        for tr, v in d.items():
            self.k(tr, (t, v, ease))
        return self

    def hold(self, t0, t1, d, ease='io'):
        self.pose(t0, d, ease)
        self.pose(t1, d, ease)
        return self

    def st(self, state, *keys):
        L = self.states.setdefault(state, [])
        for t, v in keys:
            L[:] = [x for x in L if x[0] != t]
            L.append((t, v))
        L.sort(key=lambda x: x[0])
        return self

    def osc(self, track, t0, t1, center, amp, cycles, ease='sine', phase=0.0, end=None):
        """Oscillate from center: center -> +amp -> -amp ... -> center/end."""
        n = int(round(cycles * 2))
        step = (t1 - t0) / (n + 1)
        self.k(track, (t0, center, ease))
        sgn = 1 if phase == 0 else -1
        for j in range(n):
            self.k(track, (t0 + step * (j + 1), center + sgn * amp, ease))
            sgn = -sgn
        self.k(track, (t1, center if end is None else end, ease))
        return self


def finalize(clip, rig):
    N = clip.frames
    out = {}
    for tr, keys in clip.tracks.items():
        if tr not in rig.defaults:
            raise KeyError('%s: unknown track %s' % (clip.name, tr))
        base = rig.defaults[tr]
        keys = list(keys)
        if keys[0][0] > 0:
            keys.insert(0, (0, base, 'io'))
        if clip.settle is not None and keys[-1][0] < clip.settle and keys[-1][1] != base:
            keys.append((clip.settle, base, 'io'))
        if keys[-1][0] < N:
            endv = base if (clip.loop and clip.autobase) else keys[-1][1]
            keys.append((N, endv, 'io'))
        keys = [k for k in keys if k[0] <= N]
        out[tr] = keys
    sts = {}
    for s, keys in clip.states.items():
        if s not in rig.state_defaults:
            raise KeyError('%s: unknown state %s' % (clip.name, s))
        d = rig.state_defaults[s]
        keys = list(keys)
        if keys[0][0] > 0:
            keys.insert(0, (0, d))
        sts[s] = keys
    return out, sts


def is_static(keys):
    return all(abs(k[1] - keys[0][1]) < 1e-9 for k in keys)


def expand_holds(keys):
    """Mixed hold+spline: replace hold segment by a near-instant step."""
    if all(k[2] == 'h' for k in keys[:-1]):
        return keys, True
    out = []
    for j, k in enumerate(keys):
        if k[2] == 'h' and j < len(keys) - 1:
            out.append((k[0], k[1], 'lin'))
            out.append((keys[j + 1][0] - 0.05, k[1], 'lin'))
        else:
            out.append(k)
    return out, False


# ----------------------------------------------------------------- export
class Exporter:
    def __init__(self, rig, clip):
        self.rig = rig
        self.clip = clip
        self.N = clip.frames
        self.tracks, self.states = finalize(clip, rig)

    # value spec for a node prop: ('s', v) or ('a', keys, discrete)
    def prop(self, node, p):
        key = node.track + '.' + p
        if key in self.tracks:
            keys = self.tracks[key]
            if is_static(keys):
                return ('s', keys[0][1])
            keys, disc = expand_holds(keys)
            return ('a', keys, disc)
        return ('s', self.rig.defaults[key])

    def vis(self, node):
        """visibility from state: ('s', 0/1) or ('a', keys, True)"""
        if not node.show:
            return ('s', 1)
        s, vals = node.show
        keys = self.states.get(s)
        if keys is None:
            return ('s', 1 if self.rig.state_defaults[s] in vals else 0)
        ks = [(t, 1 if v in vals else 0, 'h') for t, v in keys]
        # collapse
        c = [ks[0]]
        for k in ks[1:]:
            if k[1] != c[-1][1]:
                c.append(k)
        if len(c) == 1:
            return ('s', c[0][1])
        return ('a', c, True)

    def visible_ever(self, node):
        v = self.vis(node)
        if v[0] == 's' and v[1] == 0:
            return False
        o = self.prop(node, 'o')
        if o[0] == 's' and o[1] == 0:
            return False
        return True

    # ---------------- SVG
    def smil(self, kind, keys, disc, conv):
        N = self.N
        if disc:   # switch a hair early so frame t shows the new state, exactly like a Lottie hold key
            kt = ';'.join(r2_str(max(0.0, (k[0] - (0.02 if j else 0)) / N), 6) for j, k in enumerate(keys))
        else:
            kt = ';'.join(r2_str(k[0] / N, 6) for k in keys)
        vals = ';'.join(conv(k[1]) for k in keys)
        timing = 'dur="%ss" begin="0s" %s' % (r2_str(N / FPS, 4),
                                               'repeatCount="indefinite"' if self.clip.loop else 'fill="freeze"')
        if disc:
            mode = 'calcMode="discrete"'
        else:
            spl = ';'.join('%g %g %g %g' % EASE[k[2]] for k in keys[:-1])
            mode = 'calcMode="spline" keySplines="%s"' % spl
        if kind == 'opacity':
            return '<animate attributeName="opacity" values="%s" keyTimes="%s" %s %s/>' % (vals, kt, mode, timing)
        return '<animateTransform attributeName="transform" type="%s" values="%s" keyTimes="%s" %s %s/>' % (
            kind, vals, kt, mode, timing)

    def svg_node(self, n, out):
        if isinstance(n, Shape):
            out.append(svg_shape(n))
            return
        if not self.visible_ever(n):
            return
        px, py = n.pivot
        P = {p: self.prop(n, p) for p in PROPS}
        V = self.vis(n)
        levels = [
            ('translate', P['x'], lambda v: '%s 0' % fs(v), lambda v: v == 0),
            ('translate', P['y'], lambda v: '0 %s' % fs(v), lambda v: v == 0),
            ('rotate', P['r'], lambda v: fs(v), lambda v: v == 0),
            ('scale', P['sx'], lambda v: '%s 1' % fs(v), lambda v: v == 1),
            ('scale', P['sy'], lambda v: '1 %s' % fs(v), lambda v: v == 1),
        ]
        anim_any = any(L[1][0] == 'a' for L in levels)
        static_tf = [L for L in levels if L[1][0] == 's' and not L[3](L[1][1])]
        opened = 0
        if not anim_any:
            if static_tf:
                tf = 'translate(%s %s) ' % (fs(px), fs(py)) + ' '.join(
                    '%s(%s)' % (L[0], L[2](L[1][1])) for L in static_tf) + ' translate(%s %s)' % (fs(-px), fs(-py))
                out.append('<g transform="%s">' % tf)
                opened += 1
        else:
            pending = ['translate(%s %s)' % (fs(px), fs(py))]
            for kind, spec, conv, ident in levels:
                if spec[0] == 's':
                    if not ident(spec[1]):
                        pending.append('%s(%s)' % (kind, conv(spec[1])))
                else:
                    if pending:
                        out.append('<g transform="%s">' % ' '.join(pending))
                        opened += 1
                        pending = []
                    out.append('<g>' + self.smil(kind, spec[1], spec[2], conv))
                    opened += 1
            pending.append('translate(%s %s)' % (fs(-px), fs(-py)))
            out.append('<g transform="%s">' % ' '.join(pending))
            opened += 1
        # visibility (state) then opacity
        for spec in (V, P['o']):
            if spec[0] == 'a':
                out.append('<g>' + self.smil('opacity', spec[1], spec[2], lambda v: fs(v)))
                opened += 1
            elif spec[1] != 1:
                out.append('<g opacity="%s">' % fs(spec[1]))
                opened += 1
        for c in n.children:
            self.svg_node(c, out)
        out.append('</g>' * opened)

    def svg(self):
        out = ['<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">',
               '<title>%s</title>' % self.clip.name]
        self.svg_node(self.rig.root, out)
        out.append('</svg>')
        return ''.join(out)

    # ---------------- Lottie
    def lprop(self, spec, conv, dims):
        if spec[0] == 's':
            v = conv(spec[1])
            return {"a": 0, "k": v if dims > 1 else v[0]}
        keys, disc = spec[1], spec[2]
        kf = []
        for j, (t, v, e) in enumerate(keys):
            d = {"t": r2(t), "s": conv(v)}
            if j < len(keys) - 1:
                if disc or e == 'h':
                    d["h"] = 1
                else:
                    x1, y1, x2, y2 = EASE[e]
                    d["o"] = {"x": [x1], "y": [y1]}
                    d["i"] = {"x": [x2], "y": [y2]}
            kf.append(d)
        return {"a": 1, "k": kf}

    def ltr(self, p=None, a=None, s=None, r=None, o=None):
        st = lambda v: {"a": 0, "k": v}
        return {"ty": "tr", "p": p or st([0, 0]), "a": a or st([0, 0]), "s": s or st([100, 100]),
                "r": r or st(0), "o": o or st(100), "sk": st(0), "sa": st(0), "nm": "Transform"}

    def lot_node(self, n):
        if isinstance(n, Shape):
            return lottie_shape(n)
        if not self.visible_ever(n):
            return None
        items = []
        for c in reversed(n.children):   # lottie: first item draws on top
            g = self.lot_node(c)
            if g:
                items.append(g)
        px, py = n.pivot
        P = {p: self.prop(n, p) for p in PROPS}
        V = self.vis(n)
        grp = lambda its, tr, nm: {"ty": "gr", "it": its + [tr], "nm": nm, "np": len(its), "cix": 2, "bm": 0}
        anim_any = any(P[p][0] == 'a' for p in ('x', 'y', 'r', 'sx', 'sy'))
        # innermost: opacity + (if static) whole transform
        o_spec = P['o']
        if not anim_any:
            tr = self.ltr(p={"a": 0, "k": [r2(px + P['x'][1]), r2(py + P['y'][1])]},
                          a={"a": 0, "k": [r2(px), r2(py)]},
                          s={"a": 0, "k": [r2(P['sx'][1] * 100), r2(P['sy'][1] * 100)]},
                          r={"a": 0, "k": r2(P['r'][1])},
                          o=self.lprop(o_spec, lambda v: [r2(v * 100)], 1))
            g = grp(items, tr, n.name)
        else:
            tr = self.ltr(a={"a": 0, "k": [r2(px), r2(py)]}, o=self.lprop(o_spec, lambda v: [r2(v * 100)], 1))
            g = grp(items, tr, n.name + '_o')
            for p, mk in (('sy', lambda v: {'s': self.lprop(v, lambda q: [100, r2(q * 100)], 2)}),
                          ('sx', lambda v: {'s': self.lprop(v, lambda q: [r2(q * 100), 100], 2)}),
                          ('r', lambda v: {'r': self.lprop(v, lambda q: [r2(q)], 1)}),
                          ('y', lambda v: {'p': self.lprop(v, lambda q: [0, r2(q)], 2)})):
                spec = P[p]
                if spec[0] == 's' and spec[1] == PDEF[p]:
                    continue
                g = grp([g], self.ltr(**mk(spec)), n.name + '_' + p)
            g = grp([g], self.ltr(p=self.lprop(P['x'], lambda q: [r2(px + q), r2(py)], 2)), n.name)
        if V[0] == 'a':
            g = grp([g], self.ltr(o=self.lprop(V, lambda v: [v * 100], 1)), n.name + '_vis')
        return g

    def lottie(self):
        root = self.lot_node(self.rig.root)
        N = self.N
        st = lambda v: {"a": 0, "k": v}
        layer = {"ddd": 0, "ind": 1, "ty": 4, "nm": "fox", "sr": 1,
                 "ks": {"o": st(100), "r": st(0), "p": st([0, 0, 0]), "a": st([0, 0, 0]), "s": st([100, 100, 100])},
                 "ao": 0, "shapes": [root], "ip": 0, "op": N, "st": 0, "bm": 0}
        return {"v": "5.7.0", "fr": FPS, "ip": 0, "op": N, "w": 512, "h": 512, "nm": self.clip.name,
                "ddd": 0, "assets": [], "layers": [layer], "markers": []}


def fs(v):
    return ('%.3f' % v).rstrip('0').rstrip('.') if v != int(v) else str(int(v))


def r2_str(v, n):
    s = ('%.' + str(n) + 'f') % v
    return s.rstrip('0').rstrip('.') if '.' in s else s


def svg_shape(s):
    d = ''.join(p.d() for p in s.paths)
    a = ['d="%s"' % d]
    a.append('fill="%s"' % (s.fill or 'none'))
    if s.fill and s.fo != 1:
        a.append('fill-opacity="%s"' % fs(s.fo))
    if s.stroke:
        a.append('stroke="%s" stroke-width="%s" stroke-linejoin="round" stroke-linecap="%s"' % (
            s.stroke, fs(s.sw), s.cap))
        if s.so != 1:
            a.append('stroke-opacity="%s"' % fs(s.so))
    return '<path %s/>' % ' '.join(a)


def lottie_shape(s):
    it = [p.lottie() for p in s.paths]
    if s.stroke:
        it.append({"ty": "st", "c": {"a": 0, "k": hexrgb(s.stroke) + [1]}, "o": {"a": 0, "k": r2(s.so * 100)},
                   "w": {"a": 0, "k": r2(s.sw)}, "lc": 2 if s.cap == 'round' else 1, "lj": 2, "ml": 4, "bm": 0,
                   "nm": "Stroke"})
    if s.fill:
        it.append({"ty": "fl", "c": {"a": 0, "k": hexrgb(s.fill) + [1]}, "o": {"a": 0, "k": r2(s.fo * 100)},
                   "r": 1, "bm": 0, "nm": "Fill"})
    st = lambda v: {"a": 0, "k": v}
    it.append({"ty": "tr", "p": st([0, 0]), "a": st([0, 0]), "s": st([100, 100]), "r": st(0), "o": st(100),
               "sk": st(0), "sa": st(0), "nm": "Transform"})
    return {"ty": "gr", "it": it, "nm": s.name, "np": len(it) - 1, "cix": 2, "bm": 0}
