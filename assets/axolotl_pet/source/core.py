"""Core: geometry, scene graph, keyframe tracks and the two exporters (Lottie 5.7 + SMIL SVG).

Every clip is described once (rig + tracks) and compiled to both formats, so motion is identical.

Node transform (both formats):
    T(p) R(r) S(s) T(dp) R(dr) S(ds) T(-a)
  pose slot  = p, r, s     (absolute pose values; anchor-relative)
  anim slot  = dp, dr, ds  (offsets layered on top, pivoting around the anchor)
"""
import math, re, json

KAPPA = 0.5522847498
EIO = (0.42, 0.0, 0.58, 1.0)      # ease-in-out used for every move
FPS = 30


def fmt(x, nd=3):
    if abs(x) < 0.5 * 10 ** -nd:
        return '0'
    s = f"{x:.{nd}f}".rstrip('0').rstrip('.')
    return s


# ------------------------------------------------------------------ matrices
def m_mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * F + e, b * E + d * F + f)


def m_t(x, y):
    return (1, 0, 0, 1, x, y)


def m_r(deg):
    t = math.radians(deg)
    return (math.cos(t), math.sin(t), -math.sin(t), math.cos(t), 0, 0)


def m_s(sx, sy=None):
    return (sx, 0, 0, sx if sy is None else sy, 0, 0)


def m_apply(m, p):
    a, b, c, d, e, f = m
    return (a * p[0] + c * p[1] + e, b * p[0] + d * p[1] + f)


def M(*ms):
    out = (1, 0, 0, 1, 0, 0)
    for m in ms:
        out = m_mul(out, m)
    return out


# ------------------------------------------------------------------ paths
class Sub:
    """One bezier subpath: vertices with absolute in/out handles."""

    def __init__(self, closed=False):
        self.v, self.i, self.o = [], [], []
        self.closed = closed

    def add(self, v, i=None, o=None):
        self.v.append(tuple(v))
        self.i.append(tuple(i) if i is not None else tuple(v))
        self.o.append(tuple(o) if o is not None else tuple(v))

    def xf(self, m):
        s = Sub(self.closed)
        s.v = [m_apply(m, p) for p in self.v]
        s.i = [m_apply(m, p) for p in self.i]
        s.o = [m_apply(m, p) for p in self.o]
        return s


def xf(subs, *ms):
    m = M(*ms)
    return [s.xf(m) for s in subs]


def _arc_to_cubic(x1, y1, rx, ry, phi, fa, fs, x2, y2):
    if rx == 0 or ry == 0:
        return [((x1, y1), (x2, y2), (x2, y2))]
    phi = math.radians(phi)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1:
        rx *= math.sqrt(lam); ry *= math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = math.sqrt(max(0, num / den)) if den else 0
    if fa == fs:
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    n = max(1, int(math.ceil(abs(dt) / (math.pi / 2) - 1e-9)))
    d = dt / n
    out = []
    k = 4 / 3 * math.tan(d / 4)
    for j in range(n):
        a1 = t1 + j * d
        a2 = a1 + d
        p1 = (math.cos(a1), math.sin(a1))
        p2 = (math.cos(a2), math.sin(a2))
        c1 = (p1[0] - k * p1[1], p1[1] + k * p1[0])
        c2 = (p2[0] + k * p2[1], p2[1] - k * p2[0])

        def tr(p):
            x, y = p[0] * rx, p[1] * ry
            return (cp * x - sp * y + cx, sp * x + cp * y + cy)
        out.append((tr(c1), tr(c2), tr(p2)))
    return out


def P(d):
    """Parse an SVG path string (M L H V C S Q A Z, abs+rel) into Subs."""
    toks = re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', d)
    subs, cur = [], None
    i, n = 0, len(toks)
    cmd = None
    pos = (0.0, 0.0)
    start = pos
    lastc = None

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v

    def close():
        nonlocal pos
        cur.closed = True
        if len(cur.v) > 1 and math.dist(cur.v[-1], cur.v[0]) < 1e-6:
            cur.i[0] = cur.i[-1]
            cur.v.pop(); cur.i.pop(); cur.o.pop()
        pos = start

    while i < n:
        if toks[i].isalpha():
            cmd = toks[i]; i += 1
            if cmd in 'Zz':
                close(); lastc = None
                continue
        rel = cmd.islower()
        C = cmd.upper()
        ox, oy = pos if rel else (0.0, 0.0)
        if C == 'M':
            x, y = num() + ox, num() + oy
            cur = Sub(); subs.append(cur); cur.add((x, y))
            pos = start = (x, y)
            cmd = 'l' if rel else 'L'
            lastc = None
        elif C == 'L':
            x, y = num() + ox, num() + oy
            cur.add((x, y)); pos = (x, y); lastc = None
        elif C == 'H':
            x = num() + (pos[0] if rel else 0)
            cur.add((x, pos[1])); pos = (x, pos[1]); lastc = None
        elif C == 'V':
            y = num() + (pos[1] if rel else 0)
            cur.add((pos[0], y)); pos = (pos[0], y); lastc = None
        elif C == 'C':
            c1 = (num() + ox, num() + oy); c2 = (num() + ox, num() + oy); p = (num() + ox, num() + oy)
            cur.o[-1] = c1; cur.add(p, i=c2); pos = p; lastc = c2
        elif C == 'S':
            c1 = (2 * pos[0] - lastc[0], 2 * pos[1] - lastc[1]) if lastc else pos
            c2 = (num() + ox, num() + oy); p = (num() + ox, num() + oy)
            cur.o[-1] = c1; cur.add(p, i=c2); pos = p; lastc = c2
        elif C == 'Q':
            q = (num() + ox, num() + oy); p = (num() + ox, num() + oy)
            c1 = (pos[0] + 2 / 3 * (q[0] - pos[0]), pos[1] + 2 / 3 * (q[1] - pos[1]))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            cur.o[-1] = c1; cur.add(p, i=c2); pos = p; lastc = None
        elif C == 'A':
            rx, ry, ph, fa, fs = num(), num(), num(), num(), num()
            p = (num() + ox, num() + oy)
            for c1, c2, q in _arc_to_cubic(pos[0], pos[1], rx, ry, ph, int(fa), int(fs), p[0], p[1]):
                cur.o[-1] = c1; cur.add(q, i=c2)
            pos = p; lastc = None
        else:
            raise ValueError('unsupported path command ' + cmd)
    return subs


def ellipse(cx, cy, rx, ry, k=KAPPA):
    s = Sub(True)
    s.add((cx, cy - ry), (cx - k * rx, cy - ry), (cx + k * rx, cy - ry))
    s.add((cx + rx, cy), (cx + rx, cy - k * ry), (cx + rx, cy + k * ry))
    s.add((cx, cy + ry), (cx + k * rx, cy + ry), (cx - k * rx, cy + ry))
    s.add((cx - rx, cy), (cx - rx, cy + k * ry), (cx - rx, cy - k * ry))
    return [s]


def circle(cx, cy, r):
    return ellipse(cx, cy, r, r)


def smooth(points, closed=True, t=1 / 6):
    """Catmull-Rom spline through points -> bezier Sub."""
    s = Sub(closed)
    n = len(points)
    for k in range(n):
        p = points[k]
        if closed:
            a, b = points[(k - 1) % n], points[(k + 1) % n]
        else:
            a, b = points[max(k - 1, 0)], points[min(k + 1, n - 1)]
        tx, ty = (b[0] - a[0]) * t, (b[1] - a[1]) * t
        s.add(p, (p[0] - tx, p[1] - ty), (p[0] + tx, p[1] + ty))
    return [s]


def scallop(points, bump, closed=True):
    """Polyline whose every edge bulges outward (left-normal of travel) by `bump`."""
    s = Sub(closed)
    s.add(points[0])
    seq = points[1:] + ([points[0]] if closed else [])
    prev = points[0]
    for k, B in enumerate(seq):
        A = prev
        dx, dy = B[0] - A[0], B[1] - A[1]
        L = math.hypot(dx, dy) or 1
        b = bump(k) if callable(bump) else bump
        nx, ny = dy / L * b, -dx / L * b
        c1 = (A[0] + dx / 3 + nx, A[1] + dy / 3 + ny)
        c2 = (A[0] + 2 * dx / 3 + nx, A[1] + 2 * dy / 3 + ny)
        s.o[-1] = c1
        if closed and k == len(seq) - 1:
            s.i[0] = c2
        else:
            s.add(B, i=c2)
        prev = B
    return [s]


def svg_d(subs):
    out = []
    pt = lambda p: f"{fmt(p[0], 2)} {fmt(p[1], 2)}"
    for s in subs:
        out.append('M' + pt(s.v[0]))
        n = len(s.v)
        segs = [(k - 1, k) for k in range(1, n)] + ([(n - 1, 0)] if s.closed else [])
        for a, b in segs:
            if s.o[a] == s.v[a] and s.i[b] == s.v[b]:
                out.append('L' + pt(s.v[b]))
            else:
                out.append('C' + pt(s.o[a]) + ' ' + pt(s.i[b]) + ' ' + pt(s.v[b]))
        if s.closed:
            out.append('Z')
    return ''.join(out)


def lottie_sh(s, name):
    r = lambda x: round(x, 2)
    return {"ty": "sh", "nm": name, "ind": 0, "ks": {"a": 0, "k": {
        "i": [[r(i[0] - v[0]), r(i[1] - v[1])] for i, v in zip(s.i, s.v)],
        "o": [[r(o[0] - v[0]), r(o[1] - v[1])] for o, v in zip(s.o, s.v)],
        "v": [[r(v[0]), r(v[1])] for v in s.v],
        "c": s.closed}}}


# ------------------------------------------------------------------ scene graph
class Shape:
    def __init__(self, name, subs, fill=None, fo=1.0, stroke=None, sw=0.0, cid=None):
        self.name, self.subs = name, subs
        self.fill, self.fo, self.stroke, self.sw, self.cid = fill, fo, stroke, sw, cid


class Node:
    def __init__(self, name, children=None, a=(0, 0), p=None, r=0.0, s=(1, 1), o=1.0, alias=None):
        self.name = name
        self.children = list(children or [])
        self.a = tuple(a)
        self.p = tuple(p) if p is not None else tuple(a)
        self.r, self.s, self.o = r, tuple(s), o
        self.dp, self.dr, self.ds = (0, 0), 0.0, (1, 1)
        self.alias = alias

    @property
    def key(self):
        return self.alias or self.name

    def walk(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.walk()

    def find(self, name):
        for n in self.walk():
            if n.name == name:
                return n
        raise KeyError(name)

    def find_key(self, key):
        return [n for n in self.walk() if n.key == key]


# ------------------------------------------------------------------ clips / tracks
def hex_rgb(h):
    h = h.lstrip('#')
    return [int(h[k:k + 2], 16) / 255 for k in (0, 2, 4)]


def lerp(a, b, t):
    if isinstance(a, tuple):
        return tuple(x + (y - x) * t for x, y in zip(a, b))
    return a + (b - a) * t


def bez_xy(e, u):
    x1, y1, x2, y2 = e
    mu = 1 - u
    return (3 * mu * mu * u * x1 + 3 * mu * u * u * x2 + u ** 3,
            3 * mu * mu * u * y1 + 3 * mu * u * u * y2 + u ** 3)


def bez_solve(e, x):
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if bez_xy(e, mid)[0] < x:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def split_ease(e, tau):
    """Exactly split a timing bezier at time fraction tau -> (value fraction, left ease, right ease)."""
    u = bez_solve(e, tau)
    P0, P1, P2, P3 = (0, 0), (e[0], e[1]), (e[2], e[3]), (1, 1)
    L = lambda a, b: (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
    A, B, Cc = L(P0, P1), L(P1, P2), L(P2, P3)
    D, E = L(A, B), L(B, Cc)
    F = L(D, E)
    def norm(pt, o, w):
        return ((pt[0] - o[0]) / w[0] if w[0] else 0, (pt[1] - o[1]) / w[1] if w[1] else 0)
    wl = (F[0], F[1]) if F[1] else (F[0], 1)
    le = norm(A, (0, 0), wl) + norm(D, (0, 0), wl)
    wr = (1 - F[0], 1 - F[1]) if 1 - F[1] else (1 - F[0], 1)
    re_ = norm(E, F, wr) + norm(Cc, F, wr)
    clamp = lambda t4: tuple(min(1, max(0, v)) for v in t4)
    return F[1], clamp(le), clamp(re_)


class Clip:
    def __init__(self, name, category, frames, loop, rig, base_pose='sit', start_pose=None, end_pose=None, desc=''):
        self.name, self.category, self.frames, self.loop = name, category, frames, loop
        self.rig = rig
        self.base_pose = base_pose
        self.start_pose = start_pose or base_pose
        self.end_pose = end_pose or (self.start_pose if loop else base_pose)
        self.desc = desc
        self.tracks = {}   # (key, prop) -> {'hold': bool, 'keys': {t: (v, ease)}}

    def k(self, key, prop, kv, hold=False, ease=EIO):
        tr = self.tracks.setdefault((key, prop), {'hold': hold, 'keys': {}})
        if tr['hold'] != hold:
            raise ValueError(f'{self.name}: track {key}.{prop} mixes hold/eased keys')
        for item in kv:
            t, v = item[0], item[1]
            e = item[2] if len(item) > 2 else ease
            if isinstance(v, list):
                v = tuple(v)
            tr['keys'][round(t, 4)] = (v, e)
        return self

    def value_at(self, key, prop, t, static):
        tr = self.tracks.get((key, prop))
        if not tr:
            return static
        ks = sorted(tr['keys'].items())
        if t <= ks[0][0]:
            return ks[0][1][0]
        for (t0, (v0, e0)), (t1, (v1, _)) in zip(ks, ks[1:]):
            if t0 <= t < t1:
                if tr['hold']:
                    return v0
                if isinstance(v0, str):
                    return v0
                y = bez_xy(e0, bez_solve(e0, (t - t0) / (t1 - t0)))[1]
                return lerp(v0, v1, y)
        return ks[-1][1][0]

    def final(self, key, prop):
        tr = self.tracks[(key, prop)]
        ks = sorted(tr['keys'].items())
        N = self.frames
        out = [(t, v, e) for t, (v, e) in ks if 0 <= t <= N]
        if not out:
            raise ValueError(f'{self.name}: empty track {key}.{prop}')
        if out[0][0] > 0:
            out.insert(0, (0, out[0][1], EIO))
        if out[-1][0] < N:
            out.append((N, out[-1][1], EIO))
        return out, tr['hold']

    def check(self, rig):
        """Loops must start and end on the same values (seamless)."""
        probs = []
        if self.loop:
            for (key, prop) in self.tracks:
                if prop != 'o' and (key, 'o') in self.tracks:
                    oks, _ = self.final(key, 'o')
                    if oks[0][1] == 0 and oks[-1][1] == 0:
                        continue   # invisible at the seam: jump is not visible
                ks, _ = self.final(key, prop)
                a, b = ks[0][1], ks[-1][1]
                same = a == b if isinstance(a, str) else (
                    all(abs(x - y) < 1e-6 for x, y in zip(a, b)) if isinstance(a, tuple) else abs(a - b) < 1e-6)
                if not same:
                    # allowed when invisible (opacity 0 effects / rotations by full turns)
                    if prop == 'r' or prop == 'dr':
                        if abs(((a - b) % 360)) < 1e-6:
                            continue
                    probs.append(f'{key}.{prop}: {a} -> {b}')
        return probs

    # --- wrap-around effect lifetimes (loops) -----------------------------------
    def life(self, key, start, rel, hold_props=()):
        """rel: {prop: [(trel, v), ...]} relative to start. Wraps around the loop boundary."""
        N = self.frames
        for prop, kv in rel.items():
            keys = [(start + t, v, EIO) for t, v in kv]
            if keys[-1][0] > N and self.loop:
                # split segment crossing N
                pre, post = [], []
                for idx, (t, v, e) in enumerate(keys):
                    if t < N:
                        pre.append((t, v, e))
                    elif t == N:
                        pre.append((t, v, e)); post.append((0, v, e))
                    else:
                        post.append((t - N, v, e))
                if pre and post and pre[-1][0] < N and post[0][0] > 0:
                    t0, v0, e0 = pre[-1]
                    t1, v1 = post[0][0] + N, post[0][1]
                    tau = (N - t0) / (t1 - t0)
                    if prop in hold_props:
                        vb = v0
                        pre.append((N, vb, e0)); post.insert(0, (0, vb, e0))
                    else:
                        yf, le, re_ = split_ease(e0, tau)
                        vb = lerp(v0, v1, yf)
                        pre[-1] = (t0, v0, le)
                        pre.append((N, vb, re_))
                        post.insert(0, (0, vb, re_))
                keys = post + pre
                # remove duplicate time 0 / N collisions handled by dict
            self.k(key, prop, keys, hold=prop in hold_props)


# ------------------------------------------------------------------ exporters
IDENT = {'p': (0, 0), 'r': 0, 's': (1, 1), 'dp': (0, 0), 'dr': 0, 'ds': (1, 1)}


def _static(node, prop):
    return getattr(node, prop)


def _is_ident(prop, v):
    ref = IDENT[prop]
    if isinstance(ref, tuple):
        return all(abs(a - b) < 1e-9 for a, b in zip(v, ref))
    return abs(v - ref) < 1e-9


def _get(clip, node, prop):
    if (node.key, prop) in clip.tracks:
        ks, hold = clip.final(node.key, prop)
        return ('a', ks, hold)
    return ('s', _static(node, prop))


class SVGOut:
    def __init__(self, clip):
        self.clip = clip
        N = clip.frames
        self.timing = f'begin="0s" dur="{fmt(N / FPS, 4)}s" ' + ('repeatCount="indefinite"' if clip.loop else 'fill="freeze"')
        self.lines = []

    def anim(self, tag, attrs, ks, hold, conv):
        N = self.clip.frames
        vals = ';'.join(conv(v) for _, v, _ in ks)
        if hold:   # switch a hair early so integer-frame sampling never lands on the wrong side of rounding
            kt = ';'.join(fmt(max(0.0, t - 0.02) / N, 7) for t, _, _ in ks)
        else:
            kt = ';'.join(fmt(t / N, 7) for t, _, _ in ks)
        if hold:
            mode = 'calcMode="discrete"'
        else:
            spl = ';'.join(' '.join(fmt(x, 4) for x in e) for _, _, e in ks[:-1])
            mode = f'calcMode="spline" keySplines="{spl}"'
        return f'<{tag} {attrs} values="{vals}" keyTimes="{kt}" {mode} {self.timing}/>'


def _tconv(typ):
    if typ == 'translate':
        return lambda v: f'{fmt(v[0])} {fmt(v[1])}'
    if typ == 'rotate':
        return lambda v: fmt(v)
    return lambda v: f'{fmt(v[0], 4)} {fmt(v[1], 4)}'


def _tstr(typ, v):
    if typ == 'translate':
        return f'translate({fmt(v[0])} {fmt(v[1])})'
    if typ == 'rotate':
        return f'rotate({fmt(v)})'
    return f'scale({fmt(v[0], 4)} {fmt(v[1], 4)})'


def svg_node(out, node, ind=''):
    clip = out.clip
    comps = [('translate', 'p'), ('rotate', 'r'), ('scale', 's'), ('translate', 'dp'), ('rotate', 'dr'), ('scale', 'ds')]
    items = [(typ, prop, _get(clip, node, prop)) for typ, prop in comps]
    items.append(('translate', 'p', ('s', (-node.a[0], -node.a[1]))))
    anim_idx = [k for k, it in enumerate(items) if it[2][0] == 'a']
    lead, mid, trail = items, [], []
    if anim_idx:
        f, l = anim_idx[0], anim_idx[-1]
        lead, mid, trail = items[:f], items[f:l + 1], items[l + 1:]
    tf = ' '.join(_tstr(t, st[1]) for t, pr, st in lead if not _is_ident(pr, st[1]))
    o = _get(clip, node, 'o')
    attrs = f'id="{node.name}"'
    if tf:
        attrs += f' transform="{tf}"'
    if o[0] == 's' and o[1] != 1:
        attrs += f' opacity="{fmt(o[1], 4)}"'
    out.lines.append(f'{ind}<g {attrs}>')
    for typ, pr, st in mid:
        if st[0] == 'a':
            out.lines.append(ind + ' ' + out.anim('animateTransform', f'attributeName="transform" type="{typ}" additive="sum"', st[1], st[2], _tconv(typ)))
        elif not _is_ident(pr, st[1]):
            ks = [(0, st[1], EIO), (clip.frames, st[1], EIO)]
            out.lines.append(ind + ' ' + out.anim('animateTransform', f'attributeName="transform" type="{typ}" additive="sum"', ks, False, _tconv(typ)))
    if o[0] == 'a':
        out.lines.append(ind + ' ' + out.anim('animate', 'attributeName="opacity"', o[1], o[2], lambda v: fmt(v, 4)))
    tt = ' '.join(_tstr(t, st[1]) for t, pr, st in trail if not _is_ident(pr, st[1]))
    inner = ind + ' '
    if tt:
        out.lines.append(f'{ind} <g transform="{tt}">')
        inner = ind + '  '
    for c in node.children:
        if isinstance(c, Node):
            svg_node(out, c, inner)
        else:
            svg_shape(out, c, inner)
    if tt:
        out.lines.append(f'{ind} </g>')
    out.lines.append(f'{ind}</g>')


def svg_shape(out, sh, ind):
    clip = out.clip
    a = f'd="{svg_d(sh.subs)}"'
    fill_anim = None
    if sh.fill:
        a += f' fill="{sh.fill}"'
        if sh.fo != 1:
            a += f' fill-opacity="{fmt(sh.fo, 4)}"'
        if sh.cid and (sh.cid, 'fill') in clip.tracks:
            ks, hold = clip.final(sh.cid, 'fill')
            fill_anim = out.anim('animate', 'attributeName="fill"', ks, hold, lambda v: v)
    else:
        a += ' fill="none"'
    if sh.stroke:
        a += f' stroke="{sh.stroke}" stroke-width="{fmt(sh.sw)}" stroke-linecap="round" stroke-linejoin="round"'
    if fill_anim:
        out.lines.append(f'{ind}<path {a}>{fill_anim}</path>')
    else:
        out.lines.append(f'{ind}<path {a}/>')


def export_svg(clip):
    out = SVGOut(clip)
    out.lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" data-clip="{clip.name}" data-frames="{clip.frames}" data-fps="{FPS}" data-loop="{str(clip.loop).lower()}">')
    out.lines.append(f'<title>{clip.name}</title>')
    for c in clip.rig.children:
        svg_node(out, c, '')
    out.lines.append('</svg>')
    return '\n'.join(out.lines) + '\n'


# ---- Lottie
def _lconv(prop):
    if prop in ('p', 'dp', 'a'):
        return lambda v: [round(v[0], 3), round(v[1], 3)]
    if prop in ('s', 'ds'):
        return lambda v: [round(v[0] * 100, 3), round(v[1] * 100, 3)]
    if prop in ('r', 'dr'):
        return lambda v: round(v, 3)
    if prop == 'o':
        return lambda v: round(v * 100, 3)
    if prop == 'fill':
        return lambda v: [round(x, 4) for x in hex_rgb(v)] + [1]
    raise KeyError(prop)


def _lprop(clip, key, prop, static, conv=None):
    conv = conv or _lconv(prop)
    if (key, prop) in clip.tracks:
        ks, hold = clip.final(key, prop)
        frames = []
        for idx, (t, v, e) in enumerate(ks):
            val = conv(v)
            val = val if isinstance(val, list) else [val]
            kf = {"t": t, "s": val}
            if idx < len(ks) - 1:
                if hold:
                    kf["h"] = 1
                else:
                    d = len(val)
                    kf["o"] = {"x": [e[0]] * d, "y": [e[1]] * d}
                    kf["i"] = {"x": [e[2]] * d, "y": [e[3]] * d}
            frames.append(kf)
        return {"a": 1, "k": frames}
    return {"a": 0, "k": conv(static)}


def _ltr(a, p, s, r, o):
    return {"ty": "tr", "nm": "Transform", "a": a, "p": p, "s": s, "r": r, "o": o,
            "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0}}


def _lgr(name, items, tr):
    return {"ty": "gr", "nm": name, "np": len(items) + 1, "cix": 2, "bm": 0, "ix": 1, "hd": False,
            "it": items + [tr]}


def lot_node(clip, node):
    items = []
    for c in reversed(node.children):
        items.append(lot_node(clip, c) if isinstance(c, Node) else lot_shape(clip, c))
    key = node.key
    anim_slot = any((key, pr) in clip.tracks or not _is_ident(pr, getattr(node, pr)) for pr in ('dp', 'dr', 'ds'))
    S = lambda pr: _lprop(clip, key, pr, getattr(node, pr))
    A = {"a": 0, "k": [node.a[0], node.a[1]]}
    if anim_slot:
        inner = _lgr(node.name + '.anim', items, _ltr(A, S('dp'), S('ds'), S('dr'), {"a": 0, "k": 100}))
        return _lgr(node.name, [inner], _ltr({"a": 0, "k": [0, 0]}, S('p'), S('s'), S('r'), S('o')))
    return _lgr(node.name, items, _ltr(A, S('p'), S('s'), S('r'), S('o')))


def lot_shape(clip, sh):
    items = [lottie_sh(s, f'{sh.name}.{k}') for k, s in enumerate(sh.subs)]
    if sh.stroke:
        items.append({"ty": "st", "nm": "Stroke", "c": {"a": 0, "k": hex_rgb(sh.stroke) + [1]}, "o": {"a": 0, "k": 100},
                      "w": {"a": 0, "k": sh.sw}, "lc": 2, "lj": 2, "ml": 4, "bm": 0})
    if sh.fill:
        if sh.cid and (sh.cid, 'fill') in clip.tracks:
            c = _lprop(clip, sh.cid, 'fill', sh.fill)
        else:
            c = {"a": 0, "k": hex_rgb(sh.fill) + [1]}
        items.append({"ty": "fl", "nm": "Fill", "c": c, "o": {"a": 0, "k": round(sh.fo * 100, 3)}, "r": 1, "bm": 0})
    ident = _ltr({"a": 0, "k": [0, 0]}, {"a": 0, "k": [0, 0]}, {"a": 0, "k": [100, 100]}, {"a": 0, "k": 0}, {"a": 0, "k": 100})
    return _lgr(sh.name, items, ident)


def export_lottie(clip):
    N = clip.frames
    root_items = [lot_node(clip, c) for c in reversed(clip.rig.children)]
    layer = {"ddd": 0, "ind": 1, "ty": 4, "nm": "axolotl", "sr": 1,
             "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0}, "p": {"a": 0, "k": [0, 0, 0]},
                    "a": {"a": 0, "k": [0, 0, 0]}, "s": {"a": 0, "k": [100, 100, 100]}},
             "ao": 0, "shapes": root_items, "ip": 0, "op": N, "st": 0, "bm": 0}
    return {"v": "5.7.4", "fr": FPS, "ip": 0, "op": N, "w": 512, "h": 512, "nm": clip.name, "ddd": 0,
            "assets": [], "layers": [layer], "markers": [],
            "meta": {"g": "axolotl-pet generator", "loop": clip.loop}}
