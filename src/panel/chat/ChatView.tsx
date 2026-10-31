import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { listen } from "@tauri-apps/api/event";
import { ipc, POKE, type ChatMessage, type ChatStatus, type ChatUser, type Conversation, type TodoInput } from "../../lib/ipc";
import { addDays, isoDate } from "../../lib/dates";
import { parseQuickAdd } from "../../lib/quickAdd";
import { ReactionPicker, reactionLabel } from "./ReactionPicker";
import { TeamsPanel } from "./TeamsPanel";

const PAGE = 50;
const SELF_ID = 1;

type Mode = { kind: "all" } | { kind: "pinned" } | { kind: "search"; text: string };

/** First line in quick-add syntax becomes the todo; the rest becomes its notes. */
function toTodoInput(body: string): TodoInput {
  const [first, ...rest] = body.trim().split("\n");
  return { ...parseQuickAdd(first), notes: rest.join("\n").trim() };
}

function dayLabel(ms: number, now = new Date()): string {
  const day = isoDate(new Date(ms));
  if (day === isoDate(now)) return "Today";
  if (day === isoDate(addDays(now, -1))) return "Yesterday";
  const d = new Date(ms);
  const sameYear = d.getFullYear() === now.getFullYear();
  return d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: sameYear ? undefined : "numeric" });
}

/** Between two pokes from here, so a stuck finger doesn't flood a friend's desktop. */
const POKE_COOLDOWN_MS = 5000;

const timeOf = (ms: number) => new Date(ms).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

const peerLabel = (c: Conversation) =>
  c.kind === "self"
    ? c.title || "Notes to self"
    : c.room === "team" || c.room === "link"
      ? c.title || "?"
      : c.peerName || c.peerDevice?.slice(0, 8) || c.peerIp || "?";

const roomIcon = (c: Conversation, online: Set<string>) =>
  c.kind === "self"
    ? "📝 "
    : c.room === "team"
      ? "👥 "
      : c.room === "link"
        ? "🤝 "
        : c.room === "ip"
          ? "🗄 "
          : online.has(c.peerDevice ?? "")
            ? "🟢 "
            : "⚪ ";

/** Merge fresh rows into a page, keeping id order. */
function merge(all: ChatMessage[], fresh: ChatMessage[]): ChatMessage[] {
  const byId = new Map(all.map((m) => [m.id, m]));
  for (const m of fresh) byId.set(m.id, m);
  return [...byId.values()].sort((a, b) => a.id - b.id);
}

export function ChatView({ onEditingChange }: { onEditingChange: (open: boolean) => void }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentId, setCurrentId] = useState(SELF_ID);
  const [status, setStatus] = useState<ChatStatus | null>(null);
  const [newChat, setNewChat] = useState(false);
  const [target, setTarget] = useState("");
  const [choices, setChoices] = useState<ChatUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [threadEditing, setThreadEditing] = useState(false);
  const [teams, setTeams] = useState(false);

  useEffect(() => {
    onEditingChange(threadEditing || newChat || teams);
  }, [threadEditing, newChat, teams, onEditingChange]);

  const refresh = useCallback(
    () =>
      void ipc
        .chatConversations()
        .then(setConversations)
        .catch((e) => setError(String(e))),
    [],
  );

  useEffect(() => {
    refresh();
    void ipc.chatStatus().then(setStatus);
    const subs = [listen<ChatStatus>("chat-status", (e) => setStatus(e.payload)), listen<number>("chat-changed", refresh)];
    return () => subs.forEach((p) => void p.then((off) => off()));
  }, [refresh]);

  const current = conversations.find((c) => c.id === currentId) ?? conversations[0];
  const online = new Set(status?.users.filter((u) => u.online).map((u) => u.device));
  const requests = status?.links.filter((l) => l.state === "pending" && !l.outgoing).length ?? 0;

  const open = (who: string) => {
    setError(null);
    ipc
      .chatOpen(who)
      .then((r) => {
        if (r.kind === "choose") return setChoices(r.users);
        setChoices(null);
        setNewChat(false);
        setTeams(false);
        setTarget("");
        setCurrentId(r.conversation.id);
        refresh();
      })
      .catch((e) => setError(String(e)));
  };

  const statusLine = (() => {
    if (!status || status.state === "off")
      return (
        <>
          Chat with others is off ·{" "}
          <button className="link" onClick={() => void ipc.showPanel("settings")}>
            set a server
          </button>
        </>
      );
    if (status.state === "online")
      return (
        <span title={status.me?.device}>
          ● Online as {status.me ? `${status.me.name} · ${status.me.device.slice(0, 8)}` : "…"} · end-to-end encrypted
        </span>
      );
    if (status.state === "connecting") return <>Connecting…</>;
    return <span title={status.error ?? ""}>○ Offline{status.error ? `: ${status.error}` : ""} · messages wait until reconnected</span>;
  })();

  return (
    <div className="chat-view">
      <div className="chat-bar">
        <select
          className="chat-picker"
          value={current?.id ?? SELF_ID}
          onChange={(e) => setCurrentId(Number(e.target.value))}
          aria-label="Conversation"
        >
          {conversations.map((c) => (
            <option key={c.id} value={c.id}>
              {roomIcon(c, online)}
              {peerLabel(c)}
              {c.room === "ip" && c.peerIp ? ` · ${c.peerIp} (old)` : ""}
            </option>
          ))}
        </select>
        <button
          className={newChat ? "mini on" : "mini"}
          title="New direct chat"
          aria-label="New chat"
          onClick={() => {
            setNewChat((v) => !v);
            setChoices(null);
          }}
        >
          ＋
        </button>
        <button
          className={teams ? "mini on" : "mini"}
          title={requests ? `Teams · ${requests} request${requests === 1 ? "" : "s"} waiting` : "Teams"}
          aria-label="Teams"
          onClick={() => setTeams((v) => !v)}
        >
          👥{requests > 0 && <span className="count"> {requests}</span>}
        </button>
      </div>
      <div className={status?.state === "online" ? "chat-status online" : "chat-status"}>{statusLine}</div>

      {newChat && (
        <form
          className="chat-new"
          onSubmit={(e) => {
            e.preventDefault();
            open(target);
          }}
        >
          <input
            autoFocus
            list="chat-users"
            value={target}
            onChange={(e) => {
              setTarget(e.target.value);
              setChoices(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.stopPropagation();
                setNewChat(false);
              }
            }}
            placeholder="Name, e.g. Asha"
            aria-label="Name"
          />
          <datalist id="chat-users">
            {status?.users
              .filter((u) => u.device !== status.me?.device)
              .map((u) => (
                <option key={u.device} value={u.name}>
                  {u.device.slice(0, 8)}
                  {u.local ? "" : " · other team"}
                  {u.online ? " · online" : ""}
                </option>
              ))}
          </datalist>
          <button type="submit" className="mini primary" disabled={!target.trim()}>
            Start
          </button>
          {choices && (
            <div className="chat-choices">
              <span>Several people match:</span>
              {choices.map((u) => (
                <button type="button" key={u.device} className="chip-btn" onClick={() => open(u.device)}>
                  {u.online ? "🟢" : "⚪"} {u.name} · {u.device.slice(0, 8)}
                </button>
              ))}
            </div>
          )}
        </form>
      )}
      {error && (
        <div className="error" role="alert" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      {teams && status && (
        <TeamsPanel
          status={status}
          onError={setError}
          onOpen={(id) => {
            setTeams(false);
            setCurrentId(id);
            refresh();
          }}
        />
      )}
      {!teams && current && (
        <Thread
          key={current.id}
          conversation={current}
          members={status?.teams.find((t) => `team:${t.id}` === current.remoteId)?.members.length ?? null}
          peerOnline={online.has(current.peerDevice ?? "")}
          onEditingChange={setThreadEditing}
          onError={setError}
          onConversationChanged={refresh}
        />
      )}
    </div>
  );
}

function Thread({
  conversation,
  members,
  peerOnline,
  onEditingChange,
  onError,
  onConversationChanged,
}: {
  conversation: Conversation;
  members: number | null;
  peerOnline: boolean;
  onEditingChange: (open: boolean) => void;
  onError: (e: string | null) => void;
  onConversationChanged: () => void;
}) {
  const conv = conversation.id;
  const remote = conversation.kind === "remote";
  const group = conversation.room === "team" || conversation.room === "link";
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [mode, setMode] = useState<Mode>({ kind: "all" });
  const [searchOpen, setSearchOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<{ id: number; body: string } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [pickingReaction, setPickingReaction] = useState(false);
  const [pokeWait, setPokeWait] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  // After a render: stick to the bottom, or keep the view still while older
  // messages are prepended above it.
  const pendingScroll = useRef<{ kind: "bottom" } | { kind: "keep"; fromBottom: number } | null>(null);
  const modeRef = useRef(mode);
  modeRef.current = mode;

  const run = useCallback(
    async (op: () => Promise<unknown>): Promise<boolean> => {
      try {
        onError(null);
        await op();
        return true;
      } catch (e) {
        onError(String(e));
        return false;
      }
    },
    [onError],
  );

  const load = useCallback(
    (m: Mode) =>
      void run(async () => {
        if (m.kind === "all") {
          const page = await ipc.chatList(conv, null, PAGE);
          setMessages(page);
          setHasMore(page.length === PAGE);
        } else {
          const found = m.kind === "pinned" ? await ipc.chatPinned(conv) : (await ipc.chatSearch(conv, m.text)).reverse();
          setMessages(found);
          setHasMore(false);
        }
        pendingScroll.current = { kind: "bottom" };
      }),
    [run, conv],
  );

  useEffect(() => {
    // Typing in the search box reloads after a short pause.
    const t = window.setTimeout(() => load(mode), mode.kind === "search" ? 200 : 0);
    return () => clearTimeout(t);
  }, [mode, load]);

  // Arrivals and delivery updates from the chat connection.
  useEffect(() => {
    const sub = listen<number>("chat-changed", (e) => {
      if (e.payload !== conv || modeRef.current.kind !== "all") return;
      void ipc.chatList(conv, null, PAGE).then((page) => {
        const el = scroller.current;
        if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 60) pendingScroll.current = { kind: "bottom" };
        setMessages((all) => merge(all, page));
      });
    });
    return () => void sub.then((off) => off());
  }, [conv]);

  useEffect(() => {
    onEditingChange(editing !== null || searchOpen || pickingReaction);
  }, [editing, searchOpen, pickingReaction, onEditingChange]);

  useLayoutEffect(() => {
    const el = scroller.current;
    const p = pendingScroll.current;
    if (!el || !p) return;
    el.scrollTop = p.kind === "bottom" ? el.scrollHeight : el.scrollHeight - p.fromBottom;
    pendingScroll.current = null;
  }, [messages]);

  const loadingOlder = useRef(false);
  const loadOlder = () => {
    const el = scroller.current;
    if (!hasMore || loadingOlder.current || !el || mode.kind !== "all" || messages.length === 0) return;
    const before = messages[0].id;
    loadingOlder.current = true;
    void run(async () => {
      const page = await ipc.chatList(conv, before, PAGE);
      pendingScroll.current = { kind: "keep", fromBottom: el.scrollHeight - el.scrollTop };
      setMessages((all) => [...page, ...all]);
      setHasMore(page.length === PAGE);
    }).finally(() => (loadingOlder.current = false));
  };

  const replace = (m: ChatMessage) => setMessages((all) => all.map((x) => (x.id === m.id ? m : x)));

  const post = async (body: string) => {
    const m = await ipc.chatSend(conv, body);
    if (mode.kind === "all") {
      pendingScroll.current = { kind: "bottom" };
      setMessages((all) => merge(all, [m]));
    } else {
      setSearchOpen(false);
      setMode({ kind: "all" });
    }
  };

  const poke = () => {
    if (pokeWait) return;
    setPokeWait(true);
    window.setTimeout(() => setPokeWait(false), POKE_COOLDOWN_MS);
    void run(() => post(POKE));
  };

  const send = () => {
    if (!draft.trim()) return;
    void run(async () => {
      await post(draft);
      setDraft("");
    });
  };

  const saveEdit = () => {
    if (!editing) return;
    void run(async () => {
      replace(await ipc.chatEdit(editing.id, editing.body));
      setEditing(null);
    });
  };

  const togglePin = (m: ChatMessage) =>
    void run(async () => {
      const next = await ipc.chatPin(m.id, !m.pinned);
      if (mode.kind === "pinned" && !next.pinned) setMessages((all) => all.filter((x) => x.id !== m.id));
      else replace(next);
    });

  const remove = (m: ChatMessage) => {
    if (confirmDelete !== m.id) {
      setConfirmDelete(m.id);
      window.setTimeout(() => setConfirmDelete((id) => (id === m.id ? null : id)), 3000);
      return;
    }
    void run(async () => {
      await ipc.chatDelete(m.id);
      setMessages((all) => all.filter((x) => x.id !== m.id));
      setConfirmDelete(null);
    });
  };

  const makeTodo = (m: ChatMessage) =>
    void run(async () => {
      const input = toTodoInput(m.body);
      if (!input.title) throw new Error("The first line has no text left for a todo title");
      replace(await ipc.chatToTodo(m.id, input));
    });

  const composerKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    }
  };

  const editKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      saveEdit();
    } else if (e.key === "Escape") {
      e.stopPropagation();
      setEditing(null);
    }
  };

  const closeSearch = () => {
    setSearchOpen(false);
    setMode({ kind: "all" });
  };

  const name = peerLabel(conversation);
  const canPoke = remote && conversation.room !== "ip";
  const pokeLine = (m: ChatMessage, theirs: boolean) =>
    theirs
      ? `${m.senderName || m.senderIp?.slice(0, 8) || "Someone"} poked ${group ? "everyone" : "you"}`
      : `You poked ${group ? "everyone" : name}`;
  const empty =
    mode.kind === "pinned"
      ? "No pinned messages"
      : mode.kind === "search"
        ? "No matches"
        : group
          ? `Say hi to ${name}. Only its members can read what you write here.`
          : remote
            ? `Say hi to ${name}. Messages reach them when they're online.`
            : "Notes to self: jot anything down. Turn a message into a todo with ☐.";

  return (
    <>
      <div className="chat-bar chat-filters">
        {searchOpen ? (
          <input
            type="search"
            autoFocus
            className="chat-search"
            placeholder="Search this chat…"
            aria-label="Search messages"
            onChange={(e) => setMode(e.target.value.trim() ? { kind: "search", text: e.target.value } : { kind: "all" })}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.stopPropagation();
                closeSearch();
              }
            }}
          />
        ) : (
          <>
            <button className={mode.kind === "all" ? "chip-btn on" : "chip-btn"} onClick={() => setMode({ kind: "all" })}>
              All
            </button>
            <button className={mode.kind === "pinned" ? "chip-btn on" : "chip-btn"} onClick={() => setMode({ kind: "pinned" })}>
              📌 Pinned
            </button>
            {conversation.room === "dm" && (
              <span className="chat-peer" title={conversation.peerDevice ?? ""}>
                {peerOnline ? "🟢 online" : "⚪ offline"} · {conversation.peerDevice?.slice(0, 8)}
              </span>
            )}
            {conversation.room === "team" && members !== null && (
              <span className="chat-peer">
                {members} member{members === 1 ? "" : "s"}
              </span>
            )}
            {conversation.room === "ip" && <span className="chat-peer">{conversation.peerIp} · old server</span>}
            {remote && conversation.room !== "ip" && (
              <button
                className="mini chat-reaction"
                title="How your pet reacts when they message you"
                onClick={() => setPickingReaction(true)}
              >
                🐾 {reactionLabel(conversation.reaction)} · Change
              </button>
            )}
          </>
        )}
        <button
          className="mini chat-search-toggle"
          title={searchOpen ? "Close search (Esc)" : "Search"}
          aria-label={searchOpen ? "Close search" : "Search messages"}
          onClick={() => (searchOpen ? closeSearch() : setSearchOpen(true))}
        >
          {searchOpen ? "×" : "🔍"}
        </button>
      </div>

      <div
        className="chat-scroll"
        ref={scroller}
        onScroll={(e) => {
          if (e.currentTarget.scrollTop < 40) loadOlder();
        }}
      >
        {hasMore && (
          <button className="link chat-older" onClick={loadOlder}>
            Load older messages
          </button>
        )}
        {messages.length === 0 && <p className="empty chat-empty">{empty}</p>}
        {messages.map((m, i) => {
          const newDay = i === 0 || isoDate(new Date(messages[i - 1].createdAt)) !== isoDate(new Date(m.createdAt));
          const theirs = m.senderIp !== null;
          return (
            <div key={m.id}>
              {newDay && <div className="chat-day">{dayLabel(m.createdAt)}</div>}
              <div className={["chat-msg", theirs && "theirs", m.pinned && "pinned", m.state === "failed" && "failed"].filter(Boolean).join(" ")}>
                {editing?.id === m.id ? (
                  <div className="chat-edit">
                    <textarea
                      autoFocus
                      value={editing.body}
                      rows={Math.min(8, editing.body.split("\n").length + 1)}
                      onChange={(e) => setEditing({ id: m.id, body: e.target.value })}
                      onKeyDown={editKey}
                      aria-label="Edit message"
                    />
                    <div className="chat-edit-actions">
                      <button className="mini" onClick={() => setEditing(null)}>
                        Cancel
                      </button>
                      <button className="mini primary" onClick={saveEdit}>
                        Save
                      </button>
                    </div>
                  </div>
                ) : remote && m.body === POKE ? (
                  <div className="chat-body chat-poke">👉 {pokeLine(m, theirs)}</div>
                ) : (
                  <>
                    {theirs && group && <div className="chat-sender">{m.senderName || m.senderIp?.slice(0, 8)}</div>}
                    <div className="chat-body">{m.body}</div>
                  </>
                )}
                <div className="chat-meta">
                  {m.pinned && <span title="Pinned">📌</span>}
                  {m.todoId !== null && (
                    <span className={m.todoStatus === "done" ? "chip chat-todo done" : "chip chat-todo"} title="Made into a todo">
                      {m.todoStatus === "done" ? "☑ todo done" : "☐ todo"}
                    </span>
                  )}
                  {!theirs && m.state === "pending" && <span title="Waiting for the chat server">⏳ sending</span>}
                  {!theirs && m.state === "failed" && (
                    <button className="link chat-retry" onClick={() => void run(async () => replace(await ipc.chatRetry(m.id)))}>
                      ⚠ not sent · retry
                    </button>
                  )}
                  <span className="chat-time" title={new Date(m.createdAt).toLocaleString()}>
                    {timeOf(m.createdAt)}
                    {m.editedAt !== null && " · edited"}
                  </span>
                  {editing?.id !== m.id && (
                    <span className="chat-actions">
                      <button className="mini" title={m.pinned ? "Unpin" : "Pin"} aria-label={m.pinned ? "Unpin" : "Pin"} onClick={() => togglePin(m)}>
                        📌
                      </button>
                      {m.todoId === null && (
                        <button className="mini" title="Make a todo (first line, quick-add syntax)" aria-label="Make a todo" onClick={() => makeTodo(m)}>
                          ☐
                        </button>
                      )}
                      {!remote && (
                        <button className="mini" title="Edit" aria-label="Edit" onClick={() => setEditing({ id: m.id, body: m.body })}>
                          ✎
                        </button>
                      )}
                      <button
                        className={confirmDelete === m.id ? "mini danger" : "mini"}
                        title={confirmDelete === m.id ? "Click again to delete" : remote ? "Delete (only here)" : "Delete"}
                        aria-label="Delete"
                        onClick={() => remove(m)}
                      >
                        {confirmDelete === m.id ? "Delete?" : "🗑"}
                      </button>
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {conversation.readOnly ? (
        <div className="chat-readonly">{conversation.readOnly}</div>
      ) : (
        <form
          className="chat-composer"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <textarea
            value={draft}
            rows={Math.min(6, draft.split("\n").length)}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={composerKey}
            placeholder={
              remote ? `Message ${name}…  (Shift+Enter: new line)` : "Message to self…  (Shift+Enter: new line; passwords go in the Vault)"
            }
            aria-label="Message"
          />
          {canPoke && (
            <button
              type="button"
              className="add-btn chat-poke-btn"
              title={pokeWait ? "Poked! Wait a moment" : group ? "Poke everyone here: their pets react" : `Poke ${name}: their pet reacts`}
              aria-label={group ? "Poke everyone" : `Poke ${name}`}
              disabled={pokeWait}
              onClick={poke}
            >
              👉
            </button>
          )}
          <button type="submit" className="add-btn" title="Send (Enter)" aria-label="Send" disabled={!draft.trim()}>
            ➤
          </button>
        </form>
      )}

      {pickingReaction && (
        <ReactionPicker
          name={name}
          current={conversation.reaction}
          onError={onError}
          onCancel={() => setPickingReaction(false)}
          onPick={(reaction) =>
            void run(async () => {
              await ipc.chatSetReaction(conv, reaction);
              setPickingReaction(false);
              onConversationChanged();
            })
          }
        />
      )}
    </>
  );
}
