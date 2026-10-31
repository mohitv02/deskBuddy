import { useEffect, useState } from "react";
import { ipc, type ChatStatus, type LinkView, type TeamView } from "../../lib/ipc";

const HOURS = [1, 2, 3, 6, 12, 24, 48, 72];
const RETENTION = [
  [0, "Delete when it closes"],
  [1, "1 day"],
  [7, "7 days"],
  [30, "30 days"],
  [365, "1 year"],
  [-1, "Forever"],
] as const;

const short = (device: string) => device.slice(0, 8);

function until(ms: number, now: number): string {
  const min = Math.max(0, Math.round((ms - now) / 60000));
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  return min % 60 ? `${h} h ${min % 60} min` : `${h} h`;
}

const kindLabel = (l: LinkView) =>
  l.kind === "group"
    ? "group chat"
    : l.kind === "personal"
      ? "personal chats between members"
      : `temporary group (${l.hours} h, archive ${l.retentionDays === null ? "kept forever" : l.retentionDays === 0 ? "not kept" : `kept ${l.retentionDays} days`})`;

type Shown = { team: string; kind: "invite" | "address"; code: string };

export function TeamsPanel({
  status,
  onOpen,
  onError,
}: {
  status: ChatStatus;
  onOpen: (conversation: number) => void;
  onError: (e: string | null) => void;
}) {
  const [shown, setShown] = useState<Shown | null>(null);
  const [createName, setCreateName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [confirm, setConfirm] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [req, setReq] = useState({ team: "", address: "", kind: "group", hours: 2, retention: 7 });
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(t);
  }, []);

  const online = status.state === "online";
  const names = new Map(status.users.map((u) => [u.device, u]));
  const active = status.teams.filter((t) => !t.removed);
  const team = req.team || active[0]?.id || "";

  const run = async (op: () => Promise<unknown>, done?: string) => {
    onError(null);
    setNote(null);
    try {
      await op();
      if (done) setNote(done);
      return true;
    } catch (e) {
      onError(String(e));
      return false;
    }
  };

  // Destructive buttons ask once: the first click arms them for 3 s.
  const armed = (key: string, op: () => void) => {
    if (confirm !== key) {
      setConfirm(key);
      window.setTimeout(() => setConfirm((k) => (k === key ? null : k)), 3000);
      return;
    }
    setConfirm(null);
    op();
  };

  const show = (t: TeamView, kind: Shown["kind"]) =>
    void run(async () =>
      setShown({ team: t.id, kind, code: kind === "invite" ? await ipc.teamInvite(t.id) : await ipc.teamAddress(t.id) }),
    );

  const incoming = status.links.filter((l) => l.state === "pending" && !l.outgoing);
  const outgoing = status.links.filter((l) => l.state === "pending" && l.outgoing);
  const linked = status.links.filter((l) => l.state === "active" || l.state === "archived");

  return (
    <div className="teams-panel">
      {note && <div className="notice ok">{note}</div>}
      {!online && (
        <p className="setting-note">Connect to a chat server to create teams or send requests. Joining from an invite works offline.</p>
      )}

      <h3>Your teams</h3>
      {status.teams.length === 0 && <p className="empty">No teams yet. Create one, or paste an invite from a teammate below.</p>}
      {status.teams.map((t) => (
        <div key={t.id} className={t.removed ? "team-card removed" : "team-card"}>
          <div className="team-head">
            <b>{t.name}</b>
            <small>
              {t.removed
                ? "removed · history only"
                : `${t.members.length} member${t.members.length === 1 ? "" : "s"} · ${t.members.filter((d) => names.get(d)?.online).length} online · key v${t.keyVersion}`}
            </small>
          </div>
          {!t.removed && t.members.length > 0 && (
            <div className="team-members">
              {t.members.map((d) => (
                <span key={d} className="chip" title={d}>
                  {names.get(d)?.online ? "🟢" : "⚪"} {names.get(d)?.name ?? short(d)}
                </span>
              ))}
            </div>
          )}
          {!t.removed && (
            <div className="team-actions">
              <button className="mini" title="Invite a teammate (contains the team key: share privately)" onClick={() => show(t, "invite")}>
                Invite
              </button>
              <button className="mini" title="Public address another team needs to send you a request" onClick={() => show(t, "address")}>
                Address
              </button>
              <button
                className={confirm === `rotate:${t.id}` ? "mini danger" : "mini"}
                disabled={!online}
                title="New team key. Everyone else is removed until they join with the new invite (use this to remove someone)."
                onClick={() =>
                  armed(
                    `rotate:${t.id}`,
                    () =>
                      void run(
                        async () => setShown({ team: t.id, kind: "invite", code: await ipc.teamRotate(t.id) }),
                        "New key made. Share the new invite with the people who should stay.",
                      ),
                  )
                }
              >
                {confirm === `rotate:${t.id}` ? "New key?" : "New key"}
              </button>
              <button
                className={confirm === `leave:${t.id}` ? "mini danger" : "mini"}
                disabled={!online}
                onClick={() => armed(`leave:${t.id}`, () => void run(() => ipc.teamLeave(t.id), `You left ${t.name}.`))}
              >
                {confirm === `leave:${t.id}` ? "Leave?" : "Leave"}
              </button>
            </div>
          )}
          {shown?.team === t.id && (
            <div className="code-box">
              <small>
                {shown.kind === "invite"
                  ? "Invite: contains the team key. Send it only to people who should read this team's messages."
                  : "Address: safe to share. Another team pastes it to send you a request."}
              </small>
              <code>{shown.code}</code>
              <span className="team-actions">
                <button
                  className="mini primary"
                  onClick={() => void run(() => ipc.copyText(shown.code, shown.kind === "invite"), "Copied.")}
                >
                  Copy
                </button>
                <button className="mini" onClick={() => setShown(null)}>
                  Hide
                </button>
              </span>
            </div>
          )}
        </div>
      ))}

      <form
        className="chat-new"
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            const code = await ipc.teamCreate(createName);
            setCreateName("");
            const created = (await ipc.chatStatus()).teams.find((t) => t.name === createName.trim());
            if (created) setShown({ team: created.id, kind: "invite", code });
          }, "Team created. Copy its invite for your teammates.");
        }}
      >
        <input
          value={createName}
          maxLength={40}
          onChange={(e) => setCreateName(e.target.value)}
          placeholder="New team name"
          aria-label="New team name"
        />
        <button className="mini primary" disabled={!createName.trim() || !online}>
          Create
        </button>
      </form>
      <form
        className="chat-new"
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            const name = await ipc.teamJoin(joinCode);
            setJoinCode("");
            setNote(`Joined ${name}.`);
          });
        }}
      >
        <input
          value={joinCode}
          onChange={(e) => setJoinCode(e.target.value)}
          placeholder="Paste a team invite (DBT1-…)"
          aria-label="Team invite"
        />
        <button className="mini primary" disabled={!joinCode.trim()}>
          Join
        </button>
      </form>

      {incoming.length > 0 && <h3>Requests for your teams</h3>}
      {incoming.map((l) => (
        <div key={l.id} className="team-card request">
          <div>
            <b>{l.otherTeamName}</b> wants a {kindLabel(l)} with <b>{l.myTeamName}</b>.
          </div>
          <SafetyNumber value={l.safetyNumber} />
          <div className="team-actions">
            <button className="mini primary" disabled={!online} onClick={() => void run(() => ipc.linkRespond(l.id, true), "Accepted.")}>
              Accept
            </button>
            <button className="mini" disabled={!online} onClick={() => void run(() => ipc.linkRespond(l.id, false))}>
              Decline
            </button>
          </div>
        </div>
      ))}
      {outgoing.map((l) => (
        <div key={l.id} className="team-card request">
          <div>
            Waiting for <b>{l.otherTeamName}</b> to accept a {kindLabel(l)}.
          </div>
          <SafetyNumber value={l.safetyNumber} />
        </div>
      ))}

      {linked.length > 0 && <h3>Linked teams</h3>}
      {linked.map((l) => (
        <div key={l.id} className="team-card">
          <div className="team-head">
            <b>
              {l.myTeamName} ↔ {l.otherTeamName}
            </b>
            <small>
              {kindLabel(l)}
              {l.state === "active" && l.expiresAt !== null && ` · closes in ${until(l.expiresAt, now)}`}
              {l.state === "archived" && " · closed"}
              {l.purgeAt !== null && ` · archive deleted in ${until(l.purgeAt, now)}`}
            </small>
          </div>
          <SafetyNumber value={l.safetyNumber} />
          {l.state === "archived" && (
            <p className="setting-note">
              Archive: {l.weReleased ? "your team released its half" : "your half is withheld"} ·{" "}
              {l.theyReleased ? `${l.otherTeamName} released theirs` : `${l.otherTeamName} withholds theirs`}.{" "}
              {l.weReleased && l.theyReleased ? "Both released: it's readable." : "It's readable only when both teams release."}
            </p>
          )}
          <div className="team-actions">
            {l.conversation !== null && (l.state === "active" || (l.weReleased && l.theyReleased)) && (
              <button className="mini primary" onClick={() => onOpen(l.conversation!)}>
                Open chat
              </button>
            )}
            {l.state === "archived" && !l.weReleased && (
              <button
                className="mini"
                disabled={!online}
                onClick={() => void run(() => ipc.archiveRelease(l.id), "Your half is offered. The other team must release theirs too.")}
              >
                Release our half
              </button>
            )}
            {l.state === "archived" && (l.weReleased || l.theyReleased) && (
              <button className="mini" disabled={!online} onClick={() => void run(() => ipc.archiveLock(l.id), "Archive locked again.")}>
                Lock archive
              </button>
            )}
          </div>
          {l.kind === "personal" && l.state === "active" && (
            <p className="setting-note">Members of both teams can now start direct chats with each other (＋ in the chat bar).</p>
          )}
        </div>
      ))}

      <h3>Ask another team</h3>
      <form
        className="link-form"
        onSubmit={(e) => {
          e.preventDefault();
          const hours = req.kind === "temp" ? req.hours : null;
          const retention = req.kind === "temp" ? (req.retention < 0 ? null : req.retention) : null;
          void run(async () => {
            await ipc.linkRequest(team, req.address, req.kind, hours, retention);
            setReq((r) => ({ ...r, address: "" }));
          }, "Request sent. Compare the safety number with the other team once they see it.");
        }}
      >
        <label>
          From
          <select value={team} onChange={(e) => setReq((r) => ({ ...r, team: e.target.value }))}>
            {active.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Their address
          <input value={req.address} onChange={(e) => setReq((r) => ({ ...r, address: e.target.value }))} placeholder="DBA1-…" />
        </label>
        <label>
          Type
          <select value={req.kind} onChange={(e) => setReq((r) => ({ ...r, kind: e.target.value }))}>
            <option value="group">Group chat: both teams in one room</option>
            <option value="temp">Temporary group: closes after a few hours</option>
            <option value="personal">Personal: members may message each other directly</option>
          </select>
        </label>
        {req.kind === "temp" && (
          <>
            <label>
              Closes after
              <select value={req.hours} onChange={(e) => setReq((r) => ({ ...r, hours: Number(e.target.value) }))}>
                {HOURS.map((h) => (
                  <option key={h} value={h}>
                    {h} hour{h === 1 ? "" : "s"}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Keep the archive
              <select value={req.retention} onChange={(e) => setReq((r) => ({ ...r, retention: Number(e.target.value) }))}>
                {RETENTION.map(([d, label]) => (
                  <option key={d} value={d}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
        <button className="mini primary" disabled={!online || !team || !req.address.trim()}>
          Send request
        </button>
      </form>
    </div>
  );
}

function SafetyNumber({ value }: { value: string | null }) {
  if (!value) return null;
  return (
    <p className="setting-note" title="Both teams see the same number. If theirs differs, someone swapped the keys: don't trust this link.">
      Safety number <code>{value}</code> · compare it with the other team on a call
    </p>
  );
}
