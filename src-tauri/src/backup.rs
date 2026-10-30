//! Encrypted backup export/import (todos + vault in one `.dbkp` file).
//!
//! Export: both databases are copied with `sqlcipher_export` into temporary
//! files encrypted with Argon2id(backup password, fresh salt), then packed
//! into the container format in `crypto`. Import: unpack, open each copy with
//! the backup password (SQLCipher's HMAC rejects a wrong password or tampered
//! data), re-encrypt each under the live keys, and swap them in. The previous
//! files are kept as `*.pre-import`.

use std::path::{Path, PathBuf};

use rusqlite::Connection;
use serde::Serialize;

use crate::crypto::{self, BackupFile, BackupHeader, Key, KdfParams, SALT_LEN};
use crate::db::{self, migrations, vault, Db, Error, Result};
#[cfg(test)]
use crate::db::todos;
use crate::vault_store::VaultStore;

pub const EXTENSION: &str = "dbkp";

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Summary {
    pub todos: i64,
    pub vault_entries: i64,
}

struct TempDir(PathBuf);

impl TempDir {
    fn new(data_dir: &Path) -> Result<Self> {
        let dir = data_dir.join(format!(".backup-{}", crypto::hex(&crypto::random_bytes::<8>()?)));
        std::fs::create_dir_all(&dir)?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o700))?;
        }
        Ok(TempDir(dir))
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn count(conn: &Connection, table: &str) -> Result<i64> {
    Ok(conn.query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |r| r.get(0))?)
}

pub fn export(data_dir: &Path, todos_db: &Db, store: &VaultStore, dest: &Path, password: &str, params: KdfParams) -> Result<Summary> {
    crypto::check_new_password(password).map_err(Error::Invalid)?;
    let salt = crypto::random_bytes::<SALT_LEN>()?;
    let key = crypto::derive_key(password, &salt, params)?;
    let tmp = TempDir::new(data_dir)?;
    let vault_copy = tmp.0.join("vault.db");
    let todos_copy = tmp.0.join("todos.db");

    let vault_entries = store.with(|c| {
        db::export_to(c, &vault_copy, &key)?;
        vault::count(c)
    })?;
    let todo_count = todos_db.with(|c| {
        db::export_to(c, &todos_copy, &key)?;
        count(c, "todos")
    })?;

    let vault_bytes = std::fs::read(&vault_copy)?;
    let todos_bytes = std::fs::read(&todos_copy)?;
    let header = BackupHeader {
        version: 1,
        salt: crypto::hex(&salt),
        kdf: params,
        created_at: db::now_ms(),
        files: vec![
            BackupFile { name: "vault.db".into(), size: vault_bytes.len() as u64 },
            BackupFile { name: "todos.db".into(), size: todos_bytes.len() as u64 },
        ],
    };
    let partial = db::with_suffix(dest, ".partial");
    {
        let mut out = std::io::BufWriter::new(std::fs::File::create(&partial)?);
        crypto::write_backup(&mut out, &header, &[&vault_bytes, &todos_bytes])?;
    }
    db::restrict_file(&partial)?;
    std::fs::rename(&partial, dest)?;
    Ok(Summary { todos: todo_count, vault_entries })
}

/// Opens a copy from the backup, verifies it, upgrades its schema, and
/// re-encrypts it under `live_key` (in place).
fn prepare(path: &Path, backup_key: &Key, live_key: &Key, list: &[&str], table: &str) -> Result<i64> {
    let conn = Connection::open(path)?;
    db::apply_key(&conn, backup_key)?;
    let problems: Vec<String> = {
        let mut stmt = conn.prepare("PRAGMA cipher_integrity_check")?;
        let rows = stmt.query_map([], |r| r.get::<_, String>(0))?;
        rows.collect::<rusqlite::Result<_>>()?
    };
    if !problems.is_empty() {
        return Err(Error::Invalid("the backup is damaged (integrity check failed)".into()));
    }
    migrations::run(&conn, list)?;
    let n = count(&conn, table)?;
    db::rekey(&conn, live_key)?;
    Ok(n)
}

pub fn import(data_dir: &Path, todos_db: &Db, todos_key: &Key, store: &VaultStore, src: &Path, password: &str) -> Result<Summary> {
    let (header, files) = crypto::read_backup(&mut std::io::BufReader::new(std::fs::File::open(src)?))?;
    let key = crypto::derive_key(password, &header.salt_bytes()?, header.kdf)?;
    let tmp = TempDir::new(data_dir)?;
    let mut vault_copy = None;
    let mut todos_copy = None;
    for (meta, bytes) in header.files.iter().zip(&files) {
        let target = match meta.name.as_str() {
            "vault.db" => &mut vault_copy,
            "todos.db" => &mut todos_copy,
            _ => continue,
        };
        let path = tmp.0.join(&meta.name);
        std::fs::write(&path, bytes)?;
        db::restrict_file(&path)?;
        *target = Some(path);
    }
    let (Some(vault_copy), Some(todos_copy)) = (vault_copy, todos_copy) else {
        return Err(Error::Invalid("the backup is missing data".into()));
    };

    // Verify and re-key both before touching the live files.
    let vault_entries = store
        .with_key(|_, live| prepare(&vault_copy, &key, live, migrations::VAULT, "vault_entries"))
        .map_err(|e| if matches!(e, Error::WrongKey) { Error::Invalid("wrong backup password".into()) } else { e })?;
    let todo_count = prepare(&todos_copy, &key, todos_key, migrations::TODOS, "todos")?;

    store.replace_with(&vault_copy)?;
    todos_db.replace_with(&todos_copy, todos_key)?;
    Ok(Summary { todos: todo_count, vault_entries })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::vault::{EntryInput, Fields, Kind, SearchQuery, Secret, SecretChange};

    fn setup() -> (PathBuf, Db, Key, VaultStore) {
        let dir = std::env::temp_dir().join(format!("deskbuddy-backup-{}", crypto::hex(&crypto::random_bytes::<6>().unwrap())));
        std::fs::create_dir_all(&dir).unwrap();
        let key = crypto::random_key().unwrap();
        let todos_db = Db::open(&dir.join("deskbuddy.db"), &key).unwrap();
        let store = VaultStore::with_params(&dir, KdfParams::FAST);
        store.setup("master password").unwrap();
        (dir, todos_db, key, store)
    }

    fn add(store: &VaultStore, title: &str, secret: &str) {
        store
            .with(|c| {
                vault::create(
                    c,
                    &EntryInput {
                        kind: Kind::Password,
                        title: title.into(),
                        tags: vec![],
                        body: String::new(),
                        fields: Fields::default(),
                        secret: SecretChange::Set(Secret(secret.into())),
                    },
                )
            })
            .unwrap();
    }

    #[test]
    fn export_import_roundtrip_restores_everything() {
        let (dir, todos_db, key, store) = setup();
        add(&store, "Email", "mail-secret-42");
        todos_db.with(|c| todos::create(c, &todos::TodoInput { title: "backup me".into(), ..Default::default() })).unwrap();
        let file = dir.join("b.dbkp");
        let s = export(&dir, &todos_db, &store, &file, "backup password", KdfParams::FAST).unwrap();
        assert_eq!((s.todos, s.vault_entries), (1, 1));

        let raw = String::from_utf8_lossy(&std::fs::read(&file).unwrap()).to_string();
        for needle in ["mail-secret-42", "Email", "backup me"] {
            assert!(!raw.contains(needle), "{needle} visible in the backup file");
        }

        // Change data after the backup, then restore it.
        add(&store, "Later", "x");
        todos_db.with(|c| todos::create(c, &todos::TodoInput { title: "later".into(), ..Default::default() })).unwrap();
        let s = import(&dir, &todos_db, &key, &store, &file, "backup password").unwrap();
        assert_eq!((s.todos, s.vault_entries), (1, 1));
        assert_eq!(todos_db.with(|c| todos::list(c)).unwrap().len(), 1);
        let hits = store.with(|c| vault::search(c, &SearchQuery { text: "email".into(), ..Default::default() })).unwrap();
        assert_eq!(hits.len(), 1, "search index rebuilt after import");
        assert_eq!(store.with(|c| vault::get_secret(c, hits[0].id)).unwrap().unwrap().0, "mail-secret-42");

        // Still opens with the *master* password after a restart.
        store.lock();
        store.unlock("master password").unwrap();
        assert!(dir.join("vault.db.pre-import").exists());
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn wrong_password_and_tampering_are_rejected_without_touching_data() {
        let (dir, todos_db, key, store) = setup();
        add(&store, "Keep me", "s");
        let file = dir.join("b.dbkp");
        export(&dir, &todos_db, &store, &file, "backup password", KdfParams::FAST).unwrap();

        let err = import(&dir, &todos_db, &key, &store, &file, "not the password").unwrap_err();
        assert!(err.to_string().contains("wrong backup password"), "{err}");

        let mut bytes = std::fs::read(&file).unwrap();
        let n = bytes.len();
        bytes[n - 2000] ^= 0x55; // flip bits inside the todos database pages
        let tampered = dir.join("t.dbkp");
        std::fs::write(&tampered, &bytes).unwrap();
        assert!(import(&dir, &todos_db, &key, &store, &tampered, "backup password").is_err());

        assert_eq!(store.with(|c| vault::count(c)).unwrap(), 1, "live data untouched");
        assert!(!dir.join("vault.db.pre-import").exists());
        std::fs::remove_dir_all(dir).unwrap();
    }
}
