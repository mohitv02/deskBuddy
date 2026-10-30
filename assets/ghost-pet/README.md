# Ghost pet: animated reactions

A chibi floating ghost for a desktop pet, with 37 animated clips. Every clip comes in two formats with identical motion:

- `lottie/<clip>.json`: Lottie / bodymovin 5.7 (`"v": "5.7.0"`)
- `svg/<clip>.svg`: self-contained animated SVG (SMIL, no scripts, no external refs)

All clips are 512 × 512 at 30 fps with a fully transparent background.

## Files

| Path | What it is |
|---|---|
| `lottie/` | 37 Lottie JSON files |
| `svg/` | 37 SMIL SVG files |
| `index.json` | `fps`, `width`, `height`, and `clips[]` with `name`, `category`, `frames`, `seconds`, `loop`, `description` |
| `preview.html` | Plays every clip on a checkerboard, with an SVG / Lottie toggle and light / dark backdrops. Works offline from this folder. |
| `cursor-demo.html` | Cursor-follow demo: the ghost looks at the cursor, glides after it, can be petted, poked and dragged, and falls asleep when left alone |
| `clips.js` | Every clip bundled for the two HTML pages, so they work from `file://` |
| `vendor/lottie.min.js` | lottie-web 5.12.2 (MIT), used by the pages |
| `verification/` | Render check of both formats (see below) |
| `source/` | The Python generator (`python3 build.py out` rebuilds every clip in both formats) |

## Character and rig

The character is flat vector kawaii: no gradients, masks or images. It has a marshmallow-white dome body, a pale lavender underside and bow, soft pink cheeks and a deep purple-grey outline. The outline is 7.5 units at 80% scale, which renders at 6 px.

The rig parts are named groups. You'll find them as Lottie group `nm` values and as SVG `class` names:

- `bob` > `move` > `squash`: the root chain. `bob` carries the float bob, `move` holds the position, lean and 80% scale, and `squash` does squash and stretch.
- `tail` > `wispL`, `wispM`, `wispR`: three wisp segments. Each one ripples by path morph, with the tops pinned so the joins stay clean.
- `body`: fill plus an open outline.
- `face` > `cheekL/R`, `gaze` > `eyeL/R`, `mouth`, `brows`, `snot`, `tear`
- Eye variants: `open`, `sleepy` ∪, `happy` ^, `squint` > <, `wink`, `heart`, `round` (startled), `dizzy` (spiral), `halflid` (smug)
- Mouth variants: `smile`, `open` (with tongue), `o`, `yawn`, `frown`, `wobble` (scared, morphs), `boo`, `pout`, `smirk`
- Brows: `worried`, `angry`
- `bow`, `wrap` (the tail curled in front: blanket and face-cover poses), `anger`, `armL`, `armR` (floating mittens)
- Props: `lantern` (flat yellow `flame`, held in `armR`), and a toasted marshmallow on a stick (in the hunger thought bubble)
- `shadow`: a soft oval at y = 470. It shrinks automatically as the ghost floats higher and grows when it sinks.

Letters and symbols (z, ?, !, BOO, music notes) are vector strokes, not font text.

### Base pose

The body centre sits at (256, 291) at 80% scale. The middle tail tip hovers at about y = 427, roughly 40 px above the shadow at y = 470. The head top is at about y = 139, which leaves headroom for effects.

## Clip behaviour

- Every move uses ease-in-out, cubic-bezier(0.42, 0, 0.58, 1). Oscillations are cut exactly at the loop point, so loops have no hitch. The one exception is the dizzy stars in `move_fall_land` and `fun_spin`, which orbit at constant speed.
- Clips marked `loop: false` (`sleep_fall_asleep`, `sleep_wake_up`, `move_fall_land`) play once and hold their last frame. The SVG uses `fill="freeze"`. For Lottie, play them with `loop: false`.
- Looping clips start and end on the same frame, and a check confirmed every seam is seamless. Most of them return to the base float. A few clips are held states, so they keep their state across the seam instead:
  - `sleep_loop` floats low and wrapped up. It starts exactly where `sleep_fall_asleep` ends and ends where `sleep_wake_up` starts.
  - `int_dragged` stays stretched while held.
  - `int_look_*` keep the eyes held in their direction.
  - `move_walk` keeps leaning forward.
  - `fun_peek` starts and ends invisible at the right edge.
- The eight `int_look_*` clips share an identical 60-frame bob. When you switch direction, keep the current frame number and the bob carries on without a jump. `cursor-demo.html` does this.

### Integration notes

- **Walking:** `move_walk` faces right. Mirror it horizontally for leftward travel. The app moves the window.
- **Dragging:** the grab point for `int_dragged` is the middle tail tip at canvas (264, 427). Place the window so the cursor sits there.
- **Peeking:** `fun_peek` is drawn with the ghost centred on the canvas's right edge (x ≈ 506). Dock the window against a screen edge.
- **Sleeping:** chain `sleep_fall_asleep` → `sleep_loop` → `sleep_wake_up` → `idle_breathe`.

## Clips

| Category | Clips |
|---|---|
| Idle | idle_breathe (default), idle_look_left_right, idle_yawn, idle_stretch, idle_fade_blink, idle_lazy_drift |
| Sleep | sleep_fall_asleep (once), sleep_loop, sleep_wake_up (once) |
| Movement | move_walk, move_hop, move_phase, move_fall_land (once) |
| Interaction | int_dragged, int_petted, int_poked, int_tickled, int_look_up / up_right / right / down_right / down / down_left / left / up_left |
| Moods | mood_happy, mood_sad, mood_surprised, mood_scared, mood_hungry, mood_love, mood_smile_wink |
| Fun | fun_boo, fun_spin, fun_peek, fun_notify, fun_lantern_glow |

`index.json` lists the frames and seconds for each clip.

## Verification

Both formats are written from one shared scene model: the same keyframes, the same transform order (translate · rotate · scale · −anchor) and the same bezier easing. Then they were rendered and compared:

- **Key frames:** for each clip, 6 frames (0, 20%, 40%, 60%, 80%, last) were rendered twice. The SVG was rendered by Chromium's SMIL engine via `setCurrentTime`. The Lottie was rendered by lottie-web's SVG renderer via `goToAndStop`.
- **Result:** 222 frame pairs. The worst frame had 0.05% of pixels differing by more than 64/255, which is anti-aliasing along fast-moving edges. The largest mean difference was 0.22/255.
- **Loop seams:** every looping SVG was also compared at t = 0 and t = end, and all 34 are seamless.
- **Base pose:** frame 0 of every clip matches frame 0 of `idle_breathe`, apart from the held-state clips listed above, `sleep_wake_up` (which starts asleep) and `move_fall_land` (which starts above the canvas). The sleep chain and the ends of the play-once clips join frame-exact.

The details are in `verification/verification.json`, and `verification/verification_sheet.png` shows SVG | Lottie | diff side by side.

## Notes on opacity

Opacity fades (fade_blink, phase, poked, sad, peek, sleep glow) use layer opacity on the whole ghost layer. In lottie-web's SVG renderer and in the SVG, that fades the ghost as one image. Face-part swaps use hold keyframes (0 / 100) on groups.
