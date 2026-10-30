import type { VaultEntry, VaultFields, VaultKind } from "./ipc";

export const KINDS: { id: VaultKind; label: string; icon: string; secretLabel: string }[] = [
  { id: "vm", label: "VM", icon: "🖥", secretLabel: "Password / passphrase (optional)" },
  { id: "password", label: "Password", icon: "🔑", secretLabel: "Password" },
  { id: "api_key", label: "API key", icon: "🧩", secretLabel: "API key" },
  { id: "command", label: "Command", icon: "⌘", secretLabel: "Secret (optional)" },
  { id: "note", label: "Note", icon: "📝", secretLabel: "Secret (optional)" },
];

export const kindInfo = (k: VaultKind) => KINDS.find((x) => x.id === k)!;

export const emptyFields = (): VaultFields => ({ host: "", user: "", port: null, keyPath: "", username: "", url: "", extra: [] });

/** POSIX shell quoting; keeps a leading "~/" unquoted so it still expands. */
export function shellQuote(s: string): string {
  if (/^[\w@%+=:,./~-]+$/.test(s)) return s;
  if (s.startsWith("~/")) return "~/" + shellQuote(s.slice(2));
  return `'${s.replace(/'/g, `'\\''`)}'`;
}

export function sshCommand(f: VaultFields): string {
  const parts = ["ssh"];
  if (f.keyPath) parts.push("-i", shellQuote(f.keyPath));
  if (f.port && f.port !== 22) parts.push("-p", String(f.port));
  parts.push(shellQuote(f.user ? `${f.user}@${f.host}` : f.host));
  return parts.join(" ");
}

/** One-line summary shown under the title. */
export function subtitle(e: VaultEntry): string {
  const f = e.fields;
  switch (e.kind) {
    case "vm":
      return `${f.user ? f.user + "@" : ""}${f.host}${f.port && f.port !== 22 ? ":" + f.port : ""}`;
    case "password":
    case "api_key":
      return [f.username, f.url].filter(Boolean).join(" · ");
    case "note":
    case "command":
      return "";
  }
}

/** Parse "a, b #c" into tags. */
export const parseTags = (s: string) => s.split(/[,\s]+/).map((t) => t.replace(/^#/, "").trim()).filter(Boolean);

export function generatePassword(length = 20): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*-_=+";
  const limit = 256 - (256 % alphabet.length); // reject to avoid modulo bias
  const out: string[] = [];
  while (out.length < length) {
    for (const b of crypto.getRandomValues(new Uint8Array(length * 2))) {
      if (b < limit && out.length < length) out.push(alphabet[b % alphabet.length]);
    }
  }
  return out.join("");
}
