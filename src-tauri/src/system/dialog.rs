//! Native GTK file chooser, parented to the panel so it opens above it.

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};

use tauri::{AppHandle, Manager};

pub enum Mode {
    Save { suggested_name: String },
    Open,
}

/// A file chooser is open; the panel must not auto-hide behind it.
pub static OPEN: AtomicBool = AtomicBool::new(false);

/// Blocks the calling (non-main) thread until the user picks a file or cancels.
pub fn choose_backup_file(app: &AppHandle, title: &str, mode: Mode) -> Option<PathBuf> {
    let (tx, rx) = std::sync::mpsc::channel();
    let title = title.to_string();
    let handle = app.clone();
    let scheduled = app.run_on_main_thread(move || {
        #[cfg(target_os = "linux")]
        {
            use gtk::prelude::*;
            let parent = handle.get_webview_window(super::window::PANEL).and_then(|w| w.gtk_window().ok());
            let (action, accept) = match &mode {
                Mode::Save { .. } => (gtk::FileChooserAction::Save, "Export"),
                Mode::Open => (gtk::FileChooserAction::Open, "Import"),
            };
            let dialog = gtk::FileChooserNative::new(Some(&title), parent.as_ref(), action, Some(accept), Some("Cancel"));
            dialog.set_modal(true);
            let filter = gtk::FileFilter::new();
            filter.set_name(Some("DeskBuddy backup (*.dbkp)"));
            filter.add_pattern(&format!("*.{}", crate::backup::EXTENSION));
            dialog.add_filter(filter);
            if let Mode::Save { suggested_name } = &mode {
                dialog.set_do_overwrite_confirmation(true);
                dialog.set_current_name(suggested_name);
                if let Some(home) = std::env::var_os("HOME") {
                    let _ = dialog.set_current_folder(PathBuf::from(home));
                }
            }
            OPEN.store(true, Ordering::SeqCst);
            let path = (dialog.run() == gtk::ResponseType::Accept).then(|| dialog.filename()).flatten();
            OPEN.store(false, Ordering::SeqCst);
            let _ = tx.send(path);
        }
    });
    if scheduled.is_err() {
        return None;
    }
    let path = rx.recv().ok().flatten()?;
    // Always save with the right extension.
    Some(match path.extension() {
        Some(ext) if ext == crate::backup::EXTENSION => path,
        _ => path.with_extension(crate::backup::EXTENSION),
    })
}
