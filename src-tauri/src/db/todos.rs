//! Todo repository.

use rusqlite::{params, Connection, OptionalExtension, Row};
use serde::{Deserialize, Serialize};

use super::{now_ms, Error, Result};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    Open,
    InProgress,
    Done,
}

impl Status {
    fn as_str(self) -> &'static str {
        match self {
            Status::Open => "open",
            Status::InProgress => "in_progress",
            Status::Done => "done",
        }
    }

    pub(super) fn parse(s: &str) -> Status {
        match s {
            "in_progress" => Status::InProgress,
            "done" => Status::Done,
            _ => Status::Open,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Todo {
    pub id: i64,
    pub title: String,
    pub notes: String,
    pub due: Option<String>,
    pub priority: u8,
    pub project: String,
    pub status: Status,
    pub position: f64,
    pub created_at: i64,
    pub completed_at: Option<i64>,
    /// When the alarm will ring (unix ms), if armed.
    pub remind_at: Option<i64>,
}

/// Fields the UI may set. Used for both create and full update.
#[derive(Debug, Clone, Default, Deserialize)]
#[serde(rename_all = "camelCase", default)]
pub struct TodoInput {
    pub title: String,
    pub notes: String,
    pub due: Option<String>,
    pub priority: u8,
    pub project: String,
    pub status: Option<Status>,
    /// Ring at the due time (only for due dates with a time). Default: on.
    pub alarm: Option<bool>,
}

const COLUMNS: &str = "id, title, notes, due, priority, project, status, position, created_at, completed_at, remind_at";

fn from_row(r: &Row<'_>) -> rusqlite::Result<Todo> {
    Ok(Todo {
        id: r.get(0)?,
        title: r.get(1)?,
        notes: r.get(2)?,
        due: r.get(3)?,
        priority: r.get(4)?,
        project: r.get(5)?,
        status: Status::parse(&r.get::<_, String>(6)?),
        position: r.get(7)?,
        created_at: r.get(8)?,
        completed_at: r.get(9)?,
        remind_at: r.get(10)?,
    })
}

/// Unix ms for a local `YYYY-MM-DDTHH:MM`, or None for date-only / invalid.
pub fn local_due_ms(due: &str) -> Option<i64> {
    use chrono::{Local, NaiveDateTime, TimeZone};
    let naive = NaiveDateTime::parse_from_str(due, "%Y-%m-%dT%H:%M").ok()?;
    // `earliest` resolves DST overlaps; a time skipped by DST has no alarm.
    Local.from_local_datetime(&naive).earliest().map(|t| t.timestamp_millis())
}

/// Alarm time for a due string, only if it is still in the future.
fn arm(due: Option<&str>, now: i64) -> Option<i64> {
    due.and_then(local_due_ms).filter(|&t| t > now)
}

/// Normalised, validated copy of the input.
fn clean(input: &TodoInput) -> Result<TodoInput> {
    let title = input.title.trim();
    if title.is_empty() {
        return Err(Error::Invalid("title is required".into()));
    }
    if input.priority > 3 {
        return Err(Error::Invalid("priority must be 0-3".into()));
    }
    let due = match input.due.as_deref().map(str::trim) {
        None | Some("") => None,
        Some(d) if valid_due(d) => Some(d.to_string()),
        Some(d) => return Err(Error::Invalid(format!("invalid due date: {d}"))),
    };
    Ok(TodoInput {
        title: title.to_string(),
        notes: input.notes.trim_end().to_string(),
        due,
        priority: input.priority,
        project: input.project.trim().trim_start_matches('#').to_string(),
        status: input.status,
        alarm: input.alarm,
    })
}

/// `YYYY-MM-DD` with an optional `THH:MM`.
fn valid_due(s: &str) -> bool {
    let b = s.as_bytes();
    let digits = |r: std::ops::Range<usize>| r.into_iter().all(|i| b[i].is_ascii_digit());
    let date_ok = b.len() >= 10 && digits(0..4) && b[4] == b'-' && digits(5..7) && b[7] == b'-' && digits(8..10) && {
        let m: u32 = s[5..7].parse().unwrap_or(0);
        let d: u32 = s[8..10].parse().unwrap_or(0);
        (1..=12).contains(&m) && (1..=31).contains(&d)
    };
    match b.len() {
        10 => date_ok,
        16 => {
            date_ok && b[10] == b'T' && digits(11..13) && b[13] == b':' && digits(14..16) && {
                let h: u32 = s[11..13].parse().unwrap_or(99);
                let min: u32 = s[14..16].parse().unwrap_or(99);
                h < 24 && min < 60
            }
        }
        _ => false,
    }
}

pub fn list(conn: &Connection) -> Result<Vec<Todo>> {
    let mut stmt = conn.prepare(&format!("SELECT {COLUMNS} FROM todos ORDER BY position, id"))?;
    let rows = stmt.query_map([], from_row)?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

pub fn get(conn: &Connection, id: i64) -> Result<Todo> {
    Ok(conn.query_row(&format!("SELECT {COLUMNS} FROM todos WHERE id = ?1"), [id], from_row)?)
}

/// New todos go to the top of the list.
pub fn create(conn: &Connection, input: &TodoInput) -> Result<Todo> {
    let t = clean(input)?;
    let status = t.status.unwrap_or(Status::Open);
    let now = now_ms();
    let top: Option<f64> = conn.query_row("SELECT MIN(position) FROM todos", [], |r| r.get(0)).optional()?.flatten();
    let remind_at = (t.alarm.unwrap_or(true) && status != Status::Done).then(|| arm(t.due.as_deref(), now)).flatten();
    conn.execute(
        "INSERT INTO todos (title, notes, due, priority, project, status, position, created_at, completed_at, remind_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
        params![
            t.title,
            t.notes,
            t.due,
            t.priority,
            t.project,
            status.as_str(),
            top.map_or(0.0, |p| p - 1.0),
            now,
            (status == Status::Done).then_some(now),
            remind_at,
        ],
    )?;
    get(conn, conn.last_insert_rowid())
}

pub fn update(conn: &Connection, id: i64, input: &TodoInput) -> Result<Todo> {
    let t = clean(input)?;
    let existing = get(conn, id)?;
    let status = t.status.unwrap_or(existing.status);
    // Re-arm only when the due time changes (or the alarm is switched back on),
    // so saving an unrelated edit never makes an already-rung alarm ring again.
    let remind_at = match t.alarm {
        Some(false) => None,
        _ if t.due != existing.due => arm(t.due.as_deref(), now_ms()),
        Some(true) if existing.remind_at.is_none() => arm(t.due.as_deref(), now_ms()),
        _ => existing.remind_at,
    };
    conn.execute(
        "UPDATE todos SET title = ?1, notes = ?2, due = ?3, priority = ?4, project = ?5, remind_at = ?6 WHERE id = ?7",
        params![t.title, t.notes, t.due, t.priority, t.project, remind_at, id],
    )?;
    set_status(conn, id, status)
}

/// Changes status, maintaining `completed_at`.
pub fn set_status(conn: &Connection, id: i64, status: Status) -> Result<Todo> {
    let n = conn.execute(
        "UPDATE todos SET status = ?1,
            completed_at = CASE WHEN ?1 = 'done' THEN COALESCE(completed_at, ?2) ELSE NULL END,
            remind_at = CASE WHEN ?1 = 'done' THEN NULL ELSE remind_at END
         WHERE id = ?3",
        params![status.as_str(), now_ms(), id],
    )?;
    if n == 0 {
        return Err(Error::NotFound);
    }
    get(conn, id)
}

pub fn delete(conn: &Connection, id: i64) -> Result<()> {
    match conn.execute("DELETE FROM todos WHERE id = ?1", [id])? {
        0 => Err(Error::NotFound),
        _ => Ok(()),
    }
}

/// Open todos whose alarm time has come. Each is disarmed as it is returned,
/// so an alarm rings once (snoozing re-arms it).
pub fn take_due_alarms(conn: &mut Connection, now: i64) -> Result<Vec<Todo>> {
    let tx = conn.transaction()?;
    let due: Vec<Todo> = {
        let mut stmt = tx.prepare(&format!(
            "SELECT {COLUMNS} FROM todos WHERE remind_at IS NOT NULL AND remind_at <= ?1 AND status != 'done' ORDER BY remind_at"
        ))?;
        let rows = stmt.query_map([now], from_row)?;
        rows.collect::<rusqlite::Result<_>>()?
    };
    tx.execute("UPDATE todos SET remind_at = NULL WHERE remind_at IS NOT NULL AND remind_at <= ?1", [now])?;
    tx.commit()?;
    Ok(due)
}

/// Open todos due on or before `today` (the panel's "Today" list) with no
/// alarm still to ring, oldest due first. For the evening reminder.
pub fn open_without_alarm(conn: &Connection, today: &str) -> Result<Vec<Todo>> {
    let mut stmt = conn.prepare(&format!(
        "SELECT {COLUMNS} FROM todos WHERE status != 'done' AND remind_at IS NULL AND due IS NOT NULL AND substr(due, 1, 10) <= ?1 ORDER BY due"
    ))?;
    let rows = stmt.query_map([today], from_row)?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

pub fn snooze(conn: &Connection, id: i64, until: i64) -> Result<Todo> {
    if conn.execute("UPDATE todos SET remind_at = ?1 WHERE id = ?2 AND status != 'done'", params![until, id])? == 0 {
        return Err(Error::NotFound);
    }
    get(conn, id)
}

/// Persist a new order: `ids[i]` gets position `i`. Ids not listed keep theirs.
pub fn reorder(conn: &mut Connection, ids: &[i64]) -> Result<()> {
    let tx = conn.transaction()?;
    {
        let mut stmt = tx.prepare("UPDATE todos SET position = ?1 WHERE id = ?2")?;
        for (i, id) in ids.iter().enumerate() {
            stmt.execute(params![i as f64, id])?;
        }
    }
    tx.commit()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::Db;

    fn input(title: &str) -> TodoInput {
        TodoInput { title: title.into(), ..Default::default() }
    }

    #[test]
    fn create_list_and_order_newest_first() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            create(c, &input("first"))?;
            create(c, &input("second"))?;
            let titles: Vec<_> = list(c)?.into_iter().map(|t| t.title).collect();
            assert_eq!(titles, ["second", "first"]);
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn validates_input() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            assert!(matches!(create(c, &input("   ")), Err(Error::Invalid(_))));
            for bad in ["2026-13-01", "tomorrow", "2026-10-29T25:00", "2026-1-1"] {
                let t = TodoInput { due: Some(bad.into()), ..input("x") };
                assert!(matches!(create(c, &t), Err(Error::Invalid(_))), "{bad} should be rejected");
            }
            for good in ["2026-10-29", "2026-10-29T09:30", ""] {
                let t = TodoInput { due: Some(good.into()), ..input("x") };
                assert!(create(c, &t).is_ok(), "{good} should be accepted");
            }
            let t = TodoInput { project: " #home ".into(), ..input("  trim me  ") };
            let saved = create(c, &t)?;
            assert_eq!((saved.title.as_str(), saved.project.as_str()), ("trim me", "home"));
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn status_tracks_completed_at() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let t = create(c, &input("task"))?;
            assert_eq!(t.completed_at, None);
            let done = set_status(c, t.id, Status::Done)?;
            assert!(done.completed_at.is_some());
            // Completing again keeps the original timestamp.
            assert_eq!(set_status(c, t.id, Status::Done)?.completed_at, done.completed_at);
            assert_eq!(set_status(c, t.id, Status::Open)?.completed_at, None);
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn update_keeps_status_unless_given() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let t = create(c, &input("a"))?;
            set_status(c, t.id, Status::InProgress)?;
            let u = update(c, t.id, &TodoInput { priority: 3, notes: "n".into(), ..input("b") })?;
            assert_eq!((u.title.as_str(), u.priority, u.status), ("b", 3, Status::InProgress));
            let u = update(c, t.id, &TodoInput { status: Some(Status::Done), ..input("b") })?;
            assert!(u.completed_at.is_some());
            Ok(())
        })
        .unwrap();
    }

    fn timed(title: &str, offset_min: i64) -> TodoInput {
        let t = chrono::Local::now() + chrono::Duration::minutes(offset_min);
        TodoInput { due: Some(t.format("%Y-%m-%dT%H:%M").to_string()), ..input(title) }
    }

    #[test]
    fn evening_reminder_picks_todays_open_todos_without_alarm() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let day = today();
            create(c, &TodoInput { due: Some(day.clone()), ..input("today") })?;
            create(c, &TodoInput { due: Some("2000-01-01".into()), ..input("overdue") })?;
            create(c, &TodoInput { due: Some(format!("{day}T00:01")), alarm: Some(false), ..input("muted") })?;
            create(c, &timed("has alarm", 30))?;
            create(c, &TodoInput { due: Some("2099-01-01".into()), ..input("later") })?;
            create(c, &input("no date"))?;
            let done = create(c, &TodoInput { due: Some(day.clone()), ..input("done") })?;
            set_status(c, done.id, Status::Done)?;
            let mut titles: Vec<_> = open_without_alarm(c, &day)?.into_iter().map(|t| t.title).collect();
            titles.sort();
            assert_eq!(titles, ["muted", "overdue", "today"]);
            Ok(())
        })
        .unwrap();
    }

    fn today() -> String {
        chrono::Local::now().format("%Y-%m-%d").to_string()
    }

    #[test]
    fn alarms_arm_fire_once_and_snooze() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let future = create(c, &timed("future", 30))?;
            assert!(future.remind_at.is_some(), "timed due in the future arms the alarm");
            assert!(create(c, &timed("past", -30))?.remind_at.is_none(), "past times never ring");
            let date_only = TodoInput { due: Some("2099-01-01".into()), ..input("date only") };
            assert!(create(c, &date_only)?.remind_at.is_none(), "no time, no alarm");
            let off = TodoInput { alarm: Some(false), ..timed("muted", 30) };
            assert!(create(c, &off)?.remind_at.is_none());

            let at = future.remind_at.unwrap();
            assert!(take_due_alarms(c, at - 1)?.is_empty());
            assert_eq!(take_due_alarms(c, at)?.len(), 1);
            assert!(take_due_alarms(c, at + 60_000)?.is_empty(), "rings only once");

            snooze(c, future.id, at + 600_000)?;
            assert_eq!(take_due_alarms(c, at + 600_000)?.len(), 1, "snooze re-arms");

            // Unrelated edits do not re-arm; changing the time does.
            let edited = update(c, future.id, &TodoInput { notes: "x".into(), ..timed("future", 30) })?;
            assert!(edited.remind_at.is_none());
            let moved = update(c, future.id, &timed("future", 45))?;
            assert!(moved.remind_at.is_some());
            assert!(set_status(c, moved.id, Status::Done)?.remind_at.is_none(), "done disarms");
            Ok(())
        })
        .unwrap();
    }

    #[test]
    fn local_due_conversion() {
        let ms = local_due_ms("2026-10-29T17:00").unwrap();
        let back = chrono::DateTime::from_timestamp_millis(ms).unwrap().with_timezone(&chrono::Local);
        assert_eq!(back.format("%Y-%m-%dT%H:%M").to_string(), "2026-10-29T17:00");
        assert!(local_due_ms("2026-10-29").is_none());
    }

    #[test]
    fn reorder_and_delete() {
        let db = Db::open_in_memory().unwrap();
        db.with(|c| {
            let a = create(c, &input("a"))?.id;
            let b = create(c, &input("b"))?.id;
            let d = create(c, &input("d"))?.id;
            reorder(c, &[a, d, b])?;
            let ids: Vec<_> = list(c)?.into_iter().map(|t| t.id).collect();
            assert_eq!(ids, [a, d, b]);
            delete(c, d)?;
            assert!(matches!(delete(c, d), Err(Error::NotFound)));
            assert!(matches!(get(c, d), Err(Error::NotFound)));
            assert_eq!(list(c)?.len(), 2);
            Ok(())
        })
        .unwrap();
    }
}
