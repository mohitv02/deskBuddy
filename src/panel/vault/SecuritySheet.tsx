import { useState } from "react";
import { ipc } from "../../lib/ipc";
import { useEscape } from "../useEscape";
import { PasswordField } from "./PasswordField";

type Busy = null | "password" | "export" | "import";

export function SecuritySheet({ autoLockMinutes, onClose }: { autoLockMinutes: number; onClose: () => void }) {
  const [busy, setBusy] = useState<Busy>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEscape(() => {
    if (!busy) onClose();
  });

  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [newPw2, setNewPw2] = useState("");
  const [exportPw, setExportPw] = useState("");
  const [exportPw2, setExportPw2] = useState("");
  const [importPw, setImportPw] = useState("");
  const [importConfirm, setImportConfirm] = useState(false);

  const run = async (kind: Exclude<Busy, null>, op: () => Promise<string | null>) => {
    setBusy(kind);
    setMsg(null);
    try {
      const text = await op();
      if (text) setMsg({ ok: true, text });
    } catch (e) {
      setMsg({ ok: false, text: String(e) });
    } finally {
      setBusy(null);
    }
  };

  const changePassword = () =>
    run("password", async () => {
      await ipc.vaultChangePassword(oldPw, newPw);
      setOldPw("");
      setNewPw("");
      setNewPw2("");
      return "Master password changed. The vault was re-encrypted.";
    });

  const exportBackup = () =>
    run("export", async () => {
      const r = await ipc.backupExport(exportPw);
      if (!r) return null; // cancelled
      setExportPw("");
      setExportPw2("");
      const [path, s] = r;
      return `Saved ${s.vaultEntries} vault entries and ${s.todos} todos to ${path}`;
    });

  const importBackup = () =>
    run("import", async () => {
      const s = await ipc.backupImport(importPw);
      if (!s) return null;
      setImportPw("");
      setImportConfirm(false);
      return `Restored ${s.vaultEntries} vault entries and ${s.todos} todos. Previous data kept as *.pre-import.`;
    });

  return (
    <div
      className="sheet-backdrop"
      onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}
    >
      <div className="sheet security">
        <h3>Vault security</h3>
        <p className="hint">
          Auto-locks after {autoLockMinutes > 0 ? `${autoLockMinutes} min` : "— (never)"} without vault activity. Copied secrets clear from the clipboard
          after 30 s.
        </p>
        {msg && <p className={msg.ok ? "notice ok" : "notice bad"}>{msg.text}</p>}

        <details open>
          <summary>Change master password</summary>
          <PasswordField label="Current password" value={oldPw} onChange={setOldPw} autoComplete="current-password" />
          <PasswordField label="New password" value={newPw} onChange={setNewPw} autoComplete="new-password" />
          <PasswordField label="Confirm new password" value={newPw2} onChange={setNewPw2} autoComplete="new-password" />
          <button className="primary" disabled={!oldPw || newPw.length < 8 || newPw !== newPw2 || busy !== null} onClick={() => void changePassword()}>
            {busy === "password" ? "Re-encrypting…" : "Change password"}
          </button>
        </details>

        <details>
          <summary>Export encrypted backup</summary>
          <p className="hint">One .dbkp file with your vault and todos, encrypted with this backup password (it can be the same as your master password).</p>
          <PasswordField label="Backup password" value={exportPw} onChange={setExportPw} autoComplete="new-password" />
          <PasswordField label="Confirm" value={exportPw2} onChange={setExportPw2} autoComplete="new-password" />
          <button className="primary" disabled={exportPw.length < 8 || exportPw !== exportPw2 || busy !== null} onClick={() => void exportBackup()}>
            {busy === "export" ? "Exporting…" : "Choose file & export"}
          </button>
        </details>

        <details>
          <summary>Import backup</summary>
          <p className="hint">
            <strong>Replaces</strong> all current vault entries and todos with the backup's. Your current data is kept beside it as <code>*.pre-import</code>.
          </p>
          <PasswordField label="Backup password" value={importPw} onChange={setImportPw} autoComplete="off" />
          <label className="check">
            <input type="checkbox" checked={importConfirm} onChange={(e) => setImportConfirm(e.target.checked)} />I understand this replaces my current data
          </label>
          <button className="danger" disabled={!importPw || !importConfirm || busy !== null} onClick={() => void importBackup()}>
            {busy === "import" ? "Importing…" : "Choose file & import"}
          </button>
        </details>

        <div className="actions">
          <span className="spacer" />
          <button className="ghost" disabled={busy !== null} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
