import { useCallback, useEffect, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { ipc, type PanelView } from "../lib/ipc";
import { TodoView } from "./todos/TodoView";
import { ChatView } from "./chat/ChatView";
import { VaultGate } from "./vault/VaultGate";
import { SettingsView } from "./settings/SettingsView";

const TABS: { id: PanelView; label: string }[] = [
  { id: "todos", label: "Todos" },
  { id: "chat", label: "Chat" },
  { id: "vault", label: "Vault" },
  { id: "settings", label: "Settings" },
];

export function App() {
  const [view, setView] = useState<PanelView>("todos");
  const [pinned, setPinned] = useState(false);
  const pinnedRef = useRef(false);
  pinnedRef.current = pinned;
  const editorOpen = useRef(false);
  const setEditorOpen = useCallback((open: boolean) => {
    editorOpen.current = open;
    void ipc.setPanelEditing(open);
  }, []);

  const togglePin = () => {
    const next = !pinned;
    setPinned(next);
    void ipc.updateSettings({ panelPinned: next }).catch(() => setPinned(!next));
  };

  useEffect(() => {
    void ipc.getSettings().then((s) => setPinned(s.panelPinned));
    const unlisten = listen<PanelView>("navigate", (e) => setView(e.payload));
    const onKey = (e: KeyboardEvent) => {
      // Esc closes an open editor first (handled there), otherwise hides an
      // unpinned panel (a pinned one only closes with ×).
      if (e.key === "Escape" && !editorOpen.current && !pinnedRef.current) void ipc.hidePanel();
    };
    window.addEventListener("keydown", onKey);
    // A native <select> popup takes focus from the panel window (Linux), which
    // would otherwise auto-hide an unpinned panel. Flag it while it's open.
    let dropdown = false;
    const setDropdown = (open: boolean) => {
      if (dropdown === open) return;
      dropdown = open;
      void ipc.setPanelDropdown(open);
    };
    const onPointer = (e: MouseEvent) => setDropdown(e.target instanceof HTMLSelectElement);
    const onChange = (e: Event) => e.target instanceof HTMLSelectElement && setDropdown(false);
    const onFocus = () => setDropdown(false);
    window.addEventListener("mousedown", onPointer, true);
    window.addEventListener("change", onChange, true);
    window.addEventListener("focus", onFocus);
    return () => {
      void unlisten.then((f) => f());
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onPointer, true);
      window.removeEventListener("change", onChange, true);
      window.removeEventListener("focus", onFocus);
      setDropdown(false);
    };
  }, []);

  return (
    <div className="card">
      <header className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={t.id === view} className={t.id === view ? "active" : ""} onClick={() => setView(t.id)}>
            {t.label}
          </button>
        ))}
        <button
          className={pinned ? "pin pinned" : "pin"}
          title={pinned ? "Pinned: stays open until you press ×" : "Pin: keep open when clicking outside"}
          aria-label={pinned ? "Unpin panel" : "Pin panel"}
          aria-pressed={pinned}
          onClick={togglePin}
        >
          📌
        </button>
        <button className="close" title={pinned ? "Close" : "Hide (Esc)"} aria-label="Hide panel" onClick={() => void ipc.hidePanel()}>
          ×
        </button>
      </header>
      {view === "todos" && <TodoView onEditingChange={setEditorOpen} />}
      {view === "chat" && <ChatView onEditingChange={setEditorOpen} />}
      {view === "vault" && <VaultGate onEditingChange={setEditorOpen} />}
      {view === "settings" && <SettingsView />}
    </div>
  );
}
