//! Conversations: the built-in "Notes to self" plus one per peer machine.

use rusqlite::{params, Connection, OptionalExtension, Row};
use serde::Serialize;

use super::{now_ms, Error, Result};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Conversation {
    pub id: i64,
    /// "self" or "remote".
    pub kind: String,
    pub title: String,
    pub peer_ip: Option<String>,
    pub peer_name: String,
    pub remote_id: Option<String>,
    pub last_seq: i64,
    pub updated_at: i64,
    /// Newest message, for the conversation list.
    pub last_body: Option<String>,
    /// Pet reaction to their messages: "" default, "none", or a pet state.
    pub reaction: String,
}

impl Conversation {
    pub fn is_remote(&self) -> bool {
        self.kind == "remote"
    }
}

const SELECT: &str = "SELECT c.id, c.kind, c.title, c.peer_ip, c.peer_name, c.remote_id, c.last_seq, c.updated_at,
        (SELECT body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1), c.reaction
     FROM conversations c";

fn from_row(r: &Row<'_>) -> rusqlite::Result<Conversation> {
    Ok(Conversation {
        id: r.get(0)?,
        kind: r.get(1)?,
        title: r.get(2)?,
        peer_ip: r.get(3)?,
        peer_name: r.get(4)?,
        remote_id: r.get(5)?,
        last_seq: r.get(6)?,
        updated_at: r.get(7)?,
        last_body: r.get(8)?,
        reaction: r.get(9)?,
    })
}

/// Notes to self first, then the most recently active.
pub fn list(conn: &Connection) -> Result<Vec<Conversation>> {
    let mut stmt = conn.prepare(&format!("{SELECT} ORDER BY c.kind = 'self' DESC, c.updated_at DESC, c.id"))?;
    let rows = stmt.query_map([], from_row)?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

pub fn get(conn: &Connection, id: i64) -> Result<Conversation> {
    Ok(conn.query_row(&format!("{SELECT} WHERE c.id = ?1"), [id], from_row)?)
}

pub fn by_peer(conn: &Connection, ip: &str) -> Result<Option<Conversation>> {
    Ok(conn.query_row(&format!("{SELECT} WHERE c.peer_ip = ?1"), [ip], from_row).optional()?)
}

/// The conversation with `ip`, created if new. A non-empty `name` refreshes
/// the stored display name.
pub fn open_remote(conn: &Connection, ip: &str, name: &str) -> Result<Conversation> {
    let now = now_ms();
    conn.execute(
        "INSERT INTO conversations (kind, title, peer_ip, peer_name, created_at, updated_at)
         VALUES ('remote', '', ?1, ?2, ?3, ?3)
         ON CONFLICT (peer_ip) WHERE peer_ip IS NOT NULL
         DO UPDATE SET peer_name = CASE WHEN excluded.peer_name <> '' THEN excluded.peer_name ELSE peer_name END",
        params![ip, name.trim(), now],
    )?;
    Ok(by_peer(conn, ip)?.expect("just upserted"))
}

pub fn set_peer_name(conn: &Connection, ip: &str, name: &str) -> Result<()> {
    conn.execute("UPDATE conversations SET peer_name = ?1 WHERE peer_ip = ?2 AND ?1 <> ''", params![name.trim(), ip])?;
    Ok(())
}

/// Record the server's id for this conversation. If it changed (our own
/// address changed), syncing starts over from the beginning.
pub fn bind_remote(conn: &Connection, id: i64, remote_id: &str) -> Result<()> {
    conn.execute(
        "UPDATE conversations SET last_seq = CASE WHEN remote_id IS ?2 THEN last_seq ELSE 0 END, remote_id = ?2 WHERE id = ?1",
        params![id, remote_id],
    )?;
    Ok(())
}

/// "" (default), "none", or a pet state name.
pub fn set_reaction(conn: &Connection, id: i64, reaction: &str) -> Result<Conversation> {
    let valid = reaction.len() <= 32 && reaction.bytes().all(|b| b.is_ascii_alphanumeric());
    if !valid {
        return Err(Error::Invalid(format!("unknown reaction {reaction}")));
    }
    if conn.execute("UPDATE conversations SET reaction = ?1 WHERE id = ?2 AND kind = 'remote'", params![reaction, id])? == 0 {
        return Err(Error::NotFound);
    }
    get(conn, id)
}

/// Everything up to `seq` has been received.
pub fn advance(conn: &Connection, id: i64, seq: i64) -> Result<()> {
    conn.execute("UPDATE conversations SET last_seq = MAX(last_seq, ?1) WHERE id = ?2", params![seq, id])?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::Db;

    #[test]
    fn self_first_and_peers_upsert() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let a = open_remote(c, "10.0.0.2", "Asha")?;
            assert!(a.is_remote());
            let again = open_remote(c, "10.0.0.2", "")?;
            assert_eq!((again.id, again.peer_name.as_str()), (a.id, "Asha"), "empty name keeps the old one");
            assert_eq!(open_remote(c, "10.0.0.2", "Asha K")?.peer_name, "Asha K");
            open_remote(c, "10.0.0.3", "")?;
            let all = list(c)?;
            assert_eq!(all[0].kind, "self");
            assert_eq!(all.len(), 3);
            assert!(by_peer(c, "10.0.0.9")?.is_none());
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn reactions() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let id = open_remote(c, "10.0.0.2", "")?.id;
            assert_eq!(get(c, id)?.reaction, "", "default at first");
            assert_eq!(set_reaction(c, id, "doubleClick")?.reaction, "doubleClick");
            assert_eq!(set_reaction(c, id, "none")?.reaction, "none");
            assert_eq!(set_reaction(c, id, "")?.reaction, "");
            assert!(matches!(set_reaction(c, id, "x'; --"), Err(Error::Invalid(_))));
            assert!(matches!(set_reaction(c, 1, "done"), Err(Error::NotFound)), "not for notes to self");
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn sync_position() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let id = open_remote(c, "10.0.0.2", "")?.id;
            bind_remote(c, id, "dm:a|b")?;
            advance(c, id, 5)?;
            advance(c, id, 3)?;
            assert_eq!(get(c, id)?.last_seq, 5, "never goes back");
            bind_remote(c, id, "dm:a|b")?;
            assert_eq!(get(c, id)?.last_seq, 5, "same id keeps the position");
            bind_remote(c, id, "dm:c|b")?;
            assert_eq!(get(c, id)?.last_seq, 0, "a new id starts over");
            Ok(())
        })
        .unwrap();
    }
}
