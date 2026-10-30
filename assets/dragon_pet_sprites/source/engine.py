"""One keyframe model -> Lottie (bodymovin 5.7) JSON and self-contained SMIL SVG with identical motion."""
import json, math, re, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rig

FPS = 30
CANVAS = 512
EIO = (0.42, 0.0, 0.58, 1.0)     # ease-in-out (CSS)
LIN = (0.0, 0.0, 1.0, 1.0)
DEFAULTS = {'p': (0.0, 0.0), 'r': 0.0, 's': (1.0, 1.0)}

# ------------------------------------------------------------------ clip model
class Clip:
    def __init__(self, name, cat, frames, loop, neutral_start=True, neutral_end=True, note=''):
        self.name, self.cat, self.N, self.loop = name, cat, frames, loop
        self.neutral_start, self.neutral_end = neutral_start, neutral_end
        self.tracks = {}        # (target, prop) -> {frame: (value, ease)}
        self.fx = {}            # effect name -> dict(kind, parent, pos)
        self.fx_order = []
        self.markers = []
        self.note = note

    # --- generic keys
    def k(self, target, prop, keys, ease=EIO):
        tr = self.tracks.setdefault((target, prop), {})
        for item in keys:
            f, v = item[0], item[1]
            e = item[2] if len(item) > 2 else ease
            if prop in ('p', 's'): v = (float(v[0]), float(v[1]))
            else: v = float(v)
            if f in tr and not _eq(tr[f][0], v):
                raise ValueError(f'{self.name}: conflicting key {target}.{prop}@{f}: {tr[f][0]} vs {v}')
            tr[f] = (v, e)
        return self

    def vis(self, drawable, changes):
        """step visibility: changes = [(frame, 0|1), ...] (value holds from that frame)"""
        cur = self.default_o(drawable)
        keys = []
        for f, v in sorted(changes):
            if f == 0: keys.append((0, v)); cur = v; continue
            if v == cur: continue
            keys.append((f - 1, cur, LIN)); keys.append((f, v)); cur = v
        if keys and keys[0][0] != 0: keys.insert(0, (0, self.default_o(drawable)))
        self.k(drawable, 'o', keys)
        return self

    def show(self, drawable, f0, f1):
        """visible on [f0, f1) (hidden outside), for default-hidden drawables"""
        ch = [(f0, 1)]
        if f1 < self.N: ch.append((f1, 0))
        return self.vis(drawable, ch)

    def hide(self, drawable, f0, f1):
        ch = [(f0, 0)]
        if f1 < self.N: ch.append((f1, 1))
        return self.vis(drawable, ch)

    def swap(self, a, b, f0, f1):
        """hide a / show b on [f0,f1)"""
        self.hide(a, f0, f1); self.show(b, f0, f1); return self

    def default_o(self, d):
        if d in self.fx: return 0
        return rig.DEFAULT_VIS[d]

    def effect(self, name, kind, pos, parent='stage'):
        self.fx[name] = dict(kind=kind, parent=parent, pos=pos)
        self.fx_order.append(name)
        return name

    def sample(self, target, prop, fn, f0=0, f1=None, step=2):
        f1 = self.N if f1 is None else f1
        keys = []
        f = f0
        while f < f1:
            keys.append((f, fn(f), LIN)); f += step
        keys.append((f1, fn(f1), LIN))
        self.k(target, prop, keys)

    # --- evaluation (used for checks + sequencing)
    def value(self, target, prop, f):
        tr = self.tracks.get((target, prop))
        if not tr:
            return self.default_o(target) if prop == 'o' else DEFAULTS[prop]
        ks = sorted(tr.items())
        if f <= ks[0][0]: return ks[0][1][0]
        if f >= ks[-1][0]: return ks[-1][1][0]
        for (fa, (va, e)), (fb, (vb, _)) in zip(ks, ks[1:]):
            if fa <= f <= fb:
                u = bez_y(e, (f - fa) / (fb - fa))
                if isinstance(va, tuple): return tuple(a + (b - a) * u for a, b in zip(va, vb))
                return va + (vb - va) * u

def _eq(a, b):
    if isinstance(a, tuple): return all(abs(x - y) < 1e-6 for x, y in zip(a, b))
    return abs(a - b) < 1e-6

def bez_y(e, x):
    x1, y1, x2, y2 = e
    if (x1, y1, x2, y2) == LIN: return x
    lo, hi = 0.0, 1.0
    for _ in range(50):
        m = (lo + hi) / 2
        bx = 3 * (1 - m) ** 2 * m * x1 + 3 * (1 - m) * m * m * x2 + m ** 3
        lo, hi = (m, hi) if bx < x else (lo, m)
    m = (lo + hi) / 2
    return 3 * (1 - m) ** 2 * m * y1 + 3 * (1 - m) * m * m * y2 + m ** 3

# ------------------------------------------------------------------ scene assembly
def scene(clip):
    """returns (bones dict name->(parent,pivot), drawables list [(name,bone,shapes,offset)])"""
    bones = dict(rig.BONES)
    draws = []
    for name, bone, shapes, vis in rig.D:
        if vis == 0 and (name, 'o') not in clip.tracks: continue
        draws.append((name, bone, shapes, (0, 0)))
    for name in clip.fx_order:
        fx = clip.fx[name]
        bones[name] = (fx['parent'], fx['pos'])
        draws.append((name, name, rig.effect_shapes(fx['kind']), fx['pos']))
    # keep only bones that are needed
    need = set()
    for _, b, _, _ in draws:
        while b: need.add(b); b = bones[b][0]
    bones = {k: v for k, v in bones.items() if k in need}
    return bones, draws

def chain(bones, b):
    c = []
    while b: c.append(b); b = bones[b][0]
    return list(reversed(c))

def check_clip(clip):
    """neutral start/end + seamless loops (effect motion tracks are exempt: effects are invisible at the ends)"""
    errs = []
    for (t, p), tr in clip.tracks.items():
        if t in clip.fx and p != 'o': continue
        v0 = clip.value(t, p, 0); vN = clip.value(t, p, clip.N)
        d = clip.default_o(t) if p == 'o' else DEFAULTS[p]
        same = lambda a, b: _eq(a, b) or (p == 'r' and abs((a - b) % 360) < 1e-6)
        if clip.loop and not same(v0, vN): errs.append(f'{t}.{p} not seamless {v0}->{vN}')
        if clip.neutral_start and not _eq(v0, d): errs.append(f'{t}.{p} start {v0} != neutral {d}')
        if clip.neutral_end and not same(vN, d): errs.append(f'{t}.{p} end {vN} != neutral {d}')
    return errs

# ------------------------------------------------------------------ LOTTIE
def _static(v): return {"a": 0, "k": v}
def _conv(prop, v, pivot):
    if prop == 'p': return [round(pivot[0] + v[0], 3), round(pivot[1] + v[1], 3), 0]
    if prop == 's': return [round(v[0] * 100, 4), round(v[1] * 100, 4), 100]
    if prop == 'o': return [round(v * 100, 3)]
    return [round(v, 4)]

def lprop(clip, target, prop, pivot=(0, 0)):
    tr = clip.tracks.get((target, prop))
    if not tr:
        d = clip.default_o(target) if prop == 'o' else DEFAULTS[prop]
        v = _conv(prop, d, pivot)
        return _static(v if prop in ('p', 's') else v[0])
    ks = sorted(tr.items()); out = []
    if all(_eq(v, ks[0][1][0]) for _, (v, _) in ks):      # constant track -> static value
        v = _conv(prop, ks[0][1][0], pivot)
        return _static(v if prop in ('p', 's') else v[0])
    for n, (f, (v, e)) in enumerate(ks):
        s = _conv(prop, v, pivot)
        k = {"t": f, "s": s}
        if n < len(ks) - 1:
            dim = len(s)
            k["o"] = {"x": [e[0]] * dim, "y": [e[1]] * dim}
            k["i"] = {"x": [e[2]] * dim, "y": [e[3]] * dim}
            if prop == 'p': k["to"] = [0, 0, 0]; k["ti"] = [0, 0, 0]
        out.append(k)
    return {"a": 1, "k": out}

def l_shape(sh, offset):
    from build_lottie_shapes import path_items, rgb
    it = []
    if sh['k'] == 'path': it += path_items(sh['d'])
    else: it.append({"ty": "el", "d": 1, "p": _static([sh['cx'], sh['cy']]), "s": _static([2 * sh['rx'], 2 * sh['ry']])})
    if sh.get('stroke'):
        it.append({"ty": "st", "c": _static(rgb(sh['stroke'])), "o": _static(100), "w": _static(sh['sw']), "lc": 2, "lj": 2, "ml": 4})
    if sh.get('fill'):
        it.append({"ty": "fl", "c": _static(rgb(sh['fill'])), "o": _static(100), "r": 1})
    it.append({"ty": "tr", "p": _static(list(offset)), "a": _static([0, 0]), "s": _static([100, 100]), "r": _static(0),
               "o": _static(round(sh.get('op', 1) * 100, 2)), "sk": _static(0), "sa": _static(0)})
    return {"ty": "gr", "it": it, "nm": sh['k']}

def to_lottie(clip):
    bones, draws = scene(clip)
    N = clip.N
    ind = {}
    layers_nulls = []
    for i, b in enumerate(bones): ind[b] = i + 1
    for b, (parent, pivot) in bones.items():
        if b == 'stage':
            ks = {"o": _static(100), "r": _static(0), "p": _static([rig.STAGE['tx'], rig.STAGE['ty'], 0]),
                  "a": _static([0, 0, 0]), "s": _static([rig.STAGE['s'] * 100, rig.STAGE['s'] * 100, 100])}
        else:
            ks = {"o": _static(100), "r": lprop(clip, b, 'r'), "p": lprop(clip, b, 'p', pivot),
                  "a": _static([pivot[0], pivot[1], 0]), "s": lprop(clip, b, 's')}
        L = {"ddd": 0, "ind": ind[b], "ty": 3, "nm": 'bone_' + b, "sr": 1, "ks": ks, "ao": 0, "ip": 0, "op": N, "st": 0, "bm": 0}
        if parent: L["parent"] = ind[parent]
        layers_nulls.append(L)
    layers_d = []
    nxt = len(bones) + 1
    for name, bone, shapes, offset in draws:
        ks = {"o": lprop(clip, name, 'o'), "r": _static(0), "p": _static([0, 0, 0]), "a": _static([0, 0, 0]), "s": _static([100, 100, 100])}
        layers_d.append({"ddd": 0, "ind": nxt, "ty": 4, "nm": name, "sr": 1, "ks": ks, "ao": 0, "parent": ind[bone],
                         "shapes": [l_shape(s, offset) for s in reversed(shapes)], "ip": 0, "op": N, "st": 0, "bm": 0})
        nxt += 1
    layers = list(reversed(layers_d)) + layers_nulls
    return {"v": "5.7.0", "fr": FPS, "ip": 0, "op": N, "w": CANVAS, "h": CANVAS, "nm": clip.name, "ddd": 0,
            "assets": [], "layers": layers,
            "markers": [{"tm": m[0], "cm": m[1], "dr": m[2]} for m in clip.markers]}

# ------------------------------------------------------------------ SVG / SMIL
def fmt(v): return ('%.3f' % v).rstrip('0').rstrip('.') if abs(v) > 1e-9 else '0'

def is_const(clip, target, prop):
    tr = clip.tracks.get((target, prop))
    if not tr: return True
    v0 = next(iter(tr.values()))[0]
    return all(_eq(v, v0) for v, _ in tr.values())

def smil_track(clip, target, prop, pivot=(0, 0)):
    tr = clip.tracks.get((target, prop))
    ks = sorted(tr.items())
    if ks[0][0] > 0: ks.insert(0, (0, (ks[0][1][0], EIO)))
    if ks[-1][0] < clip.N: ks.append((clip.N, (ks[-1][1][0], EIO)))
    def val(v):
        if prop == 'p': return f'{fmt(pivot[0] + v[0])} {fmt(pivot[1] + v[1])}'
        if prop == 's': return f'{fmt(v[0])} {fmt(v[1])}'
        return fmt(v)
    values = ';'.join(val(v) for _, (v, _) in ks)
    times = ';'.join(fmt(f / clip.N) for f, _ in ks)
    splines = ';'.join(' '.join(fmt(x) for x in e) for _, (_, e) in ks[:-1])
    dur = fmt(clip.N / FPS) + 's'
    rep = 'repeatCount="indefinite"' if clip.loop else 'fill="freeze"'
    common = f'dur="{dur}" values="{values}" keyTimes="{times}" calcMode="spline" keySplines="{splines}" {rep}'
    if prop == 'o': return f'<animate attributeName="opacity" {common}/>'
    typ = {'p': 'translate', 'r': 'rotate', 's': 'scale'}[prop]
    return f'<animateTransform attributeName="transform" type="{typ}" {common}/>'

def svg_shape(sh):
    st = ''
    if sh.get('stroke'): st += f' stroke="{sh["stroke"]}" stroke-width="{fmt(sh["sw"])}" stroke-linejoin="round" stroke-linecap="round"'
    else: st += ' stroke="none"'
    st += f' fill="{sh["fill"]}"' if sh.get('fill') else ' fill="none"'
    if sh.get('op', 1) != 1: st += f' opacity="{fmt(sh["op"])}"'
    if sh['k'] == 'path': return f'<path d="{sh["d"]}"{st}/>'
    return f'<ellipse cx="{fmt(sh["cx"])}" cy="{fmt(sh["cy"])}" rx="{fmt(sh["rx"])}" ry="{fmt(sh["ry"])}"{st}/>'

def bone_open(clip, b, pivot):
    """returns list of opening tags (each a <g ...>) for this bone"""
    if b == 'stage':
        return [f'<g transform="translate({fmt(rig.STAGE["tx"])} {fmt(rig.STAGE["ty"])}) scale({fmt(rig.STAGE["s"])})">']
    anim = {p: (b, p) in clip.tracks for p in 'prs'}
    if not any(anim.values()):
        return [f'<g>']   # no-op bone (pivot only)
    tags = []
    if anim['p']: tags.append('<g>' + smil_track(clip, b, 'p', pivot))
    else: tags.append(f'<g transform="translate({fmt(pivot[0])} {fmt(pivot[1])})">')
    if anim['r']: tags.append('<g>' + smil_track(clip, b, 'r'))
    if anim['s']: tags.append('<g>' + smil_track(clip, b, 's'))
    tags.append(f'<g transform="translate({fmt(-pivot[0])} {fmt(-pivot[1])})">')
    return tags

def to_svg(clip):
    bones, draws = scene(clip)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS}" height="{CANVAS}" viewBox="0 0 {CANVAS} {CANVAS}">',
           f'<title>{clip.name}</title>']
    stack = []   # list of (bone, n_tags)
    for name, bone, shapes, offset in draws:
        ch = chain(bones, bone)
        # pop divergent levels
        common = 0
        while common < len(stack) and common < len(ch) and stack[common][0] == ch[common]: common += 1
        while len(stack) > common:
            _, n = stack.pop(); out.append('</g>' * n)
        for b in ch[common:]:
            tags = bone_open(clip, b, bones[b][1]); out += tags; stack.append((b, len(tags)))
        # drawable group (opacity)
        op = ''
        if (name, 'o') in clip.tracks:
            v0 = clip.value(name, 'o', 0)
            out.append(f'<g opacity="{fmt(v0)}">' + smil_track(clip, name, 'o'))
        else:
            out.append('<g>')
        if offset != (0, 0): out.append(f'<g transform="translate({fmt(offset[0])} {fmt(offset[1])})">')
        out += [svg_shape(s) for s in shapes]
        if offset != (0, 0): out.append('</g>')
        out.append('</g>')
    while stack:
        _, n = stack.pop(); out.append('</g>' * n)
    out.append('</svg>')
    return '\n'.join(out)

# ------------------------------------------------------------------ sequencing
def sequence(name, cat, clips, loop=True):
    N = sum(c.N for c in clips)
    s = Clip(name, cat, N, loop)
    keys_all = {}
    for c in clips:
        for key in c.tracks: keys_all.setdefault(key, None)
        for fx in c.fx_order:
            if fx in s.fx and s.fx[fx] != c.fx[fx]: raise ValueError('fx clash ' + fx)
            if fx not in s.fx: s.effect(fx, c.fx[fx]['kind'], c.fx[fx]['pos'], c.fx[fx]['parent'])
    t0 = 0
    for c in clips:
        s.markers.append((t0, c.name, c.N))
        for (tgt, p) in keys_all:
            tr = c.tracks.get((tgt, p))
            if tr:
                ks = sorted(tr.items())
                if ks[0][0] > 0: ks.insert(0, (0, (ks[0][1][0], EIO)))
                if ks[-1][0] < c.N: ks.append((c.N, (ks[-1][1][0], EIO)))
            else:
                d = rig.DEFAULT_VIS.get(tgt, 0) if p == 'o' else DEFAULTS[p]
                ks = [(0, (d, EIO)), (c.N, (d, EIO))]
            dest = s.tracks.setdefault((tgt, p), {})
            for f, (v, e) in ks:
                F = t0 + f
                if F in dest:
                    if not _eq(dest[F][0], v) and not (tgt in s.fx and p != 'o'):
                        raise ValueError(f'seam mismatch {tgt}.{p} at {c.name} start: {dest[F][0]} vs {v}')
                    dest[F] = (v, e)   # keep easing of the new segment
                else:
                    dest[F] = (v, e)
        t0 += c.N
    return s
