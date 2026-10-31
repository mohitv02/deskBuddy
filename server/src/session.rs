//! One WebSocket connection: challenge, signed hello, then a loop of requests.

use std::net::IpAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};

use axum::extract::ws::{Message, WebSocket};
use futures_util::{SinkExt, StreamExt};
use mongodb::bson::{doc, Bson, DateTime};
use tokio::sync::mpsc;

use crate::fed::{self, Event, FedMessage};
use crate::hub::{Outbox, OUTBOX_CAPACITY};
use crate::protocol::{self as p, ChatMessage, ClientMsg, LinkKind, LinkState, ServerMsg, Share, TeamRef};
use crate::rooms::{self, Access};
use crate::store::{bson, JoinError, LinkDoc, Store};
use crate::App;

const HELLO_TIMEOUT: Duration = Duration::from_secs(10);
/// At most this many sends per window, per connection.
const SEND_BURST: usize = 20;
const SEND_WINDOW: Duration = Duration::from_secs(10);
const USER_LIST_LIMIT: i64 = 1000;
const CONVERSATION_LIMIT: i64 = 300;

struct Session {
    app: Arc<App>,
    device: String,
    conn_id: u64,
    out: Outbox,
    recent_sends: Vec<Instant>,
}

fn verify(device: &str, dh_pub: &str, nonce: &str, sig: &str) -> bool {
    use ed25519_dalek::{Signature, Verifier, VerifyingKey};
    let (Some(key), Some(sig)) = (unhex::<32>(device), unhex::<64>(sig)) else { return false };
    let Ok(key) = VerifyingKey::from_bytes(&key) else { return false };
    key.verify(p::hello_payload(nonce, device, dh_pub).as_bytes(), &Signature::from_bytes(&sig)).is_ok()
}

fn unhex<const N: usize>(s: &str) -> Option<[u8; N]> {
    if s.len() != N * 2 {
        return None;
    }
    let mut out = [0u8; N];
    for (i, b) in out.iter_mut().enumerate() {
        *b = u8::from_str_radix(s.get(i * 2..i * 2 + 2)?, 16).ok()?;
    }
    Some(out)
}

pub async fn run(socket: WebSocket, peer: IpAddr, app: Arc<App>) {
    let (mut sink, mut stream) = socket.split();
    let nonce = crate::random_hex::<16>();
    if sink.send(Message::Text(ServerMsg::Challenge { nonce: nonce.clone() }.to_json().into())).await.is_err() {
        return;
    }
    let (device, dh_pub, name, sig) = match tokio::time::timeout(HELLO_TIMEOUT, next_client_msg(&mut stream)).await {
        Ok(Some(Ok(ClientMsg::Hello { device, dh_pub, name, sig }))) => (device, dh_pub, name, sig),
        Ok(Some(Ok(_))) => return reject(&mut sink, "hello_required", "send hello first").await,
        Ok(Some(Err(e))) => return reject(&mut sink, "bad_request", e).await,
        _ => return,
    };
    if !p::is_key(&device) || !p::is_key(&dh_pub) || !verify(&device, &dh_pub, &nonce, &sig) {
        return reject(&mut sink, "bad_identity", "the device signature does not check out").await;
    }
    let Some(store) = app.store().filter(|_| app.db_ok()) else {
        return reject(&mut sink, "unavailable", "the chat server's database is not connected").await;
    };
    let name = p::clean_name(name.as_deref(), &device[..8]);
    let me = match store.touch_user(&device, &name, &dh_pub).await {
        Ok(u) => u,
        Err(e) => {
            eprintln!("chat: store error on hello: {e}");
            return reject(&mut sink, "unavailable", "storage is unavailable").await;
        }
    };

    // The welcome must be the first frame: queue it before this connection
    // can receive any push. Anything sent in between is caught up by the
    // app's `conversations` + `sync` right after the welcome.
    let (out, mut outbox) = mpsc::channel::<String>(OUTBOX_CAPACITY);
    let _ = out.send(welcome(&app, &store, &device, me.info(true)).await.to_json()).await;
    let (conn_id, came_online) = app.hub.register(&device, out.clone());
    eprintln!("chat: {name} ({}…, {peer}) connected", &device[..12]);
    let _ = store.set_presence(&app.instance, std::slice::from_ref(&device)).await;
    if came_online {
        let frame = ServerMsg::Presence { device: device.clone(), name: name.clone(), online: true }.to_json();
        app.deliver_all(&frame, &device).await;
    }
    let writer = tokio::spawn(async move {
        while let Some(frame) = outbox.recv().await {
            if sink.send(Message::Text(frame.into())).await.is_err() {
                break;
            }
        }
        let _ = sink.close().await;
    });

    let mut s = Session { app: app.clone(), device: device.clone(), conn_id, out, recent_sends: Vec::new() };

    while let Some(msg) = next_client_msg(&mut stream).await {
        match msg {
            Ok(m) => s.handle(m).await,
            Err(e) => s.reply(ServerMsg::error("bad_request", e)).await,
        }
    }

    drop(s);
    if app.hub.unregister(&device, conn_id) {
        if let Some(store) = app.store() {
            let _ = store.clear_presence(&app.instance, &device).await;
            let elsewhere = store.online_devices().await.map(|l| l.contains(&device)).unwrap_or(false);
            if !elsewhere {
                let frame = ServerMsg::Presence { device: device.clone(), name, online: false }.to_json();
                app.deliver_all(&frame, &device).await;
            }
            let _ = store.mark_seen(&device).await;
        }
    }
    writer.abort();
    eprintln!("chat: {}… disconnected", &device[..12]);
}

/// Next text frame parsed as a request; `None` when the socket closes.
async fn next_client_msg(stream: &mut futures_util::stream::SplitStream<WebSocket>) -> Option<Result<ClientMsg, String>> {
    while let Some(frame) = stream.next().await {
        match frame {
            Ok(Message::Text(text)) => return Some(serde_json::from_str(&text).map_err(|e| format!("invalid request: {e}"))),
            Ok(Message::Close(_)) | Err(_) => return None,
            Ok(_) => continue, // ping/pong are answered by the library; binary is ignored
        }
    }
    None
}

async fn reject(sink: &mut futures_util::stream::SplitSink<WebSocket, Message>, code: &'static str, message: impl Into<String>) {
    let _ = sink.send(Message::Text(ServerMsg::error(code, message).to_json().into())).await;
    let _ = sink.close().await;
}

/// Who and what this device sees on login.
async fn welcome(app: &App, store: &Store, device: &str, you: p::UserInfo) -> ServerMsg {
    let teams = store.teams_of(device).await.unwrap_or_default();
    let team_ids: Vec<String> = teams.iter().map(|t| t.id.clone()).collect();
    let mut links = Vec::new();
    for l in store.links_of(&team_ids).await.unwrap_or_default() {
        if rooms::my_side(store, &l, device).await.is_some() {
            links.push(l);
        }
    }
    let link_ids: Vec<String> = links.iter().map(|l| l.id.clone()).collect();
    let mut online = store.online_devices().await.unwrap_or_default();
    online.extend(app.hub.devices());
    let users = store
        .users_visible(&link_ids, USER_LIST_LIMIT)
        .await
        .unwrap_or_default()
        .iter()
        .map(|u| u.info(online.contains(&u.device) || u.device == device))
        .collect();
    let servers = store.live_servers().await.ok().filter(|s| !s.is_empty()).unwrap_or_else(|| app.urls());
    ServerMsg::Welcome {
        you,
        home: store.home.clone(),
        servers,
        users,
        teams: teams.iter().map(|t| t.info()).collect(),
        links: links.iter().map(|l| l.info()).collect(),
    }
}

fn store_error(e: mongodb::error::Error) -> ServerMsg {
    eprintln!("chat: store error: {e}");
    ServerMsg::error("unavailable", "storage error; try again")
}

type Reply = Result<(), ServerMsg>;

impl Session {
    async fn reply(&self, msg: ServerMsg) {
        let _ = self.out.send(msg.to_json()).await;
    }

    fn store(&self) -> Result<Arc<Store>, ServerMsg> {
        self.app.store().ok_or_else(|| ServerMsg::error("unavailable", "the chat server's database is not connected"))
    }

    /// This home's live servers (falling back to our own address).
    async fn servers(&self, store: &Store) -> Vec<String> {
        store.live_servers().await.ok().filter(|s| !s.is_empty()).unwrap_or_else(|| self.app.urls())
    }

    async fn my_links(&self, store: &Store) -> Result<Vec<LinkDoc>, ServerMsg> {
        let teams: Vec<String> = store.teams_of(&self.device).await.map_err(store_error)?.into_iter().map(|t| t.id).collect();
        let mut links = store.links_of(&teams).await.map_err(store_error)?;
        // Only links whose local side includes us (not just the other side's id).
        let mut mine = Vec::new();
        for l in links.drain(..) {
            if rooms::my_side(store, &l, &self.device).await.is_some() {
                mine.push(l);
            }
        }
        Ok(mine)
    }

    async fn handle(&mut self, msg: ClientMsg) {
        let result = match msg {
            ClientMsg::Hello { .. } => Err(ServerMsg::error("bad_request", "already said hello")),
            ClientMsg::Send { conversation_id, client_msg_id, body } => {
                self.send(&conversation_id, &client_msg_id, &body).await.map_err(|e| e.for_send(&client_msg_id))
            }
            ClientMsg::Conversations => self.conversations().await,
            ClientMsg::Sync { conversation_id, after_seq, limit } => self.sync(&conversation_id, after_seq, limit).await,
            ClientMsg::TeamJoin { team_id, name, dh_pub, proof } => self.team_join(&team_id, &name, &dh_pub, &proof).await,
            ClientMsg::TeamLeave { team_id } => self.team_leave(&team_id).await,
            ClientMsg::TeamRotate { team_id, proof, new_proof } => self.team_rotate(&team_id, &proof, &new_proof).await,
            ClientMsg::LinkRequest { link_id, kind, hours, retention_days, from_team, to_team, fed_token, share } => {
                self.link_request(link_id, kind, hours, retention_days, &from_team, to_team, fed_token, share).await
            }
            ClientMsg::LinkRespond { link_id, accept, share } => self.link_respond(&link_id, accept, share).await,
            ClientMsg::ArchiveRelease { link_id, to_peer } => self.archive_release(&link_id, to_peer).await,
            ClientMsg::ArchiveLock { link_id } => self.archive_lock(&link_id).await,
        };
        if let Err(e) = result {
            self.reply(e).await;
        }
    }

    fn rate_limited(&mut self) -> bool {
        let now = Instant::now();
        self.recent_sends.retain(|t| now.duration_since(*t) < SEND_WINDOW);
        if self.recent_sends.len() >= SEND_BURST {
            return true;
        }
        self.recent_sends.push(now);
        false
    }

    async fn send(&mut self, conversation: &str, client_msg_id: &str, body: &str) -> Reply {
        if !p::check_client_msg_id(client_msg_id) {
            return Err(ServerMsg::error("bad_request", "clientMsgId must be 1-64 letters, digits, - or _"));
        }
        p::check_body(body).map_err(|e| ServerMsg::error("bad_request", e))?;
        if self.rate_limited() {
            return Err(ServerMsg::error("rate_limited", "too many messages; wait a few seconds"));
        }
        let store = self.store()?;
        let room = rooms::open(&store, conversation, &self.device, Access::Write).await?;
        let (doc, is_new) =
            store.append(&room.id, &room.dm_members, &self.device, client_msg_id, body, None).await.map_err(store_error)?;
        let message = ChatMessage::from(doc);
        if is_new {
            let push = ServerMsg::Message { message: message.clone() }.to_json();
            self.app.deliver(&room.local, &push, Some(self.conn_id)).await;
            for link in &room.forward {
                let m = FedMessage {
                    conversation_id: message.conversation_id.clone(),
                    from: message.from.clone(),
                    client_msg_id: message.client_msg_id.clone(),
                    body: message.body.clone(),
                    created_at: message.created_at,
                };
                fed::send(&store, link, Event::Message { message: m }).await;
            }
        }
        self.reply(ServerMsg::Ack { client_msg_id: client_msg_id.to_string(), message }).await;
        Ok(())
    }

    async fn conversations(&self) -> Reply {
        let store = self.store()?;
        let mut ids: Vec<String> = store.teams_of(&self.device).await.map_err(store_error)?.iter().map(|t| format!("team:{}", t.id)).collect();
        ids.extend(self.my_links(&store).await?.iter().filter(|l| rooms::readable(l)).map(|l| format!("link:{}", l.id)));
        let list = store.conversations_for(&self.device, &ids, CONVERSATION_LIMIT).await.map_err(store_error)?;
        self.reply(ServerMsg::Conversations { items: list.iter().map(|c| c.info()).collect() }).await;
        Ok(())
    }

    async fn sync(&self, conversation: &str, after_seq: i64, limit: Option<u32>) -> Reply {
        let store = self.store()?;
        let room = rooms::open(&store, conversation, &self.device, Access::Read).await?;
        let limit = limit.unwrap_or(p::MAX_SYNC_PAGE).clamp(1, p::MAX_SYNC_PAGE);
        let docs = store.messages_after(&room.id, after_seq, limit as i64).await.map_err(store_error)?;
        let more = docs.len() == limit as usize;
        let items = docs.into_iter().map(ChatMessage::from).collect();
        self.reply(ServerMsg::Messages { conversation_id: room.id, items, more }).await;
        Ok(())
    }

    /// Tell every linked home about a team's current members.
    async fn announce_members(&self, store: &Store, team: &str) {
        let links = store.links_of(&[team.to_string()]).await.unwrap_or_default();
        for link in links.iter().filter(|l| l.state == LinkState::Active || l.state == LinkState::Pending) {
            let Some(side) = link.side_of(team) else { continue };
            let members = rooms::member_list(store, team).await;
            let servers = self.servers(store).await;
            let key = if side == 'a' { "a" } else { "b" };
            let set = doc! { format!("{key}.members"): bson(&members), format!("{key}.servers"): bson(&servers) };
            let Ok(Some(updated)) = store.update_link(&link.id, doc! {}, set).await else { continue };
            fed::send(store, &updated, Event::Members { team: updated.team(side).clone() }).await;
            fed::push_link(&self.app, store, &updated).await;
        }
    }

    async fn team_join(&self, team: &str, name: &str, dh_pub: &str, proof: &str) -> Reply {
        let name = name.trim();
        if !p::is_id(team) || !p::is_key(dh_pub) || !p::is_key(proof) || name.is_empty() || name.chars().count() > p::MAX_NAME_CHARS {
            return Err(ServerMsg::error("bad_request", "bad team details"));
        }
        let store = self.store()?;
        let doc = match store.team_join(team, name, dh_pub, &crate::sha256_hex(proof), &self.device).await {
            Ok(t) => t,
            Err(JoinError::WrongKey) => return Err(ServerMsg::error("wrong_key", "that team key is not valid (old invite?)")),
            Err(JoinError::Db(e)) => return Err(store_error(e)),
        };
        self.app.deliver(&doc.members, &ServerMsg::Team { team: doc.info() }.to_json(), None).await;
        for l in self.my_links(&store).await.unwrap_or_default() {
            self.reply(ServerMsg::Link { link: l.info() }).await;
        }
        self.announce_members(&store, team).await;
        Ok(())
    }

    async fn team_leave(&self, team: &str) -> Reply {
        let store = self.store()?;
        if let Some(doc) = store.team_leave(team, &self.device).await.map_err(store_error)? {
            self.app.deliver(&doc.members, &ServerMsg::Team { team: doc.info() }.to_json(), None).await;
        }
        self.app.deliver(std::slice::from_ref(&self.device), &ServerMsg::TeamGone { team_id: team.into() }.to_json(), None).await;
        self.announce_members(&store, team).await;
        Ok(())
    }

    async fn team_rotate(&self, team: &str, proof: &str, new_proof: &str) -> Reply {
        if !p::is_key(proof) || !p::is_key(new_proof) {
            return Err(ServerMsg::error("bad_request", "bad proof"));
        }
        let store = self.store()?;
        let (doc, dropped) = match store.team_rotate(team, &crate::sha256_hex(proof), &crate::sha256_hex(new_proof), &self.device).await {
            Ok(r) => r,
            Err(JoinError::WrongKey) => return Err(ServerMsg::error("wrong_key", "you are not in that team, or its key changed")),
            Err(JoinError::Db(e)) => return Err(store_error(e)),
        };
        self.app.deliver(&dropped, &ServerMsg::TeamGone { team_id: team.into() }.to_json(), None).await;
        self.app.deliver(&doc.members, &ServerMsg::Team { team: doc.info() }.to_json(), None).await;
        self.announce_members(&store, team).await;
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    async fn link_request(
        &self,
        link_id: String,
        kind: LinkKind,
        hours: Option<u32>,
        retention_days: Option<u32>,
        from_team: &str,
        to_team: TeamRef,
        fed_token: String,
        share: Option<Share>,
    ) -> Reply {
        let bad = |m: &str| ServerMsg::error("bad_request", m);
        if !p::is_id(&link_id) || !p::is_id(&fed_token) {
            return Err(bad("bad link id"));
        }
        p::check_team_ref(&to_team).map_err(bad)?;
        if to_team.id == from_team {
            return Err(bad("a team can't link to itself"));
        }
        let hours = match kind {
            LinkKind::Temp => Some(hours.filter(|h| (1..=p::MAX_TEMP_HOURS).contains(h)).ok_or_else(|| bad("temporary groups last 1-72 hours"))?),
            _ => None,
        };
        let share = share.unwrap_or_default();
        if !p::check_share(&share) || (kind == LinkKind::Temp && (share.own.is_none() || share.to_peer.is_none())) {
            return Err(bad("a temporary group needs your half of the archive key"));
        }
        let store = self.store()?;
        let mine = store.team(from_team).await.map_err(store_error)?.filter(|t| t.members.contains(&self.device));
        let mine = mine.ok_or_else(|| ServerMsg::error("not_found", "you are not in that team"))?;
        let servers = self.servers(&store).await;
        let a = TeamRef {
            id: mine.id.clone(),
            name: mine.name.clone(),
            dh_pub: mine.dh_pub.clone(),
            home: store.home.clone(),
            servers,
            members: rooms::member_list(&store, &mine.id).await,
        };
        let mut b = TeamRef { members: vec![], ..to_team };
        let same_home = b.home == store.home;
        if same_home {
            let t = store.team(&b.id).await.map_err(store_error)?.ok_or_else(|| ServerMsg::error("not_found", "no such team on this server"))?;
            b = TeamRef { id: t.id.clone(), name: t.name.clone(), dh_pub: t.dh_pub.clone(), home: store.home.clone(), servers: a.servers.clone(), members: rooms::member_list(&store, &t.id).await };
        }
        let now = DateTime::now();
        let link = LinkDoc {
            id: link_id,
            kind,
            state: LinkState::Pending,
            a,
            b,
            hours,
            expires_at: None,
            retention_days: retention_days.map(|d| d.min(p::MAX_RETENTION_DAYS)),
            purge_at: None,
            share_a: share,
            share_b: Share::default(),
            fed_token,
            created_at: now,
            updated_at: now,
        };
        if !store.insert_link(&link).await.map_err(store_error)? {
            return Err(bad("that link id is taken"));
        }
        if !same_home {
            fed::send(&store, &link, Event::Request { link: link.info() }).await;
        }
        fed::push_link(&self.app, &store, &link).await;
        Ok(())
    }

    async fn link_respond(&self, link_id: &str, accept: bool, share: Option<Share>) -> Reply {
        let store = self.store()?;
        let link = store.link(link_id).await.map_err(store_error)?.ok_or_else(|| ServerMsg::error("not_found", "no such request"))?;
        let side = rooms::my_side(&store, &link, &self.device).await;
        if side != Some('b') || link.state != LinkState::Pending {
            return Err(ServerMsg::error("not_found", "no pending request for your team"));
        }
        let share = share.unwrap_or_default();
        if !p::check_share(&share) || (accept && link.kind == LinkKind::Temp && (share.own.is_none() || share.to_peer.is_none())) {
            return Err(ServerMsg::error("bad_request", "accepting a temporary group needs your half of the archive key"));
        }
        let state = if accept { LinkState::Active } else { LinkState::Declined };
        let mut set = doc! {
            "state": bson(&state),
            "shareB": bson(&share),
            "b.members": bson(&rooms::member_list(&store, &link.b.id).await),
            "b.servers": bson(&self.servers(&store).await),
        };
        if accept && link.kind == LinkKind::Temp {
            let hours = link.hours.unwrap_or(1) as i64;
            set.insert("expiresAt", DateTime::from_millis(DateTime::now().timestamp_millis() + hours * 3_600_000));
        }
        // Only if still pending: two members accepting at once answer once.
        let link = store
            .update_link(link_id, doc! { "state": "pending" }, set)
            .await
            .map_err(store_error)?
            .ok_or_else(|| ServerMsg::error("not_found", "no pending request for your team"))?;
        let expires_at = link.expires_at.map(|d| d.timestamp_millis());
        fed::send(&store, &link, Event::Respond { accept, team: link.b.clone(), share: Some(share), expires_at }).await;
        fed::push_link(&self.app, &store, &link).await;
        Ok(())
    }

    async fn archive_release(&self, link_id: &str, to_peer: String) -> Reply {
        if !p::check_blob(&to_peer) {
            return Err(ServerMsg::error("bad_request", "bad key share"));
        }
        let store = self.store()?;
        let link = store.link(link_id).await.map_err(store_error)?.ok_or_else(|| ServerMsg::error("not_found", "no such group"))?;
        let side = rooms::my_side(&store, &link, &self.device).await.ok_or_else(|| ServerMsg::error("not_found", "no such group"))?;
        let field = if side == 'a' { "shareA.toPeer" } else { "shareB.toPeer" };
        let link = store
            .update_link(link_id, doc! { "state": "archived" }, doc! { field: &to_peer })
            .await
            .map_err(store_error)?
            .ok_or_else(|| ServerMsg::error("bad_request", "only a closed temporary group has an archive"))?;
        fed::send(&store, &link, Event::Release { to_peer }).await;
        fed::push_link(&self.app, &store, &link).await;
        Ok(())
    }

    async fn archive_lock(&self, link_id: &str) -> Reply {
        let store = self.store()?;
        let link = store.link(link_id).await.map_err(store_error)?.ok_or_else(|| ServerMsg::error("not_found", "no such group"))?;
        rooms::my_side(&store, &link, &self.device).await.ok_or_else(|| ServerMsg::error("not_found", "no such group"))?;
        let set = doc! { "shareA.toPeer": Bson::Null, "shareB.toPeer": Bson::Null };
        let link = store
            .update_link(link_id, doc! { "state": "archived" }, set)
            .await
            .map_err(store_error)?
            .ok_or_else(|| ServerMsg::error("bad_request", "only a closed temporary group has an archive"))?;
        fed::send(&store, &link, Event::Lock).await;
        fed::push_link(&self.app, &store, &link).await;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{Signer, SigningKey};

    #[test]
    fn hello_signature() {
        let key = SigningKey::from_bytes(&[7u8; 32]);
        let device = crate::hex(key.verifying_key().as_bytes());
        let dh = "11".repeat(32);
        let nonce = "ab".repeat(16);
        let sig = crate::hex(&key.sign(p::hello_payload(&nonce, &device, &dh).as_bytes()).to_bytes());
        assert!(verify(&device, &dh, &nonce, &sig));
        assert!(!verify(&device, &dh, &"cd".repeat(16), &sig), "another challenge");
        assert!(!verify(&device, &"22".repeat(32), &nonce, &sig), "another DH key");
        assert!(!verify(&"00".repeat(32), &dh, &nonce, &sig));
        assert!(!verify(&device, &dh, &nonce, "zz"));
    }
}
