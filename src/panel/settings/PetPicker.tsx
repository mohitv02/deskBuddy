import { useEffect, useMemo, useRef, useState } from "react";
import { ipc, type PetInfo, type PetList } from "../../lib/ipc";

type Row = [state: string, label: string, hint: string];

/** Mapping rows, grouped, in the order things usually happen. */
export const GROUPS: [title: string, rows: Row[]][] = [
  [
    "Everyday",
    [
      ["intro", "Appears", "when DeskBuddy starts or the pet changes"],
      ["idle", "Idle", "most of the time"],
      ["hover", "Mouse over", "while the pointer rests on it"],
      ["doubleClick", "Double-click", ""],
      ["clicks", "Click spree", "three or more quick clicks"],
    ],
  ],
  [
    "Your todos",
    [
      ["added", "Todo added", ""],
      ["started", "Todo started", "set to in progress"],
      ["done", "Todo completed", ""],
      ["allDone", "All done", "the last open todo is completed"],
      ["deleted", "Todo deleted", ""],
      ["overdue", "Worried", "now and then while a todo is overdue"],
      ["hungry", "Hungry", "now and then around 12:00 and 19:00"],
    ],
  ],
  [
    "Alarms",
    [
      ["alarm", "Alarm ringing", "loops until stopped"],
      ["alarmClosed", "Alarm stopped", ""],
      ["snooze", "Alarm snoozed", ""],
    ],
  ],
  [
    "Carried around",
    [
      ["dragged", "Dragged", "while you move it"],
      ["falling", "Falling", "let go higher up: it drops back down a few inches"],
      ["dropped", "Lands", "when it's back on the ground"],
      ["thrown", "Thrown sideways", "flick it left or right as you let go: it tumbles along"],
      ["thrownLanded", "Lands, sideways", "after a sideways throw: it turns back to face you"],
      ["thrownUp", "Thrown up", "flick it up, straight or diagonally: it flies up and falls back"],
      ["thrownUpLanded", "Lands, from up high", "after an upward throw"],
      ["thrownDown", "Thrown down", "flick it down: it slams into the ground"],
      ["thrownDownLanded", "Lands, slammed", "after a downward throw"],
    ],
  ],
  [
    "Sleep",
    [
      ["fallAsleep", "Dozes off", "after a while with nothing happening (Sleep after)"],
      ["sleep", "Sleeping", ""],
      ["wakeUp", "Wakes up", "hover for 1.5 s, click, or a todo changes"],
    ],
  ],
];

/** Eyes follow the pointer while it's near: state, arrow, as a 3×3 grid. */
const LOOKS: [string, string][] = [
  ["lookUpLeft", "↖"],
  ["lookUp", "↑"],
  ["lookUpRight", "↗"],
  ["lookLeft", "←"],
  ["", ""], // the pet, in the middle
  ["lookRight", "→"],
  ["lookDownLeft", "↙"],
  ["lookDown", "↓"],
  ["lookDownRight", "↘"],
];

/** Where a state with no clip goes (mirrors svgstates.ts). */
const FALLBACK: Record<string, string[]> = {
  alarmClosed: ["hover"],
  clicks: ["alarm"],
  done: ["hover"],
  allDone: ["done", "hover"],
  falling: ["dragged"],
  thrown: ["falling", "dragged"],
  thrownUp: ["falling", "dragged"],
  thrownDown: ["falling", "dragged"],
};
const BASIC = ["idle", "hover", "alarm", "alarmClosed", "clicks", "done", "snooze", "sleep", "allDone", "falling"];

const CLIP_NAMES: Record<string, string> = {
  idle_breathe: "Breathing",
  hang_idle: "Hanging, swaying",
  sleep_fall_asleep: "Falls asleep",
  sleep_loop: "Snoozing, z z z",
  sleep_wake_up: "Wakes with a start",
  move_fall_land: "Drops in and lands",
  "move_fall_land@0.45": "Lands with a squash, dizzy",
  sit_to_hang: "Jumps onto its branch",
  int_poked: "Poked: puffs up, annoyed",
  int_petted: "Petted: happy eyes, hearts",
  int_tickled: "Tickled: wriggles, laughs",
  fun_notify: "Holds up a \"!\" sign",
  drop_in: "Falls in and lands",
  fall: "Falls, wings flapping",
  land: "Lands on its feet",
  tumble: "Tumbles head over heels",
  thrown_fire: "Shakes it off, breathes fire back",
  intro_walk: "Walks up to you from far away",
  intro_fly: "Flies in straight at you, lands",
  head_tilt: "Faces you, tilts its head",
  boop: "Boops its snout on your screen",
  front_walk: "Walks towards you",
  front_moment: "Turns to look at you",
  fly_front: "Hovers in front of you",
  front_fire: "Breathes fire at you",
  front_fire_alarm: "Breathes fire straight at you",
  barrel_roll: "Takes off, barrel roll, lands",
  play_bow: "Play bow: \"play with me!\"",
  belly_up: "Rolls over, belly up",
  snooze: "Lies down for a nap",
  wake_up: "Gets up, stretches, yawns",
  lie_down: "Lies down",
  fire: "Breathes fire (side view)",
  dragged: "Dangles, held by the scruff",
  int_dragged: "Dangles, surprised",
  thrown_tumble: "Rolls head over heels, dizzy",
  thrown_flail: "Flies along, flailing",
  thrown_up_whee: "Arms up: \"whee!\"",
  thrown_panic: "Flails, shocked",
  thrown_down_dive: "Head-first ninja dive",
  land_dizzy: "Crash-lands, sees stars",
  land_splat: "Splats flat, pops back up",
  land_dust_off: "Dusts itself off: \"hmph\"",
};

/** "mood_smile_wink" -> "Smile wink". */
export function clipLabel(clip: string): string {
  if (CLIP_NAMES[clip]) return CLIP_NAMES[clip];
  const words = clip.replace(/^(idle|int|mood|fun|move|hang|sleep)_/, "").replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Still frame of a pet's idle SVG; hovering the card plays it. A live image
 * per card would keep the panel repainting the whole time it's open. */
function Thumb({ svg, live }: { svg: string; live: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const url = useMemo(() => {
    const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
    const root = doc.documentElement;
    root.querySelectorAll("title").forEach((n) => n.remove());
    // An intrinsic size, so the image can be drawn (some use width="100%").
    root.setAttribute("width", "160");
    root.setAttribute("height", "160");
    return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(root));
  }, [svg]);

  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const img = new Image();
    img.onload = () => c.getContext("2d")?.drawImage(img, 0, 0, c.width, c.height);
    img.src = url;
  }, [url]);

  return (
    <span className="pet-thumb">
      <canvas ref={canvas} width={160} height={160} hidden={live} />
      {live && <img src={url} alt="" />}
    </span>
  );
}

/** The built-in character, drawn statically. */
function BuddyThumb() {
  return (
    <span className="pet-thumb">
      <svg viewBox="0 0 96 96">
        <ellipse cx="48" cy="89" rx="22" ry="4" fill="rgba(0,0,0,0.22)" />
        <line x1="48" y1="38" x2="48" y2="29" stroke="#6b4a12" strokeWidth="3" strokeLinecap="round" />
        <path d="M51 10 L41 23 H47 L44 31 L56 18 H50 L53 10 Z" fill="#ff9f1c" stroke="#6b4a12" strokeWidth="2" strokeLinejoin="round" />
        <ellipse cx="48" cy="62" rx="31" ry="25" fill="#ffd84d" stroke="#6b4a12" strokeWidth="3" />
        <ellipse cx="38" cy="60" rx="5.5" ry="6.5" fill="#fff" />
        <ellipse cx="58" cy="60" rx="5.5" ry="6.5" fill="#fff" />
        <circle cx="39" cy="61" r="3.2" fill="#2b2110" />
        <circle cx="59" cy="61" r="3.2" fill="#2b2110" />
        <ellipse cx="29" cy="70" rx="4.5" ry="2.5" fill="#ff8fb1" opacity="0.75" />
        <ellipse cx="67" cy="70" rx="4.5" ry="2.5" fill="#ff8fb1" opacity="0.75" />
        <path d="M43 71 Q48 75 53 71" fill="none" stroke="#2b2110" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
    </span>
  );
}

function Mapping({ pet, onError }: { pet: PetInfo; onError: (e: string) => void }) {
  const preview = (key: string) => void ipc.previewPetState(key).catch((e) => onError(String(e)));
  // The built-in character has no clips, just described reactions.
  const builtIn = pet.id === "classic";
  return (
    <section className="pet-map">
      <h2>What does what · {pet.name}</h2>
      {pet.description && <p className="setting-note">{pet.description}</p>}
      {GROUPS.map(([title, rows]) => {
        const shown = rows.filter(([state]) => !builtIn || pet.states[state]);
        if (shown.length === 0) return null;
        return (
          <div key={title}>
            <h3>{title}</h3>
            <ul>
              {shown.map(([state, label, hint]) => {
                const clips = pet.states[state];
                const instead = BASIC.includes(state) ? `same as ${FALLBACK[state]?.find((s) => pet.states[s]) ?? "idle"}` : "nothing";
                return (
                  <li key={state} className={clips ? "" : "unmapped"}>
                    <span>
                      {label}
                      {hint && <small>{hint}</small>}
                    </span>
                    <span className="pet-clips">
                      {!clips && <span className="pet-none">{instead}</span>}
                      {clips?.map((clip, i) =>
                        builtIn ? (
                          <span key={clip}>{clip}</span>
                        ) : (
                          <button key={clip} className="chip-button" title={`${clip}: play on the mascot`} onClick={() => preview(`${state}#${i}`)}>
                            ▶ {clipLabel(clip)}
                          </button>
                        ),
                      )}
                    </span>
                    {builtIn && state !== "idle" && (
                      <button className="mini play" title="Play on the mascot" aria-label={`Play ${label}`} onClick={() => preview(state)}>
                        ▶
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
      {LOOKS.some(([state]) => pet.states[state]) && (
        <div>
          <h3>Watching you</h3>
          <p className="setting-note">While the pointer is near (but not on) the pet, its eyes follow it.</p>
          <div className="pet-looks">
            {LOOKS.map(([state, arrow]) =>
              pet.states[state] ? (
                <button key={state} className="chip-button" title={pet.states[state][0]} onClick={() => preview(state)}>
                  {arrow}
                </button>
              ) : (
                <span key={state || "pet"} />
              ),
            )}
          </div>
        </div>
      )}
      {pet.idleVariants.length > 0 && (
        <>
          <h3>Idle moments</h3>
          <p className="setting-note">One of these plays every 9 to 23 seconds while nothing else is happening.</p>
          <div className="pet-variants">
            {pet.idleVariants.map((clip, i) => (
              <button key={clip} className="chip-button" title={clip} onClick={() => preview(`variant:${i}`)}>
                ▶ {clipLabel(clip)}
              </button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

export function PetPicker({
  list,
  animationEnabled,
  onBack,
  onPick,
  onError,
}: {
  list: PetList;
  animationEnabled: boolean;
  onBack: () => void;
  onPick: (id: string) => Promise<void>;
  onError: (e: string) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const active = list.pets.find((p) => p.id === list.active) ?? list.pets[0];

  const pick = async (id: string) => {
    if (busy || id === list.active) return;
    setBusy(true);
    try {
      await onPick(id);
    } finally {
      // Let the mascot finish its swap before another one starts.
      window.setTimeout(() => setBusy(false), 600);
    }
  };

  return (
    <div className="pets">
      <div className="pets-head">
        <button className="link" onClick={onBack}>
          ‹ Settings
        </button>
        <span>Choose a pet</span>
      </div>
      <div className="pet-grid" role="radiogroup" aria-label="Pet">
        {list.pets.map((p) => (
          <button
            key={p.id}
            role="radio"
            aria-checked={p.id === list.active}
            className={p.id === list.active ? "pet-card selected" : "pet-card"}
            disabled={busy && p.id !== list.active}
            title={p.description}
            onClick={() => void pick(p.id)}
            onMouseEnter={() => setHovered(p.id)}
            onMouseLeave={() => setHovered((h) => (h === p.id ? null : h))}
          >
            {p.preview ? <Thumb svg={p.preview} live={hovered === p.id} /> : <BuddyThumb />}
            <span className="pet-name">{p.name}</span>
          </button>
        ))}
      </div>
      {!animationEnabled && <p className="setting-note">Animation is off, so previews show a still pose.</p>}
      <Mapping key={active.id} pet={active} onError={onError} />
    </div>
  );
}
