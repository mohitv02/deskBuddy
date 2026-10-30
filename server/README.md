# DeskBuddy chat server

LAN chat between DeskBuddy machines: a WebSocket server in front of MongoDB.
**Each user is identified by their machine's IP address.**

```bash
cp .env.example .env      # then edit
cargo run --release
```

| Variable | Default | Meaning |
|---|---|---|
| `MONGODB_URI` | — (required) | Cluster router, e.g. `mongodb://192.168.1.10:27017/?tls=true&tlsCAFile=/etc/ssl/mongodb/ca.pem` |
| `MONGODB_DB` | `deskbuddy_chat` | Database (collections `users`, `conversations`, `messages`; indexes are created on start) |
| `CHAT_BIND` | `0.0.0.0:8787` | Listen address |
| `CHAT_STRICT_IP` | `true` | A client may only claim the IP it connects from. `false` trusts the `ip` it sends |

## HTTP

- `GET /whoami` → `{"ip": "192.168.1.20"}`: the address the server sees you connect from (auto-detection).
- `GET /health` → `ok`

## WebSocket `/ws`

JSON text frames with a `type`. The first frame must be `hello`.

| Client → server | |
|---|---|
| `{"type":"hello","ip":"192.168.1.20","name":"Mohit"}` | `ip` optional: without it the connection's address is used |
| `{"type":"send","to":"192.168.1.30","clientMsgId":"<uuid>","body":"hi"}` | Resending the same `clientMsgId` never duplicates |
| `{"type":"conversations"}` | Your conversations, most recent first |
| `{"type":"sync","conversationId":"dm:…","afterSeq":12,"limit":100}` | Messages with `seq > afterSeq`, oldest first |

| Server → client | |
|---|---|
| `welcome {you, users}` | After `hello`. `users` lists known machines with `online` |
| `presence {ip, name, online}` | A machine came online / went offline |
| `ack {clientMsgId, message}` | Your `send` was stored; `message.seq` is its position |
| `message {message}` | New message for you (or sent from your other window) |
| `conversations {items}` / `messages {conversationId, items, more}` | Replies |
| `error {code, message}` | `bad_request`, `bad_ip`, `ip_mismatch`, `not_found`, `rate_limited`, `unavailable` |

Limits: 20 KB per message, 20 sends per 10 s per connection, 64 KB per frame.

**Security note:** there is no password; on a LAN, strict IP mode stops casual
impersonation but not someone who controls the network. Messages are stored
in MongoDB as plain text.
