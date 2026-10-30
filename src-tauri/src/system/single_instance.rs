//! Ensures only one DeskBuddy runs per user. The first instance listens on a
//! Unix socket; a later launch connects, asks it to show the panel, and exits.

use std::io::{Read, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::PathBuf;

use tauri::AppHandle;

use crate::paths;

const SHOW: &[u8] = b"show";

fn socket_path() -> PathBuf {
    paths::runtime_dir().join("deskbuddy.sock")
}

/// Returns `None` if another instance is already running (and has been told
/// to show its panel), otherwise the listener this instance should serve.
pub fn acquire() -> Option<Option<UnixListener>> {
    let path = socket_path();
    if let Ok(mut stream) = UnixStream::connect(&path) {
        let _ = stream.write_all(SHOW);
        return None;
    }
    // Nobody answered: any socket file left behind is from a crashed run.
    let _ = std::fs::remove_file(&path);
    if let Some(dir) = path.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    match UnixListener::bind(&path) {
        Ok(listener) => Some(Some(listener)),
        Err(e) => {
            eprintln!("deskbuddy: single-instance socket unavailable: {e}");
            Some(None)
        }
    }
}

pub fn serve(app: AppHandle, listener: UnixListener) {
    let _ = std::thread::Builder::new().name("single-instance".into()).spawn(move || {
        for mut stream in listener.incoming().flatten() {
            let mut buf = [0u8; 16];
            let n = stream.read(&mut buf).unwrap_or(0);
            if &buf[..n] == SHOW {
                let _ = super::window::show_panel(&app, None);
            }
        }
    });
}
