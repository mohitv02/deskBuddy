//! Tauri command handlers: thin glue between the UI and the backend modules.

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, State};

use zeroize::Zeroizing;

use crate::db::{self, conversations, messages, todos, vault, Db};
use crate::vault_store::{self, VaultStore};
use crate::{backup, chat, crypto, legacy, paths};
use crate::settings::{Settings, SettingsStore};
use crate::system::{alarm, autolock, autostart, clipboard, dialog, fullscreen, hotkey, window};

type CmdResult<T> = Result<T, String>;

fn err(e: impl std::fmt::Display) -> String {
    e.to_string()
}

#[tauri::command]
pub fn get_settings(store: State<'_, SettingsStore>) -> Settings {
    store.get()
}

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SettingsPatch {
    autostart: Option<bool>,
    hotkey: Option<String>,
    icon_size: Option<u32>,
    animation_enabled: Option<bool>,
    auto_lock_minutes: Option<u32>,
    alarm_effect: Option<String>,
    pet: Option<String>,
    sleep_after_seconds: Option<u32>,
    panel_pinned: Option<bool>,
    chat_server: Option<String>,
    chat_name: Option<String>,
    chat_ip: Option<String>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SettingsInfo {
    settings: Settings,
    /// Why the saved shortcut isn't active, if it isn't.
    hotkey_error: Option<String>,
    data_dir: String,
    config_dir: String,
    version: String,
}

#[tauri::command]
pub fn settings_info(app: AppHandle, store: State<'_, SettingsStore>) -> SettingsInfo {
    SettingsInfo {
        settings: store.get(),
        hotkey_error: app.state::<hotkey::HotkeyState>().0.lock().unwrap().clone(),
        data_dir: paths::data_dir().display().to_string(),
        config_dir: paths::config_dir().display().to_string(),
        version: app.package_info().version.to_string(),
    }
}

/// Apply and persist changed settings, with their side effects.
#[tauri::command]
pub fn update_settings(app: AppHandle, store: State<'_, SettingsStore>, patch: SettingsPatch) -> CmdResult<Settings> {
    if let Some(accel) = patch.hotkey {
        hotkey::change(&app, accel.trim())?;
    }
    if let Some(on) = patch.autostart {
        autostart::set(on).map_err(|e| format!("couldn't update the autostart entry: {e}"))?;
        store.update(|s| s.autostart = on);
    }
    if let Some(size) = patch.icon_size {
        if !window::ICON_SIZES.contains(&size) {
            return Err(format!("icon size must be {}–{} px", window::ICON_SIZES.start(), window::ICON_SIZES.end()));
        }
        store.update(|s| s.icon_size = size);
        window::set_mascot_size(&app, size).map_err(err)?;
    }
    if let Some(on) = patch.animation_enabled {
        store.update(|s| s.animation_enabled = on);
        app.emit_to(window::MASCOT, "animation-enabled", on).map_err(err)?;
    }
    if let Some(minutes) = patch.auto_lock_minutes {
        if minutes > 24 * 60 {
            return Err("auto-lock can be at most 24 hours".into());
        }
        store.update(|s| s.auto_lock_minutes = minutes);
    }
    if let Some(effect) = patch.alarm_effect {
        if effect != "auto" && !crate::mascot::EFFECTS.contains(&effect.as_str()) {
            return Err(format!("unknown effect {effect}"));
        }
        store.update(|s| s.alarm_effect = effect);
    }
    if let Some(seconds) = patch.sleep_after_seconds {
        if seconds > 24 * 3600 {
            return Err("sleep can be at most 24 hours away".into());
        }
        store.update(|s| s.sleep_after_seconds = seconds);
        app.emit_to(window::MASCOT, "mascot-sleep-after", seconds).map_err(err)?;
    }
    if let Some(on) = patch.panel_pinned {
        store.update(|s| s.panel_pinned = on);
    }
    if patch.chat_server.is_some() || patch.chat_name.is_some() || patch.chat_ip.is_some() {
        let server = patch.chat_server.map(|v| v.trim().to_string());
        if let Some(v) = &server {
            chat::ws_url(v)?;
        }
        let name = patch.chat_name.map(|v| v.trim().to_string());
        if name.as_ref().is_some_and(|v| v.chars().count() > chat::MAX_NAME_CHARS) {
            return Err(format!("name can be at most {} characters", chat::MAX_NAME_CHARS));
        }
        let ip = match patch.chat_ip.map(|v| v.trim().to_string()) {
            Some(v) if !v.is_empty() => Some(chat::parse_ip(&v).ok_or_else(|| format!("{v} is not an IP address"))?),
            other => other,
        };
        store.update(|s| {
            if let Some(v) = server {
                s.chat_server = v;
            }
            if let Some(v) = name {
                s.chat_name = v;
            }
            if let Some(v) = ip {
                s.chat_ip = v;
            }
        });
        app.state::<chat::ChatClient>().reconfigure();
    }
    if let Some(pet) = patch.pet {
        if !crate::mascot::is_known(&pet) {
            return Err(format!("unknown pet {pet}"));
        }
        store.update(|s| s.pet = pet);
        // The mascot page fades the old pet out and reloads with the new one.
        app.emit_to(window::MASCOT, "mascot-pet-changed", ()).map_err(err)?;
    }
    Ok(store.get())
}

#[tauri::command]
pub fn preview_effect(app: AppHandle) -> CmdResult<()> {
    window::preview_fx(&app).map_err(err)
}

#[tauri::command]
pub fn set_animation_enabled(app: AppHandle, store: State<'_, SettingsStore>, enabled: bool) -> CmdResult<()> {
    store.update(|s| s.animation_enabled = enabled);
    app.emit_to(window::MASCOT, "animation-enabled", enabled).map_err(err)
}

#[tauri::command]
pub fn is_fullscreen() -> bool {
    fullscreen::is_fullscreen()
}

#[tauri::command]
pub fn toggle_panel(app: AppHandle) -> CmdResult<()> {
    window::toggle_panel(&app).map_err(err)
}

#[tauri::command]
pub fn show_panel(app: AppHandle, view: Option<String>) -> CmdResult<()> {
    window::show_panel(&app, view.as_deref()).map_err(err)
}

#[tauri::command]
pub fn hide_panel(app: AppHandle) -> CmdResult<()> {
    window::hide_panel(&app).map_err(err)
}

/// An editor sheet is open in the panel: don't auto-hide it on focus loss.
#[tauri::command]
pub fn set_panel_editing(open: bool) {
    window::PANEL_EDITING.store(open, std::sync::atomic::Ordering::SeqCst);
}

/// A <select> dropdown is open in the panel: don't auto-hide it on focus loss.
#[tauri::command]
pub fn set_panel_dropdown(open: bool) {
    window::PANEL_DROPDOWN.store(open, std::sync::atomic::Ordering::SeqCst);
}

#[tauri::command]
pub fn quit_app(app: AppHandle, store: State<'_, SettingsStore>) {
    store.flush();
    app.exit(0);
}

#[tauri::command]
pub fn custom_mascot(store: State<'_, SettingsStore>) -> Option<crate::mascot::CustomMascot> {
    crate::mascot::load(&store.get().pet)
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PetList {
    /// The pet on screen ("" in settings resolved to custom or classic).
    active: String,
    pets: Vec<crate::mascot::PetInfo>,
}

#[tauri::command]
pub fn list_pets(store: State<'_, SettingsStore>) -> PetList {
    PetList { active: crate::mascot::resolve(&store.get().pet), pets: crate::mascot::list() }
}

/// Play one state (or `variant:<i>`) on the mascot, for the settings mapping.
#[tauri::command]
pub fn preview_pet_state(app: AppHandle, state: String) -> CmdResult<()> {
    app.emit_to(window::MASCOT, "mascot-preview", state).map_err(err)
}

/// Copy non-secret text (commands, ssh lines). `sensitive` clears it after 30 s.
#[tauri::command]
pub fn copy_text(app: AppHandle, text: String, sensitive: bool) -> CmdResult<()> {
    clipboard::copy(&app, text, sensitive.then_some(clipboard::SECRET_CLEAR_AFTER)).map_err(err)
}

#[tauri::command]
pub fn list_todos(db: State<'_, Db>) -> CmdResult<Vec<todos::Todo>> {
    db.with(|c| todos::list(c)).map_err(err)
}

#[tauri::command]
pub fn create_todo(app: AppHandle, db: State<'_, Db>, input: todos::TodoInput) -> CmdResult<todos::Todo> {
    let todo = db.with(|c| todos::create(c, &input)).map_err(err)?;
    let _ = app.emit_to(window::MASCOT, "mascot-mood", "added");
    Ok(todo)
}

#[tauri::command]
pub fn update_todo(app: AppHandle, db: State<'_, Db>, id: i64, input: todos::TodoInput) -> CmdResult<todos::Todo> {
    let (before, after) = db.with(|c| Ok((todos::get(c, id)?, todos::update(c, id, &input)?))).map_err(err)?;
    react_to_status(&app, &db, &before, &after);
    Ok(after)
}

#[tauri::command]
pub fn set_todo_status(app: AppHandle, db: State<'_, Db>, id: i64, status: todos::Status) -> CmdResult<todos::Todo> {
    let (before, after) = db.with(|c| Ok((todos::get(c, id)?, todos::set_status(c, id, status)?))).map_err(err)?;
    react_to_status(&app, &db, &before, &after);
    Ok(after)
}

#[tauri::command]
pub fn delete_todo(app: AppHandle, db: State<'_, Db>, id: i64) -> CmdResult<()> {
    db.with(|c| todos::delete(c, id)).map_err(err)?;
    let _ = app.emit_to(window::MASCOT, "mascot-mood", "deleted");
    Ok(())
}

#[tauri::command]
pub fn reorder_todos(db: State<'_, Db>, ids: Vec<i64>) -> CmdResult<()> {
    db.with(|c| todos::reorder(c, &ids)).map_err(err)
}

#[tauri::command]
pub fn chat_status(client: State<'_, chat::ChatClient>) -> chat::Status {
    client.status()
}

#[tauri::command]
pub fn chat_conversations(db: State<'_, Db>) -> CmdResult<Vec<conversations::Conversation>> {
    db.with(|c| conversations::list(c)).map_err(err)
}

/// Start (or reopen) a chat with an IP address or a name.
#[tauri::command]
pub fn chat_open(db: State<'_, Db>, client: State<'_, chat::ChatClient>, target: String) -> CmdResult<chat::OpenResult> {
    match client.resolve(&target)? {
        Ok(user) => {
            let conversation = db.with(|c| conversations::open_remote(c, &user.ip, &user.name)).map_err(err)?;
            Ok(chat::OpenResult::Opened { conversation })
        }
        Err(users) => Ok(chat::OpenResult::Choose { users }),
    }
}

#[tauri::command]
pub fn chat_list(db: State<'_, Db>, conversation: i64, before: Option<i64>, limit: u32) -> CmdResult<Vec<messages::Message>> {
    db.with(|c| messages::list(c, conversation, before, limit)).map_err(err)
}

#[tauri::command]
pub fn chat_pinned(db: State<'_, Db>, conversation: i64) -> CmdResult<Vec<messages::Message>> {
    db.with(|c| messages::pinned(c, conversation)).map_err(err)
}

#[tauri::command]
pub fn chat_search(db: State<'_, Db>, conversation: i64, text: String) -> CmdResult<Vec<messages::Message>> {
    db.with(|c| messages::search(c, conversation, &text, messages::MAX_PAGE)).map_err(err)
}

/// Notes to self are stored; chat messages are stored as pending and handed
/// to the chat connection (sent now if online, else on reconnect).
#[tauri::command]
pub fn chat_send(db: State<'_, Db>, client: State<'_, chat::ChatClient>, conversation: i64, body: String) -> CmdResult<messages::Message> {
    let conv = db.with(|c| conversations::get(c, conversation)).map_err(err)?;
    let remote = conv.is_remote();
    let Some(peer) = conv.peer_ip.filter(|_| remote) else {
        return db.with(|c| messages::create(c, conversation, &body)).map_err(err);
    };
    let message = db.with(|c| messages::create_outgoing(c, conversation, &body, &chat::new_client_msg_id())).map_err(err)?;
    client.send(&peer, &message);
    Ok(message)
}

/// How the pet reacts to this person's messages ("" default, "none", or a pet state).
#[tauri::command]
pub fn chat_set_reaction(db: State<'_, Db>, conversation: i64, reaction: String) -> CmdResult<conversations::Conversation> {
    db.with(|c| conversations::set_reaction(c, conversation, reaction.trim())).map_err(err)
}

/// Send a failed chat message again.
#[tauri::command]
pub fn chat_retry(db: State<'_, Db>, client: State<'_, chat::ChatClient>, id: i64) -> CmdResult<messages::Message> {
    let (message, conv) = db
        .with(|c| {
            let m = messages::set_state(c, id, "pending")?;
            Ok((m.clone(), conversations::get(c, m.conversation_id)?))
        })
        .map_err(err)?;
    if let Some(peer) = &conv.peer_ip {
        client.send(peer, &message);
    }
    Ok(message)
}

#[tauri::command]
pub fn chat_edit(db: State<'_, Db>, id: i64, body: String) -> CmdResult<messages::Message> {
    db.with(|c| messages::update_body(c, id, &body)).map_err(err)
}

#[tauri::command]
pub fn chat_pin(db: State<'_, Db>, id: i64, pinned: bool) -> CmdResult<messages::Message> {
    db.with(|c| messages::set_pinned(c, id, pinned)).map_err(err)
}

#[tauri::command]
pub fn chat_delete(db: State<'_, Db>, id: i64) -> CmdResult<()> {
    db.with(|c| messages::delete(c, id)).map_err(err)
}

#[tauri::command]
pub fn chat_to_todo(app: AppHandle, db: State<'_, Db>, id: i64, input: todos::TodoInput) -> CmdResult<messages::Message> {
    let (message, _) = db.with(|c| messages::to_todo(c, id, &input)).map_err(err)?;
    let _ = app.emit_to(window::MASCOT, "mascot-mood", "added");
    Ok(message)
}

/// Mascot reactions to a status change: started, done, or the last one done.
fn react_to_status(app: &AppHandle, db: &Db, before: &todos::Todo, after: &todos::Todo) {
    if before.status != todos::Status::Done && after.status == todos::Status::Done {
        alarm::stop_for(app, after.id);
        let open = db.with(|c| todos::list(c)).map(|all| all.iter().filter(|t| t.status != todos::Status::Done).count());
        if open.map_or(false, |n| n == 0) {
            let _ = app.emit_to(window::MASCOT, "mascot-mood", "allDone");
        } else {
            let _ = app.emit_to(window::MASCOT, "mascot-happy", ());
        }
    } else if before.status != todos::Status::InProgress && after.status == todos::Status::InProgress {
        let _ = app.emit_to(window::MASCOT, "mascot-mood", "started");
    }
}

#[tauri::command]
pub fn alarm_current(state: State<'_, alarm::AlarmState>) -> Option<alarm::AlarmInfo> {
    state.current()
}

#[tauri::command]
pub fn alarm_stop(app: AppHandle) {
    alarm::stop(&app);
}

#[tauri::command]
pub fn alarm_snooze(app: AppHandle, id: i64) -> CmdResult<()> {
    alarm::snooze(&app, id)
}

#[tauri::command]
pub fn alarm_complete(app: AppHandle, id: i64) -> CmdResult<()> {
    alarm::complete(&app, id)
}

/// Ring an alarm right now for a todo (used by "Test alarm" in the editor).
#[tauri::command]
pub fn alarm_test(app: AppHandle, db: State<'_, Db>, id: i64) -> CmdResult<()> {
    let todo = db.with(|c| todos::get(c, id)).map_err(err)?;
    alarm::ring(&app, &todo);
    Ok(())
}

#[tauri::command]
pub fn vault_search(store: State<'_, VaultStore>, query: vault::SearchQuery) -> CmdResult<Vec<vault::Entry>> {
    store.with(|c| vault::search(c, &query)).map_err(err)
}

#[tauri::command]
pub fn vault_get(store: State<'_, VaultStore>, id: i64) -> CmdResult<vault::Entry> {
    store.with(|c| vault::get(c, id)).map_err(err)
}

#[tauri::command]
pub fn vault_create(store: State<'_, VaultStore>, input: vault::EntryInput) -> CmdResult<vault::Entry> {
    store.with(|c| vault::create(c, &input)).map_err(err)
}

#[tauri::command]
pub fn vault_update(store: State<'_, VaultStore>, id: i64, input: vault::EntryInput) -> CmdResult<vault::Entry> {
    store.with(|c| vault::update(c, id, &input)).map_err(err)
}

#[tauri::command]
pub fn vault_delete(store: State<'_, VaultStore>, id: i64) -> CmdResult<()> {
    store.with(|c| vault::delete(c, id)).map_err(err)
}

#[tauri::command]
pub fn vault_tags(store: State<'_, VaultStore>) -> CmdResult<Vec<vault::TagCount>> {
    store.with(|c| vault::tags(c)).map_err(err)
}

/// Only called when the user clicks "reveal"; the UI re-masks it on a timer.
#[tauri::command]
pub fn vault_reveal_secret(store: State<'_, VaultStore>, id: i64) -> CmdResult<Option<String>> {
    store.with(|c| vault::get_secret(c, id)).map(|s| s.map(|s| s.0)).map_err(err)
}

/// Copies the secret without it ever passing through the UI; auto-clears in 30 s.
#[tauri::command]
pub fn vault_copy_secret(app: AppHandle, store: State<'_, VaultStore>, id: i64) -> CmdResult<()> {
    let secret = store.with(|c| vault::get_secret(c, id)).map_err(err)?.ok_or("this entry has no secret")?;
    clipboard::copy(&app, secret.0, Some(clipboard::SECRET_CLEAR_AFTER)).map_err(err)
}

// ---------------------------------------------------------------------------
// Vault lock / master password / backups
// ---------------------------------------------------------------------------

/// The todos database key (from the login keyring), needed to re-key imports.
pub struct TodosKey(pub crypto::Key);

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct VaultStatus {
    state: vault_store::Status,
    /// Unencrypted entries from an older version waiting to be imported.
    legacy_entries: i64,
    auto_lock_minutes: u32,
}

#[tauri::command]
pub fn vault_status(store: State<'_, VaultStore>, settings: State<'_, SettingsStore>) -> VaultStatus {
    VaultStatus {
        state: store.status(),
        legacy_entries: legacy::count_vault_entries(&legacy::path(&paths::data_dir())),
        auto_lock_minutes: settings.get().auto_lock_minutes,
    }
}

/// Argon2id takes ~0.5 s by design; never run it on the UI/IPC thread.
async fn blocking<T: Send + 'static>(f: impl FnOnce() -> db::Result<T> + Send + 'static) -> CmdResult<T> {
    tauri::async_runtime::spawn_blocking(f).await.map_err(err)?.map_err(err)
}

#[tauri::command]
pub async fn vault_setup(app: AppHandle, password: String) -> CmdResult<()> {
    let password = Zeroizing::new(password);
    blocking(move || {
        let store = app.state::<VaultStore>();
        store.setup(&password)?;
        let old = legacy::path(&paths::data_dir());
        if old.exists() {
            let n = store.with(|c| legacy::import_vault(c, &old))?;
            eprintln!("deskbuddy: encrypted {n} vault entries from the previous unencrypted database");
        }
        Ok(())
    })
    .await
}

#[tauri::command]
pub async fn vault_unlock(app: AppHandle, password: String) -> CmdResult<()> {
    let password = Zeroizing::new(password);
    blocking(move || {
        let result = app.state::<VaultStore>().unlock(&password);
        if matches!(result, Err(db::Error::WrongKey)) {
            // On top of Argon2's cost: slow down guessing through the UI.
            std::thread::sleep(std::time::Duration::from_millis(800));
            return Err(db::Error::Invalid("wrong master password".into()));
        }
        result
    })
    .await
}

#[tauri::command]
pub fn vault_lock(app: AppHandle) {
    autolock::lock(&app);
}

#[tauri::command]
pub async fn vault_change_password(app: AppHandle, old: String, new: String) -> CmdResult<()> {
    let (old, new) = (Zeroizing::new(old), Zeroizing::new(new));
    blocking(move || {
        app.state::<VaultStore>().change_password(&old, &new).map_err(|e| match e {
            db::Error::WrongKey => db::Error::Invalid("current master password is wrong".into()),
            e => e,
        })
    })
    .await
}

/// Ask where to save, then write an encrypted backup. `None` = cancelled.
#[tauri::command]
pub async fn backup_export(app: AppHandle, password: String) -> CmdResult<Option<(String, backup::Summary)>> {
    let password = Zeroizing::new(password);
    crypto::check_new_password(&password)?;
    blocking(move || {
        let date = chrono::Local::now().format("%Y-%m-%d").to_string();
        let mode = dialog::Mode::Save { suggested_name: format!("deskbuddy-{date}.{}", backup::EXTENSION) };
        let Some(dest) = dialog::choose_backup_file(&app, "Export encrypted backup", mode) else { return Ok(None) };
        let summary = backup::export(
            &paths::data_dir(),
            &app.state::<Db>(),
            &app.state::<VaultStore>(),
            &dest,
            &password,
            crypto::KdfParams::DEFAULT,
        )?;
        Ok(Some((dest.display().to_string(), summary)))
    })
    .await
}

/// Ask for a backup file, then replace all todos and vault entries with it.
#[tauri::command]
pub async fn backup_import(app: AppHandle, password: String) -> CmdResult<Option<backup::Summary>> {
    let password = Zeroizing::new(password);
    let result = blocking({
        let app = app.clone();
        move || {
            let Some(src) = dialog::choose_backup_file(&app, "Import encrypted backup", dialog::Mode::Open) else { return Ok(None) };
            let summary = backup::import(
                &paths::data_dir(),
                &app.state::<Db>(),
                &app.state::<TodosKey>().0,
                &app.state::<VaultStore>(),
                &src,
                &password,
            )?;
            Ok(Some(summary))
        }
    })
    .await?;
    let _ = app.emit("todos-changed", ());
    Ok(result)
}
