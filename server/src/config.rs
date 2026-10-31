//! Settings from the environment and the `.env` file. The file wins over the
//! process environment and is read again on every call, so the app (or an
//! admin) can change the database URI while the server runs.

use std::collections::HashMap;
use std::path::PathBuf;

pub struct Config {
    pub mongodb_uri: Option<String>,
    pub mongodb_db: String,
    pub bind: String,
    public_url: Option<String>,
}

fn env_file() -> PathBuf {
    std::env::var("CHAT_ENV_FILE").map(PathBuf::from).unwrap_or_else(|_| PathBuf::from(".env"))
}

pub fn load() -> Config {
    let file: HashMap<String, String> =
        dotenvy::from_path_iter(env_file()).map(|it| it.filter_map(Result::ok).collect()).unwrap_or_default();
    let get = |key: &str| {
        file.get(key).cloned().or_else(|| std::env::var(key).ok()).map(|v| v.trim().to_string()).filter(|v| !v.is_empty())
    };
    Config {
        mongodb_uri: get("MONGODB_URI"),
        mongodb_db: get("MONGODB_DB").unwrap_or_else(|| "deskbuddy_chat".into()),
        bind: get("CHAT_BIND").unwrap_or_else(|| "0.0.0.0:8787".into()),
        public_url: get("CHAT_PUBLIC_URL"),
    }
}

impl Config {
    /// How other servers and apps reach this one.
    pub fn public_urls(&self, port: u16) -> Vec<String> {
        if let Some(list) = &self.public_url {
            return list.split(',').map(|s| s.trim().trim_end_matches('/').to_string()).filter(|s| !s.is_empty()).collect();
        }
        match lan_ip() {
            Some(ip) => vec![format!("http://{ip}:{port}")],
            None => vec![format!("http://127.0.0.1:{port}")],
        }
    }
}

/// The address this machine uses on the LAN (no packet is sent).
pub fn lan_ip() -> Option<std::net::IpAddr> {
    let s = std::net::UdpSocket::bind("0.0.0.0:0").ok()?;
    s.connect("8.8.8.8:80").ok()?;
    s.local_addr().ok().map(|a| a.ip()).filter(|ip| !ip.is_loopback())
}

/// Certificate files named in the URI must exist; say which one is missing
/// instead of the driver's long error.
pub fn check_tls_files(uri: &str) -> Result<(), String> {
    let query = uri.split_once('?').map(|(_, q)| q).unwrap_or("");
    for pair in query.split('&') {
        let Some((k, v)) = pair.split_once('=') else { continue };
        if matches!(k, "tlsCAFile" | "tlsCertificateKeyFile") && !std::path::Path::new(v).is_file() {
            return Err(format!("{k} {v} does not exist on the server machine"));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tls_files() {
        assert!(check_tls_files("mongodb://h:1/").is_ok());
        assert!(check_tls_files("mongodb://h:1/?tls=true").is_ok());
        let e = check_tls_files("mongodb://h:1/?tls=true&tlsCAFile=/nope/ca.pem").unwrap_err();
        assert!(e.contains("/nope/ca.pem"));
    }

    #[test]
    fn public_urls() {
        let c = Config { mongodb_uri: None, mongodb_db: String::new(), bind: String::new(), public_url: Some("http://a:1/, http://b:2".into()) };
        assert_eq!(c.public_urls(9), ["http://a:1", "http://b:2"]);
    }
}
