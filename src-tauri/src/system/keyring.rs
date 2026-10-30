//! The todos database key lives in the login keyring (GNOME Keyring via the
//! Secret Service), which is unlocked when you log in — so todos and alarms
//! work without a password prompt while the file stays encrypted at rest.
//! If no Secret Service is available, the key falls back to a 0600 key file.

use std::path::Path;

use crate::crypto::{self, Key};

const SERVICE: &str = "DeskBuddy";
const ACCOUNT: &str = "todos-database-key";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KeySource {
    Keyring,
    File,
}

fn file_key(path: &Path) -> Result<Key, String> {
    if let Ok(text) = std::fs::read_to_string(path) {
        return crypto::key_from_hex(&text).ok_or_else(|| format!("{} is corrupt", path.display()));
    }
    let key = crypto::random_key().map_err(|e| e.to_string())?;
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    }
    let hexed = zeroize::Zeroizing::new(crypto::hex(key.as_ref()));
    std::fs::write(path, hexed.as_bytes()).map_err(|e| e.to_string())?;
    crate::db::restrict_file(path).map_err(|e| e.to_string())?;
    Ok(key)
}

/// Load the key, creating it on first run.
pub fn todos_key(data_dir: &Path) -> Result<(Key, KeySource), String> {
    let fallback = data_dir.join("todos.key");
    if fallback.exists() {
        return file_key(&fallback).map(|k| (k, KeySource::File));
    }
    let entry = match keyring::Entry::new(SERVICE, ACCOUNT) {
        Ok(e) => e,
        Err(e) => {
            eprintln!("deskbuddy: login keyring unavailable ({e}); storing the todos key in a 0600 file");
            return file_key(&fallback).map(|k| (k, KeySource::File));
        }
    };
    match entry.get_password() {
        Ok(text) => {
            let text = zeroize::Zeroizing::new(text);
            crypto::key_from_hex(&text).map(|k| (k, KeySource::Keyring)).ok_or_else(|| "the keyring entry for DeskBuddy is corrupt".into())
        }
        Err(keyring::Error::NoEntry) => {
            let key = crypto::random_key().map_err(|e| e.to_string())?;
            let hexed = zeroize::Zeroizing::new(crypto::hex(key.as_ref()));
            match entry.set_password(&hexed) {
                Ok(()) => Ok((key, KeySource::Keyring)),
                Err(e) => {
                    eprintln!("deskbuddy: could not save to the login keyring ({e}); using a 0600 key file");
                    file_key(&fallback).map(|k| (k, KeySource::File))
                }
            }
        }
        Err(e) => {
            eprintln!("deskbuddy: login keyring error ({e}); using a 0600 key file");
            file_key(&fallback).map(|k| (k, KeySource::File))
        }
    }
}
