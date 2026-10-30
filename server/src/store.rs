//! MongoDB persistence. Three collections in one database:
//!   users          { _id: ip, name, firstSeen, lastSeen }
//!   conversations  { _id: "dm:<ip>|<ip>", members: [ip, ip], lastSeq, createdAt, updatedAt }
//!   messages       { _id, conversationId, seq, from, clientMsgId, body, createdAt }

use futures_util::TryStreamExt;
use mongodb::bson::{doc, oid::ObjectId, DateTime};
use mongodb::error::{ErrorKind, WriteFailure};
use mongodb::options::{IndexOptions, ReturnDocument};
use mongodb::{Client, Collection, IndexModel};
use serde::{Deserialize, Serialize};

use crate::protocol::{ChatMessage, ConversationInfo};

pub type Result<T> = mongodb::error::Result<T>;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UserDoc {
    #[serde(rename = "_id")]
    pub ip: String,
    pub name: String,
    pub first_seen: DateTime,
    pub last_seen: DateTime,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationDoc {
    #[serde(rename = "_id")]
    pub id: String,
    pub members: Vec<String>,
    pub last_seq: i64,
    pub created_at: DateTime,
    pub updated_at: DateTime,
}

impl ConversationDoc {
    pub fn info_for(&self, ip: &str) -> ConversationInfo {
        let with = self.members.iter().find(|m| *m != ip).cloned().unwrap_or_else(|| ip.to_string());
        ConversationInfo { id: self.id.clone(), with, last_seq: self.last_seq, updated_at: self.updated_at.timestamp_millis() }
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

pub struct Store {
    users: Collection<UserDoc>,
    conversations: Collection<ConversationDoc>,
    messages: Collection<MessageDoc>,
}

fn is_duplicate_key(e: &mongodb::error::Error) -> bool {
    matches!(&*e.kind, ErrorKind::Write(WriteFailure::WriteError(w)) if w.code == 11000)
}

impl Store {
    /// Connect, check the server answers, and create the indexes (a no-op when
    /// they already exist).
    pub async fn connect(uri: &str, db: &str) -> Result<Self> {
        let client = Client::with_uri_str(uri).await?;
        let db = client.database(db);
        db.run_command(doc! { "ping": 1 }).await?;
        let store = Store {
            users: db.collection("users"),
            conversations: db.collection("conversations"),
            messages: db.collection("messages"),
        };
        store.ensure_indexes().await?;
        Ok(store)
    }

    async fn ensure_indexes(&self) -> Result<()> {
        let unique = || IndexOptions::builder().unique(true).build();
        self.messages
            .create_index(IndexModel::builder().keys(doc! { "conversationId": 1, "seq": 1 }).options(unique()).build())
            .await?;
        // Makes a retried send (same sender + clientMsgId) idempotent.
        self.messages
            .create_index(
                IndexModel::builder().keys(doc! { "conversationId": 1, "from": 1, "clientMsgId": 1 }).options(unique()).build(),
            )
            .await?;
        self.conversations.create_index(IndexModel::builder().keys(doc! { "members": 1, "updatedAt": -1 }).build()).await?;
        Ok(())
    }

    pub async fn touch_user(&self, ip: &str, name: &str) -> Result<UserDoc> {
        let now = DateTime::now();
        let user = self
            .users
            .find_one_and_update(
                doc! { "_id": ip },
                doc! { "$set": { "name": name, "lastSeen": now }, "$setOnInsert": { "firstSeen": now } },
            )
            .upsert(true)
            .return_document(ReturnDocument::After)
            .await?;
        Ok(user.expect("upsert returns the document"))
    }

    pub async fn mark_seen(&self, ip: &str) -> Result<()> {
        self.users.update_one(doc! { "_id": ip }, doc! { "$set": { "lastSeen": DateTime::now() } }).await?;
        Ok(())
    }

    pub async fn users(&self, limit: i64) -> Result<Vec<UserDoc>> {
        self.users.find(doc! {}).sort(doc! { "lastSeen": -1 }).limit(limit).await?.try_collect().await
    }

    pub async fn conversation(&self, id: &str) -> Result<Option<ConversationDoc>> {
        self.conversations.find_one(doc! { "_id": id }).await
    }

    pub async fn conversations_for(&self, ip: &str, limit: i64) -> Result<Vec<ConversationDoc>> {
        self.conversations.find(doc! { "members": ip }).sort(doc! { "updatedAt": -1 }).limit(limit).await?.try_collect().await
    }

    async fn find_sent(&self, conversation: &str, from: &str, client_msg_id: &str) -> Result<Option<MessageDoc>> {
        self.messages.find_one(doc! { "conversationId": conversation, "from": from, "clientMsgId": client_msg_id }).await
    }

    /// Store a message with the conversation's next `seq`. Returns the stored
    /// message and whether it is new (false: this `clientMsgId` was already sent).
    pub async fn append(
        &self,
        conversation: &str,
        members: &[String; 2],
        from: &str,
        client_msg_id: &str,
        body: &str,
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
            created_at: now,
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
}
