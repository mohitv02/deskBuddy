//! Global shortcut that toggles the panel (X11 key grab via the official
//! global-shortcut plugin). Ubuntu binds Ctrl+Alt+T (Terminal) and Ctrl+Alt+D
//! (show desktop), so the default is Ctrl+Alt+B; shortcuts the desktop already
//! uses are refused with the owning action named on the Settings page.

use std::sync::Mutex;

use tauri::{AppHandle, Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

use crate::settings::SettingsStore;
use crate::system::window;

/// Earlier defaults, both taken by Ubuntu; migrated to DEFAULT on startup.
const OLD_DEFAULTS: [&str; 2] = ["Ctrl+Alt+T", "Ctrl+Alt+D"];
pub const DEFAULT: &str = "Ctrl+Alt+B";

/// Last registration error, for the Settings page.
#[derive(Default)]
pub struct HotkeyState(pub Mutex<Option<String>>);

/// Canonical form for comparing shortcuts: sorted modifiers + lowercase key.
fn canonical(mods: &mut Vec<&'static str>, key: &str) -> String {
    mods.sort_unstable();
    mods.dedup();
    let key = match key.to_ascii_lowercase().as_str() {
        "page_up" | "prior" => "pageup".to_string(),
        "page_down" | "next" => "pagedown".to_string(),
        "return" => "enter".to_string(),
        k => k.to_string(),
    };
    format!("{}+{key}", mods.join("+"))
}

/// "Ctrl+Alt+D" → canonical.
fn canonical_ours(accel: &str) -> Option<String> {
    let mut parts: Vec<&str> = accel.split('+').map(str::trim).filter(|p| !p.is_empty()).collect();
    let key = parts.pop()?;
    let mut mods = Vec::new();
    for m in parts {
        mods.push(match m.to_ascii_lowercase().as_str() {
            "ctrl" | "control" | "commandorcontrol" => "ctrl",
            "alt" | "option" => "alt",
            "shift" => "shift",
            "super" | "meta" | "cmd" | "command" => "super",
            _ => return None,
        });
    }
    Some(canonical(&mut mods, key))
}

/// GNOME's "<Primary><Alt>t" → canonical.
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
fn canonical_gnome(accel: &str) -> Option<String> {
    let mut rest = accel.trim();
    let mut mods = Vec::new();
    while let Some(stripped) = rest.strip_prefix('<') {
        let end = stripped.find('>')?;
        mods.push(match stripped[..end].to_ascii_lowercase().as_str() {
            "primary" | "control" | "ctrl" => "ctrl",
            "alt" | "mod1" => "alt",
            "shift" => "shift",
            "super" | "mod4" | "meta" => "super",
            _ => return None,
        });
        rest = &stripped[end + 1..];
    }
    (!rest.is_empty()).then(|| canonical(&mut mods, rest))
}

/// Which GNOME action already uses this shortcut, if any. Grabbing it would
/// not fail on X11 — both programs would react — so check the desktop's own
/// keybinding settings instead of relying on a registration error.
#[cfg(target_os = "linux")]
fn desktop_conflict(accel: &str) -> Option<String> {
    use gtk::gio::prelude::*;
    let wanted = canonical_ours(accel)?;
    let source = gtk::gio::SettingsSchemaSource::default()?;
    const SCHEMAS: [&str; 5] = [
        "org.gnome.settings-daemon.plugins.media-keys",
        "org.gnome.desktop.wm.keybindings",
        "org.gnome.shell.keybindings",
        "org.gnome.mutter.keybindings",
        "org.gnome.mutter.wayland.keybindings",
    ];
    for id in SCHEMAS {
        let Some(schema) = source.lookup(id, true) else { continue };
        let settings = gtk::gio::Settings::new(id);
        for key in schema.list_keys() {
            let value = settings.value(&key);
            let accels: Vec<String> = value.get::<Vec<String>>().or_else(|| value.get::<String>().map(|s| vec![s])).unwrap_or_default();
            if accels.iter().any(|a| canonical_gnome(a).as_deref() == Some(wanted.as_str())) {
                return Some(key.replace('-', " "));
            }
        }
    }
    None
}

#[cfg(not(target_os = "linux"))]
fn desktop_conflict(_: &str) -> Option<String> {
    None
}

fn register(app: &AppHandle, accel: &str) -> Result<(), String> {
    let gs = app.global_shortcut();
    let _ = gs.unregister_all();
    if accel.trim().is_empty() {
        return Ok(()); // disabled
    }
    if let Some(action) = desktop_conflict(accel) {
        return Err(format!("{accel} is already Ubuntu's “{action}” shortcut. Pick another."));
    }
    gs.on_shortcut(accel, |app, _, event| {
        if event.state == ShortcutState::Pressed {
            let _ = window::toggle_panel(app);
        }
    })
    .map_err(|e| format!("{accel} is not available ({e}). Another app may be using it."))
}

/// Startup: register the saved shortcut, moving off the old conflicting default.
pub fn init(app: &AppHandle) {
    let store = app.state::<SettingsStore>();
    let mut accel = store.get().hotkey;
    let mut result = register(app, &accel);
    if result.is_err() && OLD_DEFAULTS.contains(&accel.as_str()) {
        accel = DEFAULT.into();
        result = register(app, &accel);
        if result.is_ok() {
            store.update(|s| s.hotkey = accel.clone());
        }
    }
    if let Err(e) = &result {
        eprintln!("deskbuddy: global shortcut: {e}");
    }
    *app.state::<HotkeyState>().0.lock().unwrap() = result.err();
}

/// Settings change: keep the old shortcut if the new one can't be registered.
pub fn change(app: &AppHandle, accel: &str) -> Result<(), String> {
    let previous = app.state::<SettingsStore>().get().hotkey;
    match register(app, accel) {
        Ok(()) => {
            app.state::<SettingsStore>().update(|s| s.hotkey = accel.to_string());
            *app.state::<HotkeyState>().0.lock().unwrap() = None;
            Ok(())
        }
        Err(e) => {
            let _ = register(app, &previous);
            Err(e)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shortcut_forms_compare_equal() {
        assert_eq!(canonical_ours("Ctrl+Alt+T"), canonical_gnome("<Primary><Alt>t"));
        assert_eq!(canonical_ours("Alt+Ctrl+t"), canonical_gnome("<Control><Alt>T"));
        assert_eq!(canonical_ours("Super+PageUp"), canonical_gnome("<Super>Page_Up"));
        assert_ne!(canonical_ours("Ctrl+Alt+B"), canonical_gnome("<Primary><Alt>t"));
        assert_ne!(canonical_ours("Ctrl+Shift+T"), canonical_gnome("<Primary><Alt>t"));
        assert_eq!(canonical_ours("Hyper+X"), None);
        assert_eq!(canonical_gnome("<Primary>"), None);
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn knows_ubuntus_terminal_shortcut() {
        // Only meaningful on a GNOME machine with the default bindings.
        if gtk::gio::SettingsSchemaSource::default().and_then(|s| s.lookup("org.gnome.settings-daemon.plugins.media-keys", true)).is_some() {
            assert!(desktop_conflict("Ctrl+Alt+T").is_some());
            assert!(desktop_conflict(DEFAULT).is_none(), "the default must be free");
        }
    }
}
