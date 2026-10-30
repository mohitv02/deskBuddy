//! One WebSocket connection: handshake, then a loop of client requests.

use std::net::IpAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};

use axum::extract::ws::{Message, WebSocket};
use futures_util::{SinkExt, StreamExt};
use tokio::sync::mpsc;

use crate::hub::{Outbox, OUTBOX_CAPACITY};
use crate::protocol::{self as p, ChatMessage, ClientMsg, ServerMsg, UserInfo};
use crate::App;

const HELLO_TIMEOUT: Duration = Duration::from_secs(10);
/// At most this many sends per window, per connection.
const SEND_BURST: usize = 20;
const SEND_WINDOW: Duration = Duration::from_secs(10);
const USER_LIST_LIMIT: i64 = 500;
const CONVERSATION_LIMIT: i64 = 200;

struct Session {
    app: Arc<App>,
    ip: String,
    conn_id: u64,
    out: Outbox,
    recent_sends: Vec<Instant>,
}

pub async fn run(socket: WebSocket, peer: IpAddr, app: Arc<App>) {
    let (mut sink, mut stream) = socket.split();
    let peer = p::canonical_ip(peer);

    let hello = match tokio::time::timeout(HELLO_TIMEOUT, next_client_msg(&mut stream)).await {
        Ok(Some(Ok(ClientMsg::Hello { ip, name }))) => (ip, name),
        Ok(Some(Ok(_))) => return reject(&mut sink, "hello_required", "send hello first").await,
        Ok(Some(Err(e))) => return reject(&mut sink, "bad_request", e).await,
        _ => return,
    };
    let ip = match hello.0.as_deref().map(p::parse_ip) {
        None => peer.clone(),
        Some(None) => return reject(&mut sink, "bad_ip", "ip is not a valid address").await,
        Some(Some(claimed)) if app.strict_ip && claimed != peer => {
            let msg = format!("you connect from {peer}, not {claimed}; leave ip empty or use {peer}");
            return reject(&mut sink, "ip_mismatch", msg).await;
        }
        Some(Some(claimed)) => claimed,
    };
    let name = p::clean_name(hello.1.as_deref(), &ip);
    let me = match app.store.touch_user(&ip, &name).await {
        Ok(u) => u,
        Err(e) => {
            eprintln!("chat: store error on hello from {ip}: {e}");
            return reject(&mut sink, "unavailable", "storage is unavailable").await;
        }
    };

    let (out, mut outbox) = mpsc::channel::<String>(OUTBOX_CAPACITY);
    let (conn_id, came_online) = app.hub.register(&ip, out.clone());
    eprintln!("chat: {ip} ({name}) connected");
    if came_online {
        app.hub.broadcast(&ServerMsg::Presence { ip: ip.clone(), name: name.clone(), online: true }.to_json(), &ip);
    }
    let writer = tokio::spawn(async move {
        while let Some(frame) = outbox.recv().await {
            if sink.send(Message::Text(frame.into())).await.is_err() {
                break;
            }
        }
        let _ = sink.close().await;
    });

    let mut s = Session { app: app.clone(), ip: ip.clone(), conn_id, out, recent_sends: Vec::new() };
    let users = match app.store.users(USER_LIST_LIMIT).await {
        Ok(list) => list
            .into_iter()
            .map(|u| UserInfo { online: app.hub.is_online(&u.ip), ip: u.ip, name: u.name, last_seen: u.last_seen.timestamp_millis() })
            .collect(),
        Err(_) => Vec::new(),
    };
    let you = UserInfo { ip: me.ip, name: me.name, online: true, last_seen: me.last_seen.timestamp_millis() };
    s.reply(ServerMsg::Welcome { you, users }).await;

    while let Some(msg) = next_client_msg(&mut stream).await {
        match msg {
            Ok(m) => s.handle(m).await,
            Err(e) => s.reply(ServerMsg::error("bad_request", e)).await,
        }
    }

    drop(s);
    if app.hub.unregister(&ip, conn_id) {
        app.hub.broadcast(&ServerMsg::Presence { ip: ip.clone(), name, online: false }.to_json(), &ip);
        let _ = app.store.mark_seen(&ip).await;
    }
    writer.abort();
    eprintln!("chat: {ip} disconnected");
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

impl Session {
    async fn reply(&self, msg: ServerMsg) {
        let _ = self.out.send(msg.to_json()).await;
    }

    async fn handle(&mut self, msg: ClientMsg) {
        let result = match msg {
            ClientMsg::Hello { .. } => Err(ServerMsg::error("bad_request", "already said hello")),
            ClientMsg::Send { to, client_msg_id, body } => {
                self.send(&to, &client_msg_id, &body).await.map_err(|e| e.for_send(&client_msg_id))
            }
            ClientMsg::Conversations => self.conversations().await,
            ClientMsg::Sync { conversation_id, after_seq, limit } => self.sync(&conversation_id, after_seq, limit).await,
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

    async fn send(&mut self, to: &str, client_msg_id: &str, body: &str) -> Result<(), ServerMsg> {
        let to = p::parse_ip(to).ok_or_else(|| ServerMsg::error("bad_ip", "`to` is not a valid address"))?;
        if to == self.ip {
            return Err(ServerMsg::error("bad_request", "use local notes to message yourself"));
        }
        if !p::check_client_msg_id(client_msg_id) {
            return Err(ServerMsg::error("bad_request", "clientMsgId must be 1-64 letters, digits, - or _"));
        }
        p::check_body(body).map_err(|e| ServerMsg::error("bad_request", e))?;
        if self.rate_limited() {
            return Err(ServerMsg::error("rate_limited", "too many messages; wait a few seconds"));
        }
        let (conversation, members) = p::dm_id(&self.ip, &to);
        let (doc, is_new) = self.app.store.append(&conversation, &members, &self.ip, client_msg_id, body).await.map_err(store_error)?;
        let message = ChatMessage::from(doc);
        if is_new {
            let push = ServerMsg::Message { message: message.clone() }.to_json();
            self.app.hub.send_to(&to, &push, None);
            self.app.hub.send_to(&self.ip, &push, Some(self.conn_id));
        }
        self.reply(ServerMsg::Ack { client_msg_id: client_msg_id.to_string(), message }).await;
        Ok(())
    }

    async fn conversations(&self) -> Result<(), ServerMsg> {
        let list = self.app.store.conversations_for(&self.ip, CONVERSATION_LIMIT).await.map_err(store_error)?;
        let items = list.iter().map(|c| c.info_for(&self.ip)).collect();
        self.reply(ServerMsg::Conversations { items }).await;
        Ok(())
    }

    async fn sync(&self, conversation: &str, after_seq: i64, limit: Option<u32>) -> Result<(), ServerMsg> {
        let conv = self.app.store.conversation(conversation).await.map_err(store_error)?;
        if !conv.is_some_and(|c| c.members.contains(&self.ip)) {
            return Err(ServerMsg::error("not_found", "no such conversation"));
        }
        let limit = limit.unwrap_or(p::MAX_SYNC_PAGE).clamp(1, p::MAX_SYNC_PAGE);
        let docs = self.app.store.messages_after(conversation, after_seq, limit as i64).await.map_err(store_error)?;
        let more = docs.len() == limit as usize;
        let items = docs.into_iter().map(ChatMessage::from).collect();
        self.reply(ServerMsg::Messages { conversation_id: conversation.to_string(), items, more }).await;
        Ok(())
    }
}

fn store_error(e: mongodb::error::Error) -> ServerMsg {
    eprintln!("chat: store error: {e}");
    ServerMsg::error("unavailable", "storage error; try again")
}
