# Chibi Ninja desktop pet: animation clips

A chibi redesign of your black-and-red ninja, built as a rig of flat vector parts and animated into **47 clips**.
Every clip comes in two formats with identical motion:

- `lottie/<clip>.json`: Lottie / bodymovin 5.7 (one shape layer, nested groups, cubic-bezier easing)
- `svg/<clip>.svg`: self-contained animated SVG (SMIL `animateTransform` / `animate`, same keyframes and easing curves)

All clips are 512 × 512, 30 fps, with a fully transparent background. The feet rest on the ground at **y ≈ 470**, centred at **x = 256**. The character is about 300 px tall, which leaves headroom for jumps and effects.

## Files

| path | what it is |
|---|---|
| `index.json` | every clip: `name`, `category`, `frames`, `seconds`, `loop`, plus `description` and file paths |
| `lottie/` | 47 Lottie JSON files |
| `svg/` | 47 animated SVG files |
| `preview.html` | plays every clip on a checkerboard, with a frame-scrub player (Lottie/SVG toggle) and a cursor-follow demo. Works offline: double-click it (uses `vendor/lottie.min.js`) |
| `verification/` | key frames of every clip rendered from both formats (top row Lottie, bottom row SVG) plus `report.json` with pixel diffs |
| `source/` | the Python generator: edit a pose or timing and rebuild both formats |

## How the clips behave

- **Loops** (`loop: true`) start and end on the same frame, so they repeat seamlessly. `idle_*` loops start and end in the neutral standing stance, so you can drop back to `idle_breathe` after any of them. `sleep_loop`, `int_dragged` and the `thrown_*` clips are *state* loops: they loop in their own pose (dozing, dangling, flying). The `land_*` one-shots start from the impact and end in the neutral stance.
- **One-shots** (`loop: false`) play once and hold their last frame. All of them except these end in the neutral stance:
  - `sleep_fall_asleep` ends in the `sleep_loop` pose.
  - `fun_peek` ends invisible, after vanishing in smoke.
  - `int_look_*` ends holding the gaze direction (meant for cursor following: play the matching one whenever the direction changes).
- Easing: ease-in-out on most moves. Cool actions (throws, landings, glances, poses) use a snappy fast-in curve, then hold, then settle.
- SVG one-shots use `fill="freeze"`; looping SVGs use `repeatCount="indefinite"`.

## Suggested pet state machine

`idle_breathe` is the default. While the cursor moves, play `int_look_<direction>` (8 directions, cursor angle from the head centre). After a few seconds without input, play a random idle variant, then go back to `idle_breathe`. After a longer pause, play `sleep_fall_asleep` → `sleep_loop`, and on any input `sleep_wake_up`.
- Click → `int_poked`
- Rub over the character → `int_petted`
- Mouse down + drag → `int_dragged` (move the window with the cursor), then on release → `move_fall_land`
- Moving the window → `move_walk` or `move_run`; teleporting → `move_teleport` or the smoke in `fun_peek`

`preview.html` implements exactly this logic in about 60 lines of JavaScript (`startDemo()`), which you can port.

## Playing them on Linux

- **Lottie**: lottie-web inside a webview (WebKitGTK, QtWebEngine, Electron/Tauri), or natively with rlottie (C++ library; Python bindings exist).
- **SVG**: SMIL animation runs in browser engines (Chromium, Firefox, WebKitGTK). Many native SVG renderers (librsvg, plain image widgets) draw only the first frame, so use a webview for the SVGs or use the Lottie files natively.
- For a transparent always-on-top window, render into a frameless window with a transparent background and click-through outside the character.

## The design

- **Identity kept from your ninja**: black/charcoal hood and gi with a crossed collar, red headband with the knot and tails on the right, red belt with a front knot and tails, bare hands, skin-tone feet in red-soled sandals, an angry-brow default expression.
- **Cute**: oversized round head (about 57% of the height), big glossy eyes in the mask window, rosy cheeks peeking above the mask, mitten hands, stubby body.
- **Cool**: a 3-segment red scarf and 2 × 2-segment headband tails that sway, stream and droop with the action; smoke puffs and speed lines as signature effects; confident snap timing.
- **Palette**: charcoal `#2f2f3d` + red `#e8303d`, outline `#17151f`, skin `#ffd3b3`, white. Flat fills only, 6 px outlines on the main shapes, no gradients, masks or images.

### Rig parts (group names in both formats)

head · hoodN · eyes (variants: `eyes_open`, `eyes_sleepy` ∪, `eyes_happy` ^, `eyes_sharp`, `eyes_squint` > <, `eyes_wink`, `eyes_heart`, `eyes_big`, `eyes_dot`, `eyes_spiral` @ @ with spinning `spiralL`/`spiralR`, `eyes_meh` - _ -) · brows (`det`, `angry`, `sad`, `worried`, `up`, `calm`) · mouth on the mask (`smile`, `grin`, `frown`, `o`, `shout`, `yawn`, `pout`, `flat`, `wavy`) · cheeks, blush · maskup (pull-up mask) · scarffront · bandN, knot, htailA1→htailA2, htailB1→htailB2 · torso (belt, beltknot, scarf wrap, rumble) · scarf1→scarf2→scarf3 · armL/armR → handL/handR (variants `fist`, `open`, `peace`, `point`) · legL, legR, lap (crossed legs for sitting) · props: shurikenHand, swordHand (wooden practice sword), shuriken · effects: smoke0-3, bigsmoke, dust0-1, spark0-2, heart0-2, star0-2 (yellow dizzy stars), z0-2, exclaim, question, sweat, tear, anger, snot, speed, speed2, swoosh, swoosh2, thought (rice ball), scroll, pebble, aura (flames).

## Clips

| name | category | frames | seconds | loops | what happens |
|---|---|---|---|---|---|
| `idle_breathe` | idle | 120 | 4.00 | yes | Default loop: calm ready stance, slow breathing, breeze, blink. |
| `idle_look_left_right` | idle | 120 | 4.00 | yes | Sharp alert glances left and right, brows narrowing. |
| `idle_yawn` | idle | 96 | 3.20 | yes | A cute yawn, quickly covered with a hand, then a cool pose again. |
| `idle_stretch` | idle | 96 | 3.20 | yes | Big overhead arm stretch, scarf flutters. |
| `idle_twirl_shuriken` | idle | 96 | 3.20 | yes | Spins a shuriken on one finger, then tucks it away. |
| `idle_meditate` | idle | 180 | 6.00 | yes | Sits cross-legged, eyes closed, floating calmly a few pixels above the ground. |
| `sleep_fall_asleep` | sleep | 150 | 5.00 | no | Nods off while standing guard, then sits and leans on its sword. |
| `sleep_loop` | sleep | 120 | 4.00 | yes | Dozing sitting up: snot bubble, rising z z z, headband tails drooping. |
| `sleep_wake_up` | sleep | 120 | 4.00 | no | Bubble pops, startled jump into a fighting pose, nothing there, embarrassed sweat drop. |
| `move_walk` | movement | 32 | 1.07 | yes | Sneaky tiptoe walk in place, leaning forward (the app moves the window). |
| `move_run` | movement | 20 | 0.67 | yes | Ninja run: arms swept back, speed lines, scarf streaming. |
| `move_hop` | movement | 50 | 1.67 | yes | High flip jump with a twist. |
| `move_teleport` | movement | 72 | 2.40 | no | Vanishes in a smoke puff and reappears in the same spot with a cool pose. |
| `move_fall_land` | movement | 60 | 2.00 | no | Drops from above and lands in a three-point superhero landing with a dust puff. |
| `int_dragged` | interaction | 30 | 1.00 | yes | Held by the scarf: legs kicking, flustered face, sweat drop. |
| `int_petted` | interaction | 110 | 3.67 | no | Tries to stay cool, then melts into happy ^ ^ eyes with blushing cheeks; hearts pop up. |
| `int_poked` | interaction | 134 | 4.47 | no | First poke "hm?", then pouty cheeks, angry brows and anger mark, finally a smoke-puff dodge. |
| `int_look_up` | interaction | 40 | 1.33 | no | Eyes and head turn up and hold (cursor following). |
| `int_look_up_right` | interaction | 40 | 1.33 | no | Eyes and head turn up-right and hold (cursor following). |
| `int_look_right` | interaction | 40 | 1.33 | no | Eyes and head turn right and hold (cursor following). |
| `int_look_down_right` | interaction | 40 | 1.33 | no | Eyes and head turn down-right and hold (cursor following). |
| `int_look_down` | interaction | 40 | 1.33 | no | Eyes and head turn down and hold (cursor following). |
| `int_look_down_left` | interaction | 40 | 1.33 | no | Eyes and head turn down-left and hold (cursor following). |
| `int_look_left` | interaction | 40 | 1.33 | no | Eyes and head turn left and hold (cursor following). |
| `int_look_up_left` | interaction | 40 | 1.33 | no | Eyes and head turn up-left and hold (cursor following). |
| `mood_happy` | mood | 80 | 2.67 | no | Little victory jump with a peace sign and sparkles. |
| `mood_sad` | mood | 130 | 4.33 | no | Slumped shoulders, droopy headband, teardrop, kicks a pebble. |
| `mood_surprised` | mood | 76 | 2.53 | no | Jumps back into a defensive pose, big eyes, "!" mark. |
| `mood_hungry` | mood | 120 | 4.00 | no | Belly rumble lines and a thought bubble with a rice ball. |
| `mood_love` | mood | 116 | 3.87 | no | Heart eyes, blushing, hides its face behind its scarf. |
| `mood_angry` | mood | 110 | 3.67 | no | Fiery aura flickers around it, determined brows, fist clenched. |
| `mood_determined` | mood | 96 | 3.20 | no | Tightens its headband, eyes glint with a sparkle, cool pose. |
| `mood_embarrassed` | mood | 116 | 3.87 | no | Blushes, pulls the mask up over its whole face, sweat drop. |
| `mood_smile_wink` | mood | 76 | 2.53 | no | Confident smile and wink, with a sparkle. |
| `fun_spin` | fun | 64 | 2.13 | no | Spinning jump kick with a swoosh trail. |
| `fun_peek` | fun | 96 | 3.20 | no | Peeks in from the right edge of the canvas, then vanishes in a smoke puff. |
| `fun_notify` | fun | 120 | 4.00 | no | Unrolls a small scroll with a "!" on it, held up toward the viewer. |
| `fun_shadow_clone` | fun | 110 | 3.67 | no | Two translucent copies pop out beside it, wave, then disappear in smoke. |
| `fun_throw_shuriken` | fun | 84 | 2.80 | no | Throws a shuriken off-screen; it boomerangs back to be caught. |
| `thrown_tumble` | thrown | 24 | 0.80 | yes | Thrown sideways: curled into a ball, rolling head over heels with spinning spiral eyes. |
| `thrown_flail` | thrown | 24 | 0.80 | yes | Thrown sideways: flies along leaning back, arms and legs flailing, big panicked eyes, sweat drop. |
| `thrown_up_whee` | thrown | 30 | 1.00 | yes | Thrown up: arms out in a V, legs swinging, happy eyes and an open-mouthed "whee!", sparkles. |
| `thrown_panic` | thrown | 24 | 0.80 | yes | Thrown up or down: flails its arms over its head, legs kicking, blank shocked eyes, "!" and a sweat drop. |
| `thrown_down_dive` | thrown | 20 | 0.67 | yes | Thrown down: head-first ninja dive, arms out in front, sharp eyes and a battle cry, speed lines above. |
| `land_dizzy` | landing | 120 | 4.00 | no | Crash-lands with a squash, wobbles around with spiral eyes and stars circling its head, then shakes it off. |
| `land_splat` | landing | 100 | 3.33 | no | Splats flat as a pancake, quivers, pops back up with a boing, shakes itself off. |
| `land_dust_off` | landing | 110 | 3.67 | no | Lands with a stumble, pats the dust off its gi with a grumpy -_- face, then turns away: "hmph". |

## Rebuilding

`source/` holds the generator (Python 3, no dependencies for building). `rig.py` defines the parts, `clips.py` the keyframes.
Run `python3 build.py ../out`, then `python3 make_preview.py ../out page.html`. `verify.py` / `review.py` need Playwright + Chromium and `lottie-web` to re-render the comparison sheets.

Third-party: `vendor/lottie.min.js` is lottie-web 5.12.2 (MIT, Airbnb); its licence is in `vendor/LICENSE.md`.
