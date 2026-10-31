"""Red panda chibi rig: palette, parts, node tree and layer stack.

All shapes are authored in *character space* at 100% scale: ground at y=0, centre x=0,
y grows downward. The root node maps character space onto the 512x512 canvas
(translate 256,470, scale 0.8), so a 7.5-unit outline renders at 6px.
"""
from geom import ellipse, circle, smooth, poly, svgpath, xform, mirror_x
import math

# ---------------------------------------------------------------- palette
O = "#3d2218"        # outline, dark brown
RUST = "#e27440"     # main fur
RUST_D = "#c65a2f"   # inner ear
GINGER = "#f8c58e"   # pale-ginger tail rings
CREAM = "#fff1dc"    # face mask
WHITE = "#fffbf4"    # brow marks, ear rims
TEAR = "#9a432b"     # tear tracks
LIMB = "#7a4636"     # legs / arms
BELLY = "#94553e"    # belly
EYE = "#3a1f17"
BLUSH = "#f8a3a0"
MOUTH_IN = "#8f3a33"
TONGUE = "#ff9393"
BARK = "#a86a42"
BARK_D = "#7f4c2d"
WOOD = "#efc99a"
LEAF = "#9fcf6a"
LEAF_D = "#6fa645"
BAMBOO = "#acd57c"
BAMBOO_D = "#7cb253"
BAMBOO_TOP = "#dcefbf"
HEART = "#ff8ba1"
GOLD = "#ffd56b"
WATER = "#a9d9f2"
STEAM = "#fff6ec"

SW = 7.5   # main outline (6px on canvas)
SWD = 6.0  # detail lines
SWF = 4.5  # fine lines


def S(path, fill=None, stroke=None, width=SW, fo=1.0, strokes=None):
    """A drawable: path + fill + one or more strokes (drawn in order)."""
    st = []
    if stroke:
        st.append((stroke, width))
    if strokes:
        st.extend(strokes)
    return {"path": path, "fill": fill, "fo": fo, "strokes": st}


# ---------------------------------------------------------------- nodes
class Node:
    def __init__(self, name, parent, pivot, pos=None, rot=0.0, scale=(1.0, 1.0)):
        self.name, self.parent, self.pivot = name, parent, tuple(pivot)
        self.pos = tuple(pos) if pos is not None else tuple(pivot)
        self.rot, self.scale = rot, tuple(scale)


J = [(62, -32), (100, -30), (164, -52), (186, -112)]  # tail joints
TAIL_TIP = (186, -152)

NODES = {}


def node(name, parent, pivot, **kw):
    NODES[name] = Node(name, parent, pivot, **kw)


node("root", None, (0, 0), pos=(256, 470), scale=(0.8, 0.8))
node("shadow", "root", (40, 2))
node("branch", "root", (0, -112))
node("lift", "root", (0, -335))
node("char", "lift", (0, -150))
node("squash", "char", (0, 0))
node("legL", "squash", (-46, -12))
node("legR", "squash", (46, -12))
node("torso", "squash", (0, -10))
node("body", "torso", (0, -10))
node("head", "torso", (0, -165))
node("earL", "head", (-88, -318))
node("earR", "head", (88, -318))
node("eyes", "head", (0, -262))
node("eyeL", "eyes", (-58, -262))
node("eyeR", "eyes", (58, -262))
node("brows", "head", (0, -305))
node("mouth", "head", (0, -192))
node("cheekL", "head", (-98, -208))
node("cheekR", "head", (98, -208))
node("armL", "torso", (-50, -128))
node("armR", "torso", (50, -128))
node("tail0", "torso", J[0])
node("tail1", "tail0", J[1])
node("tail2", "tail1", J[2])
node("tail3", "tail2", J[3])
node("bamboo", "torso", (0, -140))
node("flag", "armR", (44, -72))

# ---------------------------------------------------------------- parts
HEAD_PTS = [(0, -350), (66, -344), (113, -320), (136, -281), (140, -238), (147, -205), (120, -182),
            (68, -164), (0, -158), (-68, -164), (-120, -182), (-147, -205), (-140, -238), (-136, -281),
            (-113, -320), (-66, -344)]
HEAD = smooth(HEAD_PTS)


def face_mask():
    """Cream lower face. Its outer edge re-uses the head's exact bezier segments
    (vertices 4..12) so it meets the outline with no gap and no overshoot."""
    h = HEAD[0]
    a, b = 4, 12
    v = h["v"][a:b + 1]
    i = h["i"][a:b + 1]
    o = h["o"][a:b + 1]
    inner = [(-114, -240), (-86, -233), (-62, -230), (-34, -233), (0, -241), (34, -233), (62, -230),
             (86, -233), (114, -240)]
    seq = [v[-1]] + inner + [v[0]]
    tan = []
    for k in range(len(seq)):
        p0 = seq[max(k - 1, 0)]
        p1 = seq[min(k + 1, len(seq) - 1)]
        tan.append(((p1[0] - p0[0]) / 6, (p1[1] - p0[1]) / 6))
    o = list(o)
    i = list(i)
    o[-1] = tan[0]
    vv = list(v) + inner
    ii = i + [(-t[0], -t[1]) for t in tan[1:-1]]
    oo = o + [t for t in tan[1:-1]]
    ii[0] = (-tan[-1][0], -tan[-1][1])
    return [{"v": vv, "i": ii, "o": oo, "c": True}]


def ear(side):
    s = -1 if side == "L" else 1
    cx, cy = 104 * s, -336
    rot = 15 * s
    parts = [
        S(ellipse(cx, cy, 44, 46, rot), WHITE, O),
        S(ellipse(cx - 2 * s, cy + 6, 30, 31, rot), RUST_D),
        S(smooth([(cx - 26 * s, cy + 14), (cx - 16 * s, cy - 2), (cx - 8 * s, cy + 8), (cx + 0 * s, cy - 10),
                  (cx + 8 * s, cy + 6), (cx + 17 * s, cy - 3), (cx + 25 * s, cy + 16), (cx, cy + 34)]), CREAM),
    ]
    return parts


def head_base():
    sh = [S(HEAD, RUST)]
    sh.append(S(face_mask(), CREAM))
    for s in (-1, 1):
        sh.append(S(ellipse(52 * s, -303, 21, 12, 12 * s * -1), WHITE))
    for s in (-1, 1):
        sh.append(S(svgpath(f"M{62*s} -236 Q{50*s} -206 {30*s} -188"), None, TEAR, 13))
    sh.append(S(HEAD, None, O))
    # little fur tufts on the forehead
    sh.append(S(svgpath("M-14 -342 Q-8 -330 0 -336 Q8 -330 14 -342"), None, O, SWF))
    return sh


def nose():
    return [S(svgpath("M-12 -216 C-12 -223 12 -223 12 -216 C12 -210 4 -205 0 -205 C-4 -205 -12 -210 -12 -216 Z"), EYE, O, 3),
            S(ellipse(-4, -217, 3.2, 2), WHITE)]


def eye_open(cx, cy):
    return [S(ellipse(cx, cy, 21, 25), EYE),
            S(circle(cx - 6, cy - 9, 7.5), WHITE),
            S(circle(cx + 7, cy + 8, 3.6), WHITE)]


def eye_closed(cx, cy):
    return [S(svgpath(f"M{cx-18} {cy-2} Q{cx} {cy+16} {cx+18} {cy-2}"), None, O, 6.5)]


def eye_happy(cx, cy):
    return [S(svgpath(f"M{cx-18} {cy+8} Q{cx} {cy-16} {cx+18} {cy+8}"), None, O, 6.5)]


def eye_squint(cx, cy, s):
    # s=-1 left eye draws ">", s=1 right eye draws "<"
    return [S(poly([(cx + 13 * s, cy - 13), (cx - 12 * s, cy), (cx + 13 * s, cy + 13)]), None, O, 6.5)]


def eye_wink(cx, cy):
    return [S(svgpath(f"M{cx-19} {cy+2} Q{cx} {cy-14} {cx+19} {cy+2}"), None, O, 6.5),
            S(svgpath(f"M{cx+17} {cy} L{cx+25} {cy-6}"), None, O, 5)]


def eye_shock(cx, cy):
    return [S(ellipse(cx, cy, 22, 26), WHITE, O, 5.5),
            S(ellipse(cx, cy + 1, 9, 11), EYE),
            S(circle(cx - 3, cy - 3, 3), WHITE)]


HEART_D = "M0 10 C-4 6 -16 0 -16 -7 C-16 -13 -11 -16 -7 -16 C-3 -16 -1 -13 0 -11 C1 -13 3 -16 7 -16 C11 -16 16 -13 16 -7 C16 0 4 6 0 10 Z"


def eye_heart(cx, cy):
    return [S(xform(svgpath(HEART_D), cx, cy + 2, sx=1.55), HEART, O, 5),
            S(ellipse(cx - 11, cy - 10, 4, 3, -30), WHITE)]


def spiral(cx, cy, r, turns=2.2, n=26, s=1):
    pts = []
    for k in range(n):
        t = k / (n - 1)
        a = s * t * turns * 2 * math.pi
        rr = r * (0.12 + 0.88 * t)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return smooth(pts, closed=False)


def eye_swirl(cx, cy, s):
    return [S(spiral(cx, cy, 19, s=s), None, O, 5)]


def brows_worried():
    out = []
    for s in (-1, 1):
        out.append(S(svgpath(f"M{76*s} -296 Q{58*s} -304 {38*s} -314"), None, O, 6.5))
    return out


def brows_angry():
    out = []
    for s in (-1, 1):
        out.append(S(svgpath(f"M{78*s} -314 Q{60*s} -306 {36*s} -292"), None, O, 7))
    return out


def mouth_smile():
    return [S(svgpath("M0 -205 L0 -198 M-15 -200 Q-8 -189 0 -198 Q8 -189 15 -200"), None, O, 5.5)]


def mouth_tongue():
    return [S(svgpath("M-21 -200 Q0 -195 21 -200 C21 -180 11 -168 0 -168 C-11 -168 -21 -180 -21 -200 Z"), MOUTH_IN),
            S(svgpath("M-12 -175 C-12 -186 12 -186 12 -175 C9 -169 -9 -169 -12 -175 Z"), TONGUE),
            S(svgpath("M-21 -200 Q0 -195 21 -200 C21 -180 11 -168 0 -168 C-11 -168 -21 -180 -21 -200 Z"), None, O, 5.5)]


def mouth_o():
    return [S(ellipse(0, -188, 8, 10), MOUTH_IN, O, 5)]


def fang(x, top, s=1):
    return S(poly([(x - 3.6 * s, top), (x, top + 8.5), (x + 3.6 * s, top - 0.5)], True), WHITE, O, 2.5)


def mouth_yawn():
    return [S(ellipse(0, -183, 20, 21), MOUTH_IN),
            S(svgpath("M-12 -169 C-12 -180 12 -180 12 -169 C8 -164 -8 -164 -12 -169 Z"), TONGUE),
            fang(-8.5, -201.5), fang(8.5, -201.5),
            S(ellipse(0, -183, 20, 21), None, O, 5.5)]


def mouth_frown():
    return [S(svgpath("M-13 -186 Q0 -199 13 -186"), None, O, 5.5)]


def mouth_rawr():
    d = "M-17 -199 Q0 -202 17 -199 C17 -186 9 -179 0 -179 C-9 -179 -17 -186 -17 -199 Z"
    return [S(svgpath(d), MOUTH_IN),
            S(svgpath("M-8 -183 C-8 -189 8 -189 8 -183 C5 -180 -5 -180 -8 -183 Z"), TONGUE),
            fang(-9, -199.5), fang(9, -199.5),
            S(svgpath(d), None, O, 5.5)]


BODY = smooth([(0, -176), (48, -168), (76, -134), (84, -86), (82, -40), (64, -10), (32, 2), (0, 5), (-32, 2),
               (-64, -10), (-82, -40), (-84, -86), (-76, -134), (-48, -168)])
BELLY_P = smooth([(0, -128), (33, -119), (47, -86), (44, -42), (24, -15), (0, -11), (-24, -15), (-44, -42),
                  (-47, -86), (-33, -119)])


def body_parts():
    return [S(BODY, RUST, O), S(BELLY_P, BELLY)]


ARM_L = smooth([(-50, -147), (-65, -140), (-68, -118), (-66, -96), (-63, -81), (-55, -67), (-42, -63), (-29, -69),
                (-24, -83), (-28, -100), (-33, -121), (-36, -141)])


def arm(side):
    p = ARM_L if side == "L" else mirror_x(ARM_L)
    s = -1 if side == "L" else 1
    return [S(p, LIMB, O), S(svgpath(f"M{35*s} -76 Q{39*s} -70 {36*s} -66"), None, O, 3.5)]


def foot(side):
    s = -1 if side == "L" else 1
    return [S(ellipse(46 * s, -13, 29, 17), LIMB, O),
            S(svgpath(f"M{38*s} -7 L{38*s} 1 M{54*s} -7 L{54*s} 1"), None, O, 3.5)]


THIGH_L = smooth([(-46, -126), (-25, -119), (-23, -62), (-25, -16), (-46, -8), (-67, -16), (-69, -62), (-67, -119)])


def thigh(side):
    p = THIGH_L if side == "L" else mirror_x(THIGH_L)
    return [S(p, LIMB, O)]


# tail puffs: centre, angle, rx, ry, colour, segment node
PUFFS = [
    ((80, -33), 3, 30, 32, RUST, "tail0"),
    ((118, -34), -5, 30, 36, GINGER, "tail1"),
    ((150, -46), -30, 30, 37, RUST, "tail1"),
    ((174, -70), -58, 30, 37, GINGER, "tail2"),
    ((186, -102), -80, 29, 35, RUST, "tail2"),
    ((186, -134), -95, 28, 31, GINGER, "tail3"),
]


def puff(k):
    (cx, cy), a, rx, ry, col, _ = PUFFS[k]
    return [S(ellipse(cx, cy, rx, ry, a), col, O)]


LEAF_D_PATH = "M0 0 C10 -12 34 -12 46 0 C34 12 10 12 0 0 Z"


def leaf(x, y, rot, s=1.0):
    return [S(xform(svgpath(LEAF_D_PATH), x, y, rot, s), LEAF, O, 5),
            S(xform(svgpath("M6 0 L38 0"), x, y, rot, s), None, LEAF_D, 3)]


def branch_parts():
    bar = smooth([(-212, -128), (-100, -129), (40, -127), (160, -125), (206, -119), (228, -113), (206, -106),
                  (160, -99), (40, -97), (-100, -96), (-212, -97)], closed=True)
    out = []
    out += [S(xform(svgpath("M0 0 Q6 -16 20 -26"), 128, -124), None, O, 11),
            S(xform(svgpath("M0 0 Q6 -16 20 -26"), 128, -124), None, BARK, 5)]
    out += leaf(146, -150, -40, 1.0)
    out += [S(bar, BARK, O)]
    out += [S(svgpath("M-160 -116 Q-128 -112 -98 -116"), None, BARK_D, 4),
            S(svgpath("M-20 -106 Q14 -103 48 -107"), None, BARK_D, 4),
            S(svgpath("M100 -118 Q126 -115 150 -118"), None, BARK_D, 4)]
    out += [S(ellipse(-212, -112.5, 10, 16), WOOD, O, 6), S(ellipse(-212, -112.5, 4.5, 8), None, BARK_D, 3)]
    out += leaf(-120, -100, 130, 0.9)
    return out


def bamboo_parts(scale=1.0, dx=0, dy=0, rot=0, ox=0, oy=-140):
    def X(p):
        return xform(p, dx, dy, rot, scale, ox=ox, oy=oy)
    out = []
    out += [S(X(xform(svgpath(LEAF_D_PATH), 10, -206, -55, 0.95)), LEAF, O, 5),
            S(X(xform(svgpath(LEAF_D_PATH), -10, -168, -150, 0.85)), LEAF, O, 5)]
    stalk = svgpath("M-12 -228 L12 -228 L12 -62 Q12 -56 0 -56 Q-12 -56 -12 -62 Z")
    out.append(S(X(stalk), BAMBOO, O, 6))
    for y in (-180, -124):
        out.append(S(X(svgpath(f"M-12 {y} L12 {y}")), None, BAMBOO_D, 5))
        out.append(S(X(svgpath(f"M-12 {y} L12 {y}")), None, O, 3))
    out.append(S(X(ellipse(0, -228, 12, 4.5)), BAMBOO_TOP, O, 4.5))
    out.append(S(X(svgpath("M-5 -210 L-5 -190")), None, "#d4ecb0", 3.5))
    return out


def flag_leaf():
    # a bamboo leaf held in the right paw like a little flag
    X = lambda p: xform(xform(p, sx=1.4), 42, -74, 40)
    return [S(X(svgpath("M0 0 C14 -16 52 -22 78 -14 C54 -2 18 6 0 0 Z")), LEAF, O, 5),
            S(X(svgpath("M6 -1 L66 -13")), None, LEAF_D, 3),
            S(X(svgpath("M0 0 L-6 10")), None, O, 5)]


# ---------------------------------------------------------------- layers
class Layer:
    def __init__(self, name, node, shapes, group=None, opts=()):
        self.name, self.node, self.shapes, self.group, self.opts = name, node, shapes, group, set(opts)


GROUP_DEFAULT = {"eyes": "open", "brows": "none", "mouth": "smile", "tail": "back", "branch": "none",
                 "bamboo": "none", "flag": "none"}

EYE_VARIANTS = {
    "open": (lambda c, s: eye_open(*c)),
    "closed": (lambda c, s: eye_closed(*c)),
    "happy": (lambda c, s: eye_happy(*c)),
    "squint": (lambda c, s: eye_squint(c[0], c[1], s)),
    "shock": (lambda c, s: eye_shock(*c)),
    "heart": (lambda c, s: eye_heart(*c)),
    "swirl": (lambda c, s: eye_swirl(c[0], c[1], s)),
}


def build_layers():
    L = []
    add = lambda *a, **k: L.append(Layer(*a, **k))
    add("shadow", "shadow", [S(ellipse(40, 2, 150, 14), O, fo=0.16)])
    add("branch_back", "branch", branch_parts(), "branch", ["back"])
    add("tail_b1", "tail0", puff(0))
    add("tail_b2", "tail1", puff(1), "tail", ["back", "top"])
    for k in range(2, 6):
        add(f"tail_b{k+1}", PUFFS[k][5], puff(k), "tail", ["back"])
    add("thighL", "legL", thigh("L"))
    add("thighR", "legR", thigh("R"))
    add("body", "body", body_parts())
    add("branch_front", "branch", branch_parts(), "branch", ["front"])
    add("footL", "legL", foot("L"))
    add("footR", "legR", foot("R"))
    for k in range(1, 6):
        add(f"tail_f{k+1}", PUFFS[k][5], puff(k), "tail", ["front"])
    add("earL", "earL", ear("L"))
    add("earR", "earR", ear("R"))
    add("head", "head", head_base())
    add("cheekL", "cheekL", [S(ellipse(-98, -208, 17, 10), BLUSH)])
    add("cheekR", "cheekR", [S(ellipse(98, -208, 17, 10), BLUSH)])
    for var, fn in EYE_VARIANTS.items():
        opts = [var] + (["wink"] if var == "open" else [])
        add(f"eyeL_{var}", "eyeL", fn((-58, -262), -1), "eyes", opts)
        add(f"eyeR_{var}", "eyeR", fn((58, -262), 1), "eyes", [var])
    add("eyeR_wink", "eyeR", eye_wink(58, -262), "eyes", ["wink"])
    add("brows_worried", "brows", brows_worried(), "brows", ["worried"])
    add("brows_angry", "brows", brows_angry(), "brows", ["angry"])
    for var, fn in [("smile", mouth_smile), ("tongue", mouth_tongue), ("o", mouth_o), ("yawn", mouth_yawn),
                    ("frown", mouth_frown), ("rawr", mouth_rawr)]:
        add(f"mouth_{var}", "mouth", fn(), "mouth", [var])
    add("nose", "head", nose())
    for k in range(2, 6):
        add(f"tail_t{k+1}", PUFFS[k][5], puff(k), "tail", ["top"])
    add("bamboo", "bamboo", bamboo_parts(), "bamboo", ["held"])
    add("flag", "flag", flag_leaf(), "flag", ["held"])
    add("armL", "armL", arm("L"))
    add("armR", "armR", arm("R"))
    return L


LAYERS = build_layers()
FX_UNDER = "armL"  # fx inserted with z='under_arms' go before this layer


# ---------------------------------------------------------------- fx shapes (authored around 0,0)
def fx_heart(s=1.0):
    return [S(xform(svgpath(HEART_D), sx=s), HEART, O, 4.5), S(ellipse(-8 * s, -9 * s, 3 * s, 2 * s, -30), WHITE)]


def fx_sparkle(s=1.0):
    return [S(xform(svgpath("M0 -14 Q2 -2 14 0 Q2 2 0 14 Q-2 2 -14 0 Q-2 -2 0 -14 Z"), sx=s), GOLD, O, 3.5)]


def fx_star(s=1.0):
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        r = 11 * s if k % 2 == 0 else 5 * s
        pts.append((r * math.cos(a), r * math.sin(a)))
    return [S(poly(pts, True), GOLD, O, 3.2)]


def double_stroke(p, inner=CREAM, wo=9, wi=4):
    return S(p, None, O, wo, strokes=[(inner, wi)])


def fx_z(s=1.0):
    p = xform(poly([(-7, -7), (7, -7), (-7, 7), (7, 7)]), sx=s)
    return [double_stroke(p, CREAM, 8.5 * s ** 0.5 + 1, 3.6 * s ** 0.5)]


def fx_exclaim(s=1.0, inner=GOLD):
    return [double_stroke(xform(poly([(0, -14), (0, 2)]), sx=s), inner, 11, 5),
            S(circle(0, 12 * s, 4.4 * s), inner, O, 3.2)]


def fx_question(s=1.0, inner=CREAM):
    p = xform(svgpath("M-7 -7 C-7 -17 8 -17 8 -8 C8 -2 0 -1 0 5"), sx=s)
    return [double_stroke(p, inner, 10, 4.5), S(circle(0, 13 * s, 4 * s), inner, O, 3)]


DROP_D = "M0 -11 C4 -5 9 0 9 5 C9 10 5 13 0 13 C-5 13 -9 10 -9 5 C-9 0 -4 -5 0 -11 Z"


def fx_drop(s=1.0, rot=0):
    return [S(xform(svgpath(DROP_D), rot=rot, sx=s), WATER, O, 3.5),
            S(xform(ellipse(-3.5, 5, 2.2, 3.2), rot=rot, sx=s), WHITE)]


def cloud_path(w, h, bumps=7, depth=0.18):
    pts = []
    n = bumps * 2
    for k in range(n):
        a = k / n * 2 * math.pi
        r = 1.0 if k % 2 == 0 else 1 - depth
        pts.append((w / 2 * r * math.cos(a), h / 2 * r * math.sin(a)))
    return smooth(pts, k=1.15)


def fx_puff(s=1.0):
    return [S(xform(cloud_path(30, 24, 5, 0.22), sx=s), STEAM, O, 4)]


def fx_crumb(s=1.0, col=BAMBOO):
    return [S(xform(smooth([(-4, -3), (2, -5), (5, 0), (1, 4), (-4, 3)]), sx=s), col, O, 2.6)]


def fx_thought():
    out = [S(xform(circle(0, 0, 5.5), -44, 40), WHITE, O, 4),
           S(xform(circle(0, 0, 8.5), -28, 24), WHITE, O, 4),
           S(cloud_path(96, 72, 8, 0.12), WHITE, O, 4.5)]
    out += bamboo_parts(scale=0.3, dx=0, dy=140 * 1, rot=28, ox=0, oy=-140)
    return out


def fx_badge():
    return [S(circle(0, 0, 24), GOLD, O, 5.5),
            S(poly([(0, -12), (0, 3)]), None, O, 7.5),
            S(circle(0, 11, 4.2), O)]


def fx_leaf(s=1.0):
    return [S(xform(svgpath(LEAF_D_PATH), -23 * s, 0, sx=s), LEAF, O, 4.5),
            S(xform(svgpath("M6 0 L38 0"), -23 * s, 0, sx=s), None, LEAF_D, 2.5)]
