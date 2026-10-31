"""Integration tests for the chat server, against a real MongoDB.

Starts its own throwaway MongoDB (port 27100, in a temporary folder) and
servers on 127.0.0.1:
   :8811 + :8812 share database h1 (one home, two servers)
   :8813 uses database h2 (another home)

Needs mongod and mongosh on PATH, and: pip install websockets pynacl
Run from server/:   cargo build && python3 -u tests/integration.py [name filter]
"""
import asyncio, json, os, secrets, shutil, subprocess, sys, tempfile, time, urllib.request
import websockets
from nacl.signing import SigningKey
from nacl.public import PrivateKey

S = tempfile.mkdtemp(prefix="deskbuddy-chat-test-")
BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "target", "debug", "deskbuddy-chat-server")
MPORT = 27100
URI = f"mongodb://127.0.0.1:{MPORT}/"
procs = {}

def h(n=16): return secrets.token_hex(n)

# ---------------------------------------------------------------- processes
def mongo(cmd):
    return subprocess.run(["mongosh", "--quiet", "--port", str(MPORT), "--eval", cmd], capture_output=True, text=True).stdout.strip()

def start_mongo(fresh=False):
    d = f"{S}/suite-mdb"
    if fresh:
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    subprocess.run(["mongod", "--dbpath", d, "--port", str(MPORT), "--bind_ip", "127.0.0.1", "--fork", "--logpath", f"{S}/suite-mdb.log"],
                   capture_output=True, check=True)

def stop_mongo():
    subprocess.run(["mongod", "--dbpath", f"{S}/suite-mdb", "--shutdown"], capture_output=True)

def write_env(port, db, uri=URI):
    with open(f"{S}/suite-{port}.env", "w") as f:
        if uri:
            f.write(f"MONGODB_URI={uri}\n")
        f.write(f"MONGODB_DB={db}\nCHAT_BIND=127.0.0.1:{port}\nCHAT_PUBLIC_URL=http://127.0.0.1:{port}\n")

def start_server(port, db=None, uri=URI):
    if db is not None:
        write_env(port, db, uri)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MONGODB", "CHAT_"))}
    env["CHAT_ENV_FILE"] = f"{S}/suite-{port}.env"
    procs[port] = subprocess.Popen([BIN], env=env, stdout=open(f"{S}/suite-{port}.log", "a"), stderr=subprocess.STDOUT)

def kill_server(port):
    p = procs.pop(port, None)
    if p:
        p.kill(); p.wait()

def health(port):
    try:
        return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).read())
    except Exception as e:
        return {"down": str(e)}

async def until(pred, what, timeout=15):
    for _ in range(int(timeout / 0.2)):
        r = pred()
        if r:
            return r
        await asyncio.sleep(0.2)
    raise AssertionError(f"timed out: {what}")

def post_fed(port, payload):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/fed", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=3).status
    except urllib.error.HTTPError as e:
        return e.code

# ---------------------------------------------------------------- client
class Client:
    def __init__(self, name, port, sk=None, dh=None):
        self.name, self.port = name, port
        self.sk = sk or SigningKey.generate()
        self.dh = dh or PrivateKey.generate()
        self.device = self.sk.verify_key.encode().hex()
        self.dh_pub = bytes(self.dh.public_key).hex()
        self.inbox = []

    def clone(self, port=None):
        return Client(self.name, port or self.port, self.sk, self.dh)

    async def connect(self):
        self.ws = await websockets.connect(f"ws://127.0.0.1:{self.port}/ws", max_size=None)
        ch = json.loads(await self.ws.recv())
        assert ch["type"] == "challenge", ch
        sig = self.sk.sign(f"deskbuddy-hello-v2\n{ch['nonce']}\n{self.device}\n{self.dh_pub}".encode()).signature.hex()
        await self.ws.send(json.dumps({"type": "hello", "device": self.device, "dhPub": self.dh_pub, "name": self.name, "sig": sig}))
        self.welcome = json.loads(await self.ws.recv())
        assert self.welcome["type"] == "welcome", self.welcome
        self.task = asyncio.create_task(self.reader())
        return self

    async def reader(self):
        try:
            async for m in self.ws:
                self.inbox.append(json.loads(m))
        except Exception:
            pass

    async def send(self, **frame):
        await self.ws.send(json.dumps(frame))

    async def wait(self, pred, what, timeout=10):
        for _ in range(int(timeout / 0.05)):
            for m in self.inbox:
                if pred(m):
                    self.inbox.remove(m)
                    return m
            await asyncio.sleep(0.05)
        raise AssertionError(f"{self.name}@{self.port}: timed out waiting for {what}; inbox={[m['type'] for m in self.inbox][-8:]}")

    async def none(self, pred, what, wait=1.5):
        await asyncio.sleep(wait)
        bad = [m for m in self.inbox if pred(m)]
        assert not bad, f"{self.name}: unexpected {what}: {bad[:1]}"

    async def error(self, code=None, timeout=5):
        e = await self.wait(lambda m: m["type"] == "error", f"error {code}", timeout)
        assert code is None or e["code"] == code, f"expected {code}, got {e}"
        return e

    async def msg(self, conv, cid, body="e1.0.x"):
        await self.send(type="send", conversationId=conv, clientMsgId=cid, body=body)
        return (await self.wait(lambda m: (m["type"] == "ack" and m["clientMsgId"] == cid) or (m["type"] == "error" and m.get("clientMsgId") == cid), f"ack {cid}"))

    async def got(self, cid, timeout=12):
        return await self.wait(lambda m: m["type"] == "message" and m["message"]["clientMsgId"] == cid, f"message {cid}", timeout)

    async def close(self):
        await self.ws.close()

def dm(a, b): return "dm:" + "|".join(sorted([a.device, b.device]))

async def make_team(*members, name="Team"):
    tid, proof, dh = h(), h(32), PrivateKey.generate()
    for c in members:
        await c.send(type="teamJoin", teamId=tid, name=name, dhPub=bytes(dh.public_key).hex(), proof=proof)
        await c.wait(lambda m: m["type"] == "team" and c.device in m["team"]["members"], "join")
    return {"id": tid, "proof": proof, "dh": dh, "name": name, "home": members[0].welcome["home"], "port": members[0].port}

def ref(team):
    return {"id": team["id"], "name": team["name"], "dhPub": bytes(team["dh"].public_key).hex(), "home": team["home"], "servers": [f"http://127.0.0.1:{team['port']}"]}

async def make_link(a, ta, b, tb, kind="group", **extra):
    lid = h()
    shares = {"share": {"own": "ownA", "toPeer": "peerA"}} if kind == "temp" else {}
    await a.send(type="linkRequest", linkId=lid, kind=kind, fromTeam=ta["id"], toTeam=ref(tb), fedToken=h(), **shares, **extra)
    await b.wait(lambda m: m["type"] == "link" and m["link"]["id"] == lid, "request", 15)
    await b.send(type="linkRespond", linkId=lid, accept=True, **({"share": {"own": "ownB", "toPeer": "peerB"}} if kind == "temp" else {}))
    await a.wait(lambda m: m["type"] == "link" and m["link"]["id"] == lid and m["link"]["state"] == "active", "active", 15)
    return lid

# ---------------------------------------------------------------- tests
TESTS = []
def test(fn):
    TESTS.append(fn); return fn

async def raw(port):
    ws = await websockets.connect(f"ws://127.0.0.1:{port}/ws")
    ch = json.loads(await ws.recv())
    return ws, ch["nonce"]

@test
async def auth_rejects_forged_replayed_and_malformed():
    c = Client("X", 8811)
    ws, nonce = await raw(8811)
    await ws.send(json.dumps({"type": "hello", "device": c.device, "dhPub": c.dh_pub, "sig": "00" * 64}))
    assert json.loads(await ws.recv())["code"] == "bad_identity"
    # Replay: a signature for one challenge is useless for the next.
    ws, nonce = await raw(8811)
    sig = c.sk.sign(f"deskbuddy-hello-v2\n{nonce}\n{c.device}\n{c.dh_pub}".encode()).signature.hex()
    ws2, _ = await raw(8811)
    await ws2.send(json.dumps({"type": "hello", "device": c.device, "dhPub": c.dh_pub, "sig": sig}))
    assert json.loads(await ws2.recv())["code"] == "bad_identity", "replayed signature accepted"
    # Swapping the DH key invalidates the signature.
    ws3, n3 = await raw(8811)
    sig = c.sk.sign(f"deskbuddy-hello-v2\n{n3}\n{c.device}\n{c.dh_pub}".encode()).signature.hex()
    await ws3.send(json.dumps({"type": "hello", "device": c.device, "dhPub": h(32), "sig": sig}))
    assert json.loads(await ws3.recv())["code"] == "bad_identity", "DH key swap accepted"
    ws4, _ = await raw(8811)
    await ws4.send(json.dumps({"type": "conversations"}))
    assert json.loads(await ws4.recv())["code"] == "hello_required"
    ws5, _ = await raw(8811)
    await ws5.send("{not json")
    assert json.loads(await ws5.recv())["code"] == "bad_request"
    ws6, _ = await raw(8811)
    await ws6.send(json.dumps({"type": "hello", "device": "ZZ", "dhPub": c.dh_pub, "sig": "00"}))
    assert json.loads(await ws6.recv())["code"] == "bad_identity"

@test
async def hello_timeout_closes():
    ws, _ = await raw(8811)
    t = time.time()
    try:
        await asyncio.wait_for(ws.recv(), 15)
    except websockets.ConnectionClosed:
        pass
    assert 9 <= time.time() - t < 14, "silent client not dropped after ~10 s"

@test
async def login_storm_welcome_comes_first():
    clients = [Client(f"S{i}", 8811 if i % 2 else 8812) for i in range(40)]
    results = await asyncio.gather(*(c.connect() for c in clients), return_exceptions=True)
    bad = [r for r in results if isinstance(r, Exception)]
    assert not bad, f"{len(bad)}/40 logins failed, e.g. {bad[0]}"
    for c in clients:
        await c.close()

@test
async def direct_messages_ack_seq_and_idempotency():
    a, b = await Client("A", 8811).connect(), await Client("B", 8811).connect()
    conv = dm(a, b)
    r1 = await a.msg(conv, "m1")
    assert r1["type"] == "ack" and r1["message"]["seq"] == 1
    assert (await b.got("m1"))["message"]["from"] == a.device
    r2 = await a.msg(conv, "m1")
    assert r2["message"]["seq"] == 1 and r2["message"]["id"] == r1["message"]["id"], "retry created a new message"
    await b.none(lambda m: m["type"] == "message", "duplicate push")
    assert (await b.msg(conv, "m2"))["message"]["seq"] == 2
    await a.got("m2")
    await a.send(type="conversations")
    cs = await a.wait(lambda m: m["type"] == "conversations", "conversations")
    assert any(i["id"] == conv and i["lastSeq"] == 2 for i in cs["items"])

@test
async def validation_errors():
    a, b = await Client("A", 8811).connect(), await Client("B", 8811).connect()
    conv = dm(a, b)
    for cid, body, why in [("bad id!", "x", "clientMsgId"), ("ok1", "", "empty"), ("ok2", "x" * 32001, "too long")]:
        r = await a.msg(conv, cid, body)
        assert r["type"] == "error" and r["code"] == "bad_request", (why, r)
    r = await a.msg("team:nothex", "c1")
    assert r["code"] == "bad_request"
    r = await a.msg(f"dm:{b.device}|{a.device}" if b.device > a.device else f"dm:{a.device}|{b.device}x", "c2")
    assert r["type"] == "error", "unsorted dm id accepted"
    stranger = PrivateKey.generate()
    ghost = h(32)
    r = await a.msg("dm:" + "|".join(sorted([a.device, ghost])), "c3")
    assert r["code"] == "not_found", "DM to a device that never connected"
    c = await Client("C", 8811).connect()
    r = await c.msg(conv, "c4")
    assert r["code"] == "not_found", "third party wrote into someone else's DM"
    await c.send(type="sync", conversationId=conv, afterSeq=0)
    assert (await c.error())["code"] == "not_found", "third party read someone else's DM"

@test
async def rate_limit():
    a, b = await Client("A", 8811).connect(), await Client("B", 8811).connect()
    conv = dm(a, b)
    for i in range(20):
        await a.send(type="send", conversationId=conv, clientMsgId=f"r{i}", body="e1.0.x")
    await a.send(type="send", conversationId=conv, clientMsgId="r20", body="e1.0.x")
    e = await a.wait(lambda m: m["type"] == "error" and m.get("clientMsgId") == "r20", "rate limit")
    assert e["code"] == "rate_limited"

@test
async def sync_paging():
    a, b = await Client("A", 8811).connect(), await Client("B", 8811).connect()
    conv = dm(a, b)
    for i in range(5):
        await a.msg(conv, f"p{i}")
    seen, after = [], 0
    while True:
        await b.send(type="sync", conversationId=conv, afterSeq=after, limit=2)
        page = await b.wait(lambda m: m["type"] == "messages", "page")
        seen += [m["clientMsgId"] for m in page["items"]]
        if not page["more"]:
            break
        after = page["items"][-1]["seq"]
    assert seen == [f"p{i}" for i in range(5)], seen

@test
async def same_device_two_connections():
    a, b = await Client("A", 8811).connect(), await Client("B", 8811).connect()
    a2 = await a.clone(8812).connect()
    await a.msg(dm(a, b), "s1")
    await a2.got("s1")
    await a.none(lambda m: m["type"] == "message" and m["message"]["clientMsgId"] == "s1", "echo to the sending connection")
    await b.got("s1")

@test
async def teams_membership_rules():
    a, b, c = [await Client(n, 8811).connect() for n in "ABC"]
    t = await make_team(a)
    await b.send(type="teamJoin", teamId=t["id"], name="x", dhPub=h(32), proof=h(32))
    await b.error("wrong_key")
    await b.send(type="teamJoin", teamId=t["id"], name="x", dhPub=h(32), proof=t["proof"])
    await a.wait(lambda m: m["type"] == "team" and b.device in m["team"]["members"], "A told about B")
    assert (await c.msg(f"team:{t['id']}", "x1"))["code"] == "not_found"
    await c.send(type="sync", conversationId=f"team:{t['id']}", afterSeq=0)
    await c.error("not_found")
    await a.msg(f"team:{t['id']}", "t1")
    await b.got("t1")
    await c.none(lambda m: m["type"] == "message", "team message leaked to outsider", 0.5)
    await b.send(type="teamLeave", teamId=t["id"])
    await b.wait(lambda m: m["type"] == "teamGone", "teamGone")
    assert (await b.msg(f"team:{t['id']}", "t2"))["code"] == "not_found"

@test
async def rotation_drops_others_and_old_key():
    a, b = await Client("A", 8811).connect(), await Client("B", 8812).connect()
    t = await make_team(a, b)
    new = h(32)
    await a.send(type="teamRotate", teamId=t["id"], proof=h(32), newProof=new)
    await a.error("wrong_key")
    await a.send(type="teamRotate", teamId=t["id"], proof=t["proof"], newProof=new)
    await b.wait(lambda m: m["type"] == "teamGone", "B dropped (other server)")
    await b.send(type="teamJoin", teamId=t["id"], name="x", dhPub=h(32), proof=t["proof"])
    await b.error("wrong_key")
    await b.send(type="teamJoin", teamId=t["id"], name="x", dhPub=h(32), proof=new)
    await b.wait(lambda m: m["type"] == "team" and b.device in m["team"]["members"], "rejoined")

@test
async def same_home_link_and_who_may_accept():
    a, b = await Client("A", 8811).connect(), await Client("B", 8812).connect()
    ta, tb = await make_team(a, name="Alpha"), await make_team(b, name="Beta")
    lid = h()
    await a.send(type="linkRequest", linkId=lid, kind="group", fromTeam=ta["id"], toTeam=ref(tb), fedToken=h())
    await b.wait(lambda m: m["type"] == "link" and m["link"]["id"] == lid, "request on same home")
    await a.send(type="linkRespond", linkId=lid, accept=True)
    await a.error("not_found")
    await b.send(type="linkRespond", linkId=lid, accept=True)
    await a.wait(lambda m: m["type"] == "link" and m["link"]["state"] == "active", "active")
    await a.msg(f"link:{lid}", "l1")
    await b.got("l1")
    await b.send(type="linkRespond", linkId=lid, accept=True)
    await b.error("not_found")

@test
async def link_request_validation():
    a, c = await Client("A", 8811).connect(), await Client("C", 8813).connect()
    ta, tc = await make_team(a), await make_team(c)
    base = dict(type="linkRequest", fromTeam=ta["id"], toTeam=ref(tc), fedToken=h())
    for extra, why in [({"kind": "temp", "hours": 2}, "temp without shares"), ({"kind": "temp", "hours": 0, "share": {"own": "a", "toPeer": "b"}}, "0 h"),
                       ({"kind": "temp", "hours": 73, "share": {"own": "a", "toPeer": "b"}}, "73 h"), ({"kind": "group", "fromTeam": tc["id"]}, "not my team")]:
        await a.send(**{**base, "linkId": h(), **extra})
        e = await a.error()
        assert e["code"] in ("bad_request", "not_found"), (why, e)
    lid = h()
    await a.send(**{**base, "linkId": lid, "kind": "group"})
    await a.wait(lambda m: m["type"] == "link", "ok")
    await a.send(**{**base, "linkId": lid, "kind": "group"})
    await a.error("bad_request")
    await a.send(**{**base, "linkId": h(), "kind": "group", "toTeam": {**ref(tc), "servers": ["javascript:x"]}})
    await a.error("bad_request")

@test
async def cross_home_group_decline_and_personal():
    a, c = await Client("A", 8811).connect(), await Client("C", 8813).connect()
    ta, tc = await make_team(a, name="One"), await make_team(c, name="Two")
    lid = h()
    await a.send(type="linkRequest", linkId=lid, kind="group", fromTeam=ta["id"], toTeam=ref(tc), fedToken=h())
    await c.wait(lambda m: m["type"] == "link" and m["link"]["id"] == lid, "request", 15)
    await c.send(type="linkRespond", linkId=lid, accept=False)
    await a.wait(lambda m: m["type"] == "link" and m["link"]["state"] == "declined", "declined", 15)
    assert (await a.msg(f"link:{lid}", "d1"))["code"] == "closed"
    g = await make_link(a, ta, c, tc)
    await a.msg(f"link:{g}", "g1"); await c.got("g1")
    await c.msg(f"link:{g}", "g2"); await a.got("g2")
    assert (await a.msg(dm(a, c), "pd0"))["code"] == "not_found", "cross-home DM without personal link"
    p = await make_link(a, ta, c, tc, kind="personal")
    assert (await a.msg(f"link:{p}", "pg"))["code"] == "closed", "personal link has no room"
    await a.msg(dm(a, c), "pd1"); await c.got("pd1")
    await c.msg(dm(a, c), "pd2"); await a.got("pd2")

@test
async def new_member_after_link_is_announced():
    a, c = await Client("A", 8811).connect(), await Client("C", 8813).connect()
    ta, tc = await make_team(a), await make_team(c)
    lid = await make_link(a, ta, c, tc)
    late = await Client("Late", 8812).connect()
    await late.send(type="teamJoin", teamId=ta["id"], name="x", dhPub=h(32), proof=ta["proof"])
    await late.wait(lambda m: m["type"] == "link" and m["link"]["id"] == lid, "existing link sent to the new member")
    await c.wait(lambda m: m["type"] == "user" and m["user"]["device"] == late.device, "home2 learns the new member", 15)
    await late.msg(f"link:{lid}", "n1")
    await c.got("n1")
    await c.msg(f"link:{lid}", "n2")
    await late.got("n2")

@test
async def concurrent_archive_release():
    """Both teams press "release" at the same moment, several times."""
    a, c = await Client("A", 8811).connect(), await Client("C", 8813).connect()
    ta, tc = await make_team(a), await make_team(c)
    failures = 0
    for round in range(6):
        lid = await make_link(a, ta, c, tc, kind="temp", hours=1, retentionDays=7)
        await a.msg(f"link:{lid}", f"x{round}")
        mongo(f'for (const d of ["h1","h2"]) db.getSiblingDB(d).links.updateOne({{_id:"{lid}"}},{{$set:{{state:"archived", expiresAt:new Date(Date.now()-1000), "shareA.toPeer":null, "shareB.toPeer":null}}}})')
        await asyncio.gather(a.send(type="archiveRelease", linkId=lid, toPeer="ra"), c.send(type="archiveRelease", linkId=lid, toPeer="rc"))
        await asyncio.sleep(4)
        st = [json.loads(mongo(f'JSON.stringify(db.getSiblingDB("{d}").links.findOne({{_id:"{lid}"}},{{shareA:1,shareB:1}}))')) for d in ("h1", "h2")]
        if not all(s["shareA"]["toPeer"] == "ra" and s["shareB"]["toPeer"] == "rc" for s in st):
            failures += 1
    assert failures == 0, f"a release was lost in {failures}/6 rounds"

@test
async def zero_retention_archive_is_purged():
    a, c = await Client("A", 8811).connect(), await Client("C", 8813).connect()
    ta, tc = await make_team(a), await make_team(c)
    lid = await make_link(a, ta, c, tc, kind="temp", hours=1, retentionDays=0)
    await a.msg(f"link:{lid}", "z1"); await c.got("z1")
    mongo(f'for (const d of ["h1","h2"]) db.getSiblingDB(d).links.updateOne({{_id:"{lid}"}},{{$set:{{expiresAt:new Date(Date.now()-1000)}}}})')
    await a.wait(lambda m: m["type"] == "link" and m["link"]["id"] == lid and m["link"]["state"] == "closed", "purged", 75)
    n = mongo(f'db.getSiblingDB("h1").messages.countDocuments({{conversationId:"link:{lid}"}})')
    assert n == "0", f"{n} messages left after purge"

@test
async def federation_endpoint_rejects_forgeries():
    a, c = await Client("A", 8811).connect(), await Client("C", 8813).connect()
    ta, tc = await make_team(a), await make_team(c)
    lid = await make_link(a, ta, c, tc)
    home1 = a.welcome["home"]
    msg = {"conversationId": f"link:{lid}", "from": a.device, "clientMsgId": "f1", "body": "e1.0.x", "createdAt": int(time.time() * 1000)}
    assert post_fed(8813, {"linkId": lid, "token": h(), "home": home1, "event": {"type": "message", "message": msg}}) == 403, "wrong token"
    assert post_fed(8813, {"linkId": h(), "token": h(), "home": home1, "event": {"type": "lock"}}) == 404
    assert post_fed(8813, {"linkId": "x", "token": "y", "home": "z", "event": {"type": "lock"}}) == 400
    assert post_fed(8813, {"garbage": 1}) in (400, 415, 422)
    token = mongo(f'db.getSiblingDB("h2").links.findOne({{_id:"{lid}"}}).fedToken')
    impostor = {**msg, "from": h(32), "clientMsgId": "f2"}
    assert post_fed(8813, {"linkId": lid, "token": token, "home": home1, "event": {"type": "message", "message": impostor}}) == 403, "non-member sender"
    assert post_fed(8813, {"linkId": lid, "token": token, "home": c.welcome["home"], "event": {"type": "lock"}}) in (400, 403), "own home id"
    req = {"id": h(), "kind": "group", "state": "pending", "a": ref(ta), "b": {**ref(tc), "id": h()}, "hours": None, "expiresAt": None,
           "retentionDays": None, "purgeAt": None, "shareA": {}, "shareB": {}, "createdAt": 0}
    assert post_fed(8813, {"linkId": req["id"], "token": h(), "home": home1, "event": {"type": "request", "link": req}}) == 404, "request for unknown team"

@test
async def late_temp_messages_survive_the_other_home_being_down():
    a, c = await Client("A", 8811).connect(), await Client("C", 8813).connect()
    ta, tc = await make_team(a), await make_team(c)
    lid = await make_link(a, ta, c, tc, kind="temp", hours=1, retentionDays=7)
    await c.close()
    kill_server(8813)
    await a.msg(f"link:{lid}", "late1")
    await asyncio.sleep(2)  # the group closes after the message was written
    # The group's time runs out while home 2 is still down.
    mongo(f'db.getSiblingDB("h2").links.updateOne({{_id:"{lid}"}},{{$set:{{state:"archived", expiresAt:new Date(Date.now()-1000), "shareA.toPeer":null, "shareB.toPeer":null}}}})')
    mongo(f'db.getSiblingDB("h1").links.updateOne({{_id:"{lid}"}},{{$set:{{expiresAt:new Date(Date.now()-1000)}}}})')
    await asyncio.sleep(2)
    start_server(8813)
    await until(lambda: health(8813).get("db", {}).get("state") == "connected", "H2 back")
    await until(lambda: mongo(f'db.getSiblingDB("h2").messages.countDocuments({{conversationId:"link:{lid}"}})') == "1",
                "message written before the group closed reaches home 2", 30)

@test
async def outbox_survives_restarts():
    a, c = await Client("A", 8811).connect(), await Client("C", 8813).connect()
    ta, tc = await make_team(a), await make_team(c)
    lid = await make_link(a, ta, c, tc)
    await c.close()
    kill_server(8813)
    await a.msg(f"link:{lid}", "ob1")
    kill_server(8811); kill_server(8812)
    start_server(8811); start_server(8812)
    await until(lambda: health(8811).get("db", {}).get("state") == "connected", "H1 back")
    start_server(8813)
    await until(lambda: health(8813).get("db", {}).get("state") == "connected", "H2 back")
    await until(lambda: mongo(f'db.getSiblingDB("h2").messages.countDocuments({{conversationId:"link:{lid}"}})') == "1", "delivered after restarts", 40)

@test
async def queued_members_and_request_arrive_in_any_order():
    a, c = await Client("A", 8811).connect(), await Client("C", 8813).connect()
    ta, tc = await make_team(a), await make_team(c)
    kill_server(8813)
    lid = h()
    await a.send(type="linkRequest", linkId=lid, kind="group", fromTeam=ta["id"], toTeam=ref(tc), fedToken=h())
    await a.wait(lambda m: m["type"] == "link", "pending")
    b = await Client("B", 8812).connect()
    await b.send(type="teamJoin", teamId=ta["id"], name="x", dhPub=h(32), proof=ta["proof"])
    await b.wait(lambda m: m["type"] == "team", "joined")
    # Make the members update due before the request, as a busy cluster might.
    mongo('db.getSiblingDB("h1").outbox.find().forEach(o => { if (o.payload.includes(\'"type":"members"\')) '
          'db.getSiblingDB("h1").outbox.updateOne({_id:o._id},{$set:{nextAt:new Date(0)}}) })')
    start_server(8813)
    await until(lambda: health(8813).get("db", {}).get("state") == "connected", "H2 back")
    await until(lambda: mongo(f'db.getSiblingDB("h2").links.findOne({{_id:"{lid}"}})?.a.members.length') == "2",
                "home 2 ends with both members of team 1", 40)

@test
async def database_outage_and_recovery():
    stop_mongo()
    await until(lambda: health(8811).get("db", {}).get("state") == "error", "/health reports the outage", 40)
    assert "down" not in health(8811), "server died with the database"
    try:
        await Client("A", 8811).connect()
        raise AssertionError("login worked without a database")
    except AssertionError as e:
        if "login worked" in str(e):
            raise
    start_mongo()
    await until(lambda: health(8811).get("db", {}).get("state") == "connected", "reconnected", 40)
    a, b = await Client("A", 8811).connect(), await Client("B", 8812).connect()
    await a.msg(dm(a, b), "after"); await b.got("after")

@test
async def env_hot_reload_and_unconfigured_start():
    start_server(8814, "h3", uri=None)
    await until(lambda: health(8814).get("db", {}).get("state") == "unconfigured", "runs without a URI")
    write_env(8814, "h3")
    await until(lambda: health(8814).get("db", {}).get("state") == "connected", "picks up a new URI", 20)
    write_env(8814, "h4")
    await until(lambda: health(8814).get("db", {}).get("database") == "h4" and health(8814)["db"]["state"] == "connected", "switches database", 20)
    kill_server(8814)

async def main():
    flt = sys.argv[1] if len(sys.argv) > 1 else ""
    stop_mongo()
    start_mongo(fresh=True)
    start_server(8811, "h1"); start_server(8812, "h1"); start_server(8813, "h2")
    for p in (8811, 8812, 8813):
        await until(lambda: health(p).get("db", {}).get("state") == "connected", f"{p} up")
    passed = failed = 0
    for t in TESTS:
        if flt not in t.__name__:
            continue
        t0 = time.time()
        try:
            await asyncio.wait_for(t(), 180)
            passed += 1
            print(f"  ✓ {t.__name__} ({time.time() - t0:.1f}s)")
        except Exception as e:
            failed += 1
            print(f"  ✗ {t.__name__}: {type(e).__name__}: {e}")
        if "down" in health(8811) or mongo("1") != "1":
            start_mongo()
        for p in (8811, 8812, 8813):
            if p not in procs or procs[p].poll() is not None:
                start_server(p)
        for p in (8811, 8812, 8813):
            await until(lambda: health(p).get("db", {}).get("state") == "connected", f"{p} up", 40)
    print(f"{passed} passed, {failed} failed")
    for p in list(procs):
        kill_server(p)
    stop_mongo()
    shutil.rmtree(S, ignore_errors=True)
    os._exit(1 if failed else 0)

if __name__ == "__main__":
    asyncio.run(main())
