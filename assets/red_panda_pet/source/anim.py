"""Clip model + exporters. One keyframe model feeds both Lottie (bodymovin 5.7) and SMIL SVG,
so the two formats share identical keyframes, easing curves and draw order."""
import json
import math
from collections import defaultdict
from geom import to_d, to_lottie_sh, fmt


def fmt4(x):
    v = f"{x:.4f}".rstrip("0").rstrip(".")
    return "0" if v in ("-0", "") else v

import rig
from rig import NODES, LAYERS, Node, Layer, GROUP_DEFAULT

FPS = 30
W = H = 512
EASE = (0.42, 0.0, 0.58, 1.0)          # standard ease-in-out
SOFT = (0.33, 0.0, 0.67, 1.0)          # gentle ease-in-out (floaty loops)
EOUT = (0.2, 0.0, 0.4, 1.0)            # ease-in-out, front-loaded (launches)
EIN = (0.6, 0.0, 0.85, 1.0)            # ease-in-out, back-loaded (falls)


def rest_value(node, prop):
    n = NODES.get(node)
    if prop == "p":
        return (0.0, 0.0)
    if prop == "r":
        return 0.0
    if prop == "s":
        if n is not None and getattr(n, "rest_s", None) is not None:
            return n.rest_s
        return (1.0, 1.0)


def norm(prop, v):
    if prop == "s" and not isinstance(v, (tuple, list)):
        return (float(v), float(v))
    if prop in ("p", "s"):
        return (float(v[0]), float(v[1]))
    return float(v)


def same(a, b, eps=1e-6):
    if isinstance(a, tuple):
        return all(abs(x - y) < eps for x, y in zip(a, b))
    return abs(a - b) < eps


class Clip:
    def __init__(self, name, category, frames, loop=True, base="sitting", seam="base", desc=""):
        self.name, self.category, self.frames, self.loop = name, category, frames, loop
        self.base, self.seam, self.desc = base, seam, desc
        self.tracks = defaultdict(dict)
        self.vis = defaultdict(dict)
        self.lvis = defaultdict(dict)
        self.fx_nodes = {}
        self.fx_layers = []

    # ---- authoring
    def k(self, node, prop, f, value, ease=EASE):
        assert node in NODES or node in self.fx_nodes, node
        self.tracks[(node, prop)][int(round(f))] = (norm(prop, value), ease)

    def pose(self, f, P, ease=EASE):
        for node, props in P.items():
            for prop, val in props.items():
                self.k(node, prop, f, val, ease)

    def poses(self, seq, ease=EASE):
        for f, P in seq:
            self.pose(f, P, ease)

    def hold(self, f0, f1, P, ease=EASE):
        self.pose(f0, P, ease)
        self.pose(f1, P, ease)

    def v(self, group, f, opt):
        self.vis[group][int(round(f))] = opt

    def vseq(self, group, seq):
        for f, o in seq:
            self.v(group, f, o)

    def fx(self, name, shapes, at=(0, 0), parent="root", z="top", rest_s=(0.0, 0.0)):
        n = Node(name, parent, (0, 0), pos=at)
        n.rest_s = rest_s
        self.fx_nodes[name] = n
        self.fx_layers.append((Layer(name, name, shapes), z))
        return name

    def pop(self, node, f_in, f_out, size=1.0, dur=6, overshoot=1.2, ease=EASE):
        """Scale pop in at f_in, out at f_out."""
        self.k(node, "s", f_in, 0, ease)
        self.k(node, "s", f_in + dur * 0.6, size * overshoot, ease)
        self.k(node, "s", f_in + dur, size, ease)
        self.k(node, "s", f_out - dur * 0.5, size * 1.1 if overshoot > 1 else size, ease)
        self.k(node, "s", f_out, 0, ease)

    # ---- resolution
    def node(self, name):
        return self.fx_nodes.get(name) or NODES[name]

    def rest(self, name, prop):
        n = self.node(name)
        if prop == "s" and getattr(n, "rest_s", None) is not None:
            return tuple(n.rest_s)
        return rest_value(name, prop)

    def base_pose(self):
        return BASES[self.base]

    def resolved_tracks(self):
        N = self.frames
        bp = self.base_pose()["nodes"]
        out = {}
        # nodes posed by the base pose but not animated by this clip hold their base value
        for node, props in bp.items():
            for prop, val in props.items():
                if (node, prop) not in self.tracks:
                    out[(node, prop)] = [(0, norm(prop, val), EASE)]
        for (node, prop), keys in self.tracks.items():
            ks = dict(keys)
            basev = bp.get(node, {}).get(prop)
            basev = norm(prop, basev) if basev is not None else self.rest(node, prop)
            if 0 not in ks:
                ks[0] = (basev, EASE)
            if N not in ks:
                if self.loop:
                    ks[N] = ks[0]
                else:
                    last = ks[max(ks)]
                    ks[N] = last
            lst = sorted((f, v, e) for f, (v, e) in ks.items() if 0 <= f <= N)
            if self.loop and not same(lst[0][1], lst[-1][1]):
                raise ValueError(f"{self.name}: {node}.{prop} does not loop ({lst[0][1]} vs {lst[-1][1]})")
            if self.loop and self.seam == "base" and not same(lst[0][1], basev):
                raise ValueError(f"{self.name}: {node}.{prop} seam {lst[0][1]} != base {basev}")
            if all(same(x[1], lst[0][1]) for x in lst):
                lst = [lst[0]]
            out[(node, prop)] = lst
        return out

    def resolved_vis(self):
        """layer name -> list of (frame, bool)"""
        N = self.frames
        bv = self.base_pose()["vis"]
        gtracks = {}
        for g, default in GROUP_DEFAULT.items():
            ks = dict(self.vis.get(g, {}))
            start = bv.get(g, default)
            if 0 not in ks:
                ks[0] = start
            if self.loop and self.seam == "base" and ks[0] != start:
                raise ValueError(f"{self.name}: vis {g} seam {ks[0]} != base {start}")
            gtracks[g] = sorted(ks.items())
        res = {}
        allayers = list(LAYERS) + [l for l, z in self.fx_layers]
        for L in allayers:
            if L.group:
                seq = [(f, o in L.opts) for f, o in gtracks[L.group]]
            elif L.name in self.lvis:
                ks = dict(self.lvis[L.name])
                ks.setdefault(0, True)
                seq = sorted(ks.items())
            else:
                seq = [(0, True)]
            comp = []
            for f, b in seq:
                if f > N:
                    continue
                if not comp or comp[-1][1] != b:
                    comp.append((f, b))
            res[L.name] = comp
        return res

    def layer_stack(self):
        stack = list(LAYERS)
        for L, z in self.fx_layers:
            if z == "top":
                stack.append(L)
            elif z == "bottom":
                stack.insert(1, L)
            else:  # insert before named layer
                idx = [l.name for l in stack].index(z)
                stack.insert(idx, L)
        return stack

    def chain(self, node):
        out = []
        n = node
        while n:
            out.append(n)
            n = self.node(n).parent
        return list(reversed(out))


# ---------------------------------------------------------------- base poses
BASES = {
    "sitting": {"nodes": {}, "vis": {}},
    "draped": {"nodes": {}, "vis": {"eyes": "closed", "branch": "front"}},
}


# ---------------------------------------------------------------- forward kinematics (authoring helper)
def mat_mul(a, b):
    return [a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1], a[0] * b[2] + a[2] * b[3],
            a[1] * b[2] + a[3] * b[3], a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5]]


def mat_node(n, p=(0, 0), r=0.0, s=(1, 1)):
    px, py = n.pos[0] + p[0], n.pos[1] + p[1]
    rr = math.radians(n.rot + r)
    sx, sy = n.scale[0] * s[0], n.scale[1] * s[1]
    c, si = math.cos(rr), math.sin(rr)
    m = [c * sx, si * sx, -si * sy, c * sy, 0, 0]
    ax, ay = n.pivot
    m[4] = px - (m[0] * ax + m[2] * ay)
    m[5] = py - (m[1] * ax + m[3] * ay)
    return m


def apply(m, pt):
    return (m[0] * pt[0] + m[2] * pt[1] + m[4], m[1] * pt[0] + m[3] * pt[1] + m[5])


def inv(m):
    det = m[0] * m[3] - m[1] * m[2]
    a, b, c, d = m[3] / det, -m[1] / det, -m[2] / det, m[0] / det
    return [a, b, c, d, -(a * m[4] + c * m[5]), -(b * m[4] + d * m[5])]


def world(pose, node, upto_root=False):
    """Matrix of `node` in character space (root excluded) for pose dict {node:{p,r,s}}."""
    chain = []
    n = node
    while n and n != "root":
        chain.append(n)
        n = NODES[n].parent
    m = [1, 0, 0, 1, 0, 0]
    for name in reversed(chain):
        pr = pose.get(name, {})
        m = mat_mul(m, mat_node(NODES[name], norm("p", pr.get("p", (0, 0))), pr.get("r", 0.0),
                                norm("s", pr.get("s", 1.0))))
    return m


def world_rot(pose, node):
    m = world(pose, node)
    return math.degrees(math.atan2(m[1], m[0]))


def place(pose, node, point, target, rot_world=None):
    """Set pose[node] p (and r) so that `point` (rest coords of node) lands at `target`."""
    n = NODES[node]
    pose.setdefault(node, {})
    parent_m = world(pose, n.parent) if n.parent and n.parent != "root" else [1, 0, 0, 1, 0, 0]
    if rot_world is not None:
        prot = math.degrees(math.atan2(parent_m[1], parent_m[0]))
        pose[node]["r"] = rot_world - prot
    r = pose[node].get("r", 0.0)
    s = norm("s", pose[node].get("s", 1.0))
    q = apply(inv(parent_m), target)
    m0 = mat_node(n, (0, 0), r, s)
    cur = apply(m0, point)
    pose[node]["p"] = (q[0] - cur[0], q[1] - cur[1])
    return pose


def tail_dirs(pose, dirs, parent_rot=None):
    """Point the four tail segments in world directions (deg, 0=right, 90=down)."""
    pts = rig.J + [rig.TAIL_TIP]
    rest = [math.degrees(math.atan2(pts[k + 1][1] - pts[k][1], pts[k + 1][0] - pts[k][0])) for k in range(4)]
    if parent_rot is None:
        parent_rot = world_rot(pose, "torso")
    acc_prev = parent_rot
    for k in range(4):
        world_target = dirs[k]
        local = world_target - rest[k] - acc_prev
        # keep the rotation in (-180,180] so interpolation takes the short way
        local = (local + 180) % 360 - 180
        pose.setdefault(f"tail{k}", {})["r"] = local
        acc_prev += local
    return pose


TAIL_REST_DIRS = None


def _rest_dirs():
    pts = rig.J + [rig.TAIL_TIP]
    return [math.degrees(math.atan2(pts[k + 1][1] - pts[k][1], pts[k + 1][0] - pts[k][0])) for k in range(4)]


TAIL_REST_DIRS = _rest_dirs()


# ---------------------------------------------------------------- exporters
def hex_rgb(h):
    h = h.lstrip("#")
    return [round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)]


def node_components(clip, name, tracks):
    n = clip.node(name)
    tp = tracks.get((name, "p"))
    tr = tracks.get((name, "r"))
    ts = tracks.get((name, "s"))
    identity_static = (not tp and not tr and not ts and n.pos == n.pivot and n.rot == 0 and n.scale == (1.0, 1.0))
    return n, tp, tr, ts, identity_static


def _static_or_track(lst):
    if lst is None:
        return None
    if len(lst) == 1:
        return lst[0][1]
    return lst


def lottie_prop(lst, conv, static):
    if lst is None or len(lst) == 1:
        val = conv(lst[0][1]) if lst else conv(static)
        return {"a": 0, "k": val}
    ks = []
    for idx, (f, v, e) in enumerate(lst):
        val = conv(v)
        kf = {"t": f, "s": val}
        if idx < len(lst) - 1:
            n = len(val)
            kf["o"] = {"x": [e[0]] * n, "y": [e[1]] * n}
            kf["i"] = {"x": [e[2]] * n, "y": [e[3]] * n}
        ks.append(kf)
    return {"a": 1, "k": ks}


def r3(x):
    return round(x, 4)


def lottie_tr(clip, name, tracks):
    n = clip.node(name)
    tp, tr, ts = tracks.get((name, "p")), tracks.get((name, "r")), tracks.get((name, "s"))
    restp = (0.0, 0.0)
    rs = clip.rest(name, "s")
    return {
        "ty": "tr",
        "p": lottie_prop(tp, lambda d: [r3(n.pos[0] + d[0]), r3(n.pos[1] + d[1])], restp),
        "a": {"a": 0, "k": [r3(n.pivot[0]), r3(n.pivot[1])]},
        "s": lottie_prop(ts, lambda s: [r3(n.scale[0] * s[0] * 100), r3(n.scale[1] * s[1] * 100)], rs),
        "r": lottie_prop(tr, lambda r: [r3(n.rot + r)], 0.0) if tr and len(tr) > 1 else
        {"a": 0, "k": r3(n.rot + (tr[0][1] if tr else 0.0))},
        "o": {"a": 0, "k": 100}, "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0}, "nm": "Transform",
    }


def lottie_shape(sh, idx):
    items = []
    for sub in sh["path"]:
        items.append({"ty": "sh", "nm": "Path", "ks": {"a": 0, "k": to_lottie_sh(sub)}})
    for col, w in reversed(sh["strokes"]):
        items.append({"ty": "st", "nm": "Stroke", "c": {"a": 0, "k": hex_rgb(col) + [1]}, "o": {"a": 0, "k": 100},
                      "w": {"a": 0, "k": r3(w)}, "lc": 2, "lj": 2, "ml": 4, "bm": 0})
    if sh["fill"]:
        items.append({"ty": "fl", "nm": "Fill", "c": {"a": 0, "k": hex_rgb(sh["fill"]) + [1]},
                      "o": {"a": 0, "k": r3(sh["fo"] * 100)}, "r": 1, "bm": 0})
    items.append(ident_tr())
    return {"ty": "gr", "nm": f"shape{idx}", "it": items, "np": len(items) - 1, "cix": 2, "bm": 0}


def ident_tr():
    return {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]},
            "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}, "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0},
            "nm": "Transform"}


def to_lottie(clip):
    N = clip.frames
    tracks = clip.resolved_tracks()
    vis = clip.resolved_vis()
    layers = []
    stack = clip.layer_stack()
    ind = 0
    for L in reversed(stack):
        vs = vis[L.name]
        if not any(b for f, b in vs):
            continue
        ind += 1
        inner_items = [lottie_shape(sh, i) for i, sh in reversed(list(enumerate(L.shapes)))]
        inner_items.append(ident_tr())
        grp = {"ty": "gr", "nm": L.name, "it": inner_items, "np": len(inner_items) - 1, "cix": 2, "bm": 0}
        for name in reversed(clip.chain(L.node)):
            n, tp, tr, ts, ident = node_components(clip, name, tracks)
            if ident and name not in clip.fx_nodes:
                continue
            grp = {"ty": "gr", "nm": name, "it": [grp, lottie_tr(clip, name, tracks)], "np": 1, "cix": 2, "bm": 0}
        if len(vs) == 1:
            op = {"a": 0, "k": 100 if vs[0][1] else 0}
        else:
            op = {"a": 1, "k": [{"t": f, "s": [100 if b else 0], "h": 1} for f, b in vs]}
        layers.append({
            "ddd": 0, "ind": ind, "ty": 4, "nm": L.name, "ln": L.name, "sr": 1,
            "ks": {"o": op, "r": {"a": 0, "k": 0}, "p": {"a": 0, "k": [0, 0, 0]}, "a": {"a": 0, "k": [0, 0, 0]},
                   "s": {"a": 0, "k": [100, 100, 100]}},
            "ao": 0, "shapes": [grp], "ip": 0, "op": N, "st": 0, "bm": 0})
    return {"v": "5.7.4", "fr": FPS, "ip": 0, "op": N, "w": W, "h": H, "nm": clip.name, "ddd": 0,
            "assets": [], "layers": layers, "markers": []}


# ---- SVG
def kt(f, N):
    return f"{f / N:.5f}".rstrip("0").rstrip(".") if f not in (0, N) else ("0" if f == 0 else "1")


def smil_attrs(clip, lst, discrete=False):
    N = clip.frames
    dur = f"{N / FPS:.4f}".rstrip("0").rstrip(".") + "s"
    times = ";".join(kt(f, N) for f, *_ in lst)
    a = f'dur="{dur}" keyTimes="{times}" '
    if discrete:
        a += 'calcMode="discrete" '
    else:
        a += 'calcMode="spline" keySplines="' + ";".join(
            " ".join(fmt(x) for x in e) for f, v, e in lst[:-1]) + '" '
    a += 'repeatCount="indefinite"' if clip.loop else 'fill="freeze"'
    return a


def svg_node_open(clip, name, tracks):
    n, tp, tr, ts, ident = node_components(clip, name, tracks)
    if ident and name not in clip.fx_nodes:
        return "", ""
    rs = clip.rest(name, "s")
    ops = []  # (kind, static_value or None, track)
    # translate(pos+d)
    if tp and len(tp) > 1:
        ops.append(("translate", None, [(f, (n.pos[0] + v[0], n.pos[1] + v[1]), e) for f, v, e in tp]))
    else:
        d = tp[0][1] if tp else (0, 0)
        ops.append(("translate", (n.pos[0] + d[0], n.pos[1] + d[1]), None))
    if tr and len(tr) > 1:
        ops.append(("rotate", None, [(f, n.rot + v, e) for f, v, e in tr]))
    else:
        ops.append(("rotate", n.rot + (tr[0][1] if tr else 0.0), None))
    if ts and len(ts) > 1:
        ops.append(("scale", None, [(f, (n.scale[0] * v[0], n.scale[1] * v[1]), e) for f, v, e in ts]))
    else:
        sv = ts[0][1] if ts else rs
        ops.append(("scale", (n.scale[0] * sv[0], n.scale[1] * sv[1]), None))
    ops.append(("translate", (-n.pivot[0], -n.pivot[1]), None))

    def static_str(kind, v):
        if kind == "translate":
            return "" if abs(v[0]) < 1e-9 and abs(v[1]) < 1e-9 else f"translate({fmt4(v[0])} {fmt4(v[1])})"
        if kind == "rotate":
            return "" if abs(v) < 1e-9 else f"rotate({fmt4(v)})"
        if kind == "scale":
            return "" if abs(v[0] - 1) < 1e-9 and abs(v[1] - 1) < 1e-9 else f"scale({fmt4(v[0])} {fmt4(v[1])})"

    def val_str(kind, v):
        if kind == "rotate":
            return fmt4(v)
        return f"{fmt4(v[0])} {fmt4(v[1])}"

    opens, closes = [], []
    pending = []
    for kind, sv, trk in ops:
        if trk is None:
            s = static_str(kind, sv)
            if s:
                pending.append(s)
        else:
            if pending:
                opens.append(f'<g transform="{" ".join(pending)}">')
                closes.append("</g>")
                pending = []
            first = val_str(kind, trk[0][1])
            vals = ";".join(val_str(kind, v) for f, v, e in trk)
            opens.append(f'<g transform="{kind}({first})"><animateTransform attributeName="transform" type="{kind}" '
                         f'values="{vals}" {smil_attrs(clip, trk)}/>')
            closes.append("</g>")
    if pending:
        opens.append(f'<g transform="{" ".join(pending)}">')
        closes.append("</g>")
    return "".join(opens), "".join(reversed(closes))


def svg_shape(sh):
    d = to_d(sh["path"])
    out = []
    strokes = sh["strokes"]
    fillattr = f' fill="{sh["fill"]}"' + (f' fill-opacity="{fmt(sh["fo"])}"' if sh["fo"] < 1 else "") if sh["fill"] else ""
    if sh["fill"] and len(strokes) <= 1:
        st = f' stroke="{strokes[0][0]}" stroke-width="{fmt(strokes[0][1])}"' if strokes else ""
        out.append(f'<path d="{d}"{fillattr}{st}/>')
    else:
        if sh["fill"]:
            out.append(f'<path d="{d}"{fillattr}/>')
        for col, w in strokes:
            out.append(f'<path d="{d}" stroke="{col}" stroke-width="{fmt(w)}"/>')
    return "".join(out)


def to_svg(clip):
    tracks = clip.resolved_tracks()
    vis = clip.resolved_vis()
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<title>{clip.name}</title>',
           '<g fill="none" stroke-linecap="round" stroke-linejoin="round">']
    for L in clip.layer_stack():
        vs = vis[L.name]
        if not any(b for f, b in vs):
            continue
        if len(vs) == 1:
            out.append(f'<g id="{L.name}">')
        else:
            vals = ";".join("1" if b else "0" for f, b in vs)
            lst = [(f, b, None) for f, b in vs]
            out.append(f'<g id="{L.name}" opacity="{1 if vs[0][1] else 0}"><animate attributeName="opacity" '
                       f'values="{vals}" {smil_attrs(clip, lst, discrete=True)}/>')
        closes = []
        for name in clip.chain(L.node):
            o, c = svg_node_open(clip, name, tracks)
            out.append(o)
            closes.append(c)
        out.append("".join(svg_shape(sh) for sh in L.shapes))
        out.append("".join(reversed(closes)))
        out.append("</g>")
    out.append("</g></svg>")
    return "".join(out)
