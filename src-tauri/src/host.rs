//! Hosting a chat server on this machine: edit the server's `.env` (it
//! re-reads the file every few seconds) and ask the server how it is doing.

use std::path::Path;
use std::time::Duration;

use serde::Serialize;
use tokio::io::{AsyncReadExt, AsyncWriteExt};

const HTTP_TIMEOUT: Duration = Duration::from_secs(3);

#[derive(Debug, Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct HostStatus {
    pub env_exists: bool,
    /// MONGODB_URI with any password hidden.
    pub uri: Option<String>,
    pub database: Option<String>,
    /// A certificate file the URI names that isn't on this machine.
    pub missing_file: Option<String>,
    /// The local server's answer to /health, if it is running.
    pub server: Option<serde_json::Value>,
    pub server_error: Option<String>,
}

fn parse_env(text: &str) -> Vec<(String, String)> {
    text.lines()
        .filter_map(|l| {
            let l = l.trim();
            if l.starts_with('#') {
                return None;
            }
            let (k, v) = l.split_once('=')?;
            Some((k.trim().to_string(), v.trim().trim_matches('"').to_string()))
        })
        .collect()
}

fn mask(uri: &str) -> String {
    // mongodb://user:password@host → mongodb://user:•••@host
    let Some((scheme, rest)) = uri.split_once("://") else { return uri.to_string() };
    match rest.split_once('@') {
        Some((cred, host)) if cred.contains(':') => format!("{scheme}://{}:•••@{host}", cred.split(':').next().unwrap_or("")),
        _ => uri.to_string(),
    }
}

pub fn missing_tls_file(uri: &str) -> Option<String> {
    let query = uri.split_once('?').map(|(_, q)| q).unwrap_or("");
    query.split('&').filter_map(|p| p.split_once('=')).find_map(|(k, v)| {
        (matches!(k, "tlsCAFile" | "tlsCertificateKeyFile") && !Path::new(v).is_file()).then(|| v.to_string())
    })
}

fn bind_port(vars: &[(String, String)]) -> u16 {
    vars.iter()
        .find(|(k, _)| k == "CHAT_BIND")
        .and_then(|(_, v)| v.rsplit(':').next()?.parse().ok())
        .unwrap_or(8787)
}

pub async fn status(env_path: &str) -> HostStatus {
    let path = Path::new(env_path);
    let text = std::fs::read_to_string(path).ok();
    let vars = text.as_deref().map(parse_env).unwrap_or_default();
    let get = |k: &str| vars.iter().find(|(key, _)| key == k).map(|(_, v)| v.clone()).filter(|v| !v.is_empty());
    let uri = get("MONGODB_URI");
    let mut out = HostStatus {
        env_exists: text.is_some(),
        missing_file: uri.as_deref().and_then(missing_tls_file),
        uri: uri.as_deref().map(mask),
        database: get("MONGODB_DB"),
        ..Default::default()
    };
    match health(&format!("127.0.0.1:{}", bind_port(&vars))).await {
        Ok(v) => out.server = Some(v),
        Err(e) => out.server_error = Some(e),
    }
    out
}

/// Write MONGODB_URI / MONGODB_DB into the `.env`, keeping its other lines.
pub fn save(env_path: &str, uri: &str, database: &str) -> Result<(), String> {
    let uri = uri.trim();
    if !(uri.starts_with("mongodb://") || uri.starts_with("mongodb+srv://")) {
        return Err("the URI starts with mongodb:// or mongodb+srv://".into());
    }
    if uri.contains(char::is_whitespace) {
        return Err("the URI can't contain spaces".into());
    }
    if let Some(f) = missing_tls_file(uri) {
        return Err(format!("{f} doesn't exist on this machine; copy the certificate here first"));
    }
    let database = database.trim();
    if !database.is_empty() && !database.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-') {
        return Err("database names use letters, digits, _ and -".into());
    }
    let path = Path::new(env_path);
    if path.file_name().is_none() || env_path.trim().is_empty() {
        return Err("set the path of the server's .env file".into());
    }
    if let Some(dir) = path.parent().filter(|d| !d.as_os_str().is_empty()) {
        if !dir.is_dir() {
            return Err(format!("{} is not a folder", dir.display()));
        }
    }
    let old = std::fs::read_to_string(path).unwrap_or_default();
    let mut lines: Vec<String> = Vec::new();
    let (mut put_uri, mut put_db) = (false, database.is_empty());
    for line in old.lines() {
        let key = line.split_once('=').map(|(k, _)| k.trim()).filter(|_| !line.trim_start().starts_with('#'));
        match key {
            Some("MONGODB_URI") => {
                lines.push(format!("MONGODB_URI={uri}"));
                put_uri = true;
            }
            Some("MONGODB_DB") if !database.is_empty() => {
                lines.push(format!("MONGODB_DB={database}"));
                put_db = true;
            }
            _ => lines.push(line.to_string()),
        }
    }
    if !put_uri {
        lines.push(format!("MONGODB_URI={uri}"));
    }
    if !put_db {
        lines.push(format!("MONGODB_DB={database}"));
    }
    let tmp = path.with_extension("tmp");
    std::fs::write(&tmp, lines.join("\n") + "\n").map_err(|e| format!("can't write {}: {e}", tmp.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o600));
    }
    std::fs::rename(&tmp, path).map_err(|e| format!("can't write {}: {e}", path.display()))
}

/// GET /health from `host:port`.
pub async fn health(host: &str) -> Result<serde_json::Value, String> {
    let attempt = async {
        let mut sock = tokio::net::TcpStream::connect(host).await.map_err(|e| format!("not running ({e})"))?;
        let req = format!("GET /health HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n");
        sock.write_all(req.as_bytes()).await.map_err(|e| e.to_string())?;
        let mut buf = Vec::new();
        sock.read_to_end(&mut buf).await.map_err(|e| e.to_string())?;
        let text = String::from_utf8_lossy(&buf);
        let body = text.split_once("\r\n\r\n").map(|(_, b)| b).unwrap_or("");
        serde_json::from_str(body.trim()).map_err(|_| "answered, but isn't a v2 DeskBuddy chat server".to_string())
    };
    tokio::time::timeout(HTTP_TIMEOUT, attempt).await.map_err(|_| "did not answer".to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn masks_passwords() {
        assert_eq!(mask("mongodb://u:secret@h:1/?x=1"), "mongodb://u:•••@h:1/?x=1");
        assert_eq!(mask("mongodb://h:1/"), "mongodb://h:1/");
    }

    #[test]
    fn edits_env_in_place() {
        let dir = std::env::temp_dir().join(format!("deskbuddy-host-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let env = dir.join(".env");
        std::fs::write(&env, "# keep\nCHAT_BIND=0.0.0.0:9000\nMONGODB_URI=old\n").unwrap();
        let p = env.to_str().unwrap();
        save(p, "mongodb://10.0.0.1:27017/", "team_one").unwrap();
        let text = std::fs::read_to_string(&env).unwrap();
        assert_eq!(text, "# keep\nCHAT_BIND=0.0.0.0:9000\nMONGODB_URI=mongodb://10.0.0.1:27017/\nMONGODB_DB=team_one\n");
        assert_eq!(bind_port(&parse_env(&text)), 9000);
        assert!(save(p, "http://x", "").is_err());
        assert!(save(p, "mongodb://h/?tls=true&tlsCAFile=/nope/ca.pem", "").unwrap_err().contains("/nope/ca.pem"));
        assert!(save(p, "mongodb://h/", "bad name").is_err());
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
