# Axolotl desktop pet

A chibi pink axolotl with feathery coral gills and a lilac flower clip, plus 38 animated reactions. Its six gill fronds carry most of the emotion: they flutter, fan out, droop, spike, blush and curl.

Every clip ships in two formats with the same motion:

- `lottie/<clip>.json`: Lottie / bodymovin 5.7 (`"v": "5.7.4"`), one shape layer, no masks, images, gradients or text.
- `svg/<clip>.svg`: a self-contained SVG animated with SMIL. No scripts, CSS animation or external references.

Both formats use a 512 × 512 canvas at 30 fps with a fully transparent background. Every move uses an ease-in-out cubic bezier (0.42, 0, 0.58, 1). The letters and symbols (z, ?, !) are vector paths, not font text.

## What's in the folder

| Path | What it is |
|---|---|
| `lottie/` | 38 Lottie JSON files |
| `svg/` | 38 SMIL SVG files |
| `index.json` | Clip list: name, category, base pose, start/end pose, frames, fps, seconds, loop, description, file paths |
| `preview.html` | Plays every clip on a checkerboard. Switch the grid between SVG and Lottie, filter by category, click a clip to compare both formats side by side with a frame scrubber. Works offline (lottie-web is inlined). |
| `cursor_follow.html` | The same page opened on the cursor-follow demo. |
| `rig/rig_sheet.svg` / `.png` | The rig parts, face variants and props on one sheet. |
| `verification/` | Format match report (`report.md`, `report.json`) and one comparison sheet per clip (SVG on the top row, Lottie on the bottom). |
| `source/` | The Python generator that builds both formats from one rig, plus the render/diff harness. |

## The rig

The character is a tree of separately animatable parts. The same names appear as `id`s in the SVGs and as group names (`nm`) in the Lottie files.

```
root
├─ shadow                         ground shadow, stays at y≈470
├─ fxBack                         effects behind the character
├─ world (256,470, 80% scale)
│  ├─ move                        whole-body translation (hops, floating, falls)
│  │  └─ pose                     whole-body roll, pivots at the body's centre
│  │     └─ squash                squash & stretch, pivots at the feet
│  │        └─ char
│  │           ├─ tail1 → tail2 → tail3   3-segment tail with fin (drawn in 3 passes: outline, fin, body)
│  │           ├─ legBL, legBR    back legs
│  │           ├─ body            bean body + cream-pink belly
│  │           ├─ legFL, legFR    front legs
│  │           └─ headRig
│  │              ├─ gL1-3, gR1-3 six gill fronds, each pivoting at its base
│  │              ├─ head, flower
│  │              ├─ face
│  │              │  ├─ cheekL, cheekR
│  │              │  ├─ eyes → eyeL, eyeR  variants: _open _sleepy _happy _squint _wink _heart
│  │              │  ├─ brows             brow_worried, brow_angry
│  │              │  └─ mouth             mouth_smile _open _o _yawn _frown _wobbly _tight
│  │              └─ noseBubble
│  └─ fxWorld                     effects in front of the character
└─ fxFront
```

Each part's transform is `translate(p) rotate(r) scale(s)` for the pose, then `translate(dp) rotate(dr) scale(ds)` for the animation layered on top. Both pivot at the part's anchor. The left-side gills and legs sit inside mirrored containers, so one rotation value moves both sides symmetrically.

Props: a water bubble in three sizes (S/M/L), a pink shrimp snack, hearts, sparkles, dizzy stars, z, !, ?, an anger mark, a teardrop, a thought cloud, a yellow "!" badge and a pop burst.

### Base poses

- **sit**: feet on the ground at y≈470, character at 80% scale with headroom above. Most clips start and end here.
- **swim**: floating sideways in the middle of the canvas, legs tucked, tail trailing, gills streaming back. The ground shadow stays at y≈470, smaller and lighter.
- **lie**: asleep on its belly with its chin on its front paws. Base of `sleep_loop`.
- **drag**: dangling from under the arms. Base of `int_dragged`.
- **hidden**: below the bottom edge of the canvas. Base of `fun_peek`.

## Clips

| Clip | Category | Pose | Frames | Seconds | Plays | What happens |
|---|---|---|---|---|---|---|
| `idle_breathe` | idle | sit | 120 | 4.0 | loop | Default loop: slow breathing, rippling gills, one blink, lazy tail swish. |
| `idle_gill_wiggle` | idle | sit | 75 | 2.5 | loop | All six gills fan out wide, ripple twice, then settle. |
| `idle_look_left_right` | idle | sit | 120 | 4.0 | loop | Glances left, holds, then right; head and gills follow. A tiny "?" pops up. |
| `idle_yawn` | idle | sit | 105 | 3.5 | loop | Big yawn with squinting eyes; a small bubble floats out of its mouth. |
| `idle_stretch` | idle | sit | 90 | 3.0 | loop | Front legs stretch out, back arches, tail goes straight up, gills spread. |
| `idle_blow_bubbles` | idle | sit | 150 | 5.0 | loop | Blows three bubbles, then boops the last one with its snout and it pops. |
| `swim_idle` | swim | swim | 90 | 3.0 | loop | Swims in place with slow tail strokes, gills streaming back, small bubbles rising. |
| `sit_to_swim` | swim | sit → swim | 45 | 1.5 | once | Wiggles, floats up off the ground and rolls into the swimming pose. |
| `swim_to_sit` | swim | swim → sit | 45 | 1.5 | once | Drifts down and lands sitting with a soft squash. |
| `sleep_fall_asleep` | sleep | sit → lie | 75 | 2.5 | once | Eyes droop, lies down on its belly with its chin on its front feet, gills droop flat. |
| `sleep_loop` | sleep | lie | 120 | 4.0 | loop | Asleep on its belly: slow breathing, gills rise and fall, rising "z z z", a nose bubble. |
| `sleep_wake_up` | sleep | lie → sit | 75 | 2.5 | once | Nose bubble pops, gills spike out startled, two quick blinks, stretch, back to sitting. |
| `move_walk` | movement | sit | 40 | 1.333 | loop | Wiggly lizard walk in place, body curving in an S, gills bobbing. The app moves the window. |
| `move_hop` | movement | sit | 36 | 1.2 | loop | Crouch, jump with gills flared at the top, squash on landing. |
| `move_swim` | movement | swim | 30 | 1.0 | loop | Fast swim in place, tail kicking hard, legs tucked, a stream of bubbles behind. The app moves the window. |
| `move_fall_land` | movement | sit | 75 | 2.5 | once | Drops in from above with gills flapping, belly-flops with a big squash, dizzy stars, then sits up. |
| `int_dragged` | interaction | drag | 60 | 2.0 | loop | Held under the arms, dangling long like a noodle, tail swinging, gills swept back, surprised face. |
| `int_petted` | interaction | sit | 60 | 2.0 | loop | Happy ^ ^ eyes, gills flutter fast and blush darker pink, hearts pop up. |
| `int_poked` | interaction | sit | 45 | 1.5 | loop | Puffs up round like a ball, gills spike out, puffed cheeks, angry brows, anger mark. |
| `int_tickled` | interaction | sit | 48 | 1.6 | loop | Wriggles and laughs with eyes squeezed shut, legs kicking, gills wiggling. |
| `int_look_up` | interaction | sit | 60 | 2.0 | loop | Eyes held looking up with light breathing (cursor follow). |
| `int_look_up_right` | interaction | sit | 60 | 2.0 | loop | Eyes held looking up-right with light breathing (cursor follow). |
| `int_look_right` | interaction | sit | 60 | 2.0 | loop | Eyes held looking right with light breathing (cursor follow). |
| `int_look_down_right` | interaction | sit | 60 | 2.0 | loop | Eyes held looking down-right with light breathing (cursor follow). |
| `int_look_down` | interaction | sit | 60 | 2.0 | loop | Eyes held looking down with light breathing (cursor follow). |
| `int_look_down_left` | interaction | sit | 60 | 2.0 | loop | Eyes held looking down-left with light breathing (cursor follow). |
| `int_look_left` | interaction | sit | 60 | 2.0 | loop | Eyes held looking left with light breathing (cursor follow). |
| `int_look_up_left` | interaction | sit | 60 | 2.0 | loop | Eyes held looking up-left with light breathing (cursor follow). |
| `mood_happy` | mood | sit | 60 | 2.0 | loop | Bouncy wiggle dance with gills fanned wide and sparkles. |
| `mood_sad` | mood | sit | 120 | 4.0 | loop | Gills droop, sad brows and frown; a teardrop turns into a bubble and floats away. |
| `mood_surprised` | mood | sit | 54 | 1.8 | loop | Gills shoot straight out, big round eyes, "o" mouth, "!" mark. |
| `mood_hungry` | mood | sit | 90 | 3.0 | loop | Rubs its belly, with a thought bubble showing a little shrimp. |
| `mood_love` | mood | sit | 90 | 3.0 | loop | Heart eyes; the top gill fronds curve inward to frame a floating heart; more hearts drift up. |
| `mood_smile_wink` | mood | sit | 60 | 2.0 | loop | Big open smile with tongue, playful wink with a sparkle, excited tail wag. |
| `fun_spin` | fun | sit | 60 | 2.0 | loop | Rolls into the swim pose, spins with a ring of bubbles, then lands back sitting with a squash. |
| `fun_peek` | fun | hidden | 90 | 3.0 | loop | Rises from the bottom edge so only gills and eyes show, blinks, then sinks back with bubbles. |
| `fun_notify` | fun | sit | 60 | 2.0 | loop | Holds up a big bubble with a round yellow "!" badge inside it, happy open mouth. |
| `fun_bubble_ride` | fun | sit | 120 | 4.0 | loop | Hops into a big bubble, floats up, the bubble pops and it drops back to sitting with a squash. |

Looping clips are seamless: frame N equals frame 0 for every animated property. Clips that play once finish their motion at least 6 frames before the end and then hold the last pose.

## Using the clips

**Lottie (web)**

```js
const anim = lottie.loadAnimation({
  container: el, renderer: 'svg', autoplay: true,
  loop: clip.loop,                 // from index.json
  path: 'lottie/' + clip.name + '.json'
});
anim.addEventListener('complete', () => { /* once-clip finished: choose the next clip */ });
```

**SVG**: use it as `<img src="svg/idle_breathe.svg">`, `<object>` or inline. Loops repeat forever. Once-clips freeze on their last frame. To restart a clip, re-set the `src` (or call `svg.setCurrentTime(0)` when it is inline). To pause or scrub inline SVGs, use `svg.pauseAnimations()` and `svg.setCurrentTime(frame / 30)`.

### Chaining clips in an app

- The default loop is `idle_breathe`. Every sitting clip starts and ends in the same sitting pose, so you can cut between them on any loop boundary.
- To swim: `sit_to_swim`, then `swim_idle` or `move_swim`, then `swim_to_sit`.
- To sleep: `sleep_fall_asleep`, then `sleep_loop`, then `sleep_wake_up`.
- `move_fall_land` starts above the canvas, belly-flops, shows dizzy stars, then sits up. It ends in the sitting pose.
- `move_walk` and `move_swim` animate in place. Your app moves the window while they play.
- `fun_peek` starts and ends hidden below the canvas edge. Park the window at the bottom of the screen and play it.

### Cursor follow

Measure the angle from the pet's head (about 50% across and 47% down the canvas) to the pointer. Split it into 8 sectors of 45° and play `int_look_<dir>` for that sector: `right`, `down_right`, `down`, `down_left`, `left`, `up_left`, `up`, `up_right`. When the pointer is close to the head, or has not moved for a few seconds, fall back to `idle_breathe`. All eight look clips share the sitting pose and breathe in sync, so switching between them only moves the eyes and head. `cursor_follow.html` implements this, along with pet on click, poke on double-click, `int_dragged` while dragging and a hop when you let go.

## Notes

- **Loops with their own held pose.** `int_dragged`, `sleep_loop`, `swim_idle`, `move_swim` and `fun_peek` repeat continuously, so they loop around their own pose (drag, lie, swim, hidden) instead of returning to sitting every cycle. Use the transition clips to get in and out of them.
- **Phase-offset motion.** In the swim loops and the dangle, the later tail segments lag the first by a few frames, so they are already mid-swing at frame 0. The loop is still exact.
- **Effects across the loop seam.** Some effects in loops (rising bubbles, z's, sparkles) run across the loop point instead of all disappearing at frame 0. Each one is fully faded out at the moment it jumps back.
- **The fall in `move_fall_land`** uses a slow-start curve, `(0.5, 0, 0.8, 0.8)`, so the drop picks up speed before the landing squash. Every other move uses the standard ease-in-out.
- **Lottie player compatibility.** The files were verified with lottie-web 5.12.2. They use only shape layers, groups, paths, fills, strokes, transforms and hold keyframes, so other Lottie players should play them too.

## Rebuilding

```
cd source
python3 build.py ../            # writes lottie/, svg/, index.json
python3 verify.py .. ../verification "" 8   # needs Node + Playwright + lottie-web (see render.js)
```
`clips.py` holds every clip as keyframes on rig parts, `rig.py` holds the drawing and poses, and `core.py` holds the two exporters.
