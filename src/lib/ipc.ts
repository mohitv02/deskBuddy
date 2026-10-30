// Typed wrappers around Tauri commands so UI code never calls invoke() with raw strings.
import { invoke } from "@tauri-apps/api/core";

export interface Settings {
  iconSize: number;
  animationEnabled: boolean;
  autostart: boolean;
  hotkey: string;
  autoLockMinutes: number;
  alarmEffect: string;
  /** "classic", a bundled pack id, "custom", or "" (custom if present, else classic). */
  pet: string;
  /** Seconds with nothing happening before the pet dozes off (0 = never). */
  sleepAfterSeconds: number;
  /** Pinned: the panel stays open until closed with ×. */
  panelPinned: boolean;
  /** LAN chat server ("host", "host:port" or "ws://…"); "" = chat off. */
  chatServer: string;
  /** Name others see; "" = login name. */
  chatName: string;
  /** This machine's IP as others know it; "" = automatic. */
  chatIp: string;
}

export interface SettingsInfo {
  settings: Settings;
  hotkeyError: string | null;
  dataDir: string;
  configDir: string;
  version: string;
}

export type TodoStatus = "open" | "in_progress" | "done";

export interface Todo {
  id: number;
  title: string;
  notes: string;
  /** Local "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM". */
  due: string | null;
  /** 0 none, 1 low, 2 medium, 3 high. */
  priority: number;
  project: string;
  status: TodoStatus;
  position: number;
  createdAt: number;
  completedAt: number | null;
  /** When the alarm will ring (unix ms), if armed. */
  remindAt: number | null;
}

export interface TodoInput {
  title: string;
  notes?: string;
  due?: string | null;
  priority?: number;
  project?: string;
  status?: TodoStatus;
  /** Ring at the due time (needs a time). Default on. */
  alarm?: boolean;
}

export type VaultKind = "vm" | "password" | "api_key" | "command" | "note";

export interface VaultFields {
  host: string;
  user: string;
  port: number | null;
  keyPath: string;
  username: string;
  url: string;
  extra: { label: string; value: string }[];
}

export interface VaultEntry {
  id: number;
  kind: VaultKind;
  title: string;
  tags: string[];
  body: string;
  fields: VaultFields;
  hasSecret: boolean;
  createdAt: number;
  updatedAt: number;
}

export type SecretChange = { action: "keep" } | { action: "clear" } | { action: "set"; value: string };

export interface VaultInput {
  kind: VaultKind;
  title: string;
  tags: string[];
  body: string;
  fields: VaultFields;
  secret: SecretChange;
}

export interface VaultQuery {
  text: string;
  kind?: VaultKind | null;
  tags?: string[];
}

export interface SpriteAnimation {
  start: number;
  frames: number;
  fps: number;
  pauseMs: number;
}

export interface SpriteSheet {
  image: string;
  frameWidth: number;
  frameHeight: number;
  pixelated: boolean;
  animations: { idle: SpriteAnimation; happy: SpriteAnimation | null; alarm: SpriteAnimation | null };
  alarmEffect: string | null;
  effectOrigin: [number, number] | null;
}

export interface AlarmInfo {
  todoId: number;
  title: string;
  due: string | null;
}

export type CustomMascot =
  | { type: "image"; url: string }
  | { type: "sprite"; url: string; sheet: SpriteSheet }
  | {
      type: "svgStates";
      /** file name -> SVG markup */
      clips: Record<string, string>;
      /** state -> file names to pick from */
      states: Record<string, string[]>;
      idleVariants: string[];
      sleepAfterSeconds: number | null;
    };

export interface PetInfo {
  id: string;
  name: string;
  description: string;
  /** Idle SVG markup for the thumbnail; null for the built-in character. */
  preview: string | null;
  /** state -> clip names (one is picked at random each time) */
  states: Record<string, string[]>;
  idleVariants: string[];
  alarmEffect: string | null;
}

export interface PetList {
  /** The pet on screen. */
  active: string;
  pets: PetInfo[];
}

export interface VaultStatus {
  state: "not_set_up" | "locked" | "unlocked";
  legacyEntries: number;
  autoLockMinutes: number;
}

export interface BackupSummary {
  todos: number;
  vaultEntries: number;
}

export interface ChatMessage {
  id: number;
  conversationId: number;
  body: string;
  /** The todo made from this message, if it still exists. */
  todoId: number | null;
  todoStatus: TodoStatus | null;
  pinned: boolean;
  createdAt: number;
  editedAt: number | null;
  /** Sender's IP in a LAN chat; null when sent from here. */
  senderIp: string | null;
  /** Delivery of messages sent from here. */
  state: "pending" | "sent" | "failed";
  clientMsgId: string | null;
}

export interface Conversation {
  id: number;
  kind: "self" | "remote";
  title: string;
  peerIp: string | null;
  peerName: string;
  remoteId: string | null;
  lastSeq: number;
  updatedAt: number;
  lastBody: string | null;
  /** Pet reaction to their messages: "" default, "none", or a pet state. */
  reaction: string;
}

export interface ChatUser {
  ip: string;
  name: string;
  online: boolean;
  lastSeen: number;
}

export interface ChatStatus {
  state: "off" | "connecting" | "online" | "offline";
  server: string;
  /** Our IP and name as the server sees them, while online. */
  me: ChatUser | null;
  error: string | null;
  users: ChatUser[];
}

export type ChatOpenResult = { kind: "opened"; conversation: Conversation } | { kind: "choose"; users: ChatUser[] };

export type PanelView = "todos" | "chat" | "vault" | "settings";

export const ipc = {
  getSettings: () => invoke<Settings>("get_settings"),
  settingsInfo: () => invoke<SettingsInfo>("settings_info"),
  updateSettings: (patch: Partial<Settings>) => invoke<Settings>("update_settings", { patch }),
  previewEffect: () => invoke<void>("preview_effect"),
  setAnimationEnabled: (enabled: boolean) => invoke<void>("set_animation_enabled", { enabled }),
  isFullscreen: () => invoke<boolean>("is_fullscreen"),
  togglePanel: () => invoke<void>("toggle_panel"),
  showPanel: (view?: PanelView) => invoke<void>("show_panel", { view }),
  hidePanel: () => invoke<void>("hide_panel"),
  setPanelEditing: (open: boolean) => invoke<void>("set_panel_editing", { open }),
  quit: () => invoke<void>("quit_app"),
  customMascot: () => invoke<CustomMascot | null>("custom_mascot"),
  listPets: () => invoke<PetList>("list_pets"),
  /** Play a state (or "variant:<i>") on the mascot. */
  previewPetState: (state: string) => invoke<void>("preview_pet_state", { state }),
  copyText: (text: string, sensitive = false) => invoke<void>("copy_text", { text, sensitive }),

  listTodos: () => invoke<Todo[]>("list_todos"),
  createTodo: (input: TodoInput) => invoke<Todo>("create_todo", { input }),
  updateTodo: (id: number, input: TodoInput) => invoke<Todo>("update_todo", { id, input }),
  setTodoStatus: (id: number, status: TodoStatus) => invoke<Todo>("set_todo_status", { id, status }),
  deleteTodo: (id: number) => invoke<void>("delete_todo", { id }),
  reorderTodos: (ids: number[]) => invoke<void>("reorder_todos", { ids }),

  chatStatus: () => invoke<ChatStatus>("chat_status"),
  chatConversations: () => invoke<Conversation[]>("chat_conversations"),
  /** Start or reopen a chat with an IP address or a name. */
  chatOpen: (target: string) => invoke<ChatOpenResult>("chat_open", { target }),
  /** A page of messages, oldest first, older than `before` (newest page without it). */
  chatList: (conversation: number, before: number | null, limit: number) =>
    invoke<ChatMessage[]>("chat_list", { conversation, before, limit }),
  chatPinned: (conversation: number) => invoke<ChatMessage[]>("chat_pinned", { conversation }),
  chatSearch: (conversation: number, text: string) => invoke<ChatMessage[]>("chat_search", { conversation, text }),
  chatSend: (conversation: number, body: string) => invoke<ChatMessage>("chat_send", { conversation, body }),
  chatRetry: (id: number) => invoke<ChatMessage>("chat_retry", { id }),
  chatSetReaction: (conversation: number, reaction: string) =>
    invoke<Conversation>("chat_set_reaction", { conversation, reaction }),
  chatEdit: (id: number, body: string) => invoke<ChatMessage>("chat_edit", { id, body }),
  chatPin: (id: number, pinned: boolean) => invoke<ChatMessage>("chat_pin", { id, pinned }),
  chatDelete: (id: number) => invoke<void>("chat_delete", { id }),
  chatToTodo: (id: number, input: TodoInput) => invoke<ChatMessage>("chat_to_todo", { id, input }),

  alarmCurrent: () => invoke<AlarmInfo | null>("alarm_current"),
  alarmStop: () => invoke<void>("alarm_stop"),
  alarmSnooze: (id: number) => invoke<void>("alarm_snooze", { id }),
  alarmComplete: (id: number) => invoke<void>("alarm_complete", { id }),
  alarmTest: (id: number) => invoke<void>("alarm_test", { id }),

  vaultStatus: () => invoke<VaultStatus>("vault_status"),
  vaultSetup: (password: string) => invoke<void>("vault_setup", { password }),
  vaultUnlock: (password: string) => invoke<void>("vault_unlock", { password }),
  vaultLock: () => invoke<void>("vault_lock"),
  vaultChangePassword: (old: string, next: string) => invoke<void>("vault_change_password", { old, new: next }),
  backupExport: (password: string) => invoke<[string, BackupSummary] | null>("backup_export", { password }),
  backupImport: (password: string) => invoke<BackupSummary | null>("backup_import", { password }),

  vaultSearch: (query: VaultQuery) => invoke<VaultEntry[]>("vault_search", { query }),
  vaultCreate: (input: VaultInput) => invoke<VaultEntry>("vault_create", { input }),
  vaultUpdate: (id: number, input: VaultInput) => invoke<VaultEntry>("vault_update", { id, input }),
  vaultDelete: (id: number) => invoke<void>("vault_delete", { id }),
  vaultTags: () => invoke<{ tag: string; count: number }[]>("vault_tags"),
  vaultRevealSecret: (id: number) => invoke<string | null>("vault_reveal_secret", { id }),
  vaultCopySecret: (id: number) => invoke<void>("vault_copy_secret", { id }),
};
