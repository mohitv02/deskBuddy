import { useCallback, useEffect, useMemo, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { ipc, type AlarmInfo, type Todo, type TodoInput } from "../../lib/ipc";
import { isDueTodayOrEarlier, isSameLocalDay } from "../../lib/dates";
import { parseQuickAdd } from "../../lib/quickAdd";
import { TodoEditor } from "./TodoEditor";
import { TodoSection } from "./TodoSection";

type Editing = { mode: "create"; draft: TodoInput } | { mode: "edit"; todo: Todo } | null;

/** Re-render once a minute so "overdue" and "today" stay accurate. */
function useMinuteClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export function TodoView({ onEditingChange }: { onEditingChange: (open: boolean) => void }) {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [quick, setQuick] = useState("");
  const [editing, setEditing] = useState<Editing>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCompleted, setShowCompleted] = useState(false);
  const [ringing, setRinging] = useState<AlarmInfo | null>(null);
  const now = useMinuteClock();

  const run = useCallback(async (op: () => Promise<unknown>): Promise<boolean> => {
    try {
      setError(null);
      await op();
      setTodos(await ipc.listTodos());
      return true;
    } catch (e) {
      setError(String(e));
      return false;
    }
  }, []);

  useEffect(() => {
    void run(async () => {});
    void ipc.alarmCurrent().then(setRinging);
    // The backend changes todos too (alarm Done/Snooze from the notification).
    const subs = [
      listen("todos-changed", () => void run(async () => {})),
      listen<AlarmInfo>("alarm", (e) => {
        setRinging(e.payload);
        void run(async () => {}); // its bell icon disappears once it has rung
      }),
      listen("alarm-stopped", () => setRinging(null)),
    ];
    return () => subs.forEach((p) => void p.then((off) => off()));
  }, [run]);

  useEffect(() => {
    onEditingChange(editing !== null);
  }, [editing, onEditingChange]);

  const sections = useMemo(() => {
    const today: Todo[] = [];
    const pending: Todo[] = [];
    const doneToday: Todo[] = [];
    const completed: Todo[] = [];
    for (const t of todos) {
      if (t.status === "done") {
        (t.completedAt && isSameLocalDay(t.completedAt, now) ? doneToday : completed).push(t);
      } else if (isDueTodayOrEarlier(t.due, now)) today.push(t);
      else pending.push(t);
    }
    completed.sort((a, b) => (b.completedAt ?? 0) - (a.completedAt ?? 0));
    return { today, pending, doneToday, completed };
  }, [todos, now]);

  const quickAdd = () => {
    const input = parseQuickAdd(quick);
    if (!input.title) {
      // "+" with nothing typed opens the full form.
      setEditing({ mode: "create", draft: input });
      return;
    }
    void run(async () => {
      await ipc.createTodo(input);
      setQuick("");
    });
  };

  const toggleDone = (t: Todo) => void run(() => ipc.setTodoStatus(t.id, t.status === "done" ? "open" : "done"));

  /** Reorder inside one section while keeping every other todo's slot. */
  const reorderSection = (sectionIds: number[]) => {
    const inSection = new Set(sectionIds);
    const queue = [...sectionIds];
    const ids = todos.map((t) => (inSection.has(t.id) ? queue.shift()! : t.id));
    const byId = new Map(todos.map((t) => [t.id, t]));
    setTodos(ids.map((id) => byId.get(id)!)); // optimistic
    void run(() => ipc.reorderTodos(ids));
  };

  const save = (input: TodoInput) =>
    run(async () => {
      if (editing?.mode === "edit") await ipc.updateTodo(editing.todo.id, input);
      else await ipc.createTodo(input);
      setEditing(null);
    });

  const remove = (t: Todo) =>
    void run(async () => {
      await ipc.deleteTodo(t.id);
      setEditing(null);
    });

  const itemProps = { now, onToggle: toggleDone, onOpen: (t: Todo) => setEditing({ mode: "edit", todo: t }), onReorder: reorderSection };

  return (
    <div className="todo-view">
      <form
        className="quick-add"
        onSubmit={(e) => {
          e.preventDefault();
          quickAdd();
        }}
      >
        <input
          autoFocus
          value={quick}
          onChange={(e) => setQuick(e.target.value)}
          placeholder="Add a todo…  #project !high @tomorrow 09:00"
          aria-label="Quick add todo"
        />
        <button type="submit" className="add-btn" title="Add (Enter). Empty: open full form" aria-label="Add todo">
          +
        </button>
      </form>
      {error && (
        <div className="error" role="alert" onClick={() => setError(null)}>
          {error}
        </div>
      )}
      {ringing && (
        <div className="alarm-banner" role="alert">
          <span className="alarm-bell">⏰</span>
          <span className="alarm-title">{ringing.title}</span>
          <button onClick={() => void run(() => ipc.alarmComplete(ringing.todoId))}>Done</button>
          <button onClick={() => void run(() => ipc.alarmSnooze(ringing.todoId))}>Snooze 10m</button>
          <button onClick={() => void ipc.alarmStop()}>Stop</button>
        </div>
      )}

      <div className="todo-scroll">
        <TodoSection
          title="Today"
          hint="due today or overdue"
          todos={sections.today}
          trailing={sections.doneToday}
          empty={sections.doneToday.length ? "All done for today 🎉" : "Nothing due today"}
          {...itemProps}
        />
        <TodoSection title="Pending" hint="all other incomplete" todos={sections.pending} empty="No pending todos" {...itemProps} />
        {sections.completed.length > 0 && (
          <section className="todo-section">
            <button className="section-toggle" onClick={() => setShowCompleted((v) => !v)}>
              {showCompleted ? "▾" : "▸"} Completed <span className="count">{sections.completed.length}</span>
            </button>
            {showCompleted && <TodoSection todos={sections.completed.slice(0, 50)} {...itemProps} />}
          </section>
        )}
      </div>

      {editing && (
        <TodoEditor
          key={editing.mode === "edit" ? editing.todo.id : "new"}
          initial={editing.mode === "edit" ? editing.todo : editing.draft}
          isNew={editing.mode === "create"}
          onSave={save}
          onDelete={editing.mode === "edit" ? () => remove(editing.todo) : undefined}
          onTestAlarm={editing.mode === "edit" ? () => void run(() => ipc.alarmTest(editing.todo.id)) : undefined}
          onCancel={() => setEditing(null)}
        />
      )}
    </div>
  );
}
