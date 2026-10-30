//! Wire protocol: JSON text frames tagged by `type`. Users are keyed by the
//! IPv4/IPv6 address of their machine; a direct conversation is keyed by its
//! two members' addresses.

use std::net::IpAddr;

use serde::{Deserialize, Serialize};

pub const MAX_BODY_BYTES: usize = 20_000;
pub const MAX_NAME_CHARS: usize = 40;
pub const MAX_CLIENT_ID_LEN: usize = 64;
pub const MAX_SYNC_PAGE: u32 = 200;

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "camelCase", rename_all_fields = "camelCase")]
pub enum ClientMsg {
    /// First frame. `ip` is optional: without it the server uses the address
    /// it sees the connection come from.
    Hello { ip: Option<String>, name: Option<String> },
    Send { to: String, client_msg_id: String, body: String },
    Conversations,
    Sync { conversation_id: String, after_seq: i64, limit: Option<u32> },
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ChatMessage {
    pub id: String,
    pub conversation_id: String,
    /// 1, 2, 3… within the conversation. Gaps are possible (a retried send).
    pub seq: i64,
    pub from: String,
    pub client_msg_id: String,
    pub body: String,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UserInfo {
    pub ip: String,
    pub name: String,
    pub online: bool,
    pub last_seen: i64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationInfo {
    pub id: String,
    /// The other member's address.
    pub with: String,
    pub last_seq: i64,
    pub updated_at: i64,
}

#[derive(Debug, Serialize)]
#[serde(tag = "type", rename_all = "camelCase", rename_all_fields = "camelCase")]
pub enum ServerMsg {
    Welcome { you: UserInfo, users: Vec<UserInfo> },
    Presence { ip: String, name: String, online: bool },
    /// Reply to `send`: the stored message (also for a retried `clientMsgId`).
    Ack { client_msg_id: String, message: ChatMessage },
    /// A new message for you, or one you sent from another connection.
    Message { message: ChatMessage },
    Conversations { items: Vec<ConversationInfo> },
    Messages { conversation_id: String, items: Vec<ChatMessage>, more: bool },
    /// `clientMsgId` is set when the error is the answer to that `send`.
    Error {
        code: &'static str,
        message: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        client_msg_id: Option<String>,
    },
}

impl ServerMsg {
    pub fn error(code: &'static str, message: impl Into<String>) -> Self {
        ServerMsg::Error { code, message: message.into(), client_msg_id: None }
    }

    /// Tag an error with the `send` it answers.
    pub fn for_send(self, id: &str) -> Self {
        match self {
            ServerMsg::Error { code, message, .. } => ServerMsg::Error { code, message, client_msg_id: Some(id.to_string()) },
            other => other,
        }
    }

    pub fn to_json(&self) -> String {
        serde_json::to_string(self).expect("server messages always serialize")
    }
}

/// Canonical text form of an address (`::ffff:1.2.3.4` becomes `1.2.3.4`).
pub fn canonical_ip(ip: IpAddr) -> String {
    ip.to_canonical().to_string()
}

pub fn parse_ip(s: &str) -> Option<String> {
    s.trim().parse::<IpAddr>().ok().map(canonical_ip)
}

/// Same id whichever side starts the conversation.
pub fn dm_id(a: &str, b: &str) -> (String, [String; 2]) {
    let (lo, hi) = if a <= b { (a, b) } else { (b, a) };
    (format!("dm:{lo}|{hi}"), [lo.to_string(), hi.to_string()])
}

pub fn clean_name(name: Option<&str>, ip: &str) -> String {
    let name: String = name.unwrap_or("").trim().chars().filter(|c| !c.is_control()).take(MAX_NAME_CHARS).collect();
    if name.is_empty() { ip.to_string() } else { name }
}

pub fn check_body(body: &str) -> Result<(), &'static str> {
    if body.trim().is_empty() {
        Err("message is empty")
    } else if body.len() > MAX_BODY_BYTES {
        Err("message is too long")
    } else {
        Ok(())
    }
}

pub fn check_client_msg_id(id: &str) -> bool {
    (1..=MAX_CLIENT_ID_LEN).contains(&id.len()) && id.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_client_frames() {
        let m: ClientMsg = serde_json::from_str(r#"{"type":"send","to":"10.0.0.2","clientMsgId":"a1","body":"hi"}"#).unwrap();
        assert!(matches!(m, ClientMsg::Send { ref to, ref client_msg_id, .. } if to == "10.0.0.2" && client_msg_id == "a1"));
        let m: ClientMsg = serde_json::from_str(r#"{"type":"hello"}"#).unwrap();
        assert!(matches!(m, ClientMsg::Hello { ip: None, name: None }));
        let m: ClientMsg = serde_json::from_str(r#"{"type":"sync","conversationId":"dm:a|b","afterSeq":3}"#).unwrap();
        assert!(matches!(m, ClientMsg::Sync { after_seq: 3, limit: None, .. }));
        assert!(serde_json::from_str::<ClientMsg>(r#"{"type":"nope"}"#).is_err());
    }

    #[test]
    fn server_frames_are_camel_case() {
        let json = ServerMsg::error("bad", "x").to_json();
        assert_eq!(json, r#"{"type":"error","code":"bad","message":"x"}"#);
        let json = ServerMsg::error("bad", "x").for_send("c1").to_json();
        assert_eq!(json, r#"{"type":"error","code":"bad","message":"x","clientMsgId":"c1"}"#);
        let json = ServerMsg::Presence { ip: "1.2.3.4".into(), name: "n".into(), online: true }.to_json();
        assert_eq!(json, r#"{"type":"presence","ip":"1.2.3.4","name":"n","online":true}"#);
    }

    #[test]
    fn addresses_and_ids() {
        assert_eq!(parse_ip(" 192.168.1.5 ").as_deref(), Some("192.168.1.5"));
        assert_eq!(parse_ip("::ffff:10.0.0.1").as_deref(), Some("10.0.0.1"));
        assert_eq!(parse_ip("not an ip"), None);
        assert_eq!(dm_id("10.0.0.9", "10.0.0.1"), dm_id("10.0.0.1", "10.0.0.9"));
        assert_eq!(dm_id("b", "a").0, "dm:a|b");
    }

    #[test]
    fn validation() {
        assert_eq!(clean_name(Some("  Mohit\u{7} "), "1.1.1.1"), "Mohit");
        assert_eq!(clean_name(None, "1.1.1.1"), "1.1.1.1");
        assert_eq!(clean_name(Some(&"x".repeat(100)), "ip").chars().count(), MAX_NAME_CHARS);
        assert!(check_body(" \n").is_err());
        assert!(check_body(&"x".repeat(MAX_BODY_BYTES + 1)).is_err());
        assert!(check_body("ok").is_ok());
        assert!(check_client_msg_id("0b6f-11_ab"));
        assert!(!check_client_msg_id(""));
        assert!(!check_client_msg_id("has space"));
        assert!(!check_client_msg_id(&"a".repeat(MAX_CLIENT_ID_LEN + 1)));
    }
}
