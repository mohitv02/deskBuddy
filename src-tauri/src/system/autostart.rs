//! Start on login via an XDG autostart entry (~/.config/autostart/deskbuddy.desktop).

use std::path::PathBuf;

fn entry_path() -> PathBuf {
    let config = match std::env::var_os("XDG_CONFIG_HOME") {
        Some(v) if !v.is_empty() => PathBuf::from(v),
        _ => PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".config"),
    };
    config.join("autostart").join("deskbuddy.desktop")
}

/// What to launch: the AppImage itself when running from one (its mounted
/// path changes every run), otherwise this executable.
fn exec_path() -> std::io::Result<PathBuf> {
    match std::env::var_os("APPIMAGE") {
        Some(p) if !p.is_empty() => Ok(PathBuf::from(p)),
        _ => std::env::current_exe(),
    }
}

/// Desktop Entry `Exec` quoting: wrap in quotes, escape `"` `` ` `` `$` `\`.
fn quote_exec(path: &str) -> String {
    let mut out = String::from("\"");
    for c in path.chars() {
        if matches!(c, '"' | '`' | '$' | '\\') {
            out.push('\\');
        }
        out.push(c);
    }
    out.push('"');
    out
}

fn contents(exec: &str) -> String {
    format!(
        "[Desktop Entry]\nType=Application\nName=DeskBuddy\nComment=Floating desk buddy with todos and an encrypted vault\nExec={}\nIcon=deskbuddy\nTerminal=false\nX-GNOME-Autostart-enabled=true\nX-GNOME-Autostart-Delay=3\n",
        quote_exec(exec)
    )
}

pub fn set(enabled: bool) -> std::io::Result<()> {
    let path = entry_path();
    if !enabled {
        return match std::fs::remove_file(&path) {
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
            other => other,
        };
    }
    std::fs::create_dir_all(path.parent().expect("autostart dir"))?;
    let exe = exec_path()?;
    std::fs::write(path, contents(&exe.to_string_lossy()))
}

/// Keep the entry in sync with the setting (and with where the app now lives).
pub fn reconcile(enabled: bool) {
    let wanted = enabled.then(|| exec_path().ok()).flatten().map(|exe| contents(&exe.to_string_lossy()));
    let current = std::fs::read_to_string(entry_path()).ok();
    if wanted != current {
        if let Err(e) = set(enabled) {
            eprintln!("deskbuddy: autostart: {e}");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exec_is_quoted_per_desktop_entry_spec() {
        assert_eq!(quote_exec("/usr/bin/deskbuddy"), "\"/usr/bin/deskbuddy\"");
        assert_eq!(quote_exec("/home/a b/$x\"y"), "\"/home/a b/\\$x\\\"y\"");
        let c = contents("/opt/DeskBuddy.AppImage");
        assert!(c.starts_with("[Desktop Entry]\n") && c.contains("Exec=\"/opt/DeskBuddy.AppImage\"\n"));
    }
}
