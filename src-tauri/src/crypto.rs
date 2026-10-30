//! Crypto module: Argon2id key derivation, randomness, SQLCipher raw-key
//! formatting, and the encrypted backup container. Page encryption itself is
//! done by SQLCipher (AES-256-CBC + HMAC-SHA512 per page); passing it a raw
//! 256-bit key skips SQLCipher's own PBKDF2 in favour of Argon2id.
//!
//! Nothing in here logs or formats key material except into Zeroizing buffers.

use std::io::{self, Read, Write};

use argon2::{Algorithm, Argon2, Params, Version};
use serde::{Deserialize, Serialize};
use zeroize::Zeroizing;

pub type Key = Zeroizing<[u8; 32]>;

pub const SALT_LEN: usize = 16;
pub const MIN_PASSWORD_LEN: usize = 8;

#[derive(Debug)]
pub enum CryptoError {
    Kdf(String),
    Random(String),
    BadBackup(String),
    Io(io::Error),
}

impl std::fmt::Display for CryptoError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CryptoError::Kdf(e) => write!(f, "key derivation failed: {e}"),
            CryptoError::Random(e) => write!(f, "system randomness unavailable: {e}"),
            CryptoError::BadBackup(e) => write!(f, "not a valid DeskBuddy backup: {e}"),
            CryptoError::Io(e) => write!(f, "file error: {e}"),
        }
    }
}

impl std::error::Error for CryptoError {}

impl From<io::Error> for CryptoError {
    fn from(e: io::Error) -> Self {
        CryptoError::Io(e)
    }
}

/// Argon2id cost parameters, stored next to each salt so they can be raised later.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KdfParams {
    pub memory_kib: u32,
    pub iterations: u32,
    pub parallelism: u32,
}

impl KdfParams {
    /// 64 MiB, 3 passes: ~0.3–0.8 s on a desktop CPU, well above OWASP's minimum.
    pub const DEFAULT: KdfParams = KdfParams { memory_kib: 64 * 1024, iterations: 3, parallelism: 1 };
    /// Cheap parameters so the test suite stays fast. Never used outside tests.
    #[cfg(test)]
    pub const FAST: KdfParams = KdfParams { memory_kib: 1024, iterations: 1, parallelism: 1 };

    /// Reject absurd values read from a (possibly tampered) file.
    fn sane(&self) -> bool {
        (8..=4 * 1024 * 1024).contains(&self.memory_kib) && (1..=64).contains(&self.iterations) && (1..=16).contains(&self.parallelism)
    }
}

pub fn derive_key(password: &str, salt: &[u8], params: KdfParams) -> Result<Key, CryptoError> {
    if !params.sane() {
        return Err(CryptoError::Kdf("unsupported parameters".into()));
    }
    let p = Params::new(params.memory_kib, params.iterations, params.parallelism, Some(32)).map_err(|e| CryptoError::Kdf(e.to_string()))?;
    let mut key: Key = Zeroizing::new([0u8; 32]);
    Argon2::new(Algorithm::Argon2id, Version::V0x13, p)
        .hash_password_into(password.as_bytes(), salt, key.as_mut())
        .map_err(|e| CryptoError::Kdf(e.to_string()))?;
    Ok(key)
}

pub fn random_bytes<const N: usize>() -> Result<[u8; N], CryptoError> {
    let mut buf = [0u8; N];
    getrandom::fill(&mut buf).map_err(|e| CryptoError::Random(e.to_string()))?;
    Ok(buf)
}

pub fn random_key() -> Result<Key, CryptoError> {
    Ok(Zeroizing::new(random_bytes::<32>()?))
}

pub fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push(DIGITS[(b >> 4) as usize] as char);
        s.push(DIGITS[(b & 15) as usize] as char);
    }
    s
}

pub fn unhex(s: &str) -> Option<Vec<u8>> {
    if s.len() % 2 != 0 {
        return None;
    }
    (0..s.len()).step_by(2).map(|i| u8::from_str_radix(s.get(i..i + 2)?, 16).ok()).collect()
}

pub fn key_from_hex(s: &str) -> Option<Key> {
    let bytes = Zeroizing::new(unhex(s.trim())?);
    let arr: [u8; 32] = bytes.as_slice().try_into().ok()?;
    Some(Zeroizing::new(arr))
}

/// SQLCipher raw-key literal: `x'<64 hex digits>'`.
pub fn sqlcipher_key(key: &Key) -> Zeroizing<String> {
    let mut hexed = Zeroizing::new(hex(key.as_ref()));
    let out = Zeroizing::new(format!("x'{}'", hexed.as_str()));
    zeroize::Zeroize::zeroize(&mut *hexed);
    out
}

/// Constant-time comparison for keys.
pub fn ct_eq(a: &[u8], b: &[u8]) -> bool {
    a.len() == b.len() && a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

pub fn check_new_password(password: &str) -> Result<(), String> {
    if password.chars().count() < MIN_PASSWORD_LEN {
        return Err(format!("use at least {MIN_PASSWORD_LEN} characters"));
    }
    if password.trim().is_empty() {
        return Err("password cannot be only spaces".into());
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Backup container
//
//   DESKBUDDY-BACKUP\n
//   {"version":1,"salt":"<hex>","kdf":{...},"files":[{"name":"vault.db","size":N},...]}\n
//   <file 1 bytes><file 2 bytes>...
//
// Each embedded file is a complete SQLCipher database encrypted with
// Argon2id(backup password, salt). SQLCipher's per-page HMAC authenticates
// the contents, so tampering or a wrong password is detected on open.
// ---------------------------------------------------------------------------

const MAGIC: &[u8] = b"DESKBUDDY-BACKUP\n";
const MAX_HEADER: usize = 64 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BackupFile {
    pub name: String,
    pub size: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BackupHeader {
    pub version: u32,
    pub salt: String,
    pub kdf: KdfParams,
    pub created_at: i64,
    pub files: Vec<BackupFile>,
}

impl BackupHeader {
    pub fn salt_bytes(&self) -> Result<Vec<u8>, CryptoError> {
        unhex(&self.salt).filter(|s| s.len() == SALT_LEN).ok_or_else(|| CryptoError::BadBackup("bad salt".into()))
    }
}

pub fn write_backup(out: &mut impl Write, header: &BackupHeader, files: &[&[u8]]) -> Result<(), CryptoError> {
    out.write_all(MAGIC)?;
    out.write_all(&serde_json::to_vec(header).map_err(|e| CryptoError::BadBackup(e.to_string()))?)?;
    out.write_all(b"\n")?;
    for f in files {
        out.write_all(f)?;
    }
    out.flush()?;
    Ok(())
}

pub fn read_backup(input: &mut impl Read) -> Result<(BackupHeader, Vec<Vec<u8>>), CryptoError> {
    let mut magic = [0u8; MAGIC.len()];
    input.read_exact(&mut magic).map_err(|_| CryptoError::BadBackup("file too short".into()))?;
    if magic != MAGIC {
        return Err(CryptoError::BadBackup("wrong file type".into()));
    }
    let mut header = Vec::new();
    let mut byte = [0u8; 1];
    loop {
        input.read_exact(&mut byte).map_err(|_| CryptoError::BadBackup("truncated header".into()))?;
        if byte[0] == b'\n' {
            break;
        }
        header.push(byte[0]);
        if header.len() > MAX_HEADER {
            return Err(CryptoError::BadBackup("header too large".into()));
        }
    }
    let header: BackupHeader = serde_json::from_slice(&header).map_err(|e| CryptoError::BadBackup(e.to_string()))?;
    if header.version != 1 {
        return Err(CryptoError::BadBackup(format!("unsupported version {}", header.version)));
    }
    header.salt_bytes()?;
    let mut files = Vec::with_capacity(header.files.len());
    for f in &header.files {
        if f.size > 2 * 1024 * 1024 * 1024 {
            return Err(CryptoError::BadBackup("embedded file too large".into()));
        }
        let mut buf = vec![0u8; f.size as usize];
        input.read_exact(&mut buf).map_err(|_| CryptoError::BadBackup("truncated data".into()))?;
        files.push(buf);
    }
    Ok((header, files))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn derivation_is_deterministic_and_salted() {
        let salt = [7u8; SALT_LEN];
        let a = derive_key("correct horse", &salt, KdfParams::FAST).unwrap();
        let b = derive_key("correct horse", &salt, KdfParams::FAST).unwrap();
        assert_eq!(*a, *b, "same password + salt -> same key");
        let other_salt = derive_key("correct horse", &[8u8; SALT_LEN], KdfParams::FAST).unwrap();
        assert_ne!(*a, *other_salt, "salt changes the key");
        let other_pw = derive_key("correct horsf", &salt, KdfParams::FAST).unwrap();
        assert_ne!(*a, *other_pw, "one character changes the key");
        let stronger = KdfParams { iterations: 2, ..KdfParams::FAST };
        assert_ne!(*a, *derive_key("correct horse", &salt, stronger).unwrap(), "params are part of the derivation");
    }

    #[test]
    fn argon2id_matches_reference_implementation() {
        // Expected value produced independently by the Argon2 reference C
        // implementation (argon2-cffi: hash_secret_raw, Type.ID, version 0x13,
        // t=1, m=1024 KiB, p=1, 32 bytes). Guards algorithm/version/parameter
        // wiring — a mismatch would make existing vaults impossible to open.
        let key = derive_key("password", b"somesaltsomesalt", KdfParams::FAST).unwrap();
        assert_eq!(hex(key.as_ref()), REFERENCE_KEY);
    }
    const REFERENCE_KEY: &str = include_str!("../tests/argon2id_fast_vector.txt");

    #[test]
    fn rejects_insane_params() {
        let bad = KdfParams { memory_kib: 1, ..KdfParams::FAST };
        assert!(derive_key("x", &[0; SALT_LEN], bad).is_err());
        let huge = KdfParams { memory_kib: u32::MAX, ..KdfParams::FAST };
        assert!(derive_key("x", &[0; SALT_LEN], huge).is_err());
    }

    #[test]
    fn randomness_and_hex() {
        let a = random_bytes::<16>().unwrap();
        let b = random_bytes::<16>().unwrap();
        assert_ne!(a, b);
        assert_eq!(hex(&[0x00, 0xab, 0xff]), "00abff");
        assert_eq!(unhex("00abff").unwrap(), vec![0x00, 0xab, 0xff]);
        assert!(unhex("abc").is_none() && unhex("zz").is_none());
        let k = random_key().unwrap();
        assert_eq!(*key_from_hex(&hex(k.as_ref())).unwrap(), *k);
        assert!(key_from_hex("00ff").is_none(), "wrong length");
        let lit = sqlcipher_key(&k);
        assert!(lit.starts_with("x'") && lit.ends_with('\'') && lit.len() == 67);
    }

    #[test]
    fn constant_time_eq_and_password_rules() {
        assert!(ct_eq(b"abc", b"abc"));
        assert!(!ct_eq(b"abc", b"abd"));
        assert!(!ct_eq(b"abc", b"ab"));
        assert!(check_new_password("short").is_err());
        assert!(check_new_password("        ").is_err());
        assert!(check_new_password("long enough").is_ok());
        assert!(check_new_password("пароль-ok").is_ok(), "counts characters, not bytes");
    }

    #[test]
    fn backup_container_roundtrip_and_rejects_garbage() {
        let header = BackupHeader {
            version: 1,
            salt: hex(&[1u8; SALT_LEN]),
            kdf: KdfParams::FAST,
            created_at: 0,
            files: vec![BackupFile { name: "a".into(), size: 3 }, BackupFile { name: "b".into(), size: 2 }],
        };
        let mut buf = Vec::new();
        write_backup(&mut buf, &header, &[b"abc", b"de"]).unwrap();
        let (h, files) = read_backup(&mut buf.as_slice()).unwrap();
        assert_eq!(h.files.len(), 2);
        assert_eq!(files, vec![b"abc".to_vec(), b"de".to_vec()]);

        assert!(read_backup(&mut &b"not a backup"[..]).is_err());
        let truncated = &buf[..buf.len() - 1];
        assert!(matches!(read_backup(&mut &truncated[..]), Err(CryptoError::BadBackup(_))));
        let bad_version = String::from_utf8(buf.clone()).unwrap().replace("\"version\":1", "\"version\":9");
        assert!(read_backup(&mut bad_version.as_bytes()).is_err());
    }
}
