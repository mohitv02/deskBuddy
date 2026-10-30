//! DeskBuddy LAN chat server: WebSocket in front of MongoDB. Users are
//! identified by their machine's IP address.
//!
//! Configuration (environment, or a `.env` file next to where it runs):
//!   MONGODB_URI     required, e.g. mongodb://host:27018/?tls=true&tlsCAFile=/path/ca.pem
//!   MONGODB_DB      database name (default `deskbuddy_chat`)
//!   CHAT_BIND       listen address (default `0.0.0.0:8787`)
//!   CHAT_STRICT_IP  `true` (default): a client may only claim the address it
//!                   connects from; `false` trusts whatever `ip` it sends

mod hub;
mod protocol;
mod session;
mod store;

use std::net::SocketAddr;
use std::sync::Arc;

use axum::extract::{ConnectInfo, State, WebSocketUpgrade};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::{Json, Router};

/// Largest frame accepted from a client (a max-size message plus JSON overhead).
const MAX_FRAME_BYTES: usize = 64 * 1024;

pub struct App {
    pub store: store::Store,
    pub hub: hub::Hub,
    pub strict_ip: bool,
}

fn env_or(key: &str, default: &str) -> String {
    std::env::var(key).ok().filter(|v| !v.trim().is_empty()).unwrap_or_else(|| default.to_string())
}

async fn ws(ws: WebSocketUpgrade, ConnectInfo(peer): ConnectInfo<SocketAddr>, State(app): State<Arc<App>>) -> Response {
    ws.max_message_size(MAX_FRAME_BYTES).max_frame_size(MAX_FRAME_BYTES).on_upgrade(move |socket| session::run(socket, peer.ip(), app))
}

/// The address this server sees you connect from: what a client uses as its
/// identity when the user has not set one.
async fn whoami(ConnectInfo(peer): ConnectInfo<SocketAddr>) -> impl IntoResponse {
    Json(serde_json::json!({ "ip": protocol::canonical_ip(peer.ip()) }))
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
    let _ = dotenvy::dotenv();
    let Ok(uri) = std::env::var("MONGODB_URI") else {
        eprintln!("chat: MONGODB_URI is not set (see .env.example)");
        std::process::exit(2);
    };
    let db = env_or("MONGODB_DB", "deskbuddy_chat");
    let bind = env_or("CHAT_BIND", "0.0.0.0:8787");
    let strict_ip = env_or("CHAT_STRICT_IP", "true") != "false";

    let store = match store::Store::connect(&uri, &db).await {
        Ok(s) => s,
        Err(e) => {
            eprintln!("chat: cannot reach MongoDB: {e}");
            std::process::exit(1);
        }
    };
    let app = Arc::new(App { store, hub: hub::Hub::default(), strict_ip });
    let router = Router::new()
        .route("/ws", get(ws))
        .route("/whoami", get(whoami))
        .route("/health", get(|| async { "ok" }))
        .with_state(app);

    let listener = match tokio::net::TcpListener::bind(&bind).await {
        Ok(l) => l,
        Err(e) => {
            eprintln!("chat: cannot listen on {bind}: {e}");
            std::process::exit(1);
        }
    };
    eprintln!("chat: listening on {bind} (database `{db}`, strict ip: {strict_ip})");
    axum::serve(listener, router.into_make_service_with_connect_info::<SocketAddr>())
        .with_graceful_shutdown(shutdown_signal())
        .await
        .expect("server error");
}
