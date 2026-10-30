import { useRef, useState } from "react";
import { useEscape } from "../useEscape";
import type { SecretChange, VaultEntry, VaultFields, VaultInput, VaultKind } from "../../lib/ipc";
import { KINDS, emptyFields, generatePassword, kindInfo, parseTags } from "../../lib/vault";

interface Props {
  entry: VaultEntry | null;
  defaultKind: VaultKind;
  /** Resolves true on success; on failure the sheet stays open for a retry. */
  onSave: (input: VaultInput) => Promise<boolean>;
  onDelete?: () => void;
  onCancel: () => void;
}

export function VaultEditor({ entry, defaultKind, onSave, onDelete, onCancel }: Props) {
  const [kind, setKind] = useState<VaultKind>(entry?.kind ?? defaultKind);
  const [title, setTitle] = useState(entry?.title ?? "");
  const [tags, setTags] = useState(entry?.tags.join(", ") ?? "");
  const [body, setBody] = useState(entry?.body ?? "");
  const [fields, setFields] = useState<VaultFields>(entry?.fields ?? emptyFields());
  // Existing secrets are kept unless the user explicitly changes or removes them.
  const [secretMode, setSecretMode] = useState<"keep" | "edit" | "clear">(entry?.hasSecret ? "keep" : "edit");
  const [secret, setSecret] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const set = <K extends keyof VaultFields>(k: K, v: VaultFields[K]) => setFields((f) => ({ ...f, [k]: v }));
  const valid = title.trim() !== "" && (kind !== "vm" || fields.host.trim() !== "");

  useEscape(onCancel);
  const submitted = useRef(false); // one save per sheet, even on key repeat
  const submit = () => {
    if (!valid || submitted.current) return;
    submitted.current = true;
    let change: SecretChange = { action: "keep" };
    if (secretMode === "clear") change = { action: "clear" };
    else if (secretMode === "edit") change = secret ? { action: "set", value: secret } : entry?.hasSecret ? { action: "clear" } : { action: "keep" };
    void onSave({ kind, title, tags: parseTags(tags), body, fields, secret: change }).then((ok) => {
      if (!ok) submitted.current = false;
    });
  };

  const field = (label: string, k: "host" | "user" | "keyPath" | "username" | "url", placeholder = "", required = false) => (
    <label>
      {label}
      <input value={fields[k]} placeholder={placeholder} required={required} onChange={(e) => set(k, e.target.value)} spellCheck={false} />
    </label>
  );

  const bodyLabel = kind === "command" ? "Command" : kind === "note" ? "Note" : "Notes";
  const extra = fields.extra ?? [];
  const setExtra = (i: number, key: "label" | "value", v: string) => set("extra", extra.map((f, j) => (j === i ? { ...f, [key]: v } : f)));

  return (
    <div
      className="sheet-backdrop"
      onMouseDown={(e) => e.target === e.currentTarget && onCancel()}
      onKeyDown={(e) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
          e.preventDefault(); // otherwise the form's implicit Enter-submit fires too
          submit();
        }
      }}
    >
      <form
        className="sheet"
        autoComplete="off"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <h3>{entry ? "Edit entry" : "New entry"}</h3>
        <div className="kind-picker" role="radiogroup" aria-label="Type">
          {KINDS.map((k) => (
            <button type="button" key={k.id} role="radio" aria-checked={kind === k.id} className={kind === k.id ? "chip-btn on" : "chip-btn"} onClick={() => setKind(k.id)}>
              {k.icon} {k.label}
            </button>
          ))}
        </div>
        <label>
          Title
          <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>

        {kind === "vm" && (
          <>
            <div className="row">
              {field("Host / IP", "host", "10.0.0.5", true)}
              <label className="narrow">
                Port
                <input
                  inputMode="numeric"
                  value={fields.port ?? ""}
                  placeholder="22"
                  onChange={(e) => {
                    const n = parseInt(e.target.value.replace(/\D/g, ""), 10);
                    set("port", Number.isFinite(n) && n > 0 && n <= 65535 ? n : null);
                  }}
                />
              </label>
            </div>
            <div className="row">
              {field("User", "user", "ubuntu")}
              {field("SSH key path", "keyPath", "~/.ssh/id_ed25519")}
            </div>
          </>
        )}
        {(kind === "password" || kind === "api_key") && (
          <div className="row">
            {field(kind === "password" ? "Username" : "Account", "username")}
            {field(kind === "password" ? "Website" : "Service / URL", "url")}
          </div>
        )}

        <label>
          {kindInfo(kind).secretLabel}
          {secretMode === "keep" ? (
            <span className="secret-saved">
              <span className="masked">•••••••• saved</span>
              <button type="button" className="link" onClick={() => setSecretMode("edit")}>
                change
              </button>
              <button type="button" className="link danger-text" onClick={() => setSecretMode("clear")}>
                remove
              </button>
            </span>
          ) : secretMode === "clear" ? (
            <span className="secret-saved">
              <span>Will be removed on save</span>
              <button type="button" className="link" onClick={() => setSecretMode("keep")}>
                undo
              </button>
            </span>
          ) : (
            <span className="secret-input">
              <input
                type={showSecret ? "text" : "password"}
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                spellCheck={false}
                autoComplete="new-password"
              />
              <button type="button" className="mini" onClick={() => setShowSecret((v) => !v)}>
                {showSecret ? "Hide" : "Show"}
              </button>
              {kind === "password" && (
                <button
                  type="button"
                  className="mini"
                  onClick={() => {
                    setSecret(generatePassword());
                    setShowSecret(true);
                  }}
                >
                  Generate
                </button>
              )}
            </span>
          )}
        </label>

        <label>
          {bodyLabel}
          <textarea
            rows={kind === "command" || kind === "note" ? 5 : 2}
            className={kind === "command" ? "mono" : ""}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            spellCheck={kind !== "command"}
          />
        </label>
        <div className="extra-fields">
          <span className="extra-head">Extra fields</span>
          {extra.map((f, i) => (
            <div className="extra-edit" key={i}>
              <input aria-label="Field name" placeholder="Name, e.g. Logs" value={f.label} onChange={(e) => setExtra(i, "label", e.target.value)} />
              <input aria-label="Field value" placeholder="/var/log/app" value={f.value} spellCheck={false} onChange={(e) => setExtra(i, "value", e.target.value)} />
              <button type="button" className="mini" aria-label="Remove field" onClick={() => set("extra", extra.filter((_, j) => j !== i))}>
                ×
              </button>
            </div>
          ))}
          <button type="button" className="link" onClick={() => set("extra", [...extra, { label: "", value: "" }])}>
            + Add field
          </button>
        </div>
        <label>
          Tags
          <input value={tags} placeholder="prod, db" onChange={(e) => setTags(e.target.value)} />
        </label>

        <div className="actions">
          {onDelete &&
            (confirmDelete ? (
              <button type="button" className="danger" onClick={onDelete}>
                Confirm delete
              </button>
            ) : (
              <button type="button" className="ghost danger-text" onClick={() => setConfirmDelete(true)}>
                Delete
              </button>
            ))}
          <span className="spacer" />
          <button type="button" className="ghost" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={!valid}>
            {entry ? "Save" : "Add"}
          </button>
        </div>
      </form>
    </div>
  );
}
