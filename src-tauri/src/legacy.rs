//! Phases 1–3 stored todos and the vault in one *unencrypted* deskbuddy.db.
//! On first start of the encrypted version that file is moved to
//! `legacy-plaintext.db`; its todos are copied into the new encrypted todos
//! database immediately, and its vault entries when the master password is
//! created. Then the plaintext file is overwritten and deleted.

use std::path::{Path, PathBuf};

use rusqlite::Connection;

use crate::db::{self, vault, Result};

pub fn path(data_dir: &Path) -> PathBuf {
    data_dir.join("legacy-plaintext.db")
}

/// If `live` is plaintext, fold its WAL in and move it to the legacy path.
pub fn stash_if_plaintext(live: &Path, data_dir: &Path) -> Result<bool> {
    if !db::is_plaintext(live) {
        return Ok(false);
    }
    {
        let conn = Connection::open(live)?;
        conn.execute_batch("PRAGMA wal_checkpoint(TRUNCATE); PRAGMA journal_mode = DELETE;")?;
    }
    std::fs::rename(live, path(data_dir))?;
    for suffix in ["-wal", "-shm"] {
        let _ = std::fs::remove_file(db::with_suffix(live, suffix));
    }
    Ok(true)
}

fn attach(conn: &Connection, legacy: &Path) -> Result<()> {
    // KEY '' attaches an unencrypted database to an encrypted connection.
    conn.execute("ATTACH DATABASE ?1 AS legacy KEY ''", [legacy.to_string_lossy()])?;
    Ok(())
}

fn has_table(conn: &Connection, name: &str) -> Result<bool> {
    Ok(conn.query_row("SELECT COUNT(*) FROM legacy.sqlite_master WHERE type = 'table' AND name = ?1", [name], |r| r.get::<_, i64>(0))? > 0)
}

/// Copy legacy todos into the (encrypted) todos database, then drop them from
/// the legacy file so they are never imported twice.
pub fn import_todos(conn: &mut Connection, legacy: &Path) -> Result<usize> {
    attach(conn, legacy)?;
    let result = (|| -> Result<usize> {
        if !has_table(conn, "todos")? {
            return Ok(0);
        }
        let tx = conn.transaction()?;
        let n = tx.execute(
            "INSERT INTO main.todos (id, title, notes, due, priority, project, status, position, created_at, completed_at, remind_at)
             SELECT id, title, notes, due, priority, project, status, position, created_at, completed_at, remind_at FROM legacy.todos",
            [],
        )?;
        tx.execute_batch("DROP TABLE legacy.todos;")?;
        tx.commit()?;
        Ok(n)
    })();
    conn.execute_batch("DETACH DATABASE legacy;")?;
    result
}

/// Read-only peek; must never create the file (a plain `open` would).
pub fn count_vault_entries(legacy: &Path) -> i64 {
    if !legacy.is_file() {
        return 0;
    }
    Connection::open_with_flags(legacy, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)
        .and_then(|c| c.query_row("SELECT COUNT(*) FROM vault_entries", [], |r| r.get(0)))
        .unwrap_or(0)
}

/// Copy legacy vault entries into the newly created encrypted vault, then
/// shred the legacy file.
pub fn import_vault(conn: &mut Connection, legacy: &Path) -> Result<usize> {
    attach(conn, legacy)?;
    let result = (|| -> Result<usize> {
        if !has_table(conn, "vault_entries")? {
            return Ok(0);
        }
        let tx = conn.transaction()?;
        let n = tx.execute(
            "INSERT INTO main.vault_entries (id, kind, title, body, fields, secret, created_at, updated_at)
             SELECT id, kind, title, body, fields, secret, created_at, updated_at FROM legacy.vault_entries",
            [],
        )?;
        tx.execute("INSERT INTO main.vault_tags (entry_id, tag) SELECT entry_id, tag FROM legacy.vault_tags", [])?;
        vault::rebuild_index(&tx)?;
        tx.commit()?;
        Ok(n)
    })();
    conn.execute_batch("DETACH DATABASE legacy;")?;
    if result.is_ok() {
        db::shred(legacy);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::crypto::{self, KdfParams};
    use crate::db::{migrations, todos, vault::*};
    use crate::vault_store::VaultStore;

    #[test]
    fn plaintext_phase3_database_is_migrated_and_shredded() {
        let dir = std::env::temp_dir().join(format!("deskbuddy-legacy-{}", crypto::hex(&crypto::random_bytes::<6>().unwrap())));
        std::fs::create_dir_all(&dir).unwrap();
        let live = dir.join("deskbuddy.db");

        // Build a Phase 3 style plaintext database with one todo and one secret.
        {
            let mut c = Connection::open(&live).unwrap();
            c.execute_batch("PRAGMA journal_mode = WAL;").unwrap();
            migrations::run(&c, migrations::LEGACY).unwrap();
            todos::create(&c, &todos::TodoInput { title: "old todo".into(), ..Default::default() }).unwrap();
            create(
                &mut c,
                &EntryInput {
                    kind: Kind::ApiKey,
                    title: "Old key".into(),
                    tags: vec!["legacy".into()],
                    body: String::new(),
                    fields: Fields::default(),
                    secret: SecretChange::Set(Secret("sk-plaintext-0001".into())),
                },
            )
            .unwrap();
        }
        assert!(db::is_plaintext(&live));

        assert!(stash_if_plaintext(&live, &dir).unwrap());
        let legacy = path(&dir);
        assert!(!live.exists() && legacy.exists());

        let key = crypto::random_key().unwrap();
        let todos_db = db::Db::open(&live, &key).unwrap();
        assert_eq!(todos_db.with(|c| import_todos(c, &legacy)).unwrap(), 1);
        assert_eq!(todos_db.with(|c| todos::list(c)).unwrap()[0].title, "old todo");
        assert!(!db::is_plaintext(&live), "new todos file is encrypted");
        assert_eq!(count_vault_entries(&legacy), 1);
        let missing = dir.join("nope.db");
        assert_eq!(count_vault_entries(&missing), 0);
        assert!(!missing.exists(), "peeking must not create the file");

        let store = VaultStore::with_params(&dir, KdfParams::FAST);
        store.setup("master password").unwrap();
        assert_eq!(store.with(|c| import_vault(c, &legacy)).unwrap(), 1);
        assert!(!legacy.exists(), "plaintext file is gone");
        let hits = store.with(|c| search(c, &SearchQuery { text: "old key".into(), ..Default::default() })).unwrap();
        assert_eq!(hits.len(), 1);
        assert_eq!(store.with(|c| get_secret(c, hits[0].id)).unwrap().unwrap().0, "sk-plaintext-0001");
        std::fs::remove_dir_all(dir).unwrap();
    }
}
