"""Front-view animations: Ember coming towards you, and face-to-face tricks."""
import math, copy
from front import front_pose
from anims import blend, ease

TAU = 2 * math.pi
FEET = dict(r=(16.0, 0.0), l=(-16.0, 0.0), hr=(31.0, -3.0), hl=(-31.0, -3.0))


def ease_out(t):
    return 1 - (1 - t) ** 2


def idle_front(n=12, blink=False):
    out = []
    for i in range(n):
        p = i / n
        F = front_pose()
        s = math.sin(TAU * p)
        F['breath'] = s
        F['head'] = (0.0, -54.0 - 1.2 * s)
        F['head_r'] = 0.025 * math.sin(TAU * p + 1)
        F['tail_x'] = 0.8 + 0.12 * math.sin(TAU * p)
        F['wing_th'] = [30, 30]
        if blink and i in (5, 6):
            F['eye'] = 0.0 if i == 5 else 0.45
        out.append(F)
    return out


def walk_front_pose(p, k=1.0):
    """p: 0..1 walk cycle (two steps). Diagonal pairs move together."""
    F = front_pose()
    F['k'] = k
    feet = dict(FEET)
    for key, ph in (('r', 0.0), ('hl', 0.0), ('l', 0.5), ('hr', 0.5)):
        q = (p + ph) % 1.0
        lift = math.sin(math.pi * q / 0.5) * 8 if q < 0.5 else 0.0
        x, y = feet[key]
        feet[key] = (x, y - lift)
    F['feet'] = feet
    F['lift'] = 1.2 * abs(math.sin(TAU * p))
    F['lean'] = 0.035 * math.sin(TAU * p)
    F['head'] = (-3.0 * math.sin(TAU * p), -54.0 + 1.2 * math.cos(2 * TAU * p))
    F['head_r'] = -0.04 * math.sin(TAU * p)
    F['tail_x'] = 0.75 * math.cos(TAU * p)
    F['breath'] = 0.3 * math.sin(2 * TAU * p)
    return F


def walk_front(n=8):
    return [walk_front_pose(i / n) for i in range(n)]


def approach_walk(n=24, k0=0.3):
    out = []
    walk_frames = n - 4
    for i in range(walk_frames):
        t = i / (walk_frames - 1)
        k = k0 + (1 - k0) * ease_out(t)
        F = walk_front_pose((i % 8) / 8, k)
        out.append(F)
    last = out[-1]
    rest = idle_front()[0]
    for j in range(4):
        t = ease((j + 1) / 4)
        F = blend(last, rest, t)
        F['k'] = 1.0
        out.append(F)
    return out


def fly_front_pose(p, k=1.0, gy=150.0):
    F = front_pose()
    F['k'] = k
    F['gy'] = gy + 3 * math.sin(TAU * p) * k
    f = math.cos(TAU * p)                    # +1 up, -1 down
    th = 12 + 48 * f
    F['wing_open'] = [1.0, 1.0]
    F['wing_th'] = [th, th]
    F['wing_fs'] = [0.85 + 0.15 * abs(f)] * 2
    F['feet'] = dict(r=(14.0, -4.0), l=(-14.0, -4.0), hr=(26.0, -12.0), hl=(-26.0, -12.0))
    F['head'] = (0.0, -55.0 + 1.5 * math.sin(TAU * p + 0.8))
    F['tail_x'] = 0.5 * math.sin(TAU * p * 0.5 + 0.3) + 0.3
    F['lift'] = -2.0
    F['shadow_gy'] = 188.0
    F['shadow_k'] = k * 0.8
    F['shadow'] = 0.35
    return F


def fly_front(n=8):
    return [fly_front_pose(i / n) for i in range(n)]


def approach_fly(n=26):
    out = []
    fly_n = 18
    for i in range(fly_n):
        t = i / (fly_n - 1)
        k = 0.14 + (1 - 0.14) * ease_out(t) ** 1.3
        gy = 70 + (152 - 70) * ease(t)
        F = fly_front_pose((i % 6) / 6, k, gy)
        F['shadow'] = 0.1 + 0.3 * t
        F['shadow_k'] = k * 0.8
        out.append(F)
    # landing: flare, touch down, fold wings
    land = idle_front()[0]
    flare = fly_front_pose(0.0, 1.0, 172)
    flare['wing_th'] = [62, 62]
    flare['feet'] = dict(FEET)
    flare['shadow'] = 0.7
    touch = copy.deepcopy(land)
    touch['lift'] = -6
    touch['head'] = (0.0, -48.0)
    touch['wing_open'] = [0.7, 0.7]
    touch['wing_th'] = [5, 5]
    touch['fx'] = [dict(type='dust', x=160 + dx, y=186 - abs(dx) * 0.05, r=5 + abs(dx) * 0.06, a=0.8)
                   for dx in (-46, -32, 32, 46)]
    seq = [blend(out[-1], flare, 0.5), flare, blend(flare, touch, 0.5), touch]
    seq[2]['gy'] = 188
    after = blend(touch, land, 0.5)
    after['fx'] = [dict(type='dust', x=160 + dx * 1.3, y=184, r=7 + abs(dx) * 0.06, a=0.45)
                   for dx in (-46, -32, 32, 46)]
    seq += [after, land]
    for F in seq:
        F['gy'] = min(F['gy'], 188)
    out += seq
    out[-4]['gy'] = 188
    return out[:n]


def head_tilt(n=16):
    base = idle_front()[0]
    out = []
    keys = [  # (head_r, pupil, brow, look_x, head_dx)
        (0.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 0.6, 0.6, 0.0, 0.0),
        (0.32, 1.0, 1.0, 0.0, 3.0),
        (0.38, 1.0, 1.0, 0.0, 4.0),
        (0.36, 1.0, 1.0, 0.0, 4.0),
        (0.0, 1.0, 0.8, 0.0, 0.0),
        (-0.34, 1.0, 1.0, 0.0, -3.5),
        (-0.4, 1.0, 1.0, 0.0, -4.0),
        (-0.38, 1.0, 1.0, 0.0, -4.0),
        (0.0, 0.5, 0.4, 0.0, 0.0),
    ]
    # spread keys over n frames with easing
    seg = (len(keys) - 1)
    for i in range(n):
        u = i / (n - 1) * seg
        a = min(int(u), seg - 1)
        t = ease(u - a)
        r, pu, br, lx, hx = [lerp_ + (b_ - lerp_) * t for lerp_, b_ in zip(keys[a], keys[a + 1])]
        F = copy.deepcopy(base)
        F['head_r'] = r
        F['pupil'] = pu
        F['brow'] = br
        F['head'] = (hx, -54.0 - 2 * pu)
        F['tail_x'] = 0.8 + 0.15 * math.sin(i)
        F['breath'] = 0.5 * math.sin(TAU * i / n)
        out.append(F)
    return out


def front_fire(windup=4, ramp=2, sustain=6, cool=4):
    S = idle_front()[0]
    back = copy.deepcopy(S)
    back['head'] = (0.0, -62.0)
    back['head_s'] = 1.02
    back['lean'] = 0.0
    back['lift'] = 2
    back['breath'] = 1.4
    back['brow'] = -1.0
    back['jaw'] = 0.15
    back['belly_glow'] = 1.0
    back['fire_glow'] = 1.0
    back['wing_open'] = [0.35, 0.35]
    back['wing_th'] = [55, 55]
    blast = copy.deepcopy(S)
    blast['head'] = (0.0, -46.0)
    blast['head_s'] = 1.3
    blast['brow'] = -1.0
    blast['jaw'] = 1.0
    blast['belly_glow'] = 0.5
    blast['breath'] = -0.6
    blast['wing_open'] = [0.6, 0.6]
    blast['wing_th'] = [40, 40]
    out = []
    for i in range(windup):
        out.append(blend(S, back, ease((i + 1) / windup)))
    for i in range(ramp):
        t = (i + 1) / (ramp + 1)
        F = blend(back, blast, ease(min(1, t * 1.6)))
        F['fire'] = 0.3 + 0.7 * t
        F['fire_t'] = (i - ramp) / sustain
        out.append(F)
    for i in range(sustain):
        p = i / sustain
        F = copy.deepcopy(blast)
        F['fire'] = 1.0
        F['fire_t'] = p
        F['head'] = (0.6 * math.sin(TAU * p), -46.0 + 0.8 * math.sin(TAU * p))
        out.append(F)
    for i in range(cool):
        t = (i + 1) / (cool + 1)
        F = blend(blast, S, ease(t))
        F['fire'] = 0.0
        F['jaw'] = max(0.0, 1.0 - t * 1.3)
        F['fire_glow'] = 1 - t
        F['brow'] = -1 + t
        F['smoke'] = [(4.6 * sg + sg * 3 * t + sg * kk * 2, 4 - 12 * t - kk * 6, 2.5 + 3 * t + kk, 0.5 * (1 - t * 0.6))
                      for sg in (1, -1) for kk in range(3)]
        out.append(F)
    return out, (windup + ramp, windup + ramp + sustain - 1)


def boop(n=16):
    S = idle_front()[0]
    near = copy.deepcopy(S)
    near['head'] = (0.0, -26.0)
    near['head_s'] = 2.3
    near['pupil'] = 1.0
    near['brow'] = 0.8
    near['lift'] = -4
    press = copy.deepcopy(near)
    press['head_s'] = 2.45
    press['squish'] = 1.0
    press['eye_happy'] = 1.0
    press['brow'] = 0.4
    out = []
    plan = [(S, near, 5), (near, near, 2), (near, press, 2), (press, press, 3), (press, S, 4)]
    hearts_from = None
    for a, b, m in plan:
        for j in range(m):
            t = ease((j + 1) / m) if a is not b else 0
            F = blend(a, b, t)
            out.append(F)
    # little look-around before the boop and hearts after
    out[5]['look'] = (0.8, 0)
    out[6]['look'] = (-0.8, 0)
    for idx in range(9, 16):
        u = (idx - 9) / 7
        out[idx]['fx'] = [dict(type='heart', x=160 + dx + 5 * math.sin(idx * 1.3 + dx), y=110 - u * 70 + dy,
                               s=1.5 + u * 0.9, a=min(1, 2.2 - u * 2.2)) for dx, dy in ((-92, 0), (95, 12), (-112, 34), (110, 40))]
        if idx < 12:
            out[idx]['tongue'] = 0.0
    for idx in (12, 13):
        out[idx]['eye_happy'] = 1.0
    out[14]['eye_happy'] = 0.0
    return out[:n]
