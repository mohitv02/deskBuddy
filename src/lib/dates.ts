// Local-time date helpers for todo due dates ("YYYY-MM-DD" or "YYYY-MM-DDTHH:MM").

const pad = (n: number) => String(n).padStart(2, "0");

export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

export function dueDate(due: string): string {
  return due.slice(0, 10);
}

export function dueTime(due: string): string | null {
  return due.length > 10 ? due.slice(11, 16) : null;
}

/** Past its date (or past its time, if it has one). */
export function isOverdue(due: string | null, now = new Date()): boolean {
  if (!due) return false;
  const today = isoDate(now);
  const date = dueDate(due);
  if (date !== today) return date < today;
  const time = dueTime(due);
  return time !== null && time < `${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

export function isDueTodayOrEarlier(due: string | null, now = new Date()): boolean {
  return !!due && dueDate(due) <= isoDate(now);
}

export function formatDue(due: string, now = new Date()): string {
  const date = dueDate(due);
  const time = dueTime(due);
  const today = isoDate(now);
  let label: string;
  if (date === today) label = "Today";
  else if (date === isoDate(addDays(now, 1))) label = "Tomorrow";
  else if (date === isoDate(addDays(now, -1))) label = "Yesterday";
  else {
    const d = new Date(`${date}T00:00`);
    const sameYear = d.getFullYear() === now.getFullYear();
    label = d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: sameYear ? undefined : "numeric" });
  }
  return time ? `${label} ${time}` : label;
}

export function isSameLocalDay(ms: number, now = new Date()): boolean {
  return isoDate(new Date(ms)) === isoDate(now);
}
