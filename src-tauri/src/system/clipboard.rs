//! Clipboard via GTK (already linked, no extra dependency). Sensitive copies are
//! cleared after a delay — but only if we still own the clipboard, so a later
//! copy from another app is never wiped.

use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use tauri::AppHandle;

pub const SECRET_CLEAR_AFTER: Duration = Duration::from_secs(30);

static GENERATION: AtomicU64 = AtomicU64::new(0);

pub fn copy(app: &AppHandle, text: String, clear_after: Option<Duration>) -> tauri::Result<()> {
    let generation = GENERATION.fetch_add(1, Ordering::SeqCst) + 1;
    app.run_on_main_thread(move || {
        #[cfg(target_os = "linux")]
        gtk::Clipboard::get(&gtk::gdk::SELECTION_CLIPBOARD).set_text(&text);
    })?;
    if let Some(delay) = clear_after {
        let app = app.clone();
        std::thread::spawn(move || {
            std::thread::sleep(delay);
            // A newer copy from DeskBuddy supersedes this timer.
            if GENERATION.load(Ordering::SeqCst) == generation {
                let _ = app.run_on_main_thread(|| {
                    // gtk_clipboard_clear only acts while we are the owner.
                    #[cfg(target_os = "linux")]
                    gtk::Clipboard::get(&gtk::gdk::SELECTION_CLIPBOARD).clear();
                });
            }
        });
    }
    Ok(())
}
