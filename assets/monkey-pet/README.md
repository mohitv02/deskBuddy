# Chibi Monkey — desktop pet animation set

43 animated reactions for a kawaii monkey desktop pet. Every clip ships twice, with identical motion:

* `lottie/<clip>.json` — Lottie / bodymovin **5.7** (shape layers + null-layer rig, no images, masks or gradients)
* `svg/<clip>.svg` — self-contained animated SVG using **SMIL** (`animateTransform` / `animate`), no CSS or JS

All clips are **512 × 512**, **30 fps**, on a **fully transparent** background.

## What's in the zip

| Path | What it is |
|---|---|
| `lottie/` | 43 Lottie JSON files |
| `svg/` | 43 SMIL SVG files |
| `index.json` | Clip list: name, category, base pose, frames, seconds, loop, description, file paths |
| `preview.html` | Plays every clip on a checkerboard backdrop; switch between the SVG and Lottie versions |
| `cursor-demo.html` | Hanging pet whose eyes follow your pointer; click to wave, idle to fall asleep, hop down / climb up |
| `clips_data.js` | All clip data bundled for the two pages, so they work when opened straight from disk |

Open `preview.html` or `cursor-demo.html` directly in a browser. The SVG mode works offline; the Lottie mode loads `lottie-web` 5.12.2 from cdnjs.

## Base poses

* **Hanging** (signature / default): upside down from a short branch at the top of the canvas, tail curled round it, head near the middle of the canvas (centre ≈ y 300). The branch with its two leaves is drawn in every clip that hangs from it.
* **Sitting**: feet on the ground at y ≈ 470, character at 80% scale so there is headroom for effects.

Looping clips start and end exactly in their base pose (checked by the generator), so any loop can follow any other loop with the same base pose. `hang_to_sit` and `sit_to_hang` bridge the two poses. `sleep_loop` uses an asleep variant of the hanging pose (arms wrapped round itself); enter it with `sleep_fall_asleep` and leave with `sleep_wake_up`. `int_dragged` and `fun_peek` hang without the branch (from the cursor and from off the top edge).

Every move is eased (cubic-bezier 0.42, 0, 0.58, 1). Pendulum swings split each extreme-to-extreme swing at its centre into an ease-in half and an ease-out half, which together make one smooth ease-in-out swing with no stop in the middle.

## Cursor following

The eight `int_look_*` clips hold the eyes (and a slight face turn) in one direction while doing exactly what `hang_idle` does: same 120 frames, swing, blink and breathing. Switch between them and `hang_idle` and keep the current time, and only the eyes move. `cursor-demo.html` shows this: it picks the direction from the angle between the pointer and the head (canvas point 256, 300) and swaps clips with `svg.setCurrentTime()` set to the current time. With Lottie, use `goToAndPlay(currentFrame, true)`.

## The rig

The monkey keeps the original colours: fur `#8b5a2b`, face, hands and feet `#f2c894`, the round ears, the tuft on top of the head and the banana. The redesign adds an oversized head (≈ 55% of the height), big shiny eyes with two highlights, a peach heart-shaped face patch, nose dots, rosy cheeks, pink inner ears, a bean body, short limbs with mitten hands, and a curly tail. Outlines are dark brown `#4a2b18` at 6 px in the sitting pose.

The transform hierarchy (Lottie null layers; nested groups in the SVG):

```
pivot (swing point: the branch, or the ground when sitting)
└─ char (placement, scale, squash and stretch, anchored at the feet)
   └─ roll (flip / cartwheel about the body centre)
      ├─ legL, legR
      └─ body
         ├─ tail1 ─ tail2 ─ tail3   (3 segments, curl wraps the branch)
         ├─ armL, armR             (mitten hands)
         └─ head
            ├─ earL, earR
            └─ face
               ├─ eyes ─ eyeL, eyeR   open · sleepy ∪ · happy ^ · squint > < · heart · swirl (wink = one eye happy)
               ├─ mouth              smile · open + tongue · o · yawn · frown · toothy grin · gritted teeth · wavy
               ├─ brows              angry · sad · puzzled · raised
               └─ cheekL, cheekR
```

Expression variants are separate layers switched with hold keyframes. A second copy of the tail is drawn in front of the body for poses where he hugs it (`mood_sad`).

## Clips

| Clip | Category | Base pose | Frames | Seconds | Plays | What happens |
|---|---|---|---|---|---|---|
| `hang_idle` | hanging | hanging | 120 | 4.0 | loop | Default loop: hangs by its tail, gentle pendulum swing, dangling arms, floppy ears, blink. |
| `hang_swing_big` | hanging | hanging | 60 | 2.0 | loop | Big happy swings with a giggle. |
| `hang_wave` | hanging | hanging | 90 | 3.0 | loop | Waves one hand at the viewer, then winks. |
| `hang_eat_banana` | hanging | hanging | 120 | 4.0 | loop | Peels and nibbles a banana while hanging, cheeks puffing as it chews. |
| `hang_to_sit` | hanging | hanging | 48 | 1.6 | once | Plays once: flips down off the branch and lands sitting with a squash. |
| `sit_to_hang` | hanging | sitting | 54 | 1.8 | once | Plays once: jumps up, tail catches the branch, swings into hang_idle. |
| `idle_breathe` | idle | sitting | 90 | 3.0 | loop | Slow squash-and-stretch breathing, blink, tail curl swish. |
| `idle_scratch_head` | idle | sitting | 96 | 3.2 | loop | Scratches its head with a puzzled face and a small "?". |
| `idle_look_left_right` | idle | sitting | 96 | 3.2 | loop | Glances left, then right. |
| `idle_yawn` | idle | sitting | 96 | 3.2 | loop | Big yawn with squinting eyes. |
| `idle_stretch` | idle | sitting | 96 | 3.2 | loop | Arms up overhead, tail straight up. |
| `idle_groom` | idle | sitting | 120 | 4.0 | loop | Picks at its fur, finds something, shrugs. |
| `sleep_fall_asleep` | sleep | hanging | 96 | 3.2 | once | Plays once: nods off while hanging and wraps its arms around itself. |
| `sleep_loop` | sleep | hanging | 120 | 4.0 | loop | Sleeps hanging: slow breathing, gentle sway, rising z z z, snot bubble. |
| `sleep_wake_up` | sleep | hanging | 66 | 2.2 | once | Plays once: bubble pops, startled blink, nearly slips, catches itself, shakes its head. |
| `move_walk` | movement | sitting | 40 | 1.333 | loop | Knuckle-waddle in place, bobbing side to side (the app moves the window). |
| `move_hop` | movement | sitting | 40 | 1.333 | loop | Excited jump with arms up. |
| `move_swing_across` | movement | hanging | 96 | 3.2 | loop | Swings along the branch to the right with arms and tail, then loops back into place. |
| `move_fall_land` | movement | sitting | 60 | 2.0 | once | Plays once: drops in from above flailing, lands on its bottom with a squash, dizzy stars. |
| `int_dragged` | interaction | hanging | 90 | 3.0 | loop | Held by the tail: dangling and spinning slowly, surprised face, arms flailing. |
| `int_petted` | interaction | sitting | 90 | 3.0 | loop | Happy ^ ^ eyes, leans into the hand, hearts pop up. |
| `int_poked` | interaction | sitting | 96 | 3.2 | loop | Puffed cheeks, crossed arms, annoyed brows, tail flicking, anger mark. |
| `int_tickled` | interaction | sitting | 60 | 2.0 | loop | Wriggles and laughs, eyes squeezed shut, legs kicking. |
| `int_look_up` | interaction | hanging | 120 | 4.0 | loop | Eyes held looking up (cursor following); same timing as hang_idle so clips can be swapped frame-synced. |
| `int_look_up_right` | interaction | hanging | 120 | 4.0 | loop | Eyes held looking up-right (cursor following); same timing as hang_idle so clips can be swapped frame-synced. |
| `int_look_right` | interaction | hanging | 120 | 4.0 | loop | Eyes held looking right (cursor following); same timing as hang_idle so clips can be swapped frame-synced. |
| `int_look_down_right` | interaction | hanging | 120 | 4.0 | loop | Eyes held looking down-right (cursor following); same timing as hang_idle so clips can be swapped frame-synced. |
| `int_look_down` | interaction | hanging | 120 | 4.0 | loop | Eyes held looking down (cursor following); same timing as hang_idle so clips can be swapped frame-synced. |
| `int_look_down_left` | interaction | hanging | 120 | 4.0 | loop | Eyes held looking down-left (cursor following); same timing as hang_idle so clips can be swapped frame-synced. |
| `int_look_left` | interaction | hanging | 120 | 4.0 | loop | Eyes held looking left (cursor following); same timing as hang_idle so clips can be swapped frame-synced. |
| `int_look_up_left` | interaction | hanging | 120 | 4.0 | loop | Eyes held looking up-left (cursor following); same timing as hang_idle so clips can be swapped frame-synced. |
| `mood_happy` | moods | sitting | 60 | 2.0 | loop | Claps its hands and bounces, sparkles. |
| `mood_sad` | moods | sitting | 120 | 4.0 | loop | Droopy ears and tail, teardrop, hugs its tail. |
| `mood_surprised` | moods | sitting | 60 | 2.0 | loop | Jumps, ears up, big round eyes, "!" mark. |
| `mood_hungry` | moods | sitting | 120 | 4.0 | loop | Rubs its belly, thought bubble with a banana bunch. |
| `mood_love` | moods | sitting | 90 | 3.0 | loop | Heart eyes, holds a heart, floating hearts. |
| `mood_angry` | moods | sitting | 60 | 2.0 | loop | Stomps and bares a toothy pout, with steam puffs. |
| `mood_laugh` | moods | sitting | 60 | 2.0 | loop | Holds its belly and laughs, tears of joy. |
| `mood_confused` | moods | sitting | 90 | 3.0 | loop | Head tilt, swirly eyes, "?" marks. |
| `fun_spin` | fun | sitting | 48 | 1.6 | loop | Cartwheel spin. |
| `fun_peek` | fun | hanging | 120 | 4.0 | loop | Hangs down from the top edge, peeks in upside down, then pulls back up. |
| `fun_notify` | fun | hanging | 60 | 2.0 | loop | Hangs and waves a banana like a flag under a round yellow "!" badge. |
| `fun_banana_juggle` | fun | sitting | 96 | 3.2 | loop | Juggles three bananas, then catches them. |

## How the two formats were checked

Both formats are generated from one keyframe definition per clip. Before packaging, 7 key frames of every clip were rendered in Chromium: the SVG paused and seeked with `setCurrentTime()`, and the Lottie with lottie-web 5.12.2 `goToAndStop(frame, true)`. The images were then compared pixel by pixel. 300 of 301 frames had fewer than 0.05% of pixels differing (most were identical). The one exception lands exactly on frame 82 of `idle_stretch`, where an expression switches; the two players resolve that boundary frame differently, and frames 81 and 83 match.

## Using the files

* **Lottie**: any Lottie player (lottie-web, lottie-ios, lottie-android, dotLottie). Set `loop` from `index.json`.
* **SVG**: as an `<img>`, `<object>` or inline element. SMIL plays automatically: loops repeat indefinitely and once-clips hold their final frame (`fill="freeze"`). Inline SVGs can be paused, seeked and synced with `pauseAnimations()`, `setCurrentTime()` and `getCurrentTime()`.
