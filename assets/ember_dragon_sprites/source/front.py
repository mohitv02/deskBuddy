"""Front view of Ember (facing the viewer) - used for 'coming towards you' animations.

Local units: origin on the ground between the front feet, +x = viewer's right, y down.
World transform: translate(cx, gy) * scale(k)  (k grows as the dragon comes closer).
"""
import math
import cairo
from rig import (W, H, GROUND, SKIN, SKIN_HI, OUTLINE, BELLY, BELLY_HOT, BELLY_LN, HORN, HORN_SH,
                 MEMBRANE, MEMB_VEIN, MOUTH, TONGUE, TEETH, EYE, FAR, hexc, shade, mix, rot, add,
                 sub, mul, lerp, lerp2, length, norm, dirv, D, catmull, fill_stroke, tapered, ik,
                 draw_fx)


def front_pose():
    return dict(
        cx=W / 2, gy=GROUND, k=1.0,
        lift=0.0, lean=0.0, breath=0.0,
        head=(0.0, -54.0), head_r=0.0, head_s=1.12,
        jaw=0.0, eye=1.0, eye_happy=0.0, pupil=0.0, brow=0.0, tongue=0.0, look=(0.0, 0.0),
        squish=0.0,                       # snout pressed against the screen
        wing_open=[0.0, 0.0], wing_th=[30.0, 30.0], wing_fs=[1.0, 1.0],   # [right, left]
        feet=dict(r=(16.0, 0.0), l=(-16.0, 0.0), hr=(31.0, -3.0), hl=(-31.0, -3.0)),
        tail_x=0.8,                       # -1 .. 1, which side the tail sticks out
        fire=0.0, fire_t=0.0, fire_glow=0.0, belly_glow=0.0,
        shadow=1.0, shadow_gy=None, shadow_k=None,
        smoke=None, fx=None,
    )


def _chest_c(F):
    return (0.0, -40.0 - F['lift'])


def _R(F, p):
    return rot(p, F['lean'])


# ------------------------------------------------------------- parts
def draw_paw(ctx, p, s, k=1.0, scale=1.0):
    ctx.save()
    ctx.translate(*p)
    ctx.scale(scale * s, scale)
    col = shade(SKIN, k)
    catmull(ctx, [(-8, -6), (0, -8), (8, -6), (9, -1), (5, 1.5), (-5, 1.5), (-9, -1)], closed=True)
    fill_stroke(ctx, col, lw=1.2)
    for cx in (-5, 0, 5):
        ctx.move_to(cx - 2.2, -0.5)
        ctx.curve_to(cx - 1.5, 2.5, cx + 1.5, 2.5, cx + 2.2, -0.5)
        ctx.line_to(cx, 3.6)
        ctx.close_path()
        fill_stroke(ctx, shade(HORN, k), lw=0.7)
    ctx.restore()


def draw_tail(ctx, F):
    s = F['tail_x']
    if abs(s) < 0.08:
        return
    C = _chest_c(F)
    xs = [10, 26, 42, 54, 62, 67]
    ys = [-6, -4, -3, -7, -13, -19]
    pts = [_R(F, (C[0] + x * s, y - F['lift'] * 0.3)) for x, y in zip(xs, ys)]
    ws = [13, 11.5, 9.5, 7, 5, 3.4]
    top = 1 if s > 0 else -1
    tapered(ctx, pts, ws, SKIN, top=top, spikes=1, spike_col=shade(SKIN_HI, 0.9),
            belly=BELLY, belly_frac=0.3)
    tip = pts[-1]
    d = norm(sub(pts[-1], pts[-2]))
    n = (-d[1], d[0])
    catmull(ctx, [add(tip, mul(d, -3)), add(add(tip, mul(d, 5)), mul(n, 5)), add(tip, mul(d, 12)),
                  add(add(tip, mul(d, 5)), mul(n, -5))], closed=True, tension=0.6)
    fill_stroke(ctx, shade(SKIN_HI, 0.95), lw=1.1)


def wing_geom(F, i, s):
    C = _chest_c(F)
    S = (C[0] + 14 * s, C[1] - 10)
    o = F['wing_open'][i]
    th = D(F['wing_th'][i])
    fs = F['wing_fs'][i]
    # folded (draped down the flank)
    Wf = (S[0] + 18 * s, S[1] - 22)
    tips_f = [(S[0] + 30 * s, S[1] + 12), (S[0] + 28 * s, S[1] + 26), (S[0] + 22 * s, S[1] + 36)]
    Ef = (S[0] + 12 * s, S[1] - 8)
    # open (spread to the side)
    Wo = (S[0] + 44 * math.cos(th) * s, S[1] - 44 * math.sin(th))
    Eo = (S[0] + 24 * math.cos(th + 0.25) * s, S[1] - 24 * math.sin(th + 0.25))
    tips_o = []
    for off, L in zip((18, 52, 88), (58, 50, 40)):
        a = th - D(off)
        tips_o.append((Wo[0] + L * fs * math.cos(a) * s, Wo[1] - L * fs * math.sin(a)))
    Wr = lerp2(Wf, Wo, o)
    E = lerp2(Ef, Eo, o)
    tips = [lerp2(a, b, o) for a, b in zip(tips_f, tips_o)]
    B = (C[0] + 20 * s, C[1] + 12)
    f = lambda p: _R(F, p)
    return f(S), f(E), f(Wr), [f(t) for t in tips], f(B)


def draw_wing(ctx, F, i, s):
    S, E, Wr, tips, B = wing_geom(F, i, s)
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
    ctx.close_path()
    g = cairo.LinearGradient(Wr[0], Wr[1], tips[1][0], tips[1][1])
    g.add_color_stop_rgba(0, *shade(MEMBRANE, 0.8))
    g.add_color_stop_rgba(1, *mix(MEMBRANE, hexc('#c0392b'), 0.35))
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.2)
    ctx.stroke()
    ctx.set_source_rgba(*MEMB_VEIN)
    ctx.set_line_width(0.9)
    for t in tips:
        ctx.move_to(*Wr)
        ctx.line_to(*t)
    ctx.stroke()
    for t in tips:
        tapered(ctx, [Wr, lerp2(Wr, t, 0.5), t], [3.0, 2.0, 1.0], SKIN_HI, lw=0.9)
    tapered(ctx, [S, lerp2(S, E, 0.5), E], [8, 6.5, 5], SKIN, lw=1.2)
    tapered(ctx, [E, lerp2(E, Wr, 0.5), Wr], [5, 4, 3.4], SKIN, lw=1.2)
    a = math.atan2(Wr[1] - E[1], Wr[0] - E[0])
    ctx.save()
    ctx.translate(*Wr)
    ctx.rotate(a)
    ctx.move_to(-1, -1.8)
    ctx.curve_to(3, -3, 6, -2, 7, 1)
    ctx.curve_to(4, -0.2, 1.5, 0.6, -1, 1.8)
    ctx.close_path()
    fill_stroke(ctx, HORN, lw=0.8)
    ctx.restore()


def draw_hind_leg(ctx, F, key, s):
    C = _chest_c(F)
    hip = _R(F, (C[0] + 22 * s, C[1] + 4))
    foot = F['feet'][key]
    col = shade(SKIN, 0.8)
    mid = lerp2(hip, foot, 0.4)
    mid = (mid[0] + 7 * s, mid[1])
    tapered(ctx, [hip, mid, foot], [26, 20, 10], col, lw=1.3)
    draw_paw(ctx, (foot[0], foot[1] + 1), s, k=0.8, scale=0.85)


def draw_front_leg(ctx, F, key, s):
    C = _chest_c(F)
    sh = _R(F, (C[0] + 17 * s, C[1] - 4))
    foot = F['feet'][key]
    knee, ankle = ik(sh, (foot[0], foot[1] - 2), 19, 18, -1 * s)
    tapered(ctx, [sh, lerp2(sh, knee, 0.5), knee], [17, 15, 11], SKIN, lw=1.3)
    tapered(ctx, [knee, lerp2(knee, ankle, 0.5), ankle], [11, 9.5, 9], SKIN, lw=1.3)
    draw_paw(ctx, (foot[0], foot[1]), s)


CHEST = [(0, -24), (15, -22), (25, -13), (28, 0), (24, 13), (14, 20), (0, 22), (-14, 20),
         (-24, 13), (-28, 0), (-25, -13), (-15, -22)]
BAND = [(0, -21), (11, -19), (14.5, -7), (13.5, 7), (8.5, 17), (0, 19.5), (-8.5, 17), (-13.5, 7),
        (-14.5, -7), (-11, -19)]


def draw_body(ctx, F):
    C = _chest_c(F)
    b = 1 + 0.04 * F['breath']
    # haunches behind the chest
    # dorsal spikes peeking above the shoulders
    for s in (1, -1):
        for (bx, by_, tx, ty) in [(8, -21, 13, -33), (15, -18, 22, -27)]:
            ctx.move_to(*_R(F, (C[0] + (bx - 4) * s, C[1] + by_)))
            ctx.line_to(*_R(F, (C[0] + tx * s, C[1] + ty)))
            ctx.line_to(*_R(F, (C[0] + (bx + 4) * s, C[1] + by_ + 2)))
            ctx.close_path()
            fill_stroke(ctx, shade(SKIN_HI, 0.85), lw=1.0)
    pts = [_R(F, (C[0] + x * (1 + 0.02 * F['breath']), C[1] + y * b)) for x, y in CHEST]
    catmull(ctx, pts, closed=True)
    ctx.set_source_rgba(*SKIN)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    c = _R(F, (C[0] - 8, C[1] - 14))
    g = cairo.RadialGradient(c[0], c[1], 2, c[0], c[1], 30)
    g.add_color_stop_rgba(0, *SKIN_HI)
    g.add_color_stop_rgba(1, *SKIN)
    ctx.set_source(g)
    ctx.paint_with_alpha(0.6)
    band = [_R(F, (C[0] + x, C[1] + y * b)) for x, y in BAND]
    catmull(ctx, band, closed=True)
    ctx.set_source_rgba(*mix(BELLY, BELLY_HOT, F['belly_glow']))
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    ctx.set_source_rgba(*BELLY_LN)
    ctx.set_line_width(0.8)
    for y in range(-15, 19, 6):
        ctx.move_to(*_R(F, (C[0] - 16, C[1] + y * b - 1.5)))
        ctx.curve_to(*_R(F, (C[0] - 6, C[1] + y * b + 1.5)), *_R(F, (C[0] + 6, C[1] + y * b + 1.5)),
                     *_R(F, (C[0] + 16, C[1] + y * b - 1.5)))
    ctx.stroke()
    ctx.restore()
    if F['belly_glow'] > 0:
        c = _R(F, (C[0], C[1]))
        g = cairo.RadialGradient(c[0], c[1], 1, c[0], c[1], 26)
        g.add_color_stop_rgba(0, 1, 0.85, 0.4, 0.75 * F['belly_glow'])
        g.add_color_stop_rgba(1, 1, 0.5, 0.1, 0)
        ctx.set_source(g)
        ctx.paint()
    ctx.restore()
    catmull(ctx, pts, closed=True)
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.5)
    ctx.stroke()


def head_world(F):
    C = _chest_c(F)
    return _R(F, (C[0] + F['head'][0], C[1] + F['head'][1]))


def draw_neck(ctx, F):
    C = _chest_c(F)
    base = _R(F, (C[0], C[1] - 14))
    hw = head_world(F)
    top = (hw[0], hw[1] + 8 * F['head_s'])
    mid = lerp2(base, top, 0.5)
    mid = (lerp(base[0], top[0], 0.3), mid[1])
    pts = [base, mid, top]
    ws = [26, 21, 18 * F['head_s']]
    tapered(ctx, pts, ws, SKIN, lw=1.4)
    # centre plate strip
    l, r, nn = [], [], []
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, 2)]
        t = norm(sub(b, a))
        n = (-t[1], t[0])
        l.append(add(p, mul(n, ws[i] * 0.24)))
        r.append(sub(p, mul(n, ws[i] * 0.24)))
    catmull(ctx, l + list(reversed(r)), closed=True, tension=0.8)
    ctx.set_source_rgba(*mix(BELLY, BELLY_HOT, F['belly_glow']))
    ctx.fill()
    ctx.set_source_rgba(*BELLY_LN)
    ctx.set_line_width(0.8)
    for u in (0.2, 0.42, 0.64, 0.86):
        pa = lerp2(lerp2(l[0], l[1], u), lerp2(l[1], l[2], u), u)
        pb = lerp2(lerp2(r[0], r[1], u), lerp2(r[1], r[2], u), u)
        ctx.move_to(*pa)
        ctx.line_to(*pb)
    ctx.stroke()


SKULL = [(0, -15), (10, -14), (17, -8), (19, 0), (16, 8), (11, 12), (0, 13), (-11, 12),
         (-16, 8), (-19, 0), (-17, -8), (-10, -14)]
SNOUT = [(0, -5), (7, -4), (10, 1), (11, 6), (9, 10.5), (0, 12), (-9, 10.5), (-11, 6), (-10, 1),
         (-7, -4)]


def mouth_world(F):
    hw = head_world(F)
    p = rot((0, (11 + 5 * F['jaw']) * F['head_s']), F['lean'] + F['head_r'])
    return add(hw, p)


def draw_head(ctx, F):
    hw = head_world(F)
    ctx.save()
    ctx.translate(*hw)
    ctx.rotate(F['lean'] + F['head_r'])
    ctx.scale(F['head_s'], F['head_s'])
    j = F['jaw']
    # horns
    for s in (1, -1):
        pts = [(x * s, y) for x, y in [(5, -12), (10, -18), (16, -24), (22, -29), (26, -34),
                                        (27, -39), (29, -33), (27, -25), (22, -17), (15, -9)]]
        catmull(ctx, pts, closed=True, tension=0.7)
        ctx.set_source_rgba(*HORN)
        ctx.fill_preserve()
        ctx.save()
        ctx.clip()
        ctx.set_source_rgba(*HORN_SH)
        ctx.set_line_width(0.8)
        for q in range(4):
            y = -12 - q * 5
            ctx.move_to((9 + q * 4.5) * s, -15 - q * 5)
            ctx.line_to((15 + q * 4.5) * s, -11 - q * 5)
        ctx.stroke()
        ctx.restore()
        catmull(ctx, pts, closed=True, tension=0.7)
        ctx.set_source_rgba(*OUTLINE)
        ctx.set_line_width(1.1)
        ctx.stroke()
        # cheek frills
        for (bx, by_, tx, ty) in [(16, -3, 27, -2), (16, 3, 26, 7), (13, 8, 21, 15)]:
            ctx.move_to(bx * s, by_ - 3)
            ctx.line_to(tx * s, ty)
            ctx.line_to((bx - 2) * s, by_ + 3)
            ctx.close_path()
            fill_stroke(ctx, shade(SKIN_HI, 0.85), lw=1.0)
    # skull
    catmull(ctx, SKULL, closed=True)
    ctx.set_source_rgba(*SKIN)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    g = cairo.RadialGradient(-4, -10, 1, -4, -10, 18)
    g.add_color_stop_rgba(0, *SKIN_HI)
    g.add_color_stop_rgba(1, *SKIN)
    ctx.set_source(g)
    ctx.paint_with_alpha(0.75)
    ctx.restore()
    catmull(ctx, SKULL, closed=True)
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.4)
    ctx.stroke()
    # crest spike on top
    ctx.move_to(-3, -14)
    ctx.line_to(0, -20)
    ctx.line_to(3, -14)
    ctx.close_path()
    fill_stroke(ctx, shade(SKIN_HI, 0.9), lw=1.0)
    # lower jaw + mouth
    jy = 9.5 * j
    jaw = [(-10.5, 9 + jy), (10.5, 9 + jy), (10.5, 13.5 + jy), (6, 18 + jy), (0, 19 + jy),
           (-6, 18 + jy), (-10.5, 13.5 + jy)]
    if j > 0.02:
        catmull(ctx, [(-10, 7), (10, 7), (10, 11 + jy), (0, 12.5 + jy), (-10, 11 + jy)], closed=True,
                tension=0.6)
        ctx.set_source_rgba(*MOUTH)
        ctx.fill()
        ctx.save()
        ctx.translate(0, 9.5 + jy)
        ctx.scale(6.5, 1.6 + 1.6 * j)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.set_source_rgba(*TONGUE)
        ctx.fill()
    catmull(ctx, jaw, closed=True, tension=0.8)
    ctx.set_source_rgba(*SKIN)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    ctx.rectangle(-12, 15 + jy, 24, 8)
    ctx.set_source_rgba(*mix(BELLY, BELLY_HOT, F['belly_glow'] * 0.5))
    ctx.fill()
    ctx.restore()
    catmull(ctx, jaw, closed=True, tension=0.8)
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.3)
    ctx.stroke()
    if j > 0.02:
        for x in (-7.5, -4, 4, 7.5):
            ctx.move_to(x - 1.3, 10 + jy)
            ctx.line_to(x, 6.8 + jy if abs(x) > 6 else 7.6 + jy)
            ctx.line_to(x + 1.3, 10 + jy)
            ctx.close_path()
            ctx.set_source_rgba(*TEETH)
            ctx.fill()
    # snout (squish flattens it as if pressed on glass)
    sq = F['squish']
    ctx.save()
    ctx.translate(0, 6)
    ctx.scale(1 + 0.35 * sq, 1 - 0.18 * sq)
    ctx.translate(0, -6)
    catmull(ctx, SNOUT, closed=True)
    ctx.set_source_rgba(*SKIN)
    ctx.fill_preserve()
    ctx.save()
    ctx.clip()
    g = cairo.RadialGradient(-2, 2, 1, -2, 2, 13)
    g.add_color_stop_rgba(0, *mix(SKIN_HI, hexc('#5a6377'), 0.4 + 0.4 * sq))
    g.add_color_stop_rgba(1, *SKIN)
    ctx.set_source(g)
    ctx.paint()
    ctx.restore()
    catmull(ctx, SNOUT, closed=True)
    ctx.set_source_rgba(*OUTLINE)
    ctx.set_line_width(1.3)
    ctx.stroke()
    for s in (1, -1):
        ctx.arc(3 * s, -1.5, 1.2, 0, 2 * math.pi)
        ctx.set_source_rgba(*SKIN_HI)
        ctx.fill()
        ctx.save()
        ctx.translate(4.6 * s, 5.5)
        ctx.rotate(0.5 * s)
        ctx.scale(1.9, 1.0)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.set_source_rgba(*OUTLINE)
        ctx.fill()
        gl = max(F['fire'], F['fire_glow'])
        if gl > 0:
            g = cairo.RadialGradient(4.6 * s, 5.5, 0, 4.6 * s, 5.5, 4.5)
            g.add_color_stop_rgba(0, 1, 0.6, 0.15, 0.9 * gl)
            g.add_color_stop_rgba(1, 1, 0.4, 0.1, 0)
            ctx.set_source(g)
            ctx.arc(4.6 * s, 5.5, 4.5, 0, 2 * math.pi)
            ctx.fill()
    ctx.restore()
    # upper teeth along the snout's lower edge
    if j > 0.02:
        for x in (-8, -4.5, 4.5, 8):
            ctx.move_to(x - 1.3, 10.4)
            ctx.line_to(x, 13.8 if abs(x) > 6 else 12.8)
            ctx.line_to(x + 1.3, 10.4)
            ctx.close_path()
            ctx.set_source_rgba(*TEETH)
            ctx.fill()
    else:
        for x in (-8.5, 8.5):    # little fangs peeking out
            ctx.move_to(x - 1.1, 10.2)
            ctx.line_to(x, 13.2)
            ctx.line_to(x + 1.1, 10.2)
            ctx.close_path()
            ctx.set_source_rgba(*TEETH)
            ctx.fill()
    # tongue sticking out
    if F['tongue'] > 0:
        t = F['tongue']
        y0 = 10.5 + jy
        ctx.move_to(-4.5, y0)
        ctx.curve_to(-5, y0 + 6 * t, -3, y0 + 10 * t, 1, y0 + 10.5 * t)
        ctx.curve_to(4.5, y0 + 10 * t, 5, y0 + 6 * t, 4.5, y0)
        ctx.close_path()
        fill_stroke(ctx, TONGUE, lw=0.9)
        ctx.move_to(0, y0 + 1)
        ctx.line_to(0.4, y0 + 7 * t)
        ctx.set_source_rgba(*shade(TONGUE, 0.7))
        ctx.set_line_width(0.7)
        ctx.stroke()
    # eyes
    lx, ly = F['look']
    for s in (1, -1):
        ex, ey = 12.3 * s, -4.5
        if F['eye_happy'] > 0.5:
            ctx.move_to(ex - 4, ey + 1.5)
            ctx.curve_to(ex - 1.5, ey - 2.6, ex + 1.5, ey - 2.6, ex + 4, ey + 1.5)
            ctx.set_source_rgba(*OUTLINE)
            ctx.set_line_width(1.6)
            ctx.stroke()
        elif F['eye'] > 0.15:
            g = cairo.RadialGradient(ex, ey, 0, ex, ey, 8)
            g.add_color_stop_rgba(0, 1, 0.75, 0.2, 0.5)
            g.add_color_stop_rgba(1, 1, 0.6, 0.1, 0)
            ctx.set_source(g)
            ctx.arc(ex, ey, 8, 0, 2 * math.pi)
            ctx.fill()
            h = 3.0 * F['eye'] * (1 + 0.25 * F['pupil'])
            inner, outer = (ex - 4.4 * s, ey + 1.0), (ex + 4.6 * s, ey - 1.6)
            ctx.move_to(*inner)
            ctx.curve_to(ex - 2 * s, ey - h, ex + 2.5 * s, ey - h - 0.5, *outer)
            ctx.curve_to(ex + 2.5 * s, ey + h * 0.85, ex - 2 * s, ey + h * 0.95, *inner)
            ctx.close_path()
            ctx.set_source_rgba(*EYE)
            ctx.fill_preserve()
            ctx.save()
            ctx.clip_preserve()
            ctx.new_path()
            pr = F['pupil']
            ctx.translate(ex + lx * 1.6, ey - 0.3 + ly)
            ctx.scale(0.75 + 1.5 * pr, h * (0.42 + 0.1 * pr))
            ctx.arc(0, 0, 1.4, 0, 2 * math.pi)
            ctx.restore()
            ctx.set_source_rgba(0.05, 0.03, 0.02, 1)
            ctx.fill()
            ctx.arc(ex + lx * 1.6 + 1.2, ey - 1.3 + ly, 0.7 + 0.3 * pr, 0, 2 * math.pi)
            ctx.set_source_rgba(1, 1, 0.9, 0.9)
            ctx.fill()
            ctx.move_to(*inner)
            ctx.curve_to(ex - 2 * s, ey - h, ex + 2.5 * s, ey - h - 0.5, *outer)
            ctx.curve_to(ex + 2.5 * s, ey + h * 0.85, ex - 2 * s, ey + h * 0.95, *inner)
            ctx.close_path()
            ctx.set_source_rgba(*OUTLINE)
            ctx.set_line_width(0.9)
            ctx.stroke()
        else:
            ctx.move_to(ex - 4, ey + 0.5)
            ctx.curve_to(ex - 1.5, ey + 2.2, ex + 1.5, ey + 2.2, ex + 4, ey + 0.2)
            ctx.set_source_rgba(*OUTLINE)
            ctx.set_line_width(1.2)
            ctx.stroke()
        bu = F['brow'] * 2.2
        ctx.move_to(ex - 5.5 * s, ey - 4.2 - bu)
        ctx.curve_to(ex - 1.5 * s, ey - 6.8 - bu * 0.7, ex + 3 * s, ey - 7.2 - bu * 0.3,
                     ex + 6.5 * s, ey - 5.6)
        ctx.set_source_rgba(*OUTLINE)
        ctx.set_line_width(1.9)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.stroke()
    if F['smoke']:
        for (sx, sy, sr, sa) in F['smoke']:
            ctx.arc(sx, sy, sr, 0, 2 * math.pi)
            ctx.set_source_rgba(0.55, 0.55, 0.6, sa)
            ctx.fill()
    ctx.restore()


def draw_fire(ctx, F):
    """Flame blasting straight at the viewer: bright core with tongues of fire licking outward."""
    inten = F['fire']
    if inten <= 0:
        return
    m = mouth_world(F)
    T = 2 * math.pi * F['fire_t']
    R = 5 + 50 * inten
    g = cairo.RadialGradient(m[0], m[1], 0, m[0], m[1], R * 2.6)
    g.add_color_stop_rgba(0, 1, 0.7, 0.3, 0.5 * inten)
    g.add_color_stop_rgba(1, 1, 0.35, 0.05, 0)
    ctx.set_source(g)
    ctx.arc(m[0], m[1], R * 2.6, 0, 2 * math.pi)
    ctx.fill()
    N = 16
    tongues = []
    for i in range(N):
        a = i / N * 2 * math.pi + 0.25 * math.sin(T + i * 1.9)
        L = R * (1.05 + 0.28 * math.sin(T + i * 2.7) + 0.18 * math.sin(2 * T + i))
        w = R * 0.4
        tongues.append((a, L, w))
    layers = [(hexc('#a8191a', 0.92), 1.0), (hexc('#ef4f1a', 0.94), 0.84), (hexc('#ff9418', 0.96), 0.66),
              (hexc('#ffd447', 0.97), 0.47), (hexc('#fff7d6', 0.98), 0.28)]
    for li, (col, k) in enumerate(layers):
        ctx.push_group()
        ctx.set_source_rgba(col[0], col[1], col[2], 1)
        ctx.arc(m[0], m[1], R * k * 0.72, 0, 2 * math.pi)
        ctx.fill()
        for a, L, w in tongues:
            d = (math.cos(a), math.sin(a) * 0.9)
            n = (-d[1], d[0])
            tip = add(m, mul(d, L * k))
            b1 = add(add(m, mul(d, R * 0.3 * k)), mul(n, w * k))
            b2 = add(add(m, mul(d, R * 0.3 * k)), mul(n, -w * k))
            curl = mul(n, 0.35 * w * k * math.sin(T * 2 + a * 3))
            ctx.move_to(*b1)
            ctx.curve_to(*add(lerp2(b1, tip, 0.55), add(mul(n, w * k * 0.5), curl)),
                         *add(lerp2(b1, tip, 0.85), curl), *add(tip, curl))
            ctx.curve_to(*add(lerp2(b2, tip, 0.85), curl),
                         *add(lerp2(b2, tip, 0.55), add(mul(n, -w * k * 0.5), curl)), *b2)
            ctx.close_path()
            ctx.fill()
            ctx.arc(*lerp2(m, tip, 0.72), w * k * 0.62, 0, 2 * math.pi)
            ctx.fill()
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(col[3])
    for i in range(16):
        u = ((i * 0.29) + F['fire_t']) % 1.0
        a = i * 2.4
        d = R * (1.1 + 1.1 * u)
        ctx.arc(m[0] + math.cos(a) * d, m[1] + math.sin(a) * d * 0.9, 1.6 * (1 - u * 0.5), 0, 2 * math.pi)
        ctx.set_source_rgba(1, 0.88, 0.45, 0.9 * (1 - u) * inten)
        ctx.fill()


def draw_shadow(ctx, F):
    if F['shadow'] <= 0:
        return
    gy = F['shadow_gy'] if F['shadow_gy'] is not None else F['gy']
    k = F['shadow_k'] if F['shadow_k'] is not None else F['k']
    ctx.save()
    ctx.translate(F['cx'], gy + 1)
    ctx.scale(46 * k, 6 * k)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(0, 0, 0, 0.22 * F['shadow'])
    ctx.fill()


def render_front(F, scale=1):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W * scale), int(H * scale))
    ctx = cairo.Context(surf)
    ctx.scale(scale, scale)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    draw_shadow(ctx, F)
    ctx.save()
    ctx.translate(F['cx'], F['gy'])
    ctx.scale(F['k'], F['k'])
    draw_tail(ctx, F)
    draw_wing(ctx, F, 0, 1)
    draw_wing(ctx, F, 1, -1)
    draw_hind_leg(ctx, F, 'hr', 1)
    draw_hind_leg(ctx, F, 'hl', -1)
    draw_body(ctx, F)
    draw_neck(ctx, F)
    draw_front_leg(ctx, F, 'r', 1)
    draw_front_leg(ctx, F, 'l', -1)
    draw_head(ctx, F)
    draw_fire(ctx, F)
    ctx.restore()
    draw_fx(ctx, F['fx'])
    return surf
