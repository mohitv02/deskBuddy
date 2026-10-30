//! Non-secret settings persisted as JSON. Writes are debounced on a background
//! thread so dragging the mascot does not hammer the disk.

use std::fs;
use std::io;
use std::sync::mpsc::{channel, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde::{Deserialize, Serialize};

use crate::paths;

const SAVE_DEBOUNCE: Duration = Duration::from_millis(500);

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default, rename_all = "camelCase")]
pub struct Settings {
    pub mascot_x: Option<f64>,
    pub mascot_y: Option<f64>,
    pub icon_size: u32,
    pub animation_enabled: bool,
    pub autostart: bool,
    pub hotkey: String,
    pub auto_lock_minutes: u32,
    /// Alarm overlay: "auto" (sprite.json's choice, else "sparks"), "sparks",
    /// "flames", "webs", "shuriken" or "none".
    pub alarm_effect: String,
    /// Which pet to show: "classic", a bundled pack id, "custom", or "" for
    /// the user's own artwork if present, else classic (see mascot.rs).
    pub pet: String,
    /// Seconds with nothing happening before the pet dozes off (0 = never).
    pub sleep_after_seconds: u32,
    /// Pinned panels stay open until closed with ×; unpinned ones hide when
    /// they lose focus.
    pub panel_pinned: bool,
    /// LAN chat server (`host`, `host:port` or `ws://…`); empty = chat off,
    /// and DeskBuddy makes no network connections.
    pub chat_server: String,
    /// Name others see; empty = the login name.
    pub chat_name: String,
    /// This machine's address as others know it; empty = whatever address the
    /// server sees us connect from.
    pub chat_ip: String,
    /// Local date (YYYY-MM-DD) the 17:00 reminder last rang, so it rings once a day.
    pub evening_reminder_day: String,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            mascot_x: None,
            mascot_y: None,
            icon_size: 96,
            animation_enabled: true,
            autostart: false,
            hotkey: crate::system::hotkey::DEFAULT.into(),
            auto_lock_minutes: 5,
            alarm_effect: "auto".into(),
            pet: String::new(),
            sleep_after_seconds: 20,
            panel_pinned: false,
            chat_server: String::new(),
            chat_name: String::new(),
            chat_ip: String::new(),
            evening_reminder_day: String::new(),
        }
    }
}

fn settings_path() -> std::path::PathBuf {
    paths::config_dir().join("settings.json")
}

fn read() -> Settings {
    fs::read_to_string(settings_path())
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

fn write(s: &Settings) -> io::Result<()> {
    let path = settings_path();
    fs::create_dir_all(path.parent().expect("settings path has a parent"))?;
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, serde_json::to_vec_pretty(s)?)?;
    fs::rename(tmp, path)
}

pub struct SettingsStore {
    current: Arc<Mutex<Settings>>,
    dirty: Sender<()>,
}

impl SettingsStore {
    pub fn load() -> Self {
        let current = Arc::new(Mutex::new(read()));
        let (dirty, rx) = channel::<()>();
        let shared = current.clone();
        std::thread::Builder::new()
            .name("settings-saver".into())
            .spawn(move || {
                while rx.recv().is_ok() {
                    // Coalesce bursts (e.g. drag moves) into a single write.
                    loop {
                        match rx.recv_timeout(SAVE_DEBOUNCE) {
                            Ok(()) => continue,
                            Err(RecvTimeoutError::Timeout) => break,
                            Err(RecvTimeoutError::Disconnected) => return,
                        }
                    }
                    let snapshot = shared.lock().unwrap().clone();
                    if let Err(e) = write(&snapshot) {
                        eprintln!("deskbuddy: failed to save settings: {e}");
                    }
                }
            })
            .expect("spawn settings saver");
        Self { current, dirty }
    }

    pub fn get(&self) -> Settings {
        self.current.lock().unwrap().clone()
    }

    pub fn update(&self, f: impl FnOnce(&mut Settings)) -> Settings {
        let snapshot = {
            let mut s = self.current.lock().unwrap();
            f(&mut s);
            s.clone()
        };
        let _ = self.dirty.send(());
        snapshot
    }

    /// Synchronous save, used right before quitting.
    pub fn flush(&self) {
        if let Err(e) = write(&self.get()) {
            eprintln!("deskbuddy: failed to save settings: {e}");
        }
    }
}
