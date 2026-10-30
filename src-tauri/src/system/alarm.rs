//! Todo alarms: a scheduler thread checks for due alarms every few seconds and
//! rings them — looping sound, a GNOME notification with actions, the mascot's
//! alarm animation, and a click-through effect overlay around the mascot.
//! Ringing stops on any of: notification action/dismiss, clicking the mascot,
//! the panel's Stop/Done buttons, completing the todo, or after RING_FOR.

use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};

use crate::db::{now_ms, todos, Db};
use crate::paths;
use crate::system::window;

const CHECK_EVERY: Duration = Duration::from_secs(5);
const RING_FOR: Duration = Duration::from_secs(60);
/// Alarms missed while DeskBuddy was not running still ring if this recent.
const MISSED_GRACE_MS: i64 = 12 * 60 * 60 * 1000;
pub const SNOOZE: Duration = Duration::from_secs(10 * 60);
const SYSTEM_SOUND: &str = "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga";

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AlarmInfo {
    pub todo_id: i64,
    pub title: String,
    pub due: Option<String>,
}

struct Active {
    info: AlarmInfo,
    stop: Arc<AtomicBool>,
}

#[derive(Default)]
pub struct AlarmState(Mutex<Option<Active>>);

impl AlarmState {
    pub fn current(&self) -> Option<AlarmInfo> {
        self.0.lock().unwrap().as_ref().map(|a| a.info.clone())
    }
}

pub fn spawn_scheduler(app: AppHandle) {
    let _ = std::thread::Builder::new().name("alarms".into()).spawn(move || loop {
        let now = now_ms();
        match app.state::<Db>().with(|c| todos::take_due_alarms(c, now)) {
            Ok(due) => {
                // Several at once (e.g. after a restart): ring the latest, note the rest.
                if let Some(todo) = due.into_iter().filter(|t| now - t.remind_at.unwrap_or(now) < MISSED_GRACE_MS).last() {
                    ring(&app, &todo);
                }
            }
            Err(e) => eprintln!("deskbuddy: alarm check failed: {e}"),
        }
        std::thread::sleep(CHECK_EVERY);
    });
}

pub fn ring(app: &AppHandle, todo: &todos::Todo) {
    stop(app);
    let info = AlarmInfo { todo_id: todo.id, title: todo.title.clone(), due: todo.due.clone() };
    let stop_flag = Arc::new(AtomicBool::new(false));
    *app.state::<AlarmState>().0.lock().unwrap() = Some(Active { info: info.clone(), stop: stop_flag.clone() });

    let _ = app.emit("alarm", &info);
    if let Err(e) = window::open_fx(app) {
        eprintln!("deskbuddy: alarm effect unavailable: {e}");
    }
    spawn_sound(app.clone(), stop_flag.clone());
    spawn_notification(app.clone(), info);
}

/// Stops the ringing alarm, if any. Returns whether one was ringing.
pub fn stop(app: &AppHandle) -> bool {
    let Some(active) = app.state::<AlarmState>().0.lock().unwrap().take() else { return false };
    active.stop.store(true, Ordering::SeqCst);
    window::close_fx(app);
    let _ = app.emit("alarm-stopped", active.info.todo_id);
    true
}

/// Stop only if the ringing alarm belongs to this todo (e.g. it was completed).
pub fn stop_for(app: &AppHandle, todo_id: i64) {
    let ringing = app.state::<AlarmState>().current().is_some_and(|a| a.todo_id == todo_id);
    if ringing {
        stop(app);
    }
}

pub fn snooze(app: &AppHandle, todo_id: i64) -> Result<(), String> {
    let until = now_ms() + SNOOZE.as_millis() as i64;
    app.state::<Db>().with(|c| todos::snooze(c, todo_id, until)).map_err(|e| e.to_string())?;
    stop_for(app, todo_id);
    let _ = app.emit_to(window::MASCOT, "alarm-snoozed", todo_id);
    let _ = app.emit("todos-changed", ());
    Ok(())
}

pub fn complete(app: &AppHandle, todo_id: i64) -> Result<(), String> {
    app.state::<Db>()
        .with(|c| todos::set_status(c, todo_id, todos::Status::Done))
        .map_err(|e| e.to_string())?;
    stop_for(app, todo_id);
    let _ = app.emit_to(window::MASCOT, "mascot-happy", ());
    let _ = app.emit("todos-changed", ());
    Ok(())
}

/// `~/.config/deskbuddy/alarm.{oga,ogg,wav}` if present, else the system alarm.
fn sound_file() -> PathBuf {
    ["oga", "ogg", "wav"]
        .iter()
        .map(|ext| paths::config_dir().join(format!("alarm.{ext}")))
        .find(|p| p.exists())
        .unwrap_or_else(|| PathBuf::from(SYSTEM_SOUND))
}

fn play(file: &PathBuf) -> Option<Child> {
    let quiet = |mut c: Command| c.stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).spawn().ok();
    let mut paplay = Command::new("paplay");
    paplay.arg(file);
    let mut pw = Command::new("pw-play");
    pw.arg(file);
    let mut canberra = Command::new("canberra-gtk-play");
    canberra.arg("-f").arg(file);
    quiet(paplay).or_else(|| quiet(pw)).or_else(|| quiet(canberra))
}

fn spawn_sound(app: AppHandle, stop_flag: Arc<AtomicBool>) {
    let _ = std::thread::Builder::new().name("alarm-sound".into()).spawn(move || {
        let file = sound_file();
        let started = Instant::now();
        while !stop_flag.load(Ordering::SeqCst) && started.elapsed() < RING_FOR {
            let Some(mut child) = play(&file) else {
                eprintln!("deskbuddy: no sound player found (paplay / pw-play / canberra-gtk-play)");
                break;
            };
            while child.try_wait().ok().flatten().is_none() {
                if stop_flag.load(Ordering::SeqCst) {
                    let _ = child.kill();
                    let _ = child.wait();
                    return;
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            std::thread::sleep(Duration::from_millis(300));
        }
        // Timed out without being acknowledged: stop the visuals too (the
        // notification stays in GNOME's list until dismissed).
        if !stop_flag.load(Ordering::SeqCst) {
            stop(&app);
        }
    });
}

fn spawn_notification(app: AppHandle, info: AlarmInfo) {
    let _ = std::thread::Builder::new().name("alarm-notify".into()).spawn(move || {
        let time = info.due.as_deref().and_then(|d| d.get(11..16)).unwrap_or("now");
        let shown = notify_rust::Notification::new()
            .appname("DeskBuddy")
            .summary(&format!("⏰ {}", info.title))
            .body(&format!("Due at {time}"))
            .icon("alarm-symbolic")
            .urgency(notify_rust::Urgency::Critical)
            .action("default", "Open")
            .action("done", "Mark done")
            .action("snooze", "Snooze 10 min")
            .show();
        let handle = match shown {
            Ok(h) => h,
            Err(e) => return eprintln!("deskbuddy: notification failed: {e}"),
        };
        let id = info.todo_id;
        handle.wait_for_action(|action| {
            let result = match action {
                "done" => complete(&app, id),
                "snooze" => snooze(&app, id),
                "default" => {
                    stop_for(&app, id);
                    window::show_panel(&app, Some("todos")).map_err(|e| e.to_string())
                }
                // "__closed": dismissed — treat as acknowledged.
                _ => {
                    stop_for(&app, id);
                    Ok(())
                }
            };
            if let Err(e) = result {
                eprintln!("deskbuddy: alarm action failed: {e}");
            }
        });
    });
}
