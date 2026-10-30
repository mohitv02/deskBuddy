"""Pose sequences for each animation state."""
import math, copy
from rig import default_pose, wing_folded

TAU = 2 * math.pi


def blend(a, b, t):
    """Interpolate two poses (dicts / tuples / numbers)."""
    if isinstance(a, dict):
        return {k: blend(a[k], b[k], t) if k in b else a[k] for k in a}
    if isinstance(a, tuple):
        return tuple(blend(x, y, t) for x, y in zip(a, b))
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and \
            all(isinstance(x, (int, float)) for x in a + b):
        return [x + (y - x) * t for x, y in zip(a, b)]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * t
    return b if t >= 0.5 else a


def ease(t):
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------- wing poses
WING_UP = dict(t1=245, t2=265, phi=252, delta=34, fs=0.92, arm=1.0)
WING_DOWN = dict(t1=125, t2=105, phi=70, delta=-40, fs=0.8, arm=0.75)
WING_MID = dict(t1=205, t2=207, phi=180, delta=0, fs=0.75, arm=1.0)


def wing_flap(f, far=False):
    """f = +1 wings fully up, -1 fully down."""
    u = (1 - f) / 2                        # 0 up .. 1 down
    w = blend(WING_UP, WING_DOWN, u)
    w['fs'] *= 0.75 + 0.25 * abs(f)
    if far:
        w = dict(w, t1=w['t1'] + 14, t2=w['t2'] + 14, phi=w['phi'] + 16)
    return w


def folded(far=False):
    w = wing_folded()
    if far:
        w.update(t1=-140, t2=-60, phi=192)
    return w


def unwrap_folded(w):
    # express folded wing angles in the same winding as the flap set (t1/t2 positive)
    w = dict(w)
    w['t1'] = w['t1'] % 360
    w['t2'] = w['t2'] % 360
    return w


FOLD_N = unwrap_folded(folded())
FOLD_F = unwrap_folded(folded(True))


def stand():
    P = default_pose()
    P['wn'] = dict(FOLD_N)
    P['wf'] = dict(FOLD_F)
    return P


def set_feet_ground(P, offsets=None):
    bx = P['bx']
    o = offsets or {}
    base = dict(bn=(bx - 15, 185), bf=(bx - 8, 184), fn=(bx + 21, 185), ff=(bx + 28, 184))
    P['feet'] = {k: (base[k][0] + o.get(k, (0, 0))[0], base[k][1] + o.get(k, (0, 0))[1])
                 for k in base}


def fly_pose(p, by=126):
    """p in [0,1): flap cycle. Returns flying pose."""
    P = stand()
    f = math.cos(TAU * p)
    P['by'] = by + 3.5 * math.sin(TAU * p)          # body rises on downstroke
    P['br'] = -0.06 + 0.03 * math.sin(TAU * p)
    P['wn'] = wing_flap(f)
    P['wf'] = wing_flap(math.cos(TAU * p - 0.6), far=True)
    P['head_dx'], P['head_dy'], P['head_r'] = 52, -27 + 1.5 * math.sin(TAU * p + 0.6), 0.02
    P['neck_bend'] = -0.4
    P['tail_lift'], P['tail_droop'] = 0.12, 0.06
    P['tail_amp'], P['tail_phase'] = 0.12, TAU * p
    bx, by_ = P['bx'], P['by']
    P['feet'] = dict(bn=(bx - 30, by_ + 17), bf=(bx - 25, by_ + 15),
                     fn=(bx + 18, by_ + 19), ff=(bx + 24, by_ + 17))
    P['foot_tilt'] = dict(bn=2.2, bf=2.2, fn=1.2, ff=1.2)
    P['shadow'] = 0.35
    return P


# ------------------------------------------------------------- animations
def idle(n=12, blink=False):
    out = []
    for i in range(n):
        p = i / n
        P = stand()
        s = math.sin(TAU * p)
        P['breath'] = s
        P['head_dy'] += 1.2 * s
        P['head_r'] += 0.03 * math.sin(TAU * p + 1)
        P['tail_amp'] = 0.06
        P['tail_phase'] = TAU * p
        P['wn']['t2'] += 2 * s
        if blink and i in (5, 6):
            P['eye'] = 0.0 if i == 5 else 0.45
        out.append(P)
    return out


def walk(n=8, stride=20.0):
    out = []
    phase = dict(bn=0.0, ff=0.0, bf=0.5, fn=0.5)
    for i in range(n):
        p = i / n
        P = stand()
        P['by'] += 1.4 * math.sin(2 * TAU * p + 0.6)
        P['br'] = 0.02 * math.sin(2 * TAU * p)
        P['head_dy'] += 1.6 * math.sin(2 * TAU * p + 1.4)
        P['head_r'] = 0.06
        P['tail_amp'], P['tail_phase'] = 0.1, TAU * p
        offs = {}
        for k, ph in phase.items():
            q = (p + ph) % 1.0
            if q < 0.5:                                 # stance: foot slides back
                x = stride / 2 - (q / 0.5) * stride
                y = 0
            else:                                       # swing: lift & move forward
                s = (q - 0.5) / 0.5
                x = -stride / 2 + ease(s) * stride
                y = -math.sin(math.pi * s) * 7
            offs[k] = (x, y)
        set_feet_ground(P, offs)
        P['wn']['t2'] += 3 * math.sin(2 * TAU * p)
        out.append(P)
    return out


def fly(n=8):
    return [fly_pose(i / n) for i in range(n)]


def takeoff():
    S = stand()
    crouch = stand()
    crouch['by'] += 7
    crouch['head_dy'] += 4
    crouch['head_r'] = 0.25
    crouch['wn'] = wing_flap(0.85)
    crouch['wf'] = wing_flap(0.8, far=True)
    crouch['tail_lift'] = 0.5
    leap = stand()
    leap['by'] -= 14
    leap['br'] = -0.18
    leap['head_dy'] -= 4
    leap['head_r'] = -0.1
    leap['wn'] = wing_flap(-0.55)
    leap['wf'] = wing_flap(-0.45, far=True)
    leap['feet'] = dict(bn=(S['bx'] - 26, 183), bf=(S['bx'] - 20, 182),
                        fn=(S['bx'] + 16, 176), ff=(S['bx'] + 22, 175))
    leap['foot_tilt'] = dict(bn=0.9, bf=0.9, fn=0.6, ff=0.6)
    leap['shadow'] = 0.8
    seq = [
        S,
        blend(S, crouch, 0.55),
        crouch,
        blend(crouch, leap, 0.6),
        leap,
        blend(leap, fly_pose(0.5), 0.5),
        fly_pose(0.62),
        fly_pose(0.85),
    ]
    seq[5]['wn'] = wing_flap(0.6)
    seq[5]['wf'] = wing_flap(0.5, far=True)
    return seq


def land():
    S = stand()
    flare = fly_pose(0.0)
    flare['br'] = -0.22
    flare['by'] = 150
    flare['wn'] = wing_flap(0.95)
    flare['wf'] = wing_flap(0.9, far=True)
    bx = flare['bx']
    flare['feet'] = dict(bn=(bx - 16, 178), bf=(bx - 10, 177), fn=(bx + 20, 176), ff=(bx + 26, 175))
    flare['foot_tilt'] = dict(bn=0.4, bf=0.4, fn=0.3, ff=0.3)
    flare['head_dy'] = -38
    flare['head_r'] = -0.05
    flare['shadow'] = 0.7
    touch = stand()
    touch['by'] += 8
    touch['br'] = -0.05
    touch['wn'] = wing_flap(0.3)
    touch['wf'] = wing_flap(0.2, far=True)
    touch['head_dy'] += 6
    touch['head_r'] = 0.25
    touch['tail_lift'] = 0.55
    settle = blend(touch, S, 0.5)
    settle['wn'] = blend(wing_flap(0.3), FOLD_N, 0.6)
    settle['wf'] = blend(wing_flap(0.2, far=True), FOLD_F, 0.6)
    seq = [
        fly_pose(0.25),
        blend(fly_pose(0.5), flare, 0.5),
        flare,
        blend(flare, touch, 0.55),
        touch,
        settle,
        blend(settle, S, 0.6),
        S,
    ]
    return seq


def fire(windup=4, ramp=2, sustain=6, cool=3):
    S = stand()
    back = stand()
    back['bx'] -= 3
    back['br'] = -0.05
    back['head_dx'], back['head_dy'], back['head_r'] = 40, -44, -0.3
    back['jaw'] = 0.18
    back['belly_glow'] = 1.0
    back['fire_glow'] = 1.0
    back['breath'] = 1.2
    back['neck_bend'] = 0.3
    back['tail_lift'] = 0.5
    blast = stand()
    blast['bx'] += 2
    blast['br'] = 0.03
    blast['head_dx'], blast['head_dy'], blast['head_r'] = 54, -31, 0.06
    blast['jaw'] = 1.0
    blast['belly_glow'] = 0.55
    blast['neck_bend'] = -0.3
    blast['tail_lift'] = 0.42
    blast['wn'] = blend(FOLD_N, wing_flap(0.6), 0.55)
    blast['wf'] = blend(FOLD_F, wing_flap(0.6, far=True), 0.55)
    out = []
    for i in range(windup):
        t = ease((i + 1) / windup)
        out.append(blend(S, back, t))
    for i in range(ramp):
        t = (i + 1) / (ramp + 1)
        P = blend(back, blast, ease(min(1, t * 1.6)))
        P['fire'] = 0.35 + 0.65 * t
        P['fire_t'] = (i - ramp) / sustain
        out.append(P)
    for i in range(sustain):
        p = i / sustain
        P = copy.deepcopy(blast)
        P['fire'] = 1.0
        P['fire_t'] = p
        P['head_dy'] += 0.8 * math.sin(TAU * p)
        P['head_r'] += 0.02 * math.sin(TAU * p * 2)
        P['breath'] = -0.6
        P['tail_amp'], P['tail_phase'] = 0.06, TAU * p
        out.append(P)
    for i in range(cool):
        t = (i + 1) / (cool + 1)
        P = blend(blast, S, ease(t))
        P['fire'] = 0.0
        P['jaw'] = 1.0 - t
        P['fire_glow'] = 1 - t
        P['smoke'] = [(36 + 8 * t + k * 4, 2 - 10 * t - k * 6, 3 + 3 * t + k * 1.5, 0.55 * (1 - t * 0.7))
                      for k in range(4)]
        out.append(P)
    return out, (windup + ramp, windup + ramp + sustain - 1)


def sleep_pose():
    P = stand()
    P['by'] = 166
    P['head_dx'], P['head_dy'], P['head_r'] = 50, 4, 0.04
    P['neck_bend'] = -0.9
    P['eye'] = 0.0
    P['tail_lift'], P['tail_droop'] = 0.05, 0.3
    bx = P['bx']
    P['feet'] = dict(bn=(bx - 6, 186), bf=(bx - 2, 185), fn=(bx + 36, 186), ff=(bx + 42, 185))
    P['foot_tilt'] = dict(bn=0, bf=0, fn=0, ff=0)
    P['wn'] = dict(FOLD_N, t1=FOLD_N['t1'] + 12, t2=FOLD_N['t2'] + 8)
    return P


def lie_down(n=6):
    S = stand()
    L = sleep_pose()
    mid = blend(S, L, 0.5)
    mid['head_r'] = 0.3
    out = []
    for i in range(n):
        t = ease(i / (n - 1))
        P = blend(S, L, t) if i < n // 2 else blend(mid, L, (i - n // 2 + 1) / (n - n // 2))
        P['eye'] = 1.0 if i < n - 2 else (0.35 if i == n - 2 else 0.0)
        out.append(P)
    return out


def sleep(n=8):
    out = []
    for i in range(n):
        p = i / n
        P = sleep_pose()
        s = math.sin(TAU * p)
        P['breath'] = 0.8 * s
        P['by'] -= 0.6 * s
        P['head_dy'] += 0.4 * s
        puffs = []
        for k in range(3):
            u = (p + k / 3) % 1.0
            puffs.append((36 + u * 10, -4 - u * 18, 1.6 + u * 3.5, 0.5 * (1 - u)))
        P['smoke'] = puffs
        out.append(P)
    return out


def dragged(n=6):
    out = []
    for i in range(n):
        p = i / n
        P = stand()
        P['bx'], P['by'] = 150, 98
        P['br'] = -1.2 + 0.06 * math.sin(TAU * p)
        P['head_dx'], P['head_dy'], P['head_r'] = 10, -54, -0.35 + 0.05 * math.sin(TAU * p)
        P['neck_bend'] = 0.2
        P['jaw'] = 0.35 + 0.15 * math.sin(TAU * p)
        P['tail_lift'], P['tail_droop'] = 0.15, -0.04
        P['tail_amp'], P['tail_phase'] = 0.22, TAU * p
        f = 0.15 + 0.45 * math.sin(TAU * p)
        P['wn'] = wing_flap(f)
        P['wf'] = wing_flap(f + 0.15, far=True)
        for w in (P['wn'], P['wf']):
            w['fs'] *= 0.8
        # legs dangle and kick
        from rig import to_world
        P['feet'] = {}
        for k, hip, ph in [('bn', (-19, 5), 0.0), ('bf', (-15, 3), 0.5),
                           ('fn', (16, 7), 0.25), ('ff', (19, 5), 0.75)]:
            hw = to_world(P, hip)
            kick = math.sin(TAU * (p + ph))
            P['feet'][k] = (hw[0] + 4 + 3 * kick, hw[1] + 27 - 4 * max(0, kick))
        P['foot_tilt'] = dict(bn=1.3, bf=1.3, fn=1.1, ff=1.1)
        P['shadow'] = 0.0
        out.append(P)
    return out


def fall(n=4):
    out = []
    for i in range(n):
        p = i / n
        P = stand()
        P['by'] = 128
        P['br'] = 0.05
        P['head_dx'], P['head_dy'], P['head_r'] = 46, -36, -0.2
        P['jaw'] = 0.55
        P['tail_lift'], P['tail_droop'] = 0.75, -0.03
        P['tail_amp'], P['tail_phase'] = 0.2, TAU * p
        f = 0.45 + 0.5 * math.cos(TAU * p)
        P['wn'] = wing_flap(f)
        P['wf'] = wing_flap(math.cos(TAU * p + 0.8) * 0.5 + 0.45, far=True)
        bx, by = P['bx'], P['by']
        k = math.sin(TAU * p)
        P['feet'] = dict(bn=(bx - 30, by + 26 + 2 * k), bf=(bx - 24, by + 24 - 2 * k),
                         fn=(bx + 32, by + 24 - 2 * k), ff=(bx + 38, by + 22 + 2 * k))
        P['foot_tilt'] = dict(bn=0.8, bf=0.8, fn=0.7, ff=0.7)
        P['shadow'] = 0.15
        out.append(P)
    return out
