//! Lets the mascot watch the pointer: a few times a second, find which way the
//! pointer is (8 directions) while it is near the mascot but not on it, and
//! tell the page when that changes. Polls slowly while animation is off or a
//! fullscreen app is focused.

use std::f64::consts::FRAC_PI_4;
use std::time::Duration;

use tauri::{AppHandle, Emitter, Manager};

use super::{fullscreen, window::MASCOT};
use crate::settings::SettingsStore;

const POLL: Duration = Duration::from_millis(250);
const IDLE_POLL: Duration = Duration::from_secs(2);
/// The pointer is watched up to this many mascot sizes from its centre.
const RANGE: f64 = 4.0;
/// Clockwise from "right", as screen y grows downward.
const DIRS: [&str; 8] = ["lookRight", "lookDownRight", "lookDown", "lookDownLeft", "lookLeft", "lookUpLeft", "lookUp", "lookUpRight"];

/// Look direction for a pointer offset from the mascot's centre (physical px).
fn direction(dx: f64, dy: f64, size: f64) -> Option<&'static str> {
    let dist = dx.hypot(dy);
    // On the mascot itself, hover takes over.
    if dist < size * 0.5 || dist > size * RANGE {
        return None;
    }
    let octant = (dy.atan2(dx) / FRAC_PI_4).round() as i32;
    Some(DIRS[octant.rem_euclid(8) as usize])
}

fn look(app: &AppHandle) -> Option<&'static str> {
    let win = app.get_webview_window(MASCOT)?;
    if !win.is_visible().unwrap_or(false) {
        return None;
    }
    let cursor = app.cursor_position().ok()?;
    let pos = win.outer_position().ok()?;
    let size = win.outer_size().ok()?;
    let (w, h) = (size.width as f64, size.height as f64);
    direction(cursor.x - (pos.x as f64 + w / 2.0), cursor.y - (pos.y as f64 + h / 2.0), w)
}

pub fn spawn(app: AppHandle) {
    let _ = std::thread::Builder::new().name("pointer-watch".into()).spawn(move || {
        let mut last = None;
        loop {
            let active = app.state::<SettingsStore>().get().animation_enabled && !fullscreen::is_fullscreen();
            let dir = if active { look(&app) } else { None };
            if dir != last {
                last = dir;
                let _ = app.emit_to(MASCOT, "mascot-look", dir.unwrap_or(""));
            }
            std::thread::sleep(if active { POLL } else { IDLE_POLL });
        }
    });
}

#[cfg(test)]
mod tests {
    use super::direction;

    #[test]
    fn directions() {
        assert_eq!(direction(300.0, 0.0, 100.0), Some("lookRight"));
        assert_eq!(direction(0.0, 300.0, 100.0), Some("lookDown"));
        assert_eq!(direction(-200.0, -200.0, 100.0), Some("lookUpLeft"));
        assert_eq!(direction(0.0, -300.0, 100.0), Some("lookUp"));
        assert_eq!(direction(10.0, 10.0, 100.0), None, "on the mascot");
        assert_eq!(direction(1000.0, 0.0, 100.0), None, "too far");
    }
}
