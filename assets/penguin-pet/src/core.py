"""Penguin rig core: geometry, layers, tracks, and two exporters (Lottie 5.7 + SMIL SVG)
that are driven from one shared data model so both formats carry identical motion."""
import re, math, copy, json

FPS = 30
W = H = 512

# ---------------------------------------------------------------- palette
OUT = '#2d2440'      # dark navy-brown outline
NAVY = '#3f4b7d'     # soft dark navy
WHITE = '#fdfbf6'
BEAK = '#ffc247'
FOOT = '#ff9b47'
SCARF = '#e8584f'
SCARF_D = '#bf3f3d'
CHEEK = '#ff9db1'
CHEEK_COLD = '#a9d7f6'
TONGUE = '#ff8fa3'
MOUTH = '#7b2f47'
EYE = '#272039'
HEART = '#ff7b9a'
SPARK = '#ffd66c'
SNOW = '#e9f6ff'
ICE = '#d3efff'
ICE_D = '#9fd2ef'
FISH = '#7cc6e8'
FISH_D = '#4f9dc7'
PEBBLE = '#a9a8b6'
ZCOL = '#9aa9e2'
RED = '#ee5f55'
TEAR = '#9fd4f6'
SW = 7.5             # character stroke in local units (x0.8 scale -> 6px)

K = 0.5522847498

# ---------------------------------------------------------------- geometry
class Contour:
    def __init__(self, v, i, o, closed=True):
        self.v, self.i, self.o, self.closed = v, i, o, closed

    def xform(self, fn, lin):
        return Contour([fn(p) for p in self.v], [lin(p) for p in self.i],
                       [lin(p) for p in self.o], self.closed)

def ellipse(cx, cy, rx, ry=None):
    ry = rx if ry is None else ry
    v = [(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)]
    o = [(K * rx, 0), (0, K * ry), (-K * rx, 0), (0, -K * ry)]
    i = [(-K * rx, 0), (0, -K * ry), (K * rx, 0), (0, K * ry)]
    return [Contour(v, i, o, True)]

_tok = re.compile(r'[MLCQZ]|-?\d*\.?\d+(?:e-?\d+)?')

def path(d):
    toks = _tok.findall(d)
    cons, cur, k, cmd = [], None, 0, None
    def num():
        nonlocal k
        x = float(toks[k]); k += 1
        return x
    def pt():
        return (num(), num())
    def close():
        nonlocal cur
        if cur is None:
            return
        v, i, o = cur
        if len(v) > 1 and abs(v[0][0] - v[-1][0]) < 1e-6 and abs(v[0][1] - v[-1][1]) < 1e-6:
            i[0] = i[-1]; v.pop(); i.pop(); o.pop()
        cons.append(Contour(v, i, o, True)); cur = None
    while k < len(toks):
        t = toks[k]
        if t in 'MLCQZ':
            cmd = t; k += 1
            if cmd == 'Z':
                close(); continue
        if cmd == 'M':
            if cur is not None:
                cons.append(Contour(*cur, closed=False))
            p = pt(); cur = ([p], [(0, 0)], [(0, 0)]); cmd = 'L'
        elif cmd == 'L':
            p = pt(); cur[0].append(p); cur[1].append((0, 0)); cur[2].append((0, 0))
        elif cmd == 'C':
            c1, c2, p = pt(), pt(), pt()
            p0 = cur[0][-1]
            cur[2][-1] = (c1[0] - p0[0], c1[1] - p0[1])
            cur[0].append(p); cur[1].append((c2[0] - p[0], c2[1] - p[1])); cur[2].append((0, 0))
        elif cmd == 'Q':
            q, p = pt(), pt()
            p0 = cur[0][-1]
            c1 = (p0[0] + 2 / 3 * (q[0] - p0[0]), p0[1] + 2 / 3 * (q[1] - p0[1]))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            cur[2][-1] = (c1[0] - p0[0], c1[1] - p0[1])
            cur[0].append(p); cur[1].append((c2[0] - p[0], c2[1] - p[1])); cur[2].append((0, 0))
    if cur is not None:
        cons.append(Contour(*cur, closed=False))
    return cons

def poly(pts, closed=True):
    return [Contour(list(pts), [(0, 0)] * len(pts), [(0, 0)] * len(pts), closed)]

def tx(cons, dx=0, dy=0, sx=1, sy=None, rot=0):
    sy = sx if sy is None else sy
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    def lin(p):
        x, y = p[0] * sx, p[1] * sy
        return (x * c - y * s, x * s + y * c)
    def fn(p):
        x, y = lin(p)
        return (x + dx, y + dy)
    out = [cn.xform(fn, lin) for cn in cons]
    if sx * sy < 0:  # keep orientation tidy after a mirror
        pass
    return out

def mirror(cons):
    return tx(cons, sx=-1, sy=1)

class Shape:
    def __init__(self, cons, fill=None, stroke=None, sw=SW, fo=1.0, so=1.0, nm='s'):
        self.cons, self.fill, self.stroke, self.sw, self.fo, self.so, self.nm = cons, fill, stroke, sw, fo, so, nm

def S(cons, fill=None, stroke=OUT, sw=SW, fo=1.0, so=1.0, nm='s'):
    return Shape(cons, fill, stroke, sw, fo, so, nm)

def F(cons, fill, fo=1.0, nm='f'):
    return Shape(cons, fill, None, 0, fo, 1, nm)

def L(cons, stroke=OUT, sw=SW, so=1.0, nm='l'):
    return Shape(cons, None, stroke, sw, 1, so, nm)

# ---------------------------------------------------------------- layers & tracks
EASE = {
    'io': (0.42, 0, 0.58, 1),
    'sin': (0.37, 0, 0.63, 1),
    'lin': (0, 0, 1, 1),
    'in': (0.42, 0, 1, 1),
    'out': (0, 0, 0.58, 1),
    'outq': (0.22, 0.6, 0.36, 1),
    'inq': (0.55, 0.05, 0.68, 0.19),
    'outx': (0.1, 0.8, 0.3, 1),
}

class Layer:
    def __init__(self, name, parent=None, pivot=(0, 0), pos=None, shapes=None,
                 rot=0.0, scale=(1, 1), op=1.0, z=0.0):
        self.name, self.parent = name, parent
        self.anchor = tuple(pivot)
        self.pos = tuple(pos) if pos is not None else tuple(pivot)
        self.rot, self.scale, self.op = rot, tuple(scale), op
        self.shapes = shapes  # None => null layer
        self.z = z
        self.tr = {}          # prop -> list of (frame, value, ease)
        self.step = set()     # props that are hold/step tracks

    def rest(self, prop):
        return {'p': (0.0, 0.0), 'r': self.rot, 's': self.scale, 'o': self.op}[prop]

def vadd(a, b):
    if isinstance(a, tuple):
        return tuple(x + y for x, y in zip(a, b))
    return a + b

def vmul(a, k):
    if isinstance(a, tuple):
        return tuple(x * k for x in a)
    return a * k

def vlerp(a, b, t):
    return vadd(vmul(a, 1 - t), vmul(b, t))

def norm(prop, v):
    if prop in ('p', 's') and not isinstance(v, tuple):
        v = (float(v), float(v))
    if isinstance(v, tuple):
        return tuple(float(x) for x in v)
    return float(v)

def bez_ease(e, x):
    """y for x on cubic-bezier easing e (x1,y1,x2,y2)."""
    x1, y1, x2, y2 = e
    lo, hi = 0.0, 1.0
    for _ in range(40):
        t = (lo + hi) / 2
        bx = 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3
        if bx < x: lo = t
        else: hi = t
    t = (lo + hi) / 2
    return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3

def sample(keys, f, step=False):
    if f <= keys[0][0]:
        return keys[0][1]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= f <= b[0]:
            if step:
                return b[1] if f >= b[0] else a[1]
            if b[0] == a[0]:
                return b[1]
            x = (f - a[0]) / (b[0] - a[0])
            return vlerp(a[1], b[1], bez_ease(EASE[b[2]], x))
    return keys[-1][1]

# ---------------------------------------------------------------- clip container
class Clip:
    def __init__(self, name, cat, frames, loop, layers, holds=False, note=''):
        self.name, self.cat, self.N, self.loop = name, cat, frames, loop
        self.layers = layers  # dict name->Layer (ordered)
        self.holds = holds    # loop that holds a non-base pose (documented)
        self.note = note

    def __getitem__(self, n):
        return self.layers[n]

    def add(self, layer):
        assert layer.name not in self.layers, layer.name
        self.layers[layer.name] = layer
        return layer

    def k(self, lname, prop, keys, step=False):
        lay = self.layers[lname]
        assert prop not in lay.tr, f'{self.name}: duplicate track {lname}.{prop}'
        ks = []
        for kk in keys:
            f, v = kk[0], kk[1]
            e = kk[2] if len(kk) > 2 else 'io'
            ks.append((float(f), norm(prop, v), e))
        ks.sort(key=lambda t: t[0])
        ded = []
        for kk in ks:  # same-frame duplicates: keep the later one
            if ded and abs(ded[-1][0] - kk[0]) < 1e-9:
                ded[-1] = kk
            else:
                ded.append(kk)
        lay.tr[prop] = ded
        if step:
            lay.step.add(prop)

    def show(self, lname, keys):
        """step-opacity track: keys = [(frame, 0|1), ...]"""
        self.k(lname, 'o', [(f, float(v), 'lin') for f, v in keys], step=True)

    def swap(self, group, default, segs):
        """visibility swap among variant layers.
        group: list of layer names; default: name shown at rest;
        segs: [(f_start, name), ...] — from f_start the named variant shows (until next)."""
        timeline = [(0, default)] + list(segs)
        for nm in group:
            keys, last = [], None
            for f, show_nm in timeline:
                v = 1 if show_nm == nm else 0
                if v != last:
                    keys.append((f, v)); last = v
            if len(keys) == 1 and keys[0][1] == self.layers[nm].op:
                continue
            self.show(nm, keys)

    def poses(self, seq):
        """seq: [(frame, {'layer.prop': value, ...}, ease), ...]; missing props -> rest value."""
        props = []
        for item in seq:
            for key in item[1]:
                if key not in props:
                    props.append(key)
        for key in props:
            ln, pr = key.rsplit('.', 1)
            lay = self.layers[ln]
            keys = []
            for item in seq:
                f, d = item[0], item[1]
                e = item[2] if len(item) > 2 else 'io'
                keys.append((f, d.get(key, lay.rest(pr)), e))
            self.k(ln, pr, keys)

    # ----- finalize: pad tracks to [0, N]
    def finalize(self):
        N = self.N
        for lay in self.layers.values():
            for pr, ks in lay.tr.items():
                if ks[0][0] > 0:
                    ks.insert(0, (0.0, ks[0][1], 'lin'))
                if ks[-1][0] < N:
                    ks.append((float(N), ks[-1][1], 'lin'))
                assert ks[-1][0] <= N + 1e-6, f'{self.name} {lay.name}.{pr} key beyond N'
        # prune: content layers invisible all clip, and nulls without used descendants
        used = set()
        for lay in self.layers.values():
            if lay.shapes is not None:
                hidden = lay.op == 0 and 'o' not in lay.tr
                if not hidden:
                    n = lay.name
                    while n:
                        used.add(n); n = self.layers[n].parent
        self.layers = {n: l for n, l in self.layers.items() if n in used}

    def value(self, lname, prop, f):
        lay = self.layers[lname]
        if prop in lay.tr:
            return sample(lay.tr[prop], f, prop in lay.step)
        return lay.rest(prop)

# ---------------------------------------------------------------- number formatting
def fmt(x):
    s = f'{x:.3f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

def rgba(hexc):
    h = hexc.lstrip('#')
    return [round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)] + [1]

# ---------------------------------------------------------------- Lottie export
def _lot_anim(keys, conv, step):
    if keys is None:
        return None
    out = []
    for j, (f, v, e) in enumerate(keys):
        d = {'t': round(f, 4), 's': conv(v)}
        if j < len(keys) - 1:
            if step:
                d['h'] = 1
            else:
                x1, y1, x2, y2 = EASE[keys[j + 1][2]]
                d['o'] = {'x': [x1], 'y': [y1]}
                d['i'] = {'x': [x2], 'y': [y2]}
        out.append(d)
    return {'a': 1, 'k': out}

def _lot_shape_group(sh, idx):
    items = []
    for c in sh.cons:
        items.append({'ty': 'sh', 'nm': 'p', 'ks': {'a': 0, 'k': {
            'c': c.closed,
            'v': [[round(p[0], 3), round(p[1], 3)] for p in c.v],
            'i': [[round(p[0], 3), round(p[1], 3)] for p in c.i],
            'o': [[round(p[0], 3), round(p[1], 3)] for p in c.o]}}})
    if sh.stroke:
        items.append({'ty': 'st', 'nm': 'stroke', 'c': {'a': 0, 'k': rgba(sh.stroke)},
                      'o': {'a': 0, 'k': round(sh.so * 100, 2)}, 'w': {'a': 0, 'k': sh.sw},
                      'lc': 2, 'lj': 2, 'ml': 4, 'bm': 0})
    if sh.fill:
        items.append({'ty': 'fl', 'nm': 'fill', 'c': {'a': 0, 'k': rgba(sh.fill)},
                      'o': {'a': 0, 'k': round(sh.fo * 100, 2)}, 'r': 1, 'bm': 0})
    items.append({'ty': 'tr', 'p': {'a': 0, 'k': [0, 0]}, 'a': {'a': 0, 'k': [0, 0]},
                  's': {'a': 0, 'k': [100, 100]}, 'r': {'a': 0, 'k': 0}, 'o': {'a': 0, 'k': 100},
                  'sk': {'a': 0, 'k': 0}, 'sa': {'a': 0, 'k': 0}})
    return {'ty': 'gr', 'nm': f'{sh.nm}{idx}', 'it': items, 'np': len(sh.cons), 'bm': 0}

def to_lottie(clip):
    N = clip.N
    lays = list(clip.layers.values())
    ind = {l.name: i + 1 for i, l in enumerate(lays)}
    out = []
    for lay in sorted(lays, key=lambda l: -l.z):
        tr = lay.tr
        px, py = lay.pos
        if 'p' in tr:
            kx = [(f, px + v[0], e) for f, v, e in tr['p']]
            ky = [(f, py + v[1], e) for f, v, e in tr['p']]
            p = {'s': True, 'x': _lot_anim(kx, lambda v: [round(v, 3)], False),
                 'y': _lot_anim(ky, lambda v: [round(v, 3)], False)}
        else:
            p = {'a': 0, 'k': [px, py, 0]}
        r = _lot_anim(tr.get('r'), lambda v: [round(v, 3)], 'r' in lay.step) or {'a': 0, 'k': lay.rot}
        s = _lot_anim(tr.get('s'), lambda v: [round(v[0] * 100, 3), round(v[1] * 100, 3), 100], 's' in lay.step) \
            or {'a': 0, 'k': [lay.scale[0] * 100, lay.scale[1] * 100, 100]}
        o = _lot_anim(tr.get('o'), lambda v: [round(v * 100, 3)], 'o' in lay.step) or {'a': 0, 'k': lay.op * 100}
        L = {'ddd': 0, 'ind': ind[lay.name], 'ty': 3 if lay.shapes is None else 4, 'nm': lay.name, 'sr': 1,
             'ks': {'o': o, 'r': r, 'p': p, 'a': {'a': 0, 'k': [lay.anchor[0], lay.anchor[1], 0]}, 's': s},
             'ao': 0, 'ip': 0, 'op': N, 'st': 0, 'bm': 0}
        if lay.parent:
            L['parent'] = ind[lay.parent]
        if lay.shapes is not None:
            L['shapes'] = [_lot_shape_group(sh, i) for i, sh in reversed(list(enumerate(lay.shapes)))]
        out.append(L)
    return {'v': '5.7.0', 'fr': FPS, 'ip': 0, 'op': N, 'w': W, 'h': H, 'nm': clip.name, 'ddd': 0,
            'assets': [], 'layers': out, 'markers': []}

# ---------------------------------------------------------------- SVG (SMIL) export
def svg_d(cons):
    parts = []
    for c in cons:
        v, i, o = c.v, c.i, c.o
        parts.append(f'M{fmt(v[0][0])} {fmt(v[0][1])}')
        n = len(v)
        segs = n if c.closed else n - 1
        for j in range(segs):
            a, b = j, (j + 1) % n
            if o[a] == (0, 0) and i[b] == (0, 0):
                parts.append(f'L{fmt(v[b][0])} {fmt(v[b][1])}')
            else:
                parts.append('C' + ' '.join(fmt(x) for x in (
                    v[a][0] + o[a][0], v[a][1] + o[a][1], v[b][0] + i[b][0], v[b][1] + i[b][1], v[b][0], v[b][1])))
        if c.closed:
            parts.append('Z')
    return ''.join(parts)

def svg_shape(sh):
    a = [f'd="{svg_d(sh.cons)}"']
    a.append(f'fill="{sh.fill}"' if sh.fill else 'fill="none"')
    if sh.fill and sh.fo != 1:
        a.append(f'fill-opacity="{fmt(sh.fo)}"')
    if sh.stroke:
        a.append(f'stroke="{sh.stroke}" stroke-width="{fmt(sh.sw)}" stroke-linecap="round" stroke-linejoin="round"')
        if sh.so != 1:
            a.append(f'stroke-opacity="{fmt(sh.so)}"')
    return '<path ' + ' '.join(a) + '/>'

class _Smil:
    def __init__(self, clip):
        self.N, self.loop = clip.N, clip.loop
        self.timing = f'dur="{self.N / FPS:.4f}s" begin="0s" ' + \
            ('repeatCount="indefinite"' if clip.loop else 'fill="freeze"')

    def anim(self, tag_attrs, keys, conv, step):
        N = self.N
        kt = ';'.join(fmt(f / N) for f, _, _ in keys)
        vals = ';'.join(conv(v) for _, v, _ in keys)
        if step:
            mode = 'calcMode="discrete"'
        else:
            spl = ';'.join(' '.join(fmt(x) for x in EASE[e]) for _, _, e in keys[1:])
            mode = f'calcMode="spline" keySplines="{spl}"'
        return f'<{tag_attrs} values="{vals}" keyTimes="{kt}" {mode} {self.timing}/>'

def to_svg(clip):
    sm = _Smil(clip)
    lays = clip.layers
    body = []
    defs_cache = {}

    def chain_open(lay):
        """returns list of (open_tag, needs_close) for the transform of one layer"""
        tr = lay.tr
        ops = []  # list of ('static', str) or ('anim', element)
        px, py = lay.pos
        if 'p' in tr:
            ops.append(('anim', sm.anim('animateTransform attributeName="transform" type="translate"', [
                (f, (px + v[0], py + v[1]), e) for f, v, e in tr['p']],
                lambda v: f'{fmt(v[0])} {fmt(v[1])}', 'p' in lay.step)))
        elif (px, py) != (0, 0):
            ops.append(('static', f'translate({fmt(px)} {fmt(py)})'))
        if 'r' in tr:
            ops.append(('anim', sm.anim('animateTransform attributeName="transform" type="rotate"', tr['r'],
                                        lambda v: fmt(v), 'r' in lay.step)))
        elif lay.rot:
            ops.append(('static', f'rotate({fmt(lay.rot)})'))
        if 's' in tr:
            ops.append(('anim', sm.anim('animateTransform attributeName="transform" type="scale"', tr['s'],
                                        lambda v: f'{fmt(v[0])} {fmt(v[1])}', 's' in lay.step)))
        elif tuple(lay.scale) != (1, 1):
            ops.append(('static', f'scale({fmt(lay.scale[0])} {fmt(lay.scale[1])})'))
        ax, ay = lay.anchor
        if (ax, ay) != (0, 0):
            ops.append(('static', f'translate({fmt(-ax)} {fmt(-ay)})'))
        # identity collapse for static-only pivot layers
        if all(k == 'static' for k, _ in ops) and (px, py) == (ax, ay) and not lay.rot and tuple(lay.scale) == (1, 1):
            return []
        groups, pend = [], []
        for kind, val in ops:
            if kind == 'static':
                pend.append(val)
            else:
                if pend:
                    groups.append(f'<g transform="{" ".join(pend)}">'); pend = []
                groups.append(f'<g>{val}')
        if pend:
            groups.append(f'<g transform="{" ".join(pend)}">')
        return groups

    for lay in sorted(lays.values(), key=lambda l: l.z):
        if lay.shapes is None:
            continue
        chain = []
        n = lay.name
        while n:
            chain.append(lays[n]); n = lays[n].parent
        chain.reverse()
        opens = []
        for c in chain:
            opens += chain_open(c)
        if 'o' in lay.tr:
            opens.append('<g>' + sm.anim('animate attributeName="opacity"', lay.tr['o'],
                                         lambda v: fmt(v), 'o' in lay.step))
        elif lay.op != 1:
            opens.append(f'<g opacity="{fmt(lay.op)}">')
        body.append(f'<!-- {lay.name} -->' + ''.join(opens) + ''.join(svg_shape(s) for s in lay.shapes)
                    + '</g>' * len(opens))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">'
            f'<title>{clip.name}</title>\n' + '\n'.join(body) + '\n</svg>\n')
