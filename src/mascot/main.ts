// The mascot page only draws. Mouse input (click, drag, right-click menu) is
// handled natively in Rust (system/window.rs): it is more reliable than webview
// events on GNOME/X11 and lets the window manager perform the move itself.
import { listen } from "@tauri-apps/api/event";
import { ipc, type Settings, type Todo } from "../lib/ipc";
import { isOverdue } from "../lib/dates";
import { Animator } from "./animator";
import { SpriteAnimator } from "./sprite";
import { SvgStateAnimator } from "./svgstates";

interface Renderer {
  setPaused(paused: boolean): void;
  setFullscreen(fullscreen: boolean): void;
  happy(): void;
  setAlarm(on: boolean): void;
  /** Optional reactions; renderers without them ignore the event. */
  setHover?(on: boolean): void;
  /** count: 1 = single click, 2 = double, 3 = triple. */
  clicks?(count: number): void;
  /** The user did something with their todos. */
  activity?(): void;
  snoozed?(): void;
  /** Settings preview: play a state name or "variant:<i>". */
  preview?(key: string): void;
  /** A todo mood: allDone, added, started, deleted. */
  mood?(name: string): void;
  /** A chat message arrived: a state to play, "" for the default, "none" for nothing. */
  react?(state: string): void;
  /** Picked up / let go up high and dropping / back on the ground. */
  dragStart?(): void;
  falling?(): void;
  /** Flung "side", "up" or "down"; dir: 1 = to the right, -1 = to the left, 0 = straight. */
  thrown?(dir: number, kind: "side" | "up" | "down"): void;
  landed?(): void;
  setSleepAfter?(seconds: number): void;
  /** Direction of the pointer near the mascot ("" = not near). */
  look?(dir: string): void;
}

/** Meal times (local hours) when a pet with a "hungry" clip gets peckish. */
const MEALS: [number, number][] = [
  [12, 13.5],
  [19, 20.5],
];

let todos: Todo[] = [];
const refreshTodos = () =>
  void ipc
    .listTodos()
    .then((t) => (todos = t))
    .catch(() => {});

/** Asked before each idle variant: a mood that fits the moment, if any. */
function contextMood(): string | null {
  const now = new Date();
  if (todos.some((t) => t.status !== "done" && isOverdue(t.due, now))) return "overdue";
  const h = now.getHours() + now.getMinutes() / 60;
  return MEALS.some(([a, b]) => h >= a && h < b) ? "hungry" : null;
}

/** Matches the pet-out animation in mascot.css. */
const LEAVE_MS = 280;
const PREVIEW_ALARM_MS = 3000;

/** Inline style: the stylesheet's `display: block` would beat an SVG attribute. */
function hideBuiltIn() {
  document.getElementById("mascot")!.style.display = "none";
}

/** Built-in SVG character, a user state set, image, or sprite sheet. */
async function createRenderer(settings: Settings): Promise<Renderer> {
  const custom = await ipc.customMascot().catch(() => null);
  if (custom?.type === "svgStates") {
    try {
      const r = new SvgStateAnimator(
        document.getElementById("svg-states")!,
        custom.clips,
        custom.states,
        custom.idleVariants,
        settings.sleepAfterSeconds,
        contextMood,
      );
      hideBuiltIn();
      return r;
    } catch (e) {
      console.error("state-set mascot failed, using built-in mascot", e);
    }
  }
  if (custom?.type === "sprite") {
    const sprite = new SpriteAnimator(document.getElementById("sprite")!, custom.url, custom.sheet);
    try {
      await sprite.start();
      hideBuiltIn();
      return sprite;
    } catch (e) {
      console.error("sprite sheet failed to load, using built-in mascot", e);
    }
  }
  if (custom?.type === "image") {
    const img = document.getElementById("custom-image")!;
    img.setAttribute("href", custom.url);
    img.setAttribute("visibility", "visible");
    // display (not visibility): the animator sets visibility on children, which would override it.
    document.getElementById("drawn")!.setAttribute("display", "none");
  }
  return new Animator();
}

async function init() {
  refreshTodos();
  const settings = await ipc.getSettings();
  const renderer = await createRenderer(settings);
  document.body.classList.remove("loading");
  renderer.setPaused(!settings.animationEnabled);
  renderer.setFullscreen(await ipc.isFullscreen());
  await listen<boolean>("fullscreen-changed", (e) => renderer.setFullscreen(e.payload));
  await listen<boolean>("animation-enabled", (e) => renderer.setPaused(!e.payload));
  await listen("mascot-happy", () => {
    refreshTodos();
    renderer.happy();
  });
  // Icon size changed: re-run layout (sprite scaling, SVG sizing) from scratch.
  await listen("mascot-relayout", () => location.reload());
  await listen("alarm", () => renderer.setAlarm(true));
  await listen("alarm-stopped", () => renderer.setAlarm(false));
  await listen<boolean>("mascot-hover", (e) => renderer.setHover?.(e.payload));
  await listen<number>("mascot-clicks", (e) => {
    if (renderer.clicks) renderer.clicks(e.payload);
    else if (e.payload >= 3) renderer.happy();
  });
  await listen("alarm-snoozed", () => renderer.snoozed?.());
  await listen("todos-changed", () => {
    refreshTodos();
    renderer.activity?.();
  });
  await listen<string>("mascot-mood", (e) => {
    refreshTodos();
    if (renderer.mood) renderer.mood(e.payload);
    else if (e.payload === "allDone") renderer.happy();
  });
  await listen<string>("mascot-react", (e) => {
    if (renderer.react) renderer.react(e.payload);
    else if (e.payload !== "none") renderer.happy();
  });
  await listen("mascot-drag", () => renderer.dragStart?.());
  await listen("mascot-falling", () => renderer.falling?.());
  await listen<{ kind: "side" | "up" | "down"; dir: number }>("mascot-thrown", (e) =>
    renderer.thrown ? renderer.thrown(e.payload.dir, e.payload.kind) : renderer.falling?.(),
  );
  await listen("mascot-landed", () => renderer.landed?.());
  await listen<number>("mascot-sleep-after", (e) => renderer.setSleepAfter?.(e.payload));
  await listen<string>("mascot-look", (e) => renderer.look?.(e.payload));
  // Another pet was picked: let this one shrink away, then load the new one,
  // which pops in (mascot.css). A reload drops every timer of the old renderer.
  await listen("mascot-pet-changed", () => {
    document.body.classList.add("leaving");
    window.setTimeout(() => location.reload(), LEAVE_MS);
  });
  await listen<string>("mascot-preview", (e) => {
    if (renderer.preview) return renderer.preview(e.payload);
    if (e.payload.startsWith("message:") && e.payload !== "message:none") renderer.happy();
    if (e.payload === "done") renderer.happy();
    if (e.payload === "alarm") {
      renderer.setAlarm(true);
      window.setTimeout(() => renderer.setAlarm(false), PREVIEW_ALARM_MS);
    }
  });
  if (await ipc.alarmCurrent()) renderer.setAlarm(true);
}

void init();
