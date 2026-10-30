import { useCallback, useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { ipc, type VaultStatus } from "../../lib/ipc";
import { PasswordField, strength } from "./PasswordField";
import { SecuritySheet } from "./SecuritySheet";
import { VaultView } from "./VaultView";

/** Shows setup / unlock screens until the vault is open, then the vault itself. */
export function VaultGate({ onEditingChange }: { onEditingChange: (open: boolean) => void }) {
  const [status, setStatus] = useState<VaultStatus | null>(null);
  const [security, setSecurity] = useState(false);

  const refresh = useCallback(() => void ipc.vaultStatus().then(setStatus), []);

  useEffect(() => {
    refresh();
    const off = listen("vault-locked", () => {
      setSecurity(false);
      refresh();
    });
    return () => void off.then((f) => f());
  }, [refresh]);

  useEffect(() => {
    if (security) onEditingChange(true);
  }, [security, onEditingChange]);

  if (!status) return <main className="placeholder">…</main>;
  if (status.state === "not_set_up") return <SetupScreen legacy={status.legacyEntries} onDone={refresh} />;
  if (status.state === "locked") return <UnlockScreen onDone={refresh} />;
  return (
    <>
      <VaultView onEditingChange={onEditingChange} onLock={() => void ipc.vaultLock()} onSecurity={() => setSecurity(true)} onLocked={refresh} />
      {security && (
        <SecuritySheet
          autoLockMinutes={status.autoLockMinutes}
          onClose={() => {
            setSecurity(false);
            onEditingChange(false);
          }}
        />
      )}
    </>
  );
}

function SetupScreen({ legacy, onDone }: { legacy: number; onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const s = strength(pw);
  const ok = pw.length >= 8 && pw === confirm;

  const submit = async () => {
    if (!ok || busy) return;
    setBusy(true);
    setError(null);
    try {
      await ipc.vaultSetup(pw);
      setPw("");
      setConfirm("");
      onDone();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className="lock-screen"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <div className="lock-icon">🔐</div>
      <h3>Create your master password</h3>
      <p className="lock-text">
        It encrypts your whole vault (Argon2id + SQLCipher). <strong>It cannot be recovered</strong> — if you forget it, the vault is gone. Keep an
        encrypted backup.
      </p>
      {legacy > 0 && <p className="lock-note">{legacy} entries from the previous unencrypted version will be encrypted and the old file deleted.</p>}
      <PasswordField autoFocus label="Master password" value={pw} onChange={setPw} autoComplete="new-password" />
      {pw && (
        <div className={`strength s${s.score}`}>
          <span style={{ width: `${(s.score + 1) * 25}%` }} />
          <em>{s.label}</em>
        </div>
      )}
      <PasswordField label="Confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" />
      {confirm && pw !== confirm && <p className="lock-error">Passwords don't match</p>}
      {error && <p className="lock-error">{error}</p>}
      <button className="primary wide" disabled={!ok || busy}>
        {busy ? "Encrypting…" : "Create vault"}
      </button>
    </form>
  );
}

function UnlockScreen({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!pw || busy) return;
    setBusy(true);
    setError(null);
    try {
      await ipc.vaultUnlock(pw);
      onDone();
    } catch (e) {
      setError(String(e));
    } finally {
      setPw("");
      setBusy(false);
    }
  };

  return (
    <form
      className="lock-screen"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <div className="lock-icon">🔒</div>
      <h3>Vault locked</h3>
      <PasswordField autoFocus label="Master password" value={pw} onChange={setPw} autoComplete="current-password" />
      {error && <p className="lock-error">{error}</p>}
      <button className="primary wide" disabled={!pw || busy}>
        {busy ? "Unlocking…" : "Unlock"}
      </button>
    </form>
  );
}
