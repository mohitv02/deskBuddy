//! DeskBuddy chat server: a relay in front of MongoDB. Apps log in with a
//! device key and send end-to-end encrypted messages; the server stores and
//! forwards ciphertext. Several servers can share one database (a *home*),
//! and homes forward linked teams' messages to each other.
//!
//! Configuration (environment, or a `.env` file next to where it runs; the
//! file is re-read every few seconds, so a new MONGODB_URI applies without a
//! restart):
//!   MONGODB_URI      e.g. mongodb://host:27018/?tls=true&tlsCAFile=/path/ca.pem
//!                    (unset: the server runs and waits for one)
//!   MONGODB_DB       database name (default `deskbuddy_chat`)
//!   CHAT_BIND        listen address (default `0.0.0.0:8787`)
//!   CHAT_PUBLIC_URL  how other servers reach this one, comma-separated
//!                    (default `http://<LAN address>:<port>`)
//!   CHAT_ENV_FILE    path of the file above (default `.env`)

mod cluster;
mod config;
mod fed;
mod hub;
mod protocol;
mod rooms;
mod session;
mod store;

use std::net::SocketAddr;
use std::sync::{Arc, Mutex, RwLock};
use std::time::Duration;

use axum::extract::{ConnectInfo, State, WebSocketUpgrade};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Serialize;

/// Largest frame accepted from a client (a max-size message plus JSON overhead).
const MAX_FRAME_BYTES: usize = 64 * 1024;
const DB_CHECK_EVERY: Duration = Duration::from_secs(5);
const DB_CONNECT_TIMEOUT: Duration = Duration::from_secs(20);

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DbStatus {
    /// "unconfigured", "connecting", "connected" or "error".
    pub state: &'static str,
    pub error: Option<String>,
    pub database: String,
}

pub struct App {
    store: RwLock<Option<Arc<store::Store>>>,
    db: Mutex<DbStatus>,
    pub hub: hub::Hub,
    /// This server process, among the servers sharing the database.
    pub instance: String,
    pub public_urls: Vec<String>,
}

impl App {
    /// The database, if connected.
    pub fn store(&self) -> Option<Arc<store::Store>> {
        self.store.read().unwrap_or_else(|p| p.into_inner()).clone()
    }

    fn set_db(&self, status: DbStatus, store: Option<Option<Arc<store::Store>>>) {
        *self.db.lock().unwrap_or_else(|p| p.into_inner()) = status;
        if let Some(s) = store {
            *self.store.write().unwrap_or_else(|p| p.into_inner()) = s;
        }
    }

    /// Push a frame to these devices on every server of this home.
    pub async fn deliver(&self, to: &[String], frame: &str, skip_conn: Option<u64>) {
        for d in to {
            self.hub.send_to(d, frame, skip_conn);
        }
        if let Some(s) = self.store() {
            if let Err(e) = s.publish(&self.instance, to, frame).await {
                eprintln!("chat: can't publish to other servers: {e}");
            }
        }
    }

    /// Push a frame to everyone connected to this home, except `skip`.
    pub async fn deliver_all(&self, frame: &str, skip: &str) {
        self.hub.broadcast(frame, skip);
        if let Some(s) = self.store() {
            let _ = s.publish(&self.instance, &[], frame).await;
        }
    }
}

pub fn random_hex<const N: usize>() -> String {
    let mut b = [0u8; N];
    getrandom::fill(&mut b).expect("system randomness");
    hex(&b)
}

pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

pub fn sha256_hex(s: &str) -> String {
    use sha2::Digest;
    hex(&sha2::Sha256::digest(s.as_bytes()))
}

/// Constant-time comparison.
pub fn ct_eq(a: &[u8], b: &[u8]) -> bool {
    a.len() == b.len() && a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

async fn ws(ws: WebSocketUpgrade, ConnectInfo(peer): ConnectInfo<SocketAddr>, State(app): State<Arc<App>>) -> Response {
    ws.max_message_size(MAX_FRAME_BYTES).max_frame_size(MAX_FRAME_BYTES).on_upgrade(move |socket| session::run(socket, peer.ip(), app))
}

/// The address this server sees you connect from.
async fn whoami(ConnectInfo(peer): ConnectInfo<SocketAddr>) -> impl IntoResponse {
    Json(serde_json::json!({ "ip": peer.ip().to_canonical().to_string() }))
}

/// Liveness plus database state, for the app's Settings page.
async fn health(State(app): State<Arc<App>>) -> impl IntoResponse {
    let db = app.db.lock().unwrap_or_else(|p| p.into_inner()).clone();
    let home = app.store().map(|s| s.home.clone());
    Json(serde_json::json!({ "ok": true, "version": 2, "db": db, "home": home, "instance": app.instance }))
}

/// Keep the database connected: connect when a URI appears, reconnect when it
/// changes, and report problems instead of exiting.
async fn supervise_db(app: Arc<App>) {
    let mut connected: Option<(String, String)> = None;
    loop {
        let cfg = config::load();
        let wanted = cfg.mongodb_uri.clone().map(|u| (u, cfg.mongodb_db.clone()));
        match wanted {
            None => {
                connected = None;
                let status = DbStatus { state: "unconfigured", error: Some("MONGODB_URI is not set".into()), database: cfg.mongodb_db };
                app.set_db(status, Some(None));
            }
            Some(target) if connected.as_ref() != Some(&target) => {
                let (uri, db) = target.clone();
                app.set_db(DbStatus { state: "connecting", error: None, database: db.clone() }, None);
                match config::check_tls_files(&uri) {
                    Err(e) => {
                        eprintln!("chat: {e}");
                        app.set_db(DbStatus { state: "error", error: Some(e), database: db }, Some(None));
                    }
                    Ok(()) => match tokio::time::timeout(DB_CONNECT_TIMEOUT, store::Store::connect(&uri, &db)).await {
                        Ok(Ok(s)) => {
                            eprintln!("chat: connected to MongoDB (database `{db}`, home {})", s.home);
                            app.set_db(DbStatus { state: "connected", error: None, database: db }, Some(Some(Arc::new(s))));
                            connected = Some(target);
                        }
                        Ok(Err(e)) => {
                            eprintln!("chat: cannot reach MongoDB: {e}");
                            app.set_db(DbStatus { state: "error", error: Some(e.to_string()), database: db }, Some(None));
                        }
                        Err(_) => {
                            eprintln!("chat: MongoDB did not answer within {}s", DB_CONNECT_TIMEOUT.as_secs());
                            let e = format!("MongoDB did not answer within {} s", DB_CONNECT_TIMEOUT.as_secs());
                            app.set_db(DbStatus { state: "error", error: Some(e), database: db }, Some(None));
                        }
                    },
                }
            }
            Some(_) => {}
        }
        tokio::time::sleep(DB_CHECK_EVERY).await;
    }
}

async fn shutdown_signal() {
    let ctrl_c = tokio::signal::ctrl_c();
    #[cfg(unix)]
    {
        let mut term = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()).expect("signal handler");
        tokio::select! { _ = ctrl_c => {}, _ = term.recv() => {} }
    }
    #[cfg(not(unix))]
    let _ = ctrl_c.await;
}

#[tokio::main]
async fn main() {
    let cfg = config::load();
    let listener = match tokio::net::TcpListener::bind(&cfg.bind).await {
        Ok(l) => l,
        Err(e) => {
            eprintln!("chat: cannot listen on {}: {e}", cfg.bind);
            std::process::exit(1);
        }
    };
    let port = listener.local_addr().map(|a| a.port()).unwrap_or(8787);
    let public_urls = cfg.public_urls(port);
    let app = Arc::new(App {
        store: RwLock::new(None),
        db: Mutex::new(DbStatus { state: "connecting", error: None, database: cfg.mongodb_db.clone() }),
        hub: hub::Hub::default(),
        instance: random_hex::<8>(),
        public_urls: public_urls.clone(),
    });

    tokio::spawn(supervise_db(app.clone()));
    tokio::spawn(cluster::run(app.clone()));
    tokio::spawn(fed::worker(app.clone()));
    tokio::spawn(fed::janitor(app.clone()));
    let _mdns = cluster::advertise(&app.instance, port);

    let router = Router::new()
        .route("/ws", get(ws))
        .route("/whoami", get(whoami))
        .route("/health", get(health))
        .route("/fed", post(fed::receive))
        .with_state(app.clone());

    eprintln!("chat: listening on {} (reachable as {})", cfg.bind, public_urls.join(", "));
    axum::serve(listener, router.into_make_service_with_connect_info::<SocketAddr>())
        .with_graceful_shutdown(shutdown_signal())
        .await
        .expect("server error");
    if let Some(s) = app.store() {
        let _ = s.remove_instance(&app.instance).await;
    }
}
