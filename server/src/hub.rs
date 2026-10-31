//! Live connections on this server, by device. One device may hold several
//! sockets (e.g. two app windows); it is online while any of them is open.

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;

use tokio::sync::mpsc;

/// Outgoing frames for one socket. Bounded: a client that stops reading loses
/// live pushes and catches up with `sync` instead of growing server memory.
pub type Outbox = mpsc::Sender<String>;
pub const OUTBOX_CAPACITY: usize = 256;

#[derive(Default)]
pub struct Hub {
    next_id: AtomicU64,
    conns: Mutex<HashMap<String, HashMap<u64, Outbox>>>,
}

impl Hub {
    /// Returns the connection id and whether the user just came online.
    pub fn register(&self, device: &str, outbox: Outbox) -> (u64, bool) {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let mut conns = self.conns.lock().unwrap_or_else(|p| p.into_inner());
        let sockets = conns.entry(device.to_string()).or_default();
        let first = sockets.is_empty();
        sockets.insert(id, outbox);
        (id, first)
    }

    /// Returns whether the user went offline.
    pub fn unregister(&self, device: &str, id: u64) -> bool {
        let mut conns = self.conns.lock().unwrap_or_else(|p| p.into_inner());
        let Some(sockets) = conns.get_mut(device) else { return false };
        sockets.remove(&id);
        let empty = sockets.is_empty();
        if empty {
            conns.remove(device);
        }
        empty
    }

    pub fn is_online(&self, device: &str) -> bool {
        self.conns.lock().unwrap_or_else(|p| p.into_inner()).contains_key(device)
    }

    pub fn devices(&self) -> Vec<String> {
        self.conns.lock().unwrap_or_else(|p| p.into_inner()).keys().cloned().collect()
    }

    /// Push to every socket of `device` except `skip`.
    pub fn send_to(&self, device: &str, frame: &str, skip: Option<u64>) {
        let conns = self.conns.lock().unwrap_or_else(|p| p.into_inner());
        for (id, outbox) in conns.get(device).into_iter().flatten() {
            if Some(*id) != skip {
                let _ = outbox.try_send(frame.to_string());
            }
        }
    }

    /// Push to every connected user except `skip`.
    pub fn broadcast(&self, frame: &str, skip: &str) {
        let conns = self.conns.lock().unwrap_or_else(|p| p.into_inner());
        for outbox in conns.iter().filter(|(d, _)| *d != skip).flat_map(|(_, s)| s.values()) {
            let _ = outbox.try_send(frame.to_string());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn presence_and_routing() {
        let hub = Hub::default();
        let (a1, mut ra1) = mpsc::channel(4);
        let (a2, mut ra2) = mpsc::channel(4);
        let (b, mut rb) = mpsc::channel(4);
        let (ida1, first) = hub.register("a", a1);
        assert!(first);
        let (ida2, first) = hub.register("a", a2);
        assert!(!first, "second socket of the same machine");
        hub.register("b", b);

        hub.send_to("a", "x", Some(ida1));
        assert!(ra1.try_recv().is_err());
        assert_eq!(ra2.try_recv().unwrap(), "x");
        hub.broadcast("p", "a");
        assert_eq!(rb.try_recv().unwrap(), "p");
        assert!(ra1.try_recv().is_err() && ra2.try_recv().is_err());

        assert!(!hub.unregister("a", ida1));
        assert!(hub.is_online("a"));
        assert!(hub.unregister("a", ida2));
        assert!(!hub.is_online("a"));
    }
}
