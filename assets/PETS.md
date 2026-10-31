# Pets: what each one does

Pick a pet in **Settings → Mascot → Pet → Change ›**. The page switches pets live (the old one
shrinks away and the new one pops in). For the active pet it lists every event with its clips; each
clip chip is a ▶ button that plays it on the desktop.

Each pack's mapping is in `assets/<pack>/mascot.json`. A state can name one clip or a **list**; one
is picked at random each time (never the same twice in a row), so reactions vary. An entry can start
partway in: `move_fall_land.svg@0.45` skips the clip's own fall from the sky and plays just the
landing (used for `dropped`, since the window itself does the falling). Run
`python3 scripts/prepare-pets.py` after adding or regenerating a pack.

## Events

| Event | When | Missing clip |
|---|---|---|
| `intro` | the pet appears (app start, pet switch) | skipped |
| `idle` | the rest of the time | required |
| `hover` | while the pointer rests on the pet | idle |
| `hoverHead`, `hoverBelly`, `hoverTail`, `hoverFeet` | while the pointer rests on that part: the pack's `zones` list boxes (`{"name": "tail", "box": [x0, y0, x1, y1]}` in the idle SVG's viewBox), first match wins; moving onto another part switches after 150 ms | hover |
| `doubleClick` / `clicks` | double-click / three or more quick clicks | skipped / alarm |
| `added`, `started`, `deleted` | a todo is added, set to in progress, deleted | skipped |
| `done` / `allDone` | a todo is completed / the last open one is | hover / done |
| `overdue`, `hungry` | instead of an idle moment, half the time, while a todo is overdue / around 12:00–13:30 and 19:00–20:30 | skipped |
| `alarm`, `alarmClosed`, `snooze` | an alarm rings (loops) / is stopped / is snoozed | idle / hover / idle |
| `dragged` / `falling` / `dropped` | while you drag the pet / let go higher than where the drag started: the window drops back down (up to 200 px, with gravity) / back on the ground | hover / dragged / skipped |
| `thrown` / `thrownLanded` | flick it sideways as you let go (release speed over 1000 px/s, within 22.5° of level): the window slides that way, slowing down, with this clip looping (drawn facing right; mirrored for a throw to the left) / once it stops: drawn facing right, mirrored to face back the way it came; unless the pack sets `"throwEffect": false`, the pet's `alarmEffect` is shown from `effectOrigin` about 1.4 s in, for about 1.1 s (Ember: shake off, then fire) | falling / skipped (plain `dropped`) |
| `thrownUp` / `thrownUpLanded` | flick it up, straight or diagonally: the window flies up (up to 300 px, harder = higher) in an arc, drifting sideways on a diagonal, and falls back to where a drop would land / once down. Mirrored like `thrown` on a diagonal | falling / `dropped` |
| `thrownDown` / `thrownDownLanded` | flick it down, straight or diagonally: the window slams down (up to 240 px, never off the screen) / on impact | falling / `dropped` |
| `fallAsleep` → `sleep` → `wakeUp` | **Settings → Sleep after** (default 20 s) with no hover, click or todo change; wakes on a 1.5 s hover, a click or a todo change | no sleeping |
| `lookUp`, `lookUpRight`, … (8) | the pointer is near the pet (within 4× its size) but not on it: the eyes follow it | idle |
| `idleVariants` | one plays every 9 to 23 s while idle | — |

## Throw reactions (every pet)

Flick a pet as you let go and it reacts to the direction; each row is a random pick. The Chibi Ninja
has hand-drawn clips (in its table below). Every other pet gets 7 clips that
`scripts/make-throw-clips.py` builds from its own art (re-run by `prepare-pets.py`): one of its
clips wrapped in extra motion, with stars, dust, speed lines and a sweat drop drawn on top.

| Throw | In the air | Landing |
|---|---|---|
| ← → sideways | `throw_tumble` (rolls head over heels, faces the way it flies) + the pet's own sideways clip, if any | `land_dizzy`, `land_grumpy`, its usual drop landing; Ember instead keeps `tumble` → `thrown_fire` (turns round and breathes fire) |
| ↑ ↖ ↗ up | `throw_whee` (sways and stretches with joy, sparkles), `throw_panic` (shakes, sweat drop) | its usual drop landing, `land_splat`, `land_dizzy` |
| ↓ ↙ ↘ down | `throw_dive` (upside down, head first), `throw_panic` | `land_splat`, `land_dizzy`, `land_grumpy` |

* `land_splat`: squashed flat as a pancake with dust puffs, quivers, pops up with a boing, shakes it off.
* `land_dizzy`: crash-lands with a squash, wobbles in circles under three circling stars, shakes its head.
* `land_grumpy`: a bump on landing, then the pet's annoyed clip once.

| Pet | Tumbles as | Whee as | Panics / dives as | Grumpy as | Own sideways clip |
|---|---|---|---|---|---|
| Axolotl | `int_poked` (puffed-up ball) | `mood_happy` | `mood_surprised` | `int_poked` | `move_swim` |
| Chibi Cat | `mood_surprised` | `mood_happy` | `mood_surprised` | `int_poked` | — |
| Baby Dragon | `mood_surprised` | `mood_happy` | `mood_surprised` | `int_poked` | — |
| Ember | (keeps `tumble`) | `happy_hop` | `fall` | `shake_off` | `tumble` |
| Fox | `mood_surprised` | `mood_happy` | `mood_surprised` | `int_poked` | `move_pounce` |
| Ghost | `mood_scared` | `mood_happy` | `mood_scared` | `int_poked` | — |
| Mochi | `surprised` | `happy` | `surprised` | `poked` | `tumble` |
| Monkey | `mood_surprised` | `mood_happy` | `mood_surprised` | `mood_angry` | `fun_spin` (cartwheel) |
| Otter | `mood_surprised` | `mood_happy` | `mood_surprised` | `int_poked` | `move_swim` |
| Penguin | `mood_surprised` | `mood_happy` | `mood_surprised` | `int_poked` | `move_belly_slide` |
| Red Panda | `mood_surprised` | `mood_smile_wink` | `mood_surprised` | `mood_angry` | — |
| Classic Dragon | `fly` | `fly` | `sad` | `flame` | — |

## The pets

### Buddy (built in)
Yellow lightning bug drawn in code: blinks, wiggles its antenna, bounces; a happy hop with
sparkles when a todo is done (also for all done); shakes on alarm.


### Axolotl (`axolotl_pet`)
Sits and breathes with rippling gills; swims in place, wiggles like a lizard, belly-flops in. **Emotions:** happy dance, sad (tear turns into a bubble), surprised (gills shoot out), hungry (dreams of shrimp), love, smile-wink; puffs up like a ball when poked, laughs when tickled. Only `sit_to_swim` is unused (it ends in the swim pose).

| Event | Clips |
|---|---|
| Appears | `move_fall_land`, `swim_to_sit` |
| Idle | `idle_breathe` |
| Mouse over | `int_petted`, `mood_love` |
| Double-click | `int_tickled`, `fun_spin`, `mood_smile_wink` |
| Click spree | `int_poked` |
| Todo added | `idle_gill_wiggle`, `move_hop` |
| Todo started | `move_walk`, `move_swim` |
| Todo completed | `mood_happy`, `fun_spin`, `move_hop` |
| All todos done | `fun_bubble_ride`, `mood_love` |
| Todo deleted | `mood_surprised` |
| Worried (overdue todo) | `mood_sad` |
| Hungry (meal time) | `mood_hungry` |
| Alarm ringing | `fun_notify`, `mood_surprised` |
| Alarm stopped | `mood_smile_wink` |
| Alarm snoozed | `idle_yawn` |
| Dragged | `int_dragged` |
| Dropped | `move_fall_land` |
| Dozes off | `sleep_fall_asleep` |
| Sleeping | `sleep_loop` |
| Wakes up | `sleep_wake_up` |
| Watching you | `int_look_*` (8 directions) |
| Idle moments | `idle_gill_wiggle`, `idle_look_left_right`, `idle_stretch`, `idle_blow_bubbles`, `idle_yawn`, `fun_peek`, `swim_idle` |

### Chibi Cat (`chibi_cat_reactions`)
Squash-and-stretch breathing, waddle, hop, spin, peeks from the edge, curls into a loaf to sleep. **Emotions:** happy jump, sad, surprised, hungry (fish), love, smile-wink, angry (hisses with fangs, ears pinned, tail puffed and lashing); annoyed when poked. Knows where you touch it: head, belly or tail. Only the `full_loop` demo is unused.

| Event | Clips |
|---|---|
| Appears | `move_fall_land` |
| Idle | `idle_breathe` |
| Mouse over | `int_petted`, `mood_love` |
| Mouse on its head | `int_petted`, `mood_smile_wink`, `mood_happy` |
| Mouse on its belly | `mood_surprised`, `int_poked` |
| Mouse on its tail | `mood_angry` |
| Double-click | `mood_smile_wink`, `fun_spin` |
| Click spree | `int_poked` |
| Todo added | `idle_ear_twitch` |
| Todo started | `move_walk` |
| Todo completed | `mood_happy`, `move_hop`, `fun_spin` |
| All todos done | `mood_love` |
| Todo deleted | `mood_surprised` |
| Worried (overdue todo) | `mood_sad` |
| Hungry (meal time) | `mood_hungry` |
| Alarm ringing | `fun_notify` |
| Alarm stopped | `mood_smile_wink` |
| Alarm snoozed | `idle_yawn` |
| Dragged | `int_dragged` |
| Dropped | `move_fall_land` |
| Dozes off | `sleep_fall_asleep` |
| Sleeping | `sleep_loop` |
| Wakes up | `sleep_wake_up` |
| Watching you | `int_look_*` (8 directions) |
| Idle moments | `idle_ear_twitch`, `idle_look_left_right`, `idle_stretch`, `idle_groom`, `idle_yawn`, `fun_peek` |

### Chibi Ninja (`chibi_ninja_pet`)
Ready stance, tiptoe walk, run, flip jump, smoke-puff teleport, superhero landing, shadow clones, shuriken tricks, meditation. **Emotions (the widest range):** happy (peace sign), sad (kicks a pebble), surprised, hungry (rice ball), love (hides behind the scarf), angry (fiery aura), determined (tightens headband), embarrassed (pulls the mask up), smile-wink; dizzy (spiral eyes, stars), splatted, grumpy (-_-). Reacts to throws in every direction, picking a random flight and landing each time. **All 47 clips are used.**

| Event | Clips |
|---|---|
| Appears | `move_fall_land`, `move_teleport` |
| Idle | `idle_breathe` |
| Mouse over | `int_petted`, `mood_love`, `mood_embarrassed` |
| Double-click | `mood_smile_wink`, `fun_spin`, `move_hop` |
| Click spree | `int_poked`, `mood_angry` |
| Todo added | `mood_determined`, `idle_stretch` |
| Todo started | `move_run`, `move_walk` |
| Todo completed | `mood_happy`, `fun_spin`, `move_hop` |
| All todos done | `fun_shadow_clone`, `mood_happy` |
| Todo deleted | `move_teleport`, `fun_throw_shuriken` |
| Worried (overdue todo) | `mood_sad`, `mood_angry` |
| Hungry (meal time) | `mood_hungry` |
| Alarm ringing | `fun_notify` |
| Alarm stopped | `mood_determined`, `mood_smile_wink` |
| Alarm snoozed | `idle_yawn`, `mood_sad` |
| Dragged | `int_dragged` |
| Dropped | `move_fall_land` |
| Thrown sideways | `thrown_tumble`, `thrown_flail` |
| Lands, sideways | `land_dizzy`, `land_dust_off`, `move_fall_land`, `fun_throw_shuriken` (no overlay effect: `throwEffect` is off) |
| Thrown up | `thrown_up_whee`, `thrown_panic` |
| Lands, from up high | `move_fall_land`, `land_splat`, `land_dizzy` |
| Thrown down | `thrown_down_dive`, `thrown_panic` |
| Lands, slammed | `land_splat`, `land_dizzy`, `mood_angry` |
| Dozes off | `sleep_fall_asleep` |
| Sleeping | `sleep_loop` |
| Wakes up | `sleep_wake_up` |
| Watching you | `int_look_*` (8 directions) |
| Idle moments | `idle_look_left_right`, `idle_stretch`, `idle_twirl_shuriken`, `idle_meditate`, `idle_yawn`, `fun_shadow_clone`, `fun_throw_shuriken`, `fun_peek`, `move_walk`, `mood_surprised` |

### Baby Dragon (`dragon_pet_sprites`)
Chubby red baby dragon with the same clip set as the cat: breathing, ear twitch, grooming, walk, hop, spin, peek; happy, sad, surprised, hungry, love, smile-wink, petted, poked. Only `full_loop` is unused.

| Event | Clips |
|---|---|
| Appears | `move_fall_land` |
| Idle | `idle_breathe` |
| Mouse over | `int_petted`, `mood_love` |
| Double-click | `mood_smile_wink`, `fun_spin` |
| Click spree | `int_poked` |
| Todo added | `idle_ear_twitch` |
| Todo started | `move_walk` |
| Todo completed | `mood_happy`, `move_hop`, `fun_spin` |
| All todos done | `mood_love` |
| Todo deleted | `mood_surprised` |
| Worried (overdue todo) | `mood_sad` |
| Hungry (meal time) | `mood_hungry` |
| Alarm ringing | `fun_notify` |
| Alarm stopped | `mood_smile_wink` |
| Alarm snoozed | `idle_yawn` |
| Dragged | `int_dragged` |
| Dropped | `move_fall_land` |
| Dozes off | `sleep_fall_asleep` |
| Sleeping | `sleep_loop` |
| Wakes up | `sleep_wake_up` |
| Watching you | `int_look_*` (8 directions) |
| Idle moments | `idle_ear_twitch`, `idle_look_left_right`, `idle_stretch`, `idle_groom`, `idle_yawn`, `fun_peek` |

### Ghost (`ghost-pet`)
Never touches the ground: float bob, figure-eight drift, glide, phases out and back, balloon-bounce landing, BOO, lights its lantern. **Emotions:** happy twirl, sad (fades to 70%), surprised (puffs up), scared (hides behind its tail), hungry (marshmallow), love (turns pink), smile-wink; jelly-wobble when poked. **All 37 clips are used.**

| Event | Clips |
|---|---|
| Appears | `move_fall_land`, `move_phase` |
| Idle | `idle_breathe` |
| Mouse over | `int_petted`, `mood_love` |
| Double-click | `int_tickled`, `fun_spin`, `mood_smile_wink` |
| Click spree | `int_poked` |
| Todo added | `move_hop` |
| Todo started | `move_walk` |
| Todo completed | `mood_happy`, `move_hop`, `fun_spin` |
| All todos done | `mood_love`, `fun_lantern_glow` |
| Todo deleted | `move_phase`, `mood_surprised` |
| Worried (overdue todo) | `mood_scared`, `mood_sad` |
| Hungry (meal time) | `mood_hungry` |
| Alarm ringing | `fun_notify` |
| Alarm stopped | `mood_smile_wink` |
| Alarm snoozed | `idle_yawn` |
| Dragged | `int_dragged` |
| Dropped | `move_fall_land` |
| Dozes off | `sleep_fall_asleep` |
| Sleeping | `sleep_loop` |
| Wakes up | `sleep_wake_up` |
| Watching you | `int_look_*` (8 directions) |
| Idle moments | `idle_look_left_right`, `idle_fade_blink`, `idle_lazy_drift`, `idle_stretch`, `idle_yawn`, `fun_boo`, `fun_lantern_glow`, `fun_peek` |

### Monkey (`monkey-pet`)
Two poses: **hanging** by its tail from a branch (home pose) and **sitting**. Swings, waves, eats and juggles bananas, swings along the branch, sleeps upside down. **Emotions:** happy (claps), sad (hugs its tail), surprised, hungry, love, angry (steam), laugh (tears of joy), confused (swirly eyes). Unused: the sitting-only idles (`idle_breathe`, `idle_groom`, `idle_look_left_right`, `idle_stretch`), `int_petted` and `hang_to_sit`, so it doesn't keep jumping between poses while idle.

| Event | Clips |
|---|---|
| Appears | `sit_to_hang` |
| Idle | `hang_idle` |
| Mouse over | `hang_wave` |
| Double-click | `int_tickled`, `mood_laugh`, `hang_swing_big` |
| Click spree | `int_poked`, `mood_angry` |
| Todo added | `idle_scratch_head`, `mood_confused` |
| Todo started | `move_swing_across`, `move_walk` |
| Todo completed | `mood_happy`, `fun_spin`, `move_hop` |
| All todos done | `fun_banana_juggle`, `mood_love` |
| Todo deleted | `mood_surprised` |
| Worried (overdue todo) | `mood_sad`, `mood_confused` |
| Hungry (meal time) | `mood_hungry`, `hang_eat_banana` |
| Alarm ringing | `fun_notify` |
| Alarm stopped | `hang_swing_big` |
| Alarm snoozed | `idle_yawn` |
| Dragged | `int_dragged` |
| Dropped | `move_fall_land` |
| Dozes off | `sleep_fall_asleep` |
| Sleeping | `sleep_loop` |
| Wakes up | `sleep_wake_up` |
| Watching you | `int_look_*` (8 directions) |
| Idle moments | `hang_swing_big`, `hang_eat_banana`, `hang_wave`, `fun_peek` |

### Ember (`ember_dragon_sprites`)
Image-strip dragon (320×200 frames) with **two views**. Side view: walk, fly, take off, land, fall, pounce, barrel roll, sit, roll over, play bow, wet-dog shake, sniff, stretch-yawn, fire, fireball. **Front view (coming at you):** walks up from far away (`approach_walk`), flies in straight at you (`approach_fly`), walks towards you, hovers in front of you, tilts its head, boops its snout on your screen, breathes fire at you. `scripts/prepare-pets.py` chains strips into clips (e.g. take off → fly → barrel roll → fly → land) and lines the front view up with the side view. **All 33 animations are used.** It has no sad or worried clip, so overdue todos don't change it.

| Event | Clips |
|---|---|
| Appears | `intro_walk`, `intro_fly`, `drop_in` |
| Idle | `idle` |
| Mouse over | `head_tilt`, `play_bow` |
| Double-click | `boop`, `belly_up` |
| Click spree | `pounce`, `fireball` |
| Todo added | `front_moment` |
| Todo started | `front_walk`, `walk` |
| Todo completed | `happy_hop`, `barrel_roll` |
| All todos done | `fly_front`, `boop` |
| Todo deleted | `front_fire` |
| Hungry (meal time) | `sniff` |
| Alarm ringing | `front_fire_alarm`, `fire` |
| Alarm stopped | `shake_off` |
| Alarm snoozed | `snooze` |
| Dragged | `dragged` |
| Dropped | `drop_in` |
| Dozes off | `lie_down` |
| Sleeping | `sleep` |
| Wakes up | `wake_up` |
| Idle moments | `idle_blink`, `sniff`, `sit_idle`, `stretch_yawn`, `fireball`, `front_moment`, `fly_front`, `barrel_roll` |

### Mochi (`mochi_pet`)
Round orange kitten, drawn as one spritesheet (320×320 frames, `spritesheet.png` + `spritesheet.json`). Blinks, twitches its ears, swings its striped tail, grooms, stretches, peeks in from the edge, hops and spins. **Emotions:** happy (sparkles), sad, surprised, hungry, love. `scripts/prepare-pets.py` turns each sheet row into a clip and adds `drop_in` (fall → land), `tumble` (looping spin), `look_around` (left → right), and one still per direction from `follow_cursor` for the eyes that follow the pointer. Unused: `look_up` and `look_down` (the pointer stills do that job). The `apng/`, `gifs/` and `frames/` folders are copies of the sheet and aren't used by the app.

| Event | Clips |
|---|---|
| Appears | `drop_in`, `peek` |
| Idle | `breathe` |
| Mouse over | `petted` |
| Double-click | `hop`, `spin` |
| Click spree | `poked` |
| Todo added | `ear_twitch`, `hop` |
| Todo started | `walk` |
| Todo completed | `happy`, `hop` |
| All todos done | `love`, `spin` |
| Todo deleted | `surprised` |
| Overdue | `sad` |
| Hungry (meal time) | `hungry` |
| Alarm ringing | `notify` (with sparks) |
| Alarm stopped | `happy` |
| Alarm snoozed | `yawn` |
| Dragged / falling / dropped | `dragged` / `fall` / `land` |
| Thrown | see [Throw reactions](#throw-reactions-every-pet) (plus its own `tumble` sideways) |
| Dozes off / sleeping / wakes up | `fall_asleep` / `sleep` / `wake_up` |
| Pointer nearby | `look_n`, `look_ne`, `look_e`, `look_se`, `look_s`, `look_sw`, `look_w`, `look_nw` |
| Idle moments | `idle_blink`, `ear_twitch`, `tail_swing`, `look_around`, `yawn`, `stretch`, `groom`, `peek` |

### Penguin (`penguin-pet`)
Chibi penguin with a navy back, heart-shaped white face and red knitted scarf. Waddles, hops, flaps its flippers, preens, belly-slides, throws snowballs, catches a fish, peeks in from the edge, dangles by its scarf when dragged. **Emotions:** happy, sad, surprised, hungry, love, cold (shivers), smile-wink; laughs when tickled. Every clip is used.

| Event | Clips |
|---|---|
| Appears | `move_fall_land` |
| Idle | `idle_breathe` |
| Mouse over | `int_petted`, `mood_love` |
| Double-click | `int_tickled`, `fun_spin`, `mood_smile_wink` |
| Click spree | `int_poked` |
| Todo added | `idle_flap`, `move_hop` |
| Todo started | `move_walk` |
| Todo completed | `mood_happy`, `fun_spin`, `move_hop` |
| All todos done | `fun_fish_catch`, `mood_love` |
| Todo deleted | `mood_surprised` |
| Worried (overdue todo) | `mood_sad`, `mood_cold` |
| Hungry (meal time) | `mood_hungry` |
| Alarm ringing | `fun_notify` (with sparks) |
| Alarm stopped | `mood_smile_wink` |
| Alarm snoozed | `idle_yawn` |
| Dragged / dropped | `int_dragged` / `move_fall_land` (from the landing) |
| Thrown | see [Throw reactions](#throw-reactions-every-pet) (plus `move_belly_slide` sideways) |
| Dozes off / sleeping / wakes up | `sleep_fall_asleep` / `sleep_loop` / `sleep_wake_up` |
| Watching you | `int_look_*` (8 directions) |
| Idle moments | `idle_look_left_right`, `idle_stretch`, `idle_groom`, `idle_flap`, `idle_yawn`, `fun_peek`, `fun_snowball` |

### Classic Dragon (`dragon`)
The original four-pose pack: happy (idle), fly (hover, done, alarm stopped), flame (alarm, clicks),
sad (snooze). CSS-animated, so its clips swap instantly instead of crossfading.

### Fox (`fox-desktop-pet`)
Chibi fox. Pounces, hops, walks, catches falling leaves, peeks in from the edge, twitches its ears, tilts its head. **Emotions:** happy, sad, surprised, hungry, love, mischief, smile-wink. Mapping in `assets/fox-desktop-pet/mascot.json`.

### Otter (`otter-pet`)
Chibi sea otter that floats on its back holding a lavender pebble. Cracks clams, waves, rolls, swims, juggles the pebble. Idle and sleep happen floating. Mapping in `assets/otter-pet/mascot.json`.

### Red Panda (`red_panda_pet`)
Chibi red panda. Munches bamboo, climbs, hugs its tail, drapes over a branch to sleep. **Emotions:** happy, sad, angry, surprised, hungry, love, smile-wink. Mapping in `assets/red_panda_pet/mascot.json`.
