//! The encrypted vault: `vault.db` (SQLCipher) keyed by Argon2id(master
//! password, salt). `vault.json` holds the salt and KDF parameters — nothing
//! secret. While locked no connection or key exists in memory; unlocking
//! derives the key, opens the file, and keeps both until `lock()` drops them
//! (the key is zeroized on drop).

use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use zeroize::Zeroizing;

use crate::crypto::{self, Key, KdfParams, SALT_LEN};
use crate::db::{self, migrations, vault, Error, Result};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    NotSetUp,
    Locked,
    Unlocked,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Meta {
    version: u32,
    kdf: String,
    salt: String,
    params: KdfParams,
}

impl Meta {
    fn new(params: KdfParams) -> Result<Self> {
        let salt = crypto::random_bytes::<SALT_LEN>()?;
        Ok(Meta { version: 1, kdf: "argon2id".into(), salt: crypto::hex(&salt), params })
    }

    fn derive(&self, password: &str) -> Result<Key> {
        let salt = crypto::unhex(&self.salt).filter(|s| s.len() == SALT_LEN).ok_or_else(|| Error::Invalid("vault.json: bad salt".into()))?;
        Ok(crypto::derive_key(password, &salt, self.params)?)
    }
}

struct Open {
    conn: Connection,
    key: Key,
}

pub struct VaultStore {
    dir: PathBuf,
    params: KdfParams,
    open: Mutex<Option<Open>>,
    last_activity: Mutex<Instant>,
}

impl VaultStore {
    pub fn new(dir: &Path) -> Self {
        Self::with_params(dir, KdfParams::DEFAULT)
    }

    pub fn with_params(dir: &Path, params: KdfParams) -> Self {
        Self { dir: dir.to_path_buf(), params, open: Mutex::new(None), last_activity: Mutex::new(Instant::now()) }
    }

    pub fn db_path(&self) -> PathBuf {
        self.dir.join("vault.db")
    }

    fn meta_path(&self) -> PathBuf {
        self.dir.join("vault.json")
    }

    /// Written before a rekey and renamed over vault.json after it, so a crash
    /// mid-change leaves a file we can still open with one of the two.
    fn meta_next_path(&self) -> PathBuf {
        self.dir.join("vault.json.next")
    }

    fn read_meta(path: &Path) -> Option<Meta> {
        serde_json::from_str(&std::fs::read_to_string(path).ok()?).ok()
    }

    fn write_meta(path: &Path, meta: &Meta) -> Result<()> {
        let tmp = db::with_suffix(path, ".tmp");
        std::fs::write(&tmp, serde_json::to_vec_pretty(meta).expect("meta serializes"))?;
        db::restrict_file(&tmp)?;
        std::fs::rename(tmp, path)?;
        Ok(())
    }

    fn guard(&self) -> std::sync::MutexGuard<'_, Option<Open>> {
        self.open.lock().unwrap_or_else(|p| p.into_inner())
    }

    pub fn status(&self) -> Status {
        if self.guard().is_some() {
            Status::Unlocked
        } else if self.meta_path().exists() || self.meta_next_path().exists() {
            Status::Locked
        } else {
            Status::NotSetUp
        }
    }

    pub fn touch(&self) {
        *self.last_activity.lock().unwrap() = Instant::now();
    }

    pub fn idle_for(&self) -> Duration {
        self.last_activity.lock().unwrap().elapsed()
    }

    /// Create the vault with a new master password.
    pub fn setup(&self, password: &str) -> Result<()> {
        crypto::check_new_password(password).map_err(Error::Invalid)?;
        if self.status() != Status::NotSetUp {
            return Err(Error::Invalid("the vault is already set up".into()));
        }
        // A stray vault.db without metadata can never be opened; set it aside.
        if self.db_path().exists() {
            std::fs::rename(self.db_path(), db::with_suffix(&self.db_path(), ".orphaned"))?;
        }
        let meta = Meta::new(self.params)?;
        let key = meta.derive(password)?;
        let conn = db::open_encrypted(&self.db_path(), &key, migrations::VAULT)?;
        Self::write_meta(&self.meta_path(), &meta)?;
        *self.guard() = Some(Open { conn, key });
        self.touch();
        Ok(())
    }

    pub fn unlock(&self, password: &str) -> Result<()> {
        if self.guard().is_some() {
            return Ok(());
        }
        let candidates = [(self.meta_path(), false), (self.meta_next_path(), true)];
        for (path, is_next) in candidates {
            let Some(meta) = Self::read_meta(&path) else { continue };
            let key = meta.derive(password)?;
            match db::open_encrypted(&self.db_path(), &key, migrations::VAULT) {
                Ok(conn) => {
                    if is_next {
                        // A password change was interrupted after the rekey: finish it.
                        std::fs::rename(&path, self.meta_path())?;
                    } else {
                        let _ = std::fs::remove_file(self.meta_next_path());
                    }
                    *self.guard() = Some(Open { conn, key });
                    self.touch();
                    return Ok(());
                }
                Err(Error::WrongKey) => continue,
                Err(e) => return Err(e),
            }
        }
        Err(Error::WrongKey)
    }

    /// Drop the connection and wipe the key.
    pub fn lock(&self) {
        if let Some(open) = self.guard().take() {
            let _ = open.conn.execute_batch("PRAGMA wal_checkpoint(TRUNCATE);");
            drop(open); // Key is Zeroizing: wiped here.
        }
    }

    /// Run `f` on the unlocked vault; counts as activity for auto-lock.
    pub fn with<T>(&self, f: impl FnOnce(&mut Connection) -> Result<T>) -> Result<T> {
        let mut guard = self.guard();
        let open = guard.as_mut().ok_or(Error::Locked)?;
        self.touch();
        f(&mut open.conn)
    }

    /// Same as `with`, but also gives access to the current key.
    pub fn with_key<T>(&self, f: impl FnOnce(&mut Connection, &Key) -> Result<T>) -> Result<T> {
        let mut guard = self.guard();
        let open = guard.as_mut().ok_or(Error::Locked)?;
        self.touch();
        f(&mut open.conn, &open.key)
    }

    /// Re-encrypt the vault under a new master password.
    pub fn change_password(&self, old: &str, new: &str) -> Result<()> {
        crypto::check_new_password(new).map_err(Error::Invalid)?;
        let current = Self::read_meta(&self.meta_path()).ok_or(Error::Locked)?;
        let old_key = current.derive(old)?;
        let mut guard = self.guard();
        let open = guard.as_mut().ok_or(Error::Locked)?;
        if !crypto::ct_eq(old_key.as_ref(), open.key.as_ref()) {
            return Err(Error::WrongKey);
        }
        let next = Meta::new(self.params)?;
        let new_key = next.derive(new)?;
        Self::write_meta(&self.meta_next_path(), &next)?;
        db::rekey(&open.conn, &new_key)?;
        std::fs::rename(self.meta_next_path(), self.meta_path())?;
        open.key = new_key;
        self.touch();
        Ok(())
    }

    /// Swap in another vault database (from a backup) already encrypted with
    /// the current key.
    pub fn replace_with(&self, src: &Path) -> Result<()> {
        let mut guard = self.guard();
        let open = guard.as_mut().ok_or(Error::Locked)?;
        let key = Zeroizing::new(*open.key);
        let conn = db::replace_file(&mut open.conn, &self.db_path(), src, &key, migrations::VAULT)?;
        vault::rebuild_index(&conn)?;
        open.conn = conn;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::vault::{EntryInput, Fields, Kind, SearchQuery, Secret, SecretChange};

    fn temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("deskbuddy-test-{name}-{}", crypto::hex(&crypto::random_bytes::<6>().unwrap())));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn store(dir: &Path) -> VaultStore {
        VaultStore::with_params(dir, KdfParams::FAST)
    }

    fn add_secret(v: &VaultStore) {
        v.with(|c| {
            vault::create(
                c,
                &EntryInput {
                    kind: Kind::Password,
                    title: "Bank".into(),
                    tags: vec!["money".into()],
                    body: "PIN hint: birthday".into(),
                    fields: Fields::default(),
                    secret: SecretChange::Set(Secret("TopSecret-123".into())),
                },
            )
        })
        .unwrap();
    }

    #[test]
    fn setup_lock_unlock_wrong_password() {
        let dir = temp_dir("lock");
        let v = store(&dir);
        assert_eq!(v.status(), Status::NotSetUp);
        assert!(matches!(v.setup("short"), Err(Error::Invalid(_))));
        v.setup("correct horse battery").unwrap();
        add_secret(&v);
        assert_eq!(v.status(), Status::Unlocked);

        v.lock();
        assert_eq!(v.status(), Status::Locked);
        assert!(matches!(v.with(|c| vault::count(c)), Err(Error::Locked)), "no access while locked");
        assert!(matches!(v.unlock("wrong horse battery"), Err(Error::WrongKey)));
        assert_eq!(v.status(), Status::Locked);
        v.unlock("correct horse battery").unwrap();
        assert_eq!(v.with(|c| vault::count(c)).unwrap(), 1);
        let found = v.with(|c| vault::search(c, &SearchQuery { text: "bank".into(), ..Default::default() })).unwrap();
        assert_eq!(found.len(), 1, "FTS works on the encrypted file");

        // A fresh process (new store object) must also need the password.
        v.lock();
        let again = store(&dir);
        assert_eq!(again.status(), Status::Locked);
        again.unlock("correct horse battery").unwrap();
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn file_on_disk_is_encrypted() {
        let dir = temp_dir("disk");
        let v = store(&dir);
        v.setup("correct horse battery").unwrap();
        add_secret(&v);
        v.lock(); // checkpoints the WAL into the main file
        let raw = std::fs::read(v.db_path()).unwrap();
        assert!(!raw.starts_with(b"SQLite format 3"), "no plaintext header");
        let haystack = String::from_utf8_lossy(&raw);
        for needle in ["TopSecret-123", "Bank", "birthday", "vault_entries", "money"] {
            assert!(!haystack.contains(needle), "{needle} leaked into the file");
        }
        let meta = std::fs::read_to_string(dir.join("vault.json")).unwrap();
        assert!(!meta.contains("correct horse"), "metadata holds no password");
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn change_password_and_interrupted_change_recovery() {
        let dir = temp_dir("rekey");
        let v = store(&dir);
        v.setup("first password").unwrap();
        add_secret(&v);
        assert!(matches!(v.change_password("not it", "second password"), Err(Error::WrongKey)));
        v.change_password("first password", "second password").unwrap();
        v.lock();
        assert!(matches!(v.unlock("first password"), Err(Error::WrongKey)));
        v.unlock("second password").unwrap();

        // Simulate a crash right after the rekey, before vault.json was replaced:
        // the new salt is only in vault.json.next.
        let next = Meta::new(KdfParams::FAST).unwrap();
        let key = next.derive("third password").unwrap();
        VaultStore::write_meta(&dir.join("vault.json.next"), &next).unwrap();
        v.with(|c| db::rekey(c, &key)).unwrap();
        v.lock();
        let reopened = store(&dir);
        reopened.unlock("third password").unwrap();
        assert!(!dir.join("vault.json.next").exists(), "recovery completes the change");
        assert_eq!(reopened.with(|c| vault::count(c)).unwrap(), 1);
        std::fs::remove_dir_all(dir).unwrap();
    }
}
