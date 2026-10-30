import { useRef, useState } from "react";
import type { Todo } from "../../lib/ipc";
import { formatDue, isOverdue } from "../../lib/dates";

const PRIORITY_LABEL = ["", "Low", "Medium", "High"];

interface Props {
  title?: string;
  hint?: string;
  todos: Todo[];
  /** Shown after the reorderable items (e.g. completed today). */
  trailing?: Todo[];
  empty?: string;
  now: Date;
  onToggle: (t: Todo) => void;
  onOpen: (t: Todo) => void;
  onReorder: (ids: number[]) => void;
}

export function TodoSection({ title, hint, todos, trailing = [], empty, now, onToggle, onOpen, onReorder }: Props) {
  const listRef = useRef<HTMLUListElement>(null);
  const [drag, setDrag] = useState<{ id: number; target: number } | null>(null);

  // Pointer-based reordering (HTML5 drag-and-drop is unreliable in WebKitGTK).
  const targetIndex = (clientY: number) => {
    const rows = Array.from(listRef.current?.querySelectorAll<HTMLElement>("li[data-reorder]") ?? []);
    const i = rows.findIndex((r) => {
      const b = r.getBoundingClientRect();
      return clientY < b.top + b.height / 2;
    });
    return i === -1 ? rows.length : i;
  };

  const startDrag = (e: React.PointerEvent, id: number) => {
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    setDrag({ id, target: todos.findIndex((t) => t.id === id) });
  };

  const finishDrag = () => {
    if (!drag) return;
    const ids = todos.map((t) => t.id).filter((id) => id !== drag.id);
    const from = todos.findIndex((t) => t.id === drag.id);
    const to = drag.target > from ? drag.target - 1 : drag.target;
    ids.splice(to, 0, drag.id);
    setDrag(null);
    if (to !== from) onReorder(ids);
  };

  const move = (t: Todo, delta: number) => {
    const ids = todos.map((x) => x.id);
    const i = ids.indexOf(t.id);
    const j = i + delta;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    onReorder(ids);
  };

  const row = (t: Todo, reorderable: boolean, index: number) => {
    const done = t.status === "done";
    const overdue = !done && isOverdue(t.due, now);
    const classes = ["todo", done && "done", overdue && "overdue", drag?.id === t.id && "dragging"].filter(Boolean).join(" ");
    return (
      <li key={t.id} className={classes} data-reorder={reorderable || undefined}>
        {reorderable && drag && drag.target === index && drag.id !== t.id && <div className="drop-line" />}
        {reorderable ? (
          <span
            className="handle"
            title="Drag to reorder (or Alt+↑/↓)"
            onPointerDown={(e) => startDrag(e, t.id)}
            onPointerMove={(e) => drag && setDrag({ ...drag, target: targetIndex(e.clientY) })}
            onPointerUp={finishDrag}
            onPointerCancel={() => setDrag(null)}
          >
            ⋮⋮
          </span>
        ) : (
          <span className="handle spacer" />
        )}
        <input type="checkbox" checked={done} onChange={() => onToggle(t)} aria-label={done ? "Mark as not done" : "Mark as done"} />
        <button
          className="todo-body"
          onClick={() => onOpen(t)}
          onKeyDown={(e) => {
            if (reorderable && e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
              e.preventDefault();
              move(t, e.key === "ArrowUp" ? -1 : 1);
            }
          }}
        >
          <span className="todo-title">{t.title}</span>
          {(t.due || t.project || t.priority > 0 || t.status === "in_progress" || t.notes) && (
            <span className="todo-meta">
              {t.priority > 0 && <span className={`prio p${t.priority}`}>{PRIORITY_LABEL[t.priority]}</span>}
              {t.status === "in_progress" && <span className="chip">In progress</span>}
              {t.due && (
                <span className={overdue ? "due overdue" : "due"}>
                  {t.remindAt && <span title="Alarm set">🔔 </span>}
                  {overdue ? "Overdue · " : ""}
                  {formatDue(t.due, now)}
                </span>
              )}
              {t.project && <span className="chip">#{t.project}</span>}
              {t.notes && <span className="notes-mark" title="Has notes">✎</span>}
            </span>
          )}
        </button>
      </li>
    );
  };

  const nothing = todos.length === 0 && trailing.length === 0;
  return (
    <section className="todo-section">
      {title && (
        <h2>
          {title} <span className="count">{todos.length}</span>
          {hint && <span className="hint">{hint}</span>}
        </h2>
      )}
      {nothing && empty ? (
        <p className="empty">{empty}</p>
      ) : (
        <ul ref={listRef}>
          {todos.map((t, i) => row(t, true, i))}
          {drag && drag.target === todos.length && <li className="drop-line end" />}
          {todos.length === 0 && empty && <p className="empty">{empty}</p>}
          {trailing.map((t, i) => row(t, false, i))}
        </ul>
      )}
    </section>
  );
}
