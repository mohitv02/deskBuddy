"""Shared scene-graph + keyframe model with two exporters (Lottie 5.7 JSON, SMIL SVG).
Everything is flat fills / strokes on cubic-bezier paths; motion is per-group
translate/rotate/scale + on/off opacity, so both formats are driven by the exact same data."""
import math, json
FPS = 30
K = 0.5522847498

# ---------------------------------------------------------------- geometry
class Path:
    def __init__(s, v, i=None, o=None, closed=True):
        s.v = [tuple(map(float, p)) for p in v]
        n = len(s.v)
        s.i = [tuple(map(float, p)) for p in (i or [(0, 0)] * n)]
        s.o = [tuple(map(float, p)) for p in (o or [(0, 0)] * n)]
        s.c = closed
    def d(s):
        r = lambda x: f"{x:.2f}".rstrip('0').rstrip('.')
        v, i, o = s.v, s.i, s.o
        out = [f"M{r(v[0][0])} {r(v[0][1])}"]
        n = len(v)
        segs = range(n if s.c else n - 1)
        for k in segs:
            a, b = k, (k + 1) % n
            c1 = (v[a][0] + o[a][0], v[a][1] + o[a][1]); c2 = (v[b][0] + i[b][0], v[b][1] + i[b][1])
            out.append(f"C{r(c1[0])} {r(c1[1])} {r(c2[0])} {r(c2[1])} {r(v[b][0])} {r(v[b][1])}")
        if s.c: out.append("Z")
        return "".join(out)
    def lottie(s):
        rd = lambda p: [round(p[0], 2), round(p[1], 2)]
        return {"i": [rd(p) for p in s.i], "o": [rd(p) for p in s.o], "v": [rd(p) for p in s.v], "c": s.c}

def ellipse(cx, cy, rx, ry):
    v = [(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)]
    i = [(-rx * K, 0), (0, -ry * K), (rx * K, 0), (0, ry * K)]
    o = [(rx * K, 0), (0, ry * K), (-rx * K, 0), (0, -ry * K)]
    return Path(v, i, o)
def circle(cx, cy, r): return ellipse(cx, cy, r, r)
def rrect(x, y, w, h, r):
    r = min(r, w / 2, h / 2); k = r * K
    v = [(x + r, y), (x + w - r, y), (x + w, y + r), (x + w, y + h - r), (x + w - r, y + h), (x + r, y + h), (x, y + h - r), (x, y + r)]
    i = [(-k, 0), (0, 0), (0, -k), (0, 0), (k, 0), (0, 0), (0, k), (0, 0)]
    o = [(0, 0), (k, 0), (0, 0), (0, k), (0, 0), (-k, 0), (0, 0), (0, -k)]
    return Path(v, i, o)
def poly(pts, closed=True): return Path(pts, closed=closed)
def line(*pts): return Path(pts, closed=False)
def quad(p0, c, p1):
    return Path([p0, p1], [(0, 0), ((c[0] - p1[0]) * 2 / 3, (c[1] - p1[1]) * 2 / 3)],
                [((c[0] - p0[0]) * 2 / 3, (c[1] - p0[1]) * 2 / 3), (0, 0)], closed=False)
def smooth(pts, closed=True, corners=(), t=1 / 6):
    n = len(pts); I = []; O = []
    for k in range(n):
        if k in corners or (not closed and k in (0, n - 1)):
            I.append((0, 0)); O.append((0, 0)); continue
        a = pts[(k - 1) % n]; b = pts[(k + 1) % n]
        tx, ty = (b[0] - a[0]) * t, (b[1] - a[1]) * t
        I.append((-tx, -ty)); O.append((tx, ty))
    return Path(pts, I, O, closed)
def ribbon(p0, p1, w0, w1, n=6):
    """tapered rounded segment from p0 to p1"""
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0]); pts = []
    for k in range(n + 1):
        a = ang + math.pi / 2 + math.pi * k / n
        pts.append((p1[0] + w1 / 2 * math.cos(a - math.pi), p1[1] + w1 / 2 * math.sin(a - math.pi)))
    for k in range(n + 1):
        a = ang + math.pi / 2 + math.pi * k / n
        pts.append((p0[0] + w0 / 2 * math.cos(a), p0[1] + w0 / 2 * math.sin(a)))
    return smooth(pts, True, t=1 / 7)
def star4(cx, cy, R, r, rot=0):
    pts = []
    for k in range(8):
        a = math.radians(rot + k * 45 - 90); rr = R if k % 2 == 0 else r
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return poly(pts)
def heart(cx, cy, s):
    p = [(0, -0.42), (0.38, -0.92), (0.98, -0.62), (0.86, 0.06), (0, 0.86), (-0.86, 0.06), (-0.98, -0.62), (-0.38, -0.92)]
    return smooth([(cx + x * s, cy + y * s) for x, y in p], True, corners={0, 4})
def drop(cx, cy, s):
    p = [(0, -1.25), (0.55, -0.25), (0.72, 0.35), (0.4, 0.82), (0, 0.95), (-0.4, 0.82), (-0.72, 0.35), (-0.55, -0.25)]
    return smooth([(cx + x * s, cy + y * s) for x, y in p], True, corners={0})

# ---------------------------------------------------------------- scene
def hexc(h):
    h = h.lstrip('#'); return tuple(int(h[k:k + 2], 16) / 255 for k in (0, 2, 4))
class Prim:
    def __init__(s, path, fill=None, stroke=None, w=0, fop=100):
        s.path, s.fill, s.stroke, s.w, s.fop = path, fill, stroke, w, fop
class Node:
    def __init__(s, name, anchor=(0, 0), prims=(), children=(), rot=0, pos=None, scale=(100, 100), op=100, cfirst=False):
        s.name = name; s.a = tuple(anchor); s.prims = list(prims); s.children = list(children)
        s.r0 = rot; s.p0 = tuple(pos) if pos is not None else tuple(anchor); s.s0 = tuple(scale); s.o0 = op
        s.cfirst = cfirst
    def add(s, *ch): s.children.extend(ch); return s
    def walk(s):
        yield s
        for c in s.children: yield from c.walk()
def outlined(path, fill, out, w):
    return [Prim(path, fill=fill, stroke=out, w=w)]
def capsule(p0, p1, width, fill, out, ow):
    pth = line(p0, p1)
    return [Prim(pth, stroke=out, w=width + 2 * ow), Prim(pth, stroke=fill, w=width)]

# ---------------------------------------------------------------- easing
EASE = {
    'io': (0.42, 0, 0.58, 1), 'sine': (0.37, 0, 0.63, 1), 'in': (0.42, 0, 1, 1), 'out': (0, 0, 0.58, 1),
    'snap': (0.12, 0.85, 0.25, 1), 'lin': (0, 0, 1, 1), 'soft': (0.33, 0, 0.2, 1), 'hold': None,
}
def _bez(p1, p2, s):
    return 3 * (1 - s) ** 2 * s * p1 + 3 * (1 - s) * s * s * p2 + s ** 3
def _solve(e, x):
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        if _bez(e[0], e[2], m) < x: lo = m
        else: hi = m
    return (lo + hi) / 2
def split_ease(e, x):
    """split normalized easing curve at time-fraction x -> (y_at_x, left_ease, right_ease)"""
    if e is None: return 0.0, None, None
    s = _solve(e, x)
    P = [(0, 0), (e[0], e[1]), (e[2], e[3]), (1, 1)]
    lerp = lambda a, b, t: (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    a1 = lerp(P[0], P[1], s); a2 = lerp(P[1], P[2], s); a3 = lerp(P[2], P[3], s)
    b1 = lerp(a1, a2, s); b2 = lerp(a2, a3, s); m = lerp(b1, b2, s)
    def norm(pts):
        (x0, y0), (x3, y3) = pts[0], pts[3]
        dx = x3 - x0 or 1e-9; dy = y3 - y0
        q = []
        for (px, py) in (pts[1], pts[2]):
            nx = (px - x0) / dx; ny = (py - y0) / dy if abs(dy) > 1e-9 else nx
            q += [min(1, max(0, nx)), min(1, max(0, ny))]
        return tuple(q)
    return m[1], norm([P[0], a1, b1, m]), norm([m, b2, a3, P[3]])

def _lerp(a, b, y):
    if isinstance(a, tuple): return tuple(x + (z - x) * y for x, z in zip(a, b))
    return a + (b - a) * y

def value_at(keys, t):
    if t <= keys[0][0]: return keys[0][1]
    for k in range(len(keys) - 1):
        t0, v0, e = keys[k]; t1, v1, _ = keys[k + 1]
        if t0 <= t <= t1:
            if t1 == t0: return v1
            x = (t - t0) / (t1 - t0)
            if EASE[e] is None: return v0 if t < t1 else v1
            return _lerp(v0, v1, split_ease(EASE[e], x)[0])
    return keys[-1][1]

def crop(keys, N):
    """keys: sorted list (t, v, ease). Return keys exactly covering [0, N]."""
    keys = sorted(keys, key=lambda k: k[0])
    # dedupe same time: last wins
    dd = []
    for k in keys:
        if dd and abs(dd[-1][0] - k[0]) < 1e-6: dd[-1] = k
        else: dd.append(k)
    keys = dd
    out = []
    def cut(kl, T, keep_left):
        res = []
        for k in range(len(kl)):
            t0, v0, e = kl[k]
            if k + 1 < len(kl):
                t1, v1, e1 = kl[k + 1]
                if t0 < T < t1:
                    x = (T - t0) / (t1 - t0); E = EASE[e]
                    if E is None:
                        y, L, R = (0.0, None, None)
                        vm = v0
                    else:
                        y, L, R = split_ease(E, x); vm = _lerp(v0, v1, y)
                    if keep_left:
                        res.append((t0, v0, ('c', L) if L else e)); res.append((T, vm, 'lin'))
                        return res
                    else:
                        res.append((T, vm, ('c', R) if R else e)); res += [(a, b, c) for a, b, c in kl[k + 1:]]
                        return res
            if keep_left and t0 <= T: res.append(kl[k])
            if not keep_left and t0 >= T:
                return res + kl[k:]
        return res
    if keys[0][0] < 0: keys = cut(keys, 0, False)
    if keys[-1][0] > N: keys = cut(keys, N, True)
    if keys[0][0] > 0: keys.insert(0, (0, keys[0][1], 'hold'))
    if keys[-1][0] < N: keys.append((N, keys[-1][1], 'lin'))
    return keys

def ease_tuple(e):
    if isinstance(e, tuple) and e and e[0] == 'c': return e[1]
    return EASE[e]

# ---------------------------------------------------------------- clip
PROPS = ('p', 'r', 's', 'o', 'p2', 'r2', 's2')
class Clip:
    def __init__(s, name, cat, N, loop, desc=''):
        s.name, s.cat, s.N, s.loop, s.desc = name, cat, N, loop, desc
        s.keys = {}   # (node, prop) -> list of (t, v, ease)
    def k(s, node, prop, keys):
        L = s.keys.setdefault((node, prop), [])
        for kk in keys:
            if len(kk) == 2: kk = (kk[0], kk[1], 'io')
            t, v, e = kk
            if prop in ('p', 'p2', 's', 's2') and not isinstance(v, tuple): v = tuple(v)
            L.append((t, v, e))
        return s

# ---------------------------------------------------------------- export helpers
def _final_keys(clip, node, prop):
    kl = clip.keys.get((node.name, prop))
    if not kl: return None
    kl = crop(kl, clip.N)
    if len(kl) == 2 and kl[0][1] == kl[1][1] and len({str(k[1]) for k in kl}) == 1:
        return ('static', kl[0][1])
    vals = {str(k[1]) for k in kl}
    if len(vals) == 1: return ('static', kl[0][1])
    return ('anim', kl)
def base_val(node, prop):
    return {'p': (0.0, 0.0), 'r': 0.0, 's': (100.0, 100.0), 'o': 100.0, 'p2': (0.0, 0.0), 'r2': 0.0, 's2': (100.0, 100.0)}[prop]
def resolve(clip, node, prop):
    """returns ('static', value) or ('anim', keys) in absolute terms"""
    fk = _final_keys(clip, node, prop)
    def absval(v):
        if prop == 'p': return (node.p0[0] + v[0], node.p0[1] + v[1])
        if prop == 'r': return node.r0 + v
        return v
    if fk is None:
        dv = {'p': node.p0, 'r': node.r0, 's': node.s0, 'o': node.o0}.get(prop, base_val(node, prop))
        return ('static', dv)
    if fk[0] == 'static': return ('static', absval(fk[1]))
    return ('anim', [(t, absval(v), e) for t, v, e in fk[1]])

def visible_somewhere(clip, node):
    o = resolve(clip, node, 'o')
    if o[0] == 'static': return o[1] > 0
    return any(v > 0 for _, v, _ in o[1])

# ---------------------------------------------------------------- Lottie
def _lv(v, prop):
    if prop in ('s', 's2'): return [round(v[0], 3), round(v[1], 3), 100]
    if isinstance(v, tuple): return [round(x, 3) for x in v]
    return [round(v, 3)]
def _lprop(res, prop, dims):
    if res[0] == 'static':
        v = res[1]
        if prop in ('s', 's2'): return {"a": 0, "k": [v[0], v[1], 100]}
        if isinstance(v, tuple): return {"a": 0, "k": list(v)}
        return {"a": 0, "k": v}
    kl = res[1]; out = []
    spatial = prop in ('p', 'p2')
    for idx, (t, v, e) in enumerate(kl):
        kf = {"t": round(t, 3), "s": _lv(v, prop)}
        if idx < len(kl) - 1:
            E = ease_tuple(e)
            if E is None: kf["h"] = 1
            else:
                if spatial:
                    kf["o"] = {"x": E[0], "y": E[1]}; kf["i"] = {"x": E[2], "y": E[3]}
                    kf["to"] = [0, 0]; kf["ti"] = [0, 0]
                else:
                    d = 3 if prop in ('s', 's2') else 1
                    kf["o"] = {"x": [E[0]] * d, "y": [E[1]] * d}; kf["i"] = {"x": [E[2]] * d, "y": [E[3]] * d}
        out.append(kf)
    return {"a": 1, "k": out}
def _tr(a=(0, 0), p=None, s=None, r=None, o=None):
    return {"ty": "tr", "a": {"a": 0, "k": list(a)}, "p": p or {"a": 0, "k": [0, 0]}, "s": s or {"a": 0, "k": [100, 100]},
            "r": r or {"a": 0, "k": 0}, "o": o or {"a": 0, "k": 100}, "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0}, "nm": "T"}
def _lprim(pr):
    it = [{"ty": "sh", "ks": {"a": 0, "k": pr.path.lottie()}, "nm": "p"}]
    if pr.stroke: it.append({"ty": "st", "c": {"a": 0, "k": list(pr.stroke) + [1]}, "o": {"a": 0, "k": 100}, "w": {"a": 0, "k": pr.w}, "lc": 2, "lj": 2, "ml": 4, "nm": "s"})
    if pr.fill: it.append({"ty": "fl", "c": {"a": 0, "k": list(pr.fill) + [1]}, "o": {"a": 0, "k": pr.fop}, "r": 1, "nm": "f"})
    it.append(_tr())
    return {"ty": "gr", "it": it, "nm": "g"}
def _lnode(clip, node):
    if not visible_somewhere(clip, node): return None
    R = {p: resolve(clip, node, p) for p in PROPS}
    content = []
    items = [('prim', p) for p in node.prims]
    chs = [('node', c) for c in node.children]
    order = (chs + items) if node.cfirst else (items + chs)
    for kind, x in order:
        g = _lprim(x) if kind == 'prim' else _lnode(clip, x)
        if g: content.append(g)
    content = content[::-1]  # lottie: first item on top
    sec = any(not (R[p][0] == 'static' and R[p][1] == base_val(node, p)) for p in ('p2', 'r2', 's2'))
    if not sec:
        tr = _tr(node.a, _lprop(R['p'], 'p', 2), _lprop(R['s'], 's', 3), _lprop(R['r'], 'r', 1), _lprop(R['o'], 'o', 1))
        return {"ty": "gr", "it": content + [tr], "nm": node.name}
    inner = {"ty": "gr", "it": content + [_tr(node.a)], "nm": node.name + "_a"}
    mid = {"ty": "gr", "it": [inner, _tr((0, 0), _lprop(R['p2'], 'p2', 2), _lprop(R['s2'], 's2', 3), _lprop(R['r2'], 'r2', 1))], "nm": node.name + "_2"}
    tr = _tr((0, 0), _lprop(R['p'], 'p', 2), _lprop(R['s'], 's', 3), _lprop(R['r'], 'r', 1), _lprop(R['o'], 'o', 1))
    return {"ty": "gr", "it": [mid, tr], "nm": node.name}
def to_lottie(clip, root):
    g = _lnode(clip, root)
    layer = {"ddd": 0, "ind": 1, "ty": 4, "nm": "ninja", "sr": 1,
             "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0}, "p": {"a": 0, "k": [0, 0, 0]}, "a": {"a": 0, "k": [0, 0, 0]}, "s": {"a": 0, "k": [100, 100, 100]}},
             "ao": 0, "shapes": [g] if g else [], "ip": 0, "op": clip.N, "st": 0, "bm": 0}
    return {"v": "5.7.0", "fr": FPS, "ip": 0, "op": clip.N, "w": 512, "h": 512, "nm": clip.name, "ddd": 0, "assets": [], "layers": [layer], "markers": []}

# ---------------------------------------------------------------- SVG / SMIL
def _f(x): return f"{x:.3f}".rstrip('0').rstrip('.') if isinstance(x, float) else str(x)
def _col(c): return '#%02x%02x%02x' % tuple(round(x * 255) for x in c)
def _svals(kl, conv):
    """expand hold segments for SMIL; returns values, keyTimes, keySplines"""
    pts = []; spl = []
    for k in range(len(kl)):
        t, v, e = kl[k]
        pts.append((t, v))
        if k == len(kl) - 1: break
        t1 = kl[k + 1][0]; E = ease_tuple(e)
        if E is None:
            eps = min(0.03, (t1 - t) / 2)
            spl.append((0, 0, 1, 1)); pts.append((t1 - eps, v)); spl.append((0, 0, 0, 0)); pts.append((t1 - eps / 3, kl[k + 1][1])); spl.append((0, 0, 1, 1))
        else: spl.append(E)
    return pts, spl
def _anim(tag_type, kl, conv, N, loop, attr='transform'):
    pts, spl = _svals(kl, conv)
    dur = N / FPS
    vals = ";".join(conv(v) for _, v in pts)
    kt = ";".join(("%.6f" % (t / N)).rstrip("0").rstrip(".") if t > 0 else "0" for t, _ in pts)
    ks = ";".join(" ".join(_f(float(x)) for x in e) for e in spl)
    rep = 'repeatCount="indefinite"' if loop else 'fill="freeze"'
    if attr == 'transform':
        return f'<animateTransform attributeName="transform" type="{tag_type}" dur="{_f(round(dur, 4))}s" {rep} calcMode="spline" values="{vals}" keyTimes="{kt}" keySplines="{ks}"/>'
    return f'<animate attributeName="{attr}" dur="{_f(round(dur, 4))}s" {rep} calcMode="spline" values="{vals}" keyTimes="{kt}" keySplines="{ks}"/>'
def _sprim(pr):
    a = [f'd="{pr.path.d()}"']
    a.append(f'fill="{_col(pr.fill)}"' if pr.fill else 'fill="none"')
    if pr.fill and pr.fop < 100: a.append(f'fill-opacity="{pr.fop / 100}"')
    if pr.stroke: a.append(f'stroke="{_col(pr.stroke)}" stroke-width="{_f(float(pr.w))}"')
    return f'<path {" ".join(a)}/>'
def _snode(clip, node):
    if not visible_somewhere(clip, node): return ''
    R = {p: resolve(clip, node, p) for p in PROPS}
    N, loop = clip.N, clip.loop
    items = [('prim', p) for p in node.prims]; chs = [('node', c) for c in node.children]
    order = (chs + items) if node.cfirst else (items + chs)
    inner = "".join(_sprim(x) if k == 'prim' else _snode(clip, x) for k, x in order)
    ops = []  # outermost first
    tconv = lambda v: f"{_f(round(v[0], 3))} {_f(round(v[1], 3))}"
    sconv = lambda v: f"{_f(round(v[0] / 100, 5))} {_f(round(v[1] / 100, 5))}"
    rconv = lambda v: _f(round(v, 3))
    def add(prop, typ, conv, skip):
        r = R[prop]
        if r[0] == 'static':
            if r[1] == skip: return
            ops.append(('s', f"{typ}({conv(r[1])})"))
        else:
            ops.append(('a', f'{typ}({conv(r[1][0][1])})', _anim(typ, r[1], conv, N, loop)))
    add('p', 'translate', tconv, None)
    add('r', 'rotate', rconv, 0.0)
    add('s', 'scale', sconv, (100.0, 100.0))
    add('p2', 'translate', tconv, (0.0, 0.0))
    add('r2', 'rotate', rconv, 0.0)
    add('s2', 'scale', sconv, (100.0, 100.0))
    if node.a != (0, 0): ops.append(('s', f"translate({_f(-node.a[0])} {_f(-node.a[1])})"))
    # build nested groups, merging consecutive statics
    groups = []
    for op in ops:
        if op[0] == 's' and groups and groups[-1][0] == 's': groups[-1] = ('s', groups[-1][1] + ' ' + op[1])
        else: groups.append(op)
    s = inner
    for g in reversed(groups):
        if g[0] == 's': s = f'<g transform="{g[1]}">{s}</g>'
        else: s = f'<g transform="{g[1]}">{g[2]}{s}</g>'
    o = R['o']
    if o[0] == 'anim':
        s = f'<g opacity="{_f(o[1][0][1] / 100)}">{_anim(None, o[1], lambda v: _f(round(v / 100, 4)), N, loop, "opacity")}{s}</g>'
    elif o[1] < 100:
        s = f'<g opacity="{_f(o[1] / 100)}">{s}</g>'
    return s
def to_svg(clip, root):
    body = _snode(clip, root)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" '
            f'stroke-linecap="round" stroke-linejoin="round"><title>{clip.name}</title>{body}</svg>')
