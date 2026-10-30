# Baby Dragon desktop-pet sprite set

Your chibi baby dragon (from `interactive_cute_baby_dragon.html`), rigged and animated as 33 clips.
Every clip comes in two formats with identical motion:

- `lottie/<clip>.json`: Lottie (bodymovin 5.7)
- `svg/<clip>.svg`: self-contained animated SVG (SMIL), no scripts or external files

All clips are 512 × 512, 30 fps, transparent background, flat fills and strokes only (no gradients, masks or images).

## Files
```
lottie/            one Lottie JSON per clip
svg/               one animated SVG per clip
index.json         name, category, frames, seconds, loop (+ file paths; markers for full_loop)
preview.html       plays every clip on a checkerboard; switch Lottie / SVG (works offline)
cursor_demo.html   the dragon follows your pointer, can be petted, poked and dragged (works offline)
match_report.json  key-frame comparison of the two formats (see "Checks")
source/            the Python rig + clip definitions that generate everything
```

## Placement
- The feet sit on the same ground line as your cat: **y ≈ 470**. The dragon is scaled to leave about 170 px of headroom above the head for jumps and effects.
- Effects (hearts, sparkles, z's, smoke, "!", bubbles) stay inside the canvas.
- Two clips leave the canvas on purpose: `move_fall_land` starts above the top edge, and `fun_peek` starts and ends hidden past the right edge.

## Neutral pose and loops
Every clip starts and ends in the same sitting pose, with these exceptions:
- `sleep_fall_asleep` ends in the curled-up sleeping pose, `sleep_loop` holds it, and `sleep_wake_up` starts from it.
- `move_fall_land` starts above the canvas, because it drops in.
- `fun_peek` starts and ends hidden, because it peeks in from the right edge.
- `int_look_*` keep the gaze held from the first frame to the last, so switching directions while following the cursor never snaps the eyes back to centre. The body pose at the ends is neutral.

Clips marked as loops end exactly where they begin. In the SVGs, looping clips use `repeatCount="indefinite"`. One-shot clips play once and hold their last frame (`fill="freeze"`); reload the SVG to replay it.
In Lottie, every move uses ease-in-out bezier keyframes (`o`/`i` = 0.42,0 / 0.58,1). The SVGs use the same curves as `keySplines`.

## full_loop markers
`full_loop` is idle_breathe → sleep_fall_asleep → sleep_loop → sleep_wake_up → mood_smile_wink. The Lottie file has one marker per clip:

| marker | start frame | frames |
|---|---|---|
| `idle_breathe` | 0 | 90 |
| `sleep_fall_asleep` | 90 | 90 |
| `sleep_loop` | 180 | 120 |
| `sleep_wake_up` | 300 | 96 |
| `mood_smile_wink` | 396 | 60 |

With lottie-web, play one part with `anim.playSegments([start, start + frames], true)`.

## Clips
| clip | category | frames | seconds | loop |
|---|---|---|---|---|
| `idle_breathe` | idle | 90 | 3.00 | yes |
| `idle_ear_twitch` | idle | 48 | 1.60 | no |
| `idle_look_left_right` | idle | 90 | 3.00 | no |
| `idle_yawn` | idle | 78 | 2.60 | no |
| `idle_stretch` | idle | 84 | 2.80 | no |
| `idle_groom` | idle | 96 | 3.20 | no |
| `sleep_fall_asleep` | sleep | 90 | 3.00 | no |
| `sleep_loop` | sleep | 120 | 4.00 | yes |
| `sleep_wake_up` | sleep | 96 | 3.20 | no |
| `move_walk` | movement | 30 | 1.00 | yes |
| `move_hop` | movement | 36 | 1.20 | yes |
| `move_fall_land` | movement | 72 | 2.40 | no |
| `int_dragged` | interaction | 60 | 2.00 | yes |
| `int_petted` | interaction | 72 | 2.40 | yes |
| `int_poked` | interaction | 60 | 2.00 | no |
| `int_look_up` | interaction | 60 | 2.00 | yes |
| `int_look_up_right` | interaction | 60 | 2.00 | yes |
| `int_look_right` | interaction | 60 | 2.00 | yes |
| `int_look_down_right` | interaction | 60 | 2.00 | yes |
| `int_look_down` | interaction | 60 | 2.00 | yes |
| `int_look_down_left` | interaction | 60 | 2.00 | yes |
| `int_look_left` | interaction | 60 | 2.00 | yes |
| `int_look_up_left` | interaction | 60 | 2.00 | yes |
| `mood_happy` | mood | 48 | 1.60 | no |
| `mood_sad` | mood | 96 | 3.20 | no |
| `mood_surprised` | mood | 60 | 2.00 | no |
| `mood_hungry` | mood | 96 | 3.20 | no |
| `mood_love` | mood | 84 | 2.80 | no |
| `mood_smile_wink` | mood | 60 | 2.00 | no |
| `fun_spin` | fun | 54 | 1.80 | no |
| `fun_peek` | fun | 96 | 3.20 | no |
| `fun_notify` | fun | 84 | 2.80 | no |
| `full_loop` | sequence | 456 | 15.20 | yes |

## Rig (layer names)
Each moving part is its own layer, so you can recolour or extend it:
`bone_*` null layers carry the motion: stage, grab, root, body, head, hornL/R, wingL/R, eyeL/R, lidL/R, cheekL/R, mouth, armL/R, legL/R, tail_b, tailF_b and shadow_b.
The shape layers are:
- **Body:** `body`, `head`, `hornL`, `hornR`, `wingL`, `wingR`, `armL`, `armR` (front paws), `legL`, `legR` (hind feet), `tail`, `tail_front` (tail wrapped around for sleeping), `cheekL`, `cheekR`, `nose`, `flame` (the belly flame marking), `shadow`.
- **Eyes:** `eye_open_L/R`, `eye_closed_L/R` (sleepy ∪), `eye_happy_L/R` (^), `eye_squint_L/R` (> <), `eye_wink_L/R`, `eye_heart_L/R`, plus the half-closing eyelids `lid_L/R`.
- **Brows:** `brow_sad_L/R`, `brow_angry_L/R`.
- **Mouths:** `mouth_smile` (default), `mouth_open` (with tongue), `mouth_o`, `mouth_yawn` (with tiny fangs), `mouth_frown`, `mouth_puff`.
- **Effects:** one layer each, named per clip (e.g. `heart1`, `z2`, `anger`, `badge`).

Colours are the dragon's own: outline #2B0E63, body #FF3355, cream #FFE0AC, flame #FF8521 / #FFDE3D, blush #FF8521 at 40%.
The outline is about 6 px on the 512 canvas. Effects use a soft pastel palette.

## Checks
I rendered 7 key frames of every clip in both formats in the same browser: lottie-web for the Lottie files, native SMIL for the SVGs. I then compared them pixel by pixel.
The median difference is 0.014% of pixels, and the worst frame differs by under 1% (1-px outline anti-aliasing during fast spins and jumps); per-frame numbers are in `match_report.json`.
The Lottie files also render the same in rlottie, which many Linux apps use. rlottie returns premultiplied ARGB, which Cairo expects.

## Regenerating
`source/` holds the generator. `python3 export_all.py out` rebuilds `lottie/`, `svg/` and `index.json` from `rig.py` (parts) and `clips.py` (keyframes).
`python3 build_pages.py out` rebuilds the two HTML pages (it needs lottie-web 5.12.2 in `node_modules`).
