"""Posable vector dragon rendered with Cairo.

Original design "Ember": a four-legged obsidian dragon with ember-orange belly
plates, crimson bat-wing membranes, swept bone horns and glowing amber eyes.
Facing right in local space; left-facing sprites are mirrored copies.
"""
import math
import cairo

W, H = 320, 200          # frame size (1x)
GROUND = 188             # ground line (feet rest here)

# ---------------------------------------------------------------- palette
def hexc(h, a=1.0):
    h = h.lstrip('#')
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)

def shade(c, k):
    return (c[0] * k, c[1] * k, c[2] * k, c[3])

def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(4))

SKIN      = hexc('#2d3240')
SKIN_HI   = hexc('#454c5e')
OUTLINE   = hexc('#0f1117')
BELLY     = hexc('#c9622a')
BELLY_HOT = hexc('#ffb347')
BELLY_LN  = hexc('#8a3a17')
HORN      = hexc('#dccba6')
HORN_SH   = hexc('#a8936b')
MEMBRANE  = hexc('#7d1d24')
MEMB_VEIN = hexc('#4e0f15')
MOUTH     = hexc('#4a0b10')
TONGUE    = hexc('#b8323f')
TEETH     = hexc('#f4eedf')
EYE       = hexc('#ffb21f')
FAR       = 0.62          # darkening for far-side limbs

# ---------------------------------------------------------------- geometry
def rot(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)

def add(a, b): return (a[0] + b[0], a[1] + b[1])
def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def mul(a, k): return (a[0] * k, a[1] * k)
def lerp(a, b, t): return a + (b - a) * t
def lerp2(a, b, t): return (lerp(a[0], b[0], t), lerp(a[1], b[1], t))
def length(v): return math.hypot(v[0], v[1])
def norm(v):
    l = length(v) or 1.0
    return (v[0] / l, v[1] / l)
def dirv(a): return (math.cos(a), math.sin(a))
def D(deg): return math.radians(deg)


def catmull(ctx, pts, closed=False, tension=1.0):
    """Smooth path through points (Catmull-Rom converted to cubic Bezier)."""
    n = len(pts)
    if n < 2:
        return
    ctx.move_to(*pts[0])
    rng = n if closed else n - 1
    for i in range(rng):
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[0]
        p1 = pts[i % n]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else pts[-1]
        c1 = add(p1, mul(sub(p2, p0), tension / 6))
        c2 = sub(p2, mul(sub(p3, p1), tension / 6))
        ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    if closed:
        ctx.close_path()


def fill_stroke(ctx, fill, line=OUTLINE, lw=1.4):
    ctx.set_source_rgba(*fill)
    ctx.fill_preserve()
    ctx.set_source_rgba(*line)
    ctx.set_line_width(lw)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.stroke()


def tapered(ctx, pts, widths, fill, top=1, spikes=0, spike_col=None, belly=None,
            belly_frac=0.42, cap=True, lw=1.4):
    """Draw a tapered tube along pts. top=+1/-1 picks which side is the back."""
    n = len(pts)
    left, right, normals = [], [], []
    for i in range(n):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, n - 1)]
        t = norm(sub(b, a))
        nn = (-t[1], t[0])
        normals.append(nn)
        left.append(add(pts[i], mul(nn, widths[i] / 2)))
        right.append(sub(pts[i], mul(nn, widths[i] / 2)))
    # dorsal spikes (drawn first so the tube covers their base)
    if spikes:
        ctx.save()
        for i in range(1, n - 1, spikes):
            nn = mul(normals[i], -top)
            t = norm(sub(pts[min(i + 1, n - 1)], pts[i - 1]))
            base = add(pts[i], mul(nn, widths[i] * 0.38))
            h = max(2.0, widths[i] * 0.55)
            hb = max(1.6, widths[i] * 0.28)
            tip = add(add(base, mul(nn, h)), mul(t, -h * 0.55 * (1 if top > 0 else 1)))
            ctx.move_to(*add(base, mul(t, hb)))
            ctx.line_to(*tip)
            ctx.line_to(*sub(base, mul(t, hb)))
            ctx.close_path()
            fill_stroke(ctx, spike_col or shade(fill, 0.8), lw=1.0)
        ctx.restore()
    outline = list(left) + list(reversed(right))
    catmull(ctx, outline, closed=True, tension=0.9)
    fill_stroke(ctx, fill, lw=lw)
    if belly is not None:
        # belly strip on the underside
        side = top  # underside is +top normal direction
        outer = [add(pts[i], mul(normals[i], side * widths[i] / 2 * 0.92)) for i in range(n)]
        inner = [add(pts[i], mul(normals[i], side * widths[i] / 2 * (1 - 2 * belly_frac))) for i in range(n)]
        catmull(ctx, outer + list(reversed(inner)), closed=True, tension=0.9)
        ctx.set_source_rgba(*belly)
        ctx.fill()
        ctx.set_source_rgba(*BELLY_LN)
        ctx.set_line_width(0.8)
        for i in range(1, n - 1, 1):
            ctx.move_to(*outer[i])
            ctx.line_to(*inner[i])
        ctx.stroke()
        # re-stroke silhouette edge so belly sits inside the outline
        catmull(ctx, outline, closed=True, tension=0.9)
        ctx.set_source_rgba(*OUTLINE)
        ctx.set_line_width(lw)
        ctx.stroke()
    return left, right, normals


# ---------------------------------------------------------------- pose
def wing_folded():
    return dict(t1=-150, t2=-52, phi=186, delta=21, fs=0.7, arm=0.57)

def default_pose():
    bx, by = 118, 150
    return dict(
        bx=bx, by=by, br=0.0, breath=0.0,
        head_dx=47, head_dy=-34, head_r=0.12, jaw=0.0, eye=1.0, neck_bend=0.0,
        tail_lift=0.35, tail_droop=0.28, tail_amp=0.0, tail_phase=0.0,
        wn=wing_folded(), wf=dict(wing_folded(), t1=-140, t2=-60, phi=192),
        feet=dict(bn=(bx - 15, 185), bf=(bx - 8, 184), fn=(bx + 21, 185), ff=(bx + 28, 184)),
        foot_tilt=dict(bn=0, bf=0, fn=0, ff=0),
        fire=0.0, fire_len=104, fire_t=0.0, fire_glow=0.0, belly_glow=0.0,
        smoke=None,   # list of (x, y, r, alpha) in head-local space
        shadow=1.0, shadow_k=1.0,
        tongue=0.0,   # tongue hanging out of the mouth 0..1
        eye_happy=0.0,  # 1 = closed happy ^ eyes
        pupil=0.0,    # 0 slit .. 1 big round (curious / cute)
        xf=None,      # whole-body transform: dict(px, py, rot, sx, sy, dx, dy)
        clamp=True,   # keep tail above the ground
        fx=None,      # list of effect dicts drawn on top (world space)
        brow=0.0,     # brow raise (+) / furrow (-)
    )


BODY_LOCAL = [(31, 1), (26, -12), (12, -18), (-4, -19), (-22, -15), (-34, -6),
              (-31, 7), (-14, 15), (6, 16), (24, 12)]


def to_world(P, p):
    q = (p[0], p[1] * (1 + P['breath'] * 0.06))
    q = rot(q, P['br'])
    return (q[0] + P['bx'], q[1] + P['by'])


# ---------------------------------------------------------------- parts
def ik(hip, foot, l1, l2, bend):
    d = sub(foot, hip)
    dist = length(d)
    dist = min(max(dist, abs(l1 - l2) + 0.5), l1 + l2 - 0.05)
    base = math.atan2(d[1], d[0])
    a = math.acos(max(-1, min(1, (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist))))
    knee = add(hip, mul(dirv(base + bend * a), l1))
    end = add(knee, mul(norm(sub(foot, knee)), l2))
    return knee, end


def draw_leg(ctx, P, key, hip_local, l1, l2, bend, w_hip, back, far):
    hip = to_world(P, hip_local)
    knee, ankle = ik(hip, P['feet'][key], l1, l2, bend)
    k = FAR if far else 1.0
    col = shade(SKIN, k)
    # thigh
    tapered(ctx, [hip, lerp2(hip, knee, 0.45), knee], [w_hip, w_hip * 0.95, w_hip * 0.55],
            col, lw=1.3)
    # shin
    tapered(ctx, [knee, lerp2(knee, ankle, 0.5), ankle], [w_hip * 0.5, w_hip * 0.4, w_hip * 0.36],
            col, lw=1.3)
    # foot with three claws
    tilt = P['foot_tilt'][key]
    ctx.save()
    ctx.translate(*ankle)
    ctx.rotate(tilt)
    s = 1.25 if back else 1.12
    ctx.scale(s, s)
    for i, (cx, cy) in enumerate([(9, 2.2), (7.5, 2.8), (5.5, 3.2)]):
        ctx.move_to(cx - 2, cy - 1.8)
        ctx.curve_to(cx + 1.5, cy - 2.2, cx + 3.6, cy - 0.6, cx + 3.4, cy + 1.0)
        ctx.curve_to(cx + 2.0, cy - 0.2, cx, cy + 0.2, cx - 1.6, cy + 0.6)
        ctx.close_path()
        fill_stroke(ctx, shade(HORN, k), lw=0.8)
    catmull(ctx, [(-3, -3.5), (3, -3.2), (9, -0.6), (10, 2.4), (2, 3.2), (-4, 2.2)],
            closed=True)
    fill_stroke(ctx, col, lw=1.2)
    ctx.restore()


def wing_points(P, w, root_local):
    S = to_world(P, root_local)
    t1, t2 = D(w['t1']) + P['br'], D(w['t2']) + P['br']
    arm = w.get('arm', 1.0)
    E = add(S, mul(dirv(t1), 24 * arm))
    Wr = add(E, mul(dirv(t2), 32 * arm))
    tips = []
    lens = [58, 50, 40]
    for i in range(3):
        a = D(w['phi'] - i * w['delta']) + P['br']
        tips.append(add(Wr, mul(dirv(a), lens[i] * w['fs'])))
    B = to_world(P, (-20, -12))
    return S, E, Wr, tips, B


def draw_wing(ctx, P, w, root_local, far):
    S, E, Wr, tips, B = wing_points(P, w, root_local)
    k = FAR if far else 1.0
    # membrane
    chain = [Wr] + tips + [B]
    ctx.move_to(*S)
    ctx.line_to(*E)
    ctx.line_to(*Wr)
    ctx.line_to(*tips[0])
    prev = tips[0]
    for nxt in tips[1:] + [B]:
        mid = lerp2(prev, nxt, 0.5)
        ctrl = lerp2(mid, Wr, 0.22)
        ctx.curve_to(*lerp2(prev, ctrl, 0.66), *lerp2(nxt, ctrl, 0.66), *nxt)
        prev = nxt
    ctx.line_to(*S)
    ctx.close_path()
    grad = cairo.LinearGradient(Wr[0], Wr[1], tips[1][0], tips[1][1])
    m = shade(MEMBRANE, k)
    grad.add_color_stop_rgba(0, *shade(m, 0.85))
    grad.add_color_stop_rgba(1, *mix(m, hexc('#c0392b'), 0.35))
    ctx.set_source(grad)
    ctx.fill_preserve()
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.2)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.stroke()
    # veins
    ctx.set_source_rgba(*shade(MEMB_VEIN, k))
    ctx.set_line_width(0.9)
    for t in tips:
        ctx.move_to(*Wr)
        ctx.line_to(*t)
    ctx.move_to(*E)
    ctx.line_to(*lerp2(B, tips[2], 0.5))
    ctx.stroke()
    # finger bones
    bone = shade(SKIN_HI, k)
    for t in tips:
        tapered(ctx, [Wr, lerp2(Wr, t, 0.5), t], [3.0, 2.0, 1.0], bone, lw=0.9, cap=False)
    # arm bones
    tapered(ctx, [S, lerp2(S, E, 0.5), E], [7, 5.5, 4.5], shade(SKIN, k), lw=1.2)
    tapered(ctx, [E, lerp2(E, Wr, 0.5), Wr], [4.5, 3.6, 3.2], shade(SKIN, k), lw=1.2)
    # thumb claw at wrist
    a = math.atan2(Wr[1] - E[1], Wr[0] - E[0])
    ctx.save()
    ctx.translate(*Wr)
    ctx.rotate(a)
    ctx.move_to(-1, -1.8)
    ctx.curve_to(3, -3, 6, -2, 7, 1)
    ctx.curve_to(4, -0.2, 1.5, 0.6, -1, 1.8)
    ctx.close_path()
    fill_stroke(ctx, shade(HORN, k), lw=0.8)
    ctx.restore()


def tail_points(P):
    N = 16
    seg = 4.4
    p = to_world(P, (-29, -5))
    a = math.pi + P['br'] + P['tail_lift']
    pts, ws = [p], [15.0]
    for i in range(1, N + 1):
        u = i / N
        k = -P['tail_droop'] * (1 - u * 1.6) \
            + 0.35 * P['tail_amp'] * math.sin(P['tail_phase'] - u * 3.2) * (0.35 + u)
        a += k
        p = add(p, mul(dirv(a), seg))
        wi = 15.0 * (1 - u) ** 0.9 + 2.6
        floor = GROUND - wi * 0.5 - (6 if u > 0.9 else 0)
        if P['clamp'] and p[1] > floor:                     # rest on the ground instead of sinking
            p = (p[0], floor)
            prev = pts[-1]
            a = math.atan2(p[1] - prev[1], p[0] - prev[0])
        pts.append(p)
        ws.append(15.0 * (1 - u) ** 0.9 + 2.6)
    return pts, ws, a


def draw_tail(ctx, P):
    pts, ws, a = tail_points(P)
    tapered(ctx, pts, ws, SKIN, top=-1, spikes=2, spike_col=shade(SKIN_HI, 0.9),
            belly=BELLY, belly_frac=0.33)
    # spade tip
    tip = pts[-1]
    d = dirv(a)
    n = (-d[1], d[0])
    p1 = add(tip, mul(d, -3))
    p2 = add(add(tip, mul(d, 6)), mul(n, 5.5))
    p3 = add(tip, mul(d, 13))
    p4 = add(add(tip, mul(d, 6)), mul(n, -5.5))
    catmull(ctx, [p1, p2, p3, p4], closed=True, tension=0.6)
    fill_stroke(ctx, shade(SKIN_HI, 0.95), lw=1.1)


def neck_points(P):
    P0 = to_world(P, (22, -9))
    Hd = (P['bx'] + P['head_dx'], P['by'] + P['head_dy'])
    a0 = P['br'] - 1.05 + P['neck_bend'] * 0.4
    P1 = add(P0, mul(dirv(a0), 16 + P['neck_bend'] * 6))
    ae = P['head_r'] - 0.75
    P2 = sub(Hd, mul(dirv(ae), 13))
    pts = []
    for i in range(11):
        t = i / 10
        mt = 1 - t
        x = mt**3 * P0[0] + 3 * mt * mt * t * P1[0] + 3 * mt * t * t * P2[0] + t**3 * Hd[0]
        y = mt**3 * P0[1] + 3 * mt * mt * t * P1[1] + 3 * mt * t * t * P2[1] + t**3 * Hd[1]
        pts.append((x, y))
    ws = [lerp(19, 11.5, (i / 10) ** 0.8) for i in range(11)]
    return pts, ws


def draw_neck(ctx, P):
    pts, ws = neck_points(P)
    tapered(ctx, pts, ws, SKIN, top=1, spikes=2, spike_col=shade(SKIN_HI, 0.9),
            belly=mix(BELLY, BELLY_HOT, P['belly_glow']), belly_frac=0.34)


def draw_body(ctx, P):
    pts = [to_world(P, p) for p in BODY_LOCAL]
    # back spikes
    for lp in [(-24, -14), (-12, -18), (0, -19), (12, -17)]:
        b = to_world(P, lp)
        up = rot((0, -1), P['br'])
        fw = rot((1, 0), P['br'])
        ctx.move_to(*add(b, mul(fw, 4)))
        ctx.line_to(*add(add(b, mul(up, 8)), mul(fw, -4)))
        ctx.line_to(*add(b, mul(fw, -4)))
        ctx.close_path()
        fill_stroke(ctx, shade(SKIN_HI, 0.9), lw=1.0)
    catmull(ctx, pts, closed=True)
    ctx.set_source_rgba(*SKIN)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    # subtle top highlight
    c = to_world(P, (0, -14))
    g = cairo.RadialGradient(c[0], c[1], 2, c[0], c[1], 28)
    g.add_color_stop_rgba(0, *SKIN_HI)
    g.add_color_stop_rgba(1, *mix(SKIN_HI, SKIN, 1.0))
    ctx.set_source(g)
    ctx.paint_with_alpha(0.55)
    # belly plates
    bcol = mix(BELLY, BELLY_HOT, P['belly_glow'])
    bl = [to_world(P, p) for p in [(30, 3), (20, 4), (4, 7), (-14, 6), (-32, 2),
                                     (-32, 20), (0, 24), (30, 20)]]
    catmull(ctx, bl, closed=True, tension=0.5)
    ctx.set_source_rgba(*bcol)
    ctx.fill()
    ctx.set_source_rgba(*BELLY_LN)
    ctx.set_line_width(0.8)
    for x in range(-26, 30, 7):
        a = to_world(P, (x, 4))
        b = to_world(P, (x - 2, 22))
        ctx.move_to(*a)
        ctx.line_to(*b)
    ctx.stroke()
    if P['belly_glow'] > 0:
        c = to_world(P, (12, 10))
        g = cairo.RadialGradient(c[0], c[1], 1, c[0], c[1], 26)
        g.add_color_stop_rgba(0, 1, 0.85, 0.4, 0.75 * P['belly_glow'])
        g.add_color_stop_rgba(1, 1, 0.5, 0.1, 0)
        ctx.set_source(g)
        ctx.paint()
    ctx.restore()
    catmull(ctx, pts, closed=True)
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.5)
    ctx.stroke()


HEAD_UPPER = [(-7, -1), (-3, -9), (7, -12), (16, -10), (26, -7), (34, -4), (38.5, 0.5),
              (36, 4), (22, 4.2), (8, 5), (-3, 6.5)]
JAW = [(1, 3), (20, 4.4), (33, 5.2), (34, 8), (27, 10.5), (13, 11.5), (0, 10.5)]
JAW_PIVOT = (2, 5)


def head_xform(P):
    Hd = (P['bx'] + P['head_dx'], P['by'] + P['head_dy'])
    return Hd, P['head_r']


def mouth_point(P):
    Hd, r = head_xform(P)
    ja = P['jaw'] * 0.62
    tipj = add(JAW_PIVOT, rot(sub((27, 6), JAW_PIVOT), ja))
    tipu = (29, 4)
    m = lerp2(tipu, tipj, 0.5)
    return add(Hd, rot(m, r)), r + ja * 0.45


def draw_head(ctx, P):
    Hd, r = head_xform(P)
    ctx.save()
    ctx.translate(*Hd)
    ctx.rotate(r)
    ja = P['jaw'] * 0.62
    # far horn
    catmull(ctx, [(9, -10), (-4, -15), (-14, -22), (-17, -24), (-12, -18), (-1, -10), (6, -6)],
            closed=True, tension=0.7)
    fill_stroke(ctx, shade(HORN, FAR), lw=1.0)
    # jaw frill spikes
    for (bx_, by_), (tx, ty) in [((-4, 6), (-13, 12)), ((2, 9), (-6, 16)), ((-6, 1), (-15, 4))]:
        ctx.move_to(bx_ + 3, by_ - 2)
        ctx.line_to(tx, ty)
        ctx.line_to(bx_ - 1, by_ + 3)
        ctx.close_path()
        fill_stroke(ctx, shade(SKIN_HI, 0.85), lw=1.0)
    # mouth interior (visible when jaw opens)
    if ja > 0.01:
        jaw_pts = [add(JAW_PIVOT, rot(sub(p, JAW_PIVOT), ja)) for p in JAW]
        ctx.move_to(*JAW_PIVOT)
        ctx.line_to(8, 5)
        ctx.line_to(22, 4.2)
        ctx.line_to(36, 4)
        ctx.line_to(*jaw_pts[3])
        ctx.line_to(*jaw_pts[1])
        ctx.close_path()
        ctx.set_source_rgba(*MOUTH)
        ctx.fill()
        # tongue
        tp = add(JAW_PIVOT, rot(sub((24, 6.5), JAW_PIVOT), ja * 0.75))
        ctx.move_to(4, 6)
        ctx.curve_to(12, 6 + ja * 4, tp[0] - 4, tp[1], tp[0], tp[1])
        ctx.set_source_rgba(*TONGUE)
        ctx.set_line_width(2.4)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.stroke()
    # upper teeth
    for x in [12, 18, 24, 30, 34]:
        ctx.move_to(x - 1.4, 4)
        ctx.line_to(x, 7.2 if x in (18, 30) else 6.2)
        ctx.line_to(x + 1.4, 4)
        ctx.close_path()
        ctx.set_source_rgba(*TEETH)
        ctx.fill()
    # lower jaw
    ctx.save()
    ctx.translate(*JAW_PIVOT)
    ctx.rotate(ja)
    ctx.translate(-JAW_PIVOT[0], -JAW_PIVOT[1])
    if ja > 0.01:
        for x in [14, 21, 28, 32]:
            ctx.move_to(x - 1.3, 5)
            ctx.line_to(x, 1.6 if x in (21,) else 2.6)
            ctx.line_to(x + 1.3, 5)
            ctx.close_path()
            ctx.set_source_rgba(*TEETH)
            ctx.fill()
    catmull(ctx, JAW, closed=True, tension=0.8)
    ctx.set_source_rgba(*SKIN)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    catmull(ctx, [(2, 8.5), (20, 8.2), (33, 7.4), (33, 13), (2, 13)], closed=True, tension=0.5)
    ctx.set_source_rgba(*mix(BELLY, BELLY_HOT, P['belly_glow'] * 0.5))
    ctx.fill()
    ctx.restore()
    catmull(ctx, JAW, closed=True, tension=0.8)
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.3)
    ctx.stroke()
    ctx.restore()
    if P['tongue'] > 0:
        tt = P['tongue']
        tip = add(JAW_PIVOT, rot(sub((33 + 5 * tt, 8 + 7 * tt), JAW_PIVOT), ja * 0.6))
        base = add(JAW_PIVOT, rot(sub((24, 6), JAW_PIVOT), ja * 0.6))
        ctx.move_to(*base)
        ctx.curve_to(base[0] + 6, base[1] - 1, tip[0] + 1, tip[1] - 5, tip[0], tip[1])
        ctx.curve_to(tip[0] - 3, tip[1] + 1, tip[0] - 6, tip[1] - 3, base[0] + 3, base[1] + 3)
        ctx.close_path()
        fill_stroke(ctx, TONGUE, lw=0.9)
    # skull / upper jaw
    catmull(ctx, HEAD_UPPER, closed=True, tension=0.85)
    ctx.set_source_rgba(*SKIN)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    g = cairo.RadialGradient(14, -10, 1, 14, -10, 20)
    g.add_color_stop_rgba(0, *SKIN_HI)
    g.add_color_stop_rgba(1, *SKIN)
    ctx.set_source(g)
    ctx.paint_with_alpha(0.7)
    ctx.restore()
    catmull(ctx, HEAD_UPPER, closed=True, tension=0.85)
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.4)
    ctx.stroke()
    # snout ridge bumps
    for x, y in [(22, -7.6), (28, -5.8)]:
        ctx.arc(x, y, 1.3, 0, 2 * math.pi)
        ctx.set_source_rgba(*SKIN_HI)
        ctx.fill()
    # nostril
    ctx.save()
    ctx.translate(34.2, -1.6)
    ctx.rotate(-0.4)
    ctx.scale(1.8, 0.9)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(*OUTLINE)
    ctx.fill()
    if P['fire'] > 0 or P['fire_glow'] > 0:
        gl = max(P['fire'], P['fire_glow'])
        g = cairo.RadialGradient(34, -1.6, 0, 34, -1.6, 4)
        g.add_color_stop_rgba(0, 1, 0.6, 0.15, 0.9 * gl)
        g.add_color_stop_rgba(1, 1, 0.4, 0.1, 0)
        ctx.set_source(g)
        ctx.arc(34, -1.6, 4, 0, 2 * math.pi)
        ctx.fill()
    # eye
    ex, ey = 16, -4.2
    if P['eye_happy'] > 0.5:
        ctx.move_to(ex - 4, ey + 1.2)
        ctx.curve_to(ex - 1.5, ey - 2.6, ex + 1.5, ey - 2.6, ex + 4, ey + 1.0)
        ctx.set_source_rgba(*OUTLINE)
        ctx.set_line_width(1.5)
        ctx.stroke()
    elif P['eye'] > 0.15:
        g = cairo.RadialGradient(ex, ey, 0, ex, ey, 7)
        g.add_color_stop_rgba(0, 1, 0.75, 0.2, 0.55)
        g.add_color_stop_rgba(1, 1, 0.6, 0.1, 0)
        ctx.set_source(g)
        ctx.arc(ex, ey, 7, 0, 2 * math.pi)
        ctx.fill()
        h = 2.6 * P['eye']
        ctx.move_to(ex - 4.2, ey + 0.4)
        ctx.curve_to(ex - 2, ey - h, ex + 2.5, ey - h, ex + 4.2, ey - 0.4)
        ctx.curve_to(ex + 2, ey + h * 0.8, ex - 2, ey + h * 0.8, ex - 4.2, ey + 0.4)
        ctx.close_path()
        ctx.set_source_rgba(*EYE)
        ctx.fill_preserve()
        ctx.set_source_rgba(*OUTLINE)
        ctx.set_line_width(0.9)
        ctx.stroke()
        # slit pupil
        ctx.save()
        ctx.translate(ex + 0.6, ey)
        pr = P['pupil']
        ctx.scale(0.7 + 1.3 * pr, h * (0.42 + 0.12 * pr))
        ctx.arc(0, 0, 1.4, 0, 2 * math.pi)
        ctx.restore()
        ctx.set_source_rgba(0.05, 0.03, 0.02, 1)
        ctx.fill()
        ctx.arc(ex + 1.8, ey - 0.9, 0.6, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 0.9, 0.9)
        ctx.fill()
    else:
        ctx.move_to(ex - 4, ey + 0.2)
        ctx.curve_to(ex - 1.5, ey + 1.8, ex + 1.5, ey + 1.8, ex + 4, ey)
        ctx.set_source_rgba(*OUTLINE)
        ctx.set_line_width(1.2)
        ctx.stroke()
    # heavy brow ridge
    bu = P['brow'] * 1.6
    ctx.move_to(ex - 6, ey - 2.8 - bu * 0.4)
    ctx.curve_to(ex - 2, ey - 6.2 - bu, ex + 3, ey - 5.6 - bu, ex + 6.5, ey - 2.4 - bu * 0.6)
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.8)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.stroke()
    # near horn
    catmull(ctx, [(6, -8), (-6, -13), (-17, -19), (-22, -20), (-16, -14), (-4, -6), (3, -3)],
            closed=True, tension=0.7)
    ctx.set_source_rgba(*HORN)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    ctx.set_source_rgba(*HORN_SH)
    ctx.set_line_width(0.8)
    for i in range(4):
        x = 2 - i * 5
        ctx.move_to(x, -14)
        ctx.line_to(x + 2, -2)
    ctx.stroke()
    ctx.restore()
    catmull(ctx, [(6, -8), (-6, -13), (-17, -19), (-22, -20), (-16, -14), (-4, -6), (3, -3)],
            closed=True, tension=0.7)
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.1)
    ctx.stroke()
    # small horn nub on snout
    ctx.move_to(27, -6.5)
    ctx.line_to(29.5, -10.5)
    ctx.line_to(31, -5.2)
    ctx.close_path()
    fill_stroke(ctx, HORN, lw=0.9)
    # smoke puffs (head-local)
    if P['smoke']:
        for (sx, sy, sr, sa) in P['smoke']:
            ctx.arc(sx, sy, sr, 0, 2 * math.pi)
            ctx.set_source_rgba(0.55, 0.55, 0.6, sa)
            ctx.fill()
    ctx.restore()


def draw_fire(ctx, P):
    inten = P['fire']
    if inten <= 0:
        return
    m, a = mouth_point(P)
    L = P['fire_len'] * inten
    d = dirv(a)
    n = (-d[1], d[0])
    T = 2 * math.pi * P['fire_t']        # 0..1 loops seamlessly
    parts = []
    N = 34
    for i in range(N):
        t = (i + 0.5) / N
        spread = t * L * 0.15
        for j in (-1, 0, 1):
            wob = 4.5 * t * math.sin(t * 9 - T + j * 1.3) + 2.5 * t * math.sin(t * 19 + 2 * T + i * 0.7 + j)
            lat = j * spread * (0.75 + 0.25 * math.sin(t * 13 - 2 * T + j * 2)) + wob
            taper = 1.0 if t < 0.78 else max(0.35, 1 - (t - 0.78) / 0.22 * 0.65)
            rad = (1.3 + t * 9.5) * taper * (1 + 0.18 * math.sin(t * 23 + 3 * T + i + j * 2))
            if j != 0:
                rad *= 0.78
            p = add(add(m, mul(d, t * L + (0 if j == 0 else -2))), mul(n, lat))
            parts.append((t, p, rad, j))
    # soft glow
    c = add(m, mul(d, L * 0.45))
    g = cairo.RadialGradient(c[0], c[1], 0, c[0], c[1], L * 0.6 + 8)
    g.add_color_stop_rgba(0, 1, 0.6, 0.2, 0.28 * inten)
    g.add_color_stop_rgba(1, 1, 0.35, 0.05, 0)
    ctx.set_source(g)
    ctx.arc(c[0], c[1], L * 0.6 + 8, 0, 2 * math.pi)
    ctx.fill()
    # smoke wisps curling up off the end of the flame
    for k in range(5):
        u = ((k / 5) + P['fire_t']) % 1.0
        p = add(add(m, mul(d, L * (0.82 + 0.16 * u))), (0, -u * 16 - 4))
        p = add(p, mul(n, 4 * math.sin(k * 2.1 + T)))
        ctx.arc(p[0], p[1], 3 + u * 6, 0, 2 * math.pi)
        ctx.set_source_rgba(0.32, 0.3, 0.32, 0.28 * (1 - u) * inten)
        ctx.fill()
    layers = [
        (hexc('#a8191a', 0.9), 1.18, 0.0, 1.01),
        (hexc('#ef4f1a', 0.92), 0.95, 0.0, 0.95),
        (hexc('#ff9418', 0.95), 0.72, 0.0, 0.84),
        (hexc('#ffd447', 0.95), 0.5, 0.0, 0.66),
        (hexc('#fff7d6', 0.95), 0.3, 0.0, 0.40),
    ]
    for col, k, t0, t1 in layers:
        ctx.set_source_rgba(*col)
        for t, p, rad, j in parts:
            if t0 <= t <= t1 and (j == 0 or k >= 0.72):
                ctx.new_sub_path()
                ctx.arc(p[0], p[1], rad * k, 0, 2 * math.pi)
        ctx.fill()
    # embers
    for k in range(9):
        u = ((k * 0.37) + P['fire_t']) % 1.0
        p = add(add(m, mul(d, L * (0.35 + 0.7 * u))), mul(n, 14 * math.sin(k * 3.7) * (0.4 + u)))
        p = (p[0], p[1] - u * 8)
        ctx.arc(p[0], p[1], 1.1 * (1 - u * 0.5), 0, 2 * math.pi)
        ctx.set_source_rgba(1, 0.85, 0.4, 0.9 * (1 - u) * inten)
        ctx.fill()


def draw_shadow(ctx, P):
    if P['shadow'] <= 0:
        return
    ctx.save()
    ctx.translate(P['bx'] + 4, GROUND + 1)
    ctx.scale(52 * P['shadow_k'], 4.5 * max(0.4, P['shadow_k']))
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(0, 0, 0, 0.22 * P['shadow'])
    ctx.fill()


def render(P, scale=1, ctx=None):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W * scale), int(H * scale))
    ctx = cairo.Context(surf)
    ctx.scale(scale, scale)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    draw_shadow(ctx, P)
    xf = P['xf']
    if xf:
        ctx.save()
        ctx.translate(xf.get('px', P['bx']) + xf.get('dx', 0), xf.get('py', P['by']) + xf.get('dy', 0))
        ctx.rotate(xf.get('rot', 0))
        ctx.scale(xf.get('sx', 1), xf.get('sy', 1))
        ctx.translate(-xf.get('px', P['bx']), -xf.get('py', P['by']))
    draw_wing(ctx, P, P['wf'], (9, -17), far=True)
    draw_leg(ctx, P, 'bf', (-15, 3), 17, 18, -1, 15, back=True, far=True)
    draw_leg(ctx, P, 'ff', (19, 5), 15, 16, 1, 11, back=False, far=True)
    draw_tail(ctx, P)
    draw_body(ctx, P)
    draw_neck(ctx, P)
    draw_head(ctx, P)
    draw_fire(ctx, P)
    draw_leg(ctx, P, 'bn', (-19, 5), 17, 18, -1, 21, back=True, far=False)
    draw_leg(ctx, P, 'fn', (16, 7), 15, 16, 1, 14, back=False, far=False)
    draw_wing(ctx, P, P['wn'], (4, -16), far=False)
    if xf:
        ctx.restore()
    draw_fx(ctx, P['fx'])
    return surf


# ---------------------------------------------------------------- effects
def draw_heart(ctx, x, y, s, a):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    ctx.move_to(0, 3)
    ctx.curve_to(-6, -1, -4, -6, 0, -3)
    ctx.curve_to(4, -6, 6, -1, 0, 3)
    ctx.close_path()
    ctx.restore()
    ctx.set_source_rgba(0.93, 0.27, 0.36, a)
    ctx.fill_preserve()
    ctx.set_source_rgba(0.45, 0.06, 0.12, a)
    ctx.set_line_width(0.9)
    ctx.stroke()


def draw_fireball(ctx, x, y, r, t, a=1.0, dirx=1.0):
    T = 2 * math.pi * t
    # trail
    for i in range(7):
        u = i / 7
        px = x - dirx * (r * 0.9 + u * r * 3.2)
        py = y + math.sin(T + i) * r * 0.25 * u
        ctx.arc(px, py, r * (0.8 - u * 0.6), 0, 2 * math.pi)
        ctx.set_source_rgba(1, 0.45 - 0.2 * u, 0.1, a * 0.75 * (1 - u))
        ctx.fill()
    g = cairo.RadialGradient(x, y, 0, x, y, r * 2.4)
    g.add_color_stop_rgba(0, 1, 0.7, 0.3, 0.5 * a)
    g.add_color_stop_rgba(1, 1, 0.4, 0.1, 0)
    ctx.set_source(g)
    ctx.arc(x, y, r * 2.4, 0, 2 * math.pi)
    ctx.fill()
    for k, col in [(1.0, (0.75, 0.12, 0.1)), (0.82, (0.95, 0.35, 0.1)), (0.62, (1, 0.62, 0.12)),
                   (0.42, (1, 0.86, 0.35)), (0.22, (1, 0.98, 0.85))]:
        ctx.new_path()
        n = 9
        pts = []
        for j in range(n):
            ang = j / n * 2 * math.pi
            rr = r * k * (1 + 0.13 * math.sin(3 * ang + T * 2 + k * 5))
            pts.append((x + math.cos(ang) * rr, y + math.sin(ang) * rr))
        catmull(ctx, pts, closed=True)
        ctx.set_source_rgba(*col, a)
        ctx.fill()


def draw_fx(ctx, fx):
    if not fx:
        return
    for e in fx:
        t = e['type']
        if t == 'drop':          # water droplet
            ctx.save()
            ctx.translate(e['x'], e['y'])
            ctx.rotate(e.get('ang', 0))
            ctx.scale(e['r'] * 1.5, e['r'])
            ctx.arc(0, 0, 1, 0, 2 * math.pi)
            ctx.restore()
            ctx.set_source_rgba(0.45, 0.75, 1.0, 0.85 * e.get('a', 1))
            ctx.fill_preserve()
            ctx.set_source_rgba(0.15, 0.35, 0.6, 0.8 * e.get('a', 1))
            ctx.set_line_width(0.6)
            ctx.stroke()
        elif t == 'dust':
            ctx.arc(e['x'], e['y'], e['r'], 0, 2 * math.pi)
            ctx.set_source_rgba(0.62, 0.58, 0.52, 0.5 * e.get('a', 1))
            ctx.fill()
        elif t == 'smoke':
            ctx.arc(e['x'], e['y'], e['r'], 0, 2 * math.pi)
            ctx.set_source_rgba(0.5, 0.5, 0.55, 0.5 * e.get('a', 1))
            ctx.fill()
        elif t == 'heart':
            draw_heart(ctx, e['x'], e['y'], e.get('s', 1), e.get('a', 1))
        elif t == 'fireball':
            draw_fireball(ctx, e['x'], e['y'], e['r'], e.get('t', 0), e.get('a', 1), e.get('dirx', 1))
        elif t == 'spark':
            ctx.arc(e['x'], e['y'], e.get('r', 1.2), 0, 2 * math.pi)
            ctx.set_source_rgba(1, 0.85, 0.4, e.get('a', 1))
            ctx.fill()
        elif t == 'swoosh':      # motion arc
            ctx.new_path()
            ctx.arc(e['x'], e['y'], e['r'], e['a0'], e['a1'])
            ctx.set_source_rgba(1, 1, 1, 0.55 * e.get('a', 1))
            ctx.set_line_width(e.get('w', 2))
            ctx.stroke()
