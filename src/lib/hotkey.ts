// Turn a keydown event into an accelerator string the global-shortcut plugin
// accepts ("Ctrl+Alt+D", "Super+Shift+F5"), or null while only modifiers are held.

const NAMED: Record<string, string> = {
  Space: "Space",
  Enter: "Enter",
  Tab: "Tab",
  Backspace: "Backspace",
  Delete: "Delete",
  Insert: "Insert",
  Home: "Home",
  End: "End",
  PageUp: "PageUp",
  PageDown: "PageDown",
  ArrowUp: "Up",
  ArrowDown: "Down",
  ArrowLeft: "Left",
  ArrowRight: "Right",
  Backquote: "`",
  Minus: "-",
  Equal: "=",
  BracketLeft: "[",
  BracketRight: "]",
  Semicolon: ";",
  Quote: "'",
  Comma: ",",
  Period: ".",
  Slash: "/",
  Backslash: "\\\\",
};

export function accelerator(e: KeyboardEvent): string | null {
  const code = e.code;
  let key: string | undefined;
  if (/^Key[A-Z]$/.test(code)) key = code.slice(3);
  else if (/^Digit\d$/.test(code)) key = code.slice(5);
  else if (/^F([1-9]|1[0-9]|2[0-4])$/.test(code)) key = code;
  else key = NAMED[code];
  if (!key) return null;
  const mods = [e.ctrlKey && "Ctrl", e.altKey && "Alt", e.shiftKey && "Shift", e.metaKey && "Super"].filter(Boolean) as string[];
  // A bare letter would hijack normal typing everywhere; require a modifier
  // (function keys may stand alone).
  if (mods.length === 0 && !/^F\d+$/.test(key)) return null;
  return [...mods, key].join("+");
}

export const formatAccelerator = (a: string) => a.split("+").join(" + ");
