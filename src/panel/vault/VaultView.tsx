import { useCallback, useEffect, useRef, useState } from "react";
import { ipc, type VaultEntry, type VaultInput, type VaultKind } from "../../lib/ipc";
import { KINDS } from "../../lib/vault";
import { EntryCard } from "./EntryCard";
import { VaultEditor } from "./VaultEditor";

type Editing = { mode: "create" } | { mode: "edit"; entry: VaultEntry } | null;

interface Props {
  onEditingChange: (open: boolean) => void;
  onLock: () => void;
  onSecurity: () => void;
  /** A command failed because auto-lock closed the vault meanwhile. */
  onLocked: () => void;
}

export function VaultView({ onEditingChange, onLock, onSecurity, onLocked }: Props) {
  const [text, setText] = useState("");
  const [kind, setKind] = useState<VaultKind | null>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [results, setResults] = useState<VaultEntry[]>([]);
  const [allTags, setAllTags] = useState<{ tag: string; count: number }[]>([]);
  const [editing, setEditing] = useState<Editing>(null);
  const [error, setErrorRaw] = useState<string | null>(null);
  const setError = useCallback(
    (e: string | null) => {
      if (e?.includes("locked")) onLocked();
      else setErrorRaw(e);
    },
    [onLocked],
  );
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number>(undefined);
  const searchSeq = useRef(0);

  const notify = useCallback((msg: string) => {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2500);
  }, []);

  const refresh = useCallback(async () => {
    const seq = ++searchSeq.current;
    try {
      const [r, t] = await Promise.all([ipc.vaultSearch({ text, kind, tags }), ipc.vaultTags()]);
      if (seq !== searchSeq.current) return; // a newer search finished first
      setResults(r);
      setAllTags(t);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, [text, kind, tags, setError]);

  useEffect(() => {
    const t = window.setTimeout(() => void refresh(), 60); // light debounce while typing
    return () => clearTimeout(t);
  }, [refresh]);

  useEffect(() => {
    onEditingChange(editing !== null);
  }, [editing, onEditingChange]);

  const save = async (input: VaultInput): Promise<boolean> => {
    try {
      if (editing?.mode === "edit") await ipc.vaultUpdate(editing.entry.id, input);
      else await ipc.vaultCreate(input);
      setEditing(null);
      await refresh();
      return true;
    } catch (e) {
      setError(String(e));
      return false;
    }
  };

  const remove = async (entry: VaultEntry) => {
    try {
      await ipc.vaultDelete(entry.id);
      setEditing(null);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  };

  const toggleTag = (t: string) => setTags((cur) => (cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]));

  return (
    <div className="vault-view">
      <div className="quick-add">
        <input
          autoFocus
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Search everything…"
          aria-label="Search vault"
        />
        <button className="add-btn" title="New entry" aria-label="New vault entry" onClick={() => setEditing({ mode: "create" })}>
          +
        </button>
        <button className="icon-btn" title="Security: password, backups" aria-label="Vault security" onClick={onSecurity}>
          ⚙
        </button>
        <button className="icon-btn" title="Lock vault now" aria-label="Lock vault" onClick={onLock}>
          🔒
        </button>
      </div>
      <div className="filters">
        <button className={kind === null ? "chip-btn on" : "chip-btn"} onClick={() => setKind(null)}>
          All
        </button>
        {KINDS.map((k) => (
          <button key={k.id} className={kind === k.id ? "chip-btn on" : "chip-btn"} onClick={() => setKind(kind === k.id ? null : k.id)}>
            {k.icon} {k.label}
          </button>
        ))}
      </div>
      {allTags.length > 0 && (
        <div className="filters tags">
          {allTags.map(({ tag, count }) => (
            <button key={tag} className={tags.includes(tag) ? "chip-btn tag on" : "chip-btn tag"} onClick={() => toggleTag(tag)}>
              #{tag} <span className="count">{count}</span>
            </button>
          ))}
        </div>
      )}
      {error && (
        <div className="error" role="alert" onClick={() => setErrorRaw(null)}>
          {error}
        </div>
      )}
      <div className="todo-scroll vault-results">
        {results.length === 0 ? (
          <p className="empty">{text || kind || tags.length ? "No matches" : "Your vault is empty. Click + to add a VM, password, API key, command or note."}</p>
        ) : (
          results.map((e) => <EntryCard key={e.id} entry={e} onOpen={() => setEditing({ mode: "edit", entry: e })} notify={notify} onError={setError} />)
        )}
      </div>
      {toast && <div className="toast">{toast}</div>}
      {editing && (
        <VaultEditor
          key={editing.mode === "edit" ? editing.entry.id : "new"}
          entry={editing.mode === "edit" ? editing.entry : null}
          defaultKind={kind ?? "vm"}
          onSave={save}
          onDelete={editing.mode === "edit" ? () => remove(editing.entry) : undefined}
          onCancel={() => setEditing(null)}
        />
      )}
    </div>
  );
}
