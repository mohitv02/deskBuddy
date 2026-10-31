//! Chat secrets: this device's identity and the teams it has keys for. They
//! live in the encrypted todos database and never leave it except inside a
//! team invite the user chooses to share.

use rusqlite::{params, Connection, OptionalExtension};
use zeroize::Zeroizing;

use super::{now_ms, Error, Result};
use crate::crypto::Key;

fn to_key(blob: Vec<u8>) -> rusqlite::Result<Key> {
    let arr: [u8; 32] = blob.as_slice().try_into().map_err(|_| rusqlite::Error::InvalidQuery)?;
    Ok(Zeroizing::new(arr))
}

/// (signing secret, X25519 secret), if created.
pub fn identity(conn: &Connection) -> Result<Option<(Key, Key)>> {
    Ok(conn
        .query_row("SELECT sign_secret, dh_secret FROM chat_identity WHERE id = 1", [], |r| Ok((to_key(r.get(0)?)?, to_key(r.get(1)?)?)))
        .optional()?)
}

pub fn save_identity(conn: &Connection, sign: &[u8; 32], dh: &[u8; 32]) -> Result<()> {
    conn.execute(
        "INSERT INTO chat_identity (id, sign_secret, dh_secret, created_at) VALUES (1, ?1, ?2, ?3)",
        params![&sign[..], &dh[..], now_ms()],
    )?;
    Ok(())
}

#[derive(Clone)]
pub struct Team {
    pub id: String,
    pub name: String,
    pub dh_secret: Key,
    pub key_version: u32,
    pub home: String,
    pub servers: Vec<String>,
    /// Rotated out (or left): keys kept for reading old messages only.
    pub removed: bool,
}

fn from_row(r: &rusqlite::Row<'_>) -> rusqlite::Result<Team> {
    let servers: String = r.get(5)?;
    Ok(Team {
        id: r.get(0)?,
        name: r.get(1)?,
        dh_secret: to_key(r.get(2)?)?,
        key_version: r.get(3)?,
        home: r.get(4)?,
        servers: serde_json::from_str(&servers).unwrap_or_default(),
        removed: r.get(6)?,
    })
}

const SELECT: &str = "SELECT id, name, dh_secret, key_version, home, servers, removed FROM teams";

pub fn teams(conn: &Connection) -> Result<Vec<Team>> {
    let mut stmt = conn.prepare(&format!("{SELECT} ORDER BY joined_at"))?;
    let rows = stmt.query_map([], from_row)?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

pub fn team(conn: &Connection, id: &str) -> Result<Option<Team>> {
    Ok(conn.query_row(&format!("{SELECT} WHERE id = ?1"), [id], from_row).optional()?)
}

/// Add a team, or a newer key for one we have. Returns the stored team.
pub fn add_team(conn: &Connection, t: &Team, key: &[u8; 32]) -> Result<Team> {
    if t.name.trim().is_empty() {
        return Err(Error::Invalid("team name is empty".into()));
    }
    let tx = conn.unchecked_transaction()?;
    tx.execute(
        "INSERT INTO teams (id, name, dh_secret, key_version, home, servers, removed, joined_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, 0, ?7)
         ON CONFLICT (id) DO UPDATE SET name = excluded.name, home = excluded.home, servers = excluded.servers,
             removed = CASE WHEN excluded.key_version >= key_version THEN 0 ELSE removed END,
             key_version = MAX(key_version, excluded.key_version)",
        params![
            t.id,
            t.name.trim(),
            &t.dh_secret[..],
            t.key_version,
            t.home,
            serde_json::to_string(&t.servers).expect("serializes"),
            now_ms()
        ],
    )?;
    tx.execute(
        "INSERT OR REPLACE INTO team_keys (team_id, version, key) VALUES (?1, ?2, ?3)",
        params![t.id, t.key_version, &key[..]],
    )?;
    tx.commit()?;
    Ok(team(conn, &t.id)?.expect("just stored"))
}

pub fn team_key(conn: &Connection, team: &str, version: u32) -> Result<Option<Key>> {
    Ok(conn
        .query_row("SELECT key FROM team_keys WHERE team_id = ?1 AND version = ?2", params![team, version], |r| to_key(r.get(0)?))
        .optional()?)
}

pub fn set_removed(conn: &Connection, team: &str, removed: bool) -> Result<()> {
    conn.execute("UPDATE teams SET removed = ?1 WHERE id = ?2", params![removed, team])?;
    Ok(())
}

pub fn set_servers(conn: &Connection, team: &str, home: &str, servers: &[String]) -> Result<()> {
    conn.execute(
        "UPDATE teams SET home = ?1, servers = ?2 WHERE id = ?3",
        params![home, serde_json::to_string(servers).expect("serializes"), team],
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::Db;

    fn team_v(version: u32) -> Team {
        Team {
            id: "t1".into(),
            name: "Ops".into(),
            dh_secret: Zeroizing::new([3u8; 32]),
            key_version: version,
            home: "h".into(),
            servers: vec!["http://10.0.0.1:8787".into()],
            removed: false,
        }
    }

    #[test]
    fn identity_once() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            assert!(identity(c)?.is_none());
            save_identity(c, &[1; 32], &[2; 32])?;
            let (s, d) = identity(c)?.unwrap();
            assert_eq!((*s, *d), ([1; 32], [2; 32]));
            assert!(save_identity(c, &[1; 32], &[2; 32]).is_err(), "only one identity");
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn teams_keep_old_keys() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            add_team(c, &team_v(1), &[10; 32])?;
            set_removed(c, "t1", true)?;
            let t = add_team(c, &team_v(2), &[20; 32])?;
            assert_eq!((t.key_version, t.removed), (2, false), "a newer invite brings it back");
            assert_eq!(*team_key(c, "t1", 1)?.unwrap(), [10; 32]);
            assert_eq!(*team_key(c, "t1", 2)?.unwrap(), [20; 32]);
            let t = add_team(c, &team_v(1), &[10; 32])?;
            assert_eq!(t.key_version, 2, "an old invite doesn't roll back");
            assert_eq!(t.servers, ["http://10.0.0.1:8787"]);
            assert_eq!(teams(c)?.len(), 1);
            Ok(())
        })
        .unwrap();
    }
}
