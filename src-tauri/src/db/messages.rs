//! Chat messages: notes to self, and LAN chat mirrored from the chat server.

use rusqlite::{params, Connection, OptionalExtension, Row};
use serde::Serialize;

use super::todos::{self, Status, Todo, TodoInput};
use super::vault::fts_query;
use super::{now_ms, Error, Result};

/// The built-in "Notes to self" conversation (created by the migration).
#[cfg(test)]
pub const SELF_CONVERSATION: i64 = 1;

pub const MAX_BODY_BYTES: usize = 20_000;
pub const MAX_PAGE: u32 = 200;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Message {
    pub id: i64,
    pub conversation_id: i64,
    pub body: String,
    /// The todo made from this message, if it still exists.
    pub todo_id: Option<i64>,
    pub todo_status: Option<Status>,
    pub pinned: bool,
    pub created_at: i64,
    pub edited_at: Option<i64>,
    /// Who sent it: their device key (or IP in an old chat); None when it
    /// was sent from here.
    pub sender_ip: Option<String>,
    /// Their name when it arrived, for group chats.
    pub sender_name: String,
    /// Delivery of messages sent from here: "pending", "sent" or "failed".
    pub state: String,
    pub client_msg_id: Option<String>,
}

const SELECT: &str = "SELECT m.id, m.conversation_id, m.body, m.todo_id, t.status, m.pinned, m.created_at, m.edited_at,
        m.sender_ip, m.state, m.client_msg_id, m.sender_name
     FROM messages m LEFT JOIN todos t ON t.id = m.todo_id";

fn from_row(r: &Row<'_>) -> rusqlite::Result<Message> {
    Ok(Message {
        id: r.get(0)?,
        conversation_id: r.get(1)?,
        body: r.get(2)?,
        todo_id: r.get(3)?,
        todo_status: r.get::<_, Option<String>>(4)?.map(|s| Status::parse(&s)),
        pinned: r.get(5)?,
        created_at: r.get(6)?,
        edited_at: r.get(7)?,
        sender_ip: r.get(8)?,
        state: r.get(9)?,
        client_msg_id: r.get(10)?,
        sender_name: r.get(11)?,
    })
}

/// Trailing whitespace and leading blank lines are dropped; indentation is kept.
fn clean(body: &str) -> Result<String> {
    let body = body.trim_end().trim_start_matches(['\n', '\r']);
    if body.trim().is_empty() {
        return Err(Error::Invalid("message is empty".into()));
    }
    if body.len() > MAX_BODY_BYTES {
        return Err(Error::Invalid(format!("message is too long (max {} KB)", MAX_BODY_BYTES / 1000)));
    }
    Ok(body.to_string())
}

pub fn get(conn: &Connection, id: i64) -> Result<Message> {
    Ok(conn.query_row(&format!("{SELECT} WHERE m.id = ?1"), [id], from_row)?)
}

/// One page, oldest first: the `limit` newest messages older than `before`
/// (or the newest overall without it).
pub fn list(conn: &Connection, conversation: i64, before: Option<i64>, limit: u32) -> Result<Vec<Message>> {
    let mut stmt = conn.prepare(&format!(
        "{SELECT} WHERE m.conversation_id = ?1 AND m.id < ?2 ORDER BY m.id DESC LIMIT ?3"
    ))?;
    let rows = stmt.query_map(params![conversation, before.unwrap_or(i64::MAX), limit.clamp(1, MAX_PAGE)], from_row)?;
    let mut page: Vec<Message> = rows.collect::<rusqlite::Result<_>>()?;
    page.reverse();
    Ok(page)
}

/// Pinned messages, oldest first.
pub fn pinned(conn: &Connection, conversation: i64) -> Result<Vec<Message>> {
    let mut stmt = conn.prepare(&format!("{SELECT} WHERE m.conversation_id = ?1 AND m.pinned = 1 ORDER BY m.id"))?;
    let rows = stmt.query_map([conversation], from_row)?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

/// Prefix match on every word, newest first.
pub fn search(conn: &Connection, conversation: i64, text: &str, limit: u32) -> Result<Vec<Message>> {
    let Some(q) = fts_query(text) else { return Ok(Vec::new()) };
    let mut stmt = conn.prepare(&format!(
        "{SELECT} JOIN messages_fts f ON f.rowid = m.id
         WHERE messages_fts MATCH ?1 AND m.conversation_id = ?2 ORDER BY m.id DESC LIMIT ?3"
    ))?;
    let rows = stmt.query_map(params![q, conversation, limit.clamp(1, MAX_PAGE)], from_row)?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

pub fn create(conn: &Connection, conversation: i64, body: &str) -> Result<Message> {
    let body = clean(body)?;
    let now = now_ms();
    let tx = conn.unchecked_transaction()?;
    tx.execute(
        "INSERT INTO messages (conversation_id, body, created_at) VALUES (?1, ?2, ?3)",
        params![conversation, body, now],
    )?;
    let id = tx.last_insert_rowid();
    tx.execute("UPDATE conversations SET updated_at = ?1 WHERE id = ?2", params![now, conversation])?;
    tx.commit()?;
    get(conn, id)
}

/// Saving an unchanged body does not mark the message edited. Only notes to
/// self can be edited: the other side already has its copy of a chat message.
pub fn update_body(conn: &Connection, id: i64, body: &str) -> Result<Message> {
    let body = clean(body)?;
    let n = conn.execute(
        "UPDATE messages SET edited_at = CASE WHEN body = ?1 THEN edited_at ELSE ?2 END, body = ?1
         WHERE id = ?3 AND conversation_id IN (SELECT id FROM conversations WHERE kind = 'self')",
        params![body, now_ms(), id],
    )?;
    if n == 0 {
        get(conn, id)?; // NotFound if it does not exist
        return Err(Error::Invalid("chat messages can't be edited once sent".into()));
    }
    get(conn, id)
}

pub fn set_pinned(conn: &Connection, id: i64, pinned: bool) -> Result<Message> {
    if conn.execute("UPDATE messages SET pinned = ?1 WHERE id = ?2", params![pinned, id])? == 0 {
        return Err(Error::NotFound);
    }
    get(conn, id)
}

pub fn delete(conn: &Connection, id: i64) -> Result<()> {
    match conn.execute("DELETE FROM messages WHERE id = ?1", [id])? {
        0 => Err(Error::NotFound),
        _ => Ok(()),
    }
}

/// A chat message written here, waiting for the server to take it.
pub fn create_outgoing(conn: &Connection, conversation: i64, body: &str, client_msg_id: &str) -> Result<Message> {
    let body = clean(body)?;
    let now = now_ms();
    let tx = conn.unchecked_transaction()?;
    tx.execute(
        "INSERT INTO messages (conversation_id, body, created_at, client_msg_id, state) VALUES (?1, ?2, ?3, ?4, 'pending')",
        params![conversation, body, now, client_msg_id],
    )?;
    let id = tx.last_insert_rowid();
    tx.execute("UPDATE conversations SET updated_at = ?1 WHERE id = ?2", params![now, conversation])?;
    tx.commit()?;
    get(conn, id)
}

/// Messages sent from here that the server has not acknowledged, with the
/// server conversation each goes to, oldest first.
pub fn pending_outgoing(conn: &Connection) -> Result<Vec<(Message, String)>> {
    let mut stmt = conn.prepare(&format!(
        "{SELECT} JOIN conversations c ON c.id = m.conversation_id
         WHERE m.state = 'pending' AND m.sender_ip IS NULL AND c.room <> 'ip' AND c.remote_id IS NOT NULL ORDER BY m.id"
    ))?;
    let rows = stmt.query_map([], |r| Ok((from_row(r)?, String::new())))?;
    let mut out: Vec<(Message, String)> = rows.collect::<rusqlite::Result<_>>()?;
    for (m, remote) in &mut out {
        *remote = conn.query_row("SELECT remote_id FROM conversations WHERE id = ?1", [m.conversation_id], |r| r.get(0))?;
    }
    Ok(out)
}

pub fn set_state(conn: &Connection, id: i64, state: &str) -> Result<Message> {
    if conn.execute("UPDATE messages SET state = ?1 WHERE id = ?2 AND sender_ip IS NULL", params![state, id])? == 0 {
        return Err(Error::NotFound);
    }
    get(conn, id)
}

pub fn by_client_id(conn: &Connection, client_msg_id: &str) -> Result<Option<Message>> {
    Ok(conn
        .query_row(&format!("{SELECT} WHERE m.client_msg_id = ?1 AND m.sender_ip IS NULL"), [client_msg_id], from_row)
        .optional()?)
}

/// A message as stored on the chat server.
pub struct Remote<'a> {
    pub conversation: i64,
    /// None when it was sent from this device.
    pub sender_ip: Option<&'a str>,
    pub sender_name: &'a str,
    pub client_msg_id: &'a str,
    pub seq: i64,
    pub body: &'a str,
    pub created_at: i64,
}

/// Store a message received from the server. One of ours (by clientMsgId)
/// is marked sent instead of duplicated. Returns whether anything changed.
pub fn apply_remote(conn: &Connection, m: &Remote<'_>) -> Result<bool> {
    if m.sender_ip.is_none() {
        let n = conn.execute(
            "UPDATE messages SET remote_seq = ?1, state = 'sent'
             WHERE conversation_id = ?2 AND sender_ip IS NULL AND client_msg_id = ?3 AND remote_seq IS NULL",
            params![m.seq, m.conversation, m.client_msg_id],
        )?;
        if n > 0 {
            return Ok(true);
        }
    }
    // OR IGNORE: already stored (same seq, or same sender + clientMsgId).
    let n = conn.execute(
        "INSERT OR IGNORE INTO messages (conversation_id, body, created_at, sender_ip, client_msg_id, remote_seq, state, sender_name)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'sent', ?7)",
        params![m.conversation, m.body, m.created_at, m.sender_ip, m.client_msg_id, m.seq, m.sender_name],
    )?;
    if n > 0 {
        conn.execute(
            "UPDATE conversations SET updated_at = MAX(updated_at, ?1) WHERE id = ?2",
            params![m.created_at, m.conversation],
        )?;
    }
    Ok(n > 0)
}

/// Create a todo from a message and link the two. The UI parses the body
/// (quick-add syntax) into `input`. A message links to at most one live todo.
pub fn to_todo(conn: &mut Connection, id: i64, input: &TodoInput) -> Result<(Message, Todo)> {
    let tx = conn.transaction()?;
    if get(&tx, id)?.todo_id.is_some() {
        return Err(Error::Invalid("this message is already a todo".into()));
    }
    let todo = todos::create(&tx, input)?;
    tx.execute("UPDATE messages SET todo_id = ?1 WHERE id = ?2", params![todo.id, id])?;
    tx.commit()?;
    Ok((get(conn, id)?, todo))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::Db;

    const C: i64 = SELF_CONVERSATION;

    fn bodies(list: &[Message]) -> Vec<&str> {
        list.iter().map(|m| m.body.as_str()).collect()
    }

    #[test]
    fn create_validates_and_pages_oldest_first() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            assert!(matches!(create(c, C, " \n "), Err(Error::Invalid(_))));
            assert!(matches!(create(c, C, &"x".repeat(MAX_BODY_BYTES + 1)), Err(Error::Invalid(_))));
            assert_eq!(create(c, C, "\n  indented\n")?.body, "  indented");
            for b in ["a", "b", "c", "d"] {
                create(c, C, b)?;
            }
            let last = list(c, C, None, 2)?;
            assert_eq!(bodies(&last), ["c", "d"]);
            let older = list(c, C, Some(last[0].id), 2)?;
            assert_eq!(bodies(&older), ["a", "b"]);
            assert_eq!(bodies(&list(c, C, Some(older[0].id), 10)?), ["  indented"]);
            assert!(list(c, 99, None, 10)?.is_empty(), "other conversations are separate");
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn edit_pin_delete() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let m = create(c, C, "draft")?;
            assert_eq!(update_body(c, m.id, "draft ")?.edited_at, None, "no-op edit keeps it unedited");
            let e = update_body(c, m.id, "final")?;
            assert_eq!((e.body.as_str(), e.edited_at.is_some()), ("final", true));
            assert!(set_pinned(c, m.id, true)?.pinned);
            create(c, C, "other")?;
            assert_eq!(bodies(&pinned(c, C)?), ["final"]);
            delete(c, m.id)?;
            assert!(matches!(delete(c, m.id), Err(Error::NotFound)));
            assert!(matches!(update_body(c, m.id, "x"), Err(Error::NotFound)));
            assert!(pinned(c, C)?.is_empty());
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn search_follows_edits_and_deletes() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let a = create(c, C, "Renew the passport")?;
            create(c, C, "buy milk")?;
            assert_eq!(bodies(&search(c, C, "pass", 10)?), ["Renew the passport"], "prefix match");
            assert!(search(c, C, "  ", 10)?.is_empty());
            assert!(search(c, C, "\"*(", 10)?.is_empty(), "FTS syntax is neutralised");
            update_body(c, a.id, "Renew the licence")?;
            assert!(search(c, C, "passport", 10)?.is_empty(), "old text leaves the index");
            assert_eq!(search(c, C, "licence", 10)?.len(), 1);
            delete(c, a.id)?;
            assert!(search(c, C, "licence", 10)?.is_empty());
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn outgoing_ack_and_incoming() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let conv = crate::db::conversations::open_room(c, "dm", "dm:a|b", "", Some("b"), "Asha")?.id;
            let out = create_outgoing(c, conv, "hi Asha", "c1")?;
            assert_eq!((out.state.as_str(), out.sender_ip.as_deref()), ("pending", None));
            let pending = pending_outgoing(c)?;
            assert_eq!((pending.len(), pending[0].1.as_str()), (1, "dm:a|b"));
            assert!(matches!(update_body(c, out.id, "edited"), Err(Error::Invalid(_))), "chat messages are not editable");

            // The server's copy of our own message marks it sent, no duplicate.
            let mine = Remote { conversation: conv, sender_ip: None, sender_name: "", client_msg_id: "c1", seq: 1, body: "hi Asha", created_at: 1 };
            assert!(apply_remote(c, &mine)?);
            assert!(!apply_remote(c, &mine)?, "second delivery is a no-op");
            assert_eq!(get(c, out.id)?.state, "sent");
            assert!(pending_outgoing(c)?.is_empty());

            let theirs = Remote { conversation: conv, sender_ip: Some("b"), sender_name: "Asha", client_msg_id: "c1", seq: 2, body: "hello!", created_at: 2 };
            assert!(apply_remote(c, &theirs)?, "same clientMsgId from another sender is a different message");
            assert!(!apply_remote(c, &theirs)?);
            let page = list(c, conv, None, 10)?;
            assert_eq!(bodies(&page), ["hi Asha", "hello!"]);
            assert_eq!((page[1].sender_ip.as_deref(), page[1].sender_name.as_str()), (Some("b"), "Asha"));
            assert_eq!(search(c, conv, "hello", 10)?.len(), 1);

            assert_eq!(set_state(c, out.id, "failed")?.state, "failed");
            assert!(by_client_id(c, "c1")?.is_some());
            assert!(matches!(set_state(c, page[1].id, "failed"), Err(Error::NotFound)), "only our own messages have a state");
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn to_todo_links_once_and_survives_todo_delete() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let m = create(c, C, "call the bank")?;
            let input = TodoInput { title: "call the bank".into(), ..Default::default() };
            let (linked, todo) = to_todo(c, m.id, &input)?;
            assert_eq!((linked.todo_id, linked.todo_status), (Some(todo.id), Some(Status::Open)));
            assert!(matches!(to_todo(c, m.id, &input), Err(Error::Invalid(_))));
            todos::set_status(c, todo.id, Status::Done)?;
            assert_eq!(get(c, m.id)?.todo_status, Some(Status::Done));
            todos::delete(c, todo.id)?;
            let after = get(c, m.id)?;
            assert_eq!((after.todo_id, after.body.as_str()), (None, "call the bank"));
            assert!(to_todo(c, m.id, &input).is_ok(), "can be made a todo again");
            // A failed todo insert leaves the message unlinked.
            let other = create(c, C, "x")?;
            let bad = TodoInput { title: " ".into(), ..Default::default() };
            assert!(to_todo(c, other.id, &bad).is_err());
            assert_eq!(get(c, other.id)?.todo_id, None);
            Ok(())
        })
        .unwrap();
    }
}
