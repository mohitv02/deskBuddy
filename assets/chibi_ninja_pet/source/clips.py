"""All 47 clips."""
import math
from anim import A
CLIPS = []
def clip(name, cat, N, loop, desc):
    c = A(name, cat, N, loop, desc); CLIPS.append(c); return c

NEUTRAL = {'root.p': (0, 0), 'root.r': 0, 'root.s': (100, 100), 'spin.r': 0, 'spin.p': (0, 0), 'head.r': 0, 'head.p': (0, 0),
           'eyes.p': (0, 0), 'head.s': (100, 100), 'handL.r': 0, 'handR.r': 0, 'armL.s': (100, 100), 'armR.s': (100, 100), 'handL.s': (100, 100), 'handR.s': (100, 100), 'armL.R': 22, 'armR.R': -22, 'legL.R': 0, 'legR.R': 0, 'legL.p': (0, 0), 'legR.p': (0, 0)}
def P(**kw):
    """pose helper: P(armL=.., headp=..) -> dict of node.prop"""
    m = {'root': 'root.p', 'rootr': 'root.r', 'roots': 'root.s', 'spin': 'spin.r', 'spinp': 'spin.p', 'head': 'head.r', 'headp': 'head.p',
         'heads': 'head.s', 'eyes': 'eyes.p', 'armL': 'armL.R', 'armR': 'armR.R', 'legL': 'legL.R', 'legR': 'legR.R', 'legLp': 'legL.p',
         'legRp': 'legR.p', 'handL': 'handL.r', 'handR': 'handR.r', 'torso': 'torso.s'}
    return {m.get(k, k.replace('_', '.')): v for k, v in kw.items()}
N0 = dict(NEUTRAL)
def NP(**kw):
    d = dict(N0); d.update(P(**kw)); return d
FIGHT = P(legL=15, legR=-15, armL=58, armR=-128, spin=-3, head=-3, roots=(103, 97))
SHADOW_UP = lambda h: (max(55, 100 - h * 0.35),) * 2
def shadow(c, keys):
    c.k('shadow', 's', [(t, SHADOW_UP(h), e) for t, h, e in keys])

# ================================================================ IDLE
c = clip('idle_breathe', 'idle', 120, True, 'Default loop: calm ready stance, slow breathing, breeze, blink.')
c.breathe(60).breeze(40).blink(48).blink(100).blink(106)
c.osc('head', 'r2', 1.5, 120, 0.25)
c.osc('eyes', 'p2', (1.5, 0), 120, 0.25)

c = clip('idle_look_left_right', 'idle', 120, True, 'Sharp alert glances left and right, brows narrowing.')
c.breathe(60, 0.7).breeze(40)
c.seq([(0, NP(), 'io'), (8, NP(), 'snap'), (14, NP(headp=(-7, 0), head=-5, eyes=(-10, 1), spin=-2), 'hold'), (44, NP(headp=(-7, 0), head=-5, eyes=(-10, 1), spin=-2), 'snap'),
       (52, NP(headp=(7, 0), head=5, eyes=(10, 1), spin=2), 'hold'), (86, NP(headp=(7, 0), head=5, eyes=(10, 1), spin=2), 'io'), (100, NP(), 'hold'), (120, NP(), 'hold')])
c.face([(0, dict(eyes='open', brows='det')), (9, dict(eyes='sharp', brows='angry')), (98, dict(eyes='open', brows='det'))])
c.blink(108)

c = clip('idle_yawn', 'idle', 96, True, 'A cute yawn, quickly covered with a hand, then a cool pose again.')
c.breathe(48, 0.6).breeze(48)
c.seq([(0, NP(), 'io'), (8, NP(), 'io'), (22, NP(head=-5, headp=(0, -4), roots=(97, 104), armL=34), 'io'),
       (30, NP(head=-5, headp=(0, -4), roots=(97, 104), armL=34, armR=132, handR=20), 'hold'), (46, NP(head=-5, headp=(0, -4), roots=(97, 104), armL=34, armR=132, handR=20), 'snap'),
       (52, NP(armL=-58, armR=58, legL=10, legR=-10, head=3, roots=(102, 98)), 'hold'), (76, NP(armL=-58, armR=58, legL=10, legR=-10, head=3, roots=(102, 98)), 'io'),
       (90, NP(), 'hold'), (96, NP(), 'hold')])
c.face([(0, dict()), (14, dict(eyes='sleepy', brows='calm', mouth='yawn')), (48, dict(eyes='squint', mouth='none')), (52, dict(eyes='sharp', brows='det', mouth='grin')),
        (82, dict(eyes='open', mouth='none'))])
c.hands([(0, {'R': 'fist'}), (28, {'R': 'open'}), (50, {'R': 'fist'})])
c.k('cheeks', 's2', [(0, (100, 100)), (20, (100, 100)), (28, (120, 120)), (46, (120, 120)), (52, (100, 100))])

c = clip('idle_stretch', 'idle', 96, True, 'Big overhead arm stretch, scarf flutters.')
c.breathe(48, 0.5).breeze(24, 9)
up = NP(armL=146, armR=-146, roots=(96, 106), headp=(0, -3), armL_s=(100, 280), armR_s=(100, 280), handL_s=(100, 35.7), handR_s=(100, 35.7))
c.seq([(0, NP(), 'io'), (10, NP(), 'io'), (24, up, 'io'), (36, dict(up, **P(spin=-7)), 'io'), (50, dict(up, **P(spin=7)), 'io'), (62, up, 'io'), (78, NP(), 'hold'), (96, NP(), 'hold')])
c.face([(0, dict()), (18, dict(eyes='squint', brows='calm', mouth='o')), (66, dict(eyes='happy', mouth='smile')), (80, dict(eyes='open', brows='det', mouth='none'))])
c.hands([(0, {'L': 'fist', 'R': 'fist'}), (22, {'L': 'open', 'R': 'open'}), (66, {'L': 'fist', 'R': 'fist'})])
c.seq([(0, P(scarf1_r=0), 'io'), (24, P(scarf1_r=0), 'snap'), (30, P(scarf1_r=-22), 'io'), (44, P(scarf1_r=8), 'io'), (58, P(scarf1_r=-14), 'io'), (76, P(scarf1_r=0), 'hold'), (96, P(scarf1_r=0), 'hold')])
c.blink(88)

c = clip('idle_twirl_shuriken', 'idle', 96, True, 'Spins a shuriken on one finger, then tucks it away.')
c.breathe(48, 0.6).breeze(48)
tw = NP(armR=-112, head=4, headp=(3, 0), eyes=(9, 2), handR=8)
c.seq([(0, NP(), 'io'), (6, NP(), 'snap'), (14, tw, 'io'), (62, tw, 'io'), (68, NP(armR=-112, handR=-20, head=2), 'snap'), (74, NP(armR=30, head=0), 'io'), (86, NP(), 'hold'), (96, NP(), 'hold')])
c.hands([(0, {'R': 'fist'}), (10, {'R': 'point'}), (72, {'R': 'fist'})])
c.k('shurikenHand', 'o', [(0, 0, 'hold'), (10, 100, 'hold'), (76, 0, 'hold')])
c.k('shurikenHand', 's', [(0, (0, 0), 'hold'), (10, (0, 0), 'snap'), (15, (100, 100), 'hold'), (70, (100, 100), 'in'), (76, (0, 0), 'hold')])
c.k('shurikenHand', 'r', [(14, 0, 'in'), (22, 180, 'lin'), (58, 1260, 'out'), (66, 1440, 'hold')])
c.face([(0, dict()), (12, dict(eyes='sharp', mouth='grin')), (80, dict(eyes='open', mouth='none'))])
c.pop('spark0', 64, 76, (322, 300), 80)

c = clip('idle_meditate', 'idle', 180, True, 'Sits cross-legged, eyes closed, floating calmly a few pixels above the ground.')
c.breeze(60, 4)
sit = lambda y: NP(root=(0, y), armL=34, armR=-34, roots=(100, 100))
c.seq([(0, NP(), 'io'), (8, NP(roots=(106, 92)), 'snap'), (18, sit(26), 'io'), (34, sit(12), 'sine'), (56, sit(16), 'sine'), (78, sit(10), 'sine'), (100, sit(16), 'sine'),
       (122, sit(10), 'sine'), (144, sit(15), 'io'), (160, sit(26), 'io'), (168, NP(roots=(104, 95)), 'io'), (178, NP(), 'hold'), (180, NP(), 'hold')])
c.hands([(0, {'L': 'fist', 'R': 'fist'}), (16, {'L': 'open', 'R': 'open'}), (164, {'L': 'fist', 'R': 'fist'})])
c.vis('lap', [(15, True), (165, False)], 0); c.vis('legL', [(15, False), (165, True)], 100); c.vis('legR', [(15, False), (165, True)], 100)
c.face([(0, dict()), (16, dict(eyes='sleepy', brows='calm', mouth='smile')), (166, dict(eyes='open', brows='det', mouth='none'))])
c.k('shadow', 's', [(0, (100, 100)), (18, (104, 104)), (34, (90, 90)), (56, (95, 95)), (78, (88, 88)), (100, (95, 95)), (122, (88, 88)), (144, (95, 95)), (160, (104, 104)), (178, (100, 100))])
c.osc('torso', 's2', (0.6, -2), 44, 0.5, (100, 100))
c.pop('spark0', 40, 70, pos_keys=[(40, (176, 330), 'io'), (70, (168, 280), 'hold')], peak=70)
c.pop('spark1', 80, 110, pos_keys=[(80, (338, 320), 'io'), (110, (346, 272), 'hold')], peak=70)
c.pop('spark2', 118, 146, pos_keys=[(118, (190, 250), 'io'), (146, (182, 206), 'hold')], peak=60)

# ================================================================ SLEEP
SLEEP = NP(root=(0, 26), armR=30, armL=-30, head=12, headp=(6, 6), eyes=(0, 2), handR=16)
DROOP = P(htailA1_R=58, htailA2_R=20, htailB1_R=80, htailB2_R=10, scarf1_R=118, scarf2_R=-6, scarf3_R=-4)
UPRIGHT = P(htailA1_R=-28, htailA2_R=30, htailB1_R=24, htailB2_R=22, scarf1_R=150, scarf2_R=-18, scarf3_R=-20)

c = clip('sleep_fall_asleep', 'sleep', 150, False, 'Nods off while standing guard, then sits and leans on its sword.')
c.breeze(50, 4)
guard = NP(armR=-64, handR=64, legL=8, legR=-8)
c.seq([(0, NP(), 'io'), (10, NP(armR=-60), 'snap'), (18, guard, 'hold'), (34, guard, 'in'), (52, dict(guard, **P(head=7, headp=(0, 8))), 'snap'),
       (57, dict(guard, **P(head=-2, headp=(0, -2))), 'io'), (66, guard, 'io'), (90, dict(guard, **P(head=10, headp=(2, 10), roots=(102, 97))), 'io'),
       (104, dict(guard, **P(head=10, headp=(2, 10), roots=(108, 90))), 'io'), (124, SLEEP, 'io'), (150, SLEEP, 'hold')])
c.seq([(0, UPRIGHT, 'io'), (90, UPRIGHT, 'io'), (126, DROOP, 'io'), (150, DROOP, 'hold')])
c.k('swordHand', 'o', [(0, 0, 'hold'), (12, 100, 'hold')])
c.k('swordHand', 's', [(0, (0, 0), 'hold'), (12, (0, 0), 'snap'), (18, (100, 100), 'hold')])
c.pop('spark0', 16, 28, (318, 252), 70)
c.face([(0, dict()), (20, dict(eyes='sharp')), (36, dict(eyes='sleepy', brows='calm')), (54, dict(eyes='big', brows='up')), (62, dict(eyes='sharp', brows='det')),
        (78, dict(eyes='sleepy', brows='calm')), (124, dict(mouth='o'))])
c.k('shadow', 's', [(0, (100, 100)), (104, (100, 100)), (124, (106, 106))])
c.vis('lap', [(116, True)], 0); c.vis('legL', [(116, False)], 100); c.vis('legR', [(116, False)], 100)

c = clip('sleep_loop', 'sleep', 120, True, 'Dozing sitting up: snot bubble, rising z z z, headband tails drooping.')
c.seq([(0, SLEEP, 'hold'), (120, SLEEP, 'hold')]).seq([(0, DROOP, 'hold'), (120, DROOP, 'hold')])
c.breathe(60, 1.5); c.osc('head', 'r2', 2, 60, 0.5); c.breeze(60, 2.5)
c.face([(0, dict(eyes='sleepy', brows='calm', mouth='o'))])
c.k('swordHand', 'o', [(0, 100, 'hold')])
c.vis('lap', [], 100); c.vis('legL', [], 0); c.vis('legR', [], 0)
c.k('snot', 'o', [(0, 100, 'hold')]); c.osc('snot', 's', (38, 38), 60, 0.5, (72, 72))
c.k('shadow', 's', [(0, (106, 106), 'hold')])
for j, t0 in enumerate([0, 40, 80]):
    for sh in (-120, 0, 120):
        a = t0 + sh
        c.k(f'z{j}', 'o', [(a, 100, 'hold'), (a + 60, 0, 'hold')])
        c.k(f'z{j}', 's', [(a, (0, 0), 'out'), (a + 8, (70 + 15 * j, 70 + 15 * j), 'io'), (a + 46, (90 + 15 * j, 90 + 15 * j), 'in'), (a + 60, (0, 0), 'hold')])
        c.k(f'z{j}', 'p', [(a, (318, 236), 'io'), (a + 30, (352, 196), 'io'), (a + 60, (332, 150), 'hold')])
        c.k(f'z{j}', 'r', [(a, -10, 'io'), (a + 30, 12, 'io'), (a + 60, -8, 'hold')])

c = clip('sleep_wake_up', 'sleep', 120, False, 'Bubble pops, startled jump into a fighting pose, nothing there, embarrassed sweat drop.')
c.breeze(40, 5)
FS = dict(FIGHT, **P(armR=-105))
c.seq([(0, SLEEP, 'hold'), (8, SLEEP, 'snap'), (13, NP(root=(0, -44), roots=(94, 108), armL=120, armR=-150, legL=-10, legR=10), 'in'),
       (22, dict(FS, **P(root=(0, 4), roots=(108, 92))), 'snap'), (27, FS, 'hold'), (34, FS, 'snap'), (38, dict(FS, **P(headp=(-7, 0), head=-5, eyes=(-10, 0))), 'hold'),
       (48, dict(FS, **P(headp=(-7, 0), head=-5, eyes=(-10, 0))), 'snap'), (52, dict(FS, **P(headp=(7, 0), head=5, eyes=(10, 0))), 'hold'),
       (64, dict(FS, **P(headp=(7, 0), head=5, eyes=(10, 0))), 'io'), (74, NP(armR=-40, armL=30, head=-6, headp=(0, 2)), 'hold'), (100, NP(armR=-40, armL=30, head=-6, headp=(0, 2)), 'io'),
       (114, NP(), 'hold'), (120, NP(), 'hold')])
c.seq([(0, DROOP, 'hold'), (8, DROOP, 'snap'), (16, UPRIGHT, 'hold'), (120, UPRIGHT, 'hold')])
c.k('swordHand', 'o', [(0, 100, 'hold'), (96, 0, 'hold')])
c.k('swordHand', 's', [(0, (100, 100), 'hold'), (90, (100, 100), 'in'), (96, (0, 0), 'hold')])
c.puff('smoke2', 90, 108, (320, 300), 55)
c.vis('lap', [(10, False)], 100); c.vis('legL', [(10, True)], 0); c.vis('legR', [(10, True)], 0)
c.k('snot', 'o', [(0, 100, 'hold'), (8, 0, 'hold')]); c.k('snot', 's', [(0, (80, 80), 'in'), (6, (125, 125), 'hold'), (8, (0, 0), 'hold')])
c.pop('spark0', 7, 16, (286, 290), 60, inn=2, outt=5)
c.pop('exclaim', 10, 34, (338, 168), 100, inn=3)
c.face([(0, dict(eyes='sleepy', brows='calm', mouth='o')), (8, dict(eyes='dot', brows='up', mouth='o')), (20, dict(eyes='sharp', brows='angry', mouth='shout')),
        (36, dict(mouth='flat')), (66, dict(eyes='dot', brows='worried', mouth='o')), (76, dict(eyes='open', mouth='pout', blush=True)),
        (108, dict(eyes='open', brows='det', mouth='none', blush=False))])
c.pop('sweat', 70, 104, peak=100, pos_keys=[(70, (0, 0), 'io'), (104, (0, 12), 'hold')])
c.k('shadow', 's', [(0, (106, 106)), (8, (106, 106)), (13, (82, 82)), (22, (104, 104)), (30, (100, 100))])

# ================================================================ MOVEMENT
c = clip('move_walk', 'movement', 32, True, 'Sneaky tiptoe walk in place, leaning forward (the app moves the window).')
c.breeze(16, 7)
base = dict(rootr=5, armL=78, armR=-64, head=3, eyes=(8, 1), handL=-30, handR=30)
c.seq([(0, NP(**base, root=(0, 0), legL=-6, legR=6, legLp=(0, -9), legRp=(0, 0)), 'sine'),
       (8, NP(**base, root=(0, -4), legL=4, legR=-2, legLp=(0, -4), legRp=(0, 0)), 'sine'),
       (16, NP(**base, root=(0, 0), legL=6, legR=-6, legLp=(0, 0), legRp=(0, -9)), 'sine'),
       (24, NP(**base, root=(0, -4), legL=2, legR=-4, legLp=(0, 0), legRp=(0, -4)), 'sine'),
       (32, NP(**base, root=(0, 0), legL=-6, legR=6, legLp=(0, -9), legRp=(0, 0)), 'sine')])
c.osc('head', 'p2', (0, 1.5), 16, 0.5)
c.face([(0, dict(eyes='sharp', brows='det', mouth='flat'))])
c.k('shadow', 's', [(0, (100, 100)), (8, (96, 96)), (16, (100, 100)), (24, (96, 96)), (32, (100, 100))])

c = clip('move_run', 'movement', 20, True, 'Ninja run: arms swept back, speed lines, scarf streaming.')
run = dict(rootr=10, armL=78, armR=46, head=4, eyes=(9, 1), spin=2)
stream = P(scarf1_R=176, scarf2_R=4, scarf3_R=6, htailA1_R=-168, htailA2_R=-4, htailB1_R=176, htailB2_R=6)
c.seq([(0, NP(**run, root=(0, 0), legL=30, legR=-34, legRp=(0, -8)), 'sine'), (5, NP(**run, root=(0, -8), legL=0, legR=0, legLp=(0, -4), legRp=(0, -4)), 'sine'),
       (10, NP(**run, root=(0, 0), legL=-34, legR=30, legLp=(0, -8), legRp=(0, 0)), 'sine'), (15, NP(**run, root=(0, -8), legL=0, legR=0, legLp=(0, -4), legRp=(0, -4)), 'sine'),
       (20, NP(**run, root=(0, 0), legL=30, legR=-34, legRp=(0, -8), legLp=(0, 0)), 'sine')])
c.seq([(0, stream, 'hold'), (20, stream, 'hold')])
c.wave(['scarf1', 'scarf2', 'scarf3'], 7, 10, 0.18); c.wave(['htailA1', 'htailA2'], 7, 10, 0.2); c.wave(['htailB1', 'htailB2'], 7, 10, 0.2, base_phase=0.4)
c.face([(0, dict(eyes='sharp', brows='angry', mouth='flat'))])
for nm, y0, ph in (('speed2', 300, 0), ('speed', 430, 10)):
    c.k(nm, 'o', [(0, 100, 'hold')]); c.k(nm, 's', [(0, (100, 100), 'hold')])
    keys = []
    for sh in (-20, 0, 20):
        a = ph + sh
        keys += [(a, (150, y0), 'lin'), (a + 19.9, (40, y0), 'hold')]
    c.k(nm, 'p', keys)
c.k('shadow', 's', [(0, (104, 104)), (5, (94, 94)), (10, (104, 104)), (15, (94, 94)), (20, (104, 104))])

c = clip('move_hop', 'movement', 50, True, 'High flip jump with a twist.')
c.breeze(25, 5)
c.seq([(0, NP(), 'io'), (6, NP(roots=(112, 84), armL=60, armR=-60), 'snap'), (12, NP(root=(0, -70), roots=(92, 110), armL=170, armR=-170), 'out'),
       (22, NP(root=(0, -150), legL=-28, legR=28, armL=40, armR=-40), 'in'), (32, NP(root=(0, -40), armL=120, armR=-120), 'in'),
       (36, NP(roots=(112, 86), armL=70, armR=-70, legL=10, legR=-10), 'io'), (44, NP(), 'hold'), (50, NP(), 'hold')])
c.keys.pop(('spin', 'r'), None)
c.k('spin', 'r', [(0, 0, 'hold'), (11, 0, 'io'), (31, 360, 'hold'), (50, 360, 'hold')])
c.k('spin', 's2', [(0, (100, 100), 'hold'), (12, (100, 100), 'io'), (20, (-100, 100), 'io'), (28, (100, 100), 'hold')])
c.face([(0, dict()), (6, dict(eyes='sharp', mouth='flat')), (14, dict(eyes='squint', mouth='shout')), (34, dict(eyes='sharp', mouth='grin')), (46, dict(eyes='open', mouth='none'))])
shadow(c, [(0, 0, 'io'), (8, 0, 'out'), (22, 150, 'in'), (34, 0, 'io')])
c.puff('dust0', 34, 48, (214, 462), 80); c.puff('dust1', 34, 48, (300, 462), 80)

c = clip('move_teleport', 'movement', 72, False, 'Vanishes in a smoke puff and reappears in the same spot with a cool pose.')
c.breeze(24, 5)
sign = NP(armL=-52, armR=52, head=-2, legL=6, legR=-6)
cool = NP(armL=-58, armR=58, legL=12, legR=-12, head=4, roots=(102, 98))
c.seq([(0, NP(), 'io'), (8, sign, 'snap'), (12, dict(sign, **P(roots=(104, 96))), 'hold'), (40, cool, 'hold'), (60, cool, 'io'), (72, NP(), 'hold')])
c.hands([(0, {'R': 'fist'}), (8, {'R': 'point'}), (40, {'R': 'fist'})])
c.face([(0, dict()), (8, dict(eyes='sharp', brows='angry')), (40, dict(eyes='wink', brows='det', mouth='grin')), (62, dict(eyes='open', mouth='none'))])
c.vis('root', [(18, False), (38, True)], 100); c.vis('shadow', [(18, False), (38, True)], 100)
c.pop('bigsmoke', 14, 36, (256, 372), 100, inn=4, outt=12); c.k('bigsmoke', 'r', [(14, -10, 'io'), (36, 14, 'hold')])
c.puff('smoke0', 34, 56, (190, 408), 100); c.puff('smoke1', 35, 58, (322, 402), 100); c.puff('smoke2', 36, 58, (258, 330), 90)
c.pop('spark0', 42, 56, (300, 262), 70)

c = clip('move_fall_land', 'movement', 60, False, 'Drops from above and lands in a three-point superhero landing with a dust puff.')
c.breeze(20, 8)
land = NP(root=(0, 24), spin=16, legL=64, legR=-24, armR=-14, armL=96, head=8, headp=(0, 6), eyes=(0, 4))
c.seq([(0, NP(root=(0, -560), armL=150, armR=-150, legL=-10, legR=10), 'in'), (14, NP(root=(0, 0), armL=130, armR=-130, roots=(90, 112)), 'snap'),
       (18, dict(land, **P(roots=(108, 92))), 'io'), (24, land, 'hold'), (36, land, 'snap'), (44, NP(root=(0, -10), armL=-58, armR=58, head=-2), 'io'),
       (52, NP(armL=-58, armR=58, legL=10, legR=-10), 'io'), (60, NP(), 'hold')])
c.seq([(0, P(scarf1_R=-80, scarf2_R=6, scarf3_R=6, htailA1_R=-80, htailB1_R=-60), 'in'), (14, P(scarf1_R=-60, scarf2_R=10, scarf3_R=10, htailA1_R=-60, htailB1_R=-40), 'snap'),
       (24, UPRIGHT, 'hold'), (60, UPRIGHT, 'hold')])
c.face([(0, dict(eyes='sharp', brows='angry', mouth='shout')), (18, dict(mouth='flat')), (44, dict(eyes='sharp', brows='det', mouth='grin')), (56, dict(eyes='open', mouth='none'))])
c.k('shadow', 's', [(0, (40, 40), 'in'), (14, (100, 100), 'snap'), (18, (112, 112), 'io'), (40, (112, 112), 'io'), (52, (100, 100), 'hold')])
c.pop('speed', 0, 13, peak=100, pos_keys=[(0, (256, 60), 'lin'), (13, (256, 150), 'hold')], rot=[(0, 90, 'hold')])
c.puff('dust0', 14, 34, (196, 458), 110); c.puff('dust1', 15, 35, (318, 458), 110); c.puff('smoke3', 16, 36, (256, 470), 70)

# ================================================================ INTERACTION
c = clip('int_dragged', 'interaction', 30, True, 'Held by the scarf: legs kicking, flustered face, sweat drop.')
hang = P(root=(20, -60), head=-8, spin=14)
c.seq([(0, hang, 'hold'), (30, hang, 'hold')])
c.seq([(0, P(scarf1_R=-152, scarf2_R=-6, scarf3_R=-6, htailA1_R=60, htailA2_R=10, htailB1_R=80, htailB2_R=8), 'hold'), (30, P(), 'hold')])
c.osc('spin', 'r2', 5, 30, 0.0); c.osc('legL', 'r2', 26, 10, 0.0); c.osc('legR', 'r2', -26, 10, 0.2)
c.osc('armL', 'r', 30, 15, 0.0, center=110); c.osc('armR', 'r', -30, 15, 0.3, center=-110)
c.face([(0, dict(eyes='squint', brows='worried', mouth='shout', blush=True))])
c.k('sweat', 'o', [(0, 100, 'hold')]); c.osc('sweat', 's', (8, 8), 15, 0, (100, 100))
c.k('shadow', 's', [(0, (72, 72), 'hold')]); c.k('shadow', 'p', [(0, (20, 0), 'hold')])
c.hands([(0, {'L': 'open', 'R': 'open'})])

c = clip('int_petted', 'interaction', 110, False, 'Tries to stay cool, then melts into happy ^ ^ eyes with blushing cheeks; hearts pop up.')
c.breeze(55, 5)
c.seq([(0, NP(), 'io'), (4, NP(headp=(0, 5), heads=(104, 95)), 'io'), (12, NP(headp=(-3, 5), head=-3, heads=(104, 95)), 'io'), (20, NP(headp=(3, 5), head=3, heads=(104, 95)), 'io'),
       (28, NP(headp=(-3, 5), head=-3, heads=(104, 95)), 'io'), (36, NP(headp=(0, 4), head=0, heads=(102, 98), roots=(106, 95), armL=30, armR=-30), 'io'),
       (48, NP(head=-7, roots=(106, 95), spin=-4, armL=30, armR=-30), 'sine'), (60, NP(head=7, roots=(106, 95), spin=4, armL=30, armR=-30), 'sine'),
       (72, NP(head=-7, roots=(106, 95), spin=-4, armL=30, armR=-30), 'sine'), (84, NP(head=5, roots=(104, 96), spin=3), 'io'), (100, NP(), 'hold'), (110, NP(), 'hold')])
c.face([(0, dict(eyes='sharp', mouth='flat')), (24, dict(eyes='squint', mouth='pout', blush=True)), (34, dict(eyes='happy', brows='calm', mouth='smile')),
        (96, dict(eyes='open', brows='det', mouth='none', blush=False))])
c.k('cheeks', 's2', [(0, (100, 100)), (30, (100, 100)), (38, (125, 125)), (92, (125, 125)), (100, (100, 100))])
for j, (t0, x, y) in enumerate([(38, 196, 232), (50, 322, 222), (62, 256, 196)]):
    c.pop(f'heart{j}', t0, t0 + 32, pos_keys=[(t0, (x, y), 'out'), (t0 + 32, (x + (-14 if j == 0 else 14), y - 58), 'hold')], peak=100)
    c.k(f'heart{j}', 'r', [(t0, -12, 'sine'), (t0 + 16, 12, 'sine'), (t0 + 32, -10, 'hold')])

c = clip('int_poked', 'interaction', 134, False, 'First poke "hm?", then pouty cheeks, angry brows and anger mark, finally a smoke-puff dodge.')
c.breeze(67, 5)
c.seq([(0, NP(), 'io'), (4, NP(roots=(96, 104), spin=-5), 'snap'), (10, NP(head=9, headp=(2, 0), eyes=(7, -3)), 'hold'), (38, NP(head=9, headp=(2, 0), eyes=(7, -3)), 'io'),
       (46, NP(), 'io'), (52, NP(roots=(95, 105), spin=-6), 'snap'), (58, NP(head=-7, headp=(-3, 0), eyes=(-6, 0), armL=-40, armR=40), 'hold'),
       (90, NP(head=-7, headp=(-3, 0), eyes=(-6, 0), armL=-40, armR=40), 'snap'), (94, NP(roots=(104, 96)), 'hold'), (116, NP(armL=-58, armR=58, head=3), 'hold'),
       (124, NP(armL=-58, armR=58, head=3), 'io'), (134, NP(), 'hold')])
c.face([(0, dict()), (5, dict(eyes='dot', brows='up', mouth='o')), (12, dict(eyes='open')), (42, dict(eyes='open', brows='det', mouth='none')),
        (53, dict(eyes='sharp', brows='angry', mouth='pout')), (112, dict(eyes='sharp', brows='det', mouth='grin')), (126, dict(eyes='open', mouth='none'))])
c.pop('question', 8, 38, (338, 176), 100, rot=[(8, -12, 'snap'), (14, 8, 'io'), (38, 0, 'hold')])
c.k('cheeks', 's2', [(0, (100, 100)), (54, (100, 100), 'snap'), (58, (150, 165)), (90, (150, 165)), (94, (100, 100))])
c.pop('anger', 56, 92, peak=100, scale=[(0, (0, 0), 'hold'), (56, (0, 0), 'snap'), (60, (120, 120), 'io'), (66, (95, 95), 'io'), (72, (115, 115), 'io'), (78, (95, 95), 'io'),
                                         (84, (115, 115), 'io'), (89, (100, 100), 'in'), (92, (0, 0), 'hold')])
c.vis('root', [(98, False), (114, True)], 100); c.vis('shadow', [(98, False), (114, True)], 100)
c.pop('bigsmoke', 94, 116, (256, 372), 100, inn=4, outt=10)
c.puff('smoke0', 112, 130, (200, 406), 90); c.puff('smoke1', 113, 132, (316, 400), 90)

LOOKS = {'up': ((0, -5), 0, (0, -7), 'up'), 'up_right': ((5, -3), 4, (8, -6), 'up'), 'right': ((7, 0), 5, (10, 0), 'det'),
         'down_right': ((5, 4), 6, (8, 6), 'det'), 'down': ((0, 6), 0, (0, 7), 'det'), 'down_left': ((-5, 4), -6, (-8, 6), 'det'),
         'left': ((-7, 0), -5, (-10, 0), 'det'), 'up_left': ((-5, -3), -4, (-8, -6), 'up')}
for d, (hp, hr, ep, br) in LOOKS.items():
    c = clip(f'int_look_{d}', 'interaction', 40, False, f'Eyes and head turn {d.replace("_", "-")} and hold (cursor following).')
    c.breathe(20, 0.6).breeze(20, 5)
    c.seq([(0, NP(), 'snap'), (7, NP(headp=hp, head=hr, eyes=ep, spin=hr * 0.3), 'hold'), (40, NP(headp=hp, head=hr, eyes=ep, spin=hr * 0.3), 'hold')])
    c.face([(0, dict()), (4, dict(brows=br))])
    c.blink(26)

# ================================================================ MOODS
c = clip('mood_happy', 'mood', 80, False, 'Little victory jump with a peace sign and sparkles.')
c.breeze(20, 7)
peace = NP(armR=-158, armL=40, head=5, handR=0)
c.seq([(0, NP(), 'io'), (6, NP(roots=(110, 88), armL=40, armR=-40), 'snap'), (16, NP(root=(0, -64), roots=(94, 108), armL=150, armR=-158, legL=-22, legR=22), 'in'),
       (28, NP(root=(0, 0), roots=(108, 92), armR=-158, armL=40), 'io'), (34, peace, 'hold'), (62, peace, 'io'), (74, NP(), 'hold'), (80, NP(), 'hold')])
c.hands([(0, {'R': 'fist'}), (12, {'R': 'peace'}), (68, {'R': 'fist'})])
c.face([(0, dict()), (8, dict(eyes='happy', brows='calm', mouth='shout')), (30, dict(eyes='wink', brows='det', mouth='grin')), (70, dict(eyes='open', mouth='none'))])
shadow(c, [(0, 0, 'io'), (6, 0, 'out'), (16, 64, 'in'), (28, 0, 'io')])
c.pop('spark0', 14, 40, (168, 252), 100); c.pop('spark1', 20, 46, (352, 196), 90); c.pop('spark2', 30, 58, (360, 312), 70)

c = clip('mood_sad', 'mood', 130, False, 'Slumped shoulders, droopy headband, teardrop, kicks a pebble.')
c.breeze(65, 3)
slump = NP(headp=(0, 9), head=0, eyes=(0, 6), armL=8, armR=-8, spinp=(0, 5), roots=(103, 96))
c.seq([(0, NP(), 'io'), (14, slump, 'hold'), (70, slump, 'io'), (78, dict(slump, **P(legR=14, eyes=(6, 7))), 'snap'), (82, dict(slump, **P(legR=-40, eyes=(8, 7))), 'io'),
       (92, dict(slump, **P(eyes=(8, 6))), 'hold'), (112, dict(slump, **P(eyes=(8, 6))), 'io'), (126, NP(), 'hold'), (130, NP(), 'hold')])
c.seq([(0, UPRIGHT, 'io'), (16, DROOP, 'hold'), (112, DROOP, 'io'), (126, UPRIGHT, 'hold'), (130, UPRIGHT, 'hold')])
c.face([(0, dict()), (10, dict(brows='sad', mouth='frown')), (118, dict(brows='det', mouth='none'))])
c.pop('tear', 26, 62, peak=100, pos_keys=[(26, (0, 0), 'in'), (62, (0, 36), 'hold')])
c.pop('pebble', 72, 104, peak=100, pos_keys=[(72, (296, 466), 'hold'), (81, (296, 466), 'out'), (90, (380, 420), 'in'), (104, (450, 470), 'hold')],
      rot=[(81, 0, 'lin'), (104, 540, 'hold')])
c.k('pebble', 's', [(0, (0, 0), 'hold'), (72, (0, 0), 'out'), (76, (100, 100), 'hold'), (100, (100, 100), 'in'), (104, (0, 0), 'hold')])

c = clip('mood_surprised', 'mood', 76, False, 'Jumps back into a defensive pose, big eyes, "!" mark.')
c.breeze(19, 7)
guardp = NP(legL=16, legR=-16, armL=142, armR=-142, spin=-5, head=-4, roots=(104, 96))
c.seq([(0, NP(), 'snap'), (6, NP(root=(0, -40), roots=(94, 108), armL=110, armR=-110, legL=-12, legR=12), 'in'), (14, dict(guardp, **P(roots=(110, 90))), 'io'),
       (20, guardp, 'hold'), (52, guardp, 'io'), (66, NP(), 'hold'), (76, NP(), 'hold')])
c.hands([(0, {'L': 'fist', 'R': 'fist'}), (6, {'L': 'open', 'R': 'open'}), (58, {'L': 'fist', 'R': 'fist'})])
c.face([(0, dict(eyes='big', brows='up', mouth='o')), (14, dict(mouth='shout')), (30, dict(mouth='o')), (60, dict(eyes='open', brows='det', mouth='none'))])
c.pop('exclaim', 2, 40, (340, 164), 110, inn=3)
shadow(c, [(0, 0, 'snap'), (6, 40, 'in'), (14, 0, 'io')])

c = clip('mood_hungry', 'mood', 120, False, 'Belly rumble lines and a thought bubble with a rice ball.')
c.breeze(40, 5)
belly = NP(armL=-36, armR=36, head=-4, headp=(0, 2), eyes=(5, -6), roots=(102, 98))
c.seq([(0, NP(), 'io'), (12, belly, 'hold'), (100, belly, 'io'), (114, NP(), 'hold'), (120, NP(), 'hold')])
c.hands([(0, {'L': 'fist', 'R': 'fist'}), (10, {'L': 'open', 'R': 'open'}), (104, {'L': 'fist', 'R': 'fist'})])
c.face([(0, dict()), (10, dict(brows='worried', mouth='o')), (40, dict(mouth='smile', eyes='happy')), (70, dict(eyes='open', mouth='o')), (106, dict(brows='det', mouth='none'))])
c.vis('rumble', [(14, True), (34, False), (52, True), (70, False)], 0)
c.osc('rumble', 's2', (12, 12), 6, 0, (100, 100)); c.osc('spin', 'p2', (1.6, 0), 4, 0)
c.pop('thought', 30, 104, (382, 150), 100, inn=6, outt=8)
c.osc('thought', 'p2', (0, 3), 40, 0)

c = clip('mood_love', 'mood', 116, False, 'Heart eyes, blushing, hides its face behind its scarf.')
c.breeze(29, 6)
hide = NP(armL=146, armR=-146, head=-3, headp=(0, 3), roots=(97, 103))
c.seq([(0, NP(), 'io'), (8, NP(roots=(104, 96)), 'io'), (20, NP(spin=-4, head=-6), 'sine'), (32, NP(spin=4, head=6), 'sine'), (40, NP(), 'io'),
       (48, hide, 'hold'), (92, hide, 'io'), (106, NP(), 'hold'), (116, NP(), 'hold')])
c.face([(0, dict()), (4, dict(eyes='heart', blush=True, mouth='smile', brows='calm')), (100, dict(eyes='open', blush=False, mouth='none', brows='det'))])
c.k('scarffront', 'o', [(0, 0, 'hold'), (42, 100, 'hold'), (100, 0, 'hold')])
c.k('scarffront', 's', [(0, (100, 0), 'hold'), (42, (100, 0), 'snap'), (50, (100, 100), 'hold'), (92, (100, 100), 'in'), (100, (100, 0), 'hold')])
c.hands([(0, {'L': 'fist', 'R': 'fist'}), (44, {'L': 'open', 'R': 'open'}), (98, {'L': 'fist', 'R': 'fist'})])
c.k('eyes_heart', 's2', [(4, (60, 60), 'snap'), (10, (120, 120), 'io'), (16, (100, 100), 'io'), (56, (100, 100), 'io'), (62, (115, 115), 'io'), (68, (100, 100), 'io'),
                         (74, (115, 115), 'io'), (80, (100, 100), 'hold')])
for j, (t0, x, y) in enumerate([(10, 186, 236), (22, 330, 214), (60, 352, 290)]):
    c.pop(f'heart{j}', t0, t0 + 34, pos_keys=[(t0, (x, y), 'out'), (t0 + 34, (x, y - 62), 'hold')], peak=100)

c = clip('mood_angry', 'mood', 110, False, 'Fiery aura flickers around it, determined brows, fist clenched.')
c.breeze(10, 6)
mad = NP(legL=15, legR=-15, armL=20, armR=-96, head=-3, roots=(104, 96), spin=-2)
c.seq([(0, NP(), 'io'), (8, NP(roots=(96, 104)), 'snap'), (14, mad, 'hold'), (90, mad, 'io'), (104, NP(), 'hold'), (110, NP(), 'hold')])
c.osc('armR', 'r2', 3, 4, 0); c.osc('spin', 'p2', (1.4, 0), 3, 0)
c.face([(0, dict()), (8, dict(eyes='sharp', brows='angry', mouth='shout')), (30, dict(mouth='flat')), (98, dict(eyes='open', brows='det', mouth='none'))])
c.k('aura', 'p', [(0, (256, 412), 'hold')])
c.k('aura', 'o', [(0, 0, 'hold'), (10, 100, 'hold'), (98, 0, 'hold')])
c.k('aura', 's', [(0, (0, 0), 'hold'), (10, (30, 30), 'snap'), (18, (100, 100), 'hold'), (88, (100, 100), 'in'), (98, (0, 0), 'hold')])
for j in range(7):
    c.osc(f'flame{j}', 's2', (10, 16), 8 + (j % 3) * 2, j * 0.17, (100, 100))
c.pop('anger', 16, 92, peak=100)

c = clip('mood_determined', 'mood', 96, False, 'Tightens its headband, eyes glint with a sparkle, cool pose.')
c.breeze(24, 6)
H = dict(armL_s=(100, 290), armR_s=(100, 290), handL_s=(100, 34.5), handR_s=(100, 34.5))
tie = NP(armL=162, armR=-162, head=0, headp=(0, 2), **H)
tie2 = NP(armL=150, armR=-174, head=-3, headp=(0, 2), **H)
coolp = NP(legL=14, legR=-14, armL=36, armR=-104, head=-3, roots=(104, 96))
c.seq([(0, NP(), 'io'), (12, tie, 'io'), (18, tie2, 'snap'), (21, tie, 'hold'), (28, tie, 'io'), (38, coolp, 'snap'), (76, coolp, 'io'), (90, NP(), 'hold'), (96, NP(), 'hold')])
c.seq([(0, UPRIGHT, 'io'), (18, UPRIGHT, 'snap'), (21, P(htailA1_R=-50, htailA2_R=10, htailB1_R=-8, htailB2_R=6, scarf1_R=150, scarf2_R=-18, scarf3_R=-20), 'io'),
       (36, UPRIGHT, 'hold'), (96, UPRIGHT, 'hold')])
c.face([(0, dict()), (12, dict(eyes='squint', brows='angry', mouth='flat')), (30, dict(eyes='sharp', brows='angry')), (40, dict(mouth='grin', brows='det')), (84, dict(eyes='open', mouth='none'))])
c.pop('spark0', 32, 50, (306, 258), 75, rot=[(32, 0, 'lin'), (50, 90, 'hold')])
c.pop('spark1', 36, 52, (218, 256), 50)

c = clip('mood_embarrassed', 'mood', 116, False, 'Blushes, pulls the mask up over its whole face, sweat drop.')
c.breeze(29, 5)
shy = NP(armL=-30, armR=30, head=-5, headp=(0, 3), eyes=(-8, 4), roots=(98, 100))
pull = NP(armL=150, armR=-150, head=-3, headp=(0, 4), roots=(96, 100))
c.seq([(0, NP(), 'io'), (10, shy, 'hold'), (30, shy, 'io'), (40, pull, 'hold'), (88, pull, 'io'), (104, NP(), 'hold'), (116, NP(), 'hold')])
c.face([(0, dict()), (6, dict(blush=True, brows='worried', mouth='pout')), (104, dict(blush=False, brows='det', mouth='none'))])
c.k('maskup', 'o', [(0, 0, 'hold'), (36, 100, 'hold'), (96, 0, 'hold')])
c.k('maskup', 's', [(0, (100, 0), 'hold'), (36, (100, 0), 'snap'), (44, (100, 100), 'hold'), (88, (100, 100), 'in'), (96, (100, 0), 'hold')])
c.hands([(0, {'L': 'fist', 'R': 'fist'}), (36, {'L': 'open', 'R': 'open'}), (94, {'L': 'fist', 'R': 'fist'})])
c.pop('sweat', 12, 104, peak=100, pos_keys=[(12, (0, 0), 'io'), (104, (0, 14), 'hold')])
c.osc('root', 'p2', (1.2, 0), 6, 0)

c = clip('mood_smile_wink', 'mood', 76, False, 'Confident smile and wink, with a sparkle.')
c.breeze(19, 6)
wk = NP(head=7, headp=(2, 0), armR=-118, armL=24, roots=(102, 98), spin=2)
c.seq([(0, NP(), 'io'), (10, wk, 'snap'), (14, wk, 'hold'), (56, wk, 'io'), (70, NP(), 'hold'), (76, NP(), 'hold')])
c.hands([(0, {'R': 'fist'}), (8, {'R': 'point'}), (62, {'R': 'fist'})])
c.face([(0, dict()), (10, dict(eyes='wink', mouth='grin')), (60, dict(eyes='open', mouth='none'))])
c.pop('spark0', 12, 34, (326, 246), 90, rot=[(12, 0, 'lin'), (34, 90, 'hold')])
c.pop('spark1', 16, 30, (354, 284), 50)

# ================================================================ FUN
c = clip('fun_spin', 'fun', 64, False, 'Spinning jump kick with a swoosh trail.')
c.breeze(16, 7)
c.seq([(0, NP(), 'io'), (6, NP(roots=(112, 86), armL=50, armR=-50), 'snap'), (14, NP(root=(0, -66), armL=100, armR=-100, legL=8, legR=-82), 'lin'),
       (24, NP(root=(0, -78), armL=100, armR=-100, legL=8, legR=-82), 'in'), (34, NP(root=(0, -40), armL=110, armR=-110), 'in'),
       (38, NP(roots=(110, 88), armL=60, armR=-60, legL=12, legR=-12), 'io'), (48, FIGHT, 'hold'), (54, FIGHT, 'io'), (64, NP(), 'hold')])
c.k('spin', 's2', [(0, (100, 100), 'hold'), (10, (100, 100), 'lin'), (16, (-100, 100), 'lin'), (22, (100, 100), 'lin'), (28, (-100, 100), 'lin'), (34, (100, 100), 'hold')])
c.keys.pop(('spin', 'r'), None)
c.k('spin', 'r', [(0, 0, 'hold'), (12, 0, 'io'), (24, -16, 'io'), (34, 0, 'io'), (48, -3, 'hold'), (54, -3, 'io'), (64, 0, 'hold')])
c.face([(0, dict()), (6, dict(eyes='sharp', brows='angry', mouth='shout')), (36, dict(mouth='grin', brows='det')), (56, dict(eyes='open', mouth='none'))])
c.pop('swoosh2', 12, 34, peak=100, pos_keys=[(12, (256, 352), 'lin'), (34, (256, 362), 'hold')], rot=[(12, -60, 'lin'), (34, 300, 'hold')])
c.pop('swoosh', 16, 32, peak=(100, 70), pos_keys=[(16, (256, 400), 'lin'), (32, (256, 410), 'hold')], rot=[(16, 140, 'lin'), (32, 470, 'hold')])
shadow(c, [(0, 0, 'io'), (6, 0, 'out'), (16, 70, 'lin'), (24, 78, 'in'), (36, 0, 'io')])
c.puff('dust0', 36, 52, (210, 462), 80); c.puff('dust1', 37, 53, (302, 462), 80)

c = clip('fun_peek', 'fun', 96, False, 'Peeks in from the right edge of the canvas, then vanishes in a smoke puff.')
c.breeze(24, 5)
pk = NP(root=(208, 0), rootr=-14, head=-10, headp=(-4, 0), eyes=(-10, 0), armL=70, legL=0)
c.seq([(0, NP(root=(330, 0), rootr=-14, head=-10, armL=70), 'io'), (16, pk, 'hold'), (30, pk, 'io'), (38, dict(pk, **P(head=-16, headp=(-6, 2))), 'io'),
       (50, dict(pk, **P(head=-16, headp=(-6, 2))), 'io'), (58, pk, 'hold'), (96, pk, 'hold')])
c.k('shadow', 'p', [(0, (330, 0), 'io'), (16, (208, 0), 'hold')])
c.hands([(0, {'L': 'open'})])
c.face([(0, dict(eyes='open', brows='up')), (36, dict(eyes='sharp', brows='det', mouth='grin'))])
c.blink(26)
c.vis('root', [(70, False)], 100); c.vis('shadow', [(70, False)], 100)
c.pop('bigsmoke', 66, 92, (448, 368), 85, inn=4, outt=12)
c.puff('smoke0', 68, 90, (404, 420), 90)

c = clip('fun_notify', 'fun', 120, False, 'Unrolls a small scroll with a "!" on it, held up toward the viewer.')
c.breeze(30, 5)
hold = NP(armL=104, armR=-104, root=(0, 0), head=0, headp=(0, -2))
c.seq([(0, NP(), 'io'), (10, hold, 'hold'), (100, hold, 'io'), (114, NP(), 'hold'), (120, NP(), 'hold')])
c.hands([(0, {'L': 'fist', 'R': 'fist'}), (10, {'L': 'open', 'R': 'open'}), (104, {'L': 'fist', 'R': 'fist'})])
c.k('scroll', 'p', [(0, (256, 318), 'hold'), (30, (256, 318), 'io'), (40, (256, 312), 'io'), (80, (256, 312), 'io'), (90, (256, 318), 'hold')])
c.k('scroll', 'o', [(0, 0, 'hold'), (8, 100, 'hold'), (108, 0, 'hold')])
c.k('scroll', 's', [(0, (0, 0), 'hold'), (8, (0, 0), 'snap'), (14, (100, 100), 'io'), (30, (100, 100), 'io'), (40, (116, 116), 'hold'), (80, (116, 116), 'io'),
                    (90, (100, 100), 'hold'), (100, (100, 100), 'in'), (108, (0, 0), 'hold')])
c.k('scroll_paper', 's', [(0, (100, 0), 'hold'), (14, (100, 0), 'io'), (28, (100, 100), 'hold'), (90, (100, 100), 'io'), (100, (100, 0), 'hold')])
c.k('scroll_bottom', 'p', [(0, (0, 0), 'hold'), (14, (0, 0), 'io'), (28, (0, 96), 'hold'), (90, (0, 96), 'io'), (100, (0, 0), 'hold')])
c.face([(0, dict()), (12, dict(brows='up', mouth='smile')), (40, dict(eyes='sharp', brows='det', mouth='grin')), (96, dict(eyes='open', mouth='none'))])
c.pop('spark0', 36, 52, (334, 330), 80); c.pop('spark1', 40, 56, (176, 380), 60)

c = clip('fun_shadow_clone', 'fun', 110, False, 'Two translucent copies pop out beside it, wave, then disappear in smoke.')
c.breeze(22, 6)
sign2 = NP(armL=-52, armR=52)
c.seq([(0, NP(), 'io'), (8, sign2, 'snap'), (12, dict(sign2, **P(roots=(104, 96))), 'hold'), (30, sign2, 'io'), (40, NP(armL=-58, armR=58, legL=12, legR=-12), 'hold'),
       (90, NP(armL=-58, armR=58, legL=12, legR=-12), 'io'), (104, NP(), 'hold'), (110, NP(), 'hold')])
c.hands([(0, {'R': 'fist'}), (8, {'R': 'point'}), (30, {'R': 'fist'})])
c.face([(0, dict()), (8, dict(eyes='sharp', brows='angry')), (40, dict(eyes='sharp', brows='det', mouth='grin')), (96, dict(eyes='open', mouth='none'))])
for pre, dx, side in (('c1_', -134, 'L'), ('c2_', 134, 'R')):
    c.k(pre + 'root', 'o', [(0, 0, 'hold'), (18, 100, 'hold'), (84, 0, 'hold')])
    c.k(pre + 'root', 'p', [(0, (dx, 0), 'hold')])
    c.k(pre + 'root', 's', [(0, (86, 86), 'hold'), (18, (60, 60), 'snap'), (24, (86, 86), 'hold'), (78, (86, 86), 'in'), (84, (40, 40), 'hold')])
    sh = 'c1shadow' if pre == 'c1_' else 'c2shadow'
    c.k(sh, 'o', [(0, 0, 'hold'), (18, 100, 'hold'), (84, 0, 'hold')]); c.k(sh, 'p', [(0, (dx, 0), 'hold')])
    arm = pre + 'arm' + side; up = 150 if side == 'L' else -150
    rest = 22 if side == 'L' else -22
    c.k(arm, 'r', [(0, 0, 'hold'), (26, 0, 'io'), (34, up - rest, 'sine'), (40, up - rest + (25 if side == 'L' else -25), 'sine'), (46, up - rest, 'sine'),
                   (52, up - rest + (25 if side == 'L' else -25), 'sine'), (58, up - rest, 'io'), (68, 0, 'hold')])
    c.hands([(0, {side: 'fist'}), (28, {side: 'open'}), (64, {side: 'fist'})], pre=pre)
    c.face([(0, dict(eyes='happy', mouth='smile', brows='calm'))], pre=pre)
    c.breeze(22, 6, pre=pre)
    c.k(pre + 'head', 'r', [(26, 0, 'io'), (36, -6 if side == 'L' else 6, 'io'), (58, -6 if side == 'L' else 6, 'io'), (66, 0, 'hold')])
c.puff('smoke0', 14, 36, (122, 384), 110); c.puff('smoke1', 14, 36, (390, 384), 110)
c.puff('smoke2', 78, 100, (122, 384), 110); c.puff('smoke3', 78, 100, (390, 384), 110)

c = clip('fun_throw_shuriken', 'fun', 84, False, 'Throws a shuriken off-screen; it boomerangs back to be caught.')
c.breeze(21, 6)
wind = NP(armR=-168, armL=40, spin=-6, head=-3, legL=10, legR=-10)
thr = NP(armR=-62, armL=60, spin=6, head=3, legL=12, legR=-14, eyes=(9, 0))
catch = NP(armR=-96, armL=40, spin=2, head=4, eyes=(10, -2), legL=10, legR=-10)
c.seq([(0, NP(), 'io'), (12, wind, 'hold'), (16, wind, 'snap'), (20, thr, 'hold'), (30, thr, 'io'), (40, NP(armR=-80, armL=40, eyes=(10, -2), head=4, legL=10, legR=-10), 'io'),
       (54, catch, 'snap'), (58, dict(catch, **P(spin=-2, roots=(104, 96))), 'io'), (66, catch, 'io'), (78, NP(), 'hold'), (84, NP(), 'hold')])
c.k('shurikenHand', 'o', [(0, 0, 'hold'), (6, 100, 'hold'), (18, 0, 'hold'), (55, 100, 'hold'), (74, 0, 'hold')])
c.k('shurikenHand', 's', [(0, (0, 0), 'hold'), (6, (0, 0), 'snap'), (10, (100, 100), 'hold'), (55, (100, 100), 'hold'), (68, (100, 100), 'in'), (74, (0, 0), 'hold')])
c.k('shurikenHand', 'r', [(55, 0, 'out'), (64, 200, 'hold')])
c.k('shuriken', 'o', [(0, 0, 'hold'), (18, 100, 'hold'), (55, 0, 'hold')])
c.k('shuriken', 's', [(0, (0, 0), 'hold'), (18, (100, 100), 'hold')])
c.k('shuriken', 'p', [(18, (346, 366), 'out'), (30, (560, 300), 'hold'), (36, (560, 250), 'in'), (55, (348, 340), 'hold')])
c.k('shuriken', 'r', [(18, 0, 'lin'), (55, 2400, 'hold')])
c.pop('speed', 18, 30, peak=(80, 60), pos_keys=[(18, (330, 368), 'lin'), (30, (440, 330), 'hold')], rot=[(18, -16, 'hold')])
c.pop('spark0', 54, 66, (346, 330), 80)
c.face([(0, dict()), (8, dict(eyes='sharp', brows='angry', mouth='flat')), (18, dict(mouth='shout')), (26, dict(mouth='flat')), (56, dict(eyes='wink', brows='det', mouth='grin')),
        (74, dict(eyes='open', mouth='none'))])

# ================================================================ THROWN (window flung by the app; side clips face right)
def wiggle(c, node, prop, amp, period, t0, t1, center=None):
    """sine wiggle from t0 to t1 that fades in and out, starting and ending on center"""
    center = (0, 0) if center is None and prop in ('p', 'p2') else (0 if center is None else center)
    keys = [(t0, center, 'sine')]
    k = 1
    while t0 + k * period / 2 < t1 - period / 4:
        t = t0 + k * period / 2 - period / 4
        f = math.sin(math.pi * (t - t0) / (t1 - t0)) * (1 if k % 2 else -1)
        v = tuple(cc + a * f for cc, a in zip(center, amp)) if isinstance(center, tuple) else center + amp * f
        keys.append((t, v, 'sine')); k += 1
    keys.append((t1, center, 'hold'))
    c.k(node, prop, keys)
def orbit(c, t0, t1, period=24, cx=256, cy=180, rx=92, ry=20):
    """three dizzy stars circling over the head, bigger when in front"""
    step = period / 12
    times = [t0 + k * step for k in range(int((t1 - t0) / step) + 1) if t0 + k * step < t1] + [t1]
    for j in range(3):
        ang = lambda t: 2 * math.pi * ((t - t0) / period + j / 3)
        c.pop(f'star{j}', t0, t1, peak=100, inn=6, outt=6,
              pos_keys=[(t, (cx + rx * math.cos(ang(t)), cy + ry * math.sin(ang(t))), 'lin') for t in times])
        c.k(f'star{j}', 's2', [(t, (92 + 22 * math.sin(ang(t)),) * 2, 'lin') for t in times])
        c.k(f'star{j}', 'r', [(t0, 0, 'lin'), (t1, 9 * (t1 - t0), 'hold')])
def dizzy_eyes(c, t0, t1, turns=3):
    for side in 'LR':
        c.k('spiral' + side, 'r', [(t0, 0, 'lin'), (t1, -360 * turns, 'hold')])
STREAM_DOWN = P(scarf1_R=96, scarf2_R=-4, scarf3_R=-4, htailA1_R=80, htailA2_R=6, htailB1_R=96, htailB2_R=4)
def still(c, node, **kw):
    for prop, v in kw.items(): c.k(node, prop, [(0, v, 'hold')])

c = clip('thrown_tumble', 'thrown', 24, True, 'Thrown sideways: curled into a ball, rolling head over heels with spinning spiral eyes.')
ball = NP(root=(0, -96), roots=(88, 88), armL=-40, armR=40, legL=-30, legR=30, headp=(0, 10))
c.seq([(0, ball, 'hold'), (24, ball, 'hold')])
c.keys.pop(('spin', 'r'), None)
c.k('spin', 'r', [(0, 0, 'lin'), (24, 360, 'lin')])
c.osc('root', 'p2', (0, 52), 24, -0.25, (0, 52))   # roll on the head when upside down, on the feet when upright
c.breeze(12, 10)
c.face([(0, dict(eyes='spiral', brows='worried', mouth='wavy'))])
dizzy_eyes(c, 0, 24, 2)
c.hands([(0, {'L': 'fist', 'R': 'fist'})])
still(c, 'speed2', o=100, s=(80, 70), p=(26, 330))
c.osc('speed2', 's2', (14, 0), 6, 0, (100, 100))
still(c, 'shadow', s=(84, 84))

c = clip('thrown_flail', 'thrown', 24, True, 'Thrown sideways: flies along leaning back, arms and legs flailing, big panicked eyes, sweat drop.')
fly = NP(root=(0, -50), spin=-18, head=-8, headp=(-4, 0), eyes=(9, 0))
c.seq([(0, fly, 'hold'), (24, fly, 'hold')])
c.seq([(0, P(scarf1_R=176, scarf2_R=-4, scarf3_R=-6, htailA1_R=-64, htailB1_R=-44), 'hold'), (24, P(scarf1_R=176, scarf2_R=-4, scarf3_R=-6, htailA1_R=-64, htailB1_R=-44), 'hold')])
c.breeze(8, 8)
c.osc('armL', 'r', 34, 8, 0.0, center=106); c.osc('armR', 'r', -34, 8, 0.3, center=-100)
c.osc('legL', 'r2', 28, 8, 0.0); c.osc('legR', 'r2', -28, 8, 0.25)
c.osc('spin', 'r2', 4, 12, 0)
c.face([(0, dict(eyes='big', brows='worried', mouth='shout'))])
c.hands([(0, {'L': 'open', 'R': 'open'})])
still(c, 'sweat', o=100); c.osc('sweat', 's', (10, 10), 12, 0, (100, 100))
still(c, 'speed2', o=100, s=(90, 80), p=(18, 300))
c.osc('speed2', 's2', (14, 0), 6, 0, (100, 100))
still(c, 'shadow', s=(60, 60))

c = clip('thrown_up_whee', 'thrown', 30, True, 'Thrown up: arms out in a V, legs swinging, happy eyes and an open-mouthed "whee!", sparkles.')
REACH = dict(armL_s=(100, 280), armR_s=(100, 280), handL_s=(100, 35.7), handR_s=(100, 35.7))   # arms stretched past the big head
whee = NP(root=(0, -36), armL=142, armR=-142, legL=-14, legR=14, headp=(0, -3), roots=(97, 104), **REACH)
c.seq([(0, whee, 'hold'), (30, whee, 'hold')])
c.seq([(0, STREAM_DOWN, 'hold'), (30, STREAM_DOWN, 'hold')])
c.breeze(10, 6)
c.osc('spin', 'r2', 6, 30, 0); c.osc('head', 'r2', 4, 30, 0.1)
c.osc('armL', 'r2', 10, 15, 0); c.osc('armR', 'r2', -10, 15, 0)
c.osc('legL', 'r2', 14, 10, 0); c.osc('legR', 'r2', -14, 10, 0.5)
c.face([(0, dict(eyes='happy', brows='calm', mouth='shout', blush=True))])
c.hands([(0, {'L': 'open', 'R': 'open'})])
c.pop('spark0', 2, 16, (150, 210), 80); c.pop('spark1', 12, 26, (362, 170), 70); c.pop('spark2', 20, 29, (380, 300), 55)
still(c, 'speed2', o=100, s=(80, 90), p=(256, 404), r=90)
c.osc('speed2', 's2', (14, 0), 6, 0, (100, 100))
still(c, 'shadow', o=0)

c = clip('thrown_panic', 'thrown', 24, True, 'Thrown up or down: flails its arms over its head, legs kicking, blank shocked eyes, "!" and a sweat drop.')
pan = NP(root=(0, -40), armL=140, armR=-140, roots=(98, 104))
c.seq([(0, pan, 'hold'), (24, pan, 'hold')])
c.seq([(0, STREAM_DOWN, 'hold'), (24, STREAM_DOWN, 'hold')])
c.breeze(8, 8)
c.osc('armL', 'r', 26, 6, 0.0, center=118); c.osc('armR', 'r', -26, 6, 0.5, center=-118)
c.osc('legL', 'r2', 26, 8, 0.0); c.osc('legR', 'r2', -26, 8, 0.5)
c.osc('spin', 'r2', 4, 12, 0)
c.face([(0, dict(eyes='dot', brows='up', mouth='shout')), (12, dict(eyes='big'))])
c.hands([(0, {'L': 'open', 'R': 'open'})])
still(c, 'exclaim', o=100, p=(352, 168)); c.osc('exclaim', 's', (12, 12), 12, 0, (100, 100))
still(c, 'sweat', o=100); c.osc('sweat', 's', (10, 10), 12, 0.25, (100, 100))
still(c, 'shadow', o=0)

c = clip('thrown_down_dive', 'thrown', 20, True, 'Thrown down: head-first ninja dive, arms out in front, sharp eyes and a battle cry, speed lines above.')
dive = NP(root=(0, -160), spin=180, armL=166, armR=-166, legL=6, legR=-6, **REACH)
c.seq([(0, dive, 'hold'), (20, dive, 'hold')])
c.seq([(0, STREAM_DOWN, 'hold'), (20, STREAM_DOWN, 'hold')])
c.breeze(10, 7)
c.osc('spin', 'r2', 5, 20, 0); c.osc('legL', 'r2', 10, 10, 0); c.osc('legR', 'r2', -10, 10, 0.5)
c.face([(0, dict(eyes='sharp', brows='angry', mouth='shout'))])
c.hands([(0, {'L': 'open', 'R': 'open'})])
still(c, 'speed2', o=100, s=(80, 90), p=(256, 132), r=-90)
c.osc('speed2', 's2', (14, 0), 5, 0, (100, 100))
still(c, 'shadow', o=0)

# ================================================================ LANDINGS after a throw
c = clip('land_dizzy', 'landing', 120, False, 'Crash-lands with a squash, wobbles around with spiral eyes and stars circling its head, then shakes it off.')
c.breeze(30, 5)
arms = dict(armL=40, armR=-40)
c.seq([(0, NP(root=(0, -60), armL=120, armR=-120), 'in'), (5, NP(roots=(122, 76), armL=70, armR=-70, legL=18, legR=-18), 'snap'),
       (12, NP(roots=(94, 108), root=(0, -14), **arms), 'io'), (18, NP(roots=(104, 97), **arms), 'io'), (24, NP(**arms), 'hold'), (86, NP(**arms), 'io'),
       (91, NP(head=-12), 'io'), (95, NP(head=12), 'io'), (99, NP(head=-8), 'io'), (103, NP(head=4), 'io'), (110, NP(), 'hold'), (120, NP(), 'hold')])
wiggle(c, 'spin', 'r2', 9, 24, 18, 88); wiggle(c, 'root', 'p2', (8, 0), 24, 24, 88); wiggle(c, 'head', 'r2', 7, 16, 18, 88)
c.face([(0, dict(eyes='big', brows='up', mouth='o')), (5, dict(eyes='squint', brows='worried', mouth='shout')), (14, dict(eyes='spiral', mouth='wavy')),
        (90, dict(eyes='squint', brows='det', mouth='flat')), (106, dict(eyes='open', mouth='none'))])
dizzy_eyes(c, 14, 90, 4)
orbit(c, 16, 90)
c.hands([(0, {'L': 'open', 'R': 'open'}), (24, {'L': 'fist', 'R': 'fist'})])
c.k('shadow', 's', [(0, (60, 60), 'in'), (5, (124, 124), 'io'), (18, (100, 100), 'hold')])
c.puff('dust0', 5, 24, (196, 460), 95); c.puff('dust1', 6, 25, (316, 460), 95)
c.pop('sweat', 92, 114, peak=100, pos_keys=[(92, (0, 0), 'io'), (114, (0, 12), 'hold')])

c = clip('land_splat', 'landing', 100, False, 'Splats flat as a pancake, quivers, pops back up with a boing, shakes itself off.')
c.breeze(25, 6)
flat = NP(roots=(150, 44), armL=96, armR=-96, legL=48, legR=-48)
c.seq([(0, NP(root=(0, -80), roots=(90, 112), armL=150, armR=-150), 'in'), (4, flat, 'hold'), (36, flat, 'in'),
       (40, NP(roots=(160, 38), armL=96, armR=-96, legL=48, legR=-48), 'snap'), (46, NP(root=(0, -44), roots=(84, 124), armL=150, armR=-150), 'out'),
       (54, NP(roots=(110, 90), armL=60, armR=-60), 'io'), (60, NP(roots=(97, 104)), 'io'), (66, NP(), 'hold'), (100, NP(), 'hold')])
wiggle(c, 'spin', 'p2', (2.5, 0), 4, 6, 34)
wiggle(c, 'spin', 'r2', 11, 5, 66, 86); wiggle(c, 'head', 'r2', -8, 5, 67, 87)
c.face([(0, dict(eyes='big', brows='up', mouth='shout')), (4, dict(eyes='squint', brows='worried', mouth='wavy')), (46, dict(eyes='dot', brows='up', mouth='o')),
        (64, dict(eyes='squint', brows='det', mouth='flat')), (88, dict(eyes='open', mouth='pout')), (96, dict(mouth='none'))])
c.hands([(0, {'L': 'open', 'R': 'open'}), (60, {'L': 'fist', 'R': 'fist'})])
c.k('shadow', 's', [(0, (60, 60), 'in'), (4, (150, 120), 'hold'), (40, (150, 120), 'io'), (46, (70, 70), 'in'), (54, (106, 106), 'io'), (66, (100, 100), 'hold')])
c.puff('dust0', 4, 22, (170, 458), 105); c.puff('dust1', 4, 22, (342, 458), 105)
c.puff('smoke0', 66, 84, (200, 430), 45); c.puff('smoke1', 70, 88, (316, 420), 45)
c.pop('sweat', 48, 92, peak=100, pos_keys=[(48, (0, 0), 'io'), (92, (0, 14), 'hold')])

c = clip('land_dust_off', 'landing', 110, False, 'Lands with a stumble, pats the dust off its gi with a grumpy -_- face, then turns away: "hmph".')
c.breeze(27, 5)
patL = NP(armL=-30, spin=-2); patR = NP(armR=30, spin=2); mid = NP(armL=10, armR=-10)
hmph = NP(head=-12, headp=(-4, 0), eyes=(-10, 0), armL=-58, armR=58, spin=-3)
c.seq([(0, NP(root=(0, -40), armL=110, armR=-110), 'in'), (4, NP(roots=(112, 88), armL=60, armR=-60, legL=14, legR=-14, spin=6), 'snap'),
       (10, NP(spin=-5, legL=-8), 'io'), (16, NP(), 'io'), (22, patL, 'snap'), (27, mid, 'io'), (32, patR, 'snap'), (37, mid, 'io'), (42, patL, 'snap'), (47, mid, 'io'),
       (52, patR, 'snap'), (58, NP(), 'io'), (66, hmph, 'snap'), (96, hmph, 'io'), (106, NP(), 'hold'), (110, NP(), 'hold')])
c.face([(0, dict(eyes='big', brows='up', mouth='o')), (4, dict(eyes='squint', brows='worried', mouth='shout')), (14, dict(eyes='meh', brows='angry', mouth='pout')),
        (62, dict(eyes='squint')), (66, dict(eyes='meh')), (100, dict(eyes='open', brows='det', mouth='none'))])
c.hands([(0, {'L': 'open', 'R': 'open'}), (12, {'L': 'open', 'R': 'open'}), (58, {'L': 'fist', 'R': 'fist'})])
c.k('shadow', 's', [(0, (70, 70), 'in'), (4, (112, 112), 'io'), (16, (100, 100), 'hold')])
c.puff('dust0', 4, 18, (300, 462), 70)
c.puff('dust1', 22, 34, (238, 404), 40); c.puff('smoke2', 32, 44, (276, 404), 30); c.puff('smoke3', 42, 54, (232, 410), 30)
c.pop('anger', 68, 96, peak=100, scale=[(0, (0, 0), 'hold'), (68, (0, 0), 'snap'), (72, (120, 120), 'io'), (78, (95, 95), 'io'), (84, (115, 115), 'io'),
                                        (90, (100, 100), 'in'), (96, (0, 0), 'hold')])

assert len(CLIPS) == 47, len(CLIPS)
