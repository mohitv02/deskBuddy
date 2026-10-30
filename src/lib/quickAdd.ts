// Quick-add syntax: "Pay rent #home !high @tomorrow 09:00"
//   #project            project/tag
//   !1..!3, !low/!med/!high   priority
//   @today @tomorrow @mon..@sun @YYYY-MM-DD   due date
//   HH:MM sets the time
//   without a date the todo is due today
import { addDays, isoDate } from "./dates";
import type { TodoInput } from "./ipc";

const PRIORITY: Record<string, number> = { "1": 1, low: 1, "2": 2, med: 2, medium: 2, "3": 3, high: 3 };
const WEEKDAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

function parseDate(word: string, now: Date): string | null {
  const w = word.toLowerCase();
  if (w === "today") return isoDate(now);
  if (w === "tomorrow" || w === "tmr") return isoDate(addDays(now, 1));
  const wd = WEEKDAYS.indexOf(w.slice(0, 3));
  if (wd >= 0 && WEEKDAYS.some((d) => w.startsWith(d))) {
    const delta = (wd - now.getDay() + 7) % 7 || 7; // next occurrence, never today
    return isoDate(addDays(now, delta));
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(w)) return w;
  return null;
}

export function parseQuickAdd(text: string, now = new Date()): TodoInput {
  const words = text.trim().split(/\s+/);
  const title: string[] = [];
  let project = "";
  let priority = 0;
  let date: string | null = null;
  let time: string | null = null;

  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    if (/^#\S+/.test(w)) project = w.slice(1);
    else if (/^!\S+/.test(w) && PRIORITY[w.slice(1).toLowerCase()] !== undefined) priority = PRIORITY[w.slice(1).toLowerCase()];
    else if (/^@\S+/.test(w) && parseDate(w.slice(1), now)) {
      date = parseDate(w.slice(1), now);
      const next = words[i + 1];
      if (next && /^([01]?\d|2[0-3]):[0-5]\d$/.test(next)) {
        time = next.padStart(5, "0");
        i++;
      }
    } else if (/^([01]?\d|2[0-3]):[0-5]\d$/.test(w)) time = w.padStart(5, "0");
    else title.push(w);
  }
  return {
    title: title.join(" "),
    project,
    priority,
    due: time ? `${date ?? isoDate(now)}T${time}` : (date ?? isoDate(now)),
  };
}
