"""Baby-dragon rig. Geometry is authored in the original 800x800 'source' space of the
interactive HTML dragon; the 'stage' bone maps it onto the 512 canvas (scale .512, feet at y~470)."""

OUT = '#2B0E63'      # dragon outline (kept from the original)
RED = '#FF3355'; CREAM = '#FFE0AC'; DARK = '#180838'; WHITE = '#FFFFFF'
FIRE_O = '#FF8521'; FIRE_I = '#FFDE3D'; SHADOW = '#CD8EC9'; TEAR = '#42C2FF'; BLUSH = '#FF8521'
# pastel effect palette
P_PINK = '#FFB3C7'; P_HEART = '#FF8FB1'; P_YELLOW = '#FFE58A'; P_BADGE = '#FFD84D'; P_SMOKE = '#EEE6F7'
P_BLUE = '#A9D8FF'; P_MINT = '#B8F0DC'; P_GEM = '#9EE7FF'; P_GEM2 = '#6CCBF0'; P_ANGER = '#FF6F7D'

SW = 12          # outline width in source units -> ~6.1 px on the 512 canvas
SW_THIN = 8
STAGE = dict(tx=51.2, ty=110.0, s=0.512)   # canvas = tx + s*x ; feet bottom (y~703) -> ~470

def P(d, fill=None, stroke=OUT, sw=SW, op=1.0):
    return dict(k='path', d=d, fill=fill, stroke=stroke, sw=sw, op=op)
def E(cx, cy, rx, ry, fill=None, stroke=OUT, sw=SW, op=1.0):
    return dict(k='ell', cx=cx, cy=cy, rx=rx, ry=ry, fill=fill, stroke=stroke, sw=sw, op=op)
def poly(pts, **kw):
    return P('M ' + ' L '.join(f'{x},{y}' for x, y in pts) + ' Z', **kw)

HEART = 'M 0,14 C -4,10 -16,2 -16,-6 C -16,-13 -10,-17 -5,-17 C -2,-17 0,-14 0,-11 C 0,-14 2,-17 5,-17 C 10,-17 16,-13 16,-6 C 16,2 4,10 0,14 Z'
def heart_at(cx, cy, sc, fill, stroke=OUT, sw=SW_THIN):
    import re
    nums = re.findall(r'-?\d+\.?\d*', HEART)
    it = iter(nums); out = HEART
    pts = []
    toks = re.split(r'(-?\d+\.?\d*)', HEART)
    res = []; i = 0; xs = True
    for t in toks:
        if re.fullmatch(r'-?\d+\.?\d*', t or ''):
            v = float(t); res.append(f'{(cx + v * sc) if xs else (cy + v * sc):.2f}'); xs = not xs
        else: res.append(t)
    return P(''.join(res), fill=fill, stroke=stroke, sw=sw)

def sparkle_shape(cx, cy, r, fill=P_YELLOW):
    k = 0.18 * r
    d = (f'M {cx},{cy-r} C {cx+k},{cy-k} {cx+k},{cy-k} {cx+r},{cy} C {cx+k},{cy+k} {cx+k},{cy+k} {cx},{cy+r} '
         f'C {cx-k},{cy+k} {cx-k},{cy+k} {cx-r},{cy} C {cx-k},{cy-k} {cx-k},{cy-k} {cx},{cy-r} Z')
    return P(d, fill=fill, sw=SW_THIN)

def puff(cx, cy, r, fill=P_SMOKE):
    # small cloud of three bumps
    d = (f'M {cx-r},{cy+r*0.35} C {cx-r*1.25},{cy-r*0.25} {cx-r*0.6},{cy-r*0.75} {cx-r*0.2},{cy-r*0.5} '
         f'C {cx},{cy-r*1.1} {cx+r*0.9},{cy-r*1.0} {cx+r*0.75},{cy-r*0.2} C {cx+r*1.3},{cy-r*0.1} {cx+r*1.25},{cy+r*0.7} {cx+r*0.7},{cy+r*0.7} '
         f'L {cx-r*0.6},{cy+r*0.7} C {cx-r*1.0},{cy+r*0.72} {cx-r*1.1},{cy+r*0.5} {cx-r},{cy+r*0.35} Z')
    return P(d, fill=fill, sw=SW_THIN)

def zee(cx, cy, s):
    pts = [(-1, -1), (1, -1), (1, -0.6), (-0.35, 0.6), (1, 0.6), (1, 1), (-1, 1), (-1, 0.6), (0.35, -0.6), (-1, -0.6)]
    return poly([(cx + x * s, cy + y * s) for x, y in pts], fill=P_BLUE, sw=SW_THIN)

# ---------------------------------------------------------------- bones
# name: (parent, pivot)
BONES = {
    'stage':   (None, (0, 0)),
    'shadow_b': ('stage', (400, 712)),
    'grab':    ('stage', (400, 175)),
    'root':    ('grab', (400, 450)),
    'legL':    ('root', (330, 628)),
    'legR':    ('root', (470, 628)),
    'body':    ('root', (400, 702)),
    'tail_b':  ('body', (452, 640)),
    'tailF_b': ('body', (450, 690)),
    'wingL':   ('body', (332, 522)),
    'wingR':   ('body', (468, 522)),
    'head':    ('body', (400, 505)),
    'hornL':   ('head', (262, 248)),
    'hornR':   ('head', (538, 248)),
    'eyeL':    ('head', (280, 350)),
    'eyeR':    ('head', (520, 350)),
    'lidL':    ('head', (280, 350)),
    'lidR':    ('head', (520, 350)),
    'cheekL':  ('head', (240, 412)),
    'cheekR':  ('head', (560, 412)),
    'mouth':   ('head', (400, 418)),
    'armL':    ('body', (324, 505)),
    'armR':    ('body', (476, 505)),
}

# ---------------------------------------------------------------- drawables (z-order bottom -> top)
# name: (bone, [shapes], default_opacity)
D = []
def dr(name, bone, shapes, vis=1):
    D.append((name, bone, shapes, vis))

dr('shadow', 'shadow_b', [E(400, 712, 150, 22, fill=SHADOW, stroke=None, op=0.7)])
dr('tail', 'tail_b', [P('M 452,600 C 600,600 680,720 620,740 C 580,750 520,680 432,660 Z', fill=RED),
                      poly([(540, 650), (570, 620), (590, 660)], fill=CREAM),
                      poly([(600, 690), (640, 670), (630, 710)], fill=CREAM)])
dr('wingL', 'wingL', [P('M 332,522 C 222,462 152,482 142,532 C 182,562 212,552 222,522 C 242,572 272,582 302,552 Z', fill=CREAM),
                      P('M 332,522 C 222,462 152,482 142,532 C 192,452 272,462 342,522 Z', fill=RED)])
dr('wingR', 'wingR', [P('M 468,522 C 578,462 648,482 658,532 C 618,562 588,552 578,522 C 558,572 528,582 498,552 Z', fill=CREAM),
                      P('M 468,522 C 578,462 648,482 658,532 C 608,452 528,462 458,522 Z', fill=RED)])
dr('legL', 'legL', [P('M 312,620 C 282,620 272,670 292,690 C 312,710 362,700 362,670 Z', fill=RED),
                    P('M 298,680 L 306,689 M 316,685 L 324,694 M 334,681 L 342,690', stroke=OUT, sw=SW_THIN)])
dr('legR', 'legR', [P('M 488,620 C 518,620 528,670 508,690 C 488,710 438,700 438,670 Z', fill=RED),
                    P('M 502,680 L 494,689 M 484,685 L 476,694 M 466,681 L 458,690', stroke=OUT, sw=SW_THIN)])
dr('body', 'body', [P('M 330,480 C 280,580 320,670 370,670 L 430,670 C 480,670 520,580 470,480 Z', fill=RED),
                    P('M 355,500 C 330,570 350,650 380,650 L 420,650 C 450,650 470,570 445,500 Z', fill=CREAM, sw=SW_THIN)])
dr('tail_front', 'tailF_b', [P('M 470,655 C 560,660 585,715 520,728 C 450,742 350,738 286,716 C 276,712 280,702 292,703 '
                               'C 350,712 440,714 492,700 C 520,692 515,676 470,676 Z', fill=RED),
                             poly([(520, 662), (548, 640), (556, 674)], fill=CREAM)], vis=0)
dr('hornL', 'hornL', [P('M 280,240 C 240,150 190,130 190,130 C 190,130 200,200 240,260 Z', fill=RED),
                      P('M 265,230 C 235,160 210,145 210,145 C 210,145 215,195 245,240 Z', fill=CREAM, sw=SW_THIN)])
dr('hornR', 'hornR', [P('M 520,240 C 560,150 610,130 610,130 C 610,130 600,200 560,260 Z', fill=RED),
                      P('M 535,230 C 565,160 590,145 590,145 C 590,145 585,195 555,240 Z', fill=CREAM, sw=SW_THIN)])
dr('head', 'head', [P('M 400,160 C 570,160 630,240 630,370 C 630,480 520,510 400,510 C 280,510 170,480 170,370 C 170,240 230,160 400,160 Z', fill=RED),
                    poly([(400, 150), (415, 175), (400, 195), (385, 175)], fill=CREAM, sw=SW_THIN),
                    poly([(400, 205), (415, 230), (400, 250), (385, 230)], fill=CREAM, sw=SW_THIN),
                    poly([(400, 260), (415, 285), (400, 305), (385, 285)], fill=CREAM, sw=SW_THIN)])
dr('cheekL', 'cheekL', [E(240, 412, 30, 15, fill=BLUSH, stroke=None, op=0.4)])
dr('cheekR', 'cheekR', [E(560, 412, 30, 15, fill=BLUSH, stroke=None, op=0.4)])

def eye_open(cx, cy, side):
    hx = 15 if side == 'L' else -15
    return [E(cx, cy, 45, 45, fill=DARK, stroke=None), E(cx + hx, cy - 20, 18, 18, fill=WHITE, stroke=None),
            E(cx - (20 if side == 'L' else -20), cy + 15, 8, 8, fill=WHITE, stroke=None)]
dr('eye_open_L', 'eyeL', eye_open(280, 350, 'L'))
dr('eye_open_R', 'eyeR', eye_open(520, 350, 'R'))
# eyelid variants (stroke-only, drawn in head space)
def arc(x0, y0, cx, cy, x1, y1, sw=SW + 2): return P(f'M {x0},{y0} Q {cx},{cy} {x1},{y1}', stroke=DARK, sw=sw)
dr('eye_closed_L', 'head', [arc(242, 345, 280, 392, 318, 345)], vis=0)      # sleepy  U
dr('eye_closed_R', 'head', [arc(482, 345, 520, 392, 558, 345)], vis=0)
dr('eye_happy_L', 'head', [arc(242, 368, 280, 312, 318, 368)], vis=0)       # happy  ^
dr('eye_happy_R', 'head', [arc(482, 368, 520, 312, 558, 368)], vis=0)
dr('eye_squint_L', 'head', [P('M 250,322 L 308,350 L 250,378', stroke=DARK, sw=SW + 2)], vis=0)   # >
dr('eye_squint_R', 'head', [P('M 550,322 L 492,350 L 550,378', stroke=DARK, sw=SW + 2)], vis=0)   # <
dr('eye_wink_L', 'head', [arc(240, 358, 280, 330, 320, 358), P('M 236,352 L 222,340', stroke=DARK, sw=SW_THIN)], vis=0)
dr('eye_wink_R', 'head', [arc(480, 358, 520, 330, 560, 358), P('M 564,352 L 578,340', stroke=DARK, sw=SW_THIN)], vis=0)
dr('eye_heart_L', 'eyeL', [heart_at(280, 352, 3.0, '#FF5C8A', sw=SW_THIN)], vis=0)
dr('eye_heart_R', 'eyeR', [heart_at(520, 352, 3.0, '#FF5C8A', sw=SW_THIN)], vis=0)
# half-closing lids: red dome whose lower edge is a lid line; slides down via the lid bones
dr('lid_L', 'lidL', [P('M 226,300 L 334,300 L 334,212 L 226,212 Z', fill=RED, stroke=None),
                     P('M 228,300 Q 280,292 332,300', stroke=OUT, sw=SW)], vis=0)
dr('lid_R', 'lidR', [P('M 466,300 L 574,300 L 574,212 L 466,212 Z', fill=RED, stroke=None),
                     P('M 468,300 Q 520,292 572,300', stroke=OUT, sw=SW)], vis=0)
dr('brow_sad_L', 'head', [P('M 236,298 Q 278,290 318,268', stroke=DARK, sw=SW)], vis=0)
dr('brow_sad_R', 'head', [P('M 564,298 Q 522,290 482,268', stroke=DARK, sw=SW)], vis=0)
dr('brow_angry_L', 'head', [P('M 238,270 Q 282,276 322,300', stroke=DARK, sw=SW)], vis=0)
dr('brow_angry_R', 'head', [P('M 562,270 Q 518,276 478,300', stroke=DARK, sw=SW)], vis=0)
dr('nose', 'head', [E(385, 390, 3.5, 5, fill=DARK, stroke=None), E(415, 390, 3.5, 5, fill=DARK, stroke=None)])
# mouths
dr('mouth_smile', 'mouth', [P('M 378,408 Q 400,434 422,408', stroke=DARK, sw=SW - 2)])
dr('mouth_open', 'mouth', [P('M 366,408 C 366,458 434,458 434,408 Z', fill=DARK, sw=SW - 2),
                           P('M 381,430 C 381,456 419,456 419,430 Z', fill=RED, stroke=None)], vis=0)
dr('mouth_o', 'mouth', [E(400, 420, 12, 15, fill=DARK, sw=SW - 2)], vis=0)
dr('mouth_yawn', 'mouth', [E(400, 428, 30, 38, fill=DARK, sw=SW - 2), E(400, 450, 17, 10, fill=RED, stroke=None),
                           poly([(379, 394), (390, 394), (384.5, 407)], fill=WHITE, stroke=None),
                           poly([(410, 394), (421, 394), (415.5, 407)], fill=WHITE, stroke=None)], vis=0)
dr('mouth_frown', 'mouth', [P('M 380,426 Q 400,404 420,426', stroke=DARK, sw=SW - 2)], vis=0)
dr('mouth_puff', 'mouth', [P('M 386,414 Q 393,408 400,414 Q 407,420 414,414', stroke=DARK, sw=SW - 4)], vis=0)
# belly flame marking (kept from the original design) and front paws
dr('flame', 'body', [P('M 400,472 C 428,496 428,542 400,542 C 372,542 372,496 400,472 Z', fill=FIRE_O, sw=SW),
                     P('M 400,492 C 414,511 414,533 400,533 C 386,533 386,511 400,492 Z', fill=FIRE_I, stroke=None)])
dr('armL', 'armL', [P('M 322,490 C 272,520 282,570 312,580 C 342,590 362,550 347,520 Z', fill=RED)])
dr('armR', 'armR', [P('M 478,490 C 528,520 518,570 488,580 C 458,590 438,550 453,520 Z', fill=RED)])

DEFAULT_VIS = {n: v for n, _, _, v in D}

# ---------------------------------------------------------------- effects (added per clip; bone created on the fly)
# kind -> (shape list centred at (0,0))
def effect_shapes(kind):
    if kind == 'heart':   return [heart_at(0, 0, 2.3, P_HEART)]
    if kind == 'sparkle': return [sparkle_shape(0, 0, 28)]
    if kind == 'z':       return [zee(0, 0, 20)]
    if kind == 'smoke':   return [puff(0, 0, 22)]
    if kind == 'ring':    return [E(0, 0, 15, 11, stroke='#B9A8D6', sw=7)]
    if kind == 'heart_smoke': return [heart_at(0, 0, 2.2, '#F6D7EC', stroke='#B9A8D6', sw=7)]
    if kind == 'tear':    return [P('M 0,-22 C 15,3 15,23 0,23 C -15,23 -15,3 0,-22 Z', fill=TEAR, sw=SW_THIN)]
    if kind == 'exclaim': return [P('M -9,-44 L 9,-44 L 6,8 L -6,8 Z', fill=P_BADGE, sw=SW_THIN), E(0, 26, 10, 10, fill=P_BADGE, sw=SW_THIN)]
    if kind == 'anger':
        a = []
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            a.append(P(f'M {6*sx},{22*sy} Q {8*sx},{8*sy} {22*sx},{6*sy}', stroke=P_ANGER, sw=7))
        return a
    if kind == 'badge':
        return [E(0, 0, 44, 44, fill=P_BADGE, sw=SW_THIN), P('M -7,-27 L 7,-27 L 5,8 L -5,8 Z', fill=DARK, stroke=None), E(0, 21, 7.5, 7.5, fill=DARK, stroke=None)]
    if kind == 'bubble':
        return [E(-62, 82, 9, 9, fill=WHITE, sw=SW_THIN), E(-40, 56, 13, 13, fill=WHITE, sw=SW_THIN),
                P('M -40,10 C -62,10 -66,-22 -44,-28 C -44,-52 -10,-60 2,-42 C 16,-62 54,-54 52,-28 C 74,-24 72,10 50,12 '
                  'C 44,30 16,34 6,20 C -6,34 -34,30 -40,10 Z', fill=WHITE, sw=SW_THIN)]
    if kind == 'gem':
        return [poly([(-24, -8), (-12, -22), (12, -22), (24, -8), (0, 24)], fill=P_GEM, sw=6),
                P('M -24,-8 L 24,-8 M -12,-22 L -6,-8 L 0,24 M 12,-22 L 6,-8 L 0,24', stroke='#4FA9D6', sw=4),
                poly([(-12, -18), (-4, -18), (-8, -10)], fill=WHITE, stroke=None)]
    if kind == 'swirl':   # dizzy star
        return [sparkle_shape(0, 0, 14, fill=P_MINT)]
    raise KeyError(kind)
