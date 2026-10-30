//! Vault repository: typed entries plus an FTS5 index for instant search.
//!
//! The index (`vault_fts`, rowid = entry id) is maintained here in the same
//! transaction as each write. It covers title, tags, body and the non-secret
//! type fields; the `secret` column is never indexed and never returned by
//! list/search — only by `get_secret`.

use rusqlite::types::Value;
use rusqlite::{params, params_from_iter, Connection, Row};
use serde::{Deserialize, Serialize};

use super::{now_ms, Error, Result};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Kind {
    Vm,
    Password,
    ApiKey,
    Command,
    Note,
}

impl Kind {
    fn as_str(self) -> &'static str {
        match self {
            Kind::Vm => "vm",
            Kind::Password => "password",
            Kind::ApiKey => "api_key",
            Kind::Command => "command",
            Kind::Note => "note",
        }
    }

    fn parse(s: &str) -> Kind {
        match s {
            "vm" => Kind::Vm,
            "password" => Kind::Password,
            "api_key" => Kind::ApiKey,
            "command" => Kind::Command,
            _ => Kind::Note,
        }
    }
}

/// A user-defined label/value pair, e.g. "Logs" → "/var/log/app".
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct ExtraField {
    pub label: String,
    pub value: String,
}

/// Non-secret, type-specific fields. Unused ones stay empty.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", default)]
pub struct Fields {
    /// VM: hostname or IP.
    pub host: String,
    /// VM: login user.
    pub user: String,
    /// VM: SSH port (None = default 22).
    pub port: Option<u16>,
    /// VM: path to the private key.
    pub key_path: String,
    /// Password / API key: account name.
    pub username: String,
    /// Password / API key: site or service URL.
    pub url: String,
    /// Any number of extra labelled values (paths, ports, notes…).
    pub extra: Vec<ExtraField>,
}

impl Fields {
    fn trimmed(&self) -> Fields {
        Fields {
            host: self.host.trim().into(),
            user: self.user.trim().into(),
            port: self.port,
            key_path: self.key_path.trim().into(),
            username: self.username.trim().into(),
            url: self.url.trim().into(),
            extra: self
                .extra
                .iter()
                .map(|f| ExtraField { label: f.label.trim().into(), value: f.value.trim().into() })
                .filter(|f| !f.label.is_empty() || !f.value.is_empty())
                .collect(),
        }
    }

    /// Text added to the search index.
    fn search_text(&self) -> String {
        let port = self.port.map(|p| p.to_string()).unwrap_or_default();
        let base = [&self.host, &self.user, &port, &self.key_path, &self.username, &self.url];
        let extra = self.extra.iter().flat_map(|f| [&f.label, &f.value]);
        base.into_iter().chain(extra).filter(|s| !s.is_empty()).map(|s| s.as_str()).collect::<Vec<_>>().join(" ")
    }
}

/// A secret string whose `Debug` output is redacted, so it cannot end up in logs.
#[derive(Clone, Default, Deserialize)]
#[serde(transparent)]
pub struct Secret(pub String);

impl std::fmt::Debug for Secret {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("Secret([redacted])")
    }
}

/// What to do with the secret on create/update.
#[derive(Debug, Clone, Default, Deserialize)]
#[serde(tag = "action", content = "value", rename_all = "snake_case")]
pub enum SecretChange {
    #[default]
    Keep,
    Clear,
    Set(Secret),
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Entry {
    pub id: i64,
    pub kind: Kind,
    pub title: String,
    pub tags: Vec<String>,
    pub body: String,
    pub fields: Fields,
    pub has_secret: bool,
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EntryInput {
    pub kind: Kind,
    pub title: String,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub body: String,
    #[serde(default)]
    pub fields: Fields,
    #[serde(default)]
    pub secret: SecretChange,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(rename_all = "camelCase", default)]
pub struct SearchQuery {
    pub text: String,
    pub kind: Option<Kind>,
    /// Entries must carry every listed tag.
    pub tags: Vec<String>,
    pub limit: Option<u32>,
}

#[derive(Debug, Clone, Serialize)]
pub struct TagCount {
    pub tag: String,
    pub count: i64,
}

const MAX_RESULTS: u32 = 500;
const TAG_SEP: char = '\u{1f}';

const SELECT: &str = "SELECT e.id, e.kind, e.title, e.body, e.fields, e.secret IS NOT NULL,
        e.created_at, e.updated_at,
        (SELECT group_concat(tag, char(31)) FROM vault_tags t WHERE t.entry_id = e.id)";

fn from_row(r: &Row<'_>) -> rusqlite::Result<Entry> {
    let fields: String = r.get(4)?;
    let mut tags: Vec<String> = r
        .get::<_, Option<String>>(8)?
        .map(|s| s.split(TAG_SEP).map(String::from).collect())
        .unwrap_or_default();
    tags.sort();
    Ok(Entry {
        id: r.get(0)?,
        kind: Kind::parse(&r.get::<_, String>(1)?),
        title: r.get(2)?,
        body: r.get(3)?,
        fields: serde_json::from_str(&fields).unwrap_or_default(),
        has_secret: r.get(5)?,
        created_at: r.get(6)?,
        updated_at: r.get(7)?,
        tags,
    })
}

/// Lowercase, strip leading '#', spaces to '-', dedupe, sort.
pub fn normalize_tags(tags: &[String]) -> Vec<String> {
    let mut out: Vec<String> = tags
        .iter()
        .map(|t| t.trim().trim_start_matches('#').trim().to_lowercase().split_whitespace().collect::<Vec<_>>().join("-"))
        .filter(|t| !t.is_empty())
        .map(|t| t.chars().take(40).collect())
        .collect();
    out.sort();
    out.dedup();
    out
}

fn validate(input: &EntryInput) -> Result<()> {
    if input.title.trim().is_empty() {
        return Err(Error::Invalid("title is required".into()));
    }
    if input.kind == Kind::Vm && input.fields.host.trim().is_empty() {
        return Err(Error::Invalid("host / IP is required for a VM".into()));
    }
    if input.fields.port == Some(0) {
        return Err(Error::Invalid("port must be 1-65535".into()));
    }
    Ok(())
}

/// Turn free text into an FTS5 query: every word must match as a prefix.
/// Splitting on non-alphanumerics mirrors the unicode61 tokenizer, so
/// "10.0.3" or "prod-db" find what they look like.
pub(super) fn fts_query(text: &str) -> Option<String> {
    let terms: Vec<String> = text
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .map(|w| format!("\"{w}\"*"))
        .collect();
    (!terms.is_empty()).then(|| terms.join(" "))
}

fn reindex(conn: &Connection, id: i64, title: &str, tags: &[String], body: &str, fields: &Fields) -> Result<()> {
    conn.execute("DELETE FROM vault_fts WHERE rowid = ?1", [id])?;
    conn.execute(
        "INSERT INTO vault_fts (rowid, title, tags, body, extra) VALUES (?1, ?2, ?3, ?4, ?5)",
        params![id, title, tags.join(" "), body, fields.search_text()],
    )?;
    Ok(())
}

fn write_tags(conn: &Connection, id: i64, tags: &[String]) -> Result<()> {
    conn.execute("DELETE FROM vault_tags WHERE entry_id = ?1", [id])?;
    let mut stmt = conn.prepare("INSERT INTO vault_tags (entry_id, tag) VALUES (?1, ?2)")?;
    for tag in tags {
        stmt.execute(params![id, tag])?;
    }
    Ok(())
}

pub fn get(conn: &Connection, id: i64) -> Result<Entry> {
    Ok(conn.query_row(&format!("{SELECT} FROM vault_entries e WHERE e.id = ?1"), [id], from_row)?)
}

pub fn get_secret(conn: &Connection, id: i64) -> Result<Option<Secret>> {
    let s: Option<String> = conn.query_row("SELECT secret FROM vault_entries WHERE id = ?1", [id], |r| r.get(0))?;
    Ok(s.map(Secret))
}

pub fn create(conn: &mut Connection, input: &EntryInput) -> Result<Entry> {
    validate(input)?;
    let tags = normalize_tags(&input.tags);
    let fields = input.fields.trimmed();
    let secret = match &input.secret {
        SecretChange::Set(s) if !s.0.is_empty() => Some(s.0.clone()),
        _ => None,
    };
    let now = now_ms();
    let tx = conn.transaction()?;
    tx.execute(
        "INSERT INTO vault_entries (kind, title, body, fields, secret, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6)",
        params![
            input.kind.as_str(),
            input.title.trim(),
            input.body.trim_end(),
            serde_json::to_string(&fields).expect("fields serialize"),
            secret,
            now
        ],
    )?;
    let id = tx.last_insert_rowid();
    write_tags(&tx, id, &tags)?;
    reindex(&tx, id, input.title.trim(), &tags, input.body.trim_end(), &fields)?;
    tx.commit()?;
    get(conn, id)
}

pub fn update(conn: &mut Connection, id: i64, input: &EntryInput) -> Result<Entry> {
    validate(input)?;
    let tags = normalize_tags(&input.tags);
    let fields = input.fields.trimmed();
    let tx = conn.transaction()?;
    let n = tx.execute(
        "UPDATE vault_entries SET kind = ?1, title = ?2, body = ?3, fields = ?4, updated_at = ?5 WHERE id = ?6",
        params![
            input.kind.as_str(),
            input.title.trim(),
            input.body.trim_end(),
            serde_json::to_string(&fields).expect("fields serialize"),
            now_ms(),
            id
        ],
    )?;
    if n == 0 {
        return Err(Error::NotFound);
    }
    match &input.secret {
        SecretChange::Keep => {}
        SecretChange::Clear => {
            tx.execute("UPDATE vault_entries SET secret = NULL WHERE id = ?1", [id])?;
        }
        SecretChange::Set(s) => {
            let v = (!s.0.is_empty()).then(|| s.0.clone());
            tx.execute("UPDATE vault_entries SET secret = ?1 WHERE id = ?2", params![v, id])?;
        }
    }
    write_tags(&tx, id, &tags)?;
    reindex(&tx, id, input.title.trim(), &tags, input.body.trim_end(), &fields)?;
    tx.commit()?;
    get(conn, id)
}

pub fn delete(conn: &mut Connection, id: i64) -> Result<()> {
    let tx = conn.transaction()?;
    if tx.execute("DELETE FROM vault_entries WHERE id = ?1", [id])? == 0 {
        return Err(Error::NotFound);
    }
    tx.execute("DELETE FROM vault_fts WHERE rowid = ?1", [id])?;
    tx.commit()?;
    Ok(())
}

/// Ranked full-text search (title > tags > fields > body) with optional type
/// and tag filters. Empty text lists everything, most recently updated first.
pub fn search(conn: &Connection, q: &SearchQuery) -> Result<Vec<Entry>> {
    let mut args: Vec<Value> = Vec::new();
    let mut sql = String::from(SELECT);
    let fts = fts_query(&q.text);
    if let Some(m) = &fts {
        sql.push_str(" FROM vault_fts JOIN vault_entries e ON e.id = vault_fts.rowid WHERE vault_fts MATCH ?");
        args.push(Value::Text(m.clone()));
    } else {
        sql.push_str(" FROM vault_entries e WHERE 1");
    }
    if let Some(kind) = q.kind {
        sql.push_str(" AND e.kind = ?");
        args.push(Value::Text(kind.as_str().into()));
    }
    for tag in normalize_tags(&q.tags) {
        sql.push_str(" AND EXISTS (SELECT 1 FROM vault_tags t WHERE t.entry_id = e.id AND t.tag = ?)");
        args.push(Value::Text(tag));
    }
    sql.push_str(if fts.is_some() {
        " ORDER BY bm25(vault_fts, 10.0, 5.0, 1.0, 3.0), e.updated_at DESC"
    } else {
        " ORDER BY e.updated_at DESC, e.id DESC"
    });
    sql.push_str(" LIMIT ?");
    args.push(Value::Integer(q.limit.unwrap_or(MAX_RESULTS).min(MAX_RESULTS) as i64));

    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt.query_map(params_from_iter(args), from_row)?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

/// Rebuild the search index from the entries (after importing old data).
pub fn rebuild_index(conn: &Connection) -> Result<()> {
    conn.execute("DELETE FROM vault_fts", [])?;
    let entries: Vec<Entry> = {
        let mut stmt = conn.prepare(&format!("{SELECT} FROM vault_entries e"))?;
        let rows = stmt.query_map([], from_row)?;
        rows.collect::<rusqlite::Result<_>>()?
    };
    for e in entries {
        reindex(conn, e.id, &e.title, &e.tags, &e.body, &e.fields)?;
    }
    Ok(())
}

pub fn count(conn: &Connection) -> Result<i64> {
    Ok(conn.query_row("SELECT COUNT(*) FROM vault_entries", [], |r| r.get(0))?)
}

pub fn tags(conn: &Connection) -> Result<Vec<TagCount>> {
    let mut stmt = conn.prepare("SELECT tag, COUNT(*) FROM vault_tags GROUP BY tag ORDER BY COUNT(*) DESC, tag")?;
    let rows = stmt.query_map([], |r| Ok(TagCount { tag: r.get(0)?, count: r.get(1)? }))?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::Db;

    fn entry(kind: Kind, title: &str) -> EntryInput {
        EntryInput {
            kind,
            title: title.into(),
            tags: vec![],
            body: String::new(),
            fields: Fields::default(),
            secret: SecretChange::Keep,
        }
    }

    fn vm(title: &str, host: &str, tags: &[&str]) -> EntryInput {
        EntryInput {
            fields: Fields { host: host.into(), user: "ubuntu".into(), port: Some(2222), ..Default::default() },
            tags: tags.iter().map(|t| t.to_string()).collect(),
            ..entry(Kind::Vm, title)
        }
    }

    fn titles(v: Vec<Entry>) -> Vec<String> {
        v.into_iter().map(|e| e.title).collect()
    }

    fn q(text: &str) -> SearchQuery {
        SearchQuery { text: text.into(), ..Default::default() }
    }

    fn seed(c: &mut Connection) -> Result<()> {
        create(c, &vm("Prod database", "10.0.3.17", &["prod", "db"]))?;
        create(c, &vm("Staging web", "staging.example.internal", &["staging"]))?;
        create(c, &EntryInput { body: "docker compose logs -f --tail=100".into(), tags: vec!["docker".into()], ..entry(Kind::Command, "Tail compose logs") })?;
        create(
            c,
            &EntryInput {
                fields: Fields { username: "mohit".into(), url: "https://github.com".into(), ..Default::default() },
                secret: SecretChange::Set(Secret("hunter2-SuperSecret".into())),
                tags: vec!["#Dev".into()],
                ..entry(Kind::Password, "GitHub")
            },
        )?;
        create(c, &EntryInput { body: "Remember the database backup runs at 02:00".into(), ..entry(Kind::Note, "Backups") })?;
        Ok(())
    }

    #[test]
    fn prefix_search_across_title_fields_and_body() {
        let db = Db::open_in_memory_with(crate::db::migrations::VAULT).unwrap();
        db.with(|c| {
            seed(c)?;
            assert_eq!(titles(search(c, &q("prod"))?), ["Prod database"]);
            assert_eq!(titles(search(c, &q("10.0.3"))?), ["Prod database"], "IP fragments match");
            assert_eq!(titles(search(c, &q("staging.exam"))?), ["Staging web"], "host prefix");
            assert_eq!(titles(search(c, &q("compose tail"))?), ["Tail compose logs"], "all words, any order");
            assert_eq!(titles(search(c, &q("mohit"))?), ["GitHub"], "username field");
            assert!(search(c, &q("nonexistentword"))?.is_empty());
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn title_matches_rank_above_body_matches() {
        let db = Db::open_in_memory_with(crate::db::migrations::VAULT).unwrap();
        db.with(|c| {
            seed(c)?;
            // "database" is in one title and one note body.
            assert_eq!(titles(search(c, &q("database"))?), ["Prod database", "Backups"]);
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn secrets_are_not_searchable_or_listed() {
        let db = Db::open_in_memory_with(crate::db::migrations::VAULT).unwrap();
        db.with(|c| {
            seed(c)?;
            assert!(search(c, &q("hunter2"))?.is_empty());
            assert!(search(c, &q("SuperSecret"))?.is_empty());
            let gh = &search(c, &q("github"))?[0];
            assert!(gh.has_secret);
            assert_eq!(get_secret(c, gh.id)?.unwrap().0, "hunter2-SuperSecret");
            assert_eq!(format!("{:?}", get_secret(c, gh.id)?), "Some(Secret([redacted]))");
            // The FTS shadow tables must not contain the secret either.
            let token_hits: i64 = c.query_row("SELECT COUNT(*) FROM vault_fts WHERE vault_fts MATCH 'hunter2'", [], |r| r.get(0))?;
            let text_hits: i64 = c.query_row(
                "SELECT COUNT(*) FROM vault_fts WHERE (title || tags || body || extra) LIKE '%hunter2%'",
                [],
                |r| r.get(0),
            )?;
            assert_eq!((token_hits, text_hits), (0, 0));
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn type_and_tag_filters() {
        let db = Db::open_in_memory_with(crate::db::migrations::VAULT).unwrap();
        db.with(|c| {
            seed(c)?;
            let vms = search(c, &SearchQuery { kind: Some(Kind::Vm), ..Default::default() })?;
            assert_eq!(vms.len(), 2);
            let prod = search(c, &SearchQuery { tags: vec!["prod".into()], ..Default::default() })?;
            assert_eq!(titles(prod), ["Prod database"]);
            let both = search(c, &SearchQuery { tags: vec!["prod".into(), "db".into()], ..Default::default() })?;
            assert_eq!(both.len(), 1);
            let none = search(c, &SearchQuery { tags: vec!["prod".into(), "staging".into()], ..Default::default() })?;
            assert!(none.is_empty());
            let combo = search(c, &SearchQuery { text: "web".into(), kind: Some(Kind::Command), ..Default::default() })?;
            assert!(combo.is_empty(), "text + kind filter combine");
            assert_eq!(search(c, &SearchQuery { tags: vec!["DEV".into()], ..Default::default() })?.len(), 1, "tags are case-insensitive");
            let counts: Vec<_> = tags(c)?.into_iter().map(|t| (t.tag, t.count)).collect();
            assert!(counts.contains(&("prod".into(), 1)) && counts.contains(&("dev".into(), 1)));
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn update_reindexes_and_delete_unindexes() {
        let db = Db::open_in_memory_with(crate::db::migrations::VAULT).unwrap();
        db.with(|c| {
            let id = create(c, &vm("Old name", "1.2.3.4", &["a"]))?.id;
            update(c, id, &vm("Renamed box", "5.6.7.8", &["b"]))?;
            assert!(search(c, &q("old"))?.is_empty());
            assert!(search(c, &q("1.2.3.4"))?.is_empty());
            assert_eq!(titles(search(c, &q("renamed 5.6"))?), ["Renamed box"]);
            assert_eq!(search(c, &SearchQuery { tags: vec!["b".into()], ..Default::default() })?.len(), 1);
            delete(c, id)?;
            assert!(search(c, &q("renamed"))?.is_empty());
            let fts_rows: i64 = c.query_row("SELECT COUNT(*) FROM vault_fts", [], |r| r.get(0))?;
            let tag_rows: i64 = c.query_row("SELECT COUNT(*) FROM vault_tags", [], |r| r.get(0))?;
            assert_eq!((fts_rows, tag_rows), (0, 0));
            assert!(matches!(delete(c, id), Err(Error::NotFound)));
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn extra_fields_are_saved_trimmed_and_searchable() {
        let db = Db::open_in_memory_with(crate::db::migrations::VAULT).unwrap();
        db.with(|c| {
            let mut input = vm("App server", "10.1.1.1", &[]);
            input.fields.extra = vec![
                ExtraField { label: " Logs ".into(), value: " /var/log/myapp/current.log ".into() },
                ExtraField { label: "".into(), value: "".into() }, // dropped
                ExtraField { label: "Deploy dir".into(), value: "/srv/releases".into() },
            ];
            let e = create(c, &input)?;
            assert_eq!(e.fields.extra.len(), 2);
            assert_eq!(e.fields.extra[0], ExtraField { label: "Logs".into(), value: "/var/log/myapp/current.log".into() });
            assert_eq!(titles(search(c, &q("myapp current"))?), ["App server"]);
            assert_eq!(titles(search(c, &q("releases"))?), ["App server"]);
            assert_eq!(titles(search(c, &q("deploy"))?), ["App server"], "labels are searchable too");
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn secret_keep_set_clear() {
        let db = Db::open_in_memory_with(crate::db::migrations::VAULT).unwrap();
        db.with(|c| {
            let mut input = EntryInput { secret: SecretChange::Set(Secret("k1".into())), ..entry(Kind::ApiKey, "OpenWeather") };
            let id = create(c, &input)?.id;
            input.secret = SecretChange::Keep;
            update(c, id, &input)?;
            assert_eq!(get_secret(c, id)?.unwrap().0, "k1");
            input.secret = SecretChange::Set(Secret("k2".into()));
            update(c, id, &input)?;
            assert_eq!(get_secret(c, id)?.unwrap().0, "k2");
            input.secret = SecretChange::Clear;
            assert!(!update(c, id, &input)?.has_secret);
            assert!(get_secret(c, id)?.is_none());
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn validation_and_query_building() {
        let db = Db::open_in_memory_with(crate::db::migrations::VAULT).unwrap();
        db.with(|c| {
            assert!(matches!(create(c, &entry(Kind::Note, "  ")), Err(Error::Invalid(_))));
            assert!(matches!(create(c, &entry(Kind::Vm, "no host")), Err(Error::Invalid(_))));
            let mut bad_port = vm("x", "h", &[]);
            bad_port.fields.port = Some(0);
            assert!(matches!(create(c, &bad_port), Err(Error::Invalid(_))));
            // FTS syntax characters in user input must not break the query.
            for tricky in ["\"", "AND OR NOT", "foo*", "(a)", "-x", "col:val", "😀"] {
                search(c, &q(tricky))?;
            }
            Ok(())
        })
        .unwrap();
        assert_eq!(fts_query("  "), None);
        assert_eq!(fts_query("prod-db 10.0").unwrap(), "\"prod\"* \"db\"* \"10\"* \"0\"*");
        assert_eq!(normalize_tags(&["#Prod".into(), "prod".into(), " my tag ".into(), "".into()]), ["my-tag", "prod"]);
    }
}
