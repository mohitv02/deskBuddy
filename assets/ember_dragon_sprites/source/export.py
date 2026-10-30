import json, os, shutil, cairo
from PIL import Image
import rig, anims, front, anims_front as af, anims_tricks as at

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
for sub in ('1x', '2x', 'previews'):
    shutil.rmtree(os.path.join(OUT, sub), ignore_errors=True)

fire_poses, fire_loop = anims.fire()
ANIMS = [
    # name, poses, fps, loop, next, extra
    ('idle', anims.idle(), 8, True, None, {}),
    ('idle_blink', anims.idle(blink=True), 8, True, None,
     {'note': 'Same as idle with a blink; mix it in randomly.'}),
    ('walk', anims.walk(), 10, True, None,
     {'move_px_per_frame': 5, 'note': 'Move the window 5 px (1x) per frame in the facing direction so feet stay planted.'}),
    ('fly', anims.fly(), 12, True, None, {'move_px_per_frame': 4}),
    ('takeoff', anims.takeoff(), 12, False, 'fly',
     {'note': 'Start moving the window upward from frame 4.'}),
    ('land', anims.land(), 12, False, 'idle',
     {'note': 'Feet touch the ground on frame 3.'}),
    ('fire', fire_poses, 12, False, 'idle',
     {'sustain_loop': list(fire_loop),
      'note': f'Frames 0-{fire_loop[0]-1} wind-up, {fire_loop[0]}-{fire_loop[1]} flame (loop these to hold the fire), rest cool-down with smoke.'}),
    ('lie_down', anims.lie_down(), 8, False, 'sleep',
     {'note': 'Play in reverse to wake up.'}),
    ('sleep', anims.sleep(), 4, True, None, {}),
    ('dragged', anims.dragged(), 10, True, None,
     {'grab_point': [150, 74], 'note': 'Held by the scruff; keep grab_point under the mouse cursor.'}),
    ('fall', anims.fall(), 10, True, 'land',
     {'note': 'Loop while falling; on hitting the ground jump to land frame 3.'}),
]
for e in ANIMS:
    e[5]['group'] = 'core'

ro = at.roll_over()
TRICKS = [
    ('sit', at.sit(), 10, False, 'sit_idle', {'note': 'Play reversed to stand back up.'}),
    ('sit_idle', at.sit_idle(), 8, True, None, {'note': 'Sitting like a pup, tail swishing.'}),
    ('roll_over', ro, 12, False, 'belly_up', {'note': 'Rolls onto its back. Play reversed (or use roll_back) to get up.'}),
    ('belly_up', at.belly_up(), 8, True, None, {'note': 'Lying on its back, paws paddling, tongue out. Good reaction to a click.'}),
    ('roll_back', list(reversed(ro)), 12, False, 'idle', {}),
    ('pounce', at.pounce(), 12, False, 'idle',
     {'leap_frames': [7, 9], 'move_px_per_frame_during_leap': 14,
      'note': 'Crouch and butt-wiggle (0-6), leap (7-9), land (10). Move the window forward during the leap. Great for pouncing on the mouse cursor.'}),
    ('play_bow', at.play_bow(), 10, True, None, {'note': 'Front down, rump up, tail wagging: "play with me!"'}),
    ('shake_off', at.shake_off(), 14, False, 'idle', {'note': 'Shakes like a wet dog, water drops flying.'}),
    ('happy_hop', at.happy_hop(), 12, True, None, {'note': 'Excited bouncing with wing flutters.'}),
    ('stretch_yawn', at.stretch_yawn(), 8, False, 'idle', {'note': 'Cat-style stretch then a big yawn. Nice after waking up.'}),
    ('sniff', at.sniff(), 10, True, None, {'note': 'Nose to the ground, snuffling.'}),
    ('barrel_roll', at.barrel_roll(), 14, False, 'fly', {'move_px_per_frame': 5, 'note': 'Mid-flight trick; play from fly and return to fly.'}),
    ('fireball', at.fireball(), 12, False, 'idle',
     {'note': 'Spits a fireball that flies off the right edge (left edge when mirrored).'}),
]
for e in TRICKS:
    e[5]['group'] = 'tricks'

ff_poses, ff_loop = af.front_fire()
FRONT = [
    ('approach_walk', af.approach_walk(), 10, False, 'front_idle',
     {'note': 'Walks towards you from the distance, growing from small to full size, feet on the ground line.'}),
    ('approach_fly', af.approach_fly(), 12, False, 'front_idle',
     {'note': 'Flies in from far away straight at you, then lands (touchdown on frame 21).'}),
    ('front_idle', af.idle_front(), 8, True, None, {}),
    ('front_idle_blink', af.idle_front(blink=True), 8, True, None, {}),
    ('front_walk', af.walk_front(), 10, True, None,
     {'note': 'Walking towards you in place. Scale the window up slowly for a continuous approach.'}),
    ('fly_front', af.fly_front(), 12, True, None, {'note': 'Hovering in front of you, wings beating.'}),
    ('head_tilt', af.head_tilt(), 8, False, 'front_idle', {'note': 'Curious tilt to each side with big round pupils.'}),
    ('front_fire', ff_poses, 12, False, 'front_idle',
     {'sustain_loop': list(ff_loop), 'note': 'Breathes fire straight at you.'}),
    ('boop', af.boop(), 10, False, 'front_idle',
     {'note': 'Leans right up to the screen, squishes its snout on the glass, little hearts.'}),
]
for e in FRONT:
    e[5]['group'] = 'front'
    e[5]['view'] = 'front'

ANCHOR = [124, rig.GROUND]   # point between the feet on the ground line (right-facing, 1x)


def frame(P, scale, flip):
    s = front.render_front(P, scale) if 'squish' in P else rig.render(P, scale)
    if not flip:
        return s
    w, h = s.get_width(), s.get_height()
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    c = cairo.Context(out)
    c.translate(w, 0)
    c.scale(-1, 1)
    c.set_source_surface(s, 0, 0)
    c.paint()
    return out


def to_pil(surf):
    import numpy as np
    w, h = surf.get_width(), surf.get_height()
    arr = np.frombuffer(bytes(surf.get_data()), np.uint8).reshape(h, surf.get_stride() // 4, 4)[:, :w]
    b, g, r, a = [arr[..., i].astype(np.float32) for i in range(4)]
    safe = np.where(a > 0, a, 1)
    rgb = [np.clip(ch * 255 / safe, 0, 255) for ch in (r, g, b)]
    out = np.dstack(rgb + [a]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


meta = {
    'name': 'Ember (original dragon desktop pet)',
    'frame_width': rig.W, 'frame_height': rig.H,
    'scales': {'1x': 1, '2x': 2},
    'layout': 'Each PNG is one horizontal strip: frame i is at x = i * frame_width.',
    'facing': {'right': 'right/', 'left': 'left/ (mirrored)', 'front': 'front/ (faces the viewer)'},
    'ground_y': rig.GROUND,
    'anchor_right': ANCHOR,
    'anchor_left': [rig.W - ANCHOR[0], ANCHOR[1]],
    'anchor_note': 'Point between the feet on the ground. Values are 1x pixels; double them for 2x. '
                   'Mirror x for left-facing (frame_width - x).',
    'animations': {},
}

previews = {}
for name, poses, fps, loop, nxt, extra in ANIMS + TRICKS + FRONT:
    facings = ('front',) if extra.get('view') == 'front' else ('right', 'left')
    for scale_name, scale in (('1x', 1), ('2x', 2)):
        for facing in facings:
            frames = [to_pil(frame(P, scale, facing == 'left')) for P in poses]
            fw, fh = frames[0].size
            strip = Image.new('RGBA', (fw * len(frames), fh), (0, 0, 0, 0))
            for i, f in enumerate(frames):
                strip.paste(f, (i * fw, 0))
            d = os.path.join(OUT, scale_name, facing)
            os.makedirs(d, exist_ok=True)
            strip.save(os.path.join(d, f'{name}.png'), optimize=True)
            if scale_name == '1x' and facing in ('right', 'front'):
                previews[name] = (frames, fps)
    entry = {'file': f'{name}.png', 'folders': list(facings), 'frames': len(poses), 'fps': fps, 'loop': loop}
    if nxt:
        entry['next'] = nxt
    entry.update(extra)
    meta['animations'][name] = entry
    print('done', name, len(poses))

with open(os.path.join(OUT, 'dragon.json'), 'w') as f:
    json.dump(meta, f, indent=2)

# animated previews on a neutral background
pd = os.path.join(OUT, 'previews')
os.makedirs(pd, exist_ok=True)
for name, (frames, fps) in previews.items():
    bg = []
    for f in frames:
        b = Image.new('RGBA', f.size, (236, 239, 244, 255))
        b.alpha_composite(f)
        bg.append(b.convert('RGB'))
    bg[0].save(os.path.join(pd, f'{name}.gif'), save_all=True, append_images=bg[1:],
               duration=int(1000 / fps), loop=0, disposal=2)

# overview sheets: every animation as a row, one sheet per group
from PIL import ImageDraw
groups = {'core': ANIMS, 'tricks': TRICKS, 'front': FRONT}
for gname, lst in groups.items():
    rows = [(e[0], previews[e[0]][0]) for e in lst]
    cols = max(len(fr) for _, fr in rows)
    sc = 0.5
    fw, fh = int(rig.W * sc), int(rig.H * sc)
    label_w = 100
    sheet = Image.new('RGB', (label_w + cols * fw, len(rows) * fh), (236, 239, 244))
    dr = ImageDraw.Draw(sheet)
    for r, (name, frames) in enumerate(rows):
        dr.text((8, r * fh + fh // 2 - 6), name, fill=(40, 44, 52))
        for c, f in enumerate(frames):
            cell = Image.new('RGBA', f.size, (228, 232, 238, 255) if c % 2 else (236, 239, 244, 255))
            cell.alpha_composite(f)
            sheet.paste(cell.resize((fw, fh), Image.LANCZOS).convert('RGB'), (label_w + c * fw, r * fh))
    sheet.save(os.path.join(OUT, f'overview_{gname}.png'))
print('ok')
