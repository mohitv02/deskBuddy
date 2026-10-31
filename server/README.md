# DeskBuddy chat server

A relay in front of MongoDB for DeskBuddy's end-to-end encrypted chat. Apps
log in with a device key; the server stores and forwards ciphertext it can't
read.

```bash
cp .env.example .env      # then edit, or let DeskBuddy's Settings write it
cargo run --release
```

| Variable | Default | Meaning |
|---|---|---|
| `MONGODB_URI` | unset | e.g. `mongodb://192.168.1.10:27017/?tls=true&tlsCAFile=/etc/ssl/mongodb/ca.pem`. Unset or unreachable: the server keeps running, reports why on `/health`, and retries every 5 s |
| `MONGODB_DB` | `deskbuddy_chat` | The database. One database is one **home** |
| `CHAT_BIND` | `0.0.0.0:8787` | Listen address |
| `CHAT_PUBLIC_URL` | `http://<LAN address>:<port>` | How apps and other homes reach this server, comma-separated |
| `CHAT_ENV_FILE` | `.env` | The file above. It is re-read every 5 s, so a new URI applies without a restart |

## Run it in the background (systemd)

```ini
# /etc/systemd/system/deskbuddy-chat.service
[Unit]
Description=DeskBuddy chat server
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/path/to/server
ExecStart=/path/to/server/target/release/deskbuddy-chat-server
Restart=always
RestartSec=3
User=you

[Install]
WantedBy=multi-user.target
```

`sudo systemctl enable --now deskbuddy-chat`, then `curl localhost:8787/health`.
Don't use `EnvironmentFile=` for the database URI: the server reads `.env`
from its working directory itself, so changes apply without a restart.

## Design

**Identity.** Each app install has an Ed25519 key; its hex public key is the
device id. On connect the server sends a random `challenge`, and the app's
`hello` signs it together with its X25519 key. Names are display only.

**Encryption** happens in the app (`src-tauri/src/e2e.rs`). Bodies arrive as
`e1.<key version>.<base64>`; the server checks only their size.

| Conversation | Id | Who can read it | Key |
|---|---|---|---|
| Direct | `dm:<device>\|<device>` | the two devices | X25519 of the two devices |
| Team | `team:<id>` | members | from the team key, which travels only in invites |
| Team to team | `link:<id>` | members of both teams | X25519 of the two teams' keys |
| Temporary | `link:<id>` | both teams, until it closes | the above plus one half from each team |

**Teams.** Joining needs a proof derived from the team key; the server keeps
only its SHA-256, so it can check membership without being able to read
anything. Rotating the key replaces the proof and drops every other member.

**Links** connect two teams: `group`, `temp` (1–72 h, then archived) or
`personal` (members may message each other directly). A temporary group's
key mixes a random half from each team. Each team stores its own half
encrypted with its team key (`own`) and the other team's copy encrypted for
them (`toPeer`). When the group closes, the server drops both `toPeer` copies,
so neither team can read the archive alone; `archiveRelease` offers a half
again, and sync is allowed only while both are offered. Archives are deleted
after `retentionDays` (never, if unset).

### Several servers, one home

Servers sharing a database register in `instances`, keep `presence` fresh,
and publish pushes for each other to `events` (polled every 300 ms; TTL 10
min). Apps get the live server list in `welcome` and fail over between them.
Servers also announce `_deskbuddy._tcp` over mDNS, which the app's **Find
servers on this network** button looks for.

### Homes talking to each other (federation)

A link between teams on different databases is forwarded with `POST /fed`.
Every delivery carries the link's random `fedToken`, which both homes stored
when the link was made. Deliveries go through the `outbox` collection, so
they survive restarts and are retried with backoff (up to a week) while the
other home is offline. Each home keeps its own copy of the link's messages.

## Tests

`cargo test` runs the unit tests. `tests/integration.py` starts a throwaway
MongoDB plus three servers (two sharing a database, one on its own) and
checks logins, permissions, teams, every link type, archives, federation
forgeries, outages and restarts:

```bash
pip install websockets pynacl      # mongod and mongosh must be installed
cargo build && python3 -u tests/integration.py
```

## Protocol

JSON text frames on `ws://host:8787/ws`, tagged by `type`.

| App → server | |
|---|---|
| `hello {device, dhPub, name, sig}` | First frame, answering `challenge` |
| `send {conversationId, clientMsgId, body}` | Resending the same `clientMsgId` never duplicates |
| `conversations` / `sync {conversationId, afterSeq, limit}` | Catching up |
| `teamJoin {teamId, name, dhPub, proof}` / `teamLeave` / `teamRotate {proof, newProof}` | Teams |
| `linkRequest {linkId, kind, hours?, retentionDays?, fromTeam, toTeam, fedToken, share?}` | Ask another team |
| `linkRespond {linkId, accept, share?}` | Any member of the asked team |
| `archiveRelease {linkId, toPeer}` / `archiveLock {linkId}` | Temporary group archives |

| Server → app | |
|---|---|
| `challenge {nonce}`, then `welcome {you, home, servers, users, teams, links}` | |
| `presence`, `user`, `team`, `teamGone`, `link` | Changes |
| `ack`, `message`, `conversations`, `messages` | Messages |
| `error {code, message, clientMsgId?}` | e.g. `bad_identity`, `wrong_key`, `not_found`, `closed`, `rate_limited`, `unavailable` |

HTTP: `GET /health` (`{"ok", "version": 2, "db": {state, error, database}, "home"}`),
`GET /whoami`, `POST /fed`.

Limits: 32 KB per message body, 20 sends per 10 s per connection, 64 KB per frame.

**What the server can see:** who is in which team, who wrote to which
conversation and when, and message sizes. Not the text. On a network you
don't trust, put TLS in front of it; the app doesn't support `wss://` yet.
