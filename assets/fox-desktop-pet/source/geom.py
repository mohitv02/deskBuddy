import math
from model import Path, smooth


def bez(p0, c1, c2, p1, t):
    u = 1 - t
    return (u * u * u * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * p1[0],
            u * u * u * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * p1[1])


def sample(path, per=16):
    n = len(path.v)
    pts = []
    segs = n if path.closed else n - 1
    for k in range(segs):
        a, b = k, (k + 1) % n
        p0 = path.v[a]
        p1 = path.v[b]
        c1 = (p0[0] + path.o[a][0], p0[1] + path.o[a][1])
        c2 = (p1[0] + path.i[b][0], p1[1] + path.i[b][1])
        for j in range(per):
            pts.append(bez(p0, c1, c2, p1, j / per))
    if not path.closed:
        pts.append(path.v[-1])
    return pts


def resample(pts, n, closed=True):
    """n points evenly by arclength."""
    P = list(pts) + ([pts[0]] if closed else [])
    L = [0]
    for a, b in zip(P, P[1:]):
        L.append(L[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    tot = L[-1]
    out = []
    m = n if closed else n - 1
    j = 0
    for k in range(n):
        s = tot * k / m
        while j < len(L) - 2 and L[j + 1] < s:
            j += 1
        seg = L[j + 1] - L[j] or 1
        f = (s - L[j]) / seg
        a, b = P[j], P[j + 1]
        out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    return out


def spiky(path, n, amp, inner=0.35, round_=0.15):
    """Zig-zag fur version of a closed path (spikes outward)."""
    pts = resample(sample(path, 24), n * 2)
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    out = []
    N = len(pts)
    for k, p in enumerate(pts):
        a, b = pts[(k - 1) % N], pts[(k + 1) % N]
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1
        nx, ny = ty / ln, -tx / ln
        # make normal point outward
        if (p[0] - cx) * nx + (p[1] - cy) * ny < 0:
            nx, ny = -nx, -ny
        d = amp if k % 2 == 0 else -amp * inner
        out.append((p[0] + nx * d, p[1] + ny * d, round_ if k % 2 == 0 else 0.6))
    return smooth(out)


def patch(path, i0, i1, extra, t=1.0):
    """Sub-region bounded by the exact contour from vertex i0..i1 (forward)
    and a custom curve `extra` back to i0."""
    n = len(path.v)
    idx = []
    k = i0
    while True:
        idx.append(k)
        if k == i1:
            break
        k = (k + 1) % n
    v = [path.v[k] for k in idx]
    ii = [path.i[k] for k in idx]
    oo = [path.o[k] for k in idx]
    chain = [v[-1]] + list(extra) + [v[0]]
    sm = smooth(chain, closed=False, t=t)
    oo[-1] = sm.o[0]
    ii[0] = sm.i[-1]
    ev = [(p[0], p[1]) for p in extra]
    return Path(v + ev, ii + sm.i[1:-1], oo + sm.o[1:-1], True)


def open_part(path, i0, i1):
    n = len(path.v)
    idx = []
    k = i0
    while True:
        idx.append(k)
        if k == i1:
            break
        k = (k + 1) % n
    v = [path.v[k] for k in idx]
    ii = [path.i[k] for k in idx]
    oo = [path.o[k] for k in idx]
    ii[0] = (0, 0)
    oo[-1] = (0, 0)
    return Path(v, ii, oo, False)


def heart(cx, cy, s):
    """Heart path, s ~ half-width."""
    k = s / 16.0
    pts = [(0, -5, 0.0), (6, -11), (14, -10), (16.5, -3), (12, 6), (0, 15, 0.0), (-12, 6), (-16.5, -3), (-14, -10),
           (-6, -11)]
    return smooth([(cx + x * k, cy + y * k, *r) for x, y, *r in pts])


def star(cx, cy, r, inner=0.48, n=5, rot=-90, rnd=0.25):
    pts = []
    for k in range(n * 2):
        a = math.radians(rot + k * 180 / n)
        rr = r if k % 2 == 0 else r * inner
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a), rnd if k % 2 == 0 else 0.5))
    return smooth(pts, t=0.6)


def sparkle(cx, cy, r):
    pts = []
    for k in range(8):
        a = math.radians(-90 + k * 45)
        rr = r if k % 2 == 0 else r * 0.28
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a), 0.05 if k % 2 == 0 else 1.2))
    return smooth(pts)


def drop(cx, cy, s):
    """teardrop pointing up; s = radius of round part"""
    return smooth([(cx, cy - s * 1.9, 0.0), (cx + s * 0.75, cy - s * 0.7), (cx + s, cy + s * 0.25),
                   (cx, cy + s), (cx - s, cy + s * 0.25), (cx - s * 0.75, cy - s * 0.7)])


def leafshape(cx, cy, L, w, ang):
    p = smooth([(-L / 2, 0, 0.0), (-L * 0.15, -w), (L * 0.25, -w * 0.85), (L / 2, 0, 0.0), (L * 0.25, w * 0.85),
                (-L * 0.15, w)])
    return p.rot(ang, 0, 0).move(cx, cy)


def ell_pts(cx, cy, rx, ry, a0, a1, n):
    out = []
    for k in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        out.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return out
