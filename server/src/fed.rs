//! Federation: homes (separate databases) linked by a team-to-team request
//! forward that link's events and messages to each other over HTTP
//! (`POST /fed`). Deliveries go through the `outbox` collection, so they
//! survive restarts and wait while the other home is offline.
//!
//! Each link carries a random `fedToken` both homes store; every delivery
//! must present it. Message bodies are ciphertext the servers can't read.

use std::sync::Arc;
use std::time::Duration;

use axum::extract::State;
use axum::http::StatusCode;
use axum::Json;
use mongodb::bson::DateTime;
use serde::{Deserialize, Serialize};
use tokio::io::{AsyncReadExt, AsyncWriteExt};

use crate::protocol::{self as p, LinkInfo, LinkKind, LinkState, ServerMsg, Share, TeamRef};
use crate::rooms;
use crate::store::{LinkDoc, Store};
use crate::App;

const HTTP_TIMEOUT: Duration = Duration::from_secs(8);
const JANITOR_EVERY: Duration = Duration::from_secs(30);

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Envelope {
    pub link_id: String,
    pub token: String,
    /// The sending home.
    pub home: String,
    pub event: Event,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "camelCase", rename_all_fields = "camelCase")]
pub enum Event {
    Request { link: LinkInfo },
    Respond { accept: bool, team: TeamRef, share: Option<Share>, expires_at: Option<i64> },
    Members { team: TeamRef },
    Message { message: FedMessage },
    Release { to_peer: String },
    Lock,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FedMessage {
    pub conversation_id: String,
    pub from: String,
    pub client_msg_id: String,
    pub body: String,
    pub created_at: i64,
}

/// Queue `event` for the other home(s) of `link`.
pub async fn send(store: &Store, link: &LinkDoc, event: Event) {
    let payload = Envelope { link_id: link.id.clone(), token: link.fed_token.clone(), home: store.home.clone(), event };
    let json = serde_json::to_string(&payload).expect("serializes");
    for side in ['a', 'b'] {
        let team = link.team(side);
        if team.home == store.home {
            continue;
        }
        if team.servers.is_empty() {
            eprintln!("chat: no server address for team {} of link {}; can't forward", team.name, link.id);
            continue;
        }
        if let Err(e) = store.enqueue(&team.servers, &json).await {
            eprintln!("chat: can't queue a delivery: {e}");
        }
    }
}

/// Push the link's current state to its local members.
pub async fn push_link(app: &App, store: &Store, link: &LinkDoc) {
    let to = rooms::link_local_devices(store, link).await;
    app.deliver(&to, &ServerMsg::Link { link: link.info() }.to_json(), None).await;
}

async fn remember_members(app: &App, store: &Store, link: &LinkDoc, team: &TeamRef) {
    let to = rooms::link_local_devices(store, link).await;
    for m in &team.members {
        if !p::is_key(&m.device) || !p::is_key(&m.dh_pub) {
            continue;
        }
        if let Ok(u) = store.upsert_foreign_user(m, &link.id).await {
            app.deliver(&to, &ServerMsg::User { user: u.info(false) }.to_json(), None).await;
        }
    }
}

fn check_team(t: &TeamRef) -> bool {
    p::check_team_ref(t).is_ok() && t.members.len() <= 500
}

pub async fn receive(State(app): State<Arc<App>>, Json(env): Json<Envelope>) -> StatusCode {
    let Some(store) = app.store() else { return StatusCode::SERVICE_UNAVAILABLE };
    if !p::is_id(&env.link_id) || !p::is_id(&env.token) || !p::is_id(&env.home) || env.home == store.home {
        return StatusCode::BAD_REQUEST;
    }
    match handle(&app, &store, env).await {
        Ok(()) => StatusCode::OK,
        Err(code) => code,
    }
}

async fn handle(app: &App, store: &Store, env: Envelope) -> Result<(), StatusCode> {
    let db = |e: mongodb::error::Error| {
        eprintln!("chat: federation store error: {e}");
        StatusCode::SERVICE_UNAVAILABLE
    };
    if let Event::Request { link } = env.event {
        // A team on another home asks one of ours.
        if link.id != env.link_id || link.a.home != env.home || link.b.home != store.home || !check_team(&link.a) {
            return Err(StatusCode::BAD_REQUEST);
        }
        if let Some(existing) = store.link(&link.id).await.map_err(db)? {
            return if crate::ct_eq(existing.fed_token.as_bytes(), env.token.as_bytes()) { Ok(()) } else { Err(StatusCode::FORBIDDEN) };
        }
        let ours = store.team(&link.b.id).await.map_err(db)?.ok_or(StatusCode::NOT_FOUND)?;
        let servers = store.live_servers().await.unwrap_or_else(|_| app.public_urls.clone());
        let b = TeamRef {
            id: ours.id.clone(),
            name: ours.name.clone(),
            dh_pub: ours.dh_pub.clone(),
            home: store.home.clone(),
            servers,
            members: rooms::member_list(store, &ours.id).await,
        };
        let valid = link.share_a.own.as_deref().is_none_or(p::check_blob) && link.share_a.to_peer.as_deref().is_none_or(p::check_blob);
        if !valid {
            return Err(StatusCode::BAD_REQUEST);
        }
        let now = DateTime::now();
        let doc = LinkDoc {
            id: link.id.clone(),
            kind: link.kind,
            state: LinkState::Pending,
            a: link.a.clone(),
            b,
            hours: link.hours.map(|h| h.clamp(1, p::MAX_TEMP_HOURS)),
            expires_at: None,
            retention_days: link.retention_days.map(|d| d.min(p::MAX_RETENTION_DAYS)),
            purge_at: None,
            share_a: link.share_a,
            share_b: Share::default(),
            fed_token: env.token,
            created_at: now,
            updated_at: now,
        };
        if store.insert_link(&doc).await.map_err(db)? {
            remember_members(app, store, &doc, &doc.a).await;
            push_link(app, store, &doc).await;
        }
        return Ok(());
    }

    let mut link = store.link(&env.link_id).await.map_err(db)?.ok_or(StatusCode::NOT_FOUND)?;
    if !crate::ct_eq(link.fed_token.as_bytes(), env.token.as_bytes()) {
        return Err(StatusCode::FORBIDDEN);
    }
    let foreign = ['a', 'b'].into_iter().find(|s| link.team(*s).home == env.home && !rooms::is_local(store, &link, *s));
    let Some(foreign) = foreign else { return Err(StatusCode::FORBIDDEN) };

    match env.event {
        Event::Request { .. } => unreachable!("handled above"),
        Event::Respond { accept, team, share, expires_at } => {
            if foreign != 'b' || link.state != LinkState::Pending || team.id != link.b.id || !check_team(&team) {
                return Err(StatusCode::CONFLICT);
            }
            if share.as_ref().is_some_and(|s| !p::check_share(s)) {
                return Err(StatusCode::BAD_REQUEST);
            }
            link.b = TeamRef { home: link.b.home.clone(), ..team };
            link.state = if accept { LinkState::Active } else { LinkState::Declined };
            if accept && link.kind == LinkKind::Temp {
                let hours = link.hours.unwrap_or(1) as i64;
                let latest = DateTime::now().timestamp_millis() + hours * 3_600_000;
                link.expires_at = Some(DateTime::from_millis(expires_at.unwrap_or(latest).min(latest)));
            }
            link.share_b = share.unwrap_or_default();
            store.save_link(&mut link).await.map_err(db)?;
            let b = link.b.clone();
            remember_members(app, store, &link, &b).await;
            push_link(app, store, &link).await;
        }
        Event::Members { team } => {
            if team.id != link.team(foreign).id || !check_team(&team) {
                return Err(StatusCode::BAD_REQUEST);
            }
            let home = link.team(foreign).home.clone();
            *link.team_mut(foreign) = TeamRef { home, ..team.clone() };
            store.save_link(&mut link).await.map_err(db)?;
            remember_members(app, store, &link, &team).await;
            push_link(app, store, &link).await;
        }
        Event::Message { message: m } => {
            if !p::check_client_msg_id(&m.client_msg_id) || p::check_body(&m.body).is_err() || !p::is_key(&m.from) {
                return Err(StatusCode::BAD_REQUEST);
            }
            let room = rooms::incoming(store, &m.conversation_id, &m.from, &link).await.ok_or(StatusCode::FORBIDDEN)?;
            let at = DateTime::from_millis(m.created_at.clamp(0, DateTime::now().timestamp_millis() + 60_000));
            let (doc, is_new) =
                store.append(&room.id, &room.dm_members, &m.from, &m.client_msg_id, &m.body, Some(at)).await.map_err(db)?;
            if is_new {
                let frame = ServerMsg::Message { message: doc.into() }.to_json();
                app.deliver(&room.local, &frame, None).await;
            }
        }
        Event::Release { to_peer } => {
            if link.state != LinkState::Archived || !p::check_blob(&to_peer) {
                return Err(StatusCode::CONFLICT);
            }
            link.share_mut(foreign).to_peer = Some(to_peer);
            store.save_link(&mut link).await.map_err(db)?;
            push_link(app, store, &link).await;
        }
        Event::Lock => {
            link.share_a.to_peer = None;
            link.share_b.to_peer = None;
            store.save_link(&mut link).await.map_err(db)?;
            push_link(app, store, &link).await;
        }
    }
    Ok(())
}

enum Outcome {
    Delivered,
    /// The other home refused it for good (unknown link, bad token…).
    Rejected(u16),
    Retry(String),
}

async fn post(url: &str, body: &str) -> Outcome {
    let Some(host) = url.strip_prefix("http://") else { return Outcome::Rejected(0) };
    let attempt = async {
        let mut sock = tokio::net::TcpStream::connect(host).await.map_err(|e| e.to_string())?;
        let req = format!(
            "POST /fed HTTP/1.1\r\nHost: {host}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        );
        sock.write_all(req.as_bytes()).await.map_err(|e| e.to_string())?;
        let mut head = vec![0u8; 64];
        let n = sock.read(&mut head).await.map_err(|e| e.to_string())?;
        let line = String::from_utf8_lossy(&head[..n]);
        line.split_whitespace().nth(1).and_then(|c| c.parse::<u16>().ok()).ok_or_else(|| "bad HTTP reply".to_string())
    };
    match tokio::time::timeout(HTTP_TIMEOUT, attempt).await {
        Ok(Ok(code)) if (200..300).contains(&code) => Outcome::Delivered,
        Ok(Ok(code)) if matches!(code, 400 | 403 | 404 | 409) => Outcome::Rejected(code),
        Ok(Ok(code)) => Outcome::Retry(format!("HTTP {code}")),
        Ok(Err(e)) => Outcome::Retry(e),
        Err(_) => Outcome::Retry("timed out".into()),
    }
}

/// Send queued deliveries; any server of the home may pick one up.
pub async fn worker(app: Arc<App>) {
    loop {
        let Some(store) = app.store() else {
            tokio::time::sleep(Duration::from_secs(2)).await;
            continue;
        };
        let job = match store.claim_delivery().await {
            Ok(Some(job)) => job,
            Ok(None) => {
                tokio::time::sleep(Duration::from_secs(1)).await;
                continue;
            }
            Err(e) => {
                eprintln!("chat: outbox: {e}");
                tokio::time::sleep(Duration::from_secs(5)).await;
                continue;
            }
        };
        let mut done = false;
        let mut last = String::new();
        for url in &job.urls {
            match post(url, &job.payload).await {
                Outcome::Delivered => {
                    done = true;
                    break;
                }
                Outcome::Rejected(code) => {
                    eprintln!("chat: {url} refused a delivery (HTTP {code}); dropping it");
                    done = true;
                    break;
                }
                Outcome::Retry(e) => last = format!("{url}: {e}"),
            }
        }
        let r = if done { store.delivered(job.id).await } else { store.retry_delivery(&job).await };
        if !done && job.attempts == 0 {
            eprintln!("chat: delivery to another home failed ({last}); will retry");
        }
        if let Err(e) = r {
            eprintln!("chat: outbox: {e}");
        }
    }
}

/// Close temporary groups when their time is up and delete archives past
/// their retention. Every home does this for its own copy.
pub async fn janitor(app: Arc<App>) {
    let mut tick = tokio::time::interval(JANITOR_EVERY);
    loop {
        tick.tick().await;
        let Some(store) = app.store() else { continue };
        for mut link in store.expired_temp_links().await.unwrap_or_default() {
            link.state = LinkState::Archived;
            link.purge_at = link.retention_days.map(|d| DateTime::from_millis(DateTime::now().timestamp_millis() + d as i64 * 86_400_000));
            link.share_a.to_peer = None;
            link.share_b.to_peer = None;
            if store.save_link(&mut link).await.is_ok() {
                eprintln!("chat: temporary group {} closed", link.id);
                push_link(&app, &store, &link).await;
            }
        }
        for mut link in store.purgeable_links().await.unwrap_or_default() {
            if store.delete_conversation(&format!("link:{}", link.id)).await.is_ok() {
                link.state = LinkState::Closed;
                if store.save_link(&mut link).await.is_ok() {
                    push_link(&app, &store, &link).await;
                }
            }
        }
    }
}
