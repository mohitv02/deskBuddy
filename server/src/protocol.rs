//! Wire protocol v2: JSON text frames tagged by `type`.
//!
//! Identity is a device key: `device` is the hex Ed25519 public key of one
//! app install, proven by signing the server's `challenge`. Message bodies are
//! end-to-end encrypted by the apps; the server stores and relays ciphertext.
//!
//! Conversation ids:
//!   dm:<device>|<device>   two devices, sorted
//!   team:<teamId>          a team's internal chat
//!   link:<linkId>          a group chat between two teams

use serde::{Deserialize, Serialize};

/// Ciphertext is base64 of the plaintext plus a small header, so this is
/// larger than the app's 20 KB plaintext limit.
pub const MAX_BODY_BYTES: usize = 32_000;
pub const MAX_NAME_CHARS: usize = 40;
pub const MAX_CLIENT_ID_LEN: usize = 64;
pub const MAX_SYNC_PAGE: u32 = 200;
/// Encrypted key shares and similar small blobs.
pub const MAX_BLOB_BYTES: usize = 512;
pub const MAX_SERVERS: usize = 8;
pub const MAX_TEMP_HOURS: u32 = 72;
pub const MAX_RETENTION_DAYS: u32 = 3650;

pub const HELLO_CONTEXT: &str = "deskbuddy-hello-v2";

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "camelCase", rename_all_fields = "camelCase")]
pub enum ClientMsg {
    /// Answer to `challenge`: `sig` signs [`hello_payload`] with the device key.
    Hello { device: String, dh_pub: String, name: Option<String>, sig: String },
    Send { conversation_id: String, client_msg_id: String, body: String },
    Conversations,
    Sync { conversation_id: String, after_seq: i64, limit: Option<u32> },
    /// Join (or create) a team. `proof` is derived from the team key, so only
    /// someone holding the key can join; the server keeps only its hash.
    TeamJoin { team_id: String, name: String, dh_pub: String, proof: String },
    TeamLeave { team_id: String },
    /// New team key: `new_proof` replaces the old one and every other member
    /// is dropped until they join again with the new invite.
    TeamRotate { team_id: String, proof: String, new_proof: String },
    LinkRequest {
        link_id: String,
        kind: LinkKind,
        hours: Option<u32>,
        retention_days: Option<u32>,
        from_team: String,
        to_team: TeamRef,
        fed_token: String,
        share: Option<Share>,
    },
    LinkRespond { link_id: String, accept: bool, share: Option<Share> },
    /// Offer our half of a temporary group's archive key to the other team.
    ArchiveRelease { link_id: String, to_peer: String },
    /// Withdraw both halves again.
    ArchiveLock { link_id: String },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum LinkKind {
    /// One shared room for both teams.
    Group,
    /// A shared room that closes after `hours`; its messages are archived.
    Temp,
    /// No room: members of both teams may message each other directly.
    Personal,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum LinkState {
    Pending,
    Active,
    Declined,
    /// A temporary group that has closed; messages kept until `purgeAt`.
    Archived,
    /// Archive deleted.
    Closed,
}

/// A team as another home sees it: enough to reach and encrypt for it.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct TeamRef {
    pub id: String,
    pub name: String,
    pub dh_pub: String,
    pub home: String,
    /// HTTP base URLs of that home's servers (federation endpoint is `/fed`).
    #[serde(default)]
    pub servers: Vec<String>,
    /// Known members (filled in for the other home's teams).
    #[serde(default)]
    pub members: Vec<Member>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Member {
    pub device: String,
    pub name: String,
    pub dh_pub: String,
}

/// One team's half of a temporary group's archive key, encrypted twice:
/// `own` with the team's own key (kept), `toPeer` for the other team
/// (withdrawn when the group closes, offered again on release).
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Share {
    #[serde(default)]
    pub own: Option<String>,
    #[serde(default)]
    pub to_peer: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ChatMessage {
    pub id: String,
    pub conversation_id: String,
    /// 1, 2, 3… within the conversation on this home. Gaps are possible.
    pub seq: i64,
    pub from: String,
    pub client_msg_id: String,
    pub body: String,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UserInfo {
    pub device: String,
    pub name: String,
    pub dh_pub: String,
    pub online: bool,
    pub last_seen: i64,
    /// False for members of another home's team.
    pub local: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TeamInfo {
    pub id: String,
    pub name: String,
    pub dh_pub: String,
    pub members: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LinkInfo {
    pub id: String,
    pub kind: LinkKind,
    pub state: LinkState,
    /// `a` asked, `b` was asked.
    pub a: TeamRef,
    pub b: TeamRef,
    pub hours: Option<u32>,
    pub expires_at: Option<i64>,
    pub retention_days: Option<u32>,
    pub purge_at: Option<i64>,
    pub share_a: Share,
    pub share_b: Share,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationInfo {
    pub id: String,
    pub last_seq: i64,
    pub updated_at: i64,
}

#[derive(Debug, Serialize)]
#[serde(tag = "type", rename_all = "camelCase", rename_all_fields = "camelCase")]
pub enum ServerMsg {
    Challenge { nonce: String },
    Welcome { you: UserInfo, home: String, servers: Vec<String>, users: Vec<UserInfo>, teams: Vec<TeamInfo>, links: Vec<LinkInfo> },
    Presence { device: String, name: String, online: bool },
    /// Someone new, or changed name / key.
    User { user: UserInfo },
    Team { team: TeamInfo },
    /// A team you were in that you no longer are (left, or rotated out).
    TeamGone { team_id: String },
    Link { link: LinkInfo },
    /// Reply to `send`: the stored message (also for a retried `clientMsgId`).
    Ack { client_msg_id: String, message: ChatMessage },
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

/// What the device signs in `hello`.
pub fn hello_payload(nonce: &str, device: &str, dh_pub: &str) -> String {
    format!("{HELLO_CONTEXT}\n{nonce}\n{device}\n{dh_pub}")
}

pub fn is_hex(s: &str, bytes: usize) -> bool {
    s.len() == bytes * 2 && s.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

/// A device id or X25519 public key: 32 bytes, lowercase hex.
pub fn is_key(s: &str) -> bool {
    is_hex(s, 32)
}

/// Team and link ids: 16 random bytes, lowercase hex.
pub fn is_id(s: &str) -> bool {
    is_hex(s, 16)
}

/// Same id whichever side starts the conversation.
#[cfg(test)]
pub fn dm_id(a: &str, b: &str) -> (String, [String; 2]) {
    let (lo, hi) = if a <= b { (a, b) } else { (b, a) };
    (format!("dm:{lo}|{hi}"), [lo.to_string(), hi.to_string()])
}

#[derive(Debug, PartialEq)]
pub enum ConvRef {
    Dm(String, String),
    Team(String),
    Link(String),
}

pub fn parse_conversation(id: &str) -> Option<ConvRef> {
    if let Some(rest) = id.strip_prefix("dm:") {
        let (a, b) = rest.split_once('|')?;
        return (is_key(a) && is_key(b) && a < b).then(|| ConvRef::Dm(a.into(), b.into()));
    }
    if let Some(t) = id.strip_prefix("team:") {
        return is_id(t).then(|| ConvRef::Team(t.into()));
    }
    let l = id.strip_prefix("link:")?;
    is_id(l).then(|| ConvRef::Link(l.into()))
}

pub fn clean_name(name: Option<&str>, fallback: &str) -> String {
    let name: String = name.unwrap_or("").trim().chars().filter(|c| !c.is_control()).take(MAX_NAME_CHARS).collect();
    if name.is_empty() { fallback.to_string() } else { name }
}

pub fn check_body(body: &str) -> Result<(), &'static str> {
    if body.is_empty() {
        Err("message is empty")
    } else if body.len() > MAX_BODY_BYTES {
        Err("message is too long")
    } else {
        Ok(())
    }
}

pub fn check_blob(s: &str) -> bool {
    !s.is_empty() && s.len() <= MAX_BLOB_BYTES && s.bytes().all(|b| b.is_ascii_graphic())
}

pub fn check_client_msg_id(id: &str) -> bool {
    (1..=MAX_CLIENT_ID_LEN).contains(&id.len()) && id.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}

/// `http://host:port` without a path; used for federation addresses.
pub fn check_server_url(s: &str) -> bool {
    let Some(rest) = s.strip_prefix("http://") else { return false };
    !rest.is_empty() && rest.len() <= 200 && !rest.contains('/') && rest.bytes().all(|b| b.is_ascii_graphic())
}

pub fn check_team_ref(t: &TeamRef) -> Result<(), &'static str> {
    if !is_id(&t.id) || !is_key(&t.dh_pub) || !is_id(&t.home) {
        return Err("bad team reference");
    }
    if t.name.trim().is_empty() || t.name.chars().count() > MAX_NAME_CHARS {
        return Err("bad team name");
    }
    if t.servers.len() > MAX_SERVERS || !t.servers.iter().all(|s| check_server_url(s)) {
        return Err("bad server list");
    }
    Ok(())
}

pub fn check_share(s: &Share) -> bool {
    s.own.as_deref().is_none_or(check_blob) && s.to_peer.as_deref().is_none_or(check_blob)
}

#[cfg(test)]
mod tests {
    use super::*;

    const A: &str = "0000000000000000000000000000000000000000000000000000000000000001";
    const B: &str = "00000000000000000000000000000000000000000000000000000000000000ff";
    const T: &str = "0123456789abcdef0123456789abcdef";

    #[test]
    fn parses_client_frames() {
        let m: ClientMsg =
            serde_json::from_str(&format!(r#"{{"type":"send","conversationId":"team:{T}","clientMsgId":"a1","body":"e1:x"}}"#)).unwrap();
        assert!(matches!(m, ClientMsg::Send { ref client_msg_id, .. } if client_msg_id == "a1"));
        let m: ClientMsg = serde_json::from_str(&format!(r#"{{"type":"hello","device":"{A}","dhPub":"{B}","sig":"00"}}"#)).unwrap();
        assert!(matches!(m, ClientMsg::Hello { name: None, .. }));
        let m: ClientMsg = serde_json::from_str(r#"{"type":"sync","conversationId":"dm:a|b","afterSeq":3}"#).unwrap();
        assert!(matches!(m, ClientMsg::Sync { after_seq: 3, limit: None, .. }));
        let req = format!(
            r#"{{"type":"linkRequest","linkId":"{T}","kind":"temp","hours":2,"fromTeam":"{T}","fedToken":"{T}",
                "toTeam":{{"id":"{T}","name":"Two","dhPub":"{B}","home":"{T}","servers":["http://10.0.0.2:8787"]}}}}"#
        );
        assert!(matches!(serde_json::from_str(&req), Ok(ClientMsg::LinkRequest { kind: LinkKind::Temp, hours: Some(2), .. })));
        assert!(serde_json::from_str::<ClientMsg>(r#"{"type":"nope"}"#).is_err());
    }

    #[test]
    fn server_frames_are_camel_case() {
        assert_eq!(ServerMsg::error("bad", "x").to_json(), r#"{"type":"error","code":"bad","message":"x"}"#);
        assert_eq!(
            ServerMsg::error("bad", "x").for_send("c1").to_json(),
            r#"{"type":"error","code":"bad","message":"x","clientMsgId":"c1"}"#
        );
        let json = ServerMsg::TeamGone { team_id: "t".into() }.to_json();
        assert_eq!(json, r#"{"type":"teamGone","teamId":"t"}"#);
    }

    #[test]
    fn ids() {
        assert!(is_key(A) && is_key(B) && !is_key(&B.to_uppercase()) && !is_key("00"));
        assert!(is_id(T) && !is_id(A));
        assert_eq!(dm_id(B, A), dm_id(A, B));
        assert_eq!(parse_conversation(&dm_id(B, A).0), Some(ConvRef::Dm(A.into(), B.into())));
        assert_eq!(parse_conversation(&format!("dm:{B}|{A}")), None, "must be sorted");
        assert_eq!(parse_conversation(&format!("team:{T}")), Some(ConvRef::Team(T.into())));
        assert_eq!(parse_conversation(&format!("link:{T}")), Some(ConvRef::Link(T.into())));
        assert_eq!(parse_conversation("team:xyz"), None);
        assert_eq!(parse_conversation("dm:10.0.0.1|10.0.0.2"), None, "v1 ids are gone");
    }

    #[test]
    fn validation() {
        assert_eq!(clean_name(Some("  Mohit\u{7} "), "x"), "Mohit");
        assert_eq!(clean_name(None, "x"), "x");
        assert!(check_body("").is_err());
        assert!(check_body(&"x".repeat(MAX_BODY_BYTES + 1)).is_err());
        assert!(check_client_msg_id("0b6f-11_ab") && !check_client_msg_id("has space"));
        assert!(check_server_url("http://10.0.0.2:8787"));
        assert!(!check_server_url("http://10.0.0.2:8787/fed") && !check_server_url("ftp://x"));
        let mut t = TeamRef { id: T.into(), name: "One".into(), dh_pub: A.into(), home: T.into(), servers: vec![], members: vec![] };
        assert!(check_team_ref(&t).is_ok());
        t.servers = vec!["nope".into()];
        assert!(check_team_ref(&t).is_err());
        assert!(check_share(&Share { own: Some("abc".into()), to_peer: None }));
        assert!(!check_share(&Share { own: Some("a b".into()), to_peer: None }));
    }
}
