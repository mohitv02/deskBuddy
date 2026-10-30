//! Locks the vault after `autoLockMinutes` without vault activity (0 = never).

use std::time::Duration;

use tauri::{AppHandle, Emitter, Manager};

use crate::settings::SettingsStore;
use crate::vault_store::{Status, VaultStore};

pub fn spawn(app: AppHandle) {
    let _ = std::thread::Builder::new().name("vault-autolock".into()).spawn(move || loop {
        std::thread::sleep(Duration::from_secs(5));
        let minutes = app.state::<SettingsStore>().get().auto_lock_minutes;
        let store = app.state::<VaultStore>();
        if minutes > 0 && store.status() == Status::Unlocked && store.idle_for() >= Duration::from_secs(minutes as u64 * 60) {
            lock(&app);
        }
    });
}

pub fn lock(app: &AppHandle) {
    app.state::<VaultStore>().lock();
    let _ = app.emit("vault-locked", ());
}
