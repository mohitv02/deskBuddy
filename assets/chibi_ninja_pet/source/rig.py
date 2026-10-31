"""The chibi ninja rig. Canvas 512x512, ground y=470, centre x=256."""
import math
from core import *

PAL = dict(out='#17151f', suit='#2f2f3d', suit_hi='#4a4b60', red='#e8303d', red_dk='#a91f2b', skin='#ffd3b3',
           cheek='#ff8a9c', white='#ffffff', eye='#17151f', mouth='#9a9bb4', steel='#c9ccda', steel_dk='#8d90a3',
           wood='#c98b55', wood_dk='#8a5a33', smoke='#eeeef5', paper='#f8f0dc', rice='#ffffff', nori='#2f2f3d', star='#ffd84a')
GHOST = dict(PAL, out='#6f7590', suit='#b9c0db', suit_hi='#cfd5ea', red='#f3a3aa', red_dk='#e98c95', skin='#ffe9dc',
             cheek='#ffc7d0', eye='#6f7590', mouth='#8f95ad')
OW = 6      # main outline width
GROUND = 470

def spiral(c, r=11, turns=2.2, n=34):
    """Archimedean spiral from the centre of an eye outwards."""
    pts = []
    for k in range(n):
        u = k / (n - 1); a = u * turns * 2 * math.pi
        pts.append((c[0] + r * u * math.cos(a), c[1] + r * u * math.sin(a)))
    return smooth(pts, closed=False, t=1 / 6)

def star5(cx, cy, R, r):
    return poly([(cx + (R if k % 2 == 0 else r) * math.cos(math.radians(-90 + 36 * k)), cy + (R if k % 2 == 0 else r) * math.sin(math.radians(-90 + 36 * k))) for k in range(10)])

def build_character(pre='', pal=PAL, props=True):
    C = {k: hexc(v) for k, v in pal.items()}
    out, suit, red, skin = C['out'], C['suit'], C['red'], C['skin']
    n = lambda name, *a, **k: Node(pre + name, *a, **k)

    # ---------- scarf tail (3 chained segments, behind body)
    def seg(name, A, L, w0, w1, rot, child=None, tip=False):
        prims = outlined(ribbon(A, (A[0] + L, A[1]), w0, w1), red, out, 5)
        if tip:  # little forked end
            prims += [Prim(line((A[0] + L - 6, A[1] - 4), (A[0] + L + 6, A[1])), stroke=out, w=4)]
        nd = n(name, A, prims, rot=rot, cfirst=True)
        if child: nd.add(child)
        return nd
    sA = (206, 344)
    s3 = seg('scarf3', (sA[0] + 76, sA[1]), 38, 21, 15, -20)
    s2 = seg('scarf2', (sA[0] + 38, sA[1]), 38, 23, 21, -18, s3)
    s1 = seg('scarf1', sA, 38, 24, 23, 150, s2)
    s1.p0 = sA
    # child anchors are in parent-local coordinates (parent drawn along +x from its anchor)
    s2.a = (sA[0] + 38, sA[1]); s2.p0 = s2.a
    s3.a = (sA[0] + 76, sA[1]); s3.p0 = s3.a

    # ---------- legs
    def leg(name, hip, foot_dx):
        hx, hy = hip
        prims = capsule((hx, hy), (hx, hy + 20), 30, suit, out, OW / 2 + 0.5)
        fx = hx + foot_dx
        prims += outlined(rrect(fx - 23, 462, 46, 10, 5), red, out, 4.5)
        prims += outlined(ellipse(fx, 459, 18, 9), skin, out, 4.5)
        prims += [Prim(quad((fx - 9, 463), (fx, 452), (fx + 9, 463)), stroke=red, w=5)]
        return n(name, hip, prims)
    legL = leg('legL', (238, 434), -5); legR = leg('legR', (274, 434), 5)

    # ---------- torso
    tor_pts = [(212, 336), (256, 332), (300, 336), (314, 368), (321, 414), (310, 442), (256, 447), (202, 442), (191, 414), (198, 368)]
    torso_prims = outlined(smooth(tor_pts), suit, out, OW)
    torso_prims += [Prim(line((224, 342), (270, 404)), stroke=C['suit_hi'], w=5),
                    Prim(line((290, 342), (257, 386)), stroke=C['suit_hi'], w=5)]
    belt = [Prim(smooth([(193, 403), (256, 408), (319, 403), (321, 420), (256, 426), (192, 420)], corners={0, 2, 3, 5}, t=1 / 8), fill=red, stroke=out, w=5)]
    beltknot = n('beltknot', (256, 414), outlined(ribbon((250, 420), (240, 446), 12, 9), red, out, 4) + outlined(ribbon((262, 420), (273, 445), 12, 9), red, out, 4)
                 + outlined(rrect(244, 406, 24, 18, 7), red, out, 4.5))
    wrap = outlined(rrect(198, 330, 116, 28, 13), red, out, 5)
    rumble = n('rumble', (256, 390), [Prim(quad((300 + 10 * k, 378 + 12 * k), (310 + 10 * k, 386 + 12 * k), (300 + 10 * k, 394 + 12 * k)), stroke=out, w=4) for k in range(0)]
               + [Prim(quad((326, 372), (338, 386), (326, 400)), stroke=out, w=5), Prim(quad((338, 366), (354, 386), (338, 406)), stroke=out, w=5),
                  Prim(quad((186, 372), (174, 386), (186, 400)), stroke=out, w=5), Prim(quad((174, 366), (158, 386), (174, 406)), stroke=out, w=5)], op=0)
    torso = n('torso', (256, 446), torso_prims + belt + wrap, [beltknot, rumble])

    # ---------- head
    HC = (256, 262); HRX, HRY = 94, 86
    def band_poly(top0, bot0, k):
        def ex(y):  # half width of head ellipse at y
            v = 1 - ((y - HC[1]) / HRY) ** 2
            return HRX * math.sqrt(max(0, v))
        def inside(x, y): return ((x - HC[0]) / HRX) ** 2 + ((y - HC[1]) / HRY) ** 2 <= 1
        topf = lambda x: top0 + k * (x - 256) ** 2
        botf = lambda x: bot0 + k * (x - 256) ** 2
        def xmax(f):
            lo, hi = 0, HRX
            for _ in range(40):
                m = (lo + hi) / 2
                if inside(256 + m, f(256 + m)): lo = m
                else: hi = m
            return lo
        xt, xb = xmax(topf), xmax(botf)
        pts = [(256 + x, topf(256 + x)) for x in [-xt + 2 * xt * j / 10 for j in range(11)]]
        # right edge along ellipse from top to bottom
        a0 = math.atan2((topf(256 + xt) - HC[1]) / HRY, xt / HRX); a1 = math.atan2((botf(256 + xb) - HC[1]) / HRY, xb / HRX)
        pts += [(HC[0] + HRX * math.cos(a0 + (a1 - a0) * j / 3), HC[1] + HRY * math.sin(a0 + (a1 - a0) * j / 3)) for j in (1, 2)]
        pts += [(256 + x, botf(256 + x)) for x in [xb - 2 * xb * j / 10 for j in range(11)]]
        pts += [(HC[0] - HRX * math.cos(a1 + (a0 - a1) * j / 3), HC[1] + HRY * math.sin(a1 + (a0 - a1) * j / 3)) for j in (1, 2)]
        return smooth(pts, True, corners={0, 10, 13, 23}, t=1 / 6)
    # headband tails (2 x 2 segments) behind the hood
    knot = (338, 222)
    def tail(name, L1, L2, w, r1, r2):
        t2 = n(name + '2', (knot[0] + L1, knot[1]), outlined(ribbon((knot[0] + L1, knot[1]), (knot[0] + L1 + L2, knot[1]), w - 4, w - 11), red, out, 5), rot=r2)
        t1 = n(name + '1', knot, outlined(ribbon(knot, (knot[0] + L1, knot[1]), w, w - 3), red, out, 5), [t2], rot=r1, cfirst=True)
        return t1
    tailA = tail('htailA', 42, 38, 25, -28, 30); tailB = tail('htailB', 38, 32, 23, 24, 22)
    hood = outlined(ellipse(HC[0], HC[1], HRX, HRY), suit, out, OW)
    hood_hi = [Prim(Path([(196, 214), (232, 186)], [(0, 0), (-16, 6)], [(8, -16), (0, 0)], closed=False), stroke=C['suit_hi'], w=11)]
    face = outlined(rrect(181, 234, 150, 66, 30), skin, out, 5)
    cheeks = n('cheeks', (256, 290), [Prim(ellipse(205, 289, 13, 7), fill=C['cheek']), Prim(ellipse(307, 289, 13, 7), fill=C['cheek'])])
    blush = n('blush', (256, 290), [Prim(line((196 + 8 * j, 294), (202 + 8 * j, 284)), stroke=C['red_dk'], w=3) for j in range(3)]
              + [Prim(line((298 + 8 * j, 294), (304 + 8 * j, 284)), stroke=C['red_dk'], w=3) for j in range(3)], op=0)
    EL, ER, EY = (224, 270), (288, 270), 270
    def eye_open(c, s=1.0):
        x, y = c
        return [Prim(ellipse(x, y, 13 * s, 17 * s), fill=C['eye']), Prim(circle(x + 4.5 * s, y - 6 * s, 5.5 * s), fill=C['white']),
                Prim(circle(x - 4 * s, y + 6.5 * s, 2.6 * s), fill=C['white'])]
    def eye_sharp(c, side):
        x, y = c; inn = 1 if side == 'L' else -1   # inner corner lower
        top_o = (x - 14 * inn, y - 12); top_i = (x + 14 * inn, y - 3)
        pth = smooth([top_o, top_i, (x + 13 * inn, y + 6), (x, y + 16), (x - 13 * inn, y + 6)], corners={0, 1}, t=1 / 5)
        return [Prim(pth, fill=C['eye']), Prim(circle(x + 3, y - 1, 4.5), fill=C['white']), Prim(circle(x - 4, y + 8, 2.2), fill=C['white'])]
    arcd = lambda c, up: Prim(quad((c[0] - 12, c[1] + (5 if up else -3)), (c[0], c[1] + (-13 if up else 11)), (c[0] + 12, c[1] + (5 if up else -3))), stroke=out, w=5.5)
    eyes_open = n('eyes_open', (256, EY), [], [n('eyeL', EL, eye_open(EL)), n('eyeR', ER, eye_open(ER))])
    variants = {
        'open': eyes_open,
        'sleepy': n('eyes_sleepy', (256, EY), [arcd(EL, False), arcd(ER, False)], op=0),
        'happy': n('eyes_happy', (256, EY), [arcd(EL, True), arcd(ER, True)], op=0),
        'sharp': n('eyes_sharp', (256, EY), eye_sharp(EL, 'L') + eye_sharp(ER, 'R'), op=0),
        'squint': n('eyes_squint', (256, EY), [Prim(line((212, 261), (234, 270), (212, 279)), stroke=out, w=5.5), Prim(line((300, 261), (278, 270), (300, 279)), stroke=out, w=5.5)], op=0),
        'wink': n('eyes_wink', (256, EY), eye_open(EL) + [arcd(ER, True)], op=0),
        'heart': n('eyes_heart', (256, EY), [Prim(heart(EL[0], EL[1] + 1, 15), fill=red, stroke=out, w=4), Prim(heart(ER[0], ER[1] + 1, 15), fill=red, stroke=out, w=4),
                                             Prim(circle(EL[0] - 6, EL[1] - 6, 3), fill=C['white']), Prim(circle(ER[0] - 6, ER[1] - 6, 3), fill=C['white'])], op=0),
        'big': n('eyes_big', (256, EY), eye_open(EL, 1.22) + eye_open(ER, 1.22), op=0),
        'dot': n('eyes_dot', (256, EY), [Prim(circle(EL[0], EL[1], 15), fill=C['white'], stroke=out, w=4.5), Prim(circle(EL[0], EL[1], 5), fill=out),
                                         Prim(circle(ER[0], ER[1], 15), fill=C['white'], stroke=out, w=4.5), Prim(circle(ER[0], ER[1], 5), fill=out)], op=0),
        # dizzy @ @: the spirals spin on their own nodes (spiralL / spiralR)
        'spiral': n('eyes_spiral', (256, EY), [Prim(circle(EL[0], EL[1], 15), fill=C['white'], stroke=out, w=4.5), Prim(circle(ER[0], ER[1], 15), fill=C['white'], stroke=out, w=4.5)],
                    [n('spiralL', EL, [Prim(spiral(EL), stroke=out, w=3.5)]), n('spiralR', ER, [Prim(spiral(ER), stroke=out, w=3.5)])], op=0),
        # annoyed - _ -
        'meh': n('eyes_meh', (256, EY), [Prim(line((211, 271), (237, 271)), stroke=out, w=6), Prim(line((275, 271), (301, 271)), stroke=out, w=6)], op=0),
    }
    eyes = n('eyes', (256, EY), [], list(variants.values()))
    B = lambda pts, w=6: Prim(line(*pts), stroke=out, w=w)
    Q = lambda a, c, b, w=6: Prim(quad(a, c, b), stroke=out, w=w)
    brows = {
        'det': n('brows_det', (256, 246), [B([(209, 243), (237, 250)]), B([(303, 243), (275, 250)])]),
        'angry': n('brows_angry', (256, 246), [B([(208, 239), (239, 254)], 7), B([(304, 239), (273, 254)], 7)], op=0),
        'sad': n('brows_sad', (256, 246), [B([(209, 252), (236, 243)]), B([(303, 252), (276, 243)])], op=0),
        'worried': n('brows_worried', (256, 246), [Q((208, 250), (226, 238), (238, 247)), Q((304, 250), (286, 238), (274, 247))], op=0),
        'up': n('brows_up', (256, 246), [Q((210, 247), (223, 238), (236, 245)), Q((302, 247), (289, 238), (276, 245))], op=0),
        'calm': n('brows_calm', (256, 246), [Q((211, 248), (224, 244), (236, 248), 5), Q((301, 248), (288, 244), (276, 248), 5)], op=0),
    }
    browsN = n('brows', (256, 246), [], list(brows.values()))
    M = C['mouth']; MY = 320
    mouths = {
        'smile': n('mouth_smile', (256, MY), [Prim(quad((243, 315), (256, 329), (269, 315)), stroke=M, w=5)], op=0),
        'grin': n('mouth_grin', (256, MY), [Prim(quad((242, 318), (258, 328), (271, 312)), stroke=M, w=5)], op=0),
        'frown': n('mouth_frown', (256, MY), [Prim(quad((244, 325), (256, 312), (268, 325)), stroke=M, w=5)], op=0),
        'o': n('mouth_o', (256, MY), [Prim(ellipse(256, 320, 7, 8), fill=out, stroke=M, w=4)], op=0),
        'shout': n('mouth_shout', (256, MY), [Prim(smooth([(239, 309), (273, 309), (268, 326), (256, 334), (244, 326)], corners={0, 1}), fill=out, stroke=M, w=4),
                                               Prim(ellipse(256, 327, 8, 4.5), fill=red)], op=0),
        'yawn': n('mouth_yawn', (256, MY), [Prim(ellipse(256, 322, 13, 16), fill=out, stroke=M, w=4), Prim(ellipse(256, 331, 8, 5), fill=red)], op=0),
        'pout': n('mouth_pout', (256, MY), [Prim(line((245, 320), (250, 315), (256, 320), (262, 315), (267, 320)), stroke=M, w=4.5)], op=0),
        'flat': n('mouth_flat', (256, MY), [Prim(line((247, 319), (265, 319)), stroke=M, w=5)], op=0),
        'wavy': n('mouth_wavy', (256, MY), [Prim(smooth([(240, 321), (248, 314), (256, 321), (264, 328), (272, 321)], closed=False, corners={0, 4}), stroke=M, w=5)], op=0),
    }
    mouthN = n('mouth', (256, MY), [], list(mouths.values()))
    maskup = n('maskup', (256, 302), outlined(rrect(179, 232, 154, 72, 30), suit, out, 5) + [Prim(line((200, 262), (312, 262)), stroke=C['suit_hi'], w=4)], scale=(100, 0), op=0)
    headband = [Prim(band_poly(206, 232, 0.0017), fill=red, stroke=out, w=5)]
    sf_pts = [(184, 292), (210, 284), (236, 290), (256, 284), (278, 290), (302, 284), (328, 292), (332, 318), (318, 340), (256, 346), (194, 340), (180, 318)]
    scarffront = n('scarffront', (256, 344), outlined(smooth(sf_pts, corners={0, 6}), red, out, 5) +
                   [Prim(quad((206, 304), (230, 312), (252, 304)), stroke=C['red_dk'], w=4), Prim(quad((262, 318), (286, 326), (308, 316)), stroke=C['red_dk'], w=4)], scale=(100, 0), op=0)
    knotN = n('knot', knot, outlined(smooth([(326, 210), (346, 208), (352, 224), (342, 238), (325, 234)]), red, out, 5))
    snot = n('snot', (268, 306), [Prim(circle(283, 296, 15), fill=hexc('#e9f6ff'), stroke=out, w=4), Prim(circle(278, 290, 4), fill=C['white'])], scale=(0, 0), op=0)
    sweat = n('sweat', (340, 250), [Prim(drop(340, 250, 15), fill=C['white'], stroke=out, w=4), Prim(circle(336, 254, 3.5), fill=hexc('#cfe4ff'))], scale=(0, 0), op=0)
    anger = n('anger', (338, 196), [Prim(quad(a, c, b), stroke=red, w=6) for a, c, b in [((326, 186), (336, 188), (334, 178)), ((350, 186), (340, 188), (342, 178)),
                                                                   ((326, 206), (336, 204), (334, 214)), ((350, 206), (340, 204), (342, 214))]], scale=(0, 0), op=0)
    tear = n('tear', (222, 292), [Prim(drop(222, 296, 9), fill=hexc('#e9f6ff'), stroke=out, w=3.5)], scale=(0, 0), op=0)
    head = n('head', (256, 340), [], [tailA, tailB, Node(pre + 'hoodN', (0, 0), hood + hood_hi + face), cheeks, blush, eyes, browsN, mouthN, maskup, scarffront,
                                     Node(pre + 'bandN', (0, 0), headband), knotN, snot, sweat, anger, tear])

    # ---------- arms + hands
    def mitten(cx, cy, thumb_dx):
        return outlined(circle(cx + thumb_dx, cy - 9, 7), skin, out, 4.5) + outlined(circle(cx, cy, 15), skin, out, 5)
    def hand(side, sx, wy):
        cx, cy = sx, wy + 6; tdx = 11 if side == 'L' else -11
        fist = n('hand' + side + '_fist', (cx, cy), mitten(cx, cy, tdx))
        opn = n('hand' + side + '_open', (cx, cy), outlined(ellipse(cx + tdx * 1.4, cy - 4, 6, 9), skin, out, 4.5) + outlined(ellipse(cx, cy + 2, 15, 17), skin, out, 5), op=0)
        peace = n('hand' + side + '_peace', (cx, cy), capsule((cx - 6, cy + 2), (cx - 9, cy + 30), 9, skin, out, 4) + capsule((cx + 6, cy + 2), (cx + 10, cy + 29), 9, skin, out, 4)
                  + outlined(circle(cx, cy, 14), skin, out, 5), op=0)
        point = n('hand' + side + '_point', (cx, cy), capsule((cx, cy + 4), (cx, cy + 30), 9, skin, out, 4) + outlined(circle(cx, cy, 14), skin, out, 5), op=0)
        kids = [fist, opn, peace, point]
        return n('hand' + side, (cx, wy), [], kids)
    def arm(side, sh):
        sx, sy = sh
        h = hand(side, sx, sy + 38)
        a = n('arm' + side, sh, capsule((sx, sy), (sx, sy + 36), 25, suit, out, OW / 2 + 0.5), [h], rot=(22 if side == 'L' else -22))
        return a, h
    armL, handL = arm('L', (213, 356)); armR, handR = arm('R', (299, 356))
    if props:
        # shuriken held between fingers (child of right hand, drawn under the fingers)
        shR = n('shurikenHand', (299, 432), shuriken_prims(299, 432, 22, C), scale=(0, 0), op=0)
        sw = n('swordHand', (299, 400), sword_prims(299, 400, C, length=150, angle=-90), op=0)
        handR.children = [shR, sw] + handR.children
    lp = capsule((318, 424), (232, 440), 30, suit, out, OW / 2 + 0.5) + outlined(ellipse(224, 441, 14, 9), skin, out, 4.5) + [Prim(line((212, 448), (236, 448)), stroke=red, w=5)]
    lp += capsule((194, 424), (280, 440), 30, suit, out, OW / 2 + 0.5) + outlined(ellipse(288, 441, 14, 9), skin, out, 4.5) + [Prim(line((276, 448), (300, 448)), stroke=red, w=5)]
    lap = n('lap', (256, 436), lp, op=0)
    spin = n('spin', (256, 380), [], [s1, legL, legR, torso, lap, head, armL, armR])
    root = n('root', (256, GROUND), [], [spin])
    return root

def shuriken_prims(cx, cy, R, C):
    return [Prim(star4(cx, cy, R, R * 0.36), fill=C['steel'], stroke=C['out'], w=4.5), Prim(circle(cx, cy, R * 0.26), fill=C['steel_dk'], stroke=C['out'], w=3.5)]
def sword_prims(gx, gy, C, length=150, angle=-90):
    """bokken: grip centred at (gx,gy), blade pointing along angle (deg, -90 = up)"""
    a = math.radians(angle); dx, dy = math.cos(a), math.sin(a)
    tip = (gx + dx * length, gy + dy * length); pommel = (gx - dx * 26, gy - dy * 26); guard = (gx + dx * 18, gy + dy * 18)
    p = capsule(guard, tip, 13, C['wood'], C['out'], 4.5)
    p += capsule(pommel, guard, 14, C['wood_dk'], C['out'], 4.5)
    p += [Prim(ellipse(guard[0], guard[1], 13, 13), fill=C['out'])]
    return p
def scroll_node(pre, C):
    return None

def build_effects(C=None):
    C = C or {k: hexc(v) for k, v in PAL.items()}
    out = C['out']
    E = []
    def puff(name, r=1.0, col=None):
        col = col or C['smoke']
        cs = [(0, -4, 22), (-22, 6, 17), (22, 6, 18), (-11, 16, 15), (12, 17, 15), (-4, -20, 14), (16, -14, 13), (-19, -12, 12)]
        prims = [Prim(circle(x * r, y * r, (rr + 5) * r), fill=out) for x, y, rr in cs] + [Prim(circle(x * r, y * r, rr * r), fill=col) for x, y, rr in cs]
        prims += [Prim(circle(-8 * r, -10 * r, 7 * r), fill=C['white'])]
        return Node(name, (0, 0), prims, scale=(0, 0), op=0)
    for k in range(4): E.append(puff(f'smoke{k}', 1.0 + 0.25 * (k % 2)))
    for k in range(2): E.append(puff(f'dust{k}', 0.62))
    E.append(Node('bigsmoke', (0, 0), [Prim(circle(x, y, r + 6), fill=out) for x, y, r in BIG] + [Prim(circle(x, y, r), fill=C['smoke']) for x, y, r in BIG]
                  + [Prim(circle(x - r * 0.3, y - r * 0.32, r * 0.32), fill=C['white']) for x, y, r in BIG[:5]], scale=(0, 0), op=0))
    for k in range(3):
        E.append(Node(f'spark{k}', (0, 0), [Prim(star4(0, 0, 15, 4.5), fill=C['white'], stroke=out, w=4)], scale=(0, 0), op=0))
    for k in range(3):
        E.append(Node(f'star{k}', (0, 0), [Prim(star5(0, 0, 20, 9), fill=C['star'], stroke=out, w=4)], scale=(0, 0), op=0))
    for k in range(3):
        E.append(Node(f'heart{k}', (0, 0), [Prim(heart(0, 0, 13), fill=C['red'], stroke=out, w=4), Prim(circle(-5, -6, 2.6), fill=C['white'])], scale=(0, 0), op=0))
    zz = lambda s: Path([(-8 * s, -8 * s), (8 * s, -8 * s), (-8 * s, 8 * s), (8 * s, 8 * s)], closed=False)
    for k in range(3):
        E.append(Node(f'z{k}', (0, 0), [Prim(zz(1.0), stroke=out, w=10), Prim(zz(1.0), stroke=C['white'], w=4.5)], scale=(0, 0), op=0))
    E.append(Node('exclaim', (0, 0), [Prim(smooth([(-6, -30), (6, -30), (4, 2), (-4, 2)], corners={0, 1, 2, 3}), fill=C['red'], stroke=out, w=4.5),
                                      Prim(circle(0, 13, 6), fill=C['red'], stroke=out, w=4.5)], scale=(0, 0), op=0))
    qm = Path([(-11, -16), (0, -27), (11, -15), (0, -3), (0, 4)], [(0, 0), (-8, 0), (0, -7), (5, -4), (0, 0)], [(0, -6), (8, 0), (0, 7), (-1, 3), (0, 0)], closed=False)
    E.append(Node('question', (0, 0), [Prim(qm, stroke=out, w=11), Prim(qm, stroke=C['white'], w=5), Prim(circle(0, 15, 6), fill=C['white'], stroke=out, w=3.5)], scale=(0, 0), op=0))
    # speed lines (group of 4)
    sl = []
    for y, x0, L in [(-36, 0, 46), (-12, 18, 60), (12, 4, 40), (36, 22, 52)]:
        sl += [Prim(line((x0, y), (x0 + L, y)), stroke=out, w=11), Prim(line((x0, y), (x0 + L, y)), stroke=C['white'], w=4)]
    E.append(Node('speed', (0, 0), sl, scale=(0, 0), op=0))
    E.append(Node('speed2', (0, 0), sl, scale=(0, 0), op=0))
    # swoosh crescent (spin kick)
    sw = smooth([(-92, 10), (-60, -46), (0, -70), (62, -50), (96, 4), (70, -24), (0, -46), (-58, -22)], corners={0, 4}, t=1 / 6)
    E.append(Node('swoosh', (0, 0), [Prim(sw, fill=C['white'], stroke=out, w=5)], scale=(0, 0), op=0))
    E.append(Node('swoosh2', (0, 0), [Prim(sw, fill=C['white'], stroke=out, w=5)], scale=(0, 0), op=0))
    # shuriken (free), pebble, thought bubble with onigiri, scroll, aura flames
    E.append(Node('shuriken', (0, 0), shuriken_prims(0, 0, 22, C), scale=(0, 0), op=0))
    E.append(Node('pebble', (0, 0), [Prim(smooth([(-9, 2), (-6, -6), (4, -7), (10, 0), (5, 6), (-5, 6)]), fill=hexc('#a7a3b2'), stroke=out, w=4)], scale=(0, 0), op=0))
    oni = [Prim(smooth([(0, -26), (24, 14), (16, 22), (-16, 22), (-24, 14)], t=1 / 5), fill=C['rice'], stroke=out, w=4.5),
           Prim(rrect(-12, 6, 24, 17, 3), fill=C['nori'], stroke=out, w=3.5)]
    bub = [Prim(circle(-62, 52, 7), fill=C['white'], stroke=out, w=4), Prim(circle(-46, 34, 10), fill=C['white'], stroke=out, w=4)]
    cloud = [(0, 0, 38), (-28, 6, 26), (28, 6, 27), (-14, -22, 24), (16, -22, 24)]
    bub += [Prim(circle(x, y, r + 4.5), fill=out) for x, y, r in cloud] + [Prim(circle(x, y, r), fill=C['white']) for x, y, r in cloud]
    E.append(Node('thought', (0, 0), bub + [Prim(p.path, p.fill, p.stroke, p.w) for p in oni], scale=(0, 0), op=0))
    # scroll: top roller + paper (scales down from roller) + bottom roller
    paper = Node('scroll_paper', (0, 0), outlined(rrect(-46, 0, 92, 96, 4), C['paper'], out, 4.5) +
                 [Prim(smooth([(-6, 18), (6, 18), (4, 58), (-4, 58)], corners={0, 1, 2, 3}), fill=C['red'], stroke=out, w=4), Prim(circle(0, 72, 6), fill=C['red'], stroke=out, w=4)],
                 scale=(100, 0))
    rb = Node('scroll_bottom', (0, 0), capsule((-54, 0), (54, 0), 12, C['wood'], out, 4))
    rt = capsule((-54, 0), (54, 0), 12, C['wood'], out, 4)
    E.append(Node('scroll', (0, 0), rt, [paper, rb], scale=(0, 0), op=0, cfirst=True))
    fl = lambda cx, cy, s, rot: smooth([(cx + x * s, cy + y * s) for x, y in [(0, -1.3), (0.42, -0.55), (0.62, 0.15), (0.45, 0.65), (0, 0.8), (-0.45, 0.65), (-0.62, 0.15), (-0.32, -0.42)]], corners={0})
    flames = []
    for k, (x, y, s) in enumerate([(-118, -70, 58), (118, -70, 58), (-104, -170, 52), (104, -170, 52), (0, -268, 56), (-120, 24, 46), (120, 24, 46)]):
        flames.append(Node(f'flame{k}', (x, y + 30 * s / 40), [Prim(fl(x, y, s, 0), fill=C['red'], stroke=out, w=5), Prim(fl(x, y + 10 * s / 40, s * 0.5, 0), fill=hexc('#ff8a6a'))]))
    E.append(Node('aura', (0, 0), [], flames, scale=(0, 0), op=0))
    return {e.name: e for e in E}

BIG = [(0, 0, 70), (-58, 22, 50), (58, 22, 52), (-34, 64, 44), (36, 66, 44), (-40, -46, 44), (42, -44, 42), (0, -70, 40), (-80, -20, 34), (82, -16, 34), (0, 70, 40)]

def build_scene(clones=False):
    fx = build_effects()
    C = {k: hexc(v) for k, v in PAL.items()}
    shadow = Node('shadow', (256, 473), [Prim(ellipse(256, 473, 66, 9), fill=(0, 0, 0), fop=22)])
    char = build_character()
    kids = [fx['aura'], shadow]
    if clones:
        g1 = build_character('c1_', GHOST, props=False); g2 = build_character('c2_', GHOST, props=False)
        g1.o0 = 0; g2.o0 = 0
        kids += [Node('c1shadow', (256, 473), [Prim(ellipse(256, 473, 60, 8), fill=(0, 0, 0), fop=14)], op=0),
                 Node('c2shadow', (256, 473), [Prim(ellipse(256, 473, 60, 8), fill=(0, 0, 0), fop=14)], op=0), g1, g2]
    behind = ['speed2', 'swoosh2']
    kids += [fx[k] for k in behind]
    kids += [char]
    kids += [v for k, v in fx.items() if k not in behind + ['aura']]
    return Node('scene', (0, 0), [], kids)
