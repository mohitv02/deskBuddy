"""The penguin rig (separate parts, pivots and variants) plus props and effect shapes."""
import math
from collections import OrderedDict
from core import *

# character-local coordinates: feet centre at (0,0), +y down. Root places it at (256,470) x0.8.
ROOT_POS = (256, 470)
ROOT_S = 0.8

EYE_L, EYE_R = (-48, -318), (48, -318)
BEAK_C = (0, -282)

def to_canvas(x, y):
    return (ROOT_POS[0] + x * ROOT_S, ROOT_POS[1] + y * ROOT_S)

# ------------------------------------------------ part geometry
def g_body():
    return path('M0 -240 C72 -240 114 -172 112 -96 C110 -36 64 -6 0 -6 '
                'C-64 -6 -110 -36 -112 -96 C-114 -172 -72 -240 0 -240 Z')

def g_belly():
    return ellipse(0, -94, 76, 80)

def g_foot_l():
    return path('M-80 -14 C-82 -30 -64 -36 -46 -36 C-28 -36 -10 -30 -12 -14 '
                'C-12 -6 -18 -2 -25 -3 C-29 1 -37 1 -41 -3 C-46 1 -54 1 -58 -3 '
                'C-63 1 -71 0 -75 -4 C-79 -6 -80 -10 -80 -14 Z')

def g_tail():
    return path('M70 -44 C92 -40 114 -28 128 -12 C108 -8 86 -12 66 -20 Z')

def g_flipper_l():
    return path('M-86 -182 C-112 -174 -130 -134 -132 -102 C-134 -80 -121 -71 -108 -78 '
                'C-94 -86 -84 -122 -76 -156 C-74 -168 -78 -180 -86 -182 Z')

def g_head():
    return ellipse(0, -312, 142, 124)

def g_patch():
    return path('M0 -206 C-62 -228 -116 -262 -114 -312 C-112 -362 -82 -390 -50 -390 '
                'C-24 -390 -8 -374 0 -354 C8 -374 24 -390 50 -390 C82 -390 112 -362 114 -312 '
                'C116 -262 62 -228 0 -206 Z')

def g_tuft():
    c = path('M-10 -414 C-15 -440 -9 -464 0 -476 C9 -464 15 -440 10 -414 Z')
    l = path('M-16 -412 C-30 -426 -40 -444 -42 -460 C-28 -454 -14 -440 -2 -420 Z')
    return c + l + mirror(l)

def scarf_y(x, base):
    return base - 0.0016 * x * x

def g_scarf_seg(x0, x1, end=None):
    """band segment between x0..x1 following the chin curve. end='l'|'r' rounds the outer end."""
    top, bot = -210, -172
    def q(xa, xb, base):
        ya, yb = scarf_y(xa, base), scarf_y(xb, base)
        sl = -2 * 0.0016 * xa
        qx, qy = (xa + xb) / 2, ya + sl * (xb - xa) / 2
        return f'Q{qx} {qy} {xb} {yb}'
    d = f'M{x0} {scarf_y(x0, top)} ' + q(x0, x1, top)
    if end == 'r':
        yt, yb = scarf_y(x1, top), scarf_y(x1, bot)
        d += f' C{x1 + 14} {yt + 4} {x1 + 14} {yb - 4} {x1} {yb}'
    else:
        d += f' L{x1} {scarf_y(x1, bot)}'
    d += ' ' + q(x1, x0, bot)
    if end == 'l':
        yt, yb = scarf_y(x0, top), scarf_y(x0, bot)
        d += f' C{x0 - 14} {yb - 4} {x0 - 14} {yt + 4} {x0} {yt}'
    d += ' Z'
    return path(d)

def g_scarf_ribs(x0, x1):
    out = []
    x = x0 + 10
    while x < x1 - 6:
        out += path(f'M{x} {scarf_y(x, -203)} L{x - 2} {scarf_y(x, -180)}')
        x += 13
    return out

def g_tail_a():
    body = path('M38 -192 C52 -164 62 -138 66 -110 L94 -114 C88 -142 78 -168 64 -194 Z')
    ribs = path('M54 -170 L72 -174') + path('M60 -148 L82 -152') + path('M64 -128 L88 -132')
    fringe = path('M70 -109 L71 -99') + path('M80 -111 L82 -101') + path('M89 -112 L91 -102')
    return body, ribs, fringe

def g_tail_b():
    body = path('M48 -190 C46 -164 40 -142 30 -120 L56 -112 C64 -138 70 -164 72 -192 Z')
    ribs = path('M46 -168 L68 -166') + path('M42 -146 L62 -142') + path('M36 -128 L58 -122')
    fringe = path('M34 -117 L30 -108') + path('M43 -114 L40 -105') + path('M52 -112 L50 -103')
    return body, ribs, fringe

# eyes (drawn around eye centre)
def eye_open(c):
    x, y = c
    return [F(ellipse(x, y, 22.5, 28), EYE, nm='eye'),
            F(ellipse(x + 7.5, y - 10, 8.5), WHITE, nm='hl1'),
            F(ellipse(x - 8, y + 11, 4), WHITE, nm='hl2')]

def eye_line(d):
    return [L(path(d), EYE, 7, nm='lid')]

def eye_sleepy(c):
    x, y = c
    return eye_line(f'M{x - 18} {y - 2} Q{x} {y + 15} {x + 18} {y - 2}')

def eye_happy(c):
    x, y = c
    return eye_line(f'M{x - 18} {y + 7} Q{x} {y - 15} {x + 18} {y + 7}')

def eye_squint(c, side):
    x, y = c
    s = 1 if side == 'L' else -1
    return eye_line(f'M{x - 12 * s} {y - 13} L{x + 12 * s} {y} L{x - 12 * s} {y + 13}')

def eye_wink(c):
    x, y = c
    return eye_line(f'M{x - 18} {y + 3} Q{x} {y - 11} {x + 18} {y + 3}') + \
        eye_line(f'M{x + 17} {y + 2} L{x + 25} {y - 6}')

def heart_cons(cx, cy, s):
    d = (f'M{cx} {cy + s * 0.9} C{cx - s * 1.25} {cy + s * 0.05} {cx - s * 1.1} {cy - s * 0.95} {cx - s * 0.5} {cy - s * 0.95} '
         f'C{cx - s * 0.18} {cy - s * 0.95} {cx} {cy - s * 0.7} {cx} {cy - s * 0.5} '
         f'C{cx} {cy - s * 0.7} {cx + s * 0.18} {cy - s * 0.95} {cx + s * 0.5} {cy - s * 0.95} '
         f'C{cx + s * 1.1} {cy - s * 0.95} {cx + s * 1.25} {cy + s * 0.05} {cx} {cy + s * 0.9} Z')
    return path(d)

def eye_heart(c):
    x, y = c
    return [S(heart_cons(x, y, 24), HEART, OUT, 5, nm='heart'),
            F(ellipse(x + 8, y - 10, 4.5), WHITE, nm='hl')]

def eye_dizzy(c):
    x, y = c
    return eye_line(f'M{x + 1} {y} Q{x + 1} {y - 7} {x - 5} {y - 6} Q{x - 12} {y - 4} {x - 11} {y + 4} '
                    f'Q{x - 9} {y + 13} {x + 2} {y + 12} Q{x + 15} {y + 10} {x + 16} {y - 2} '
                    f'Q{x + 16} {y - 17} {x} {y - 20}')

# beak variants (local to beak centre, then shifted)
def _b(cons):
    return tx(cons, BEAK_C[0], BEAK_C[1])

def upper_beak(w=21, top=-16, tip=14, y0=-8):
    return path(f'M{-w} {y0} C{-w} {top} {w} {top} {w} {y0} C{w - 1} {y0 + 10} 8 {tip - 2} 0 {tip} '
                f'C-8 {tip - 2} {-w + 1} {y0 + 10} {-w} {y0} Z')

def lower_beak(y, w=15):
    return path(f'M{-w} {y} C{-w + 2} {y + 12} {w - 2} {y + 12} {w} {y} C{w * 0.5} {y + 6} {-w * 0.5} {y + 6} {-w} {y} Z')

def beak_smile():
    return [S(_b(upper_beak()), BEAK, sw=6, nm='beak'),
            L(_b(path('M-11 -1 Q0 6 11 -1')), OUT, 3.6, nm='crease')]

def beak_frown():
    return [S(_b(upper_beak()), BEAK, sw=6, nm='beak'),
            L(_b(path('M-11 4 Q0 -3 11 4')), OUT, 3.6, nm='crease')]

def beak_tongue():
    return [S(_b(path('M-16 -6 C-16 6 -8 17 0 17 C8 17 16 6 16 -6 Z')), MOUTH, sw=5.5, nm='mouth'),
            F(_b(ellipse(0, 10, 8, 5.5)), TONGUE, nm='tongue'),
            S(_b(lower_beak(13, 13)), BEAK, sw=5, nm='lower'),
            S(_b(upper_beak(20, -20, 1, -12)), BEAK, sw=6, nm='upper')]

def beak_o():
    return [S(_b(ellipse(0, -1, 14, 15)), BEAK, sw=6, nm='ring'),
            F(_b(ellipse(0, 0, 6.5, 7.5)), MOUTH, nm='hole')]

def beak_yawn():
    return [S(_b(ellipse(0, 2, 19, 24)), MOUTH, sw=5.5, nm='mouth'),
            F(_b(ellipse(0, 14, 10, 7)), TONGUE, nm='tongue'),
            S(_b(lower_beak(20, 15)), BEAK, sw=5, nm='lower'),
            S(_b(upper_beak(19, -32, -15, -24)), BEAK, sw=6, nm='upper')]

def beak_squawk():
    return [S(_b(path('M-27 -8 L27 -8 C21 10 9 23 0 23 C-9 23 -21 10 -27 -8 Z')), MOUTH, sw=5.5, nm='mouth'),
            F(_b(ellipse(0, 14, 9.5, 5.5)), TONGUE, nm='tongue'),
            S(_b(lower_beak(19, 14)), BEAK, sw=5, nm='lower'),
            S(_b(upper_beak(29, -19, 1, -11)), BEAK, sw=6, nm='upper')]

# ------------------------------------------------ props (character scale, centred at origin)
def p_fish():
    return [S(path('M22 0 L44 -16 C40 -6 40 6 44 16 Z'), FISH, nm='tail'),
            S(path('M-36 0 C-26 -19 12 -21 28 0 C12 21 -26 19 -36 0 Z'), FISH, nm='body'),
            L(path('M2 -12 Q8 0 2 12'), FISH_D, 4, nm='gill'),
            F(ellipse(-20, -3, 4), OUT, nm='eye')]

def p_snowball(r=22):
    return [S(ellipse(0, 0, r), WHITE, nm='ball'),
            F(path(f'M{r * 0.55} {r * 0.05} C{r * 0.55} {r * 0.5} {r * 0.2} {r * 0.7} {-r * 0.25} {r * 0.72} '
                   f'C{r * 0.35} {r * 0.95} {r * 0.95} {r * 0.5} {r * 0.85} {-r * 0.05} Z'), '#cfe6f7', nm='shade')]

def p_pebble():
    return [S(ellipse(0, 0, 27, 19), PEBBLE, nm='stone'),
            F(ellipse(-9, -7, 8, 4.5), '#d3d2dc', nm='hl')]

def p_floe():
    top = path('M-134 -10 L-98 -26 L42 -28 L124 -16 L136 0 L92 12 L-62 14 L-124 8 Z')
    side = path('M-134 -10 L-124 8 L-62 14 L92 12 L136 0 L136 22 L92 36 L-62 38 L-124 32 L-134 14 Z')
    return [S(side, ICE_D, nm='side'), S(top, ICE, nm='top'),
            L(path('M-70 -6 L-30 -8') + path('M40 -4 L76 0'), WHITE, 5, nm='glint')]

# ------------------------------------------------ effect shapes (canvas px, centred at origin)
EW = 3.5  # effect outline width (canvas px)

def e_heart(s=13):
    return [S(heart_cons(0, 0, s), HEART, OUT, EW, nm='heart'),
            F(ellipse(s * 0.35, -s * 0.45, s * 0.18), WHITE, nm='hl')]

def e_sparkle(s=12, col=SPARK):
    a = s * 0.18
    d = f'M0 {-s} C{a} {-a} {a} {-a} {s} 0 C{a} {a} {a} {a} 0 {s} C{-a} {a} {-a} {a} {-s} 0 C{-a} {-a} {-a} {-a} 0 {-s} Z'
    return [S(path(d), col, OUT, 3, nm='spark')]

def e_star(s=11):
    pts = []
    for i in range(10):
        r = s if i % 2 == 0 else s * 0.45
        a = math.radians(-90 + i * 36)
        pts.append((r * math.cos(a), r * math.sin(a)))
    return [S(poly(pts), SPARK, OUT, 3, nm='star')]

def glyph(d, col, w=5.5, outline=3.5):
    return [L(path(d), OUT, w + outline * 2, nm='gout'), L(path(d), col, w, nm='g')]

def e_z(s=9):
    return glyph(f'M{-s} {-s} L{s} {-s} L{-s} {s} L{s} {s}', ZCOL, 4.5, 3)

def e_question():
    return glyph('M-9 -11 C-9 -24 10 -24 10 -11 C10 -3 1 -2 1 6', ZCOL, 5.5, 3) + \
        [S(ellipse(1, 17, 4.6), ZCOL, OUT, 3, nm='dot')]

def e_bang(col=RED, s=1.0):
    return [S(path(f'M{-6 * s} {-24 * s} L{6 * s} {-24 * s} L{3 * s} {5 * s} L{-3 * s} {5 * s} Z'), col, OUT, 3.5, nm='bar'),
            S(ellipse(0, 15 * s, 5.2 * s), col, OUT, 3.5, nm='dot')]

def e_anger(s=1.0):
    d = []
    for sx in (1, -1):
        for sy in (1, -1):
            d += path(f'M{sx * 4 * s} {sy * 15 * s} Q{sx * 4 * s} {sy * 4 * s} {sx * 15 * s} {sy * 4 * s}')
    return [L(d, OUT, 10, nm='aout'), L(d, RED, 5, nm='anger')]

def e_tear():
    return [S(path('M0 -11 C6 -3 9 2 9 7 C9 12 5 15 0 15 C-5 15 -9 12 -9 7 C-9 2 -6 -3 0 -11 Z'), TEAR, OUT, 3, nm='tear'),
            F(ellipse(-3, 6, 2.2, 3), WHITE, nm='hl')]

def e_snowflake(s=9):
    d = []
    for a in (0, 60, 120):
        r = math.radians(a)
        dx, dy = math.cos(r) * s, math.sin(r) * s
        d += path(f'M{-dx} {-dy} L{dx} {dy}')
    return [L(d, OUT, 7, nm='fout'), L(d, SNOW, 3.2, nm='flake')]

def e_speedline(l=34):
    return [L(path(f'M{-l / 2} 0 L{l / 2} 0'), '#b9c6f0', 5, nm='speed')]

def e_puff(r=6):
    return [S(ellipse(0, 0, r), WHITE, OUT, 2.5, nm='puff')]

def e_feather():
    return [S(path('M0 -12 C7 -6 7 6 0 12 C-7 6 -7 -6 0 -12 Z'), WHITE, OUT, 2.5, nm='feather'),
            L(path('M0 -9 L0 14'), OUT, 2, nm='quill')]

def e_snot(r=12):
    return [S(ellipse(0, 0, r), '#cfeaff', '#7fb3da', 2.5, fo=0.8, nm='bubble'),
            F(ellipse(-r * 0.35, -r * 0.35, r * 0.22), WHITE, nm='hl')]

def e_burst(r=12):
    d = []
    for i in range(6):
        a = math.radians(i * 60 + 30)
        d += path(f'M{math.cos(a) * r * 0.6} {math.sin(a) * r * 0.6} L{math.cos(a) * r} {math.sin(a) * r}')
    return [L(d, '#7fb3da', 3, nm='burst')]

def e_cloud():
    circles = [(-30, 0, 21), (0, -10, 26), (30, 0, 21), (-14, 13, 17), (14, 13, 17)]
    cons = []
    for x, y, r in circles:
        cons += ellipse(x, y, r)
    return [L(cons, OUT, 7, nm='cout'), F(cons, WHITE, nm='cloud')]

def e_badge():
    return [S(ellipse(0, 0, 30), SPARK, OUT, 4, nm='badge')] + \
        [F(path('M-5.5 -19 L5.5 -19 L3 5 L-3 5 Z'), OUT, nm='bar'), F(ellipse(0, 13, 5), OUT, nm='dot')]

def e_bead(r=5):
    return [S(ellipse(0, 0, r), WHITE, OUT, 2.5, nm='bead')]

# ------------------------------------------------ rig
def build_rig():
    Ls = OrderedDict()
    z = [0]
    def add(name, parent=None, pivot=(0, 0), shapes=None, **kw):
        z[0] += 10
        Ls[name] = Layer(name, parent, pivot, shapes=shapes, z=z[0], **kw)
        return Ls[name]

    # nulls (z irrelevant)
    add('root', None, (0, 0), pos=ROOT_POS, scale=(ROOT_S, ROOT_S))
    add('rock', 'root', (0, 0))
    add('breath', 'rock', (0, 0))
    add('body', 'breath', (0, 0))
    add('head', 'body', (0, -196))
    add('headx', 'head', (0, -196))
    add('patch', 'headx', (0, -300))
    add('face', 'headx', (0, -300))
    add('eyeL', 'face', EYE_L)
    add('eyeR', 'face', EYE_R)
    add('beak', 'face', BEAK_C)
    add('cheekL', 'face', (-80, -264))
    add('cheekR', 'face', (80, -264))
    add('flipL', 'body', (-90, -172))
    add('flipR', 'body', (90, -172))
    add('flipLx', 'flipL', (-90, -172))
    add('flipRx', 'flipR', (90, -172))
    add('scarf', 'body', (0, -192))

    # content (draw order)
    add('shadow', None, (256, 472), shapes=[F(ellipse(256, 474, 102, 13), OUT, fo=0.17, nm='shadow')])
    add('tail', 'body', (70, -30), shapes=[S(g_tail(), NAVY)])
    fl = g_flipper_l()
    add('flipL_back', 'flipLx', (-90, -172), shapes=[S(fl, NAVY)])
    add('flipR_back', 'flipRx', (90, -172), shapes=[S(mirror(fl), NAVY)])
    add('body_shape', 'body', (0, 0), shapes=[S(g_body(), NAVY)])
    add('belly', 'body', (0, -94), shapes=[F(g_belly(), WHITE)])
    add('back_shape', 'body', (0, 0), op=0, shapes=[F(path('M0 -232 C60 -232 100 -170 100 -100 C100 -46 60 -16 0 -16 '
                                                           'C-60 -16 -100 -46 -100 -100 C-100 -170 -60 -232 0 -232 Z'), NAVY),
                                                     L(path('M-36 -60 Q0 -40 36 -60'), '#34406c', 5)])
    fo = g_foot_l()
    add('footL', 'rock', (-46, -10), shapes=[S(fo, FOOT)])
    add('footR', 'rock', (46, -10), shapes=[S(mirror(fo), FOOT)])
    tb, rb, fb = g_tail_b()
    add('scarf_tailB', 'scarf', (60, -190), shapes=[S(tb, SCARF), L(rb, SCARF_D, 4), L(fb, OUT, 4.5)])
    ta, ra, fa = g_tail_a()
    add('scarf_tailA', 'scarf', (50, -192), shapes=[S(ta, SCARF), L(ra, SCARF_D, 4), L(fa, OUT, 4.5)])
    add('tuft', 'headx', (0, -420), shapes=[S(g_tuft(), NAVY)])
    add('head_shape', 'headx', (0, -312), shapes=[S(g_head(), NAVY)])
    add('back_head', 'headx', (0, -312), op=0, shapes=[S(g_head(), NAVY)])
    add('patch_shape', 'patch', (0, -300), shapes=[F(g_patch(), WHITE)])
    for side, sx in (('L', -1), ('R', 1)):
        c = (80 * sx, -264)
        add(f'cheek{side}_pink', f'cheek{side}', c, shapes=[F(ellipse(c[0], c[1], 19, 11), CHEEK, fo=0.9)])
        add(f'cheek{side}_cold', f'cheek{side}', c, op=0,
            shapes=[F(ellipse(c[0], c[1], 19, 11), CHEEK_COLD, fo=0.95),
                    L(path(f'M{c[0] - 8} {c[1] - 2} L{c[0] - 3} {c[1] + 3}') + path(f'M{c[0] + 2} {c[1] - 2} L{c[0] + 7} {c[1] + 3}'),
                      '#6fa9d6', 2.5)])
        add(f'cheek{side}_blush', f'cheek{side}', c, op=0,
            shapes=[F(ellipse(c[0], c[1], 22, 13), '#ff7d9c', fo=0.9),
                    L(path(f'M{c[0] - 10} {c[1] - 3} L{c[0] - 5} {c[1] + 4}') + path(f'M{c[0] - 1} {c[1] - 3} L{c[0] + 4} {c[1] + 4}')
                      + path(f'M{c[0] + 8} {c[1] - 3} L{c[0] + 13} {c[1] + 4}'), '#e0587a', 2.5)])
    for side, c in (('L', EYE_L), ('R', EYE_R)):
        add(f'eye{side}_open', f'eye{side}', c, shapes=eye_open(c))
        add(f'eye{side}_sleepy', f'eye{side}', c, op=0, shapes=eye_sleepy(c))
        add(f'eye{side}_happy', f'eye{side}', c, op=0, shapes=eye_happy(c))
        add(f'eye{side}_squint', f'eye{side}', c, op=0, shapes=eye_squint(c, side))
        add(f'eye{side}_wink', f'eye{side}', c, op=0, shapes=eye_wink(c))
        add(f'eye{side}_heart', f'eye{side}', c, op=0, shapes=eye_heart(c))
        add(f'eye{side}_dizzy', f'eye{side}', c, op=0, shapes=eye_dizzy(c) if side == 'L' else
            [L(mirror(eye_dizzy((-c[0], c[1]))[0].cons), EYE, 7)])
    wl = path('M-68 -352 L-32 -363')
    al = path('M-68 -366 L-32 -351')
    add('browL_worried', 'face', (-50, -357), op=0, shapes=[L(wl, OUT, 6.5)])
    add('browR_worried', 'face', (50, -357), op=0, shapes=[L(mirror(wl), OUT, 6.5)])
    add('browL_angry', 'face', (-50, -357), op=0, shapes=[L(al, OUT, 6.5)])
    add('browR_angry', 'face', (50, -357), op=0, shapes=[L(mirror(al), OUT, 6.5)])
    add('beak_smile', 'beak', BEAK_C, shapes=beak_smile())
    add('beak_tongue', 'beak', BEAK_C, op=0, shapes=beak_tongue())
    add('beak_o', 'beak', BEAK_C, op=0, shapes=beak_o())
    add('beak_yawn', 'beak', BEAK_C, op=0, shapes=beak_yawn())
    add('beak_frown', 'beak', BEAK_C, op=0, shapes=beak_frown())
    add('beak_squawk', 'beak', BEAK_C, op=0, shapes=beak_squawk())
    add('scarf_L', 'scarf', (-60, -190), shapes=[S(g_scarf_seg(-98, -30, 'l'), SCARF), L(g_scarf_ribs(-98, -30), SCARF_D, 4)])
    add('scarf_R', 'scarf', (60, -190), shapes=[S(g_scarf_seg(30, 98, 'r'), SCARF), L(g_scarf_ribs(30, 98), SCARF_D, 4)])
    add('scarf_M', 'scarf', (0, -190), shapes=[S(g_scarf_seg(-36, 36), SCARF), L(g_scarf_ribs(-36, 36), SCARF_D, 4)])
    add('flipL_front', 'flipLx', (-90, -172), op=0, shapes=[S(fl, NAVY)])
    add('flipR_front', 'flipRx', (90, -172), op=0, shapes=[S(mirror(fl), NAVY)])
    return Ls

EYES_L = ['eyeL_open', 'eyeL_sleepy', 'eyeL_happy', 'eyeL_squint', 'eyeL_wink', 'eyeL_heart', 'eyeL_dizzy']
EYES_R = [n.replace('eyeL', 'eyeR') for n in EYES_L]
BEAKS = ['beak_smile', 'beak_tongue', 'beak_o', 'beak_yawn', 'beak_frown', 'beak_squawk']
