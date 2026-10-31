//! Conversations: the built-in "Notes to self", direct chats, team chats and
//! team-to-team groups (plus read-only chats from the old IP-based server).

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
    /// For remote chats: "dm", "team", "link", or "ip" (old server).
    pub room: String,
    /// The other device of a direct chat.
    pub peer_device: Option<String>,
    /// Why nothing can be sent here right now; "" when sending works.
    pub read_only: String,
}

impl Conversation {
    pub fn is_remote(&self) -> bool {
        self.kind == "remote"
    }
}

const SELECT: &str = "SELECT c.id, c.kind, c.title, c.peer_ip, c.peer_name, c.remote_id, c.last_seq, c.updated_at,
        (SELECT body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1), c.reaction,
        c.room, c.peer_device, c.read_only
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
        room: r.get(10)?,
        peer_device: r.get(11)?,
        read_only: r.get(12)?,
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

/// A new display name for a device's direct chat.
pub fn set_device_name(conn: &Connection, device: &str, name: &str) -> Result<()> {
    conn.execute("UPDATE conversations SET peer_name = ?1 WHERE peer_device = ?2 AND ?1 <> ''", params![name.trim(), device])?;
    Ok(())
}

pub fn by_remote(conn: &Connection, remote_id: &str) -> Result<Option<Conversation>> {
    Ok(conn.query_row(&format!("{SELECT} WHERE c.remote_id = ?1 AND c.room <> 'ip'"), [remote_id], from_row).optional()?)
}

/// The v2 conversation with server id `remote_id`, created if new. Non-empty
/// `title` / `peer_name` refresh the stored ones.
pub fn open_room(conn: &Connection, room: &str, remote_id: &str, title: &str, peer_device: Option<&str>, peer_name: &str) -> Result<Conversation> {
    if !matches!(room, "dm" | "team" | "link") {
        return Err(Error::Invalid(format!("unknown room {room}")));
    }
    let now = now_ms();
    conn.execute(
        "INSERT INTO conversations (kind, room, remote_id, title, peer_device, peer_name, created_at, updated_at)
         VALUES ('remote', ?1, ?2, ?3, ?4, ?5, ?6, ?6)
         ON CONFLICT (remote_id) WHERE room <> 'ip'
         DO UPDATE SET title = CASE WHEN excluded.title <> '' THEN excluded.title ELSE title END,
                       peer_name = CASE WHEN excluded.peer_name <> '' THEN excluded.peer_name ELSE peer_name END",
        params![room, remote_id, title.trim(), peer_device, peer_name.trim(), now],
    )?;
    Ok(by_remote(conn, remote_id)?.expect("just upserted"))
}

pub fn set_read_only(conn: &Connection, id: i64, reason: &str) -> Result<()> {
    conn.execute("UPDATE conversations SET read_only = ?1 WHERE id = ?2", params![reason, id])?;
    Ok(())
}

/// Drop every message and start syncing again from the beginning (a closed
/// temporary group, or an archive being locked again).
pub fn clear(conn: &Connection, id: i64) -> Result<()> {
    let tx = conn.unchecked_transaction()?;
    tx.execute("DELETE FROM messages WHERE conversation_id = ?1", [id])?;
    tx.execute("UPDATE conversations SET last_seq = 0 WHERE id = ?1", [id])?;
    tx.commit()?;
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
    fn self_first_and_rooms_upsert() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let a = open_room(c, "dm", "dm:a|b", "", Some("b"), "Asha")?;
            assert!(a.is_remote());
            assert_eq!((a.room.as_str(), a.peer_device.as_deref(), a.read_only.as_str()), ("dm", Some("b"), ""));
            let again = open_room(c, "dm", "dm:a|b", "", Some("b"), "")?;
            assert_eq!((again.id, again.peer_name.as_str()), (a.id, "Asha"), "empty name keeps the old one");
            set_device_name(c, "b", "Asha K")?;
            assert_eq!(get(c, a.id)?.peer_name, "Asha K");
            let t = open_room(c, "team", "team:x", "Ops", None, "")?;
            assert_eq!(open_room(c, "team", "team:x", "Ops 2", None, "")?.title, "Ops 2");
            assert!(open_room(c, "nope", "x", "", None, "").is_err());
            let all = list(c)?;
            assert_eq!(all[0].kind, "self");
            assert_eq!(all.len(), 3);
            assert_eq!(by_remote(c, "team:x")?.map(|c| c.id), Some(t.id));
            assert!(by_remote(c, "team:y")?.is_none());
            set_read_only(c, t.id, "closed")?;
            assert_eq!(get(c, t.id)?.read_only, "closed");
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn reactions() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let id = open_room(c, "dm", "dm:a|b", "", Some("b"), "")?.id;
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
    fn sync_position_and_clear() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let id = open_room(c, "link", "link:l", "A ↔ B", None, "")?.id;
            advance(c, id, 5)?;
            advance(c, id, 3)?;
            assert_eq!(get(c, id)?.last_seq, 5, "never goes back");
            crate::db::messages::create(c, id, "x")?;
            clear(c, id)?;
            assert_eq!(get(c, id)?.last_seq, 0);
            assert!(crate::db::messages::list(c, id, None, 10)?.is_empty());
            Ok(())
        })
        .unwrap();
    }
}
