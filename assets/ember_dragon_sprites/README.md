# Ember: dragon desktop pet sprites

Ember is an original four-legged obsidian dragon with ember-orange belly plates, crimson wings and amber eyes.
There are 33 animations in three groups: core movement, side-view pet tricks, and front-view
"coming towards you" animations.

## Layout
- `1x/` frames are 320×200 px. `2x/` frames are 640×400 px, for HiDPI screens.
- Side-view animations come in `right/` (facing right) and `left/` (a mirrored copy).
- Front-view animations are in `front/`, with the dragon facing you.
- Each PNG is one horizontal strip with a transparent background. Frame `i` sits at `x = i * frame_width`.
- `dragon.json` covers each animation: frame count, fps, looping, the suggested `next` state,
  `folders`, `group`, and movement hints.
- `previews/` has an animated GIF of every animation.
- `overview_core.png`, `overview_tricks.png` and `overview_front.png` show every frame.

## Core (side view)
| name | frames | fps | loops | notes |
|---|---|---|---|---|
| idle / idle_blink | 12 | 8 | yes | breathing, tail sway |
| walk | 8 | 10 | yes | move window 5 px/frame (1x) |
| fly | 8 | 12 | yes | move window ~4 px/frame |
| takeoff | 8 | 12 | no | → fly |
| land | 8 | 12 | no | → idle, feet touch on frame 3 |
| fire | 15 | 12 | no | loop frames 6–11 to hold the flame |
| lie_down | 6 | 8 | no | → sleep; play reversed to wake |
| sleep | 8 | 4 | yes | smoke puffs |
| dragged | 6 | 10 | yes | keep `grab_point` under the cursor |
| fall | 4 | 10 | yes | on landing jump to land frame 3 |

## Pet tricks (side view)
| name | frames | fps | loops | notes |
|---|---|---|---|---|
| sit → sit_idle | 6 / 10 | 10 / 8 | – / yes | sits like a pup; play sit reversed to stand |
| roll_over → belly_up → roll_back | 8 / 8 / 8 | 12 / 8 / 12 | – / yes / – | rolls onto its back, paws paddling, tongue out |
| pounce | 13 | 12 | no | crouch + butt wiggle, leap on frames 7–9 (move window ~14 px/frame) |
| play_bow | 8 | 10 | yes | front down, rump up, tail wagging |
| shake_off | 12 | 14 | no | wet-dog shake with water drops |
| happy_hop | 8 | 12 | yes | excited bouncing |
| stretch_yawn | 13 | 8 | no | cat stretch then a big yawn |
| sniff | 12 | 10 | yes | nose to the ground |
| barrel_roll | 12 | 14 | no | mid-flight trick, fly → barrel_roll → fly |
| fireball | 8 | 12 | no | spits a fireball that flies off the edge |

## Coming towards you (front view)
| name | frames | fps | loops | notes |
|---|---|---|---|---|
| approach_walk | 24 | 10 | no | walks in from the distance, small to full size |
| approach_fly | 24 | 12 | no | flies in straight at you and lands |
| front_idle / front_idle_blink | 12 | 8 | yes | sitting facing you |
| front_walk | 8 | 10 | yes | walking towards you in place |
| fly_front | 8 | 12 | yes | hovering in front of you |
| head_tilt | 16 | 8 | no | curious tilt, big round pupils |
| front_fire | 16 | 12 | no | breathes fire at you; loop 6–11 to hold |
| boop | 16 | 10 | no | presses its snout on the screen, hearts |

Front-view animations are a separate view. Cut between side and front views, for example
`approach_walk → front_idle → head_tilt`, then later `idle` facing left or right.

## Anchoring
Every grounded state, side and front, keeps the feet on the same ground line (y = 188 at 1x).
For side views, the point between the feet is (124, 188) facing right and (196, 188) facing left.
For front views, it's (160, 188). Align that point with the bottom of the screen or taskbar.
Double all numbers for 2x.

## Regenerating
`source/` holds the Python + Cairo generator (`pip install pycairo pillow numpy`).
- `rig.py` draws the side view, `front.py` the front view
- `anims.py`, `anims_tricks.py` and `anims_front.py` hold the poses
- run `python3 export.py` to rebuild everything
- run `python3 preview.py <name>…` for quick contact sheets
