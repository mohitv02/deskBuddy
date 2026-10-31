//! Let go of a lifted mascot and it drops back down. A drag is the window
//! manager's own move, so the release never reaches the webview: we watch the
//! pointer button instead. If the mascot ended up higher than where the drag
//! started, the window falls (accelerating, like gravity) up to `MAX_FALL`
//! back towards that spot, then the page plays its landing clip.
//!
//! Flick it as you let go and it is thrown instead, one of 8 ways:
//! sideways it slides along, slowing down (and falling if it was lifted),
//! tumbling as it goes, then turns back and, if the pet has the clips,
//! breathes its effect at you; up (straight or diagonally) it flies up in an
//! arc and falls back; down it slams into the ground below.

use std::f64::consts::FRAC_PI_4;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, WebviewWindow};

use super::window::{self, MASCOT};
use crate::settings::SettingsStore;

/// Longest fall, in logical px (a few inches on most screens).
const MAX_FALL: f64 = 200.0;
/// Shorter drops just land in place.
const MIN_FALL: f64 = 12.0;
/// Logical px/s²: a full fall takes about 0.37 s.
const GRAVITY: f64 = 3000.0;
const FRAME: Duration = Duration::from_millis(16);
const BUTTON_POLL: Duration = Duration::from_millis(16);
/// Release speed (logical px/s) needed for a throw.
const THROW_SPEED: f64 = 1000.0;
/// Highest an upward throw flies, in logical px.
const MAX_RISE: f64 = 300.0;
/// A downward throw keeps its release speed about this long (s) before it
/// hits the ground, so a harder flick slams it further down, at most `MAX_SLAM`.
const SLAM_REACH: f64 = 0.12;
const MAX_SLAM: f64 = 240.0;
/// Faster flicks than this slide no further.
const MAX_THROW_SPEED: f64 = 3000.0;
/// Sliding friction, logical px/s²: a hard throw slides about 0.9 s.
const FRICTION: f64 = 1500.0;
const MAX_SLIDE: f64 = 600.0;
/// Too little room to slide (e.g. against the screen edge): just drop.
const MIN_SLIDE: f64 = 40.0;
/// Only the pointer's last moments before the release set the throw speed.
const VELOCITY_WINDOW: Duration = Duration::from_millis(100);
/// After a throw the pet shakes off, winds up and breathes fire for about a
/// second; the overlay follows that (assets/ember_dragon_sprites thrown_fire).
const FIRE_AFTER: Duration = Duration::from_millis(1360);
const FIRE_FOR: Duration = Duration::from_millis(1100);
/// Without X11 button state, the drag is over once the window stops moving this long.
const STILL_FOR: Duration = Duration::from_millis(400);
const MAX_DRAG: Duration = Duration::from_secs(120);

static LAST_MOVE: Mutex<Option<Instant>> = Mutex::new(None);
/// Bumped by every drag, so a reaction from an older throw knows it's stale.
static DRAG_SEQ: AtomicU64 = AtomicU64::new(0);

/// Called for every move of the mascot window.
pub fn note_moved() {
    *LAST_MOVE.lock().unwrap() = Some(Instant::now());
}

/// The window manager just took over a drag of the mascot.
pub fn drag_started(app: &AppHandle) {
    let Some(start) = app.get_webview_window(MASCOT).and_then(|w| w.outer_position().ok()) else { return };
    note_moved();
    let seq = DRAG_SEQ.fetch_add(1, Ordering::SeqCst) + 1;
    // Picked up again mid-reaction: the effect would stay behind.
    if !alarm_ringing(app) {
        window::close_fx(app);
    }
    let _ = app.emit_to(MASCOT, "mascot-drag", ());
    let app = app.clone();
    let _ = std::thread::Builder::new().name("mascot-drop".into()).spawn(move || {
        let (vx, vy) = wait_for_release();
        let scale = app.get_webview_window(MASCOT).and_then(|w| w.scale_factor().ok()).unwrap_or(1.0);
        let flung = classify(vx / scale, vy / scale);
        let thrown = flung.is_some_and(|(kind, dir)| {
            throw(&app, start, kind, dir, vx, vy).unwrap_or_else(|e| {
                eprintln!("deskbuddy: mascot throw: {e}");
                false
            })
        });
        if !thrown {
            if let Err(e) = drop_down(&app, start) {
                eprintln!("deskbuddy: mascot drop: {e}");
            }
        }
        let _ = app.emit_to(MASCOT, "mascot-landed", ());
        if let (true, Some((Fling::Side, dir))) = (thrown, flung) {
            fire_back(&app, -dir, seq);
        }
    });
}

/// Which way a throw goes; the page has a clip family for each.
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
enum Fling {
    Side,
    Up,
    Down,
}

/// Payload of `mascot-thrown`: the kind and the sideways direction
/// (1 = right, -1 = left, 0 = straight up or down).
#[derive(Serialize, Clone)]
struct Thrown {
    kind: Fling,
    dir: i32,
}

/// A fast enough release (logical px/s) is a throw, sorted into 8 directions:
/// right/left are sideways, the three upper ones up, the three lower ones down.
fn classify(vx: f64, vy: f64) -> Option<(Fling, i32)> {
    if vx.hypot(vy) < THROW_SPEED {
        return None;
    }
    // Clockwise from "right", as screen y grows downward.
    Some(match (vy.atan2(vx) / FRAC_PI_4).round() as i32 {
        0 => (Fling::Side, 1),
        4 | -4 => (Fling::Side, -1),
        1 => (Fling::Down, 1),
        2 => (Fling::Down, 0),
        3 => (Fling::Down, -1),
        -1 => (Fling::Up, 1),
        -2 => (Fling::Up, 0),
        _ => (Fling::Up, -1),
    })
}

fn alarm_ringing(app: &AppHandle) -> bool {
    app.state::<crate::system::alarm::AlarmState>().current().is_some()
}

/// Waits for the button to come up; returns the pointer's velocity at the
/// release (physical px/s), or zero if it can't be measured.
fn wait_for_release() -> (f64, f64) {
    let deadline = Instant::now() + MAX_DRAG;
    #[cfg(target_os = "linux")]
    if let Ok(v) = x11::wait_for_button_up(deadline) {
        return v;
    }
    while Instant::now() < deadline {
        std::thread::sleep(BUTTON_POLL);
        if LAST_MOVE.lock().unwrap().map_or(true, |t| t.elapsed() >= STILL_FOR) {
            break;
        }
    }
    (0.0, 0.0)
}

/// Average velocity over pointer samples `(seconds, x, y)`, oldest first.
fn release_velocity(samples: &[(f64, f64, f64)]) -> (f64, f64) {
    match (samples.first(), samples.last()) {
        (Some(a), Some(b)) if b.0 - a.0 > 0.01 => ((b.1 - a.1) / (b.0 - a.0), (b.2 - a.2) / (b.0 - a.0)),
        _ => (0.0, 0.0),
    }
}

/// How far a throw at `speed` slides before friction stops it, at most `max`.
fn slide_distance(speed: f64, max: f64) -> f64 {
    let v = speed.min(MAX_THROW_SPEED);
    (v * v / (2.0 * FRICTION)).min(max)
}

/// How high an upward throw at `speed` flies (logical px/s → px).
fn rise_height(speed: f64) -> f64 {
    let v = speed.min(MAX_THROW_SPEED);
    (v * v / (2.0 * GRAVITY)).min(MAX_RISE)
}

/// How far below the release a downward throw at `speed` slams (logical).
fn slam_depth(speed: f64) -> f64 {
    (speed.min(MAX_THROW_SPEED) * SLAM_REACH).min(MAX_SLAM)
}

/// Time to cover `d` falling from speed `v0` under gravity `g`.
fn fall_time(v0: f64, d: f64, g: f64) -> f64 {
    ((v0 * v0 + 2.0 * g * d).sqrt() - v0) / g
}

/// Room the window has on its monitor from `at` (physical px).
struct Room {
    left: f64,
    right: f64,
    above: f64,
    below: f64,
}

fn room(win: &WebviewWindow, at: PhysicalPosition<i32>) -> tauri::Result<Room> {
    let size = win.outer_size()?;
    Ok(match win.current_monitor()? {
        Some(m) => {
            let (x0, y0) = (m.position().x, m.position().y);
            Room {
                left: (at.x - x0) as f64,
                right: (x0 + m.size().width as i32 - size.width as i32 - at.x) as f64,
                above: (at.y - y0) as f64,
                below: (y0 + m.size().height as i32 - size.height as i32 - at.y) as f64,
            }
        }
        None => Room { left: f64::MAX, right: f64::MAX, above: f64::MAX, below: f64::MAX },
    })
}

impl Room {
    fn side(&self, dir: i32) -> f64 {
        match dir {
            1 => self.right,
            -1 => self.left,
            _ => 0.0,
        }
        .max(0.0)
    }
}

/// Fling the window (velocity in physical px/s). Returns false, without
/// moving, if a sideways throw has no room to slide: it just drops then.
fn throw(app: &AppHandle, start: PhysicalPosition<i32>, kind: Fling, dir: i32, vx: f64, vy: f64) -> tauri::Result<bool> {
    let Some(win) = app.get_webview_window(MASCOT) else { return Ok(false) };
    let end = win.outer_position()?;
    let scale = win.scale_factor()?;
    let room = room(&win, end)?;
    match kind {
        Fling::Side => slide(app, &win, start, end, scale, &room, dir, vx),
        Fling::Up | Fling::Down => {
            let _ = app.emit_to(MASCOT, "mascot-thrown", Thrown { kind, dir });
            // Diagonal throws drift sideways a bit less than a flat one slides.
            let side = (slide_distance(vx.abs() / scale, MAX_SLIDE) * 0.6 * scale).min(room.side(dir));
            if kind == Fling::Up {
                toss(&win, start, end, scale, &room, dir, side, vy.abs())?;
            } else {
                slam(&win, start, end, scale, &room, dir, side, vy.abs())?;
            }
            Ok(true)
        }
    }
}

/// Up: rise against gravity, then fall to where a plain drop would land,
/// drifting `side` px sideways over the whole flight.
#[allow(clippy::too_many_arguments)]
fn toss(win: &WebviewWindow, start: PhysicalPosition<i32>, end: PhysicalPosition<i32>, scale: f64, room: &Room, dir: i32, side: f64, vy: f64) -> tauri::Result<()> {
    let g = GRAVITY * scale;
    let rise = (rise_height(vy / scale) * scale).min(room.above).max(0.0);
    let fall = fall_distance(start.y, end.y, MAX_FALL * scale, room.below);
    let v0 = (2.0 * g * rise).sqrt();
    let flight = v0 / g + (2.0 * (rise + fall) / g).sqrt();
    let t0 = Instant::now();
    loop {
        std::thread::sleep(FRAME);
        let t = t0.elapsed().as_secs_f64().min(flight);
        let dy = (0.5 * g * t * t - v0 * t).min(fall);
        let dx = side * t / flight;
        win.set_position(PhysicalPosition::new(end.x + (dir as f64 * dx).round() as i32, end.y + dy.round() as i32))?;
        if t >= flight {
            return Ok(());
        }
    }
}

/// Down: keep the release speed and accelerate into the ground below (at
/// least back to where the drag started, if it was lifted).
#[allow(clippy::too_many_arguments)]
fn slam(win: &WebviewWindow, start: PhysicalPosition<i32>, end: PhysicalPosition<i32>, scale: f64, room: &Room, dir: i32, side: f64, vy: f64) -> tauri::Result<()> {
    let g = GRAVITY * scale;
    let v0 = vy.min(MAX_THROW_SPEED * scale);
    let depth = (slam_depth(vy / scale) * scale).max(fall_distance(start.y, end.y, MAX_FALL * scale, room.below)).min(room.below).max(0.0);
    if depth < 1.0 && side < 1.0 {
        return Ok(());
    }
    let flight = fall_time(v0, depth, g).max(0.12);
    let t0 = Instant::now();
    loop {
        std::thread::sleep(FRAME);
        let t = t0.elapsed().as_secs_f64().min(flight);
        let dy = (v0 * t + 0.5 * g * t * t).min(depth);
        let dx = side * t / flight;
        win.set_position(PhysicalPosition::new(end.x + (dir as f64 * dx).round() as i32, end.y + dy.round() as i32))?;
        if t >= flight {
            return Ok(());
        }
    }
}

/// Sideways: slide (and fall, if it was lifted), slowing to a stop.
#[allow(clippy::too_many_arguments)]
fn slide(app: &AppHandle, win: &WebviewWindow, start: PhysicalPosition<i32>, end: PhysicalPosition<i32>, scale: f64, room: &Room, dir: i32, vx: f64) -> tauri::Result<bool> {
    let slide = (slide_distance(vx.abs() / scale, MAX_SLIDE) * scale).min(room.side(dir));
    if slide < MIN_SLIDE * scale {
        return Ok(false);
    }
    let fall = fall_distance(start.y, end.y, MAX_FALL * scale, room.below);
    let _ = app.emit_to(MASCOT, "mascot-thrown", Thrown { kind: Fling::Side, dir });
    let dir = dir as f64;
    // Decelerate evenly to a stop exactly `slide` away (at the edge, if that's nearer).
    let f = FRICTION * scale;
    let v0 = (2.0 * f * slide).sqrt();
    let stop_at = v0 / f;
    let g = GRAVITY * scale;
    let t0 = Instant::now();
    loop {
        std::thread::sleep(FRAME);
        let t = t0.elapsed().as_secs_f64();
        let ts = t.min(stop_at);
        let dx = (v0 * ts - 0.5 * f * ts * ts).min(slide);
        let dy = (0.5 * g * t * t).min(fall);
        win.set_position(PhysicalPosition::new(end.x + (dir * dx).round() as i32, end.y + dy.round() as i32))?;
        if t >= stop_at && dy >= fall {
            return Ok(true);
        }
    }
}

/// After a throw: the pet turns back (`facing`) and lets loose its effect,
/// timed to its clip. Skipped if it has no such clip, animation is off, an
/// alarm is ringing, or it was picked up again meanwhile.
fn fire_back(app: &AppHandle, facing: i32, seq: u64) {
    let settings = app.state::<SettingsStore>().get();
    if !settings.animation_enabled || !crate::mascot::throw_effect(&settings.pet) {
        return;
    }
    let current = || DRAG_SEQ.load(Ordering::SeqCst) == seq && !alarm_ringing(app);
    std::thread::sleep(FIRE_AFTER);
    if !current() {
        return;
    }
    if let Err(e) = window::open_reaction_fx(app, facing) {
        return eprintln!("deskbuddy: throw effect: {e}");
    }
    std::thread::sleep(FIRE_FOR);
    if current() {
        window::close_fx(app);
    }
}

/// How far a window released at `end_y` falls: back towards `start_y` if it
/// was lifted, at most `max`, and never past the bottom of the monitor.
fn fall_distance(start_y: i32, end_y: i32, max: f64, room_below: f64) -> f64 {
    ((start_y - end_y) as f64).min(max).min(room_below).max(0.0)
}

fn drop_down(app: &AppHandle, start: PhysicalPosition<i32>) -> tauri::Result<()> {
    let Some(win) = app.get_webview_window(MASCOT) else { return Ok(()) };
    let end = win.outer_position()?;
    let scale = win.scale_factor()?;
    let room_below = match win.current_monitor()? {
        Some(m) => (m.position().y + m.size().height as i32 - win.outer_size()?.height as i32 - end.y) as f64,
        None => f64::MAX,
    };
    let distance = fall_distance(start.y, end.y, MAX_FALL * scale, room_below);
    if distance < MIN_FALL * scale {
        return Ok(());
    }
    let _ = app.emit_to(MASCOT, "mascot-falling", ());
    let g = GRAVITY * scale;
    let t0 = Instant::now();
    loop {
        std::thread::sleep(FRAME);
        let t = t0.elapsed().as_secs_f64();
        let dy = (0.5 * g * t * t).min(distance);
        win.set_position(PhysicalPosition::new(end.x, end.y + dy.round() as i32))?;
        if dy >= distance {
            return Ok(());
        }
    }
}

#[cfg(target_os = "linux")]
mod x11 {
    use std::collections::VecDeque;
    use std::time::Instant;

    use x11rb::connection::Connection;
    use x11rb::protocol::xproto::{ConnectionExt as _, KeyButMask};

    /// Polls the pointer until button 1 is up; returns its velocity then.
    pub fn wait_for_button_up(deadline: Instant) -> Result<(f64, f64), Box<dyn std::error::Error>> {
        let (conn, screen) = x11rb::connect(None)?;
        let root = conn.setup().roots[screen].root;
        let t0 = Instant::now();
        let mut samples: VecDeque<(f64, f64, f64)> = VecDeque::new();
        while Instant::now() < deadline {
            let p = conn.query_pointer(root)?.reply()?;
            let now = t0.elapsed().as_secs_f64();
            samples.push_back((now, p.root_x as f64, p.root_y as f64));
            while samples.front().is_some_and(|s| now - s.0 > super::VELOCITY_WINDOW.as_secs_f64()) {
                samples.pop_front();
            }
            if !p.mask.contains(KeyButMask::BUTTON1) {
                return Ok(super::release_velocity(samples.make_contiguous()));
            }
            std::thread::sleep(super::BUTTON_POLL);
        }
        Ok((0.0, 0.0))
    }
}

#[cfg(test)]
mod tests {
    use super::{classify, fall_distance, fall_time, release_velocity, rise_height, slam_depth, slide_distance, Fling, MAX_RISE, MAX_SLAM, MAX_SLIDE};

    #[test]
    fn release_velocity_uses_first_and_last_sample() {
        assert_eq!(release_velocity(&[(0.0, 100.0, 50.0), (0.05, 130.0, 50.0), (0.1, 200.0, 40.0)]), (1000.0, -100.0));
        assert_eq!(release_velocity(&[(0.0, 100.0, 50.0)]), (0.0, 0.0), "one sample: no speed");
        assert_eq!(release_velocity(&[]), (0.0, 0.0));
    }

    #[test]
    fn fast_flicks_are_throws_in_8_directions() {
        assert_eq!(classify(1500.0, 200.0), Some((Fling::Side, 1)));
        assert_eq!(classify(-1500.0, 200.0), Some((Fling::Side, -1)), "either way");
        assert_eq!(classify(-1500.0, -10.0), Some((Fling::Side, -1)), "just above the left axis");
        assert_eq!(classify(600.0, 0.0), None, "too slow: just a drop");
        assert_eq!(classify(0.0, -1500.0), Some((Fling::Up, 0)), "screen y grows down");
        assert_eq!(classify(1100.0, -1100.0), Some((Fling::Up, 1)));
        assert_eq!(classify(-1100.0, -1100.0), Some((Fling::Up, -1)));
        assert_eq!(classify(100.0, 1500.0), Some((Fling::Down, 0)));
        assert_eq!(classify(1100.0, 1100.0), Some((Fling::Down, 1)));
        assert_eq!(classify(-1100.0, 1100.0), Some((Fling::Down, -1)));
    }

    #[test]
    fn harder_flicks_fly_higher_and_slam_deeper_up_to_a_cap() {
        assert!(rise_height(1000.0) < rise_height(1300.0));
        assert_eq!(rise_height(10_000.0), MAX_RISE);
        assert!(slam_depth(1000.0) < slam_depth(1500.0));
        assert_eq!(slam_depth(10_000.0), MAX_SLAM);
    }

    #[test]
    fn fall_time_with_and_without_a_push() {
        assert!((fall_time(0.0, 150.0, 3000.0) - 0.1_f64.sqrt()).abs() < 1e-9, "from rest: sqrt(2d/g)");
        assert!((fall_time(1000.0, 100.0, 0.000_001) - 0.1).abs() < 1e-3, "no gravity: d/v");
        assert_eq!(fall_time(1000.0, 0.0, 3000.0), 0.0);
    }

    #[test]
    fn throws_slide_further_when_faster_up_to_a_cap() {
        assert_eq!(slide_distance(1500.0, MAX_SLIDE), 600.0_f64.min(1500.0 * 1500.0 / 3000.0));
        assert!(slide_distance(1000.0, MAX_SLIDE) < slide_distance(1300.0, MAX_SLIDE));
        assert_eq!(slide_distance(10_000.0, MAX_SLIDE), MAX_SLIDE);
    }

    #[test]
    fn falls_back_down_only_when_lifted() {
        assert_eq!(fall_distance(500, 300, 200.0, 1000.0), 200.0, "lifted 200: falls all the way back");
        assert_eq!(fall_distance(500, 100, 200.0, 1000.0), 200.0, "lifted far: a few inches at most");
        assert_eq!(fall_distance(500, 450, 200.0, 1000.0), 50.0);
        assert_eq!(fall_distance(300, 500, 200.0, 1000.0), 0.0, "dragged down: no fall");
        assert_eq!(fall_distance(500, 300, 200.0, 80.0), 80.0, "stops at the screen bottom");
    }
}
