import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { ipc, type ChatStatus, type PetList, type Settings, type SettingsInfo } from "../../lib/ipc";
import { accelerator, formatAccelerator } from "../../lib/hotkey";
import { PetPicker } from "./PetPicker";

const AUTO_LOCK = [
  [1, "1 minute"],
  [2, "2 minutes"],
  [5, "5 minutes"],
  [10, "10 minutes"],
  [15, "15 minutes"],
  [30, "30 minutes"],
  [60, "1 hour"],
  [0, "Never"],
] as const;

const SLEEP_AFTER = [
  [20, "20 seconds"],
  [60, "1 minute"],
  [120, "2 minutes"],
  [300, "5 minutes"],
  [0, "Never"],
] as const;

const EFFECTS = [
  ["auto", "Automatic (sprite's choice, else sparks)"],
  ["sparks", "⚡ Sparks"],
  ["flames", "🔥 Flames"],
  ["webs", "🕸️ Webs"],
  ["shuriken", "✴️ Shuriken"],
  ["none", "None"],
] as const;

export function SettingsView() {
  const [info, setInfo] = useState<SettingsInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [recording, setRecording] = useState(false);
  const [pets, setPets] = useState<PetList | null>(null);
  const [page, setPage] = useState<"main" | "pets">("main");
  const [chat, setChat] = useState<ChatStatus | null>(null);

  useEffect(() => {
    void ipc.chatStatus().then(setChat);
    const sub = listen<ChatStatus>("chat-status", (e) => setChat(e.payload));
    return () => void sub.then((off) => off());
  }, []);

  useEffect(() => {
    void ipc.settingsInfo().then(setInfo);
    void ipc.listPets().then(setPets);
  }, []);

  const save = async (patch: Partial<Settings>) => {
    setError(null);
    try {
      const settings = await ipc.updateSettings(patch);
      setInfo((i) => (i ? { ...i, settings, hotkeyError: patch.hotkey !== undefined ? null : i.hotkeyError } : i));
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1200);
      return true;
    } catch (e) {
      setError(String(e));
      return false;
    }
  };

  // Capture the next key combination for the global shortcut.
  useEffect(() => {
    if (!recording) return;
    const onKey = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.key === "Escape") return setRecording(false);
      const accel = accelerator(e);
      if (!accel) return; // only modifiers so far
      setRecording(false);
      void save({ hotkey: accel });
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [recording]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!info) return <main className="placeholder">…</main>;
  const s = info.settings;
  const activePet = pets?.pets.find((p) => p.id === pets.active);

  if (page === "pets" && pets) {
    return (
      <div className="settings">
        {error && (
          <div className="error" role="alert" onClick={() => setError(null)}>
            {error}
          </div>
        )}
        <PetPicker
          list={pets}
          animationEnabled={s.animationEnabled}
          onBack={() => setPage("main")}
          onError={setError}
          onPick={async (id) => {
            if (await save({ pet: id })) setPets((l) => (l ? { ...l, active: id } : l));
          }}
        />
      </div>
    );
  }

  return (
    <div className="settings">
      {error && (
        <div className="error" role="alert" onClick={() => setError(null)}>
          {error}
        </div>
      )}
      {saved && <div className="saved">Saved ✓</div>}

      <section>
        <h2>General</h2>
        <label className="setting">
          <span>
            Start on login
            <small>Adds ~/.config/autostart/deskbuddy.desktop</small>
          </span>
          <input type="checkbox" className="switch" checked={s.autostart} onChange={(e) => void save({ autostart: e.target.checked })} />
        </label>
        <div className="setting">
          <span>
            Show/hide panel shortcut
            <small>{info.hotkeyError ?? "Works from any app. Shortcuts Ubuntu already uses are refused."}</small>
          </span>
          <span className="hotkey">
            <button className={recording ? "kbd recording" : "kbd"} onClick={() => setRecording((r) => !r)}>
              {recording ? "Press keys… (Esc cancels)" : s.hotkey ? formatAccelerator(s.hotkey) : "Off"}
            </button>
            {s.hotkey && !recording && (
              <button className="link" onClick={() => void save({ hotkey: "" })}>
                off
              </button>
            )}
          </span>
        </div>
      </section>

      <section>
        <h2>Mascot</h2>
        <div className="setting">
          <span>
            Pet
            <small>{activePet ? activePet.name : "…"} · choose who lives on your desk and what it does when</small>
          </span>
          <button className="mini" disabled={!pets} onClick={() => setPage("pets")}>
            Change ›
          </button>
        </div>
        <label className="setting">
          <span>
            Size <small>{s.iconSize} px</small>
          </span>
          <input
            type="range"
            min={48}
            max={256}
            step={8}
            defaultValue={s.iconSize}
            onMouseUp={(e) => void save({ iconSize: Number((e.target as HTMLInputElement).value) })}
            onKeyUp={(e) => void save({ iconSize: Number((e.target as HTMLInputElement).value) })}
          />
        </label>
        <label className="setting">
          <span>
            Animation
            <small>Also in the mascot's right-click menu</small>
          </span>
          <input type="checkbox" className="switch" checked={s.animationEnabled} onChange={(e) => void save({ animationEnabled: e.target.checked })} />
        </label>
        <label className="setting">
          <span>
            Sleep after
            <small>With no hover, click or todo change (pets that can sleep)</small>
          </span>
          <select value={s.sleepAfterSeconds} onChange={(e) => void save({ sleepAfterSeconds: Number(e.target.value) })}>
            {SLEEP_AFTER.map(([sec, label]) => (
              <option key={sec} value={sec}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <div className="setting">
          <span>
            Alarm effect
            <small>Plays around the mascot when an alarm rings</small>
          </span>
          <span className="hotkey">
            <select value={s.alarmEffect} onChange={(e) => void save({ alarmEffect: e.target.value })}>
              {EFFECTS.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
            <button className="mini" onClick={() => void ipc.previewEffect().catch((e) => setError(String(e)))}>
              Preview
            </button>
          </span>
        </div>
        <p className="setting-note">
          Custom character: put a sprite sheet + <code>sprite.json</code> in <code>{info.configDir}/mascot/</code>, or run{" "}
          <code>scripts/gif-to-sprite.py</code> on an animated GIF/WebP, then pick it under Pet.
        </p>
      </section>

      <section>
        <h2>Vault</h2>
        <label className="setting">
          <span>
            Auto-lock after
            <small>Without vault activity</small>
          </span>
          <select value={s.autoLockMinutes} onChange={(e) => void save({ autoLockMinutes: Number(e.target.value) })}>
            {AUTO_LOCK.map(([m, label]) => (
              <option key={m} value={m}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section>
        <h2>Chat</h2>
        <label className="setting">
          <span>
            Chat server
            <small>host or host:port of the DeskBuddy chat server (port 8787 if omitted). Empty: chat with others is off.</small>
          </span>
          <input
            className="setting-text"
            defaultValue={s.chatServer}
            placeholder="e.g. 192.168.1.10"
            onBlur={(e) => e.target.value.trim() !== s.chatServer && void save({ chatServer: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          />
        </label>
        <label className="setting">
          <span>
            Your name
            <small>What others see and can search for. Empty: your login name.</small>
          </span>
          <input
            className="setting-text"
            defaultValue={s.chatName}
            maxLength={40}
            placeholder="e.g. Mohit"
            onBlur={(e) => e.target.value.trim() !== s.chatName && void save({ chatName: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          />
        </label>
        <label className="setting">
          <span>
            Your IP address
            <small>
              {chat?.state === "online" && chat.me ? `Server sees you as ${chat.me.ip}. ` : ""}Empty: detected automatically. Set it if you have
              several networks.
            </small>
          </span>
          <input
            className="setting-text"
            defaultValue={s.chatIp}
            placeholder="Automatic"
            onBlur={(e) => e.target.value.trim() !== s.chatIp && void save({ chatIp: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          />
        </label>
        <p className="setting-note">
          {!chat || chat.state === "off"
            ? "Not connected."
            : chat.state === "online"
              ? `● Connected to ${chat.server}`
              : chat.state === "connecting"
                ? `Connecting to ${chat.server}…`
                : `○ Offline${chat.error ? `: ${chat.error}` : ""}. Retrying.`}
        </p>
      </section>

      <section className="about">
        <h2>About</h2>
        <p>
          DeskBuddy {info.version} · no telemetry; the only network connection is the chat server above, if set.
          <br />
          Data: <code>{info.dataDir}</code>
        </p>
      </section>
    </div>
  );
}
