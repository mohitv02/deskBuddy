//! End-to-end encryption for chat. The server only ever sees ciphertext.
//!
//! - Device identity: an Ed25519 key (signs the server's login challenge;
//!   its public key is the device id) and an X25519 key (for direct chats).
//! - Direct chat key: HKDF(X25519(my device, their device)).
//! - Team chat key: HKDF(team key). The team key travels only inside invites.
//! - Team-to-team key K_AB: HKDF(X25519(team A, team B), link id), from each
//!   team's own X25519 key (also inside the invite). A group chat between
//!   the teams uses HKDF(K_AB).
//! - Temporary group: HKDF(K_AB ‖ share A ‖ share B). Each team keeps its own
//!   half encrypted with its team key; the other team's copy is withdrawn
//!   when the group closes and offered again only on "release", so reading
//!   the archive needs both teams.
//!
//! Messages: XChaCha20-Poly1305, random 24-byte nonce, the conversation id,
//! sender and message id as associated data (a body can't be replayed into
//! another chat). Wire form: `e1.<key version>.<base64url(nonce ‖ ciphertext)>`.

use base64::engine::general_purpose::URL_SAFE_NO_PAD as B64;
use base64::Engine;
use chacha20poly1305::aead::{Aead, KeyInit, Payload};
use chacha20poly1305::{XChaCha20Poly1305, XNonce};
use ed25519_dalek::{Signer, SigningKey};
use hkdf::Hkdf;
use sha2::Sha256;
use x25519_dalek::{PublicKey, StaticSecret};
use zeroize::Zeroizing;

use crate::crypto::{hex, random_bytes, unhex, CryptoError, Key};

pub const HELLO_CONTEXT: &str = "deskbuddy-hello-v2";

pub fn derive(ikm: &[u8], info: &str) -> Key {
    let mut out = Zeroizing::new([0u8; 32]);
    Hkdf::<Sha256>::new(None, ikm).expand(info.as_bytes(), out.as_mut()).expect("32 bytes is a valid HKDF length");
    out
}

fn key32(hex_str: &str) -> Option<[u8; 32]> {
    unhex(hex_str)?.try_into().ok()
}

pub fn dh_public(secret: &[u8; 32]) -> String {
    hex(PublicKey::from(&StaticSecret::from(*secret)).as_bytes())
}

/// X25519 with a hex public key; None if it is malformed or degenerate.
pub fn dh(secret: &[u8; 32], their_pub: &str) -> Option<Key> {
    let shared = StaticSecret::from(*secret).diffie_hellman(&PublicKey::from(key32(their_pub)?));
    shared.was_contributory().then(|| Zeroizing::new(*shared.as_bytes()))
}

pub struct Identity {
    sign: SigningKey,
    dh: Zeroizing<[u8; 32]>,
}

impl Identity {
    pub fn generate() -> Result<Self, CryptoError> {
        Ok(Self::from_secrets(&random_bytes::<32>()?, &random_bytes::<32>()?))
    }

    pub fn from_secrets(sign: &[u8; 32], dh: &[u8; 32]) -> Self {
        Self { sign: SigningKey::from_bytes(sign), dh: Zeroizing::new(*dh) }
    }

    pub fn sign_secret(&self) -> Zeroizing<[u8; 32]> {
        Zeroizing::new(self.sign.to_bytes())
    }

    pub fn dh_secret(&self) -> &[u8; 32] {
        &self.dh
    }

    /// The device id: hex Ed25519 public key.
    pub fn device(&self) -> String {
        hex(self.sign.verifying_key().as_bytes())
    }

    pub fn dh_pub(&self) -> String {
        dh_public(&self.dh)
    }

    /// Signature for the server's login challenge.
    pub fn sign_hello(&self, nonce: &str) -> String {
        let payload = format!("{HELLO_CONTEXT}\n{nonce}\n{}\n{}", self.device(), self.dh_pub());
        hex(&self.sign.sign(payload.as_bytes()).to_bytes())
    }

    /// Key for the direct chat `conversation` with a device whose X25519 key is `their_pub`.
    pub fn dm_key(&self, their_pub: &str, conversation: &str) -> Option<Key> {
        let shared = dh(&self.dh, their_pub)?;
        Some(derive(shared.as_ref(), &format!("deskbuddy dm v1|{conversation}")))
    }
}

/// `dm:<a>|<b>` with the two device ids sorted.
pub fn dm_id(a: &str, b: &str) -> String {
    let (lo, hi) = if a <= b { (a, b) } else { (b, a) };
    format!("dm:{lo}|{hi}")
}

pub fn team_message_key(team_key: &[u8; 32]) -> Key {
    derive(team_key, "deskbuddy team msg v1")
}

/// What the server checks (by hash) before letting a device join a team.
pub fn team_proof(team_key: &[u8; 32]) -> String {
    hex(derive(team_key, "deskbuddy team proof v1").as_ref())
}

fn share_own_key(team_key: &[u8; 32]) -> Key {
    derive(team_key, "deskbuddy share own v1")
}

/// K_AB for one link, from our team's X25519 secret and theirs.
pub fn pair_key(our_team_dh: &[u8; 32], their_team_pub: &str, link: &str) -> Option<Key> {
    let shared = dh(our_team_dh, their_team_pub)?;
    Some(derive(shared.as_ref(), &format!("deskbuddy link v1|{link}")))
}

pub fn group_key(pair: &[u8; 32]) -> Key {
    derive(pair, "deskbuddy group v1")
}

pub fn temp_key(pair: &[u8; 32], share_a: &[u8; 32], share_b: &[u8; 32]) -> Key {
    let mut ikm = Zeroizing::new([0u8; 96]);
    ikm[..32].copy_from_slice(pair);
    ikm[32..64].copy_from_slice(share_a);
    ikm[64..].copy_from_slice(share_b);
    derive(ikm.as_ref(), "deskbuddy temp v1")
}

fn share_transfer_key(pair: &[u8; 32]) -> Key {
    derive(pair, "deskbuddy share transfer v1")
}

/// A new archive-key half, sealed for us (`own`) and for the other team (`to_peer`).
pub fn new_share(team_key: &[u8; 32], pair: &[u8; 32], link: &str) -> Result<(String, String), CryptoError> {
    let share = Zeroizing::new(random_bytes::<32>()?);
    Ok((seal_raw(&share_own_key(team_key), share.as_ref(), link)?, seal_raw(&share_transfer_key(pair), share.as_ref(), link)?))
}

/// Our own half, from the copy sealed with our team key.
pub fn open_own_share(team_key: &[u8; 32], sealed: &str, link: &str) -> Option<Key> {
    open_key(&share_own_key(team_key), sealed, link)
}

/// The other team's half, while they offer it.
pub fn open_peer_share(pair: &[u8; 32], sealed: &str, link: &str) -> Option<Key> {
    open_key(&share_transfer_key(pair), sealed, link)
}

/// Offer our half to the other team again (archive release).
pub fn reseal_for_peer(pair: &[u8; 32], share: &[u8; 32], link: &str) -> Result<String, CryptoError> {
    seal_raw(&share_transfer_key(pair), share, link)
}

fn open_key(key: &[u8; 32], sealed: &str, aad: &str) -> Option<Key> {
    let raw = Zeroizing::new(open_raw(key, sealed, aad)?);
    let arr: [u8; 32] = raw.as_slice().try_into().ok()?;
    Some(Zeroizing::new(arr))
}

/// Ten digits in two groups, the same on both teams' screens. Compare them
/// on a call or in person: a mismatch means someone swapped the keys.
pub fn safety_number(pair: &[u8; 32]) -> String {
    let k = derive(pair, "deskbuddy safety number v1");
    let n = u64::from_be_bytes(k[..8].try_into().expect("8 bytes")) % 10_000_000_000;
    let s = format!("{n:010}");
    format!("{} {}", &s[..5], &s[5..])
}

fn cipher(key: &[u8; 32]) -> XChaCha20Poly1305 {
    XChaCha20Poly1305::new(key.into())
}

fn seal_raw(key: &[u8; 32], plain: &[u8], aad: &str) -> Result<String, CryptoError> {
    let nonce = random_bytes::<24>()?;
    let ct = cipher(key)
        .encrypt(XNonce::from_slice(&nonce), Payload { msg: plain, aad: aad.as_bytes() })
        .map_err(|_| CryptoError::Random("encryption failed".into()))?;
    let mut out = Vec::with_capacity(24 + ct.len());
    out.extend_from_slice(&nonce);
    out.extend_from_slice(&ct);
    Ok(B64.encode(out))
}

fn open_raw(key: &[u8; 32], sealed: &str, aad: &str) -> Option<Vec<u8>> {
    let raw = B64.decode(sealed).ok()?;
    if raw.len() < 24 + 16 {
        return None;
    }
    let (nonce, ct) = raw.split_at(24);
    cipher(key).decrypt(XNonce::from_slice(nonce), Payload { msg: ct, aad: aad.as_bytes() }).ok()
}

/// Associated data binding a message to where it belongs.
pub fn message_aad(conversation: &str, from: &str, client_msg_id: &str) -> String {
    format!("{conversation}|{from}|{client_msg_id}")
}

pub fn seal_message(key: &[u8; 32], version: u32, plain: &str, aad: &str) -> Result<String, CryptoError> {
    Ok(format!("e1.{version}.{}", seal_raw(key, plain.as_bytes(), aad)?))
}

/// The key version a body was sealed with.
pub fn message_version(body: &str) -> Option<u32> {
    let rest = body.strip_prefix("e1.")?;
    rest.split_once('.')?.0.parse().ok()
}

pub fn open_message(key: &[u8; 32], body: &str, aad: &str) -> Option<String> {
    let rest = body.strip_prefix("e1.")?;
    let (_, sealed) = rest.split_once('.')?;
    String::from_utf8(open_raw(key, sealed, aad)?).ok()
}

/// base64url JSON, used for invite and address codes.
pub fn encode_code<T: serde::Serialize>(prefix: &str, value: &T) -> String {
    format!("{prefix}{}", B64.encode(serde_json::to_vec(value).expect("serializes")))
}

pub fn decode_code<T: serde::de::DeserializeOwned>(prefix: &str, code: &str) -> Option<T> {
    let body = code.trim().strip_prefix(prefix)?;
    serde_json::from_slice(&B64.decode(body.trim()).ok()?).ok()
}

pub fn parse_key(hex_str: &str) -> Option<Key> {
    key32(hex_str).map(Zeroizing::new)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identity_and_dm_keys_agree() {
        let a = Identity::generate().unwrap();
        let b = Identity::generate().unwrap();
        assert_eq!(a.device().len(), 64);
        let conv = dm_id(&a.device(), &b.device());
        assert_eq!(conv, dm_id(&b.device(), &a.device()));
        let ka = a.dm_key(&b.dh_pub(), &conv).unwrap();
        let kb = b.dm_key(&a.dh_pub(), &conv).unwrap();
        assert_eq!(*ka, *kb, "both ends derive the same key");
        let restored = Identity::from_secrets(&a.sign_secret(), a.dh_secret());
        assert_eq!(restored.device(), a.device());
        assert!(a.dm_key(&"00".repeat(32), &conv).is_none(), "low-order point refused");
        assert!(a.dm_key("zz", &conv).is_none());
    }

    #[test]
    fn hello_signature_matches_server_format() {
        use ed25519_dalek::{Signature, Verifier, VerifyingKey};
        let id = Identity::generate().unwrap();
        let sig = id.sign_hello("abcd");
        let key = VerifyingKey::from_bytes(&key32(&id.device()).unwrap()).unwrap();
        let payload = format!("{HELLO_CONTEXT}\nabcd\n{}\n{}", id.device(), id.dh_pub());
        let sig: [u8; 64] = unhex(&sig).unwrap().try_into().unwrap();
        assert!(key.verify(payload.as_bytes(), &Signature::from_bytes(&sig)).is_ok());
    }

    #[test]
    fn messages_roundtrip_and_bind_context() {
        let key = derive(b"k", "test");
        let aad = message_aad("team:x", "dev", "c1");
        let body = seal_message(&key, 3, "hello ✓", &aad).unwrap();
        assert!(body.starts_with("e1.3."));
        assert_eq!(message_version(&body), Some(3));
        assert_eq!(open_message(&key, &body, &aad).as_deref(), Some("hello ✓"));
        assert!(open_message(&key, &body, &message_aad("team:y", "dev", "c1")).is_none(), "another chat");
        assert!(open_message(&derive(b"other", "test"), &body, &aad).is_none(), "another key");
        let mut tampered = body.clone();
        tampered.pop();
        tampered.push(if body.ends_with('A') { 'B' } else { 'A' });
        assert!(open_message(&key, &tampered, &aad).is_none());
        assert_ne!(seal_message(&key, 3, "hello ✓", &aad).unwrap(), body, "random nonce");
    }

    #[test]
    fn team_pair_and_temp_keys() {
        let (ta, tb) = (random_bytes::<32>().unwrap(), random_bytes::<32>().unwrap());
        let link = "0123456789abcdef0123456789abcdef";
        let ab = pair_key(&ta, &dh_public(&tb), link).unwrap();
        let ba = pair_key(&tb, &dh_public(&ta), link).unwrap();
        assert_eq!(*ab, *ba);
        assert_eq!(safety_number(&ab), safety_number(&ba));
        assert_eq!(safety_number(&ab).len(), 11);
        assert_ne!(*pair_key(&ta, &dh_public(&tb), "other").unwrap(), *ab, "per link");

        let (key_a, key_b) = (random_bytes::<32>().unwrap(), random_bytes::<32>().unwrap());
        let (own_a, peer_a) = new_share(&key_a, &ab, link).unwrap();
        let (own_b, peer_b) = new_share(&key_b, &ba, link).unwrap();
        // Team A while the group is open: its own half, and B's offered half.
        let a_view = temp_key(&ab, &open_own_share(&key_a, &own_a, link).unwrap(), &open_peer_share(&ab, &peer_b, link).unwrap());
        let b_view = temp_key(&ba, &open_peer_share(&ba, &peer_a, link).unwrap(), &open_own_share(&key_b, &own_b, link).unwrap());
        assert_eq!(*a_view, *b_view);
        assert!(open_own_share(&key_b, &own_a, link).is_none(), "B can't open A's own copy");
        let again = reseal_for_peer(&ab, &open_own_share(&key_a, &own_a, link).unwrap(), link).unwrap();
        assert_eq!(*open_peer_share(&ba, &again, link).unwrap(), *open_peer_share(&ba, &peer_a, link).unwrap());
    }

    #[test]
    fn codes_roundtrip() {
        let code = encode_code("DBA1-", &serde_json::json!({ "id": "x" }));
        let v: serde_json::Value = decode_code("DBA1-", &format!("  {code} ")).unwrap();
        assert_eq!(v["id"], "x");
        assert!(decode_code::<serde_json::Value>("DBT1-", &code).is_none());
    }
}
