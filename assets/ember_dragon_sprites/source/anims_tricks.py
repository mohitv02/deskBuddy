"""Side-view pet tricks for Ember."""
import math, copy
from anims import blend, ease, stand, wing_flap, fly_pose, FOLD_N, FOLD_F
from rig import GROUND, to_world, mouth_point

TAU = 2 * math.pi


def ground_feet(P, dx=None):
    """Standard planted feet relative to bx, with optional per-foot x offsets."""
    bx = P['bx']
    dx = dx or {}
    base = dict(bn=(bx - 15, 185), bf=(bx - 8, 184), fn=(bx + 21, 185), ff=(bx + 28, 184))
    P['feet'] = {k: (v[0] + dx.get(k, 0), v[1]) for k, v in base.items()}


# ------------------------------------------------------------------ sit
def sit_pose():
    P = stand()
    P['br'] = -0.62
    P['by'] = 162
    P['bx'] = 112
    P['head_dx'], P['head_dy'], P['head_r'] = 36, -66, 0.12
    P['neck_bend'] = 0.5
    P['tail_lift'], P['tail_droop'] = -0.55, 0.05
    bx = P['bx']
    P['feet'] = dict(bn=(bx - 2, 185), bf=(bx + 4, 184), fn=(bx + 26, 185), ff=(bx + 32, 184))
    P['foot_tilt'] = dict(bn=0, bf=0, fn=0, ff=0)
    P['wn'] = dict(FOLD_N, t1=FOLD_N['t1'] + 20, t2=FOLD_N['t2'] + 22, phi=FOLD_N['phi'] + 22)
    P['wf'] = dict(FOLD_F, t1=FOLD_F['t1'] + 20, t2=FOLD_F['t2'] + 22, phi=FOLD_F['phi'] + 22)
    return P


def sit(n=6):
    S, T = stand(), sit_pose()
    return [blend(S, T, ease(i / (n - 1))) for i in range(n)]


def sit_idle(n=10):
    out = []
    for i in range(n):
        p = i / n
        P = sit_pose()
        s = math.sin(TAU * p)
        P['breath'] = s * 0.8
        P['head_dy'] += 1.0 * s
        P['tail_amp'], P['tail_phase'] = 0.3, TAU * p
        P['head_r'] += 0.03 * math.sin(TAU * p + 1)
        out.append(P)
    return out


# ------------------------------------------------------------------ roll over / belly up
def belly_base(p=0.0):
    """Pose in *unflipped* space; xf sy=-1 turns it upside down (on its back)."""
    P = stand()
    P['by'] = 164
    P['br'] = 0.0
    P['head_dx'], P['head_dy'], P['head_r'] = 46, 8, 0.15
    P['neck_bend'] = -0.6
    P['jaw'] = 0.45
    P['tongue'] = 1.0
    P['eye_happy'] = 1.0
    P['tail_lift'], P['tail_droop'] = 0.35, -0.04
    P['clamp'] = False
    P['wn'] = dict(FOLD_N, t1=200, t2=170, phi=160, fs=0.45, arm=0.5)
    P['wf'] = dict(FOLD_F, t1=195, t2=165, phi=155, fs=0.5, arm=0.55)
    bx, by = P['bx'], P['by']
    feet = {}
    for k, hip, ph in [('bn', (-19, 5), 0.0), ('bf', (-15, 3), 0.5), ('fn', (16, 7), 0.25), ('ff', (19, 5), 0.75)]:
        hw = to_world(P, hip)
        kk = math.sin(TAU * (p + ph))
        feet[k] = (hw[0] + 6 + 4 * kk, hw[1] + 26 - 5 * max(0, kk))
    P['feet'] = feet
    P['foot_tilt'] = dict(bn=0.9, bf=0.9, fn=0.6, ff=0.6)
    P['tail_amp'], P['tail_phase'] = 0.3, TAU * p
    P['xf'] = dict(px=bx, py=by, sy=-1.0, dy=0.0)
    return P


def belly_up(n=8):
    out = []
    for i in range(n):
        P = belly_base(i / n)
        P['breath'] = 0.6 * math.sin(TAU * i / n)
        P['head_r'] = 0.15 + 0.06 * math.sin(TAU * i / n)
        out.append(P)
    return out


def roll_over():
    S = stand()
    crouch = stand()
    crouch['by'] += 9
    crouch['head_dy'] += 8
    crouch['head_r'] = 0.25
    crouch['tail_lift'] = 0.2
    B = belly_base(0.0)
    plan = [  # (blend t towards belly pose, sy, world y of body centre)
        (0.0, 1.0, 150), (0.0, 1.0, 159), (0.35, 0.62, 166), (0.5, 0.32, 170),
        (0.6, -0.36, 170), (0.8, -0.75, 166), (1.0, -1.0, 164), (1.0, -1.0, 164),
    ]
    out = []
    for i, (t, sy, cy) in enumerate(plan):
        base = crouch if i > 0 else S
        P = blend(base, B, ease(t))
        P['clamp'] = t < 0.3
        if t >= 0.5:
            P['tongue'] = B['tongue']
            P['eye_happy'] = 1.0
        P['xf'] = dict(px=P['bx'], py=P['by'], sy=sy, dy=cy - P['by'])
        P['shadow_k'] = 1.0
        if 2 <= i <= 5:
            P['fx'] = [dict(type='dust', x=P['bx'] + dx, y=184, r=4 + i, a=0.7) for dx in (-40, -10, 30)]
        out.append(P)
    out[-1]['jaw'] = 0.45
    return out


# ------------------------------------------------------------------ pounce
def pounce():
    S = stand()
    low = stand()
    low['by'] += 10
    low['br'] = 0.14
    low['head_dx'], low['head_dy'], low['head_r'] = 50, -16, 0.08
    low['neck_bend'] = -0.6
    low['pupil'] = 1.0
    low['tail_lift'], low['tail_droop'] = 0.55, 0.12
    ground_feet(low, dict(fn=6, ff=6, bn=-4, bf=-4))
    leap = stand()
    leap['by'] -= 22
    leap['br'] = -0.12
    leap['head_dx'], leap['head_dy'], leap['head_r'] = 56, -26, 0.0
    leap['jaw'] = 0.55
    leap['pupil'] = 1.0
    leap['tail_lift'], leap['tail_droop'] = 0.1, 0.02
    bx, by = leap['bx'], leap['by']
    leap['feet'] = dict(bn=(bx - 44, by + 22), bf=(bx - 38, by + 20), fn=(bx + 46, by + 14), ff=(bx + 52, by + 12))
    leap['foot_tilt'] = dict(bn=1.6, bf=1.6, fn=-0.4, ff=-0.4)
    leap['wn'] = wing_flap(0.3)
    leap['wf'] = wing_flap(0.2, far=True)
    leap['shadow'] = 0.55
    land = stand()
    land['by'] += 8
    land['br'] = 0.12
    land['head_dx'], land['head_dy'], land['head_r'] = 52, -12, 0.15
    land['jaw'] = 0.3
    ground_feet(land, dict(fn=10, ff=10, bn=-8, bf=-8))
    out = [S, blend(S, low, 0.6), low]
    for i in range(4):          # butt wiggle
        P = copy.deepcopy(low)
        w = math.sin(TAU * i / 4)
        P['br'] = 0.14 + 0.04 * w
        P['tail_amp'], P['tail_phase'] = 0.2, TAU * i / 4
        P['by'] = low['by'] - 1.5 * abs(w)
        out.append(P)
    out += [blend(low, leap, 0.55), leap, blend(leap, land, 0.5), land]
    out[-1]['fx'] = [dict(type='dust', x=land['bx'] + dx, y=184, r=5 + abs(dx) * 0.05, a=0.7)
                     for dx in (-34, 30, 44)]
    tail = blend(land, S, 0.5)
    tail['fx'] = [dict(type='dust', x=land['bx'] + dx * 1.2, y=182, r=7 + abs(dx) * 0.05, a=0.4)
                  for dx in (-34, 30, 44)]
    out += [tail, S]
    return out


# ------------------------------------------------------------------ play bow
def play_bow(n=8):
    out = []
    for i in range(n):
        p = i / n
        P = stand()
        P['br'] = 0.3
        P['by'] = 155
        P['bx'] = 114
        P['head_dx'], P['head_dy'], P['head_r'] = 50, -10 + 1.5 * math.sin(TAU * p * 2), -0.15
        P['neck_bend'] = -0.4
        P['jaw'] = 0.35
        P['tongue'] = 0.8
        P['eye_happy'] = 1.0 if i % 4 == 0 else 0.0
        P['pupil'] = 1.0
        P['brow'] = 1.0
        P['tail_lift'], P['tail_droop'] = 0.7, 0.1
        P['tail_amp'], P['tail_phase'] = 0.2, TAU * p * 2
        bx = P['bx']
        P['feet'] = dict(bn=(bx - 22, 185), bf=(bx - 16, 184), fn=(bx + 42, 185), ff=(bx + 48, 184))
        P['foot_tilt'] = dict(bn=0, bf=0, fn=0.2, ff=0.2)
        P['by'] += 1.2 * math.sin(TAU * p * 2)
        P['wn'] = dict(FOLD_N, t1=FOLD_N['t1'] - 10)
        out.append(P)
    return out


# ------------------------------------------------------------------ shake off
def shake_off(n=12):
    out = []
    for i in range(n):
        t = i / (n - 1)
        P = stand()
        amp = math.sin(math.pi * t) ** 0.7
        w = math.sin(i * 2.2)
        P['head_dx'] += 6 * w * amp
        P['head_dy'] += 2 * math.cos(i * 2.2) * amp
        P['head_r'] = 0.25 * w * amp
        P['br'] = 0.05 * -w * amp
        P['eye'] = 0.0 if 0.15 < t < 0.85 else 1.0
        P['tail_amp'], P['tail_phase'] = 0.45 * amp, i * 2.2
        f = 0.4 * w * amp
        P['wn'] = blend(FOLD_N, wing_flap(f), 0.6 * amp)
        P['wf'] = blend(FOLD_F, wing_flap(f, far=True), 0.6 * amp)
        drops = []
        if 0.1 < t < 0.95:
            for k in range(10):
                ang = -math.pi * (0.1 + 0.8 * ((k * 0.37 + i * 0.21) % 1.0))
                d = 40 + 30 * ((k * 0.53 + i * 0.17) % 1.0)
                cx, cy = P['bx'] + 10, P['by'] - 10
                drops.append(dict(type='drop', x=cx + math.cos(ang) * d * 1.5, y=cy + math.sin(ang) * d * 0.9,
                                  r=1.6 + (k % 3) * 0.5, ang=ang, a=amp))
        P['fx'] = drops
        out.append(P)
    return out


# ------------------------------------------------------------------ happy hop
def happy_hop(n=8):
    out = []
    for i in range(n):
        p = i / n
        P = stand()
        h = max(0.0, math.sin(TAU * p)) * 30
        squash = max(0.0, -math.sin(TAU * p)) * 4
        P['by'] = 150 - h + squash
        P['head_dy'] += -3 * math.sin(TAU * p) + squash
        P['head_r'] = -0.1 * math.sin(TAU * p)
        P['jaw'] = 0.45
        P['tongue'] = 0.7
        P['eye_happy'] = 1.0
        P['tail_lift'] = 0.5 + 0.2 * math.sin(TAU * p)
        P['tail_amp'], P['tail_phase'] = 0.3, TAU * p * 2
        f = math.cos(TAU * p * 2) * 0.6
        P['wn'] = wing_flap(0.5 + 0.4 * f)
        P['wf'] = wing_flap(0.45 + 0.4 * f, far=True)
        for w in (P['wn'], P['wf']):
            w['fs'] *= 0.65
            w['arm'] = 0.7
        bx = P['bx']
        lift = h * 0.75
        P['feet'] = dict(bn=(bx - 15, 185 - lift), bf=(bx - 8, 184 - lift),
                         fn=(bx + 21, 185 - lift * 0.9), ff=(bx + 28, 184 - lift * 0.9))
        tilt = 0.5 * h / 30
        P['foot_tilt'] = dict(bn=tilt, bf=tilt, fn=tilt, ff=tilt)
        P['shadow_k'] = 1 - h / 70
        out.append(P)
    return out


# ------------------------------------------------------------------ stretch & yawn
def stretch_yawn():
    S = stand()
    bow = stand()
    bow['br'] = 0.3
    bow['by'] = 157
    bow['head_dx'], bow['head_dy'], bow['head_r'] = 56, -8, 0.0
    bow['neck_bend'] = -0.8
    bow['eye'] = 0.0
    bow['tail_lift'], bow['tail_droop'] = 0.6, 0.12
    bx = bow['bx']
    bow['feet'] = dict(bn=(bx - 18, 185), bf=(bx - 12, 184), fn=(bx + 50, 185), ff=(bx + 56, 184))
    bow['foot_tilt'] = dict(bn=0, bf=0, fn=0.1, ff=0.1)
    bow['wn'] = wing_flap(0.6)
    bow['wf'] = wing_flap(0.5, far=True)
    yawn = stand()
    yawn['head_dx'], yawn['head_dy'], yawn['head_r'] = 44, -42, -0.45
    yawn['jaw'] = 1.35
    yawn['eye'] = 0.0
    yawn['breath'] = 1.0
    yawn['neck_bend'] = 0.4
    yawn['wn'] = wing_flap(0.85)
    yawn['wf'] = wing_flap(0.8, far=True)
    for w in (yawn['wn'], yawn['wf']):
        w['fs'] *= 0.9
    out = []
    for t in (0.35, 0.7, 1.0, 1.0):
        out.append(blend(S, bow, ease(t)))
    for t in (0.4, 0.75, 1.0, 1.0, 1.0):
        out.append(blend(bow, yawn, ease(t)))
    out[-2]['jaw'] = 1.25
    out[-1]['jaw'] = 1.35
    for t in (0.35, 0.7, 1.0):
        P = blend(yawn, S, ease(t))
        out.append(P)
    out[-3]['eye'] = 0.0
    out[-2]['eye'] = 0.4
    # sleepy smack: head shake
    P = copy.deepcopy(S)
    P['head_r'] = 0.12
    out.insert(len(out) - 1, P)
    return out


# ------------------------------------------------------------------ sniff
def sniff(n=12):
    out = []
    for i in range(n):
        p = i / n
        P = stand()
        P['head_dx'] = 58 + 4 * math.sin(TAU * p)
        P['head_dy'] = 0 + 2 * math.sin(TAU * p * 3)
        P['head_r'] = 0.38
        P['neck_bend'] = -1.0
        P['br'] = 0.08
        P['by'] = 152
        P['pupil'] = 0.6
        P['tail_lift'], P['tail_droop'] = 0.55, 0.15
        P['tail_amp'], P['tail_phase'] = 0.25, TAU * p
        ground_feet(P, dict(fn=3, ff=3))
        puffs = []
        for k in range(2):
            u = ((p * 3) + k / 2) % 1.0
            puffs.append((38 + u * 6, -1 - u * 6 + 8 * u, 1.2 + 2.2 * u, 0.5 * (1 - u)))
        P['smoke'] = puffs
        P['fx'] = [dict(type='dust', x=P['bx'] + 74 + 8 * math.sin(TAU * p + k), y=185, r=2 + k, a=0.4)
                   for k in range(2)]
        out.append(P)
    return out


# ------------------------------------------------------------------ barrel roll (in flight)
def barrel_roll(n=12):
    out = []
    for i in range(n):
        t = i / n
        P = fly_pose(0.0)
        P['wn'] = wing_flap(0.15 + 0.1 * math.sin(TAU * t))
        P['wf'] = wing_flap(0.2 + 0.1 * math.sin(TAU * t), far=True)
        sy = math.cos(TAU * t)
        if abs(sy) < 0.12:
            sy = 0.12 if sy >= 0 else -0.12
        P['xf'] = dict(px=P['bx'], py=P['by'], sy=sy, rot=-0.15 * math.sin(TAU * t), dy=-6 * math.sin(math.pi * t))
        P['clamp'] = False
        P['tail_amp'] = 0.25
        if 1 <= i <= n - 2:
            P['fx'] = [dict(type='swoosh', x=P['bx'] - 10, y=P['by'] - 6, r=46 + 6 * k, a0=math.pi * (0.55 + 0.15 * k),
                            a1=math.pi * (1.45 - 0.1 * k), a=0.8 - 0.25 * k, w=2.0 - 0.5 * k) for k in range(3)]
        out.append(P)
    return out


# ------------------------------------------------------------------ fireball
def fireball():
    S = stand()
    back = stand()
    back['head_dx'], back['head_dy'], back['head_r'] = 38, -46, -0.35
    back['jaw'] = 0.2
    back['belly_glow'] = 1.0
    back['fire_glow'] = 1.0
    back['breath'] = 1.2
    back['bx'] -= 3
    spit = stand()
    spit['head_dx'], spit['head_dy'], spit['head_r'] = 56, -30, 0.05
    spit['jaw'] = 1.0
    spit['bx'] += 3
    spit['fire_glow'] = 0.6
    recoil = stand()
    recoil['head_dx'], recoil['head_dy'], recoil['head_r'] = 46, -34, -0.08
    recoil['jaw'] = 0.5
    recoil['bx'] -= 2
    out = [blend(S, back, 0.5), back, back, spit, recoil]
    out[2] = copy.deepcopy(back)
    out[2]['fx'] = [dict(type='spark', x=back['bx'] + back['head_dx'] + 34, y=back['by'] + back['head_dy'] - 2 - k * 4,
                         r=1.2, a=0.8) for k in range(3)]
    m, _ = mouth_point(spit)
    xs = [m[0] + 14, m[0] + 46, m[0] + 84, m[0] + 126, m[0] + 170]
    frames = [spit, recoil, blend(recoil, S, 0.4), blend(recoil, S, 0.75), S]
    out = out[:3]
    for j, (P, x) in enumerate(zip(frames, xs)):
        P = copy.deepcopy(P)
        P['fx'] = [dict(type='fireball', x=x, y=m[1] - 2 - j * 2, r=8 + min(j, 2), t=j / 5, a=1.0)]
        if j > 0:
            P['smoke'] = [(35 + j * 2, -2 - j * 3, 1.5 + j * 0.6, 0.45 * (1 - j / 6))]
        out.append(P)
    return out
