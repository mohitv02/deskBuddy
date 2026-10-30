import { useRef, useState } from "react";
import { useEscape } from "../useEscape";
import type { TodoInput, TodoStatus } from "../../lib/ipc";
import { dueDate, dueTime, isoDate, isOverdue } from "../../lib/dates";

interface Props {
  initial: TodoInput;
  isNew: boolean;
  /** Resolves true on success; on failure the sheet stays open for a retry. */
  onSave: (input: TodoInput) => Promise<boolean>;
  onDelete?: () => void;
  onCancel: () => void;
  /** Ring this todo's alarm now (existing todos only). */
  onTestAlarm?: () => void;
}

export function TodoEditor({ initial, isNew, onSave, onDelete, onCancel, onTestAlarm }: Props) {
  const [title, setTitle] = useState(initial.title);
  const [notes, setNotes] = useState(initial.notes ?? "");
  const [date, setDate] = useState(initial.due ? dueDate(initial.due) : "");
  const [time, setTime] = useState(initial.due ? (dueTime(initial.due) ?? "") : "");
  const [priority, setPriority] = useState(initial.priority ?? 0);
  const [project, setProject] = useState(initial.project ?? "");
  const [status, setStatus] = useState<TodoStatus>(initial.status ?? "open");
  // Existing todos: on if an alarm is still pending, or for a new time.
  const [alarm, setAlarm] = useState(initial.alarm ?? ("remindAt" in initial ? initial.remindAt != null || !initial.due?.includes("T") : true));
  const [confirmDelete, setConfirmDelete] = useState(false);
  const timePassed = !!date && !!time && isOverdue(`${date}T${time}`);

  useEscape(onCancel);
  const submitted = useRef(false); // one save per sheet, even on key repeat
  const submit = () => {
    if (!title.trim() || submitted.current) return;
    submitted.current = true;
    void onSave({ title, notes, due: date ? (time ? `${date}T${time}` : date) : null, priority, project, status, alarm }).then((ok) => {
      if (!ok) submitted.current = false;
    });
  };

  return (
    <div
      className="sheet-backdrop"
      onMouseDown={(e) => e.target === e.currentTarget && onCancel()}
      onKeyDown={(e) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
          e.preventDefault(); // otherwise the form's implicit Enter-submit fires too
          submit();
        }
      }}
    >
      <form
        className="sheet"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <h3>{isNew ? "New todo" : "Edit todo"}</h3>
        <label>
          Title
          <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label>
          Notes
          <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
        <div className="row">
          <label>
            <span>
              Due date{" "}
              {date && (
                <button type="button" className="link" onClick={() => (setDate(""), setTime(""))}>
                  clear
                </button>
              )}
            </span>
            <input type="date" className={date ? "" : "unset"} value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <label>
            Time
            <input
              type="time"
              className={time ? "" : "unset"}
              value={time}
              onChange={(e) => {
                setTime(e.target.value);
                // A time on its own means today.
                if (e.target.value && !date) setDate(isoDate(new Date()));
              }}
            />
          </label>
        </div>
        <div className="alarm-row">
          <label className="check">
            <input type="checkbox" checked={alarm} onChange={(e) => setAlarm(e.target.checked)} />
            🔔 Ring at {time || "the due time"}
          </label>
          {alarm && !time && <span className="hint">pick a time above for the alarm to ring</span>}
          {alarm && timePassed && <span className="hint">that time has passed, so it won't ring</span>}
          {onTestAlarm && (
            <button type="button" className="link" onClick={onTestAlarm}>
              Test alarm now
            </button>
          )}
        </div>
        <div className="row">
          <label>
            Priority
            <select value={priority} onChange={(e) => setPriority(Number(e.target.value))}>
              <option value={0}>None</option>
              <option value={1}>Low</option>
              <option value={2}>Medium</option>
              <option value={3}>High</option>
            </select>
          </label>
          <label>
            Status
            <select value={status} onChange={(e) => setStatus(e.target.value as TodoStatus)}>
              <option value="open">Open</option>
              <option value="in_progress">In progress</option>
              <option value="done">Done</option>
            </select>
          </label>
        </div>
        <label>
          Project / tag
          <input value={project} placeholder="e.g. home" onChange={(e) => setProject(e.target.value)} />
        </label>
        <div className="actions">
          {onDelete &&
            (confirmDelete ? (
              <button type="button" className="danger" onClick={onDelete}>
                Confirm delete
              </button>
            ) : (
              <button type="button" className="ghost danger-text" onClick={() => setConfirmDelete(true)}>
                Delete
              </button>
            ))}
          <span className="spacer" />
          <button type="button" className="ghost" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={!title.trim()}>
            {isNew ? "Add" : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
