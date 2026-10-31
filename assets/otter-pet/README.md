# Otter Pet – animated reaction set

A chibi sea otter desktop pet. Its signature pose is floating on its back with its favourite lavender pebble on its belly.
There are 41 clips, and every clip ships as a **Lottie JSON (bodymovin 5.7)** and a **self-contained animated SVG (SMIL)**. Both files are generated from the same keyframes, so the motion is identical.

- Canvas 512 × 512, 30 fps, fully transparent background
- Ease-in-out cubic `0.42 0 0.58 1` on every move (the same bezier in Lottie `i/o` and SMIL `keySplines`)
- Flat vector only: no gradients, masks, images, or font text. The z, !, and ? marks are drawn as vector paths.
- Outlines are 6 px at 512 px (7.5 design units inside the 80% character root)

## Contents

```
lottie/<clip>.json      bodymovin 5.7 Lottie, one per clip
svg/<clip>.svg          animated SVG (SMIL), self-contained, one per clip
index.json              clip list: name, category, base_pose, start_pose, end_pose, frames, seconds, loop
preview.html            plays every clip on a checkerboard backdrop (SVG / Lottie switch) + cursor-follow demo
vendor/lottie.min.js    lottie-web 5.12.2 (MIT), used by preview.html offline
verification/           Lottie-vs-SVG key-frame renders, diff images and verify_report.json
source/                 the generator (Node): rig, poses, clip choreography, both exporters
```

Open `preview.html` straight from the folder. It needs no server.

## Base poses

| pose | description |
|---|---|
| **float** | Lies on its back in the water strip (surface y ≈ 420), head to the left, both paws holding the pebble on its belly, feet and tail poking up on the right. |
| **sit** | Feet on the ground at y ≈ 470, character at 80% scale for headroom, pebble tucked under its right arm, water hidden, soft ground shadow. |

Looping clips start and end exactly on their start pose, so they loop seamlessly. Rotations that complete a full turn (`float_roll`, `fun_spin`, the pebble flips in `idle_juggle_pebble`) end at ±360°, which is pixel-identical to 0°.
Clips that play once (`loop: false`) hold their last pose. Chain them like this:

```
sit  ──sit_to_float──▶  float  ──float_to_sit──▶  sit
float ──sleep_fall_asleep──▶ sleep ⟲ sleep_loop ──sleep_wake_up──▶ float
(off-canvas) ──move_fall_land──▶ float
```

A few loops use a variant of a base pose as their resting frame. Their `start_pose` in `index.json` records which one:
`sleep_loop` (sleep: paws over eyes), `move_walk` (walk: on all fours), `move_swim` (swim: belly-down in the water),
`int_dragged` (dangling), `int_look_*` (eyes held in the direction), `fun_notify` (badge instead of pebble), and `fun_peek` (fully under water).

**Direction:** `move_walk` and `move_swim` face left. To travel right, mirror the clip (`scaleX(-1)`). In both clips the otter animates in place, and your app moves the window.

## Clips

| clip | category | base | frames | sec | play | what happens |
|---|---|---|---|---|---|---|
| `float_idle` | floating | float | 120 | 4.00 | loop | Bobs on gentle waves, turns the pebble over and back, one blink, slow tail sculling. Default loop. |
| `float_crack_shell` | floating | float | 150 | 5.00 | loop | Bangs a clam on the pebble twice, it pops open, nibbles with puffed cheeks. |
| `float_roll` | floating | float | 100 | 3.33 | loop | Rolls over once through the water with small splashes, then floats again. |
| `float_wave` | floating | float | 90 | 3.00 | loop | Waves its left paw at the viewer, then winks with a sparkle. |
| `sit_to_float` | floating | sit | 80 | 2.67 | once | Hops in with a splash and pops up floating on its back. |
| `float_to_sit` | floating | float | 80 | 2.67 | once | Climbs out, shakes off water droplets, sits with the pebble under its arm. |
| `idle_breathe` | idle | sit | 120 | 4.00 | loop | Slow squash-and-stretch breathing, one blink, whisker twitch, lazy tail swish. |
| `idle_look_left_right` | idle | sit | 120 | 4.00 | loop | Eyes glance left, hold, then right; whiskers follow; a small "?" at the end. |
| `idle_yawn` | idle | sit | 90 | 3.00 | loop | Big yawn with squinted eyes, head tilts back. |
| `idle_stretch` | idle | sit | 96 | 3.20 | loop | Sets the pebble down, arms up overhead, body stretches taller, tail straight up. |
| `idle_groom` | idle | sit | 96 | 3.20 | loop | Scrubs its face and whiskers fast with both paws. |
| `idle_juggle_pebble` | idle | sit | 150 | 5.00 | loop | Tosses the pebble paw to paw four times, then hugs it. |
| `sleep_fall_asleep` | sleep | float | 100 | 3.33 | once | While floating, yawns and covers its eyes with both paws; pebble rests on its belly. |
| `sleep_loop` | sleep | float | 120 | 4.00 | loop | Asleep with paws over eyes, gentle bob, slow breathing, rising z z z, snot bubble. |
| `sleep_wake_up` | sleep | float | 110 | 3.67 | once | Startled blink and "!", drops the pebble, catches it just before it sinks, hugs it in relief. |
| `move_walk` | movement | sit | 30 | 1.00 | loop | Bouncy hump-backed lope in place, tail trailing (faces left). |
| `move_hop` | movement | sit | 48 | 1.60 | loop | Crouch, jump with arms up (pebble in paw), squash on landing. |
| `move_swim` | movement | float | 40 | 1.33 | loop | Belly-down swim, head up, tail kicking, ripples behind (faces left). |
| `move_fall_land` | movement | float | 96 | 3.20 | once | Drops in from above flailing, big splash ring, comes up floating with dizzy stars. |
| `int_dragged` | interaction | sit | 60 | 2.00 | loop | Held under the arms, body dangling like a noodle, clutching the pebble, surprised. |
| `int_petted` | interaction | sit | 100 | 3.33 | loop | Closes its eyes and leans into the hand, reaches a paw up, hearts pop up. |
| `int_poked` | interaction | sit | 84 | 2.80 | loop | Hides the pebble behind its back, puffed cheeks, angry brows, anger mark. |
| `int_tickled` | interaction | sit | 60 | 2.00 | loop | Wriggles and laughs, eyes squeezed shut, feet kicking. |
| `int_look_up` | interaction | sit | 60 | 2.00 | loop | Eyes held up with light breathing (sitting, for cursor following). |
| `int_look_up_right` | interaction | sit | 60 | 2.00 | loop | Eyes held up-right with light breathing (sitting, for cursor following). |
| `int_look_right` | interaction | sit | 60 | 2.00 | loop | Eyes held right with light breathing (sitting, for cursor following). |
| `int_look_down_right` | interaction | sit | 60 | 2.00 | loop | Eyes held down-right with light breathing (sitting, for cursor following). |
| `int_look_down` | interaction | sit | 60 | 2.00 | loop | Eyes held down with light breathing (sitting, for cursor following). |
| `int_look_down_left` | interaction | sit | 60 | 2.00 | loop | Eyes held down-left with light breathing (sitting, for cursor following). |
| `int_look_left` | interaction | sit | 60 | 2.00 | loop | Eyes held left with light breathing (sitting, for cursor following). |
| `int_look_up_left` | interaction | sit | 60 | 2.00 | loop | Eyes held up-left with light breathing (sitting, for cursor following). |
| `mood_happy` | moods | sit | 64 | 2.13 | loop | Claps its paws and bounces, sparkles. |
| `mood_sad` | moods | sit | 96 | 3.20 | loop | Droopy whiskers and ears, holds the pebble close, sad brows, teardrop. |
| `mood_surprised` | moods | sit | 64 | 2.13 | loop | Jumps, whiskers spring out, big round eyes, "!" mark. |
| `mood_hungry` | moods | sit | 100 | 3.33 | loop | Rubs its belly, thought bubble showing a clam. |
| `mood_love` | moods | sit | 100 | 3.33 | loop | Heart eyes, hugs the pebble (tiny heart highlight), floating hearts. |
| `mood_smile_wink` | moods | sit | 64 | 2.13 | loop | Big open smile with tongue, playful wink with a sparkle. |
| `fun_spin` | fun | sit | 64 | 2.13 | loop | Cartwheel spin with the tail sweeping around, lands sitting with a squash. |
| `fun_peek` | fun | float | 96 | 3.20 | loop | Pops its head up through the water strip, whiskers twitch, sinks back with bubbles. |
| `fun_notify` | fun | float | 60 | 2.00 | loop | Floats holding a round yellow "!" badge in place of the pebble, happy open mouth. |
| `fun_pebble_gift` | fun | sit | 120 | 4.00 | loop | Shyly offers its pebble toward the viewer, blushing, then pulls it back and hugs it. |

## Layers

Each file has the same four layers. They are named identically in Lottie (`layers[].nm`) and in the SVG (`<g id="…">`), listed here from back to front:

1. `shadow`: ground shadow (visible when sitting)
2. `character`: the rig (below)
3. `water`: pastel-blue strip with two wave lines, drawn **in front of** the otter, so it sits in the water. You can hide this layer; the character is fully drawn underneath.
4. `fx`: effects used by that clip: ripple rings, splashes, droplets, bubbles, hearts, sparkles, stars, z's, "!", "?", anger mark, and thought bubble

## Rig parts (group names inside `character`)

`character` (static 80% scale about the feet) › `char` (hop, squash and stretch) › `spin` (rolls and cartwheels) ›

- `tail1 › tail2 › tail3`: tapered 3-segment chain with seamless joints
- `pebbleBack` (behind the body, used when hiding the pebble), `body › belly`, `footL`, `footR`
- `head` › `earL`, `earR`, head shape, cream face mask, `faceShift` ›
  - `muzzle`, `cheekL`, `cheekR`, `blush`, `whiskerL`, `whiskerR`
  - `eyeL` / `eyeR` › `_open` (two highlights), `_sleepy` ∪, `_happy` ^, `_squint` > <, `_wink`, `_heart`, `_dizzy`
  - `brow_worried`, `brow_angry`
  - `mouth` › `mouth_smile`, `mouth_open` (tongue), `mouth_o`, `mouth_yawn`, `mouth_frown`, `mouth_grin` (toothy)
  - `nose`, `tear`, `snot`
- `pawL` › `clam › clamTop` (the clam shell is held in the left mitten), `pawR` › `pebbleHeld`
- `pebble › pebbleY › pebbleRot › pebbleBody › pebbleHeart`, `badge`

Variants switch with hold keyframes on opacity (Lottie `h:1`, SMIL `calcMode="discrete"`).

## Using the files

- **Lottie:** `lottie.loadAnimation({ renderer: 'svg', loop: clip.loop, animationData })`. Works with lottie-web, lottie-ios/android, and dotLottie players.
- **SVG:** use it as `<img src="svg/float_idle.svg">` or inline it. The animation starts at document time 0. To restart a clip that plays once, reload the image or call `svg.setCurrentTime(0)` on inline SVG. SMIL runs in Chromium/Electron, WebKit, and Gecko webviews. Static SVG libraries that ignore SMIL show frame 0 only.
- **Cursor following:** take the angle from the otter's face (about x 50%, y 43% of the canvas) to the cursor and snap it to 8 sectors (right, down_right, down, down_left, left, up_left, up, up_right). Then play `int_look_<dir>`. The preview page has a working version.

## Verification

Key frames (0%, 20%, 40%, 60%, 80%, 100% of each clip) were rendered in headless Chromium for both formats: lottie-web 5.12.2 for the Lottie files and native SMIL seeking for the SVG files. The results were pixel-diffed with pixelmatch (threshold 0.1, anti-aliasing ignored).

- 41 clips × 6 frames = 246 frame pairs compared
- 21 clips matched with 0 differing pixels on every checked frame
- Worst frame anywhere: `fun_spin` f25, 495 px (0.757% of drawn pixels)

The remaining differences are sub-pixel edge shifts on fast motion. See `verification/compare_*.png` and `verification/verify_report.json`.

## Regenerating

```
cd source && npm i lottie-web@5.12.2 pngjs pixelmatch@5 playwright
node build.js                 # writes dist/otter-pet/{lottie,svg,index.json}
node tools/verify.js out/     # renders & diffs both formats
```
Choreography lives in `src/clips.js`, poses in `src/poses.js`, and part drawing in `src/rig.js`.
