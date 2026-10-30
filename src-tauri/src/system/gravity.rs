//! Let go of a lifted mascot and it drops back down. A drag is the window
//! manager's own move, so the release never reaches the webview: we watch the
//! pointer button instead. If the mascot ended up higher than where the drag
//! started, the window falls (accelerating, like gravity) up to `MAX_FALL`
//! back towards that spot, then the page plays its landing clip.
//!
//! Flick it sideways as you let go and it is thrown instead: it slides that
//! way, slowing down (and falling if it was lifted), tumbling as it goes,
//! then turns back and, if the pet has the clips, breathes its effect at you.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Emitter, Manager, PhysicalPosition};

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
/// Release speed (logical px/s) needed for a throw, mostly sideways.
const THROW_SPEED: f64 = 1000.0;
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
        let thrown = is_throw(vx / scale, vy / scale) && throw(&app, start, vx).unwrap_or_else(|e| {
            eprintln!("deskbuddy: mascot throw: {e}");
            false
        });
        if !thrown {
            if let Err(e) = drop_down(&app, start) {
                eprintln!("deskbuddy: mascot drop: {e}");
            }
        }
        let _ = app.emit_to(MASCOT, "mascot-landed", ());
        if thrown {
            fire_back(&app, if vx > 0.0 { -1 } else { 1 }, seq);
        }
    });
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

/// Fast and mostly sideways (logical px/s).
fn is_throw(vx: f64, vy: f64) -> bool {
    vx.abs() >= THROW_SPEED && vx.abs() > vy.abs()
}

/// How far a throw at `speed` slides before friction stops it, at most `max`.
fn slide_distance(speed: f64, max: f64) -> f64 {
    let v = speed.min(MAX_THROW_SPEED);
    (v * v / (2.0 * FRICTION)).min(max)
}

/// Slide the window sideways (and down, if it was lifted). Returns false,
/// without moving, if there's no room to slide.
fn throw(app: &AppHandle, start: PhysicalPosition<i32>, vx: f64) -> tauri::Result<bool> {
    let Some(win) = app.get_webview_window(MASCOT) else { return Ok(false) };
    let end = win.outer_position()?;
    let scale = win.scale_factor()?;
    let size = win.outer_size()?;
    let dir = if vx > 0.0 { 1.0 } else { -1.0 };
    let (room_side, room_below) = match win.current_monitor()? {
        Some(m) => {
            let right = m.position().x + m.size().width as i32 - size.width as i32;
            let side = if dir > 0.0 { right - end.x } else { end.x - m.position().x };
            (side as f64, (m.position().y + m.size().height as i32 - size.height as i32 - end.y) as f64)
        }
        None => (f64::MAX, f64::MAX),
    };
    let slide = (slide_distance(vx.abs() / scale, MAX_SLIDE) * scale).min(room_side).max(0.0);
    if slide < MIN_SLIDE * scale {
        return Ok(false);
    }
    let fall = fall_distance(start.y, end.y, MAX_FALL * scale, room_below);
    let _ = app.emit_to(MASCOT, "mascot-thrown", dir as i32);
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
    if !settings.animation_enabled || !crate::mascot::has_state(&settings.pet, "thrownLanded") {
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
    use super::{fall_distance, is_throw, release_velocity, slide_distance, MAX_SLIDE};

    #[test]
    fn release_velocity_uses_first_and_last_sample() {
        assert_eq!(release_velocity(&[(0.0, 100.0, 50.0), (0.05, 130.0, 50.0), (0.1, 200.0, 40.0)]), (1000.0, -100.0));
        assert_eq!(release_velocity(&[(0.0, 100.0, 50.0)]), (0.0, 0.0), "one sample: no speed");
        assert_eq!(release_velocity(&[]), (0.0, 0.0));
    }

    #[test]
    fn only_fast_sideways_flicks_are_throws() {
        assert!(is_throw(1500.0, 200.0));
        assert!(is_throw(-1500.0, 200.0), "either way");
        assert!(!is_throw(600.0, 0.0), "too slow: just a drop");
        assert!(!is_throw(1200.0, 1500.0), "mostly vertical");
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
