use tauri::menu::{CheckMenuItem, Menu, MenuEvent, MenuItem, PredefinedMenuItem};
use tauri::{
    AppHandle, Emitter, LogicalPosition, Manager, Monitor, PhysicalPosition, WebviewUrl,
    WebviewWindow, WebviewWindowBuilder, WindowEvent,
};

use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use crate::settings::{Settings, SettingsStore};

pub const MASCOT: &str = "mascot";
pub const PANEL: &str = "panel";
pub const FX: &str = "fx";

/// Alarm effect overlay: a click-through window around the effect origin,
/// which sits at FX_ORIGIN unless the overlay has to shift to stay on-screen.
const FX_W: f64 = 600.0;
const FX_H: f64 = 480.0;
const FX_ORIGIN: (f64, f64) = (300.0, 300.0);

const PANEL_W: f64 = 380.0;
const PANEL_H: f64 = 560.0;
const PANEL_GAP: f64 = 6.0;
/// Focus can blink out and back (popups, grabs); only hide if it stays away.
const PANEL_BLUR_GRACE: Duration = Duration::from_millis(200);
/// Set by the panel while an editor sheet is open, so a half-typed entry
/// isn't hidden when you click away to copy something.
pub static PANEL_EDITING: AtomicBool = AtomicBool::new(false);
/// Set by the panel while a native <select> dropdown is open: on Linux its
/// popup is a separate window that takes focus away from the panel.
pub static PANEL_DROPDOWN: AtomicBool = AtomicBool::new(false);
#[allow(dead_code)]
const DRAG_THRESHOLD_PX: f64 = 4.0;

#[derive(Clone, Copy)]
struct Rect {
    x: f64,
    y: f64,
    w: f64,
    h: f64,
}

impl Rect {
    fn contains(&self, x: f64, y: f64) -> bool {
        x >= self.x && y >= self.y && x < self.x + self.w && y < self.y + self.h
    }
}

fn logical_bounds(m: &Monitor) -> Rect {
    let s = m.scale_factor();
    let p = m.position();
    let z = m.size();
    Rect { x: p.x as f64 / s, y: p.y as f64 / s, w: z.width as f64 / s, h: z.height as f64 / s }
}

fn default_mascot_pos(app: &AppHandle, size: f64) -> (f64, f64) {
    match app.primary_monitor().ok().flatten() {
        Some(m) => {
            let b = logical_bounds(&m);
            (b.x + b.w - size - 48.0, b.y + b.h - size - 96.0)
        }
        None => (100.0, 100.0),
    }
}

/// Restore the saved position unless it no longer lies on any monitor.
fn initial_mascot_pos(app: &AppHandle, s: &Settings, size: f64) -> (f64, f64) {
    if let (Some(x), Some(y)) = (s.mascot_x, s.mascot_y) {
        let monitors = app.available_monitors().unwrap_or_default();
        let (cx, cy) = (x + size / 2.0, y + size / 2.0);
        if monitors.iter().any(|m| logical_bounds(m).contains(cx, cy)) {
            return (x, y);
        }
    }
    default_mascot_pos(app, size)
}

pub fn create_mascot(app: &AppHandle, s: &Settings) -> tauri::Result<WebviewWindow> {
    let size = s.icon_size as f64;
    let (x, y) = initial_mascot_pos(app, s, size);
    let win = WebviewWindowBuilder::new(app, MASCOT, WebviewUrl::App("index.html".into()))
        .title("DeskBuddy")
        .inner_size(size, size)
        .position(x, y)
        // GTK sizes non-resizable windows to their natural size (200px here),
        // ignoring inner_size; undecorated windows can't be user-resized anyway.
        .resizable(true)
        .decorations(false)
        .transparent(true)
        .shadow(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .visible_on_all_workspaces(true)
        .focused(false)
        // Map only after all hints are set: if mutter sees the window before the
        // "no decorations" hint it frames it and grows the client by the title bar.
        .visible(false)
        .build()?;

    #[cfg(target_os = "linux")]
    {
        linux::apply_mascot_hints(&win, s.icon_size as i32);
        linux::install_input(&win, app.clone());
    }
    win.show()?;

    let handle = app.clone();
    win.on_window_event(move |event| match event {
        WindowEvent::Moved(pos) => {
            remember_position(&handle, *pos);
            super::gravity::note_moved();
        }
        // Edge tiling or maximize grew the window: an invisible full-size pane
        // would swallow clicks on that part of the screen, so snap back.
        WindowEvent::Resized(size) => restore_mascot_size(&handle, *size),
        _ => {}
    });
    Ok(win)
}

fn restore_mascot_size(app: &AppHandle, size: tauri::PhysicalSize<u32>) {
    let Some(win) = app.get_webview_window(MASCOT) else { return };
    let want = app.state::<SettingsStore>().get().icon_size as f64;
    let got = size.to_logical::<f64>(win.scale_factor().unwrap_or(1.0));
    if (got.width - want).abs() > 1.0 || (got.height - want).abs() > 1.0 {
        let _ = win.unmaximize();
        let _ = win.set_size(tauri::LogicalSize::new(want, want));
    }
}

fn remember_position(app: &AppHandle, pos: PhysicalPosition<i32>) {
    let Some(win) = app.get_webview_window(MASCOT) else { return };
    let scale = win.scale_factor().unwrap_or(1.0);
    let logical: LogicalPosition<f64> = pos.to_logical(scale);
    app.state::<SettingsStore>().update(|s| {
        s.mascot_x = Some(logical.x);
        s.mascot_y = Some(logical.y);
    });
}

/// Open the alarm effect overlay around the mascot (no-op for effect "none").
pub fn open_fx(app: &AppHandle) -> tauri::Result<()> {
    close_fx(app);
    let settings = app.state::<SettingsStore>().get();
    let size = settings.icon_size as f64;
    let (custom_effect, custom_origin) = crate::mascot::effect_spec(&settings.pet, size);
    let effect = if settings.alarm_effect != "auto" && crate::mascot::EFFECTS.contains(&settings.alarm_effect.as_str()) {
        settings.alarm_effect.clone()
    } else {
        custom_effect.unwrap_or_else(|| "sparks".into())
    };
    open_effect(app, &effect, custom_origin.unwrap_or((size * 0.5, size * 0.2)), None)
}

/// The pet's own effect, aimed one way (1 = right, -1 = left), for a reaction
/// such as breathing fire after a throw. The pet's art faces right, so facing
/// left mirrors the origin. No-op if the pet has no effect of its own.
pub fn open_reaction_fx(app: &AppHandle, facing: i32) -> tauri::Result<()> {
    let settings = app.state::<SettingsStore>().get();
    let size = settings.icon_size as f64;
    let (Some(effect), Some((ox, oy))) = crate::mascot::effect_spec(&settings.pet, size) else { return Ok(()) };
    if effect == "none" {
        return Ok(());
    }
    close_fx(app);
    let ox = if facing < 0 { size - ox } else { ox };
    open_effect(app, &effect, (ox, oy), Some(facing))
}

/// `origin` is inside the mascot window; `dir` None aims toward open screen.
fn open_effect(app: &AppHandle, effect: &str, (ox, oy): (f64, f64), dir: Option<i32>) -> tauri::Result<()> {
    if effect == "none" {
        return Ok(());
    }
    let Some(mascot) = app.get_webview_window(MASCOT) else { return Ok(()) };
    let scale = mascot.scale_factor()?;
    let pos: LogicalPosition<f64> = mascot.outer_position()?.to_logical(scale);
    let (gx, gy) = (pos.x + ox, pos.y + oy);
    // Keep the overlay on the mascot's monitor ourselves (mutter would push it
    // back on-screen anyway, silently moving the effect away from the mascot),
    // aim toward the middle of the screen, and pass the true origin.
    let (fx_x, fx_y, dir) = match mascot.current_monitor()? {
        Some(m) => {
            let b = logical_bounds(&m);
            let x = (gx - FX_ORIGIN.0).clamp(b.x, (b.x + b.w - FX_W).max(b.x));
            let y = (gy - FX_ORIGIN.1).clamp(b.y, (b.y + b.h - FX_H).max(b.y));
            (x, y, dir.unwrap_or(if gx > b.x + b.w / 2.0 { -1 } else { 1 }))
        }
        None => (gx - FX_ORIGIN.0, gy - FX_ORIGIN.1, dir.unwrap_or(-1)),
    };
    let config = serde_json::json!({ "effect": effect, "x": gx - fx_x, "y": gy - fx_y, "dir": dir });
    let fx = WebviewWindowBuilder::new(app, FX, WebviewUrl::App("fx.html".into()))
        .title("DeskBuddy effect")
        .initialization_script(&format!("window.__FX__ = {config};"))
        .inner_size(FX_W, FX_H)
        .position(fx_x, fx_y)
        .resizable(true) // see create_mascot: non-resizable GTK windows ignore inner_size
        .decorations(false)
        .transparent(true)
        .shadow(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .visible_on_all_workspaces(true)
        .focused(false)
        .visible(false)
        .build()?;
    #[cfg(target_os = "linux")]
    linux::make_click_through(&fx);
    fx.show()
}

pub fn close_fx(app: &AppHandle) {
    if let Some(w) = app.get_webview_window(FX) {
        let _ = w.destroy();
    }
}

fn show_mascot_menu(app: &AppHandle, win: &WebviewWindow) {
    let paused = !app.state::<SettingsStore>().get().animation_enabled;
    let build = || -> tauri::Result<Menu<tauri::Wry>> {
        Menu::with_items(
            app,
            &[
                &MenuItem::with_id(app, "open", "Open", true, None::<&str>)?,
                &CheckMenuItem::with_id(app, "pause", "Pause animation", true, paused, None::<&str>)?,
                &MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?,
                &PredefinedMenuItem::separator(app)?,
                &MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?,
            ],
        )
    };
    match build().and_then(|menu| win.popup_menu(&menu)) {
        Ok(()) => {}
        Err(e) => eprintln!("deskbuddy: context menu failed: {e}"),
    }
}

/// App-wide menu handler (registered on the Builder).
pub fn on_menu_event(app: &AppHandle, event: MenuEvent) {
    match event.id().as_ref() {
        "open" => {
            let _ = show_panel(app, Some("todos"));
        }
        "settings" => {
            let _ = show_panel(app, Some("settings"));
        }
        "pause" => {
            let s = app.state::<SettingsStore>().update(|s| s.animation_enabled = !s.animation_enabled);
            let _ = app.emit_to(MASCOT, "animation-enabled", s.animation_enabled);
        }
        "quit" => {
            app.state::<SettingsStore>().flush();
            app.exit(0);
        }
        _ => {}
    }
}

pub const ICON_SIZES: std::ops::RangeInclusive<u32> = 48..=256;

/// Resize the mascot live; the page re-lays itself out on "mascot-relayout".
pub fn set_mascot_size(app: &AppHandle, size: u32) -> tauri::Result<()> {
    let Some(win) = app.get_webview_window(MASCOT) else { return Ok(()) };
    // Loosen the fixed-size hints first, or GTK clamps the resize to the old size.
    #[cfg(target_os = "linux")]
    if let Ok(gw) = win.gtk_window() {
        linux::pin_size(&gw, size as i32);
    }
    win.set_size(tauri::LogicalSize::new(size as f64, size as f64))?;
    #[cfg(target_os = "linux")]
    if let Ok(gw) = win.gtk_window() {
        linux::set_input_shape(&gw, size as i32);
    }
    win.emit_to(MASCOT, "mascot-relayout", size)
}

/// Show the current alarm effect for a few seconds (Settings preview).
pub fn preview_fx(app: &AppHandle) -> tauri::Result<()> {
    open_fx(app)?;
    let app = app.clone();
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_secs(4));
        if app.state::<crate::system::alarm::AlarmState>().current().is_none() {
            close_fx(&app);
        }
    });
    Ok(())
}

pub fn create_panel(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    let win = WebviewWindowBuilder::new(app, PANEL, WebviewUrl::App("panel.html".into()))
        .title("DeskBuddy")
        .inner_size(PANEL_W, PANEL_H)
        .resizable(false)
        .decorations(false)
        .transparent(true)
        .shadow(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .visible(false)
        .build()?;

    let handle = win.clone();
    win.on_window_event(move |event| match event {
        WindowEvent::CloseRequested { api, .. } => {
            api.prevent_close();
            let _ = handle.hide();
        }
        // Unpinned: clicking outside the panel hides it.
        WindowEvent::Focused(false) => {
            let panel = handle.clone();
            std::thread::spawn(move || {
                std::thread::sleep(PANEL_BLUR_GRACE);
                let keep = panel.app_handle().state::<SettingsStore>().get().panel_pinned
                    || PANEL_EDITING.load(Ordering::SeqCst)
                    || PANEL_DROPDOWN.load(Ordering::SeqCst)
                    || super::dialog::OPEN.load(Ordering::SeqCst)
                    || panel.is_focused().unwrap_or(true);
                if !keep {
                    let _ = panel.hide();
                }
            });
        }
        _ => {}
    });
    Ok(win)
}

fn panel(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    match app.get_webview_window(PANEL) {
        Some(w) => Ok(w),
        None => create_panel(app),
    }
}

pub fn toggle_panel(app: &AppHandle) -> tauri::Result<()> {
    let p = panel(app)?;
    if p.is_visible()? {
        // A pinned panel only closes with its × button.
        if app.state::<SettingsStore>().get().panel_pinned {
            p.set_focus()
        } else {
            p.hide()
        }
    } else {
        show_panel(app, None)
    }
}

pub fn show_panel(app: &AppHandle, view: Option<&str>) -> tauri::Result<()> {
    let p = panel(app)?;
    if let Some((x, y)) = anchor_near_mascot(app) {
        p.set_position(LogicalPosition::new(x, y))?;
    }
    p.show()?;
    p.set_focus()?;
    if let Some(view) = view {
        p.emit_to(PANEL, "navigate", view)?;
    }
    Ok(())
}

pub fn hide_panel(app: &AppHandle) -> tauri::Result<()> {
    panel(app)?.hide()
}

/// Place the panel above the mascot (or below if there is no room), right-aligned
/// with it, and clamped to the mascot's monitor.
fn anchor_near_mascot(app: &AppHandle) -> Option<(f64, f64)> {
    let mascot = app.get_webview_window(MASCOT)?;
    let scale = mascot.scale_factor().ok()?;
    let pos: LogicalPosition<f64> = mascot.outer_position().ok()?.to_logical(scale);
    let size = mascot.outer_size().ok()?.to_logical::<f64>(scale);
    let mon = logical_bounds(&mascot.current_monitor().ok()??);

    let m = Rect { x: pos.x, y: pos.y, w: size.width, h: size.height };
    let fits_above = m.y - PANEL_H - PANEL_GAP >= mon.y;
    let fits_below = m.y + m.h + PANEL_GAP + PANEL_H <= mon.y + mon.h;

    let (x, y) = if fits_above || fits_below {
        let y = if fits_above { m.y - PANEL_H - PANEL_GAP } else { m.y + m.h + PANEL_GAP };
        (m.x + m.w - PANEL_W, y)
    } else {
        // Not enough vertical room: sit beside the mascot instead.
        let left = m.x - PANEL_W - PANEL_GAP;
        let x = if left >= mon.x { left } else { m.x + m.w + PANEL_GAP };
        (x, m.y + m.h / 2.0 - PANEL_H / 2.0)
    };
    let x = x.clamp(mon.x, (mon.x + mon.w - PANEL_W).max(mon.x));
    let y = y.clamp(mon.y, (mon.y + mon.h - PANEL_H).max(mon.y));
    Some((x, y))
}

#[cfg(target_os = "linux")]
mod linux {
    use gtk::cairo::{RectangleInt, Region};
    use gtk::prelude::*;
    use std::cell::Cell;
    use std::rc::Rc;

    use std::time::{Duration, Instant};

    use gtk::gdk::EventMask;
    use gtk::glib::Propagation;
    use tauri::{AppHandle, Emitter, WebviewWindow};

    /// Clicks closer together than this count as one streak.
    const CLICK_STREAK_GAP: Duration = Duration::from_millis(450);
    /// The page hears about streaks up to this long (1 = single click, which
    /// wakes a sleeping mascot; 2 = double click; 3 = "clicks").
    const CLICK_STREAK_MAX: u32 = 3;
    /// How often the page hears where the pointer is on the mascot.
    const POINTER_EVERY: Duration = Duration::from_millis(60);

    use super::DRAG_THRESHOLD_PX;

    /// Handle mascot mouse input natively on the webview widget, before WebKit
    /// sees it. Press+move starts the WM's own move (with the real event
    /// timestamp, which is what mutter requires); press+release toggles the
    /// panel; right-click opens the menu.
    pub fn install_input(win: &WebviewWindow, app: AppHandle) {
        let Ok(gw) = win.gtk_window() else { return };
        let Some(target) = deepest_child(gw.upcast_ref()) else { return };
        target.add_events(
            EventMask::BUTTON_PRESS_MASK
                | EventMask::BUTTON_RELEASE_MASK
                | EventMask::POINTER_MOTION_MASK
                | EventMask::ENTER_NOTIFY_MASK
                | EventMask::LEAVE_NOTIFY_MASK,
        );
        let press: Rc<Cell<Option<(f64, f64)>>> = Rc::new(Cell::new(None));
        // (clicks in the current streak, time of the last one)
        let streak: Rc<Cell<(u32, Option<Instant>)>> = Rc::new(Cell::new((0, None)));

        let a = app.clone();
        target.connect_enter_notify_event(move |_, _| {
            let _ = a.emit_to(super::MASCOT, "mascot-hover", true);
            Propagation::Proceed
        });
        let a = app.clone();
        target.connect_leave_notify_event(move |_, ev| {
            // Inferior = moved onto a child window, not really leaving.
            if ev.detail() != gtk::gdk::NotifyType::Inferior {
                let _ = a.emit_to(super::MASCOT, "mascot-hover", false);
            }
            Propagation::Proceed
        });

        let (p, a, w) = (press.clone(), app.clone(), win.clone());
        target.connect_button_press_event(move |_, ev| {
            match ev.button() {
                1 if ev.event_type() == gtk::gdk::EventType::ButtonPress => p.set(Some(ev.root())),
                3 => {
                    p.set(None);
                    super::show_mascot_menu(&a, &w);
                }
                _ => {}
            }
            Propagation::Stop
        });

        let (p, g, a) = (press.clone(), gw.clone(), app.clone());
        let last_pointer: Cell<Option<Instant>> = Cell::new(None);
        target.connect_motion_notify_event(move |_, ev| {
            // Where on the pet the pointer rests (window px), for body-part
            // reactions; a few times a second is plenty.
            if p.get().is_none() && last_pointer.get().is_none_or(|t| t.elapsed() >= POINTER_EVERY) {
                last_pointer.set(Some(Instant::now()));
                let _ = a.emit_to(super::MASCOT, "mascot-pointer", ev.position());
            }
            if let Some((x0, y0)) = p.get() {
                let (x, y) = ev.root();
                if (x - x0).hypot(y - y0) > DRAG_THRESHOLD_PX {
                    p.set(None);
                    g.begin_move_drag(1, x as i32, y as i32, ev.time());
                    crate::system::gravity::drag_started(&a);
                }
            }
            Propagation::Stop
        });

        let p = press;
        target.connect_button_release_event(move |_, ev| {
            if ev.button() != 1 || p.take().is_none() {
                return Propagation::Stop;
            }
            let now = Instant::now();
            let (count, last) = streak.get();
            let count = match last {
                Some(t) if now.duration_since(t) < CLICK_STREAK_GAP => count + 1,
                _ => 1,
            };
            streak.set((count, Some(now)));
            // While an alarm rings, a click on the mascot silences it.
            if crate::system::alarm::stop(&app) {
                return Propagation::Stop;
            }
            // Only the first click of a streak toggles the panel; rapid
            // follow-up clicks play with the mascot instead.
            if count == 1 {
                let _ = super::toggle_panel(&app);
            }
            if count <= CLICK_STREAK_MAX {
                let _ = app.emit_to(super::MASCOT, "mascot-clicks", count);
            }
            Propagation::Stop
        });
    }

    /// Empty input region: every click goes to the windows underneath.
    pub fn make_click_through(win: &WebviewWindow) {
        let Ok(gw) = win.gtk_window() else { return };
        gw.set_skip_pager_hint(true);
        gw.set_skip_taskbar_hint(true);
        gw.set_accept_focus(false);
        gw.input_shape_combine_region(Some(&Region::create()));
    }

    fn deepest_child(w: &gtk::Widget) -> Option<gtk::Widget> {
        match w.downcast_ref::<gtk::Container>().and_then(|c| c.children().into_iter().next()) {
            Some(child) => deepest_child(&child).or(Some(child)),
            None => None,
        }
    }

    pub fn apply_mascot_hints(win: &WebviewWindow, size: i32) {
        let Ok(gw) = win.gtk_window() else { return };
        gw.set_skip_pager_hint(true);
        gw.set_skip_taskbar_hint(true);
        pin_size(&gw, size);
        set_input_shape(&gw, size);
    }

    /// min = max size hints: mutter then treats the window as fixed-size and
    /// won't edge-tile or maximize it when it is dragged against a screen edge.
    pub fn pin_size(gw: &gtk::ApplicationWindow, size: i32) {
        let geometry = gtk::gdk::Geometry::new(
            size, size, size, size, 0, 0, 0, 0, 0.0, 0.0, gtk::gdk::Gravity::NorthWest,
        );
        gw.set_geometry_hints(
            None::<&gtk::Widget>,
            Some(&geometry),
            gtk::gdk::WindowHints::MIN_SIZE | gtk::gdk::WindowHints::MAX_SIZE,
        );
    }

    /// Restrict the X11 input region to an ellipse around the mascot so clicks on
    /// the transparent corners fall through to whatever is underneath. This is
    /// a static shape (zero runtime cost) rather than per-pixel hit testing.
    pub fn set_input_shape(gw: &gtk::ApplicationWindow, size: i32) {
        let s = size as f64;
        let (cx, cy, rx, ry) = (s * 0.5, s * 0.55, s * 0.40, s * 0.45);
        let region = Region::create();
        let band = 2;
        let mut y = 0;
        while y < size {
            let dy = (y as f64 + band as f64 / 2.0 - cy) / ry;
            if dy.abs() < 1.0 {
                let half = rx * (1.0 - dy * dy).sqrt();
                let rect = RectangleInt::new((cx - half) as i32, y, (2.0 * half).ceil() as i32, band);
                let _ = region.union_rectangle(&rect);
            }
            y += band;
        }
        // Widget-level API: GTK stores the region and re-applies it on realize/map,
        // whereas a raw GdkWindow shape gets reset when the window is shown.
        gw.input_shape_combine_region(Some(&region));
    }
}
