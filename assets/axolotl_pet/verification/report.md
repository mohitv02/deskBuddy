# Format match report

Each clip was rendered at 8 evenly spaced key frames in headless Chromium: the SMIL SVG (paused, `setCurrentTime`) and the Lottie JSON (lottie-web 5.12.2, SVG renderer, `goToAndStop`). The two 512x512 RGBA frames were diffed pixel by pixel.

Columns: mean absolute channel difference (0-255 scale) of the worst frame, and the most pixels in any one frame whose largest channel difference is above 40 (out of 262,144 pixels). The remaining differences are anti-aliasing along edges.

Each `<clip>.jpg` sheet shows SVG frames on the top row and Lottie frames on the bottom row.

| clip | frames checked | worst mean diff | worst pixels > 40 |
|---|---|---|---|
| idle_breathe | 0, 17, 34, 51, 68, 85, 102, 119 | 0.0208 | 34 |
| idle_gill_wiggle | 0, 11, 21, 32, 42, 53, 63, 74 | 0.0226 | 54 |
| idle_look_left_right | 0, 17, 34, 51, 68, 85, 102, 119 | 0.003 | 7 |
| idle_yawn | 0, 15, 30, 45, 59, 74, 89, 104 | 0.0257 | 51 |
| idle_stretch | 0, 13, 25, 38, 51, 64, 76, 89 | 0.0248 | 43 |
| idle_blow_bubbles | 0, 21, 43, 64, 85, 106, 128, 149 | 0.0208 | 33 |
| swim_idle | 0, 13, 25, 38, 51, 64, 76, 89 | 0.005 | 25 |
| sit_to_swim | 0, 6, 13, 19, 25, 31, 38, 44 | 0.0208 | 33 |
| swim_to_sit | 0, 6, 13, 19, 25, 31, 38, 44 | 0.0262 | 62 |
| sleep_fall_asleep | 0, 11, 21, 32, 42, 53, 63, 74 | 0.0268 | 60 |
| sleep_loop | 0, 17, 34, 51, 68, 85, 102, 119 | 0.0265 | 48 |
| sleep_wake_up | 0, 11, 21, 32, 42, 53, 63, 74 | 0.0319 | 43 |
| move_walk | 0, 6, 11, 17, 22, 28, 33, 39 | 0.0311 | 86 |
| move_hop | 0, 5, 10, 15, 20, 25, 30, 35 | 0.0243 | 52 |
| move_swim | 0, 4, 8, 12, 17, 21, 25, 29 | 0.0044 | 8 |
| move_fall_land | 0, 11, 21, 32, 42, 53, 63, 74 | 0.0283 | 38 |
| int_dragged | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0042 | 6 |
| int_petted | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0411 | 40 |
| int_poked | 0, 6, 13, 19, 25, 31, 38, 44 | 0.0208 | 33 |
| int_tickled | 0, 7, 13, 20, 27, 34, 40, 47 | 0.0236 | 63 |
| int_look_up | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0237 | 50 |
| int_look_up_right | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0027 | 7 |
| int_look_right | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0048 | 7 |
| int_look_down_right | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0241 | 51 |
| int_look_down | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0279 | 75 |
| int_look_down_left | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0234 | 45 |
| int_look_left | 0, 8, 17, 25, 34, 42, 51, 59 | 0.006 | 11 |
| int_look_up_left | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0032 | 6 |
| mood_happy | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0242 | 40 |
| mood_sad | 0, 17, 34, 51, 68, 85, 102, 119 | 0.0242 | 47 |
| mood_surprised | 0, 8, 15, 23, 30, 38, 45, 53 | 0.0034 | 14 |
| mood_hungry | 0, 13, 25, 38, 51, 64, 76, 89 | 0.0039 | 8 |
| mood_love | 0, 13, 25, 38, 51, 64, 76, 89 | 0.0027 | 7 |
| mood_smile_wink | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0218 | 35 |
| fun_spin | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0235 | 45 |
| fun_peek | 0, 13, 25, 38, 51, 64, 76, 89 | 0.0058 | 10 |
| fun_notify | 0, 8, 17, 25, 34, 42, 51, 59 | 0.0208 | 33 |
| fun_bubble_ride | 0, 17, 34, 51, 68, 85, 102, 119 | 0.0027 | 7 |
