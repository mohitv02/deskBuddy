import { useCallback, useEffect, useState } from "react";
import { ipc, type HostStatus } from "../../lib/ipc";

/** For the machine that runs the chat server: point it at a database. */
export function HostSection({ envPath, onError }: { envPath: string; onError: (e: string | null) => void }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<HostStatus | null>(null);
  const [path, setPath] = useState(envPath);
  const [uri, setUri] = useState("");
  const [database, setDatabase] = useState("");
  const [saved, setSaved] = useState(false);

  const refresh = useCallback(
    () =>
      void ipc
        .chatHostStatus()
        .then(setStatus)
        .catch(() => setStatus(null)),
    [],
  );

  useEffect(() => {
    if (!open) return;
    refresh();
    const t = window.setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [open, refresh]);

  const save = async () => {
    onError(null);
    try {
      await ipc.chatHostSave(path, uri, database);
      setUri("");
      setSaved(true);
      window.setTimeout(() => setSaved(false), 6000);
      refresh();
    } catch (e) {
      onError(String(e));
    }
  };

  const db = status?.server?.db;
  const serverLine = !status
    ? "…"
    : status.serverError
      ? `Server: not running on this machine (${status.serverError}). Start it with: sudo systemctl start deskbuddy-chat`
      : db?.state === "connected"
        ? `● Server running, database “${db.database}” connected${status.server?.home ? ` · cluster ${status.server.home.slice(0, 8)}` : ""}`
        : db?.state === "unconfigured"
          ? "Server running, waiting for a MongoDB URI."
          : db?.state === "connecting"
            ? "Server running, connecting to the database…"
            : `Server running, but the database isn't connected: ${db?.error ?? "unknown error"}`;

  return (
    <>
      <div className="setting">
        <span>
          Host a chat server on this machine
          <small>Only for the computer that runs the server: give it its MongoDB database.</small>
        </span>
        <button className="mini" onClick={() => setOpen((o) => !o)}>
          {open ? "Hide" : "Set up ›"}
        </button>
      </div>
      {open && (
        <div className="host-box">
          <label>
            Server's .env file
            <input
              className="setting-text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              onBlur={() => path.trim() !== envPath && void ipc.updateSettings({ chatHostEnv: path }).then(refresh)}
              placeholder="/home/you/deskbuddy/server/.env"
              spellCheck={false}
            />
          </label>
          <label>
            MongoDB URI
            <input
              className="setting-text"
              value={uri}
              onChange={(e) => setUri(e.target.value)}
              placeholder={status?.uri ?? "mongodb://127.0.0.1:27017/"}
              spellCheck={false}
              autoComplete="off"
            />
          </label>
          <label>
            Database name
            <input
              className="setting-text"
              value={database}
              onChange={(e) => setDatabase(e.target.value)}
              placeholder={status?.database ?? "deskbuddy_chat (one per team or community)"}
              spellCheck={false}
            />
          </label>
          <span className="team-actions">
            <button className="mini primary" disabled={!path.trim() || !uri.trim()} onClick={() => void save()}>
              Save and connect
            </button>
            {saved && <small>Saved. The server picks it up within 5 seconds.</small>}
          </span>
          <p className="setting-note">
            {status?.envExists === false && path ? "No .env there yet; saving creates it. " : ""}
            {status?.uri ? `Current URI: ${status.uri}. ` : ""}
            {status?.missingFile ? `⚠ ${status.missingFile} isn't on this machine. ` : ""}
          </p>
          <p className={db?.state === "connected" ? "setting-note ok" : "setting-note"}>{serverLine}</p>
        </div>
      )}
    </>
  );
}
