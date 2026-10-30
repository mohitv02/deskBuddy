//! XDG locations. We resolve them ourselves (instead of Tauri's path API) so the
//! folder is literally `deskbuddy`, not the reverse-DNS bundle identifier.

use std::path::PathBuf;

fn xdg(var: &str, fallback: &str) -> PathBuf {
    match std::env::var_os(var) {
        Some(v) if !v.is_empty() => PathBuf::from(v),
        _ => std::env::var_os("HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("."))
            .join(fallback),
    }
}

/// `~/.local/share/deskbuddy` — database and backups.
pub fn data_dir() -> PathBuf {
    xdg("XDG_DATA_HOME", ".local/share").join("deskbuddy")
}

/// `~/.config/deskbuddy` — non-secret UI settings, readable before unlock.
pub fn config_dir() -> PathBuf {
    xdg("XDG_CONFIG_HOME", ".config").join("deskbuddy")
}

/// `$XDG_RUNTIME_DIR/deskbuddy` (per-user tmpfs) for the single-instance socket.
pub fn runtime_dir() -> PathBuf {
    match std::env::var_os("XDG_RUNTIME_DIR") {
        Some(v) if !v.is_empty() => PathBuf::from(v).join("deskbuddy"),
        _ => config_dir(),
    }
}
