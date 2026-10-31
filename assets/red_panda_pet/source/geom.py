"""Bezier path geometry shared by the Lottie and SVG exporters.

A Path is a list of subpaths. Each subpath is a dict with
  v: vertices [(x,y)], i: in-tangents (relative), o: out-tangents (relative), c: closed
which is exactly Lottie's "sh" representation, so both exporters draw identical curves.
"""
import math
import re

KAPPA = 0.5522847498


def _sub(v, i, o, c):
    return {"v": [tuple(p) for p in v], "i": [tuple(p) for p in i], "o": [tuple(p) for p in o], "c": c}


def ellipse(cx, cy, rx, ry, rot=0.0):
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)

    def R(x, y):
        return (x * ca - y * sa, x * sa + y * ca)

    # start at top, go clockwise (screen): top, right, bottom, left
    pts = [(0, -ry), (rx, 0), (0, ry), (-rx, 0)]
    outs = [(rx * KAPPA, 0), (0, ry * KAPPA), (-rx * KAPPA, 0), (0, -ry * KAPPA)]
    v, i, o = [], [], []
    for p, t in zip(pts, outs):
        px, py = R(*p)
        tx, ty = R(*t)
        v.append((cx + px, cy + py))
        o.append((tx, ty))
        i.append((-tx, -ty))
    return [_sub(v, i, o, True)]


def circle(cx, cy, r):
    return ellipse(cx, cy, r, r)


def smooth(pts, closed=True, k=1.0):
    """Catmull-Rom spline through pts, converted to cubic beziers."""
    n = len(pts)
    v, i, o = [], [], []
    for j in range(n):
        p = pts[j]
        if closed:
            pp, pn = pts[(j - 1) % n], pts[(j + 1) % n]
        else:
            pp = pts[j - 1] if j > 0 else p
            pn = pts[j + 1] if j < n - 1 else p
        tx = (pn[0] - pp[0]) / 6.0 * k
        ty = (pn[1] - pp[1]) / 6.0 * k
        v.append(p)
        o.append((tx, ty))
        i.append((-tx, -ty))
    if not closed:
        i[0] = (0, 0)
        o[-1] = (0, 0)
    return [_sub(v, i, o, closed)]


def poly(pts, closed=False):
    z = [(0, 0)] * len(pts)
    return [_sub(pts, z, z, closed)]


def svgpath(d):
    """Parse an absolute SVG path (M L C Q Z only) into a Path."""
    toks = re.findall(r"[MLCQZmlcqz]|-?\d*\.?\d+(?:e-?\d+)?", d)
    subs = []
    cur = None
    idx = 0
    cmd = None

    def num():
        nonlocal idx
        val = float(toks[idx])
        idx += 1
        return val

    while idx < len(toks):
        t = toks[idx]
        if re.match(r"[MLCQZmlcqz]", t):
            cmd = t.upper()
            idx += 1
            if cmd == "Z":
                if cur:
                    # merge closing point if equal to the first
                    if len(cur["v"]) > 1 and _close(cur["v"][-1], cur["v"][0]):
                        cur["i"][0] = cur["i"][-1]
                        cur["v"].pop(); cur["i"].pop(); cur["o"].pop()
                    cur["c"] = True
                    subs.append(cur)
                    cur = None
                continue
        if cmd == "M":
            if cur:
                subs.append(cur)
            x, y = num(), num()
            cur = {"v": [(x, y)], "i": [(0, 0)], "o": [(0, 0)], "c": False}
            cmd = "L"
        elif cmd == "L":
            x, y = num(), num()
            cur["v"].append((x, y)); cur["i"].append((0, 0)); cur["o"].append((0, 0))
        elif cmd == "C":
            x1, y1, x2, y2, x, y = [num() for _ in range(6)]
            lx, ly = cur["v"][-1]
            cur["o"][-1] = (x1 - lx, y1 - ly)
            cur["v"].append((x, y)); cur["i"].append((x2 - x, y2 - y)); cur["o"].append((0, 0))
        elif cmd == "Q":
            qx, qy, x, y = [num() for _ in range(4)]
            lx, ly = cur["v"][-1]
            cur["o"][-1] = (2 / 3 * (qx - lx), 2 / 3 * (qy - ly))
            cur["v"].append((x, y)); cur["i"].append((2 / 3 * (qx - x), 2 / 3 * (qy - y))); cur["o"].append((0, 0))
    if cur:
        subs.append(cur)
    return subs


def _close(a, b):
    return abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6


def xform(path, dx=0.0, dy=0.0, rot=0.0, sx=1.0, sy=None, ox=0.0, oy=0.0):
    """Scale/rotate about (ox,oy), then translate. Returns a new Path."""
    if sy is None:
        sy = sx
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)

    def P(p):
        x, y = (p[0] - ox) * sx, (p[1] - oy) * sy
        return (x * ca - y * sa + ox + dx, x * sa + y * ca + oy + dy)

    def T(t):
        x, y = t[0] * sx, t[1] * sy
        return (x * ca - y * sa, x * sa + y * ca)

    out = []
    for s in path:
        out.append(_sub([P(p) for p in s["v"]], [T(t) for t in s["i"]], [T(t) for t in s["o"]], s["c"]))
    return out


def mirror_x(path):
    out = []
    for s in path:
        out.append(_sub([(-x, y) for x, y in s["v"]], [(-x, y) for x, y in s["i"]], [(-x, y) for x, y in s["o"]], s["c"]))
    return out


def fmt(x):
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def to_d(path):
    parts = []
    for s in path:
        v, i, o = s["v"], s["i"], s["o"]
        n = len(v)
        parts.append(f"M{fmt(v[0][0])} {fmt(v[0][1])}")
        segs = n if s["c"] else n - 1
        for k in range(segs):
            j = (k + 1) % n
            if o[k] == (0, 0) and i[j] == (0, 0):
                parts.append(f"L{fmt(v[j][0])} {fmt(v[j][1])}")
            else:
                c1 = (v[k][0] + o[k][0], v[k][1] + o[k][1])
                c2 = (v[j][0] + i[j][0], v[j][1] + i[j][1])
                parts.append(f"C{fmt(c1[0])} {fmt(c1[1])} {fmt(c2[0])} {fmt(c2[1])} {fmt(v[j][0])} {fmt(v[j][1])}")
        if s["c"]:
            parts.append("Z")
    return "".join(parts)


def r2(x):
    return round(x, 2)


def to_lottie_sh(sub):
    return {
        "i": [[r2(a), r2(b)] for a, b in sub["i"]],
        "o": [[r2(a), r2(b)] for a, b in sub["o"]],
        "v": [[r2(a), r2(b)] for a, b in sub["v"]],
        "c": sub["c"],
    }
