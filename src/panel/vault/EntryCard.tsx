import { useEffect, useRef, useState } from "react";
import { ipc, type VaultEntry } from "../../lib/ipc";
import { kindInfo, sshCommand, subtitle } from "../../lib/vault";

const REVEAL_MS = 15_000;

interface Props {
  entry: VaultEntry;
  onOpen: () => void;
  notify: (msg: string) => void;
  onError: (msg: string) => void;
}

export function EntryCard({ entry: e, onOpen, notify, onError }: Props) {
  const info = kindInfo(e.kind);
  const sub = subtitle(e);

  const copy = (text: string, what: string) =>
    ipc.copyText(text).then(
      () => notify(`${what} copied`),
      (err) => onError(String(err)),
    );

  return (
    <article className="entry">
      <button className="entry-main" onClick={onOpen} title="Edit">
        <span className="entry-icon" aria-hidden>
          {info.icon}
        </span>
        <span className="entry-text">
          <span className="entry-title">{e.title}</span>
          {sub && <span className="entry-sub">{sub}</span>}
        </span>
        <span className="entry-kind">{info.label}</span>
      </button>

      {e.kind === "command" && e.body && (
        <div className="entry-row">
          <code className="snippet">{e.body}</code>
          <button className="mini" onClick={() => void copy(e.body, "Command")}>
            Copy
          </button>
        </div>
      )}
      {e.kind === "vm" && (
        <div className="entry-row">
          <code className="snippet">{sshCommand(e.fields)}</code>
          <button className="mini" onClick={() => void copy(sshCommand(e.fields), "SSH command")}>
            Copy ssh
          </button>
        </div>
      )}
      {e.hasSecret && <SecretRow id={e.id} notify={notify} onError={onError} />}
      {e.fields.extra?.map((f, i) => (
        <div className="entry-row" key={i}>
          <span className="extra-label" title={f.label}>
            {f.label || "—"}
          </span>
          <code className="snippet">{f.value}</code>
          <button className="mini" onClick={() => void copy(f.value, f.label || "Value")}>
            Copy
          </button>
        </div>
      ))}
      {e.kind !== "command" && e.body && <Notes text={e.body} />}
      {e.tags.length > 0 && (
        <div className="entry-tags">
          {e.tags.map((t) => (
            <span key={t} className="chip">
              #{t}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

/** Notes preview: three lines, click to expand. */
function Notes({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <p className={open ? "entry-notes open" : "entry-notes"} onClick={() => setOpen((v) => !v)} title={open ? "Collapse" : "Show all"}>
      {text}
    </p>
  );
}

/** Masked by default; reveal fetches the secret on demand and re-masks after 15 s. */
function SecretRow({ id, notify, onError }: { id: number; notify: (m: string) => void; onError: (m: string) => void }) {
  const [value, setValue] = useState<string | null>(null);
  const timer = useRef<number>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  const toggle = async () => {
    if (value !== null) {
      setValue(null);
      return;
    }
    try {
      setValue((await ipc.vaultRevealSecret(id)) ?? "");
      clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setValue(null), REVEAL_MS);
    } catch (err) {
      onError(String(err));
    }
  };

  const copy = () =>
    ipc.vaultCopySecret(id).then(
      () => notify("Secret copied — clipboard clears in 30 s"),
      (err) => onError(String(err)),
    );

  return (
    <div className="entry-row">
      <code className={value === null ? "snippet masked" : "snippet"} onClick={() => void toggle()} title={value === null ? "Click to reveal" : "Click to hide"}>
        {value === null ? "••••••••••••" : value}
      </code>
      <button className="mini" onClick={() => void toggle()} aria-label={value === null ? "Reveal secret" : "Hide secret"}>
        {value === null ? "Show" : "Hide"}
      </button>
      <button className="mini" onClick={() => void copy()}>
        Copy
      </button>
    </div>
  );
}
