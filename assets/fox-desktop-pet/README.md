# Fox Desktop Pet: animation pack

A chibi fox with a playful, slightly sly personality: bright orange fur, cream muzzle and chest, dark-brown socks,
a huge white-tipped tail and a forest-green bandana with a tiny leaf print.
There are **37 clips**, and each one comes in two formats that move identically:

* `lottie/<clip>.json`: Lottie, bodymovin **5.7.0** schema (one shape layer, no images, masks, gradients or expressions)
* `svg/<clip>.svg`: self-contained animated SVG using **SMIL** (no script, no external references)

Every clip is 512 × 512 at 30 fps on a fully transparent background.

## What's in the zip

```
lottie/             37 Lottie JSON files
svg/                37 animated SVG files
index.json          clip list: name, category, frames, seconds, loop, plus paths and notes
preview.html        plays every clip on a checkerboard; compares SVG and Lottie side by side
cursor.html         cursor-follow demo (look clips, petting, falling asleep when left alone)
vendor/lottie.min.js  lottie-web 5.12.2 (MIT), used by preview.html for Lottie playback
verification/       render report and key-frame sheets proving both formats match
source/             the Python generator that builds both formats from one rig
```

**Opening the pages:** `preview.html` and `cursor.html` play the SVGs straight from disk. To play the Lottie files in
the preview, serve the folder first, because browsers block `fetch` on `file://`:
`python3 -m http.server` then open http://localhost:8000/preview.html

## Conventions

* **Base pose:** sitting, feet on the ground at y ≈ 470, tail wrapped around the front paws. The character is drawn at
  80 % scale around the feet, which leaves headroom for jumps and effects.
* **Looping clips** loop seamlessly and start and end in the base pose. You can chain any of them into any other.
* **"Plays once" clips** (`loop: false`) end holding their final pose. In Lottie, play them with `loop: false`; the SVG
  versions already use `fill="freeze"`.
* **State loops** are the exception. These loop on their own pose instead of returning to sitting, because that's how an
  app uses them:
  * `sleep_loop` stays curled up. Enter with `sleep_fall_asleep` and leave with `sleep_wake_up`.
  * `int_dragged` dangles for as long as the drag lasts.
  * `int_look_*` (8 directions) hold the look direction for cursor following.
  * `move_walk` trots in place facing **left** with the tail floating behind. Mirror it with `scaleX(-1)` to walk
    right; the app moves the window.
  * `fun_peek` starts and ends hidden below the bottom edge.
* `move_fall_land` ends back in the sitting pose, so it chains straight into idle.
* Timing: ease-in-out on most moves; quick, springy keys (fast-out curves plus overshoot keyframes) on the pounce,
  ear flicks, landings and pops. SMIL limits spline handles to 0–1, so every overshoot is a real keyframe and both
  formats overshoot the same way.
* All letters and symbols (z, ?, !) are vector paths, not font text.

## Suggested state machine

```
idle_breathe (default) ── random ──> idle_ear_twitch | idle_head_tilt | idle_look_left_right | idle_yawn | idle_stretch | idle_groom
no input for a while ──> sleep_fall_asleep ─> sleep_loop ── input ──> sleep_wake_up ─> idle_breathe
pointer moves        ──> int_look_<dir>  (angle from fox to cursor in 45° sectors; see cursor.html)
drag start/end       ──> int_dragged ... then move_fall_land on drop
click / pet / poke / tickle ──> int_petted | int_poked | int_tickled
notifications        ──> fun_notify
```

## Clips

| name | category | frames | seconds | playback | note |
|---|---|---|---|---|---|
| `idle_breathe` | idle | 120 | 4.00 | loop | Default loop. |
| `idle_ear_twitch` | idle | 96 | 3.20 | loop |  |
| `idle_head_tilt` | idle | 100 | 3.33 | loop |  |
| `idle_look_left_right` | idle | 120 | 4.00 | loop |  |
| `idle_yawn` | idle | 100 | 3.33 | loop |  |
| `idle_stretch` | idle | 120 | 4.00 | loop |  |
| `idle_groom` | idle | 150 | 5.00 | loop |  |
| `sleep_fall_asleep` | sleep | 150 | 5.00 | once |  |
| `sleep_loop` | sleep | 120 | 4.00 | loop | State loop: starts and ends curled up. |
| `sleep_wake_up` | sleep | 160 | 5.33 | once |  |
| `move_walk` | movement | 32 | 1.07 | loop | State loop facing left; mirror (scaleX -1) to walk right. Tail floats behind. |
| `move_hop` | movement | 48 | 1.60 | loop |  |
| `move_pounce` | movement | 170 | 5.67 | loop |  |
| `move_fall_land` | movement | 130 | 4.33 | once | Ends back in the sitting pose so it chains into idle. |
| `int_dragged` | interaction | 60 | 2.00 | loop | State loop: held by the scruff for as long as the drag lasts. |
| `int_petted` | interaction | 100 | 3.33 | loop |  |
| `int_poked` | interaction | 84 | 2.80 | loop |  |
| `int_tickled` | interaction | 130 | 4.33 | loop |  |
| `int_look_up` | interaction | 60 | 2.00 | loop | Held pose for cursor following (loops in place). |
| `int_look_up_right` | interaction | 60 | 2.00 | loop | Held pose for cursor following (loops in place). |
| `int_look_right` | interaction | 60 | 2.00 | loop | Held pose for cursor following (loops in place). |
| `int_look_down_right` | interaction | 60 | 2.00 | loop | Held pose for cursor following (loops in place). |
| `int_look_down` | interaction | 60 | 2.00 | loop | Held pose for cursor following (loops in place). |
| `int_look_down_left` | interaction | 60 | 2.00 | loop | Held pose for cursor following (loops in place). |
| `int_look_left` | interaction | 60 | 2.00 | loop | Held pose for cursor following (loops in place). |
| `int_look_up_left` | interaction | 60 | 2.00 | loop | Held pose for cursor following (loops in place). |
| `mood_happy` | mood | 96 | 3.20 | loop |  |
| `mood_sad` | mood | 120 | 4.00 | loop |  |
| `mood_surprised` | mood | 76 | 2.53 | loop |  |
| `mood_hungry` | mood | 130 | 4.33 | loop |  |
| `mood_love` | mood | 136 | 4.53 | loop |  |
| `mood_mischief` | mood | 110 | 3.67 | loop |  |
| `mood_smile_wink` | mood | 80 | 2.67 | loop |  |
| `fun_spin` | fun | 140 | 4.67 | loop |  |
| `fun_peek` | fun | 110 | 3.67 | loop | Starts and ends hidden below the bottom edge. |
| `fun_notify` | fun | 100 | 3.33 | loop |  |
| `fun_leaf_catch` | fun | 160 | 5.33 | loop |  |

## Rig

The character is a rig of separate named groups, and the Lottie group names match the parts:
`world > shadow, swing > char > roll > [tail_back, tailH (heart tail), hindL, hindR, body (bodyfur, chest, bandana),
tail_mid, frontL, frontR, head (earL, earR, cheeks, puff, eyes > eyeL/eyeR > variants, brows > variants,
muzzle > nose + mouth variants + snownose + leafm, sweat, tear, anger, dz1-3), tail_top]`, then the effects:
`tuft, leaf, puff1-5, heart1-4, spark1-4, z1-3, qmark, emark, thought, badge`.

* **Tail:** a 4-segment chain (`tail1`–`tail4`, white tip on `tail4`). It is drawn in three z-layers (behind the body,
  between body and paws, above the head) that switch per clip, plus a heart-shaped variant for `mood_love`. Each
  layer renders an outline pass under a fill pass, so the joints merge into one seamless fluffy silhouette.
* **Eyes:** open, round (surprised), sleepy ∪, happy ^, squint > <, wink, sly half-lid, heart, dizzy spiral.
* **Mouths:** small smile, open with tongue, "o", big yawn with tiny fangs, frown, sly smirk, pout, lick, hold.
* **Brows:** curious, angry, sad. **Fur:** smooth or bristled (body and tail).
* **Props:** snow tuft (a snowbank for the pounce dive), autumn leaf, a bunch of red berries in a thought bubble.

Palette: fur `#f7913d`, cream `#fff4e4`, socks `#6e3d26`, outline `#4a2c1d` (6 px at 512), bandana `#3f7f50`,
blush `#ff9d93`, hearts `#ff6f82`, sparkles `#ffd25e`.

Only the variants and effects a clip actually uses are written into its file, so files stay lean
(SVG 17–81 KB, Lottie 46–194 KB).

## Verification

Before packaging, every clip was rendered in headless Chromium in both formats (lottie-web 5.12.2 SVG renderer vs.
native SMIL) at 10 evenly spaced frames plus every frame where a face, tail or fur variant switches, and the two
renders were diffed pixel by pixel. See `verification/report.txt` and the `keyframes_*.png` sheets (SVG on the
left, Lottie on the right).

## Regenerating

`source/` holds the generator: `model.py` (rig engine and both exporters), `fox.py` (character design),
`clips.py` (all animation), `build.py`. Run `python3 build.py <outdir>` (Python 3, no dependencies) to rebuild every
file. Change a pose or timing once and both formats update together.
