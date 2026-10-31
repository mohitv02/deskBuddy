mod backup;
mod chat;
mod commands;
mod crypto;
mod db;
mod e2e;
mod host;
mod legacy;
mod mascot;
mod paths;
mod settings;
mod vault_store;
mod system;

use tauri::Manager;

use settings::SettingsStore;

/// Todos: encrypted with a keyring-held key (migrating an old plaintext file
/// first). Vault: starts locked; opened later with the master password.
fn open_databases(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let data = paths::data_dir();
    let todos_path = data.join("deskbuddy.db");
    if legacy::stash_if_plaintext(&todos_path, &data)? {
        eprintln!("deskbuddy: found an unencrypted database from an older version; encrypting it");
    }
    let (key, source) = system::keyring::todos_key(&data)?;
    if source == system::keyring::KeySource::File {
        eprintln!("deskbuddy: todos key is in {}, not the login keyring", data.join("todos.key").display());
    }
    let todos_db = match db::Db::open(&todos_path, &key) {
        Err(db::Error::WrongKey) => {
            // The key was lost (e.g. keyring reset). Keep the file for recovery
            // from a backup and start fresh rather than refusing to run.
            let aside = db::with_suffix(&todos_path, &format!(".unreadable-{}", db::now_ms()));
            eprintln!("deskbuddy: todos database cannot be opened with the stored key; moved to {}", aside.display());
            std::fs::rename(&todos_path, &aside)?;
            db::Db::open(&todos_path, &key)?
        }
        other => other?,
    };
    let old = legacy::path(&data);
    if old.is_file() && std::fs::metadata(&old).map(|m| m.len() > 0).unwrap_or(false) {
        match todos_db.with(|c| legacy::import_todos(c, &old)) {
            Ok(n) if n > 0 => eprintln!("deskbuddy: encrypted {n} todos from the previous database"),
            Ok(_) => {}
            Err(e) => eprintln!("deskbuddy: could not import old todos: {e}"),
        }
    }
    app.manage(todos_db);
    app.manage(commands::TodosKey(key));
    app.manage(vault_store::VaultStore::new(&data));
    Ok(())
}

pub fn run() {
    let Some(listener) = system::single_instance::acquire() else {
        eprintln!("deskbuddy: already running; asked it to show the panel");
        return;
    };
    tauri::Builder::default()
        .manage(SettingsStore::load())
        .manage(system::alarm::AlarmState::default())
        .manage(system::hotkey::HotkeyState::default())
        .manage(chat::ChatClient::default())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .on_menu_event(system::window::on_menu_event)
        .setup(|app| {
            let handle = app.handle().clone();
            mascot::init(app.path().resource_dir().ok());
            open_databases(app)?;
            let s = app.state::<SettingsStore>().get();
            system::window::create_mascot(&handle, &s)?;
            system::window::create_panel(&handle)?;
            if let Some(listener) = listener {
                system::single_instance::serve(handle.clone(), listener);
            }
            system::alarm::spawn_scheduler(handle.clone());
            chat::spawn(handle.clone());
            system::autolock::spawn(handle.clone());
            system::hotkey::init(&handle);
            system::autostart::reconcile(s.autostart);
            system::pointer::spawn(handle.clone());
            system::fullscreen::spawn_watcher(handle);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::get_settings,
            commands::settings_info,
            commands::update_settings,
            commands::preview_effect,
            commands::set_animation_enabled,
            commands::is_fullscreen,
            commands::toggle_panel,
            commands::show_panel,
            commands::hide_panel,
            commands::set_panel_editing,
            commands::set_panel_dropdown,
            commands::quit_app,
            commands::custom_mascot,
            commands::list_pets,
            commands::preview_pet_state,
            commands::copy_text,
            commands::vault_search,
            commands::vault_get,
            commands::vault_create,
            commands::vault_update,
            commands::vault_delete,
            commands::vault_tags,
            commands::vault_reveal_secret,
            commands::vault_copy_secret,
            commands::vault_status,
            commands::vault_setup,
            commands::vault_unlock,
            commands::vault_lock,
            commands::vault_change_password,
            commands::backup_export,
            commands::backup_import,
            commands::list_todos,
            commands::create_todo,
            commands::update_todo,
            commands::set_todo_status,
            commands::delete_todo,
            commands::reorder_todos,
            commands::chat_status,
            commands::chat_identity,
            commands::team_create,
            commands::team_join,
            commands::team_invite,
            commands::team_address,
            commands::team_leave,
            commands::team_rotate,
            commands::link_request,
            commands::link_respond,
            commands::archive_release,
            commands::archive_lock,
            commands::chat_discover,
            commands::chat_host_status,
            commands::chat_host_save,
            commands::chat_conversations,
            commands::chat_open,
            commands::chat_retry,
            commands::chat_set_reaction,
            commands::chat_list,
            commands::chat_pinned,
            commands::chat_search,
            commands::chat_send,
            commands::chat_edit,
            commands::chat_pin,
            commands::chat_delete,
            commands::chat_to_todo,
            commands::alarm_current,
            commands::alarm_stop,
            commands::alarm_snooze,
            commands::alarm_complete,
            commands::alarm_test,
        ])
        .run(tauri::generate_context!())
        .expect("error while running DeskBuddy");
}
