//! Data-access layer. All SQL lives under this module; the rest of the app only
//! sees typed functions. Both database files are SQLCipher-encrypted with raw
//! 256-bit keys (see `crypto`).

pub mod chat_keys;
pub mod conversations;
pub mod messages;
pub mod migrations;
pub mod todos;
pub mod vault;

use std::path::{Path, PathBuf};
use std::sync::Mutex;

use rusqlite::Connection;

use crate::crypto::{self, Key};

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug)]
pub enum Error {
    Sql(rusqlite::Error),
    Io(std::io::Error),
    Invalid(String),
    NotFound,
    /// The key does not open this file (wrong password, or not ours).
    WrongKey,
    /// The vault is locked; unlock it first.
    Locked,
    Crypto(crypto::CryptoError),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Sql(e) => write!(f, "database error: {e}"),
            Error::Io(e) => write!(f, "file error: {e}"),
            Error::Invalid(msg) => f.write_str(msg),
            Error::NotFound => f.write_str("not found"),
            Error::WrongKey => f.write_str("wrong password"),
            Error::Locked => f.write_str("the vault is locked"),
            Error::Crypto(e) => write!(f, "{e}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<rusqlite::Error> for Error {
    fn from(e: rusqlite::Error) -> Self {
        match e {
            rusqlite::Error::QueryReturnedNoRows => Error::NotFound,
            rusqlite::Error::SqliteFailure(f, _) if f.code == rusqlite::ErrorCode::NotADatabase => Error::WrongKey,
            e => Error::Sql(e),
        }
    }
}

impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        Error::Io(e)
    }
}

impl From<crypto::CryptoError> for Error {
    fn from(e: crypto::CryptoError) -> Self {
        Error::Crypto(e)
    }
}

/// Open (or create) an encrypted database and verify the key actually opens it.
pub fn open_encrypted(path: &Path, key: &Key, migrations: &[&str]) -> Result<Connection> {
    if let Some(dir) = path.parent() {
        create_private_dir(dir)?;
    }
    let conn = Connection::open(path)?;
    restrict_file(path)?;
    apply_key(&conn, key)?;
    conn.pragma_update(None, "foreign_keys", "ON")?;
    conn.pragma_update(None, "journal_mode", "WAL")?;
    migrations::run(&conn, migrations)?;
    Ok(conn)
}

/// `PRAGMA key` + a read that fails with NotADatabase if the key is wrong.
pub fn apply_key(conn: &Connection, key: &Key) -> Result<()> {
    // SQLCipher logs every failed HMAC check (i.e. each wrong password) to
    // stderr; that is expected here, so keep the app log quiet.
    conn.execute_batch("PRAGMA cipher_log_level = NONE;")?;
    let literal = crypto::sqlcipher_key(key);
    conn.execute_batch(&format!("PRAGMA key = \"{}\";", literal.as_str()))?;
    // Wipe freed pages/buffers inside SQLCipher too.
    conn.execute_batch("PRAGMA cipher_memory_security = ON;")?;
    conn.query_row("SELECT count(*) FROM sqlite_master", [], |r| r.get::<_, i64>(0))?;
    Ok(())
}

/// Re-encrypt an open database under a new key.
pub fn rekey(conn: &Connection, new_key: &Key) -> Result<()> {
    let literal = crypto::sqlcipher_key(new_key);
    conn.execute_batch(&format!("PRAGMA rekey = \"{}\";", literal.as_str()))?;
    Ok(())
}

/// Copy an open encrypted database into a new file encrypted with `key`.
pub fn export_to(conn: &Connection, dest: &Path, key: &Key) -> Result<()> {
    let _ = std::fs::remove_file(dest);
    let literal = crypto::sqlcipher_key(key);
    let version: i64 = conn.pragma_query_value(None, "user_version", |r| r.get(0))?;
    conn.execute("ATTACH DATABASE ?1 AS export KEY ?2", rusqlite::params![dest.to_string_lossy(), literal.as_str()])?;
    let result = (|| -> Result<()> {
        conn.query_row("SELECT sqlcipher_export('export')", [], |_| Ok(()))?;
        conn.execute_batch(&format!("PRAGMA export.user_version = {version};"))?;
        Ok(())
    })();
    conn.execute_batch("DETACH DATABASE export;")?;
    restrict_file(dest)?;
    result
}

/// True if `path` is an unencrypted SQLite file (Phase 1–3 format).
pub fn is_plaintext(path: &Path) -> bool {
    let mut head = [0u8; 16];
    std::fs::File::open(path)
        .and_then(|mut f| std::io::Read::read_exact(&mut f, &mut head))
        .map(|_| &head == b"SQLite format 3\0")
        .unwrap_or(false)
}

/// Best-effort secure delete: overwrite with zeros, sync, remove (also -wal/-shm).
/// On SSDs/CoW filesystems old blocks may survive; the file is removed regardless.
pub fn shred(path: &Path) {
    for p in [path.to_path_buf(), with_suffix(path, "-wal"), with_suffix(path, "-shm")] {
        if let Ok(meta) = std::fs::metadata(&p) {
            if let Ok(mut f) = std::fs::OpenOptions::new().write(true).open(&p) {
                let zeros = vec![0u8; 64 * 1024];
                let mut left = meta.len();
                while left > 0 {
                    let n = left.min(zeros.len() as u64) as usize;
                    if std::io::Write::write_all(&mut f, &zeros[..n]).is_err() {
                        break;
                    }
                    left -= n as u64;
                }
                let _ = f.sync_all();
            }
            let _ = std::fs::remove_file(&p);
        }
    }
}

pub fn with_suffix(path: &Path, suffix: &str) -> PathBuf {
    let mut s = path.as_os_str().to_owned();
    s.push(suffix);
    PathBuf::from(s)
}

/// The todos database (always open while the app runs).
pub struct Db {
    conn: Mutex<Connection>,
    path: PathBuf,
}

impl Db {
    pub fn open(path: &Path, key: &Key) -> Result<Self> {
        Ok(Self { conn: Mutex::new(open_encrypted(path, key, migrations::TODOS)?), path: path.to_path_buf() })
    }

    #[cfg(test)]
    pub fn open_in_memory() -> Result<Self> {
        Self::open_in_memory_with(migrations::TODOS)
    }

    #[cfg(test)]
    pub fn open_in_memory_with(list: &[&str]) -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        conn.pragma_update(None, "foreign_keys", "ON")?;
        migrations::run(&conn, list)?;
        Ok(Self { conn: Mutex::new(conn), path: PathBuf::new() })
    }

    /// Run `f` with exclusive access to the connection.
    pub fn with<T>(&self, f: impl FnOnce(&mut Connection) -> Result<T>) -> Result<T> {
        let mut conn = self.conn.lock().unwrap_or_else(|p| p.into_inner());
        f(&mut conn)
    }

    /// Swap in another database file (backup import). The current file is
    /// kept as `<name>.pre-import` until the next import.
    pub fn replace_with(&self, src: &Path, key: &Key) -> Result<()> {
        let mut conn = self.conn.lock().unwrap_or_else(|p| p.into_inner());
        let fresh = replace_file(&mut conn, &self.path, src, key, migrations::TODOS)?;
        *conn = fresh;
        Ok(())
    }
}

/// Close `conn`, move `live` aside, move `src` into place, reopen with `key`.
/// `conn` is left pointing at an in-memory placeholder until the caller stores
/// the returned connection.
pub fn replace_file(conn: &mut Connection, live: &Path, src: &Path, key: &Key, migrations: &[&str]) -> Result<Connection> {
    // Checkpoint and close the live connection so its -wal is folded in.
    let _ = conn.execute_batch("PRAGMA wal_checkpoint(TRUNCATE);");
    let old = std::mem::replace(conn, Connection::open_in_memory()?);
    drop(old);
    let aside = with_suffix(live, ".pre-import");
    shred(&aside);
    if live.exists() {
        std::fs::rename(live, &aside)?;
    }
    for suffix in ["-wal", "-shm"] {
        let _ = std::fs::remove_file(with_suffix(live, suffix));
    }
    std::fs::rename(src, live)?;
    open_encrypted(live, key, migrations)
}

fn create_private_dir(dir: &Path) -> Result<()> {
    std::fs::create_dir_all(dir)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(dir, std::fs::Permissions::from_mode(0o700))?;
    }
    Ok(())
}

pub fn restrict_file(path: &Path) -> Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))?;
    }
    Ok(())
}

pub fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}
