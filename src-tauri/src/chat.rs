//! LAN chat client. One background task keeps a WebSocket open to the chat
//! server from Settings (nothing connects while that is empty), mirrors
//! conversations into the local database and tells the panel what changed.
//! Messages are stored locally first (pending) and sent once connected, so
//! writing works offline.

use std::collections::BTreeMap;
use std::net::IpAddr;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use serde_json::json;
use tauri::{AppHandle, Emitter, Manager};
use tokio::sync::{mpsc, Notify};
use tokio_tungstenite::tungstenite::Message as Frame;

use crate::db::{conversations, messages, Db};
use crate::settings::SettingsStore;
use crate::system::window;

const DEFAULT_PORT: u16 = 8787;
const CONNECT_TIMEOUT: Duration = Duration::from_secs(10);
const PING_EVERY: Duration = Duration::from_secs(30);
/// No frame at all (not even a pong) for this long: the link is dead.
const SILENCE_LIMIT: Duration = Duration::from_secs(75);
const BACKOFF_MIN: Duration = Duration::from_secs(1);
const BACKOFF_MAX: Duration = Duration::from_secs(30);
const SYNC_PAGE: u32 = 200;
pub const MAX_NAME_CHARS: usize = 40;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct User {
    pub ip: String,
    pub name: String,
    #[serde(default)]
    pub online: bool,
    #[serde(default)]
    pub last_seen: i64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum State {
    /// No chat server configured.
    Off,
    Connecting,
    Online,
    Offline,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Status {
    pub state: State,
    pub server: String,
    /// Who the server says we are (our IP and name), while online.
    pub me: Option<User>,
    pub error: Option<String>,
    pub users: Vec<User>,
}

/// Result of "start a chat with …".
#[derive(Debug, Serialize)]
#[serde(tag = "kind", rename_all = "camelCase")]
pub enum OpenResult {
    Opened { conversation: conversations::Conversation },
    /// Several people share that name: pick one.
    Choose { users: Vec<User> },
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Wire {
    conversation_id: String,
    seq: i64,
    from: String,
    client_msg_id: String,
    body: String,
    created_at: i64,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct WireConversation {
    id: String,
    with: String,
    last_seq: i64,
}

#[derive(Deserialize)]
#[serde(tag = "type", rename_all = "camelCase", rename_all_fields = "camelCase")]
enum ServerMsg {
    Welcome { you: User, users: Vec<User> },
    Presence { ip: String, name: String, online: bool },
    Ack { message: Wire },
    Message { message: Wire },
    Conversations { items: Vec<WireConversation> },
    Messages { conversation_id: String, items: Vec<Wire>, more: bool },
    Error { message: String, client_msg_id: Option<String> },
}

struct Inner {
    status: Status,
    users: BTreeMap<String, User>,
    out: Option<mpsc::UnboundedSender<String>>,
}

pub struct ChatClient {
    inner: Mutex<Inner>,
    /// Settings changed: drop the connection and start over.
    wake: Notify,
}

impl Default for ChatClient {
    fn default() -> Self {
        let status = Status { state: State::Off, server: String::new(), me: None, error: None, users: Vec::new() };
        Self { inner: Mutex::new(Inner { status, users: BTreeMap::new(), out: None }), wake: Notify::new() }
    }
}

/// `host`, `host:port` or `ws://host:port/path` → a WebSocket URL.
pub fn ws_url(server: &str) -> Result<Option<String>, String> {
    let s = server.trim().trim_end_matches('/');
    if s.is_empty() {
        return Ok(None);
    }
    if s.starts_with("wss://") || s.starts_with("http") {
        return Err("use ws://host:port (secure wss:// is not supported yet)".into());
    }
    let rest = s.strip_prefix("ws://").unwrap_or(s);
    let (host, path) = rest.split_once('/').map_or((rest, "ws"), |(h, p)| (h, p));
    if host.is_empty() || host.contains(char::is_whitespace) {
        return Err(format!("invalid chat server address: {server}"));
    }
    // Add the default port unless one is given ("[v6]:port" or "host:port").
    let has_port = if host.starts_with('[') { host.contains("]:") } else { host.matches(':').count() == 1 };
    let host = if has_port {
        host.to_string()
    } else if host.contains(':') && !host.starts_with('[') {
        format!("[{host}]:{DEFAULT_PORT}") // bare IPv6
    } else {
        format!("{host}:{DEFAULT_PORT}")
    };
    Ok(Some(format!("ws://{host}/{path}")))
}

pub fn parse_ip(s: &str) -> Option<String> {
    s.trim().parse::<IpAddr>().ok().map(|ip| ip.to_canonical().to_string())
}

/// The other member of a server conversation id `dm:<a>|<b>`.
fn peer_of(conversation_id: &str, me: &str) -> Option<String> {
    let (a, b) = conversation_id.strip_prefix("dm:")?.split_once('|')?;
    match (a == me, b == me) {
        (true, _) => Some(b.to_string()),
        (_, true) => Some(a.to_string()),
        _ => None,
    }
}

fn random_id() -> String {
    crate::crypto::random_bytes::<16>().map(|b| crate::crypto::hex(&b)).unwrap_or_else(|_| format!("t{}", crate::db::now_ms()))
}

fn default_name() -> String {
    std::env::var("USER").unwrap_or_default()
}

impl ChatClient {
    fn lock(&self) -> std::sync::MutexGuard<'_, Inner> {
        self.inner.lock().unwrap_or_else(|p| p.into_inner())
    }

    pub fn status(&self) -> Status {
        let inner = self.lock();
        let mut users: Vec<User> = inner.users.values().cloned().collect();
        users.sort_by(|a, b| b.online.cmp(&a.online).then_with(|| a.name.to_lowercase().cmp(&b.name.to_lowercase())));
        Status { users, ..inner.status.clone() }
    }

    /// Settings changed: reconnect with the new ones.
    pub fn reconfigure(&self) {
        self.wake.notify_one();
    }

    fn my_ip(&self) -> Option<String> {
        self.lock().status.me.as_ref().map(|u| u.ip.clone())
    }

    fn name_of(&self, ip: &str) -> String {
        self.lock().users.get(ip).map(|u| u.name.clone()).unwrap_or_default()
    }

    fn push(&self, frame: String) -> bool {
        self.lock().out.as_ref().is_some_and(|tx| tx.send(frame).is_ok())
    }

    fn set_status(&self, app: &AppHandle, f: impl FnOnce(&mut Inner)) {
        f(&mut self.lock());
        let _ = app.emit_to(window::PANEL, "chat-status", self.status());
    }

    /// Resolve "IP address or name" to a peer. Names are matched against
    /// everyone the server has seen: exact (any case) first, then prefix.
    pub fn resolve(&self, target: &str) -> Result<Result<User, Vec<User>>, String> {
        let target = target.trim();
        if target.is_empty() {
            return Err("enter an IP address or a name".into());
        }
        let me = self.my_ip();
        let user = if let Some(ip) = parse_ip(target) {
            let name = self.name_of(&ip);
            User { ip, name, online: false, last_seen: 0 }
        } else {
            let wanted = target.to_lowercase();
            let users: Vec<User> = self.lock().users.values().filter(|u| Some(&u.ip) != me.as_ref()).cloned().collect();
            let exact: Vec<User> = users.iter().filter(|u| u.name.to_lowercase() == wanted).cloned().collect();
            let found = if exact.is_empty() {
                users.into_iter().filter(|u| u.name.to_lowercase().starts_with(&wanted)).collect()
            } else {
                exact
            };
            match found.len() {
                0 if self.lock().status.state != State::Online => {
                    return Err("not connected to the chat server, so names can't be looked up; use an IP address".into())
                }
                0 => return Err(format!("no one named “{target}” has used the chat server; try their IP address")),
                1 => found.into_iter().next().expect("one"),
                _ => return Ok(Err(found)),
            }
        };
        if Some(&user.ip) == me.as_ref() {
            return Err("that's you: use Notes to self".into());
        }
        Ok(Ok(user))
    }

    /// Queue a stored outgoing message for the server (no-op while offline:
    /// pending messages are sent on connect).
    pub fn send(&self, peer_ip: &str, message: &messages::Message) {
        if let Some(id) = &message.client_msg_id {
            self.push(json!({ "type": "send", "to": peer_ip, "clientMsgId": id, "body": message.body }).to_string());
        }
    }
}

pub fn new_client_msg_id() -> String {
    random_id()
}

pub fn spawn(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        let client = app.state::<ChatClient>();
        let mut backoff = BACKOFF_MIN;
        loop {
            let settings = app.state::<SettingsStore>().get();
            let url = match ws_url(&settings.chat_server) {
                Ok(Some(url)) => url,
                other => {
                    let error = other.err();
                    client.set_status(&app, |i| {
                        i.status = Status { state: State::Off, server: String::new(), me: None, error, users: Vec::new() };
                        i.out = None;
                    });
                    client.wake.notified().await;
                    continue;
                }
            };
            client.set_status(&app, |i| {
                i.status.state = State::Connecting;
                i.status.server = url.clone();
                i.status.error = None;
            });
            let started = Instant::now();
            let ended = connect(&app, &client, &url, &settings.chat_ip, &settings.chat_name).await;
            client.set_status(&app, |i| {
                i.out = None;
                i.status.state = State::Offline;
                i.status.me = None;
                i.status.error = ended.as_ref().err().cloned();
                i.users.values_mut().for_each(|u| u.online = false);
            });
            if ended.is_ok() {
                backoff = BACKOFF_MIN; // reconfigured: reconnect right away
                continue;
            }
            if started.elapsed() > BACKOFF_MAX {
                backoff = BACKOFF_MIN;
            }
            tokio::select! {
                _ = tokio::time::sleep(backoff) => backoff = (backoff * 2).min(BACKOFF_MAX),
                _ = client.wake.notified() => backoff = BACKOFF_MIN,
            }
        }
    });
}

/// One connection. `Ok` means it was dropped on purpose (settings changed).
async fn connect(app: &AppHandle, client: &ChatClient, url: &str, ip: &str, name: &str) -> Result<(), String> {
    let (socket, _) = tokio::time::timeout(CONNECT_TIMEOUT, tokio_tungstenite::connect_async(url))
        .await
        .map_err(|_| "chat server did not answer".to_string())?
        .map_err(|e| format!("can't reach the chat server: {e}"))?;
    let (mut sink, mut stream) = socket.split();

    let name = if name.trim().is_empty() { default_name() } else { name.trim().to_string() };
    let mut hello = json!({ "type": "hello", "name": name });
    if let Some(ip) = parse_ip(ip) {
        hello["ip"] = json!(ip);
    }
    sink.send(Frame::Text(hello.to_string().into())).await.map_err(|e| e.to_string())?;

    let first = tokio::time::timeout(CONNECT_TIMEOUT, next_text(&mut stream))
        .await
        .map_err(|_| "chat server did not reply to hello".to_string())??;
    match serde_json::from_str::<ServerMsg>(&first) {
        Ok(ServerMsg::Welcome { you, users }) => client.set_status(app, |i| {
            i.users = users.into_iter().map(|u| (u.ip.clone(), u)).collect();
            i.status.state = State::Online;
            i.status.me = Some(you);
            i.status.error = None;
        }),
        Ok(ServerMsg::Error { message, .. }) => return Err(message),
        _ => return Err("unexpected reply from the chat server".into()),
    }

    let (tx, mut rx) = mpsc::unbounded_channel::<String>();
    client.lock().out = Some(tx.clone());
    let _ = tx.send(json!({ "type": "conversations" }).to_string());
    let db = app.state::<Db>();
    if let Ok(pending) = db.with(|c| messages::pending_outgoing(c)) {
        for (m, peer) in pending {
            client.send(&peer, &m);
        }
    }

    let mut ping = tokio::time::interval(PING_EVERY);
    let mut last_heard = Instant::now();
    loop {
        tokio::select! {
            frame = stream.next() => {
                last_heard = Instant::now();
                match frame {
                    Some(Ok(Frame::Text(text))) => handle(app, client, &text),
                    Some(Ok(Frame::Close(_))) | None => return Err("the chat server closed the connection".into()),
                    Some(Err(e)) => return Err(format!("connection lost: {e}")),
                    Some(Ok(_)) => {} // pong etc.
                }
            }
            Some(frame) = rx.recv() => {
                sink.send(Frame::Text(frame.into())).await.map_err(|e| format!("connection lost: {e}"))?;
            }
            _ = ping.tick() => {
                if last_heard.elapsed() > SILENCE_LIMIT {
                    return Err("the chat server stopped responding".into());
                }
                sink.send(Frame::Ping(Vec::new().into())).await.map_err(|e| format!("connection lost: {e}"))?;
            }
            _ = client.wake.notified() => {
                let _ = sink.close().await;
                return Ok(());
            }
        }
    }
}

async fn next_text<S>(stream: &mut S) -> Result<String, String>
where
    S: futures_util::Stream<Item = Result<Frame, tokio_tungstenite::tungstenite::Error>> + Unpin,
{
    while let Some(frame) = stream.next().await {
        match frame {
            Ok(Frame::Text(t)) => return Ok(t.to_string()),
            Ok(Frame::Close(_)) => break,
            Ok(_) => continue,
            Err(e) => return Err(e.to_string()),
        }
    }
    Err("the chat server closed the connection".into())
}

fn changed(app: &AppHandle, conversation: i64) {
    let _ = app.emit_to(window::PANEL, "chat-changed", conversation);
}

fn handle(app: &AppHandle, client: &ChatClient, text: &str) {
    let Ok(msg) = serde_json::from_str::<ServerMsg>(text) else { return };
    let db = app.state::<Db>();
    let result = match msg {
        ServerMsg::Presence { ip, name, online } => {
            client.set_status(app, |i| {
                let u = i.users.entry(ip.clone()).or_insert_with(|| User { ip: ip.clone(), name: String::new(), online, last_seen: 0 });
                u.name = name.clone();
                u.online = online;
                u.last_seen = crate::db::now_ms();
            });
            db.with(|c| conversations::set_peer_name(c, &ip, &name))
        }
        ServerMsg::Message { message } | ServerMsg::Ack { message } => receive(app, client, &db, &message, true).map(|r| {
            if let Some((_, Some(reaction))) = r {
                react(app, &reaction);
            }
        }),
        ServerMsg::Conversations { items } => db.with(|c| {
            for item in items {
                let conv = conversations::open_remote(c, &item.with, &client.name_of(&item.with))?;
                conversations::bind_remote(c, conv.id, &item.id)?;
                let have = conversations::get(c, conv.id)?.last_seq;
                if item.last_seq > have {
                    request_sync(client, &item.id, have);
                }
            }
            Ok(())
        }),
        ServerMsg::Messages { conversation_id, items, more } => {
            let mut last = None;
            let mut reaction = None;
            for m in &items {
                match receive(app, client, &db, m, false) {
                    Ok(Some((local, new_from_them))) => {
                        last = Some((local, m.seq));
                        reaction = new_from_them.or(reaction);
                    }
                    Ok(None) => {}
                    Err(e) => eprintln!("deskbuddy: chat sync: {e}"),
                }
            }
            // Caught up on missed messages: one reaction, not one per message.
            if let Some(r) = reaction {
                react(app, &r);
            }
            if let Some((local, seq)) = last {
                let _ = db.with(|c| conversations::advance(c, local, seq));
                if more {
                    request_sync(client, &conversation_id, seq);
                }
            }
            Ok(())
        }
        ServerMsg::Error { message, client_msg_id: Some(id) } => db.with(|c| {
            if let Some(m) = messages::by_client_id(c, &id)? {
                messages::set_state(c, m.id, "failed")?;
                changed(app, m.conversation_id);
            }
            eprintln!("deskbuddy: chat message not sent: {message}");
            Ok(())
        }),
        ServerMsg::Error { message, client_msg_id: None } => {
            client.set_status(app, |i| i.status.error = Some(message));
            Ok(())
        }
        ServerMsg::Welcome { .. } => Ok(()),
    };
    if let Err(e) = result {
        eprintln!("deskbuddy: chat: {e}");
    }
}

fn request_sync(client: &ChatClient, conversation_id: &str, after: i64) {
    client.push(json!({ "type": "sync", "conversationId": conversation_id, "afterSeq": after, "limit": SYNC_PAGE }).to_string());
}

/// The pet's reaction to a new message: "" = its default, "none" = nothing.
fn react(app: &AppHandle, reaction: &str) {
    if reaction != "none" {
        let _ = app.emit_to(window::MASCOT, "mascot-react", reaction);
    }
}

/// Store one server message. Live ones (`live`) advance the sync position
/// only when nothing is missing before them; a gap triggers a sync instead.
/// Returns the local conversation id and, if this was a new message from the
/// other person, the reaction set for them.
fn receive(app: &AppHandle, client: &ChatClient, db: &Db, m: &Wire, live: bool) -> crate::db::Result<Option<(i64, Option<String>)>> {
    let Some(me) = client.my_ip() else { return Ok(None) };
    let Some(peer) = peer_of(&m.conversation_id, &me) else { return Ok(None) };
    let local = db.with(|c| {
        let conv = conversations::open_remote(c, &peer, &client.name_of(&peer))?;
        conversations::bind_remote(c, conv.id, &m.conversation_id)?;
        let have = conversations::get(c, conv.id)?.last_seq;
        let sender = (m.from != me).then_some(m.from.as_str());
        let added = messages::apply_remote(
            c,
            &messages::Remote {
                conversation: conv.id,
                sender_ip: sender,
                client_msg_id: &m.client_msg_id,
                seq: m.seq,
                body: &m.body,
                created_at: m.created_at,
            },
        )?;
        if live {
            if m.seq <= have + 1 {
                conversations::advance(c, conv.id, m.seq)?;
            } else {
                request_sync(client, &m.conversation_id, have);
            }
        }
        Ok((conv.id, (added && sender.is_some()).then_some(conv.reaction)))
    })?;
    changed(app, local.0);
    Ok(Some(local))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn server_addresses() {
        assert_eq!(ws_url("").unwrap(), None);
        assert_eq!(ws_url("192.168.1.5").unwrap().unwrap(), "ws://192.168.1.5:8787/ws");
        assert_eq!(ws_url("192.168.1.5:9000").unwrap().unwrap(), "ws://192.168.1.5:9000/ws");
        assert_eq!(ws_url(" ws://chat.lan:9000/ws/ ").unwrap().unwrap(), "ws://chat.lan:9000/ws");
        assert_eq!(ws_url("fe80::1").unwrap().unwrap(), "ws://[fe80::1]:8787/ws");
        assert_eq!(ws_url("[fe80::1]:9000").unwrap().unwrap(), "ws://[fe80::1]:9000/ws");
        assert!(ws_url("wss://x").is_err());
        assert!(ws_url("a b").is_err());
    }

    #[test]
    fn peers_and_ips() {
        assert_eq!(peer_of("dm:10.0.0.1|10.0.0.2", "10.0.0.1").as_deref(), Some("10.0.0.2"));
        assert_eq!(peer_of("dm:10.0.0.1|10.0.0.2", "10.0.0.2").as_deref(), Some("10.0.0.1"));
        assert_eq!(peer_of("dm:10.0.0.1|10.0.0.2", "10.0.0.3"), None);
        assert_eq!(peer_of("group:x", "10.0.0.1"), None);
        assert_eq!(parse_ip(" ::ffff:10.0.0.1 ").as_deref(), Some("10.0.0.1"));
        assert_eq!(parse_ip("asha"), None);
    }

    /// Frames exactly as the chat server (server/src/protocol.rs) writes them.
    #[test]
    fn parses_server_frames() {
        let welcome = r#"{"type":"welcome","you":{"ip":"10.0.0.1","name":"me","online":true,"lastSeen":5},"users":[{"ip":"10.0.0.2","name":"Asha","online":false,"lastSeen":4}]}"#;
        assert!(matches!(serde_json::from_str(welcome), Ok(ServerMsg::Welcome { ref users, .. }) if users.len() == 1));
        let message = r#"{"id":"65f0","conversationId":"dm:10.0.0.1|10.0.0.2","seq":3,"from":"10.0.0.2","clientMsgId":"c9","body":"hi","createdAt":7}"#;
        let ack = format!(r#"{{"type":"ack","clientMsgId":"c9","message":{message}}}"#);
        assert!(matches!(serde_json::from_str(&ack), Ok(ServerMsg::Ack { message: Wire { seq: 3, .. } })));
        let push = format!(r#"{{"type":"message","message":{message}}}"#);
        assert!(matches!(serde_json::from_str(&push), Ok(ServerMsg::Message { .. })));
        let page = format!(r#"{{"type":"messages","conversationId":"dm:a|b","items":[{message}],"more":false}}"#);
        assert!(matches!(serde_json::from_str(&page), Ok(ServerMsg::Messages { more: false, ref items, .. }) if items.len() == 1));
        let convs = r#"{"type":"conversations","items":[{"id":"dm:a|b","with":"b","lastSeq":2,"updatedAt":9}]}"#;
        assert!(matches!(serde_json::from_str(convs), Ok(ServerMsg::Conversations { ref items }) if items[0].last_seq == 2));
        let presence = r#"{"type":"presence","ip":"10.0.0.2","name":"Asha","online":true}"#;
        assert!(matches!(serde_json::from_str(presence), Ok(ServerMsg::Presence { online: true, .. })));
        let err = r#"{"type":"error","code":"rate_limited","message":"slow down","clientMsgId":"c9"}"#;
        assert!(matches!(serde_json::from_str(err), Ok(ServerMsg::Error { client_msg_id: Some(_), .. })));
        let err = r#"{"type":"error","code":"ip_mismatch","message":"no"}"#;
        assert!(matches!(serde_json::from_str(err), Ok(ServerMsg::Error { client_msg_id: None, .. })));
    }

    #[test]
    fn resolve_by_ip_or_name() {
        let client = ChatClient::default();
        {
            let mut i = client.lock();
            i.status.state = State::Online;
            i.status.me = Some(User { ip: "10.0.0.1".into(), name: "me".into(), online: true, last_seen: 0 });
            for (ip, name) in [("10.0.0.2", "Asha"), ("10.0.0.3", "Ashok"), ("10.0.0.4", "Asha")] {
                i.users.insert(ip.into(), User { ip: ip.into(), name: name.into(), online: true, last_seen: 0 });
            }
            i.users.insert("10.0.0.5".into(), User { ip: "10.0.0.5".into(), name: "Ravi".into(), online: false, last_seen: 0 });
        }
        assert_eq!(client.resolve("10.0.0.9").unwrap().unwrap().ip, "10.0.0.9", "any IP works, even unseen");
        assert_eq!(client.resolve("ravi").unwrap().unwrap().ip, "10.0.0.5", "case-insensitive");
        assert_eq!(client.resolve("asho").unwrap().unwrap().ip, "10.0.0.3", "prefix");
        assert_eq!(client.resolve("asha").unwrap().unwrap_err().len(), 2, "two people named Asha");
        assert!(client.resolve("nobody").is_err());
        assert!(client.resolve("10.0.0.1").is_err(), "yourself");
        assert!(client.resolve("me").is_err(), "yourself by name is not listed");
        assert!(client.resolve(" ").is_err());
    }
}
