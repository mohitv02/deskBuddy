//! Forward-only schema migrations tracked with `PRAGMA user_version`, one list
//! per database file. Append new entries; never edit a migration that has shipped.

use rusqlite::Connection;

use super::Result;

/// `deskbuddy.db` — todos. Unlocked automatically (key in the login keyring).
pub const TODOS: &[&str] = &[TODOS_V1, TODOS_V2, TODOS_V3, TODOS_V4, TODOS_V5, TODOS_V6];

/// `vault.db` — vault entries. Unlocked with the master password.
pub const VAULT: &[&str] = &[VAULT_V1];

/// Phase 1–3 single plaintext database (todos + vault), kept only for importing.
#[cfg(test)]
pub const LEGACY: &[&str] = &[TODOS_V1, VAULT_V1, TODOS_V2];

const TODOS_V1: &str = 
"CREATE TABLE todos (
        id           INTEGER PRIMARY KEY,
        title        TEXT    NOT NULL CHECK (length(trim(title)) > 0),
        notes        TEXT    NOT NULL DEFAULT '',
        due          TEXT    NULL,     -- local 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM'
        priority     INTEGER NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 3),
        project      TEXT    NOT NULL DEFAULT '',
        status       TEXT    NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open', 'in_progress', 'done')),
        position     REAL    NOT NULL,
        created_at   INTEGER NOT NULL, -- unix ms
        completed_at INTEGER NULL
    );
    CREATE INDEX todos_status_position ON todos (status, position);";

// Secrets are never copied into the search index.
const VAULT_V1: &str = "CREATE TABLE vault_entries (
        id         INTEGER PRIMARY KEY,
        kind       TEXT    NOT NULL
                   CHECK (kind IN ('vm', 'password', 'api_key', 'command', 'note')),
        title      TEXT    NOT NULL CHECK (length(trim(title)) > 0),
        body       TEXT    NOT NULL DEFAULT '',
        fields     TEXT    NOT NULL DEFAULT '{}', -- JSON, type-specific (host, user, ...)
        secret     TEXT    NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );
    CREATE TABLE vault_tags (
        entry_id INTEGER NOT NULL REFERENCES vault_entries (id) ON DELETE CASCADE,
        tag      TEXT    NOT NULL,
        PRIMARY KEY (entry_id, tag)
    ) WITHOUT ROWID;
    CREATE INDEX vault_tags_tag ON vault_tags (tag);
    CREATE VIRTUAL TABLE vault_fts USING fts5 (
        title, tags, body, extra,
        tokenize = 'unicode61 remove_diacritics 2',
        prefix = '2 3'
    );";

// Todo alarms. remind_at (unix ms) is armed from a timed due date and cleared
// once the alarm has fired, been snoozed past, or the todo is done.
const TODOS_V2: &str = "ALTER TABLE todos ADD COLUMN remind_at INTEGER NULL;
    CREATE INDEX todos_remind_at ON todos (remind_at) WHERE remind_at IS NOT NULL;";

// Self-chat. Conversation 1 is the built-in "Notes to self" stream; 'remote'
// is reserved for chatting with other people (sync columns come later).
// Messages page by id, which only grows. The FTS index follows via triggers.
const TODOS_V3: &str = "CREATE TABLE conversations (
        id         INTEGER PRIMARY KEY,
        kind       TEXT    NOT NULL DEFAULT 'self' CHECK (kind IN ('self', 'remote')),
        title      TEXT    NOT NULL DEFAULT '',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );
    INSERT INTO conversations (id, kind, title, created_at, updated_at)
    VALUES (1, 'self', 'Notes to self', CAST(strftime('%s', 'now') AS INTEGER) * 1000,
                                        CAST(strftime('%s', 'now') AS INTEGER) * 1000);
    CREATE TABLE messages (
        id              INTEGER PRIMARY KEY,
        conversation_id INTEGER NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
        body            TEXT    NOT NULL CHECK (length(trim(body)) > 0),
        todo_id         INTEGER NULL REFERENCES todos (id) ON DELETE SET NULL,
        pinned          INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
        created_at      INTEGER NOT NULL, -- unix ms
        edited_at       INTEGER NULL
    );
    CREATE INDEX messages_conv_id ON messages (conversation_id, id);
    CREATE INDEX messages_pinned ON messages (conversation_id) WHERE pinned = 1;
    CREATE INDEX messages_todo ON messages (todo_id) WHERE todo_id IS NOT NULL;
    CREATE VIRTUAL TABLE messages_fts USING fts5 (
        body, content = 'messages', content_rowid = 'id',
        tokenize = 'unicode61 remove_diacritics 2',
        prefix = '2 3'
    );
    CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts (rowid, body) VALUES (new.id, new.body);
    END;
    CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
        INSERT INTO messages_fts (messages_fts, rowid, body) VALUES ('delete', old.id, old.body);
    END;
    CREATE TRIGGER messages_au AFTER UPDATE OF body ON messages BEGIN
        INSERT INTO messages_fts (messages_fts, rowid, body) VALUES ('delete', old.id, old.body);
        INSERT INTO messages_fts (rowid, body) VALUES (new.id, new.body);
    END;";

// LAN chat. A 'remote' conversation is one peer machine, keyed by its IP;
// remote_id is the server's id for it and last_seq how far we have synced.
// Messages: sender_ip NULL means sent from here; state tracks delivery of
// those; remote_seq is the server's position (NULL until acknowledged).
const TODOS_V4: &str = "ALTER TABLE conversations ADD COLUMN peer_ip TEXT NULL;
    ALTER TABLE conversations ADD COLUMN peer_name TEXT NOT NULL DEFAULT '';
    ALTER TABLE conversations ADD COLUMN remote_id TEXT NULL;
    ALTER TABLE conversations ADD COLUMN last_seq INTEGER NOT NULL DEFAULT 0;
    CREATE UNIQUE INDEX conversations_peer ON conversations (peer_ip) WHERE peer_ip IS NOT NULL;
    ALTER TABLE messages ADD COLUMN sender_ip TEXT NULL;
    ALTER TABLE messages ADD COLUMN client_msg_id TEXT NULL;
    ALTER TABLE messages ADD COLUMN remote_seq INTEGER NULL;
    ALTER TABLE messages ADD COLUMN state TEXT NOT NULL DEFAULT 'sent'
        CHECK (state IN ('pending', 'sent', 'failed'));
    CREATE UNIQUE INDEX messages_remote_seq ON messages (conversation_id, remote_seq) WHERE remote_seq IS NOT NULL;
    CREATE UNIQUE INDEX messages_client_id ON messages (conversation_id, ifnull(sender_ip, ''), client_msg_id)
        WHERE client_msg_id IS NOT NULL;
    CREATE INDEX messages_pending ON messages (state) WHERE state = 'pending';";

// How the pet reacts to a message from this person: '' = the default
// reaction, 'none' = no reaction, otherwise a pet state such as 'doubleClick'.
const TODOS_V5: &str = "ALTER TABLE conversations ADD COLUMN reaction TEXT NOT NULL DEFAULT '';";

// Chat v2: end-to-end encrypted, identified by device keys instead of IPs.
// chat_identity holds this install's Ed25519 + X25519 secrets; teams and
// team_keys hold the keys from team invites (old versions stay so old
// messages still decrypt). A remote conversation's `room` is 'dm', 'team' or
// 'link' (remote_id is then the server's conversation id), or 'ip' for a v1
// chat kept read-only. messages.sender_ip now holds the sender's id: an IP
// for v1, a device key for v2.
const TODOS_V6: &str = "CREATE TABLE chat_identity (
        id          INTEGER PRIMARY KEY CHECK (id = 1),
        sign_secret BLOB    NOT NULL,
        dh_secret   BLOB    NOT NULL,
        created_at  INTEGER NOT NULL
    );
    CREATE TABLE teams (
        id          TEXT    PRIMARY KEY,
        name        TEXT    NOT NULL,
        dh_secret   BLOB    NOT NULL,
        key_version INTEGER NOT NULL,
        home        TEXT    NOT NULL DEFAULT '',
        servers     TEXT    NOT NULL DEFAULT '[]', -- JSON list of http://host:port
        removed     INTEGER NOT NULL DEFAULT 0 CHECK (removed IN (0, 1)),
        joined_at   INTEGER NOT NULL
    );
    CREATE TABLE team_keys (
        team_id TEXT    NOT NULL REFERENCES teams (id) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        key     BLOB    NOT NULL,
        PRIMARY KEY (team_id, version)
    ) WITHOUT ROWID;
    ALTER TABLE conversations ADD COLUMN room TEXT NOT NULL DEFAULT 'ip' CHECK (room IN ('ip', 'dm', 'team', 'link'));
    ALTER TABLE conversations ADD COLUMN peer_device TEXT NULL;
    ALTER TABLE conversations ADD COLUMN read_only TEXT NOT NULL DEFAULT '';
    CREATE UNIQUE INDEX conversations_room ON conversations (remote_id) WHERE room <> 'ip';
    UPDATE conversations SET read_only = 'This chat used the old IP-based server.' WHERE kind = 'remote';
    ALTER TABLE messages ADD COLUMN sender_name TEXT NOT NULL DEFAULT '';";

pub fn run(conn: &Connection, migrations: &[&str]) -> Result<()> {
    let current: i64 = conn.pragma_query_value(None, "user_version", |r| r.get(0))?;
    for (i, sql) in migrations.iter().enumerate().skip(current as usize) {
        let tx = conn.unchecked_transaction()?;
        tx.execute_batch(sql)?;
        tx.pragma_update(None, "user_version", (i + 1) as i64)?;
        tx.commit()?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn migrations_are_idempotent() {
        for list in [TODOS, VAULT, LEGACY] {
            let conn = Connection::open_in_memory().unwrap();
            run(&conn, list).unwrap();
            run(&conn, list).unwrap();
            let v: i64 = conn.pragma_query_value(None, "user_version", |r| r.get(0)).unwrap();
            assert_eq!(v as usize, list.len());
        }
    }
}
