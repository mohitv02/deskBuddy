//! Several servers on one database act as one: each registers itself, keeps
//! the presence of its connections fresh, and replays pushes the others
//! publish to the `events` collection. Also announces this server on the LAN
//! over mDNS so apps can find it.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use mongodb::bson::{oid::ObjectId, DateTime};

use crate::App;

const TAIL_EVERY: Duration = Duration::from_millis(300);
const HEARTBEAT_EVERY: Duration = Duration::from_secs(20);
/// Events can be written slightly out of order by different servers; look
/// back this far and skip the ones already seen.
const OVERLAP_MS: i64 = 3000;

pub const MDNS_SERVICE: &str = "_deskbuddy._tcp.local.";

pub async fn run(app: Arc<App>) {
    let mut since = DateTime::now();
    let mut seen: HashMap<ObjectId, i64> = HashMap::new();
    let mut tail = tokio::time::interval(TAIL_EVERY);
    let mut beat = tokio::time::interval(HEARTBEAT_EVERY);
    loop {
        tokio::select! {
            _ = tail.tick() => {
                let Some(store) = app.store() else { continue };
                let from = DateTime::from_millis(since.timestamp_millis() - OVERLAP_MS);
                match store.events_since(&app.instance, from).await {
                    Ok(events) => {
                        for e in events {
                            if seen.insert(e.id, e.at.timestamp_millis()).is_some() {
                                continue;
                            }
                            if e.at > since {
                                since = e.at;
                            }
                            if e.to.is_empty() {
                                app.hub.broadcast(&e.frame, "");
                            } else {
                                for d in &e.to {
                                    app.hub.send_to(d, &e.frame, None);
                                }
                            }
                        }
                        let cutoff = since.timestamp_millis() - 4 * OVERLAP_MS;
                        seen.retain(|_, at| *at > cutoff);
                    }
                    Err(e) => eprintln!("chat: reading cluster events: {e}"),
                }
            }
            _ = beat.tick() => {
                let Some(store) = app.store() else { continue };
                if let Err(e) = store.heartbeat_instance(&app.instance, &app.public_urls).await {
                    eprintln!("chat: cluster heartbeat: {e}");
                }
                let _ = store.set_presence(&app.instance, &app.hub.devices()).await;
            }
        }
    }
}

/// Announce `_deskbuddy._tcp` on the LAN. The returned daemon must stay alive.
pub fn advertise(instance: &str, port: u16) -> Option<mdns_sd::ServiceDaemon> {
    let ip = crate::config::lan_ip()?;
    let daemon = mdns_sd::ServiceDaemon::new().map_err(|e| eprintln!("chat: mDNS unavailable: {e}")).ok()?;
    let name = format!("deskbuddy-{instance}");
    let host = format!("{name}.local.");
    let props = [("v", "2")];
    let info = mdns_sd::ServiceInfo::new(MDNS_SERVICE, &name, &host, ip, port, &props[..]).ok()?;
    match daemon.register(info) {
        Ok(()) => {
            eprintln!("chat: announced on the LAN as {name} ({ip}:{port})");
            Some(daemon)
        }
        Err(e) => {
            eprintln!("chat: mDNS announce failed: {e}");
            None
        }
    }
}
