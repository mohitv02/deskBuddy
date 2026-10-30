import { useEffect, useState } from "react";
import { ipc, type PetInfo } from "../../lib/ipc";
import { clipLabel, GROUPS } from "../settings/PetPicker";

/** Pet states that make sense as a one-off reaction (held ones like idle,
 * alarm or sleep would not end on their own). */
const REACTABLE = [
  "doubleClick",
  "clicks",
  "done",
  "allDone",
  "added",
  "started",
  "deleted",
  "overdue",
  "hungry",
  "alarmClosed",
  "snooze",
  "dropped",
  "thrownLanded",
  "intro",
  "wakeUp",
];

const LABELS = new Map(GROUPS.flatMap(([, rows]) => rows.map(([state, label]) => [state, label] as const)));

export function reactionLabel(reaction: string): string {
  if (reaction === "") return "Default";
  if (reaction === "none") return "No reaction";
  return LABELS.get(reaction) ?? reaction;
}

/** Choose how the pet reacts when this person's message arrives. */
export function ReactionPicker({
  name,
  current,
  onPick,
  onCancel,
  onError,
}: {
  name: string;
  current: string;
  onPick: (reaction: string) => void;
  onCancel: () => void;
  onError: (e: string) => void;
}) {
  const [pet, setPet] = useState<PetInfo | null>(null);

  useEffect(() => {
    void ipc
      .listPets()
      .then((l) => setPet(l.pets.find((p) => p.id === l.active) ?? null))
      .catch((e) => onError(String(e)));
  }, [onError]);

  const preview = (reaction: string) => void ipc.previewPetState(`message:${reaction}`).catch((e) => onError(String(e)));
  const states = REACTABLE.filter((s) => (pet?.states[s]?.length ?? 0) > 0);

  const row = (reaction: string, label: string, hint: string) => (
    <div key={reaction || "default"} className={reaction === current ? "reaction-row on" : "reaction-row"}>
      <button className="reaction-pick" onClick={() => onPick(reaction)}>
        <span className="reaction-radio">{reaction === current ? "●" : "○"}</span>
        <span className="reaction-text">
          {label}
          {hint && <small>{hint}</small>}
        </span>
      </button>
      {reaction !== "none" && (
        <button className="mini" title="Play it on the pet" aria-label={`Preview ${label}`} onClick={() => preview(reaction)}>
          ▶
        </button>
      )}
    </div>
  );

  return (
    <div className="sheet-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onCancel()}>
      <div
        className="sheet"
        role="dialog"
        aria-label="Pet reaction"
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            onCancel();
          }
        }}
      >
        <h3>When {name} messages you</h3>
        <p className="reaction-note">
          Your pet{pet ? ` (${pet.name})` : ""} plays this reaction. ▶ previews it on the desktop.
        </p>
        <div className="reaction-list">
          {row("", "Default", "the same for everyone")}
          {states.map((s) => row(s, LABELS.get(s) ?? s, (pet?.states[s] ?? []).map(clipLabel).join(" · ")))}
          {row("none", "No reaction", "stay quiet for this person")}
        </div>
        {pet && states.length === 0 && <p className="reaction-note">This pet has a single reaction; pick another pet in Settings for more.</p>}
        <div className="actions">
          <span className="spacer" />
          <button className="ghost" onClick={onCancel}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
