# Red Panda Desktop Pet — animation set

A chibi red panda rig with 36 animated clips. Every clip ships twice, with identical motion:

* `lottie/<clip>.json` — Lottie / bodymovin 5.7 (shape layers only: no masks, mattes, gradients, images, text or expressions)
* `svg/<clip>.svg` — self-contained animated SVG (SMIL: `animateTransform` + discrete `animate`)

All clips: **512 × 512 px, 30 fps, fully transparent background.**

## Folder

| Path | What it is |
|---|---|
| `lottie/` | 36 Lottie JSON files |
| `svg/` | 36 animated SVG files |
| `index.json` | Clip list: name, category, base pose, frames, seconds, loop, seam pose, end pose, description, file paths |
| `preview.html` | Plays every clip on a checkerboard (Lottie / SVG toggle, category filter) plus the cursor-follow demo. Open it straight from the folder; it reads `clips.js`. |
| `clips.js` | Every clip inlined into one script so `preview.html` works from `file://` |
| `vendor/` | lottie-web 5.12.2 SVG player (MIT) used by the preview |
| `verify/` | Format-parity report and side-by-side contact sheets (SVG row over Lottie row) |
| `source/` | The Python generator that builds both formats from one keyframe model |

## Character and rig

Rusty-orange fur with a cream face mask, white brow marks, dark red-brown tear tracks, white-rimmed ears with cream fluff, dark brown limbs and belly, and a six-ring tail (rust / pale ginger). Thick 6 px dark-brown outlines, flat colours, kawaii proportions (head plus ears ≈ 57 % of the sitting height).

Every part is its own layer (named in both formats: Lottie layer `nm`/`ln`, SVG `id`):

* **Body:** `body` (body + belly), `thighL/R` and `footL/R` (hind legs), `armL/R` (front paws), `earL/R`, `head` (head, face mask, brow marks, tear tracks, outline), `cheekL/R`, `nose`, `shadow`
* **Tail:** 4 segments (`tail0`–`tail3`) carrying 6 ring puffs. The puffs exist in three depth copies so the tail can sit behind the body (`tail_b*`), wrap in front of it (`tail_f*`, for hugs) or flop over the head (`tail_t*`). Copies switch only on frames where the tail overlaps nothing, so there is no visible pop.
* **Eyes:** `open`, `closed` (sleepy ∪), `happy` (^), `squint` (> <), `wink`, `shock` (big round), `heart`, `swirl` (dizzy)
* **Mouths:** `smile`, `tongue` (open with tongue), `o`, `yawn` (with tiny fangs), `frown`, `rawr` (tiny fangs)
* **Brows:** `worried`, `angry`
* **Props:** `branch_back` / `branch_front` (short branch with two leaves across the lower middle of the canvas), `bamboo` (stalk with leaves, held), `flag` (bamboo leaf)

Variants are swapped with hold keyframes on layer opacity (0 / 100). A clip only contains the variant layers it actually shows, so files stay small.

### Base poses

* **sitting** — feet on the ground at y ≈ 470, character at 80 % scale, tail curled on the ground beside its right foot.
* **draped** — lying belly-down over the branch, front paws and hind legs dangling, tail hanging. `sleep_loop` starts and ends on it; `sleep_fall_asleep` ends on it; `sleep_wake_up` starts on it.

## Clips

| Clip | Category | Base pose | Frames | Seconds | Playback | Loop seam |
|---|---|---|---|---|---|---|
| `idle_breathe` | idle | sitting | 120 | 4.00 | loop | sitting |
| `idle_tail_hug` | idle | sitting | 150 | 5.00 | loop | sitting |
| `idle_look_left_right` | idle | sitting | 120 | 4.00 | loop | sitting |
| `idle_yawn` | idle | sitting | 110 | 3.67 | loop | sitting |
| `idle_stretch` | idle | sitting | 120 | 4.00 | loop | sitting |
| `idle_groom` | idle | sitting | 150 | 5.00 | loop | sitting |
| `sleep_fall_asleep` | sleep | sitting | 170 | 5.67 | once → draped | — |
| `sleep_loop` | sleep | draped | 150 | 5.00 | loop | draped |
| `sleep_wake_up` | sleep | draped | 150 | 5.00 | once → sitting | — |
| `move_walk` | movement | sitting | 32 | 1.07 | loop | sitting |
| `move_hop` | movement | sitting | 45 | 1.50 | loop | sitting |
| `move_climb` | movement | sitting | 40 | 1.33 | loop | climbing (held) |
| `move_fall_land` | movement | sitting | 120 | 4.00 | once → sitting | — |
| `int_dragged` | interaction | sitting | 60 | 2.00 | loop | dangling from scruff (held) |
| `int_petted` | interaction | sitting | 90 | 3.00 | loop | sitting |
| `int_poked` | interaction | sitting | 110 | 3.67 | loop | sitting |
| `int_tickled` | interaction | sitting | 120 | 4.00 | loop | sitting |
| `int_look_up` | interaction | sitting | 60 | 2.00 | loop | looking (held) |
| `int_look_up_right` | interaction | sitting | 60 | 2.00 | loop | looking (held) |
| `int_look_right` | interaction | sitting | 60 | 2.00 | loop | looking (held) |
| `int_look_down_right` | interaction | sitting | 60 | 2.00 | loop | looking (held) |
| `int_look_down` | interaction | sitting | 60 | 2.00 | loop | looking (held) |
| `int_look_down_left` | interaction | sitting | 60 | 2.00 | loop | looking (held) |
| `int_look_left` | interaction | sitting | 60 | 2.00 | loop | looking (held) |
| `int_look_up_left` | interaction | sitting | 60 | 2.00 | loop | looking (held) |
| `mood_happy` | moods | sitting | 80 | 2.67 | loop | sitting |
| `mood_sad` | moods | sitting | 120 | 4.00 | loop | sitting |
| `mood_surprised` | moods | sitting | 90 | 3.00 | loop | sitting |
| `mood_hungry` | moods | sitting | 120 | 4.00 | loop | sitting |
| `mood_love` | moods | sitting | 120 | 4.00 | loop | sitting |
| `mood_angry` | moods | sitting | 100 | 3.33 | loop | sitting |
| `mood_smile_wink` | moods | sitting | 75 | 2.50 | loop | sitting |
| `fun_spin` | fun | sitting | 130 | 4.33 | loop | sitting |
| `fun_peek` | fun | sitting | 110 | 3.67 | loop | hidden off-canvas (held) |
| `fun_notify` | fun | sitting | 90 | 3.00 | loop | sitting |
| `fun_bamboo_munch` | fun | sitting | 120 | 4.00 | loop | sitting |

**Loop seams.** Every loop's first and last frames are identical, so it repeats with no jump. Most loops start and end on their base pose, so you can switch between them at a loop boundary without a pop. Three groups are exceptions on purpose, because their job is to hold a state:

* `int_look_*` (8 clips) hold the look direction for the whole loop. Swapping between two directions moves the eyes and head a few pixels at once.
* `int_dragged` and `move_climb` hold the dangling and climbing poses.
* `fun_peek` is hidden off-canvas at the seam and peeks in mid-loop.

If you need any of these to enter and leave through the sitting pose, play a short transition first, or ask for intro/outro variants.

**Plays once.** `sleep_fall_asleep` (sitting → draped), `sleep_wake_up` (draped → sitting) and `move_fall_land` (from above → sitting) hold their last frame. In lottie-web use `loop: false`; in SVG every animation uses `fill="freeze"`.

**Effects** (hearts, sparkles, z z z, ?, !, stars, teardrop, sweat drop, steam, dust, crumbs, thought bubble, badge, falling leaf) are drawn as vector paths, with no fonts, and stay inside the canvas.

## Integrating

**Lottie.** Tested with lottie-web 5.12.2 using both the `svg` and `canvas` renderers. Example:

```js
lottie.loadAnimation({ container, renderer: 'svg', loop: clip.loop, autoplay: true, path: 'lottie/idle_breathe.json' });
```

**SVG.** Works inline or as `<img src="svg/idle_breathe.svg">`. To restart an inline clip, call `svgEl.setCurrentTime(0)`. To pause it, call `svgEl.pauseAnimations()`.

**Desktop pet hints**

* Default loop: `idle_breathe`.
* `move_walk` and `move_climb` animate in place. Move the window yourself: sideways while walking, upward while climbing.
* Sleep chain: `sleep_fall_asleep` → `sleep_loop` (repeat) → `sleep_wake_up` → back to sitting clips.
* Drag chain: `int_dragged` while held → `move_fall_land` on release.
* Cursor follow: take the angle from the pet's face (about 45 % down the canvas) to the cursor, split it into 8 sectors, and play the matching `int_look_*` clip. Fall back to `idle_breathe` when the cursor is close or still. `preview.html` has a working implementation.

## Verification

Before delivery, 306 key frames (8 per clip, plus frames around every layer swap) were rendered in headless Chromium, once from the SVG (SMIL clock set with `setCurrentTime`) and once from the Lottie file (lottie-web, `goToAndStop`). The two were then compared pixel by pixel.

* Mean absolute difference per frame: at most **0.44 / 255**
* Worst frame: **0.055 %** of pixels differ by more than 48 / 255, all on anti-aliased edges
* Spot check with the Lottie **canvas** renderer: same result (≤ 0.05 %)

`verify/report.json` has the number for every frame, and `verify/sheets/` has the side-by-side images.

## Regenerating

```
cd source && python3 build.py ../out   # writes out/lottie, out/svg, out/index.json, out/clips.js
```

`source/rig.py` holds the parts and palette, `source/poses.py` the key poses, and `source/clips.py` the choreography. Both exporters live in `source/anim.py`.
