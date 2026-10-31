# Chibi Cat Reactions

34 reactions for a desktop-pet cat. Every clip ships twice, with identical motion:

- `lottie/<name>.json`: Lottie (bodymovin 5.7), 512×512, 30 fps, transparent, flat fills and strokes only (no gradients, masks or images).
- `svg/<name>.svg`: standalone animated SVG (SMIL), 512×512, transparent. Works in `<img>`, CSS backgrounds and inline.

`index.json` lists every clip with its category, frame count, length and whether it loops.

## Clips

| Category | Clip | Plays |
|---|---|---|
| Idle | idle_breathe (default), idle_ear_twitch, idle_look_left_right, idle_yawn, idle_stretch, idle_groom | loop |
| Sleep | sleep_fall_asleep | once, holds the loaf pose |
| Sleep | sleep_loop | loop |
| Sleep | sleep_wake_up | once, ends in the sitting pose |
| Movement | move_walk (in place), move_hop | loop |
| Movement | move_fall_land | once |
| Interaction | int_dragged, int_petted, int_poked | loop |
| Interaction | int_look_up, _up_right, _right, _down_right, _down, _down_left, _left, _up_left | loop |
| Moods | mood_happy, mood_sad, mood_surprised, mood_hungry, mood_love, mood_smile_wink, mood_angry (hisses: fangs, ears pinned, tail puffed and lashing) | loop |
| Fun | fun_spin, fun_peek, fun_notify | loop |
| Sequence | full_loop (idle → fall asleep → sleep → wake → smile), with Lottie markers | loop |

Every clip starts and ends in the same sitting pose, except the sleep clips, so you can cut between clips at any loop boundary. Chain sleep as `sleep_fall_asleep` → `sleep_loop` (repeat) → `sleep_wake_up` → any idle clip.

## Notes

- **Cursor follow:** take the angle from the cat's centre (about 50% across, 52% down the canvas) to the pointer, round it to the nearest 45°, and show the matching `int_look_*` clip. Within a small radius of the centre, show `idle_breathe`.
- **Walk:** the cat steps in place, so move the window while `move_walk` plays. Flip it horizontally (`transform: scaleX(-1)`) to walk the other way.
- **Peek:** the cat peeks in from the right edge of the canvas. Mirror it to peek from the left.
- **Fall + land:** the cat drops in from above the canvas, so keep the window position fixed while it plays.
- **One-shot SVGs** (`sleep_fall_asleep`, `sleep_wake_up`, `move_fall_land`) play once and freeze on their last frame. To replay one, call `svg.setCurrentTime(0)` on the inline SVG, or re-set the `<img>` src.
- **Lottie:** play one-shot clips with `loop: false`. In `full_loop.json`, use the markers (`idle_breathe`, `sleep_fall_asleep`, `sleep_loop`, `sleep_wake_up`, `mood_smile_wink`) with `playSegments` to play a single state.

## Rebuilding

The `source/` folder holds the rig (`rig.py`), the animation keyframes (`clips.py`) and the exporter (`build.py`). Change a colour or timing there, then run `python3 build.py` to regenerate every JSON and SVG. Python 3 is the only requirement. Afterwards run `python3 scripts/prepare-pets.py` from the repo root: it copies each clip's timing onto its SVG for the desktop app (and adds the generated `throw_*` / `land_*` clips).
