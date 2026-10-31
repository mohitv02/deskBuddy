// State-set mascot: self-animating SVG clips mapped to states (e.g. a dragon
// that is happy when idle, flies on hover, breathes fire when an alarm rings).
// A state can list several clips; one is picked at random each time it plays,
// so the same reaction doesn't always look the same.
//
// The SVGs animate either with their own CSS or with SMIL (<animate> tags).
// Left alone, WebKit repaints either kind at 60 fps (~9% CPU for a small
// dragon). Instead the animations are paused and stepped by hand — CSS through
// the Web Animations API at 6 fps idle / 24 fps in reactions, SMIL through
// setCurrentTime at the clip's own frame rate (30 fps for the axolotl), so the
// motion is the artist's but the repaint rate is ours. Paused / fullscreen /
// hidden simply stop the stepping.
//
// SMIL clips crossfade into each other and reactions play whole cycles, so
// nothing cuts mid-move. CSS clips carry <style> blocks that are
// document-global once inlined, so those swap instantly with one mounted.

import type { MascotZone } from "../lib/ipc";

type Look = "lookUp" | "lookUpRight" | "lookRight" | "lookDownRight" | "lookDown" | "lookDownLeft" | "lookLeft" | "lookUpLeft";

type State =
  | "idle"
  | "hover"
  | "hoverHead"
  | "hoverBelly"
  | "hoverTail"
  | "hoverFeet"
  | "poke"
  | "alarm"
  | "alarmClosed"
  | "clicks"
  | "doubleClick"
  | "done"
  | "snooze"
  | "intro"
  | "fallAsleep"
  | "sleep"
  | "wakeUp"
  | "allDone"
  | "added"
  | "started"
  | "deleted"
  | "overdue"
  | "hungry"
  | "dragged"
  | "falling"
  | "dropped"
  | "thrown"
  | "thrownLanded"
  | "thrownUp"
  | "thrownUpLanded"
  | "thrownDown"
  | "thrownDownLanded"
  | Look;

type Fling = "side" | "up" | "down";

/** Each kind of throw: the state while flying, and the one for the landing. */
const FLINGS: Record<Fling, [flying: State, landing: State]> = {
  side: ["thrown", "thrownLanded"],
  up: ["thrownUp", "thrownUpLanded"],
  down: ["thrownDown", "thrownDownLanded"],
};
/** Drawn facing right; mirrored when flying or landing the other way. */
const DIRECTED: string[] = Object.values(FLINGS).flat();

type Zone = "head" | "belly" | "tail" | "feet";

/** The hover reaction for the pointer resting on each body part. */
const ZONE_STATES: Record<Zone, State> = { head: "hoverHead", belly: "hoverBelly", tail: "hoverTail", feet: "hoverFeet" };
/** The pointer has to stay on another part this long before the reaction
 * changes, so brushing along an edge doesn't flicker between two. */
const ZONE_SETTLE_MS = 150;

const LOOKS: Look[] = ["lookUp", "lookUpRight", "lookRight", "lookDownRight", "lookDown", "lookDownLeft", "lookLeft", "lookUpLeft"];

/** Where a missing state falls back to before idle. */
const FALLBACK: Partial<Record<State, State[]>> = {
  alarmClosed: ["hover"],
  clicks: ["alarm"],
  done: ["hover"],
  allDone: ["done", "hover"],
  falling: ["dragged"],
  thrown: ["falling", "dragged"],
  thrownUp: ["falling", "dragged"],
  thrownDown: ["falling", "dragged"],
  hoverHead: ["hover"],
  hoverBelly: ["hover"],
  hoverTail: ["hover"],
  hoverFeet: ["hover"],
  // A friend poked you from chat: the pet's own click reaction will do.
  poke: ["clicks", "doubleClick"],
};

/** States replaced by idle when missing; every other missing state is skipped. */
const BASIC: State[] = ["idle", "hover", "alarm", "alarmClosed", "clicks", "done", "snooze", "sleep", "allDone"];

/** Events the page can be told about (todo moods); see main.ts. */
export const MOODS = ["allDone", "added", "started", "deleted"];

/** A chat message's reaction when none is set for the sender: the first the pet has. */
const MESSAGE_DEFAULT: State[] = ["doubleClick", "added", "done"];

/** Held as long as their condition lasts; a one-shot clip here loops. */
const HELD: string[] = ["idle", "hover", ...Object.values(ZONE_STATES), "alarm", "sleep", "dragged", "falling", "thrown", "thrownUp", "thrownDown"];

const TEMP_MS: Partial<Record<State, number>> = {
  alarmClosed: 3000,
  clicks: 3000,
  doubleClick: 2000,
  done: 2500,
  snooze: 4000,
  allDone: 4000,
  added: 2500,
  started: 3000,
  deleted: 2500,
  overdue: 4000,
  hungry: 4000,
  dropped: 2500,
  thrownLanded: 3000,
  thrownUpLanded: 3000,
  thrownDownLanded: 3000,
  poke: 3000,
};
const IDLE_FPS = 6;
const ACTIVE_FPS = 24;
const MAX_SMIL_FPS = 30;
/** No hover, click or todo change for this long: fall asleep (needs a "sleep" clip). */
const DEFAULT_SLEEP_AFTER_S = 20;
/** Hovering a sleeping mascot this long wakes it. */
const WAKE_HOVER_MS = 1500;
/** A leave followed by an enter within this is one continuous hover. */
const LEAVE_GRACE_MS = 250;
/** Pause between idle variants (random in this range). */
const VARIANT_GAP_MS: [number, number] = [9000, 23000];
/** Instead of a variant, the context mood (overdue todos, meal time) plays this often. */
const MOOD_CHANCE = 0.5;

/** A clip entry is a file name, optionally with a start offset:
 * "move_fall_land.svg@0.45" plays from 0.45 s (e.g. just the landing). */
function parseEntry(entry: string): [file: string, startMs: number] {
  const at = entry.lastIndexOf("@");
  if (at < 0) return [entry, 0];
  return [entry.slice(0, at), (Number(entry.slice(at + 1)) || 0) * 1000];
}

interface Clip {
  markup: string;
  /** Has <style>: can't share the document with another clip. */
  styled: boolean;
  /** Authored frame rate and cycle length (data-fps / data-frames), if given. */
  fps: number;
  cycleMs: number | null;
  loop: boolean;
}

/** Parse and strip anything active: scripts, event handlers, external refs. */
function sanitize(svgText: string): Clip | null {
  const doc = new DOMParser().parseFromString(svgText, "image/svg+xml");
  const root = doc.documentElement;
  if (root.nodeName !== "svg" || doc.querySelector("parsererror")) return null;
  // <title> too: WebKit shows it as a tooltip window, and the pointer
  // entering that window reads as leaving the mascot (breaks hover-to-wake).
  root.querySelectorAll("script, foreignObject, iframe, object, embed, title").forEach((n) => n.remove());
  for (const el of [root, ...Array.from(root.querySelectorAll("*"))]) {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase();
      const value = attr.value.trim().toLowerCase();
      if (name.startsWith("on")) el.removeAttribute(attr.name);
      else if ((name === "href" || name === "xlink:href") && !value.startsWith("#") && !value.startsWith("data:image/")) el.removeAttribute(attr.name);
    }
  }
  root.setAttribute("width", "100%");
  root.setAttribute("height", "100%");
  const fps = Number(root.getAttribute("data-fps")) || MAX_SMIL_FPS;
  const frames = Number(root.getAttribute("data-frames"));
  return {
    markup: new XMLSerializer().serializeToString(root),
    styled: root.querySelector("style") !== null,
    fps: Math.min(fps, MAX_SMIL_FPS),
    cycleMs: frames > 0 ? (frames / fps) * 1000 : null,
    loop: root.getAttribute("data-loop") !== "false",
  };
}

export class SvgStateAnimator {
  /** file name -> clip */
  private clips = new Map<string, Clip>();
  /** state -> clip entries to pick from */
  private states = new Map<State, string[]>();
  /** The pick for each state, made when the state starts. */
  private chosen = new Map<State, string>();
  private variants: string[] = [];
  /** The file on screen, and the state it plays for. */
  private shown: string | null = null;
  private shownState = "";
  private layer: HTMLElement | null = null;
  private svg: SVGSVGElement | null = null;
  private temp: { state: State; until: number } | null = null;
  private tempTimer: number | undefined;
  private variant: { index: number; until: number } | null = null;
  private variantTimer: number | undefined;
  private asleep = false;
  private sleepAfterMs: number;
  private sleepTimer: number | undefined;
  private wakeHoverTimer: number | undefined;
  private leaveTimer: number | undefined;
  private hovering = false;
  /** The body part under the pointer while hovering, and one it's moving onto. */
  private zone: Zone | null = null;
  private pendingZone: Zone | null | undefined;
  /** The first position after the pointer comes in has been seen. */
  private zoneKnown = false;
  private zoneTimer: number | undefined;
  /** Where the pointer last was on the window (px), to re-check the part when the pet turns. */
  private lastPointer: [number, number] | null = null;
  private dragging = false;
  /** Let go up high: the window is dropping back down. */
  private dropping = false;
  /** Flung: which way (null if not), and sideways 1 = right, -1 = left, 0 = straight. */
  private fling: Fling | null = null;
  private throwDir = 0;
  /** The thrown clips face right; the other way is mirrored. */
  private facing = 1;
  private looking: Look | null = null;
  private ringing = false;
  private paused = false;
  private fullscreen = false;
  private animations: Animation[] = [];
  private clockMs = 0;
  private lastTick = 0;
  private ticker: number | undefined;

  constructor(
    private el: HTMLElement,
    clips: Record<string, string>,
    states: Record<string, string[]>,
    idleVariants: string[] = [],
    sleepAfterSeconds: number | null = null,
    /** Mood that fits the moment (e.g. "overdue"), asked before each idle variant. */
    private contextMood: () => string | null = () => null,
    /** Body parts for hover reactions (boxes in the idle SVG's viewBox), first match wins. */
    private zones: MascotZone[] = [],
  ) {
    for (const [file, text] of Object.entries(clips)) {
      const clip = sanitize(text);
      if (clip) this.clips.set(file, clip);
    }
    for (const [state, files] of Object.entries(states)) {
      const usable = files.filter((f) => this.clips.has(parseEntry(f)[0]));
      if (usable.length > 0) this.states.set(state as State, usable);
    }
    if (!this.states.has("idle")) throw new Error("state set has no usable idle SVG");
    this.variants = idleVariants.filter((f) => this.clips.has(parseEntry(f)[0]));
    this.sleepAfterMs = 0;
    this.setSleepAfter(sleepAfterSeconds ?? DEFAULT_SLEEP_AFTER_S);
    this.choose("idle");
    document.addEventListener("visibilitychange", () => this.applyFreeze());
    this.el.hidden = false;
    if (this.states.has("intro")) this.flash("intro");
    else this.render();
    this.scheduleVariant();
    this.scheduleSleep();
  }

  setPaused(paused: boolean) {
    this.paused = paused;
    this.applyFreeze();
  }

  setFullscreen(fullscreen: boolean) {
    this.fullscreen = fullscreen;
    this.applyFreeze();
  }

  setHover(on: boolean) {
    clearTimeout(this.leaveTimer);
    if (on) this.applyHover(true);
    else this.leaveTimer = window.setTimeout(() => this.applyHover(false), LEAVE_GRACE_MS);
  }

  private applyHover(on: boolean) {
    if (on === this.hovering) return;
    this.hovering = on;
    if (!on) {
      clearTimeout(this.zoneTimer);
      this.zoneKnown = false;
      this.lastPointer = null;
      this.zone = null;
      this.pendingZone = undefined;
    }
    if (on) this.choose(this.hoverState());
    clearTimeout(this.wakeHoverTimer);
    // A sleeping mascot only wakes if the pointer stays a moment.
    if (on && this.asleep) this.wakeHoverTimer = window.setTimeout(() => this.wake(), WAKE_HOVER_MS);
    if (!this.asleep) this.scheduleSleep();
    this.render();
  }

  setAlarm(on: boolean) {
    if (on === this.ringing) return;
    this.ringing = on;
    this.asleep = false;
    this.scheduleSleep();
    if (on) this.choose("alarm");
    if (!on) this.flash("alarmClosed");
    else this.render();
  }

  /** Todo completed. */
  happy() {
    this.asleep = false;
    this.scheduleSleep();
    this.flash("done");
  }

  /** A todo mood from the backend: allDone, added, started, deleted. */
  mood(name: string) {
    if (!MOODS.includes(name)) return;
    this.asleep = false;
    this.scheduleSleep();
    this.flash(name as State);
  }

  /** A chat message arrived: play `state` ("" = the default reaction, "none" = nothing). */
  react(state: string) {
    if (state === "none") return;
    const pick = state && this.playable(state as State) ? (state as State) : (MESSAGE_DEFAULT.find((s) => this.states.has(s)) ?? "done");
    // Not after a throw: a landing played as a reaction faces forward.
    this.facing = 1;
    this.asleep = false;
    this.scheduleSleep();
    this.flash(pick);
  }

  /** A quick click streak: 1 = single click, 2 = double click, 3 = "clicks". */
  clicks(count = 3) {
    if (this.asleep) return this.wake();
    this.scheduleSleep();
    if (count >= 2) this.flash(count === 2 ? "doubleClick" : "clicks");
  }

  snoozed() {
    this.asleep = false;
    this.scheduleSleep();
    this.flash("snooze");
  }

  /** Todos changed: the user is around. */
  activity() {
    if (this.asleep) this.wake();
    else this.scheduleSleep();
  }

  /** Seconds of nothing happening before it dozes off (0 = never). */
  setSleepAfter(seconds: number) {
    this.sleepAfterMs = this.states.has("sleep") ? seconds * 1000 : 0;
    if (!this.asleep) this.scheduleSleep();
  }

  /** Picked up: the window manager is moving the window. */
  dragStart() {
    this.dragging = true;
    this.dropping = false;
    this.fling = null;
    this.throwDir = 0;
    this.asleep = false;
    this.temp = null;
    clearTimeout(this.sleepTimer);
    this.choose("dragged");
    this.render();
  }

  /** Let go up high: the window is dropping back down. */
  falling() {
    if (!this.dragging) return;
    this.dropping = true;
    this.choose("falling");
    this.render();
  }

  /** Flung sideways (tumbles along until it stops), up (flies up and falls
   * back) or down (slams into the ground); `dir` is the sideways part. */
  thrown(dir: number, kind: Fling = "side") {
    if (!this.dragging) return;
    this.dropping = true;
    this.fling = FLINGS[kind] ? kind : "side";
    this.throwDir = Math.sign(dir);
    this.facing = this.throwDir || 1;
    this.choose(FLINGS[this.fling][0]);
    this.render();
  }

  /** Back on the ground: play the landing (after a throw: turned round, facing you). */
  landed() {
    if (!this.dragging) return;
    this.dragging = false;
    this.dropping = false;
    this.scheduleSleep();
    const landing = this.fling && FLINGS[this.fling][1];
    if (landing && this.states.has(landing)) {
      this.facing = -this.throwDir || 1;
      this.flash(landing);
    } else this.flash("dropped");
    this.fling = null;
    this.throwDir = 0;
    this.render();
  }

  /** Pointer position on the mascot window (px): react to the body part under it. */
  pointer(x: number, y: number) {
    if (!this.hovering || this.zones.length === 0) return;
    this.lastPointer = [x, y];
    const zone = this.zoneAt(x, y);
    // Just came in: react to that part straight away.
    if (!this.zoneKnown) {
      this.zoneKnown = true;
      if (zone === this.zone) return;
      this.zone = zone;
      this.choose(this.hoverState());
      this.render();
      return;
    }
    if (zone === this.zone) {
      clearTimeout(this.zoneTimer);
      this.pendingZone = undefined;
      return;
    }
    if (zone === this.pendingZone) return;
    this.pendingZone = zone;
    clearTimeout(this.zoneTimer);
    this.zoneTimer = window.setTimeout(() => {
      this.zone = zone;
      this.pendingZone = undefined;
      if (!this.hovering) return;
      this.choose(this.hoverState());
      this.render();
    }, ZONE_SETTLE_MS);
  }

  private zoneAt(x: number, y: number): Zone | null {
    const ctm = this.svg?.getScreenCTM();
    if (!ctm) return null;
    const p = new DOMPoint(x, y).matrixTransform(ctm.inverse());
    const hit = this.zones.find(({ box: [x0, y0, x1, y1] }) => p.x >= x0 && p.x <= x1 && p.y >= y0 && p.y <= y1);
    return hit && hit.name in ZONE_STATES ? (hit.name as Zone) : null;
  }

  private hoverState(): State {
    return this.zone ? ZONE_STATES[this.zone] : "hover";
  }

  /** Which way the pointer is ("" = not near): eyes follow it, if the pet can. */
  look(dir: string) {
    this.looking = LOOKS.includes(dir as Look) ? (dir as Look) : null;
    this.render();
  }

  /** Settings preview: a state, "state#i" for one clip of its list, or "variant:<i>". */
  preview(key: string) {
    this.asleep = false;
    this.scheduleSleep();
    if (key.startsWith("message:")) return this.react(key.slice(8));
    this.facing = 1;
    if (key.startsWith("variant:")) {
      const index = Number(key.slice(8));
      if (!this.variants[index]) return;
      this.temp = null;
      this.startVariant(index);
      return;
    }
    const [state, i] = key.split("#") as [State, string | undefined];
    const files = this.states.get(state);
    if (!files) return;
    this.flash(state, i === undefined ? undefined : files[Number(i)]);
  }

  /** (Re)start the inactivity countdown. */
  private scheduleSleep() {
    clearTimeout(this.sleepTimer);
    if (this.sleepAfterMs > 0) this.sleepTimer = window.setTimeout(() => this.fallAsleep(), this.sleepAfterMs);
  }

  private fallAsleep() {
    // Busy (reacting, hovered, ringing, carried): try again after another full wait.
    if (this.ringing || this.hovering || this.dragging || (this.temp && performance.now() < this.temp.until)) return this.scheduleSleep();
    this.asleep = true;
    this.choose("sleep");
    this.flash("fallAsleep");
    this.render();
  }

  private wake() {
    clearTimeout(this.wakeHoverTimer);
    if (!this.asleep) return;
    this.asleep = false;
    this.scheduleSleep();
    this.flash("wakeUp");
    this.render();
  }

  /** Pick one of a state's clips, avoiding a repeat of the last pick. */
  private choose(state: State, file?: string) {
    const s = this.resolve(state);
    const files = this.states.get(s)!;
    const last = this.chosen.get(s);
    const pool = files.length > 1 ? files.filter((f) => f !== last) : files;
    this.chosen.set(s, file && files.includes(file) ? file : pool[Math.floor(Math.random() * pool.length)]);
  }

  private fileFor(state: State): string {
    const s = this.resolve(state);
    return this.chosen.get(s) ?? this.states.get(s)![0];
  }

  /** The pet has clips for this state, or for one it falls back to. */
  private playable(state: State): boolean {
    return this.states.has(state) || (FALLBACK[state] ?? []).some((s) => this.states.has(s));
  }

  private flash(state: State, file?: string) {
    if (!BASIC.includes(state) && !this.playable(state)) return;
    this.choose(state, file);
    const ms = this.holdMs(this.fileFor(state), TEMP_MS[state] ?? 3000);
    this.temp = { state, until: performance.now() + ms };
    clearTimeout(this.tempTimer);
    this.tempTimer = window.setTimeout(() => {
      this.temp = null;
      this.render();
    }, ms);
    this.render();
  }

  /** Reactions run whole cycles, so they never cut off mid-move. */
  private holdMs(entry: string, ms: number): number {
    const clip = this.clipOf(entry);
    if (!clip.cycleMs) return ms;
    if (!clip.loop) return Math.max(1, clip.cycleMs - parseEntry(entry)[1]);
    return Math.max(1, Math.round(ms / clip.cycleMs)) * clip.cycleMs;
  }

  private scheduleVariant() {
    if (this.variants.length === 0 && !this.hasContextMoods()) return;
    const [lo, hi] = VARIANT_GAP_MS;
    clearTimeout(this.variantTimer);
    this.variantTimer = window.setTimeout(() => this.playVariant(), lo + Math.random() * (hi - lo));
  }

  private hasContextMoods() {
    return this.states.has("overdue") || this.states.has("hungry");
  }

  private playVariant() {
    const calm = this.shownState === "idle" || LOOKS.includes(this.shownState as Look);
    if (calm && !this.isFrozen()) {
      const mood = this.contextMood() as State | null;
      if (mood && this.states.has(mood) && (Math.random() < MOOD_CHANCE || this.variants.length === 0)) this.flash(mood);
      else if (this.variants.length > 0) this.startVariant(Math.floor(Math.random() * this.variants.length));
    }
    this.scheduleVariant();
  }

  private startVariant(index: number) {
    const ms = this.holdMs(this.variants[index], 4000);
    this.variant = { index, until: performance.now() + ms };
    window.setTimeout(() => {
      if (this.variant?.index !== index) return;
      this.variant = null;
      this.render();
    }, ms);
    this.render();
  }

  private clipOf(entry: string): Clip {
    return this.clips.get(parseEntry(entry)[0])!;
  }

  private resolve(state: State): State {
    if (this.states.has(state)) return state;
    return FALLBACK[state]?.find((s) => this.states.has(s)) ?? "idle";
  }

  /** [state name, file] that should be on screen now. */
  private wanted(): [string, string] {
    const now = performance.now();
    const state = (s: State): [string, string] => [this.resolve(s), this.fileFor(s)];
    if (this.ringing) return state("alarm");
    if (this.dragging) {
      const carried: State = this.fling ? FLINGS[this.fling][0] : this.dropping ? "falling" : "dragged";
      if (this.resolve(carried) !== "idle") return state(carried);
    }
    if (this.temp && now < this.temp.until) return state(this.temp.state);
    if (this.asleep) return state("sleep");
    if (this.hovering) return state(this.hoverState());
    if (this.variant && now < this.variant.until) return ["variant", this.variants[this.variant.index]];
    if (this.looking && this.states.has(this.looking)) return state(this.looking);
    return state("idle");
  }

  private render(): void {
    const [state, file] = this.wanted();
    // Anything else interrupts an idle variant for good.
    if (state !== "variant") this.variant = null;
    this.shownState = state;
    const flipped = DIRECTED.includes(state) && this.facing < 0;
    const turned = flipped !== this.el.classList.contains("flipped");
    this.el.classList.toggle("flipped", flipped);
    // The pet turned under a resting pointer: its parts moved, check which one it's on now.
    if (turned && this.hovering && this.zoneKnown && this.lastPointer) {
      const zone = this.zoneAt(...this.lastPointer);
      if (zone !== this.zone) {
        this.zone = zone;
        this.choose(this.hoverState());
        return this.render();
      }
    }
    if (file === this.shown) return;
    const prev = this.layer;
    const prevClip = this.shown === null ? null : this.clipOf(this.shown);
    const clip = this.clipOf(file);
    this.shown = file;
    const layer = document.createElement("div");
    layer.className = "clip";
    layer.innerHTML = clip.markup;
    const fade = prev !== null && !clip.styled && !prevClip?.styled && !this.isFrozen();
    if (prev && !fade) prev.remove();
    this.el.append(layer);
    if (prev && fade) {
      // The new clip fades in over the old one, which stays opaque underneath
      // (no see-through dip halfway), then the old one goes.
      layer.classList.add("entering");
      void layer.offsetWidth;
      layer.classList.remove("entering");
      const done = () => prev.remove();
      layer.addEventListener("transitionend", done, { once: true });
      window.setTimeout(done, 400);
    }
    this.layer = layer;

    this.svg = layer.querySelector("svg");
    this.svg?.pauseAnimations();
    const startMs = parseEntry(file)[1];
    this.svg?.setCurrentTime(startMs / 1000);
    // Take over the SVG's CSS animations (getAnimations flushes styles first).
    this.animations = this.svg && typeof this.svg.getAnimations === "function" ? this.svg.getAnimations({ subtree: true }) : [];
    for (const a of this.animations) a.pause();
    this.clockMs = startMs;
    for (const a of this.animations) a.currentTime = startMs;
    this.applyFreeze();
  }

  private isFrozen(): boolean {
    return !this.ringing && (this.paused || this.fullscreen || document.hidden);
  }

  private isSmil(): boolean {
    return this.svg?.querySelector("animate, animateTransform, animateMotion, set") != null;
  }

  /** Alarms always animate (they're alerts); otherwise respect pause rules. */
  private applyFreeze() {
    const frozen = this.isFrozen();
    // A drop-in intro frozen on frame 0 would be an empty window: skip it.
    if (frozen && this.temp?.state === "intro") {
      this.temp = null;
      clearTimeout(this.tempTimer);
      this.render();
      return;
    }
    const smil = this.isSmil();
    // Fallback for engines without the Web Animations API: plain CSS freeze.
    this.el.classList.toggle("frozen", frozen || this.animations.length > 0);
    clearInterval(this.ticker);
    this.ticker = undefined;
    if (frozen || (!smil && this.animations.length === 0)) return;
    const clip = this.clipOf(this.shown!);
    const fps = smil ? clip.fps : this.shownState === "idle" ? IDLE_FPS : ACTIVE_FPS;
    this.lastTick = performance.now();
    this.ticker = window.setInterval(() => this.tick(), 1000 / fps);
    this.tick();
  }

  private tick() {
    const now = performance.now();
    this.clockMs += now - this.lastTick;
    this.lastTick = now;
    // A one-shot clip held as a state (e.g. a hover or alarm that plays once)
    // starts over instead of freezing on its last frame. Timed reactions and
    // variants already end after exactly one cycle.
    const clip = this.clipOf(this.shown!);
    const held = HELD.includes(this.shownState) && !(this.temp && now < this.temp.until);
    if (held && !clip.loop && clip.cycleMs && this.clockMs >= clip.cycleMs) this.clockMs %= clip.cycleMs;
    this.svg?.setCurrentTime(this.clockMs / 1000);
    for (const a of this.animations) a.currentTime = this.clockMs;
  }
}
