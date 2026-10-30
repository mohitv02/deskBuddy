//! Detects whether the focused window is fullscreen (X11 / EWMH) so the mascot
//! can stop animating. Event-driven: the thread blocks on X property changes
//! instead of polling. On Wayland-native sessions the connection fails and the
//! feature is silently disabled.

use std::sync::atomic::{AtomicBool, Ordering};

use tauri::{AppHandle, Emitter};

static FULLSCREEN: AtomicBool = AtomicBool::new(false);

pub fn is_fullscreen() -> bool {
    FULLSCREEN.load(Ordering::Relaxed)
}

pub fn spawn_watcher(app: AppHandle) {
    let _ = std::thread::Builder::new().name("fullscreen-watch".into()).spawn(move || {
        #[cfg(target_os = "linux")]
        if let Err(e) = x11::watch(|fs| {
            FULLSCREEN.store(fs, Ordering::Relaxed);
            let _ = app.emit_to(super::window::MASCOT, "fullscreen-changed", fs);
        }) {
            eprintln!("deskbuddy: fullscreen detection unavailable: {e}");
        }
    });
}

#[cfg(target_os = "linux")]
mod x11 {
    use x11rb::connection::Connection;
    use x11rb::protocol::xproto::{
        Atom, AtomEnum, ChangeWindowAttributesAux, ConnectionExt as _, EventMask, Window,
    };
    use x11rb::protocol::Event;
    use x11rb::rust_connection::RustConnection;

    type Res<T> = Result<T, Box<dyn std::error::Error>>;

    fn atom(conn: &RustConnection, name: &[u8]) -> Res<Atom> {
        Ok(conn.intern_atom(false, name)?.reply()?.atom)
    }

    fn active_window(conn: &RustConnection, root: Window, net_active: Atom) -> Option<Window> {
        let reply = conn
            .get_property(false, root, net_active, AtomEnum::WINDOW, 0, 1)
            .ok()?
            .reply()
            .ok()?;
        let win = reply.value32()?.next();
        win.filter(|w| *w != 0)
    }

    fn has_fullscreen_state(conn: &RustConnection, win: Window, wm_state: Atom, fs: Atom) -> bool {
        conn.get_property(false, win, wm_state, AtomEnum::ATOM, 0, 64)
            .ok()
            .and_then(|c| c.reply().ok())
            .and_then(|r| r.value32().map(|mut atoms| atoms.any(|a| a == fs)))
            .unwrap_or(false)
    }

    fn watch_props(conn: &RustConnection, win: Window, mask: EventMask) {
        // Errors (e.g. window already destroyed) arrive as ignorable events.
        let _ = conn.change_window_attributes(win, &ChangeWindowAttributesAux::new().event_mask(mask));
    }

    pub fn watch(mut on_change: impl FnMut(bool)) -> Res<()> {
        let (conn, screen) = x11rb::connect(None)?;
        let root = conn.setup().roots[screen].root;
        let net_active = atom(&conn, b"_NET_ACTIVE_WINDOW")?;
        let wm_state = atom(&conn, b"_NET_WM_STATE")?;
        let fs_atom = atom(&conn, b"_NET_WM_STATE_FULLSCREEN")?;

        watch_props(&conn, root, EventMask::PROPERTY_CHANGE);
        let mut active: Option<Window> = None;
        let mut fullscreen = false;

        loop {
            let now_active = active_window(&conn, root, net_active);
            if now_active != active {
                if let Some(old) = active {
                    watch_props(&conn, old, EventMask::NO_EVENT);
                }
                if let Some(new) = now_active {
                    watch_props(&conn, new, EventMask::PROPERTY_CHANGE);
                }
                active = now_active;
            }
            let fs = active.is_some_and(|w| has_fullscreen_state(&conn, w, wm_state, fs_atom));
            if fs != fullscreen {
                fullscreen = fs;
                on_change(fs);
            }
            conn.flush()?;

            loop {
                if let Event::PropertyNotify(ev) = conn.wait_for_event()? {
                    let root_change = ev.window == root && ev.atom == net_active;
                    let state_change = Some(ev.window) == active && ev.atom == wm_state;
                    if root_change || state_change {
                        break;
                    }
                }
            }
        }
    }
}
