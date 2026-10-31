//! Chat client. One background task keeps a WebSocket open to a chat server
//! (the ones in Settings, then any the servers told us about), logs in with
//! this device's key, mirrors conversations into the local database and
//! tells the panel what changed. Messages are stored locally first (pending)
//! and encrypted + sent once connected, so writing works offline.
//!
//! Everything sent is end-to-end encrypted (see `e2e`); the local copy is
//! plain text inside the encrypted database.

use std::collections::{BTreeMap, HashMap};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use serde_json::json;
use tauri::{AppHandle, Emitter, Manager};
use tokio::sync::{mpsc, Notify};
use tokio_tungstenite::tungstenite::Message as Frame;

use crate::crypto::{self, hex, Key};
use crate::db::{chat_keys, conversations, messages, Db};
use crate::e2e::{self, Identity};
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
/// A poke is an ordinary (end-to-end encrypted) message with this body, so
/// the server can't tell it apart and older apps just show the text.
pub const POKE: &str = "/poke";
/// Only pokes this recent play on the desktop: catching up after being away
/// doesn't replay them.
const POKE_FRESH_MS: i64 = 2 * 60 * 1000;
/// One poke reaction per person this often, however fast they poke.
const POKE_GAP_MS: i64 = 8_000;
const UNREADABLE: &str = "🔒 This message can't be decrypted (its key isn't on this device).";

const INVITE_PREFIX: &str = "DBT1-";
const ADDRESS_PREFIX: &str = "DBA1-";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct User {
    pub device: String,
    pub name: String,
    pub dh_pub: String,
    #[serde(default)]
    pub online: bool,
    #[serde(default)]
    pub last_seen: i64,
    /// False for people on another team's server.
    #[serde(default = "yes")]
    pub local: bool,
}

fn yes() -> bool {
    true
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum State {
    /// Disconnected on purpose, or no server known.
    Off,
    Connecting,
    Online,
    Offline,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Me {
    pub device: String,
    pub name: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TeamView {
    pub id: String,
    pub name: String,
    pub key_version: u32,
    /// Rotated out or left: history only.
    pub removed: bool,
    /// Member devices, as the server last told us.
    pub members: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LinkView {
    pub id: String,
    pub kind: String,
    pub state: String,
    pub my_team: String,
    pub my_team_name: String,
    pub other_team: String,
    pub other_team_name: String,
    /// We sent the request.
    pub outgoing: bool,
    pub hours: Option<u32>,
    pub expires_at: Option<i64>,
    pub retention_days: Option<u32>,
    pub purge_at: Option<i64>,
    /// Compare with the other team to rule out swapped keys.
    pub safety_number: Option<String>,
    pub we_released: bool,
    pub they_released: bool,
    pub conversation: Option<i64>,
    pub other_members: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Status {
    pub state: State,
    pub server: String,
    pub me: Option<Me>,
    pub error: Option<String>,
    pub users: Vec<User>,
    pub teams: Vec<TeamView>,
    pub links: Vec<LinkView>,
    /// The connected server cluster's id and addresses.
    pub home: Option<String>,
    pub servers: Vec<String>,
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
    last_seq: i64,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct WireTeam {
    id: String,
    members: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Member {
    pub device: String,
    pub name: String,
    pub dh_pub: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TeamRef {
    pub id: String,
    pub name: String,
    pub dh_pub: String,
    pub home: String,
    #[serde(default)]
    pub servers: Vec<String>,
    #[serde(default)]
    pub members: Vec<Member>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Share {
    #[serde(default)]
    own: Option<String>,
    #[serde(default)]
    to_peer: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Link {
    id: String,
    kind: String,
    state: String,
    a: TeamRef,
    b: TeamRef,
    hours: Option<u32>,
    expires_at: Option<i64>,
    retention_days: Option<u32>,
    purge_at: Option<i64>,
    share_a: Share,
    share_b: Share,
}

impl Link {
    fn team(&self, side: char) -> &TeamRef {
        if side == 'a' { &self.a } else { &self.b }
    }
    fn share(&self, side: char) -> &Share {
        if side == 'a' { &self.share_a } else { &self.share_b }
    }
    fn title(&self) -> String {
        format!("{} ↔ {}", self.a.name, self.b.name)
    }
}

fn other(side: char) -> char {
    if side == 'a' { 'b' } else { 'a' }
}

#[derive(Deserialize)]
#[serde(tag = "type", rename_all = "camelCase", rename_all_fields = "camelCase")]
enum ServerMsg {
    Challenge { nonce: String },
    Welcome { you: User, home: String, servers: Vec<String>, users: Vec<User>, teams: Vec<WireTeam>, links: Vec<Link> },
    Presence { device: String, name: String, online: bool },
    User { user: User },
    Team { team: WireTeam },
    TeamGone { team_id: String },
    Link { link: Link },
    Ack { message: Wire },
    Message { message: Wire },
    Conversations { items: Vec<WireConversation> },
    Messages { conversation_id: String, items: Vec<Wire>, more: bool },
    Error { message: String, client_msg_id: Option<String> },
}

/// A team invite: everything needed to join. Secret.
#[derive(Serialize, Deserialize)]
struct Invite {
    v: u32,
    id: String,
    name: String,
    key: String,
    kv: u32,
    dh: String,
    home: String,
    servers: Vec<String>,
}

/// A team's public address: what another team needs to send it a request.
#[derive(Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Address {
    v: u32,
    id: String,
    name: String,
    dh_pub: String,
    home: String,
    servers: Vec<String>,
}

struct Inner {
    state: State,
    server: String,
    error: Option<String>,
    me: Option<Me>,
    home: Option<String>,
    servers: Vec<String>,
    users: BTreeMap<String, User>,
    /// Team id → member devices, from the server.
    teams: HashMap<String, Vec<String>>,
    links: BTreeMap<String, Link>,
    out: Option<mpsc::UnboundedSender<String>>,
}

pub struct ChatClient {
    inner: Mutex<Inner>,
    identity: Mutex<Option<Arc<Identity>>>,
    /// Settings changed: drop the connection and start over.
    wake: Notify,
}

impl Default for ChatClient {
    fn default() -> Self {
        let inner = Inner {
            state: State::Off,
            server: String::new(),
            error: None,
            me: None,
            home: None,
            servers: Vec::new(),
            users: BTreeMap::new(),
            teams: HashMap::new(),
            links: BTreeMap::new(),
            out: None,
        };
        Self { inner: Mutex::new(inner), identity: Mutex::new(None), wake: Notify::new() }
    }
}

/// `host`, `host:port`, `ws://host:port/path` or `http://host:port` → a WebSocket URL.
pub fn ws_url(server: &str) -> Result<Option<String>, String> {
    let s = server.trim().trim_end_matches('/');
    if s.is_empty() {
        return Ok(None);
    }
    if s.starts_with("wss://") || s.starts_with("https://") {
        return Err("use ws://host:port (secure wss:// is not supported yet)".into());
    }
    let rest = s.strip_prefix("ws://").or_else(|| s.strip_prefix("http://")).unwrap_or(s);
    let (host, path) = rest.split_once('/').map_or((rest, "ws"), |(h, p)| (h, p));
    if host.is_empty() || host.contains(char::is_whitespace) || host.contains(',') {
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

/// Every address in a comma-separated list, checked.
pub fn server_list(servers: &str) -> Result<Vec<String>, String> {
    let mut out = Vec::new();
    for s in servers.split(',') {
        if let Some(url) = ws_url(s)? {
            if !out.contains(&url) {
                out.push(url);
            }
        }
    }
    Ok(out)
}

fn random_hex16() -> String {
    crypto::random_bytes::<16>().map(|b| hex(&b)).unwrap_or_else(|_| format!("{:032x}", crate::db::now_ms()))
}

pub fn new_client_msg_id() -> String {
    random_hex16()
}

fn default_name() -> String {
    std::env::var("USER").unwrap_or_default()
}

fn is_hex_key(s: &str) -> bool {
    s.len() == 64 && s.bytes().all(|b| b.is_ascii_hexdigit())
}

/// The first characters of a device id, for showing who is who.
pub fn short_id(device: &str) -> String {
    device.chars().take(8).collect()
}

impl ChatClient {
    fn lock(&self) -> std::sync::MutexGuard<'_, Inner> {
        self.inner.lock().unwrap_or_else(|p| p.into_inner())
    }

    /// This device's keys, created on first use.
    pub fn identity(&self, db: &Db) -> Result<Arc<Identity>, String> {
        let mut slot = self.identity.lock().unwrap_or_else(|p| p.into_inner());
        if let Some(id) = slot.as_ref() {
            return Ok(id.clone());
        }
        let id = db
            .with(|c| match chat_keys::identity(c)? {
                Some((sign, dh)) => Ok(Identity::from_secrets(&sign, &dh)),
                None => {
                    let id = Identity::generate()?;
                    chat_keys::save_identity(c, &id.sign_secret(), id.dh_secret())?;
                    Ok(id)
                }
            })
            .map_err(|e| e.to_string())?;
        let id = Arc::new(id);
        *slot = Some(id.clone());
        Ok(id)
    }

    fn my_device(&self) -> Option<String> {
        self.lock().me.as_ref().map(|m| m.device.clone())
    }

    fn name_of(&self, device: &str) -> String {
        let inner = self.lock();
        if let Some(u) = inner.users.get(device) {
            return u.name.clone();
        }
        inner
            .links
            .values()
            .flat_map(|l| l.a.members.iter().chain(&l.b.members))
            .find(|m| m.device == device)
            .map(|m| m.name.clone())
            .unwrap_or_else(|| short_id(device))
    }

    fn dh_pub_of(&self, device: &str) -> Option<String> {
        let inner = self.lock();
        inner.users.get(device).map(|u| u.dh_pub.clone()).or_else(|| {
            inner.links.values().flat_map(|l| l.a.members.iter().chain(&l.b.members)).find(|m| m.device == device).map(|m| m.dh_pub.clone())
        })
    }

    fn push(&self, frame: String) -> bool {
        self.lock().out.as_ref().is_some_and(|tx| tx.send(frame).is_ok())
    }

    fn online(&self) -> bool {
        self.lock().state == State::Online
    }

    pub fn status(&self, db: &Db) -> Status {
        let local_teams = db.with(|c| chat_keys::teams(c)).unwrap_or_default();
        let inner = self.lock();
        let mut users: Vec<User> = inner.users.values().cloned().collect();
        users.sort_by(|a, b| b.online.cmp(&a.online).then_with(|| a.name.to_lowercase().cmp(&b.name.to_lowercase())));
        let teams = local_teams
            .iter()
            .map(|t| TeamView {
                id: t.id.clone(),
                name: t.name.clone(),
                key_version: t.key_version,
                removed: t.removed,
                members: inner.teams.get(&t.id).cloned().unwrap_or_default(),
            })
            .collect();
        let links = inner.links.values().filter_map(|l| self.link_view(db, &local_teams, l)).collect();
        Status {
            state: inner.state,
            server: inner.server.clone(),
            me: inner.me.clone(),
            error: inner.error.clone(),
            users,
            teams,
            links,
            home: inner.home.clone(),
            servers: inner.servers.clone(),
        }
    }

    fn link_view(&self, db: &Db, local_teams: &[chat_keys::Team], l: &Link) -> Option<LinkView> {
        let side = my_side(local_teams, l)?;
        let mine = l.team(side);
        let theirs = l.team(other(side));
        let team = local_teams.iter().find(|t| t.id == mine.id)?;
        let pair = e2e::pair_key(&team.dh_secret, &theirs.dh_pub, &l.id);
        let conversation = db.with(|c| conversations::by_remote(c, &format!("link:{}", l.id))).ok().flatten().map(|c| c.id);
        Some(LinkView {
            id: l.id.clone(),
            kind: l.kind.clone(),
            state: l.state.clone(),
            my_team: mine.id.clone(),
            my_team_name: mine.name.clone(),
            other_team: theirs.id.clone(),
            other_team_name: theirs.name.clone(),
            outgoing: side == 'a',
            hours: l.hours,
            expires_at: l.expires_at,
            retention_days: l.retention_days,
            purge_at: l.purge_at,
            safety_number: pair.map(|p| e2e::safety_number(&p)),
            we_released: l.share(side).to_peer.is_some(),
            they_released: l.share(other(side)).to_peer.is_some(),
            conversation,
            other_members: theirs.members.iter().map(|m| m.device.clone()).collect(),
        })
    }

    fn emit(&self, app: &AppHandle) {
        let db = app.state::<Db>();
        let _ = app.emit_to(window::PANEL, "chat-status", self.status(&db));
    }

    fn set_status(&self, app: &AppHandle, f: impl FnOnce(&mut Inner)) {
        f(&mut self.lock());
        self.emit(app);
    }

    /// Settings changed: reconnect with the new ones.
    pub fn reconfigure(&self) {
        self.wake.notify_one();
    }

    /// Resolve "name or device id" to a person. Names match exactly (any
    /// case) first, then by prefix.
    pub fn resolve(&self, target: &str) -> Result<Result<User, Vec<User>>, String> {
        let target = target.trim();
        if target.is_empty() {
            return Err("enter a name".into());
        }
        let me = self.my_device();
        let users: Vec<User> = self.lock().users.values().filter(|u| Some(&u.device) != me.as_ref()).cloned().collect();
        let wanted = target.to_lowercase();
        let by_id: Vec<User> = users.iter().filter(|u| u.device.starts_with(&wanted) && wanted.len() >= 6).cloned().collect();
        let exact: Vec<User> = users.iter().filter(|u| u.name.to_lowercase() == wanted).cloned().collect();
        let found = if !by_id.is_empty() {
            by_id
        } else if !exact.is_empty() {
            exact
        } else {
            users.into_iter().filter(|u| u.name.to_lowercase().starts_with(&wanted)).collect()
        };
        match found.len() {
            0 if !self.online() => Err("not connected to a chat server, so people can't be looked up".into()),
            0 => Err(format!("no one named “{target}” is on this server or in a linked team")),
            1 => Ok(Ok(found.into_iter().next().expect("one"))),
            _ => Ok(Err(found)),
        }
    }

    /// The direct chat with `user`, created if new.
    pub fn open_dm(&self, db: &Db, user: &User) -> Result<conversations::Conversation, String> {
        let me = self.identity(db)?.device();
        if user.device == me {
            return Err("that's you: use Notes to self".into());
        }
        let id = e2e::dm_id(&me, &user.device);
        db.with(|c| conversations::open_room(c, "dm", &id, "", Some(&user.device), &user.name)).map_err(|e| e.to_string())
    }

    /// The key for a conversation (and the version to stamp on new messages).
    fn key_for(&self, db: &Db, remote_id: &str, version: Option<u32>) -> Result<(Key, u32), String> {
        let identity = self.identity(db)?;
        if let Some(pair) = remote_id.strip_prefix("dm:") {
            let me = identity.device();
            let (a, b) = pair.split_once('|').ok_or("bad conversation id")?;
            let peer = if a == me { b } else { a };
            let pub_key = self.dh_pub_of(peer).ok_or("their key isn't known yet; wait until you're connected")?;
            return identity.dm_key(&pub_key, remote_id).map(|k| (k, 0)).ok_or_else(|| "their key is invalid".into());
        }
        if let Some(team_id) = remote_id.strip_prefix("team:") {
            let team = db.with(|c| chat_keys::team(c, team_id)).map_err(|e| e.to_string())?.ok_or("you don't have this team's key")?;
            let v = version.unwrap_or(team.key_version);
            let key = db.with(|c| chat_keys::team_key(c, team_id, v)).map_err(|e| e.to_string())?.ok_or("this message used a team key you don't have")?;
            return Ok((e2e::team_message_key(&key), v));
        }
        let link_id = remote_id.strip_prefix("link:").ok_or("unknown conversation")?;
        let link = self.lock().links.get(link_id).cloned().ok_or("this group isn't known yet; wait until you're connected")?;
        let teams = db.with(|c| chat_keys::teams(c)).map_err(|e| e.to_string())?;
        let side = my_side(&teams, &link).ok_or("your team isn't in this group")?;
        let team = teams.iter().find(|t| t.id == link.team(side).id).expect("my_side found it");
        let pair = e2e::pair_key(&team.dh_secret, &link.team(other(side)).dh_pub, &link.id).ok_or("the other team's key is invalid")?;
        if link.kind != "temp" {
            return Ok((e2e::group_key(&pair), 0));
        }
        let own = own_share(db, team, link.share(side), &link.id).ok_or("your team's half of this group's key is missing")?;
        let theirs = link
            .share(other(side))
            .to_peer
            .as_deref()
            .and_then(|s| e2e::open_peer_share(&pair, s, &link.id))
            .ok_or("the other team hasn't released this archive")?;
        let (sa, sb) = if side == 'a' { (own, theirs) } else { (theirs, own) };
        Ok((e2e::temp_key(&pair, &sa, &sb), 0))
    }

    /// Encrypt and queue a stored outgoing message (no-op while offline:
    /// pending messages are sent on connect).
    pub fn send(&self, db: &Db, remote_id: &str, message: &messages::Message) -> Result<(), String> {
        let (Some(id), Some(me)) = (&message.client_msg_id, self.my_device()) else { return Ok(()) };
        let (key, version) = self.key_for(db, remote_id, None)?;
        let body = e2e::seal_message(&key, version, &message.body, &e2e::message_aad(remote_id, &me, id)).map_err(|e| e.to_string())?;
        self.push(json!({ "type": "send", "conversationId": remote_id, "clientMsgId": id, "body": body }).to_string());
        Ok(())
    }

    fn require_online(&self) -> Result<(), String> {
        if self.online() { Ok(()) } else { Err("connect to a chat server first".into()) }
    }

    fn join_frame(team: &chat_keys::Team, key: &[u8; 32]) -> String {
        json!({
            "type": "teamJoin",
            "teamId": team.id,
            "name": team.name,
            "dhPub": e2e::dh_public(&team.dh_secret),
            "proof": e2e::team_proof(key),
        })
        .to_string()
    }

    fn invite_code(&self, team: &chat_keys::Team, key: &[u8; 32]) -> String {
        let (home, servers) = {
            let inner = self.lock();
            (inner.home.clone().unwrap_or_else(|| team.home.clone()), if inner.servers.is_empty() { team.servers.clone() } else { inner.servers.clone() })
        };
        let invite = Invite {
            v: 1,
            id: team.id.clone(),
            name: team.name.clone(),
            key: hex(key),
            kv: team.key_version,
            dh: hex(team.dh_secret.as_ref()),
            home,
            servers,
        };
        e2e::encode_code(INVITE_PREFIX, &invite)
    }

    /// Create a team on the connected server; returns its invite.
    pub fn team_create(&self, db: &Db, name: &str) -> Result<String, String> {
        let name = name.trim();
        if name.is_empty() || name.chars().count() > MAX_NAME_CHARS {
            return Err(format!("team names are 1–{MAX_NAME_CHARS} characters"));
        }
        self.require_online()?;
        let key = crypto::random_key().map_err(|e| e.to_string())?;
        let (home, servers) = {
            let inner = self.lock();
            (inner.home.clone().unwrap_or_default(), inner.servers.clone())
        };
        let team = chat_keys::Team {
            id: random_hex16(),
            name: name.into(),
            dh_secret: crypto::random_key().map_err(|e| e.to_string())?,
            key_version: 1,
            home,
            servers,
            removed: false,
        };
        let team = db.with(|c| chat_keys::add_team(c, &team, &key)).map_err(|e| e.to_string())?;
        db.with(|c| conversations::open_room(c, "team", &format!("team:{}", team.id), &team.name, None, "")).map_err(|e| e.to_string())?;
        self.push(Self::join_frame(&team, &key));
        Ok(self.invite_code(&team, &key))
    }

    pub fn team_invite(&self, db: &Db, team_id: &str) -> Result<String, String> {
        let team = db.with(|c| chat_keys::team(c, team_id)).map_err(|e| e.to_string())?.ok_or("no such team")?;
        if team.removed {
            return Err("you're no longer in this team; ask a member for a new invite".into());
        }
        let key = db.with(|c| chat_keys::team_key(c, team_id, team.key_version)).map_err(|e| e.to_string())?.ok_or("key missing")?;
        Ok(self.invite_code(&team, &key))
    }

    /// Join from an invite code. Returns the servers it names, so a first
    /// join can connect to them.
    pub fn team_join(&self, db: &Db, code: &str) -> Result<(String, Vec<String>), String> {
        let invite: Invite = e2e::decode_code(INVITE_PREFIX, code).ok_or("that isn't a DeskBuddy team invite (it starts with DBT1-)")?;
        let key = e2e::parse_key(&invite.key).ok_or("the invite's key is damaged")?;
        let dh = e2e::parse_key(&invite.dh).ok_or("the invite's key is damaged")?;
        if invite.id.len() != 32 || invite.kv == 0 {
            return Err("the invite is damaged".into());
        }
        let team = chat_keys::Team {
            id: invite.id,
            name: invite.name,
            dh_secret: dh,
            key_version: invite.kv,
            home: invite.home,
            servers: invite.servers.clone(),
            removed: false,
        };
        let team = db.with(|c| chat_keys::add_team(c, &team, &key)).map_err(|e| e.to_string())?;
        let conv = db.with(|c| conversations::open_room(c, "team", &format!("team:{}", team.id), &team.name, None, "")).map_err(|e| e.to_string())?;
        let _ = db.with(|c| conversations::set_read_only(c, conv.id, ""));
        self.push(Self::join_frame(&team, &key));
        Ok((team.name, invite.servers))
    }

    pub fn team_leave(&self, db: &Db, team_id: &str) -> Result<(), String> {
        self.require_online()?;
        self.push(json!({ "type": "teamLeave", "teamId": team_id }).to_string());
        mark_team_gone(db, team_id, "You left this team.")
    }

    /// New team key: everyone else must join again with the new invite.
    pub fn team_rotate(&self, db: &Db, team_id: &str) -> Result<String, String> {
        self.require_online()?;
        let team = db.with(|c| chat_keys::team(c, team_id)).map_err(|e| e.to_string())?.ok_or("no such team")?;
        let old = db.with(|c| chat_keys::team_key(c, team_id, team.key_version)).map_err(|e| e.to_string())?.ok_or("key missing")?;
        let fresh = crypto::random_key().map_err(|e| e.to_string())?;
        let next = chat_keys::Team { key_version: team.key_version + 1, ..team };
        let next = db.with(|c| chat_keys::add_team(c, &next, &fresh)).map_err(|e| e.to_string())?;
        self.push(
            json!({ "type": "teamRotate", "teamId": team_id, "proof": e2e::team_proof(&old), "newProof": e2e::team_proof(&fresh) })
                .to_string(),
        );
        Ok(self.invite_code(&next, &fresh))
    }

    /// A team's public address, for another team's request.
    pub fn team_address(&self, db: &Db, team_id: &str) -> Result<String, String> {
        let team = db.with(|c| chat_keys::team(c, team_id)).map_err(|e| e.to_string())?.ok_or("no such team")?;
        let (home, servers) = {
            let inner = self.lock();
            (if team.home.is_empty() { inner.home.clone().unwrap_or_default() } else { team.home.clone() }, if team.servers.is_empty() { inner.servers.clone() } else { team.servers.clone() })
        };
        if home.is_empty() {
            return Err("connect to the team's server once first".into());
        }
        let address = Address { v: 1, id: team.id.clone(), name: team.name.clone(), dh_pub: e2e::dh_public(&team.dh_secret), home, servers };
        Ok(e2e::encode_code(ADDRESS_PREFIX, &address))
    }

    /// Ask another team to chat: "group", "temp" (with `hours`, archive kept
    /// `retention_days`, None = forever) or "personal".
    pub fn link_request(&self, db: &Db, my_team: &str, address: &str, kind: &str, hours: Option<u32>, retention_days: Option<u32>) -> Result<(), String> {
        self.require_online()?;
        let to: Address = e2e::decode_code(ADDRESS_PREFIX, address).ok_or("that isn't a DeskBuddy team address (it starts with DBA1-)")?;
        if !matches!(kind, "group" | "temp" | "personal") {
            return Err("unknown request type".into());
        }
        if kind == "temp" && !hours.is_some_and(|h| (1..=72).contains(&h)) {
            return Err("a temporary group lasts 1–72 hours".into());
        }
        let team = db.with(|c| chat_keys::team(c, my_team)).map_err(|e| e.to_string())?.ok_or("no such team")?;
        if team.id == to.id {
            return Err("that's the same team".into());
        }
        let link_id = random_hex16();
        let mut share = json!(null);
        if kind == "temp" {
            let pair = e2e::pair_key(&team.dh_secret, &to.dh_pub, &link_id).ok_or("their address has an invalid key")?;
            let key = latest_key(db, &team)?;
            let (own, to_peer) = e2e::new_share(&key, &pair, &link_id).map_err(|e| e.to_string())?;
            share = json!({ "own": own, "toPeer": to_peer });
        }
        self.push(
            json!({
                "type": "linkRequest",
                "linkId": link_id,
                "kind": kind,
                "hours": hours,
                "retentionDays": retention_days,
                "fromTeam": team.id,
                "toTeam": { "id": to.id, "name": to.name, "dhPub": to.dh_pub, "home": to.home, "servers": to.servers },
                "fedToken": random_hex16(),
                "share": share,
            })
            .to_string(),
        );
        Ok(())
    }

    pub fn link_respond(&self, db: &Db, link_id: &str, accept: bool) -> Result<(), String> {
        self.require_online()?;
        let link = self.lock().links.get(link_id).cloned().ok_or("no such request")?;
        let mut share = json!(null);
        if accept && link.kind == "temp" {
            let team = db.with(|c| chat_keys::team(c, &link.b.id)).map_err(|e| e.to_string())?.ok_or("you don't have the asked team's key")?;
            let pair = e2e::pair_key(&team.dh_secret, &link.a.dh_pub, link_id).ok_or("their team key is invalid")?;
            let key = latest_key(db, &team)?;
            let (own, to_peer) = e2e::new_share(&key, &pair, link_id).map_err(|e| e.to_string())?;
            share = json!({ "own": own, "toPeer": to_peer });
        }
        self.push(json!({ "type": "linkRespond", "linkId": link_id, "accept": accept, "share": share }).to_string());
        Ok(())
    }

    /// Offer our half of a closed temporary group's key again.
    pub fn archive_release(&self, db: &Db, link_id: &str) -> Result<(), String> {
        self.require_online()?;
        let link = self.lock().links.get(link_id).cloned().ok_or("no such group")?;
        let teams = db.with(|c| chat_keys::teams(c)).map_err(|e| e.to_string())?;
        let side = my_side(&teams, &link).ok_or("your team isn't in this group")?;
        let team = teams.iter().find(|t| t.id == link.team(side).id).expect("found");
        let pair = e2e::pair_key(&team.dh_secret, &link.team(other(side)).dh_pub, link_id).ok_or("invalid key")?;
        let share = own_share(db, team, link.share(side), link_id).ok_or("your team's half of the key is missing")?;
        let to_peer = e2e::reseal_for_peer(&pair, &share, link_id).map_err(|e| e.to_string())?;
        self.push(json!({ "type": "archiveRelease", "linkId": link_id, "toPeer": to_peer }).to_string());
        Ok(())
    }

    pub fn archive_lock(&self, link_id: &str) -> Result<(), String> {
        self.require_online()?;
        self.push(json!({ "type": "archiveLock", "linkId": link_id }).to_string());
        Ok(())
    }
}

fn latest_key(db: &Db, team: &chat_keys::Team) -> Result<Key, String> {
    db.with(|c| chat_keys::team_key(c, &team.id, team.key_version)).map_err(|e| e.to_string())?.ok_or_else(|| "team key missing".into())
}

/// Our half of a temporary group's key, sealed with whichever team key
/// version was current when the group started.
fn own_share(db: &Db, team: &chat_keys::Team, share: &Share, link: &str) -> Option<Key> {
    let sealed = share.own.as_deref()?;
    (1..=team.key_version).rev().find_map(|v| {
        let key = db.with(|c| chat_keys::team_key(c, &team.id, v)).ok().flatten()?;
        e2e::open_own_share(&key, sealed, link)
    })
}

/// Which side of a link our teams are on (a, if both are ours).
fn my_side(teams: &[chat_keys::Team], link: &Link) -> Option<char> {
    ['a', 'b'].into_iter().find(|s| teams.iter().any(|t| t.id == link.team(*s).id))
}

fn mark_team_gone(db: &Db, team_id: &str, why: &str) -> Result<(), String> {
    db.with(|c| {
        chat_keys::set_removed(c, team_id, true)?;
        if let Some(conv) = conversations::by_remote(c, &format!("team:{team_id}"))? {
            conversations::set_read_only(c, conv.id, why)?;
        }
        Ok(())
    })
    .map_err(|e| e.to_string())
}

pub fn spawn(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        let client = app.state::<ChatClient>();
        let mut backoff = BACKOFF_MIN;
        let mut next = 0usize;
        loop {
            let settings = app.state::<SettingsStore>().get();
            let mut candidates = server_list(&settings.chat_server).unwrap_or_default();
            for s in &settings.chat_known_servers {
                if let Ok(Some(url)) = ws_url(s) {
                    if !candidates.contains(&url) {
                        candidates.push(url);
                    }
                }
            }
            if !settings.chat_enabled || candidates.is_empty() {
                let error = server_list(&settings.chat_server).err();
                client.set_status(&app, |i| {
                    i.state = State::Off;
                    i.server.clear();
                    i.me = None;
                    i.error = error;
                    i.out = None;
                    i.users.values_mut().for_each(|u| u.online = false);
                });
                client.wake.notified().await;
                continue;
            }
            let url = candidates[next % candidates.len()].clone();
            client.set_status(&app, |i| {
                i.state = State::Connecting;
                i.server = url.clone();
                i.error = None;
            });
            let started = Instant::now();
            let ended = connect(&app, &client, &url, &settings.chat_name).await;
            client.set_status(&app, |i| {
                i.out = None;
                i.state = State::Offline;
                i.me = None;
                i.error = ended.as_ref().err().cloned();
                i.users.values_mut().for_each(|u| u.online = false);
            });
            if ended.is_ok() {
                backoff = BACKOFF_MIN; // reconfigured: reconnect right away
                continue;
            }
            // Try the next server of the cluster before backing off.
            next += 1;
            if candidates.len() > 1 && next % candidates.len() != 0 {
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
async fn connect(app: &AppHandle, client: &ChatClient, url: &str, name: &str) -> Result<(), String> {
    let db = app.state::<Db>();
    let identity = client.identity(&db)?;
    let (socket, _) = tokio::time::timeout(CONNECT_TIMEOUT, tokio_tungstenite::connect_async(url))
        .await
        .map_err(|_| format!("{url} did not answer"))?
        .map_err(|e| format!("can't reach {url}: {e}"))?;
    let (mut sink, mut stream) = socket.split();

    let first = tokio::time::timeout(CONNECT_TIMEOUT, next_text(&mut stream)).await.map_err(|_| "the chat server sent no challenge".to_string())??;
    let nonce = match serde_json::from_str::<ServerMsg>(&first) {
        Ok(ServerMsg::Challenge { nonce }) => nonce,
        Ok(ServerMsg::Error { message, .. }) => return Err(message),
        _ => return Err("this chat server is too old for this DeskBuddy (it needs the v2 server)".into()),
    };
    let name = if name.trim().is_empty() { default_name() } else { name.trim().to_string() };
    let hello = json!({ "type": "hello", "device": identity.device(), "dhPub": identity.dh_pub(), "name": name, "sig": identity.sign_hello(&nonce) });
    sink.send(Frame::Text(hello.to_string().into())).await.map_err(|e| e.to_string())?;

    let reply = tokio::time::timeout(CONNECT_TIMEOUT, next_text(&mut stream)).await.map_err(|_| "the chat server did not reply to hello".to_string())??;
    let (tx, mut rx) = mpsc::unbounded_channel::<String>();
    match serde_json::from_str::<ServerMsg>(&reply) {
        Ok(ServerMsg::Welcome { you, home, servers, users, teams, links }) => {
            {
                let mut i = client.lock();
                i.out = Some(tx.clone());
                i.users = users.into_iter().map(|u| (u.device.clone(), u)).collect();
                i.state = State::Online;
                i.me = Some(Me { device: you.device.clone(), name: you.name.clone() });
                i.error = None;
                i.home = Some(home.clone());
                i.servers = servers.clone();
                i.teams = teams.iter().map(|t| (t.id.clone(), t.members.clone())).collect();
                i.links = links.iter().map(|l| (l.id.clone(), l.clone())).collect();
            }
            remember_servers(app, &servers);
            welcome_teams(client, &db, &you.device, &home, &servers, &teams);
            for l in &links {
                apply_link(client, &db, l);
            }
            client.emit(app);
        }
        Ok(ServerMsg::Error { message, .. }) => return Err(message),
        _ => return Err("unexpected reply from the chat server".into()),
    }

    let _ = tx.send(json!({ "type": "conversations" }).to_string());
    if let Ok(pending) = db.with(|c| messages::pending_outgoing(c)) {
        for (m, remote) in pending {
            if let Err(e) = client.send(&db, &remote, &m) {
                eprintln!("deskbuddy: chat: can't send a queued message yet: {e}");
            }
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

/// Remember the cluster's servers so the next start can fail over to them.
fn remember_servers(app: &AppHandle, servers: &[String]) {
    let store = app.state::<SettingsStore>();
    let mut known = store.get().chat_known_servers;
    let before = known.len();
    for s in servers {
        if !known.contains(s) {
            known.push(s.clone());
        }
    }
    known.truncate(16);
    if known.len() != before {
        store.update(|s| s.chat_known_servers = known);
    }
}

/// After login: join the server for every team we hold a key for (a new
/// server, or a team joined offline), and keep each team's chat open.
fn welcome_teams(client: &ChatClient, db: &Db, me: &str, home: &str, servers: &[String], joined: &[WireTeam]) {
    let local = db.with(|c| chat_keys::teams(c)).unwrap_or_default();
    for team in local.iter().filter(|t| !t.removed) {
        let on_server = joined.iter().any(|j| j.id == team.id && j.members.iter().any(|m| m == me));
        let _ = db.with(|c| conversations::open_room(c, "team", &format!("team:{}", team.id), &team.name, None, ""));
        if on_server {
            let _ = db.with(|c| chat_keys::set_servers(c, &team.id, home, servers));
        } else if team.home.is_empty() || team.home == home {
            if let Ok(Some(key)) = db.with(|c| chat_keys::team_key(c, &team.id, team.key_version)) {
                client.push(ChatClient::join_frame(team, &key));
            }
        }
    }
}

/// Mirror a link's state into its local conversation.
fn apply_link(client: &ChatClient, db: &Db, l: &Link) {
    if l.kind == "personal" || matches!(l.state.as_str(), "pending" | "declined") {
        return;
    }
    let remote = format!("link:{}", l.id);
    let Ok(conv) = db.with(|c| conversations::open_room(c, "link", &remote, &l.title(), None, "")) else { return };
    let open = l.share_a.to_peer.is_some() && l.share_b.to_peer.is_some();
    let reason = match l.state.as_str() {
        "active" => String::new(),
        "archived" if open => "This temporary group has closed. You're reading its archive.".into(),
        "archived" => "This temporary group has closed. Its archive stays locked until both teams release it.".into(),
        _ => "This group's archive has been deleted.".into(),
    };
    let locked = l.state == "closed" || (l.state == "archived" && !open);
    let _ = db.with(|c| {
        if locked && conv.last_seq > 0 {
            conversations::clear(c, conv.id)?;
        }
        conversations::set_read_only(c, conv.id, &reason)
    });
    if l.state != "active" {
        client.push(json!({ "type": "conversations" }).to_string());
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
    let result: Result<(), String> = match msg {
        ServerMsg::Presence { device, name, online } => {
            client.set_status(app, |i| {
                if let Some(u) = i.users.get_mut(&device) {
                    u.name = name.clone();
                    u.online = online;
                    u.last_seen = crate::db::now_ms();
                }
            });
            db.with(|c| conversations::set_device_name(c, &device, &name)).map_err(|e| e.to_string())
        }
        ServerMsg::User { user } => {
            let _ = db.with(|c| conversations::set_device_name(c, &user.device, &user.name));
            client.set_status(app, |i| {
                let online = i.users.get(&user.device).is_some_and(|u| u.online);
                i.users.insert(user.device.clone(), User { online: online || user.online, ..user });
            });
            Ok(())
        }
        ServerMsg::Team { team } => {
            let me = client.my_device().unwrap_or_default();
            if team.members.contains(&me) {
                if let Ok(Some(t)) = db.with(|c| chat_keys::team(c, &team.id)) {
                    let _ = db.with(|c| conversations::open_room(c, "team", &format!("team:{}", t.id), &t.name, None, ""));
                }
            }
            client.set_status(app, |i| {
                i.teams.insert(team.id.clone(), team.members.clone());
            });
            client.push(json!({ "type": "conversations" }).to_string());
            Ok(())
        }
        ServerMsg::TeamGone { team_id } => {
            let r = mark_team_gone(&db, &team_id, "You're no longer in this team (its key changed). Ask a member for the new invite.");
            client.set_status(app, |i| {
                i.teams.remove(&team_id);
            });
            r
        }
        ServerMsg::Link { link } => {
            apply_link(client, &db, &link);
            client.set_status(app, |i| {
                i.links.insert(link.id.clone(), link);
            });
            client.push(json!({ "type": "conversations" }).to_string());
            Ok(())
        }
        ServerMsg::Message { message } | ServerMsg::Ack { message } => receive(app, client, &db, &message, true).map(|r| {
            if let Some((_, Some(reaction))) = r {
                react(app, &reaction);
            }
        }),
        ServerMsg::Conversations { items } => {
            for item in items {
                match ensure_conversation(client, &db, &item.id) {
                    Some(conv) if item.last_seq > conv.last_seq => request_sync(client, &item.id, conv.last_seq),
                    _ => {}
                }
            }
            Ok(())
        }
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
        ServerMsg::Error { message, client_msg_id: Some(id) } => db
            .with(|c| {
                if let Some(m) = messages::by_client_id(c, &id)? {
                    messages::set_state(c, m.id, "failed")?;
                    changed(app, m.conversation_id);
                }
                eprintln!("deskbuddy: chat message not sent: {message}");
                Ok(())
            })
            .map_err(|e| e.to_string()),
        ServerMsg::Error { message, client_msg_id: None } => {
            client.set_status(app, |i| i.error = Some(message));
            Ok(())
        }
        ServerMsg::Welcome { .. } | ServerMsg::Challenge { .. } => Ok(()),
    };
    if let Err(e) = result {
        eprintln!("deskbuddy: chat: {e}");
    }
}

/// The local conversation for a server conversation id, created if new.
fn ensure_conversation(client: &ChatClient, db: &Db, remote: &str) -> Option<conversations::Conversation> {
    if let Ok(Some(c)) = db.with(|c| conversations::by_remote(c, remote)) {
        return Some(c);
    }
    if let Some(pair) = remote.strip_prefix("dm:") {
        let me = client.my_device()?;
        let (a, b) = pair.split_once('|')?;
        let peer = if a == me { b } else if b == me { a } else { return None };
        if !is_hex_key(peer) {
            return None;
        }
        let name = client.name_of(peer);
        return db.with(|c| conversations::open_room(c, "dm", remote, "", Some(peer), &name)).ok();
    }
    if let Some(team_id) = remote.strip_prefix("team:") {
        let team = db.with(|c| chat_keys::team(c, team_id)).ok().flatten()?;
        return db.with(|c| conversations::open_room(c, "team", remote, &team.name, None, "")).ok();
    }
    let link_id = remote.strip_prefix("link:")?;
    let title = client.lock().links.get(link_id).map(|l| l.title())?;
    db.with(|c| conversations::open_room(c, "link", remote, &title, None, "")).ok()
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

/// Decrypt and store one server message. Live ones (`live`) advance the
/// sync position only when nothing is missing before them; a gap triggers a
/// sync instead. Returns the local conversation id and, if this was a new
/// message from someone else, the reaction set for that chat.
fn receive(app: &AppHandle, client: &ChatClient, db: &Db, m: &Wire, live: bool) -> Result<Option<(i64, Option<String>)>, String> {
    let Some(me) = client.my_device() else { return Ok(None) };
    let Some(conv) = ensure_conversation(client, db, &m.conversation_id) else { return Ok(None) };
    let sender = (m.from != me).then_some(m.from.as_str());
    let aad = e2e::message_aad(&m.conversation_id, &m.from, &m.client_msg_id);
    let body = client
        .key_for(db, &m.conversation_id, e2e::message_version(&m.body))
        .ok()
        .and_then(|(key, _)| e2e::open_message(&key, &m.body, &aad))
        .unwrap_or_else(|| UNREADABLE.to_string());
    let body = if body.trim().is_empty() { UNREADABLE.to_string() } else { body };
    let sender_name = sender.map(|d| client.name_of(d)).unwrap_or_default();
    let local = db
        .with(|c| {
            let have = conversations::get(c, conv.id)?.last_seq;
            let added = messages::apply_remote(
                c,
                &messages::Remote {
                    conversation: conv.id,
                    sender_ip: sender,
                    sender_name: &sender_name,
                    client_msg_id: &m.client_msg_id,
                    seq: m.seq,
                    body: &body,
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
            Ok((conv.id, added))
        })
        .map_err(|e| e.to_string())?;
    let (local, added) = local;
    let from_them = sender.filter(|_| added);
    let poke = from_them.is_some() && body == POKE;
    if let (true, Some(device)) = (poke, from_them) {
        let name = if sender_name.is_empty() { short_id(device) } else { sender_name.clone() };
        poked(app, &conv, device, &name, m.created_at, crate::db::now_ms());
    }
    changed(app, local);
    // A poke has its own reaction instead of the chat's usual one.
    Ok(Some((local, (from_them.is_some() && !poke).then(|| conv.reaction.clone()))))
}

/// Someone poked us: the pet reacts and a bubble says who. Pokes that are
/// stale (sent `POKE_FRESH_MS` ago), from someone who just poked, or in a
/// chat whose pet reaction is off only show up in the chat.
fn poked(app: &AppHandle, conv: &conversations::Conversation, device: &str, name: &str, sent_at: i64, now: i64) {
    static LAST: Mutex<BTreeMap<String, i64>> = Mutex::new(BTreeMap::new());
    if !should_react_to_poke(&mut LAST.lock().unwrap(), &conv.reaction, device, sent_at, now) {
        return;
    }
    let _ = app.emit_to(window::MASCOT, "mascot-react", "poke");
    window::show_bubble(app, &poke_text(name, &conv.room, &conv.title));
}

/// Whether a poke plays, remembering when each person last got a reaction.
fn should_react_to_poke(last: &mut BTreeMap<String, i64>, reaction: &str, device: &str, sent_at: i64, now: i64) -> bool {
    if reaction == "none" || now - sent_at > POKE_FRESH_MS || last.get(device).is_some_and(|t| now - t < POKE_GAP_MS) {
        return false;
    }
    last.insert(device.to_string(), now);
    true
}

fn poke_text(name: &str, room: &str, title: &str) -> String {
    match room {
        "team" | "link" if !title.is_empty() => format!("👉 {name} poked {title}!"),
        _ => format!("👉 {name} poked you!"),
    }
}

/// Find chat servers announced on the LAN (`_deskbuddy._tcp`), for up to `wait`.
pub fn discover(wait: Duration) -> Vec<(String, String)> {
    let Ok(daemon) = mdns_sd::ServiceDaemon::new() else { return Vec::new() };
    let Ok(rx) = daemon.browse("_deskbuddy._tcp.local.") else { return Vec::new() };
    let deadline = Instant::now() + wait;
    let mut found: Vec<(String, String)> = Vec::new();
    while let Some(left) = deadline.checked_duration_since(Instant::now()) {
        match rx.recv_timeout(left) {
            Ok(mdns_sd::ServiceEvent::ServiceResolved(info)) => {
                let name = info.get_fullname().split('.').next().unwrap_or("").to_string();
                for ip in info.get_addresses_v4() {
                    let addr = format!("{ip}:{}", info.get_port());
                    if !found.iter().any(|(_, a)| *a == addr) {
                        found.push((name.clone(), addr));
                    }
                }
            }
            Ok(_) => {}
            Err(_) => break,
        }
    }
    let _ = daemon.shutdown();
    found
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pokes_react_once_per_person_and_only_when_fresh() {
        let mut last = BTreeMap::new();
        let now = 10_000_000;
        assert!(should_react_to_poke(&mut last, "", "a", now - 500, now), "a fresh poke plays");
        assert!(!should_react_to_poke(&mut last, "", "a", now + 3_000, now + 3_000), "the same friend again right away: quiet");
        assert!(should_react_to_poke(&mut last, "", "b", now + 3_000, now + 3_000), "someone else may poke meanwhile");
        assert!(should_react_to_poke(&mut last, "", "a", now + POKE_GAP_MS, now + POKE_GAP_MS), "after the gap it plays again");
        assert!(!should_react_to_poke(&mut last, "", "c", now - POKE_FRESH_MS - 1, now), "caught up later: too old to play");
        assert!(!should_react_to_poke(&mut last, "none", "d", now, now), "pet reaction off for that chat");
        assert!(!last.contains_key("c") && !last.contains_key("d"), "skipped pokes don't start the gap");
        assert!(should_react_to_poke(&mut last, "mood_happy", "d", now, now), "a custom reaction still plays the poke");
    }

    #[test]
    fn poke_bubble_says_who() {
        assert_eq!(poke_text("Mohit", "dm", ""), "👉 Mohit poked you!");
        assert_eq!(poke_text("Mohit", "team", "Design"), "👉 Mohit poked Design!");
        assert_eq!(poke_text("Mohit", "link", "Design + Ops"), "👉 Mohit poked Design + Ops!");
        assert_eq!(poke_text("Mohit", "team", ""), "👉 Mohit poked you!", "no room name: still says who");
    }

    #[test]
    fn server_addresses() {
        assert_eq!(ws_url("").unwrap(), None);
        assert_eq!(ws_url("192.168.1.5").unwrap().unwrap(), "ws://192.168.1.5:8787/ws");
        assert_eq!(ws_url("192.168.1.5:9000").unwrap().unwrap(), "ws://192.168.1.5:9000/ws");
        assert_eq!(ws_url(" ws://chat.lan:9000/ws/ ").unwrap().unwrap(), "ws://chat.lan:9000/ws");
        assert_eq!(ws_url("http://10.0.0.2:8787").unwrap().unwrap(), "ws://10.0.0.2:8787/ws", "addresses from the server");
        assert_eq!(ws_url("fe80::1").unwrap().unwrap(), "ws://[fe80::1]:8787/ws");
        assert_eq!(ws_url("[fe80::1]:9000").unwrap().unwrap(), "ws://[fe80::1]:9000/ws");
        assert!(ws_url("wss://x").is_err());
        assert!(ws_url("a b").is_err());
        assert_eq!(server_list("10.0.0.1, 10.0.0.2:9000,10.0.0.1").unwrap(), ["ws://10.0.0.1:8787/ws", "ws://10.0.0.2:9000/ws"]);
        assert!(server_list("ok, a b").is_err());
    }

    /// Frames exactly as the chat server (server/src/protocol.rs) writes them.
    #[test]
    fn parses_server_frames() {
        let k = "ab".repeat(32);
        let t = "cd".repeat(16);
        let challenge = r#"{"type":"challenge","nonce":"n1"}"#;
        assert!(matches!(serde_json::from_str(challenge), Ok(ServerMsg::Challenge { .. })));
        let team_ref = format!(r#"{{"id":"{t}","name":"A","dhPub":"{k}","home":"{t}","servers":[],"members":[]}}"#);
        let link = format!(
            r#"{{"id":"{t}","kind":"temp","state":"active","a":{team_ref},"b":{team_ref},"hours":2,"expiresAt":5,"retentionDays":null,
                "purgeAt":null,"shareA":{{"own":"x","toPeer":"y"}},"shareB":{{"own":null,"toPeer":null}},"createdAt":1}}"#
        );
        let welcome = format!(
            r#"{{"type":"welcome","you":{{"device":"{k}","name":"me","dhPub":"{k}","online":true,"lastSeen":5,"local":true}},
                "home":"{t}","servers":["http://10.0.0.1:8787"],"users":[],"teams":[{{"id":"{t}","name":"A","dhPub":"{k}","members":["{k}"]}}],
                "links":[{link}]}}"#
        );
        assert!(matches!(serde_json::from_str(&welcome), Ok(ServerMsg::Welcome { ref links, .. }) if links[0].hours == Some(2)));
        let message = format!(r#"{{"id":"65f0","conversationId":"team:{t}","seq":3,"from":"{k}","clientMsgId":"c9","body":"e1.1.x","createdAt":7}}"#);
        assert!(matches!(serde_json::from_str(&format!(r#"{{"type":"ack","clientMsgId":"c9","message":{message}}}"#)), Ok(ServerMsg::Ack { .. })));
        let page = format!(r#"{{"type":"messages","conversationId":"team:{t}","items":[{message}],"more":false}}"#);
        assert!(matches!(serde_json::from_str(&page), Ok(ServerMsg::Messages { more: false, .. })));
        let gone = format!(r#"{{"type":"teamGone","teamId":"{t}"}}"#);
        assert!(matches!(serde_json::from_str(&gone), Ok(ServerMsg::TeamGone { .. })));
        let err = r#"{"type":"error","code":"rate_limited","message":"slow down","clientMsgId":"c9"}"#;
        assert!(matches!(serde_json::from_str(err), Ok(ServerMsg::Error { client_msg_id: Some(_), .. })));
    }

    fn user(device: &str, name: &str) -> User {
        User { device: device.into(), name: name.into(), dh_pub: String::new(), online: true, last_seen: 0, local: true }
    }

    #[test]
    fn resolve_by_name_or_id() {
        let client = ChatClient::default();
        {
            let mut i = client.lock();
            i.state = State::Online;
            i.me = Some(Me { device: "a1".repeat(32), name: "me".into() });
            for (d, n) in [("b2", "Asha"), ("c3", "Ashok"), ("d4", "Asha"), ("e5", "Ravi")] {
                i.users.insert(d.repeat(32), user(&d.repeat(32), n));
            }
        }
        assert_eq!(client.resolve("ravi").unwrap().unwrap().name, "Ravi", "case-insensitive");
        assert_eq!(client.resolve("asho").unwrap().unwrap().name, "Ashok", "prefix");
        assert_eq!(client.resolve("asha").unwrap().unwrap_err().len(), 2, "two people named Asha");
        assert_eq!(client.resolve("d4d4d4").unwrap().unwrap().device, "d4".repeat(32), "device id prefix");
        assert!(client.resolve("nobody").is_err());
        assert!(client.resolve("me").is_err(), "yourself is not listed");
        assert!(client.resolve(" ").is_err());
    }

    #[test]
    fn codes() {
        let a = Address { v: 1, id: "i".into(), name: "Ops".into(), dh_pub: "k".into(), home: "h".into(), servers: vec![] };
        let code = e2e::encode_code(ADDRESS_PREFIX, &a);
        let back: Address = e2e::decode_code(ADDRESS_PREFIX, &code).unwrap();
        assert_eq!(back.name, "Ops");
        assert!(e2e::decode_code::<Invite>(INVITE_PREFIX, &code).is_none(), "an address is not an invite");
    }

    #[test]
    fn identity_is_created_once() {
        let db = Db::open_in_memory().unwrap();
        let client = ChatClient::default();
        let a = client.identity(&db).unwrap().device();
        let fresh = ChatClient::default();
        assert_eq!(fresh.identity(&db).unwrap().device(), a, "loaded from the database");
    }
}
