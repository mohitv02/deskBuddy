"""The fox rig. Design space is 512x512 at 100%; `world` scales it to 80%
around the feet (256,470) so there is headroom for jumps and effects."""
import math
from model import Node, Shape, Rig, Path, ellipse, smooth, poly
from geom import patch, open_part, spiky, heart, star, sparkle, drop, leafshape, ell_pts, sample, resample

# ---------------------------------------------------------------- palette
OL = '#4a2c1d'   # outline (dark brown)
OR = '#f7913d'   # fur orange
OR2 = '#e97f2f'  # far-side limbs (flat, slightly deeper)
CR = '#fff4e4'   # cream
DB = '#6e3d26'   # socks / ear tips
EI = '#ffd6bd'   # inner ear
NO = '#3b2217'   # nose / eyes
BL = '#ff9d93'   # blush
GR = '#3f7f50'   # forest green accent
WH = '#ffffff'
MI = '#a43f33'   # mouth inside
TG = '#ff8f8c'   # tongue
YE = '#ffd25e'   # yellow
HT = '#ff6f82'   # hearts
DR = '#bfe2ff'   # sweat / tear
SN = '#f6fbff'   # snow
SN2 = '#d9eaf6'
LF = '#e0582f'   # autumn leaf
LF2 = '#b53e22'
BR = '#e2394c'   # berries
AN = '#ef4f5f'   # anger mark

W = 7.5          # outline width in design units (x0.8 = 6px)
FW = 6.0         # facial line width


def S(paths, fill=None, stroke=OL, sw=W, **kw):
    return Shape(paths, fill, stroke, sw, **kw)


def F(paths, fill):
    return Shape(paths, fill, None)


def glyph(path, color, w=7, ow=5.0):
    return [Shape(path, None, OL, w + ow * 2), Shape(path, None, color, w)]


def dot(cx, cy, r, color):
    return S(ellipse(cx, cy, r), color, sw=5)


EYL = (208, 240)
EYR = (304, 240)


# ---------------------------------------------------------------- head
HEAD = smooth([(256, 124), (336, 138), (382, 190), (394, 240, 0.8), (404, 274, 0.0), (372, 294), (322, 320),
               (256, 332), (190, 320), (140, 294), (108, 274, 0.0), (118, 240, 0.8), (130, 190), (176, 138)])
MASK = patch(HEAD, 4, 10, [(150, 258), (196, 272), (228, 268), (256, 250, 0.7), (284, 268), (316, 272), (362, 258)])


def ear(side):
    E = smooth([(-44, 12), (-46, -40), (-24, -86), (-4, -114, 0.12), (18, -86), (40, -42), (44, 12)])
    tip = patch(E, 2, 4, [(10, -76), (-2, -70, 1.2), (-14, -77)])
    inner = smooth([(-27, 8), (-28, -30), (-11, -70, 0.5), (14, -36), (26, 8)])
    parts = [F(E, OR), F(inner, EI), F(tip, DB), S(E)]
    tf = lambda p: p.rot(-22, 0, 0).move(182, 162)
    shapes = []
    for s in parts:
        ps = [tf(p) for p in s.paths]
        if side == 'R':
            ps = [p.mirror() for p in ps]
        shapes.append(Shape(ps, s.fill, s.stroke, s.sw, name='ear'))
    piv = (182, 162) if side == 'L' else (330, 162)
    return Node('ear' + side, piv, shapes)


def eye_variants(side):
    cx, cy = EYL if side == 'L' else EYR
    m = -1 if side == 'L' else 1    # outward direction sign
    st = 'eye' + side
    V = []

    def var(name, *shapes):
        V.append(Node(st + '_' + name, (cx, cy), shapes, show=(st, {name})))

    # open: big shiny
    var('open', F(ellipse(cx, cy, 19, 23), NO), F(ellipse(cx + 6, cy - 9, 7.5), WH), F(ellipse(cx - 6, cy + 9, 3.6), WH))
    # round (surprised): white with small pupil
    var('round', S(ellipse(cx, cy, 21, 24), WH, sw=FW), F(ellipse(cx, cy + 1, 9, 11), NO), F(ellipse(cx + 3, cy - 3, 3.4), WH))
    # sleepy U
    var('closed', S(smooth([(cx - 17, cy - 1), (cx, cy + 11), (cx + 17, cy - 1)], False), sw=FW))
    # happy ^
    var('happy', S(smooth([(cx - 17, cy + 7), (cx, cy - 10), (cx + 17, cy + 7)], False), sw=FW))
    # squint  > <
    sx = -m
    var('squint', S(poly([(cx - 13 * sx, cy - 12), (cx + 11 * sx, cy), (cx - 13 * sx, cy + 12)], False), sw=FW))
    # wink: arc with a little lash flick
    var('wink', S(smooth([(cx - 18, cy + 4), (cx, cy - 7), (cx + 18, cy + 4)], False), sw=FW),
        S(poly([(cx + 17 * m, cy + 3), (cx + 25 * m, cy - 3)], False), sw=FW - 1))
    # sly half-lid: lower part of eye under a tilted lid
    lid_y = lambda x: cy - 2 + (x - cx) * 0.18 * m
    pts = [(x, y) for x, y in ell_pts(cx, cy, 19, 23, -10, 190, 24)]
    pts = [(x, max(y, lid_y(x))) for x, y in pts]
    body = smooth([(x, y) for x, y in pts[::2]] + [(cx - 19, lid_y(cx - 19), 0)], t=0.6)
    lid = poly([(cx - 24, lid_y(cx - 24)), (cx + 24, lid_y(cx + 24))], False)
    var('half', F(body, NO), F(ellipse(cx + 6, cy + 7, 4), WH), S(lid, sw=FW + 1))
    # heart eyes
    var('heart', S(heart(cx, cy, 22), HT, sw=FW - 0.5), F(ellipse(cx - 7 * m * -1, cy - 6, 3.5), WH))
    # spiral (dizzy)
    sp = []
    for k in range(34):
        a = k * 0.55 * (-m)
        r = 2 + k * 0.6
        sp.append((cx + r * math.cos(a), cy + r * math.sin(a) * 1.1))
    var('spiral', S(smooth(sp, False), sw=FW - 1.5))
    return V


def mouth_variants():
    cx, cy = 256, 284
    V = []

    def var(name, *shapes):
        V.append(Node('mouth_' + name, (cx, cy), shapes, show=('mouth', set(name.split('|')))))

    philt = poly([(cx, cy - 10), (cx, cy - 1)], False)
    # small fox smile  ω
    var('smile', S([philt, smooth([(cx - 16, cy - 1), (cx - 8, cy + 7), (cx, cy - 1, 0.0), (cx + 8, cy + 7), (cx + 16, cy - 1)], False)], sw=FW - 0.5))
    # open with tongue
    M = smooth([(cx - 18, cy - 2, 0.3), (cx, cy + 1, 0.0), (cx + 18, cy - 2, 0.3), (cx + 13, cy + 16), (cx, cy + 22), (cx - 13, cy + 16)])
    tongue = patch(M, 3, 5, [(cx - 6, cy + 9), (cx + 6, cy + 9)])
    var('open', S(philt, sw=FW - 0.5), F(M, MI), F(tongue, TG), S(M, sw=FW - 0.5))
    # "o"
    var('o', S(philt, sw=FW - 0.5), S(ellipse(cx, cy + 9, 8, 10), MI, sw=FW - 0.5))
    # big yawn with tiny fangs
    Y = smooth([(cx, cy - 2), (cx + 20, cy + 6), (cx + 22, cy + 26), (cx, cy + 46), (cx - 22, cy + 26), (cx - 20, cy + 6)])
    yt = patch(Y, 2, 4, [(cx - 10, cy + 30), (cx + 10, cy + 30)])
    fangL = poly([(cx - 16, cy + 4), (cx - 7, cy + 1), (cx - 12, cy + 12)])
    fangR = fangL.mirror(cx)
    var('yawn', F(Y, MI), F(yt, TG), F(fangL, WH), F(fangR, WH), S(Y, sw=FW - 0.5))
    # frown
    var('frown', S(smooth([(cx - 13, cy + 8), (cx, cy + 1), (cx + 13, cy + 8)], False), sw=FW - 0.5), S(philt, sw=FW - 0.5))
    # sly smirk (one side up)
    var('smirk', S([philt, smooth([(cx - 14, cy + 2), (cx, cy + 7), (cx + 14, cy + 1), (cx + 19, cy - 5)], False)], sw=FW - 0.5))
    # pout (puffed cheek)
    var('pout', S(smooth([(cx - 8, cy + 6), (cx - 2, cy + 2), (cx + 3, cy + 7), (cx + 9, cy + 3)], False), sw=FW - 0.5), S(philt, sw=FW - 0.5))
    # lick: tongue out
    LT = smooth([(cx - 9, cy), (cx + 9, cy), (cx + 10, cy + 14), (cx, cy + 21), (cx - 10, cy + 14)])
    var('lick', S(philt, sw=FW - 0.5), S(LT, TG, sw=FW - 1), S(poly([(cx, cy + 4), (cx, cy + 12)], False), sw=3, stroke=MI),
        S(smooth([(cx - 16, cy - 1), (cx - 8, cy + 4), (cx, cy - 1, 0.0), (cx + 8, cy + 4), (cx + 16, cy - 1)], False), sw=FW - 0.5))
    # hold (closed smile used when carrying the leaf)
    var('hold', S([philt, smooth([(cx - 18, cy + 1), (cx, cy + 6), (cx + 18, cy + 1)], False)], sw=FW - 0.5))
    return V


def brows():
    V = []

    def var(name, *shapes):
        V.append(Node('brows_' + name, (256, 205), shapes, show=('brows', {name})))

    b = lambda pts: S(smooth(pts, False), sw=FW + 0.5, stroke=OL)
    var('curious', b([(188, 196), (205, 184), (224, 190)]), b([(288, 203), (304, 199), (320, 203)]))
    var('angry', b([(190, 199), (222, 209)]), b([(322, 199), (290, 209)]))
    var('sad', b([(190, 208), (220, 199)]), b([(322, 208), (292, 199)]))
    return V


def head():
    eyes = Node('eyes', (256, 240), [
        Node('eyeL', EYL, eye_variants('L')),
        Node('eyeR', EYR, eye_variants('R')),
    ])
    cheeks = Node('cheeks', (256, 278), [F(ellipse(174, 280, 17, 10), BL), F(ellipse(338, 280, 17, 10), BL)])
    # puffed cheek (right)
    pc = ellipse(384, 296, 27, 26)
    arc = smooth(ell_pts(384, 296, 27, 26, -52, 172, 8), False)
    puff = Node('puff', (384, 296), [F(pc, CR), S(arc), F(ellipse(386, 296, 13, 8), BL)], show=('puff', {'yes'}))
    nose = S(smooth([(244, 264, 0.6), (268, 264, 0.6), (256, 276, 0.4)]), NO, sw=4)
    nose_hl = F(ellipse(251, 266, 3.2, 2), WH)
    snow_nose = Node('snownose', (256, 262), [S(smooth([(232, 268), (236, 252), (250, 246), (262, 252), (276, 246), (286, 258), (282, 272), (256, 276)]), SN, sw=5),
                                             F(ellipse(266, 258, 5, 3), WH)], base={'o': 0})
    leaf_m = Node('leafm', (256, 290), [S(leafshape(288, 292, 64, 17, -14), LF, sw=5), S(poly([(262, 296), (312, 287)], False), stroke=LF2, sw=3),
                                       S(poly([(252, 298), (262, 296)], False), stroke=OL, sw=4)], base={'o': 0})
    muzzle = Node('muzzle', (256, 276), [nose, nose_hl] + mouth_variants() + [snow_nose, leaf_m])
    # head-attached effects
    sweat = Node('sweat', (372, 196), [S(drop(372, 200, 12), DR, sw=5), F(ellipse(368, 204, 3, 4), WH)], base={'o': 0})
    tear = Node('tear', (322, 266), [S(drop(324, 272, 8), DR, sw=4.5)], base={'o': 0})
    an = []
    for q in range(4):
        p = smooth([(-17, -5), (-6, -6), (-5, -17)], False).rot(q * 90, 0, 0).move(368, 150)
        an.append(p)
    anger = Node('anger', (368, 150), [Shape(an, None, OL, 13), Shape(an, None, AN, 6)], base={'o': 0})
    dz = []
    for k in range(3):
        dz.append(Node('dz%d' % (k + 1), (256, 120), [S(star(256, 120, 15), YE, sw=4.5)], base={'o': 0}))
    return Node('head', (256, 322), [
        ear('L'), ear('R'),
        F(HEAD, OR), F(MASK, CR), S(HEAD),
        puff, cheeks, eyes, Node('brows', (256, 205), brows()), muzzle,
        sweat, tear, anger] + dz)


# ---------------------------------------------------------------- body & legs
BODY = smooth([(256, 294), (306, 308), (334, 358), (340, 420), (320, 458), (256, 470), (192, 458), (172, 420),
               (178, 358), (206, 308)])
CHEST = smooth([(256, 330), (288, 344), (292, 380), (272, 404), (256, 410), (240, 404), (220, 380), (224, 344)])


def bandana():
    B = smooth([(196, 310, 0.5), (256, 324), (316, 310, 0.5), (300, 344), (264, 384, 0.4), (248, 384, 0.4), (212, 344)])
    leaves = [leafshape(236, 338, 14, 4.5, -35), leafshape(278, 340, 14, 4.5, 30), leafshape(257, 362, 13, 4.2, 80)]
    return Node('bandana', (256, 318), [S(B, GR), Shape(leaves, WH, None)])


def front_leg(side):
    C = smooth([(208, 396), (208, 430), (208, 456, 0.8), (216, 470, 0.7), (236, 471, 0.7), (245, 456, 0.8),
                (245, 430), (245, 396)])
    sock = patch(C, 1, 6, [(236, 424), (217, 424)])
    outline = open_part(C, 0, 7)
    toe = poly([(226, 462), (226, 470)], False)
    shapes = [F(C, OR), F(sock, DB), S(outline), S(toe, sw=3.5, stroke=OL)]
    if side == 'R':
        shapes = [Shape([p.mirror() for p in s.paths], s.fill, s.stroke, s.sw) for s in shapes]
    piv = (226, 400) if side == 'L' else (286, 400)
    return Node('front' + side, piv, shapes)


def hind_leg(side):
    thigh = ellipse(180, 430, 34, 38)
    foot = smooth([(150, 456), (172, 448), (196, 452), (200, 466), (178, 476), (150, 472)])
    shapes = [S(thigh, OR2), S(foot, DB)]
    if side == 'R':
        shapes = [Shape([p.mirror() for p in s.paths], s.fill, s.stroke, s.sw) for s in shapes]
    piv = (190, 420) if side == 'L' else (322, 420)
    return Node('hind' + side, piv, shapes)


# ---------------------------------------------------------------- tail (4-segment chain)
TAIL_ROOT = (330, 392)
SEG = [(54, 24, 36), (60, 36, 44), (60, 44, 42)]   # (length, w0, w1)
TIP_LEN = 92
TAIL_BASE = (58, 166, 184, 196)    # absolute angles of the wrapped base pose


def rel(a):
    return [a[0], a[1] - a[0], a[2] - a[1], a[3] - a[2]]


def seg_blob(L, w0, w1):
    m = (w0 + w1) / 2 * 1.06
    return smooth([(-w0, 0), (-w0 * 0.7, -w0 * 0.72), (0, -w0), (L / 2, -m), (L, -w1), (L + w1 * 0.7, -w1 * 0.72),
                   (L + w1, 0), (L + w1 * 0.7, w1 * 0.72), (L, w1), (L / 2, m), (0, w0), (-w0 * 0.7, w0 * 0.72)])


def tip_blob():
    P = smooth([(-42, 0), (-30, -30), (0, -43), (32, -41), (48, -36), (70, -24), (TIP_LEN, 0, 0.2), (70, 24),
                (48, 36), (32, 41), (0, 43), (-30, 30)])
    white = patch(P, 4, 8, [(40, 24, 0.4), (52, 12, 0.4), (40, 0, 0.4), (52, -12, 0.4), (40, -24, 0.4)])
    return P, white


def tail_chain(pass_, tag):
    """pass_ 'ol' = outline underlay, 'fill' = colour on top (gives a seamless union)."""
    rr = rel(TAIL_BASE)
    x, y = TAIL_ROOT
    blobs = [seg_blob(*s) for s in SEG]
    tipP, white = tip_blob()
    offs = [0, SEG[0][0], SEG[0][0] + SEG[1][0], SEG[0][0] + SEG[1][0] + SEG[2][0]]

    def shapes_for(k):
        P = blobs[k] if k < 3 else tipP
        P = P.move(x + offs[k], y)
        Pk = spiky(P, 9 if k < 3 else 10, 9)
        out = []
        for fur, path in (('smooth', P), ('spiky', Pk)):
            if pass_ == 'ol':
                sh = [Shape(path, OL, OL, W * 2)]
            else:
                sh = [Shape(path, OR, None)]
                if k == 3:
                    wpath = white.move(x + offs[k], y)
                    sh.append(Shape(wpath, WH, None))
            out.append(Node('fur_%s_%d' % (fur, k), (0, 0), sh, show=('fur', {fur})))
        return out

    node = None
    for k in (3, 2, 1, 0):
        ch = shapes_for(k) + ([node] if node else [])
        node = Node('t%s%s%d' % (tag, pass_, k + 1), (x + offs[k], y), ch, base={'r': rr[k]}, track='tail%d' % (k + 1))
    return node


def tail_layer(layer):
    return Node('tail_' + layer, (0, 0), [tail_chain('ol', layer), tail_chain('fill', layer)],
                show=('tail', {layer}))


def heart_tail():
    # the tail rises from the root and traces a heart beside the fox
    cx, cy, sc = 490, 290, 4.4
    hp = []
    for k in range(0, 49):
        t = math.pi - 0.02 - k * (2 * math.pi * 0.86) / 48
        hx = 16 * math.sin(t) ** 3
        hy = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        hp.append((cx + hx * sc, cy + hy * sc))
    lead = [TAIL_ROOT, (388, 406), (448, 390)]
    line = resample(lead + hp, 30, closed=False)
    P = smooth(line, False)
    tip = smooth(resample(line[-4:], 4, closed=False), False)
    w = 34
    return Node('tailH', (480, 365), [Shape(P, None, OL, w + 2 * W), Shape(P, None, OR, w),
                                     Shape(tip, None, OL, w + 2 * W), Shape(tip, None, WH, w)],
                show=('tail', {'heart'}))


# ---------------------------------------------------------------- props & effects
def snow_tuft():
    # a wide, lumpy snowbank across the bottom of the frame
    lumps = [(-60, 420), (6, 380), (70, 352), (132, 322), (194, 304), (256, 296), (318, 302), (380, 320), (442, 350),
             (506, 378), (572, 416)]
    pts = [(-70, 600, 0.3)]
    for k, (x, y) in enumerate(lumps):
        pts.append((x, y, 1.0))
        if k < len(lumps) - 1:
            nx, ny = lumps[k + 1]
            pts.append(((x + nx) / 2, (y + ny) / 2 + 13, 0.25))
    pts.append((582, 600, 0.3))
    P = smooth(pts)
    shade = smooth([(-40, 600), (-40, 500), (40, 486, 0.4), (120, 500, 0.4), (200, 484, 0.4), (290, 500, 0.4),
                    (370, 484, 0.4), (450, 500, 0.4), (552, 486, 0.4), (552, 600)])
    return Node('tuft', (256, 540), [S(P, SN), F(shade, SN2), F(ellipse(300, 326, 8, 5), WH), F(ellipse(150, 348, 5, 4), WH),
                                     F(ellipse(410, 352, 4, 3), WH)], base={'o': 0})


def puffs():
    out = []
    spots = [(160, 330, 14), (214, 296, 11), (300, 290, 13), (356, 324, 12), (256, 280, 10)]
    for k, (x, y, r) in enumerate(spots):
        out.append(Node('puff%d' % (k + 1), (x, y), [S(ellipse(x, y, r), SN, sw=5)], base={'o': 0}))
    return out


def hearts():
    spots = [(150, 150, 18), (360, 120, 15), (250, 70, 13), (400, 220, 12)]
    return [Node('heart%d' % (k + 1), (x, y), [S(heart(x, y, r), HT, sw=5), F(ellipse(x - r * 0.4, y - r * 0.2, r * 0.18), WH)],
                 base={'o': 0}) for k, (x, y, r) in enumerate(spots)]


def sparkles():
    spots = [(140, 180, 18), (380, 150, 15), (400, 300, 12), (120, 320, 11)]
    return [Node('spark%d' % (k + 1), (x, y), [S(sparkle(x, y, r), YE, sw=4.5)], base={'o': 0})
            for k, (x, y, r) in enumerate(spots)]


def zs():
    out = []
    for k, (x, y, s) in enumerate([(340, 300, 11), (370, 250, 14), (404, 196, 17)]):
        p = poly([(x - s, y - s), (x + s, y - s), (x - s, y + s), (x + s, y + s)], False)
        out.append(Node('z%d' % (k + 1), (x, y), glyph(p, CR, 6, 4.5), base={'o': 0}))
    return out


def qmark(x, y, s, color=YE):
    p = smooth([(x - 0.75 * s, y - 0.5 * s), (x - 0.4 * s, y - 1.0 * s), (x + 0.3 * s, y - 1.05 * s),
                (x + 0.78 * s, y - 0.55 * s), (x + 0.45 * s, y - 0.02 * s), (x, y + 0.3 * s), (x, y + 0.55 * s)], False)
    return glyph(p, color, 8, 5) + [dot(x, y + 1.15 * s, 6.5, color)]


def emark(x, y, s, color=YE):
    p = poly([(x, y - s), (x, y + 0.42 * s)], False)
    return glyph(p, color, 19, 5.5) + [dot(x, y + 1.08 * s, 11, color)]


def thought():
    cx, cy = 392, 104
    pts = []
    n = 9
    for k in range(n * 2):
        a = math.radians(-90 + k * 180 / n)
        rr = 1.0 if k % 2 == 0 else 0.86
        pts.append((cx + 74 * rr * math.cos(a), cy + 56 * rr * math.sin(a), 1.0 if k % 2 == 0 else 0.0))
    cloud = smooth(pts, t=1.1)
    berries = []
    for bx, by in ((372, 116), (398, 120), (386, 96)):
        berries += [S(ellipse(bx, by, 13), BR, sw=4.5), F(ellipse(bx - 4, by - 5, 3.5, 2.6), WH)]
    stems = S(smooth([(372, 104), (380, 80), (392, 70)], False), stroke=OL, sw=3.5)
    stems2 = S(smooth([(398, 108), (392, 82)], False), stroke=OL, sw=3.5)
    lf = S(leafshape(408, 72, 30, 9, -20), GR, sw=4)
    return Node('thought', (392, 150), [S(ellipse(326, 196, 8), WH, sw=4.5), S(ellipse(348, 170, 12), WH, sw=4.5),
                                       S(cloud, WH, sw=5), stems, stems2, lf] + berries, base={'o': 0})


def badge():
    cx, cy = 256, 22
    p = poly([(cx, cy - 16), (cx, cy + 6)], False)
    return Node('badge', (cx, cy + 34), [S(ellipse(cx, cy, 36), YE, sw=6), S(p, stroke=OL, sw=10), S(ellipse(cx, cy + 17, 5.5), OL, sw=1)],
                base={'o': 0})


def falling_leaf():
    return Node('leaf', (256, 300), [S(leafshape(256, 300, 64, 17, -14), LF, sw=5),
                                     S(poly([(232, 306), (282, 295)], False), stroke=LF2, sw=3),
                                     S(poly([(222, 308), (232, 306)], False), stroke=OL, sw=4)], base={'o': 0})


def build():
    roll = Node('roll', (256, 340), [
        tail_layer('back'), heart_tail(),
        hind_leg('L'), hind_leg('R'),
        Node('body', (256, 468), [
            Node('bodyfur', (256, 468), [S(spiky(BODY, 22, 10), OR)], show=('fur', {'spiky'})),
            S(BODY, OR), F(CHEST, CR), bandana()]),
        tail_layer('mid'),
        front_leg('L'), front_leg('R'),
        head(),
        tail_layer('top'),
    ])
    char = Node('char', (256, 470), [roll])
    swing = Node('swing', (256, 150), [char])
    shadow = Node('shadow', (256, 470), [Shape(ellipse(256, 470, 118, 15), OL, None, fo=0.16)])
    world = Node('world', (256, 470), [shadow, swing, snow_tuft(), falling_leaf()] + puffs() + hearts() + sparkles() + zs() + [
        Node('qmark', (330, 120), qmark(330, 120, 22), base={'o': 0}),
        Node('emark', (104, 150), emark(104, 116, 36), base={'o': 0}),
        thought(), badge()], base={'sx': 0.8, 'sy': 0.8})
    rig = Rig(world)
    rig.state_defaults = {'eyeL': 'open', 'eyeR': 'open', 'mouth': 'smile', 'brows': 'none', 'tail': 'mid',
                          'fur': 'smooth', 'puff': 'no'}
    return rig


TAIL_REL = rel(TAIL_BASE)
