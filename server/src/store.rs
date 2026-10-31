//! MongoDB persistence. One database is one *home*: a community's server
//! cluster. Collections:
//!   meta           { _id: "home", homeId }
//!   users          { _id: device, name, dhPub, local, via: [linkId], firstSeen, lastSeen }
//!   teams          { _id, name, dhPub, proofHash, members: [device], createdAt }
//!   links          { _id, kind, state, a, b, hours, expiresAt, retentionDays, purgeAt, shareA, shareB, fedToken, … }
//!   conversations  { _id, members: [device] (dm only), lastSeq, createdAt, updatedAt }
//!   messages       { _id, conversationId, seq, from, clientMsgId, body, createdAt }
//! and, for running several servers on one database:
//!   instances      { _id, url, until }          live servers (TTL)
//!   presence       { _id, device, instance, until }  who is connected where (TTL)
//!   events         { _id, origin, to: [device], frame, at }  pushes for other servers (TTL)
//!   outbox         { _id, urls, payload, attempts, nextAt, leaseUntil }  federation deliveries

use std::time::Duration;

use futures_util::TryStreamExt;
use mongodb::bson::{doc, oid::ObjectId, DateTime, Document};
use mongodb::error::{ErrorKind, WriteFailure};
use mongodb::options::{IndexOptions, ReturnDocument};
use mongodb::{Client, Collection, IndexModel};
use serde::{Deserialize, Serialize};

use crate::protocol::{ChatMessage, ConversationInfo, LinkInfo, LinkKind, LinkState, Member, Share, TeamInfo, TeamRef, UserInfo};

pub type Result<T> = mongodb::error::Result<T>;

/// Presence and instance records live this long without a heartbeat.
pub const LEASE: Duration = Duration::from_secs(60);
const EVENT_TTL: Duration = Duration::from_secs(600);

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UserDoc {
    #[serde(rename = "_id")]
    pub device: String,
    pub name: String,
    pub dh_pub: String,
    pub local: bool,
    #[serde(default)]
    pub via: Vec<String>,
    pub first_seen: DateTime,
    pub last_seen: DateTime,
}

impl UserDoc {
    pub fn info(&self, online: bool) -> UserInfo {
        UserInfo {
            device: self.device.clone(),
            name: self.name.clone(),
            dh_pub: self.dh_pub.clone(),
            online,
            last_seen: self.last_seen.timestamp_millis(),
            local: self.local,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TeamDoc {
    #[serde(rename = "_id")]
    pub id: String,
    pub name: String,
    pub dh_pub: String,
    pub proof_hash: String,
    pub members: Vec<String>,
    pub created_at: DateTime,
}

impl TeamDoc {
    pub fn info(&self) -> TeamInfo {
        TeamInfo { id: self.id.clone(), name: self.name.clone(), dh_pub: self.dh_pub.clone(), members: self.members.clone() }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LinkDoc {
    #[serde(rename = "_id")]
    pub id: String,
    pub kind: LinkKind,
    pub state: LinkState,
    pub a: TeamRef,
    pub b: TeamRef,
    pub hours: Option<u32>,
    pub expires_at: Option<DateTime>,
    pub retention_days: Option<u32>,
    pub purge_at: Option<DateTime>,
    pub share_a: Share,
    pub share_b: Share,
    /// Authorises server-to-server deliveries for this link.
    pub fed_token: String,
    pub created_at: DateTime,
    pub updated_at: DateTime,
}

impl LinkDoc {
    pub fn info(&self) -> LinkInfo {
        LinkInfo {
            id: self.id.clone(),
            kind: self.kind,
            state: self.state,
            a: self.a.clone(),
            b: self.b.clone(),
            hours: self.hours,
            expires_at: self.expires_at.map(|d| d.timestamp_millis()),
            retention_days: self.retention_days,
            purge_at: self.purge_at.map(|d| d.timestamp_millis()),
            share_a: self.share_a.clone(),
            share_b: self.share_b.clone(),
            created_at: self.created_at.timestamp_millis(),
        }
    }

    /// Which side (`a`/`b`) a team is on.
    pub fn side_of(&self, team: &str) -> Option<char> {
        if self.a.id == team {
            Some('a')
        } else if self.b.id == team {
            Some('b')
        } else {
            None
        }
    }

    pub fn team(&self, side: char) -> &TeamRef {
        if side == 'a' { &self.a } else { &self.b }
    }

    pub fn team_mut(&mut self, side: char) -> &mut TeamRef {
        if side == 'a' { &mut self.a } else { &mut self.b }
    }

    pub fn share_mut(&mut self, side: char) -> &mut Share {
        if side == 'a' { &mut self.share_a } else { &mut self.share_b }
    }

    /// Both halves of the archive key are on offer.
    pub fn archive_open(&self) -> bool {
        self.share_a.to_peer.is_some() && self.share_b.to_peer.is_some()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationDoc {
    #[serde(rename = "_id")]
    pub id: String,
    #[serde(default)]
    pub members: Vec<String>,
    pub last_seq: i64,
    pub created_at: DateTime,
    pub updated_at: DateTime,
}

impl ConversationDoc {
    pub fn info(&self) -> ConversationInfo {
        ConversationInfo { id: self.id.clone(), last_seq: self.last_seq, updated_at: self.updated_at.timestamp_millis() }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MessageDoc {
    #[serde(rename = "_id")]
    pub id: ObjectId,
    pub conversation_id: String,
    pub seq: i64,
    pub from: String,
    pub client_msg_id: String,
    pub body: String,
    pub created_at: DateTime,
}

impl From<MessageDoc> for ChatMessage {
    fn from(m: MessageDoc) -> Self {
        ChatMessage {
            id: m.id.to_hex(),
            conversation_id: m.conversation_id,
            seq: m.seq,
            from: m.from,
            client_msg_id: m.client_msg_id,
            body: m.body,
            created_at: m.created_at.timestamp_millis(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EventDoc {
    #[serde(rename = "_id")]
    pub id: ObjectId,
    pub origin: String,
    /// Devices to push to; empty = everyone connected.
    pub to: Vec<String>,
    pub frame: String,
    pub at: DateTime,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OutboxDoc {
    #[serde(rename = "_id")]
    pub id: ObjectId,
    pub urls: Vec<String>,
    pub payload: String,
    pub attempts: i32,
    pub next_at: DateTime,
    pub lease_until: DateTime,
}

pub enum JoinError {
    WrongKey,
    Db(mongodb::error::Error),
}

impl From<mongodb::error::Error> for JoinError {
    fn from(e: mongodb::error::Error) -> Self {
        JoinError::Db(e)
    }
}

pub struct Store {
    pub home: String,
    meta: Collection<Document>,
    users: Collection<UserDoc>,
    teams: Collection<TeamDoc>,
    links: Collection<LinkDoc>,
    conversations: Collection<ConversationDoc>,
    messages: Collection<MessageDoc>,
    instances: Collection<Document>,
    presence: Collection<Document>,
    events: Collection<EventDoc>,
    outbox: Collection<OutboxDoc>,
}

fn is_duplicate_key(e: &mongodb::error::Error) -> bool {
    matches!(&*e.kind, ErrorKind::Write(WriteFailure::WriteError(w)) if w.code == 11000)
}

fn after(d: Duration) -> DateTime {
    DateTime::from_millis(DateTime::now().timestamp_millis() + d.as_millis() as i64)
}

impl Store {
    /// Connect, check the server answers, create the indexes (a no-op when
    /// they already exist) and read or create this home's id.
    pub async fn connect(uri: &str, db: &str) -> Result<Self> {
        let client = Client::with_uri_str(uri).await?;
        let db = client.database(db);
        db.run_command(doc! { "ping": 1 }).await?;
        let mut store = Store {
            home: String::new(),
            meta: db.collection("meta"),
            users: db.collection("users"),
            teams: db.collection("teams"),
            links: db.collection("links"),
            conversations: db.collection("conversations"),
            messages: db.collection("messages"),
            instances: db.collection("instances"),
            presence: db.collection("presence"),
            events: db.collection("events"),
            outbox: db.collection("outbox"),
        };
        store.ensure_indexes().await?;
        store.home = store.home_id().await?;
        Ok(store)
    }

    async fn ensure_indexes(&self) -> Result<()> {
        let unique = || IndexOptions::builder().unique(true).build();
        let ttl = |secs: u64| IndexOptions::builder().expire_after(Duration::from_secs(secs)).build();
        self.messages
            .create_index(IndexModel::builder().keys(doc! { "conversationId": 1, "seq": 1 }).options(unique()).build())
            .await?;
        // Makes a retried send (same sender + clientMsgId) idempotent, also
        // when the same message arrives again from another home.
        self.messages
            .create_index(
                IndexModel::builder().keys(doc! { "conversationId": 1, "from": 1, "clientMsgId": 1 }).options(unique()).build(),
            )
            .await?;
        self.conversations.create_index(IndexModel::builder().keys(doc! { "members": 1, "updatedAt": -1 }).build()).await?;
        self.teams.create_index(IndexModel::builder().keys(doc! { "members": 1 }).build()).await?;
        self.links.create_index(IndexModel::builder().keys(doc! { "a.id": 1 }).build()).await?;
        self.links.create_index(IndexModel::builder().keys(doc! { "b.id": 1 }).build()).await?;
        self.users.create_index(IndexModel::builder().keys(doc! { "via": 1 }).build()).await?;
        self.instances.create_index(IndexModel::builder().keys(doc! { "until": 1 }).options(ttl(0)).build()).await?;
        self.presence.create_index(IndexModel::builder().keys(doc! { "until": 1 }).options(ttl(0)).build()).await?;
        self.presence.create_index(IndexModel::builder().keys(doc! { "device": 1 }).build()).await?;
        self.events.create_index(IndexModel::builder().keys(doc! { "at": 1 }).options(ttl(EVENT_TTL.as_secs())).build()).await?;
        self.outbox.create_index(IndexModel::builder().keys(doc! { "nextAt": 1 }).build()).await?;
        Ok(())
    }

    async fn home_id(&self) -> Result<String> {
        let fresh = crate::random_hex::<16>();
        let doc = self
            .meta
            .find_one_and_update(doc! { "_id": "home" }, doc! { "$setOnInsert": { "homeId": fresh } })
            .upsert(true)
            .return_document(ReturnDocument::After)
            .await?
            .expect("upsert returns the document");
        Ok(doc.get_str("homeId").unwrap_or_default().to_string())
    }

    // --- users -------------------------------------------------------------

    pub async fn touch_user(&self, device: &str, name: &str, dh_pub: &str) -> Result<UserDoc> {
        let now = DateTime::now();
        let user = self
            .users
            .find_one_and_update(
                doc! { "_id": device },
                doc! {
                    "$set": { "name": name, "dhPub": dh_pub, "lastSeen": now, "local": true },
                    "$setOnInsert": { "firstSeen": now, "via": [] },
                },
            )
            .upsert(true)
            .return_document(ReturnDocument::After)
            .await?;
        Ok(user.expect("upsert returns the document"))
    }

    /// A member of another home's team, known through `link`.
    pub async fn upsert_foreign_user(&self, m: &Member, link: &str) -> Result<UserDoc> {
        let now = DateTime::now();
        let user = self
            .users
            .find_one_and_update(
                doc! { "_id": &m.device, "local": { "$ne": true } },
                doc! {
                    "$set": { "name": &m.name, "dhPub": &m.dh_pub, "local": false },
                    "$addToSet": { "via": link },
                    "$setOnInsert": { "firstSeen": now, "lastSeen": now },
                },
            )
            .upsert(true)
            .return_document(ReturnDocument::After)
            .await;
        match user {
            Ok(u) => Ok(u.expect("upsert returns the document")),
            // A local user with the same device: keep the local record.
            Err(e) if is_duplicate_key(&e) => Ok(self.user(&m.device).await?.expect("exists")),
            Err(e) => Err(e),
        }
    }

    pub async fn mark_seen(&self, device: &str) -> Result<()> {
        self.users.update_one(doc! { "_id": device }, doc! { "$set": { "lastSeen": DateTime::now() } }).await?;
        Ok(())
    }

    pub async fn user(&self, device: &str) -> Result<Option<UserDoc>> {
        self.users.find_one(doc! { "_id": device }).await
    }

    /// Everyone on this home, plus other homes' members met through `links`.
    pub async fn users_visible(&self, links: &[String], limit: i64) -> Result<Vec<UserDoc>> {
        self.users
            .find(doc! { "$or": [{ "local": true }, { "via": { "$in": links } }] })
            .sort(doc! { "lastSeen": -1 })
            .limit(limit)
            .await?
            .try_collect()
            .await
    }

    // --- teams -------------------------------------------------------------

    pub async fn team(&self, id: &str) -> Result<Option<TeamDoc>> {
        self.teams.find_one(doc! { "_id": id }).await
    }

    pub async fn teams_of(&self, device: &str) -> Result<Vec<TeamDoc>> {
        self.teams.find(doc! { "members": device }).await?.try_collect().await
    }

    /// Join a team, creating it on first use. The proof hash must match.
    pub async fn team_join(&self, id: &str, name: &str, dh_pub: &str, proof_hash: &str, device: &str) -> std::result::Result<TeamDoc, JoinError> {
        let now = DateTime::now();
        let created = self
            .teams
            .find_one_and_update(
                doc! { "_id": id },
                doc! { "$setOnInsert": { "name": name, "dhPub": dh_pub, "proofHash": proof_hash, "members": [], "createdAt": now } },
            )
            .upsert(true)
            .return_document(ReturnDocument::After)
            .await?
            .expect("upsert returns the document");
        if !crate::ct_eq(created.proof_hash.as_bytes(), proof_hash.as_bytes()) {
            return Err(JoinError::WrongKey);
        }
        let team = self
            .teams
            .find_one_and_update(doc! { "_id": id }, doc! { "$addToSet": { "members": device } })
            .return_document(ReturnDocument::After)
            .await?
            .expect("exists");
        Ok(team)
    }

    pub async fn team_leave(&self, id: &str, device: &str) -> Result<Option<TeamDoc>> {
        self.teams
            .find_one_and_update(doc! { "_id": id }, doc! { "$pull": { "members": device } })
            .return_document(ReturnDocument::After)
            .await
    }

    /// Replace the proof and keep only `device`. Returns the dropped members.
    pub async fn team_rotate(&self, id: &str, old_hash: &str, new_hash: &str, device: &str) -> std::result::Result<(TeamDoc, Vec<String>), JoinError> {
        let before = self.team(id).await?.ok_or(JoinError::WrongKey)?;
        if !crate::ct_eq(before.proof_hash.as_bytes(), old_hash.as_bytes()) || !before.members.iter().any(|m| m == device) {
            return Err(JoinError::WrongKey);
        }
        let team = self
            .teams
            .find_one_and_update(
                doc! { "_id": id, "proofHash": old_hash },
                doc! { "$set": { "proofHash": new_hash, "members": [device] } },
            )
            .return_document(ReturnDocument::After)
            .await?
            .ok_or(JoinError::WrongKey)?;
        let dropped = before.members.into_iter().filter(|m| m != device).collect();
        Ok((team, dropped))
    }

    // --- links -------------------------------------------------------------

    pub async fn link(&self, id: &str) -> Result<Option<LinkDoc>> {
        self.links.find_one(doc! { "_id": id }).await
    }

    pub async fn links_of(&self, teams: &[String]) -> Result<Vec<LinkDoc>> {
        self.links
            .find(doc! { "$or": [{ "a.id": { "$in": teams } }, { "b.id": { "$in": teams } }], "state": { "$ne": "closed" } })
            .sort(doc! { "createdAt": -1 })
            .await?
            .try_collect()
            .await
    }

    /// Insert a new link; false if that id exists already.
    pub async fn insert_link(&self, link: &LinkDoc) -> Result<bool> {
        match self.links.insert_one(link).await {
            Ok(_) => Ok(true),
            Err(e) if is_duplicate_key(&e) => Ok(false),
            Err(e) => Err(e),
        }
    }

    pub async fn save_link(&self, link: &mut LinkDoc) -> Result<()> {
        link.updated_at = DateTime::now();
        self.links.replace_one(doc! { "_id": &link.id }, &*link).await?;
        Ok(())
    }

    /// Active temporary groups whose time is up.
    pub async fn expired_temp_links(&self) -> Result<Vec<LinkDoc>> {
        self.links
            .find(doc! { "kind": "temp", "state": "active", "expiresAt": { "$lte": DateTime::now() } })
            .await?
            .try_collect()
            .await
    }

    /// Archives past their retention.
    pub async fn purgeable_links(&self) -> Result<Vec<LinkDoc>> {
        self.links.find(doc! { "state": "archived", "purgeAt": { "$lte": DateTime::now() } }).await?.try_collect().await
    }

    // --- conversations and messages ------------------------------------------

    pub async fn conversations_for(&self, device: &str, ids: &[String], limit: i64) -> Result<Vec<ConversationDoc>> {
        self.conversations
            .find(doc! { "$or": [{ "members": device }, { "_id": { "$in": ids } }] })
            .sort(doc! { "updatedAt": -1 })
            .limit(limit)
            .await?
            .try_collect()
            .await
    }

    async fn find_sent(&self, conversation: &str, from: &str, client_msg_id: &str) -> Result<Option<MessageDoc>> {
        self.messages.find_one(doc! { "conversationId": conversation, "from": from, "clientMsgId": client_msg_id }).await
    }

    /// Store a message with the conversation's next `seq`. Returns the stored
    /// message and whether it is new (false: this `clientMsgId` was already
    /// stored). `members` is set for direct messages.
    pub async fn append(
        &self,
        conversation: &str,
        members: &[String],
        from: &str,
        client_msg_id: &str,
        body: &str,
        created_at: Option<DateTime>,
    ) -> Result<(MessageDoc, bool)> {
        if let Some(existing) = self.find_sent(conversation, from, client_msg_id).await? {
            return Ok((existing, false));
        }
        let now = DateTime::now();
        let conv = self
            .conversations
            .find_one_and_update(
                doc! { "_id": conversation },
                doc! {
                    "$inc": { "lastSeq": 1_i64 },
                    "$set": { "updatedAt": now },
                    "$setOnInsert": { "members": members.to_vec(), "createdAt": now },
                },
            )
            .upsert(true)
            .return_document(ReturnDocument::After)
            .await?
            .expect("upsert returns the document");
        let msg = MessageDoc {
            id: ObjectId::new(),
            conversation_id: conversation.to_string(),
            seq: conv.last_seq,
            from: from.to_string(),
            client_msg_id: client_msg_id.to_string(),
            body: body.to_string(),
            created_at: created_at.unwrap_or(now),
        };
        match self.messages.insert_one(&msg).await {
            Ok(_) => Ok((msg, true)),
            // A concurrent retry won the race; its seq is the real one.
            Err(e) if is_duplicate_key(&e) => match self.find_sent(conversation, from, client_msg_id).await? {
                Some(existing) => Ok((existing, false)),
                None => Err(e),
            },
            Err(e) => Err(e),
        }
    }

    /// Messages with `seq > after_seq`, oldest first.
    pub async fn messages_after(&self, conversation: &str, after_seq: i64, limit: i64) -> Result<Vec<MessageDoc>> {
        self.messages
            .find(doc! { "conversationId": conversation, "seq": { "$gt": after_seq } })
            .sort(doc! { "seq": 1 })
            .limit(limit)
            .await?
            .try_collect()
            .await
    }

    pub async fn delete_conversation(&self, conversation: &str) -> Result<()> {
        self.messages.delete_many(doc! { "conversationId": conversation }).await?;
        self.conversations.delete_one(doc! { "_id": conversation }).await?;
        Ok(())
    }

    // --- cluster -------------------------------------------------------------

    pub async fn heartbeat_instance(&self, instance: &str, urls: &[String]) -> Result<()> {
        self.instances
            .update_one(doc! { "_id": instance }, doc! { "$set": { "urls": urls.to_vec(), "until": after(LEASE) } })
            .upsert(true)
            .await?;
        Ok(())
    }

    pub async fn remove_instance(&self, instance: &str) -> Result<()> {
        self.instances.delete_one(doc! { "_id": instance }).await?;
        self.presence.delete_many(doc! { "instance": instance }).await?;
        Ok(())
    }

    /// Public URLs of every live server on this home.
    pub async fn live_servers(&self) -> Result<Vec<String>> {
        let docs: Vec<Document> =
            self.instances.find(doc! { "until": { "$gt": DateTime::now() } }).await?.try_collect().await?;
        let mut urls: Vec<String> = docs
            .iter()
            .filter_map(|d| d.get_array("urls").ok())
            .flatten()
            .filter_map(|u| u.as_str().map(str::to_string))
            .collect();
        urls.sort();
        urls.dedup();
        Ok(urls)
    }

    pub async fn set_presence(&self, instance: &str, devices: &[String]) -> Result<()> {
        for d in devices {
            self.presence
                .update_one(
                    doc! { "_id": format!("{instance}:{d}") },
                    doc! { "$set": { "device": d, "instance": instance, "until": after(LEASE) } },
                )
                .upsert(true)
                .await?;
        }
        Ok(())
    }

    pub async fn clear_presence(&self, instance: &str, device: &str) -> Result<()> {
        self.presence.delete_one(doc! { "_id": format!("{instance}:{device}") }).await?;
        Ok(())
    }

    /// Devices connected to any live server.
    pub async fn online_devices(&self) -> Result<Vec<String>> {
        let docs: Vec<Document> =
            self.presence.find(doc! { "until": { "$gt": DateTime::now() } }).await?.try_collect().await?;
        Ok(docs.iter().filter_map(|d| d.get_str("device").ok().map(str::to_string)).collect())
    }

    pub async fn publish(&self, origin: &str, to: &[String], frame: &str) -> Result<()> {
        let e = EventDoc { id: ObjectId::new(), origin: origin.to_string(), to: to.to_vec(), frame: frame.to_string(), at: DateTime::now() };
        self.events.insert_one(&e).await?;
        Ok(())
    }

    /// Events from other servers written at or after `since`, oldest first.
    pub async fn events_since(&self, origin: &str, since: DateTime) -> Result<Vec<EventDoc>> {
        self.events
            .find(doc! { "at": { "$gte": since }, "origin": { "$ne": origin } })
            .sort(doc! { "at": 1 })
            .limit(500)
            .await?
            .try_collect()
            .await
    }

    // --- federation outbox -----------------------------------------------------

    pub async fn enqueue(&self, urls: &[String], payload: &str) -> Result<()> {
        let now = DateTime::now();
        let d = OutboxDoc { id: ObjectId::new(), urls: urls.to_vec(), payload: payload.to_string(), attempts: 0, next_at: now, lease_until: now };
        self.outbox.insert_one(&d).await?;
        Ok(())
    }

    /// Take one due delivery for 30 s so other servers skip it.
    pub async fn claim_delivery(&self) -> Result<Option<OutboxDoc>> {
        let now = DateTime::now();
        self.outbox
            .find_one_and_update(
                doc! { "nextAt": { "$lte": now }, "leaseUntil": { "$lte": now } },
                doc! { "$set": { "leaseUntil": after(Duration::from_secs(30)) } },
            )
            .sort(doc! { "nextAt": 1 })
            .await
    }

    pub async fn delivered(&self, id: ObjectId) -> Result<()> {
        self.outbox.delete_one(doc! { "_id": id }).await?;
        Ok(())
    }

    /// Try again later, backing off up to 10 minutes; give up after a week.
    pub async fn retry_delivery(&self, d: &OutboxDoc) -> Result<()> {
        let attempts = d.attempts + 1;
        let wait = Duration::from_secs((5u64 << attempts.min(7) as u64).min(600));
        if attempts > 1500 {
            return self.delivered(d.id).await;
        }
        let next = after(wait);
        self.outbox
            .update_one(doc! { "_id": d.id }, doc! { "$set": { "attempts": attempts, "nextAt": next, "leaseUntil": next } })
            .await?;
        Ok(())
    }
}
