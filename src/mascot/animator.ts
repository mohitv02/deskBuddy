// Frame-based mascot animator. Instead of Lottie (extra dependency, 60fps rAF),
// we redraw a small SVG "sprite" on a low-rate timer. Idle is a rest pose with a
// short gesture every few seconds, so most of the time no timer runs at all and
// the window is not repainted. Everything stops when paused, hidden or a
// fullscreen app is active.

const FPS = 15;
const HAPPY_MS = 1500;
const REST_MIN_MS = 2500;
const REST_MAX_MS = 6000;

type Gesture = { name: "blink" | "wiggle" | "bounce" | "happy"; ms: number };

const GESTURES: Gesture[] = [
  { name: "blink", ms: 180 },
  { name: "blink", ms: 180 },
  { name: "wiggle", ms: 900 },
  { name: "bounce", ms: 700 },
];

const ALARM_FPS = 20;
const MOUTH_IDLE = "M43 71 Q48 75 53 71";
const MOUTH_ALARM = "M44 72 a4 5 0 1 0 8 0 a4 5 0 1 0 -8 0 Z";
const MOUTH_HAPPY = "M40 69 Q48 81 56 69 Z";

export class Animator {
  private paused = false;
  private fullscreen = false;
  private ringing = false;
  private gesture: Gesture | null = null;
  private gestureStart = 0;
  private frameTimer: number | undefined;
  private restTimer: number | undefined;

  private body = el("body");
  private shadow = el("shadow");
  private antenna = el("antenna");
  private eyesOpen = el("eyes-open");
  private eyesHappy = el("eyes-happy");
  private mouth = el("mouth");
  private sparkles = el("sparkles");

  constructor() {
    document.addEventListener("visibilitychange", () => this.sync());
    this.renderRest();
    this.sync();
  }

  get isPaused() {
    return this.paused;
  }

  setPaused(paused: boolean) {
    this.paused = paused;
    this.sync();
  }

  setFullscreen(fullscreen: boolean) {
    this.fullscreen = fullscreen;
    this.sync();
  }

  /** One-shot celebration; skipped when animation is off. */
  happy() {
    if (this.running && !this.ringing) this.play({ name: "happy", ms: HAPPY_MS });
  }

  /** Alarm loop: plays even when paused, since it is an alert. */
  setAlarm(on: boolean) {
    if (on === this.ringing) return;
    this.ringing = on;
    this.stopTimers();
    this.gesture = null;
    if (on) {
      const start = performance.now();
      this.frameTimer = window.setInterval(() => this.renderAlarm((performance.now() - start) / 1000), 1000 / ALARM_FPS);
    } else {
      this.renderRest();
      this.sync();
    }
  }

  private get running() {
    return !this.paused && !this.fullscreen && !document.hidden;
  }

  private stopTimers() {
    clearInterval(this.frameTimer);
    clearTimeout(this.restTimer);
    this.frameTimer = this.restTimer = undefined;
  }

  private sync() {
    if (this.ringing) return;
    if (!this.running) {
      this.stopTimers();
      this.gesture = null;
      this.renderRest();
    } else if (this.frameTimer === undefined && this.restTimer === undefined) {
      this.scheduleNextGesture();
    }
  }

  private scheduleNextGesture() {
    const wait = REST_MIN_MS + Math.random() * (REST_MAX_MS - REST_MIN_MS);
    this.restTimer = window.setTimeout(() => {
      this.restTimer = undefined;
      this.play(GESTURES[Math.floor(Math.random() * GESTURES.length)]);
    }, wait);
  }

  private play(g: Gesture) {
    this.stopTimers();
    this.gesture = g;
    this.gestureStart = performance.now();
    this.frameTimer = window.setInterval(() => this.tick(), 1000 / FPS);
    this.tick();
  }

  private tick() {
    const g = this.gesture;
    if (!g) return;
    const u = (performance.now() - this.gestureStart) / g.ms;
    if (u >= 1) {
      this.stopTimers();
      this.gesture = null;
      this.renderRest();
      if (this.running) this.scheduleNextGesture();
      return;
    }
    switch (g.name) {
      case "blink":
        this.renderRest();
        this.eyesOpen.setAttribute("transform", "translate(0 60) scale(1 0.12) translate(0 -60)");
        break;
      case "wiggle":
        this.renderRest();
        this.antenna.setAttribute("transform", `rotate(${(Math.sin(u * Math.PI * 4) * 14 * (1 - u)).toFixed(2)} 48 38)`);
        break;
      case "bounce": {
        const hop = Math.sin(u * Math.PI);
        this.renderRest();
        this.body.setAttribute("transform", bodyTransform(-5 * hop, 1 + 0.03 * hop));
        this.shadow.setAttribute("transform", shadowTransform(1 - hop * 0.15));
        break;
      }
      case "happy":
        this.renderHappy(u);
        break;
    }
  }

  private renderRest() {
    this.body.setAttribute("transform", "");
    this.shadow.setAttribute("transform", "");
    this.antenna.setAttribute("transform", "");
    this.eyesOpen.setAttribute("transform", "");
    this.eyesOpen.setAttribute("visibility", "visible");
    this.eyesHappy.setAttribute("visibility", "hidden");
    this.mouth.setAttribute("d", MOUTH_IDLE);
    this.mouth.setAttribute("fill", "none");
    this.sparkles.setAttribute("opacity", "0");
  }

  private renderAlarm(t: number) {
    const shake = Math.sin(t * Math.PI * 14) * 7;
    const hop = Math.abs(Math.sin(t * Math.PI * 3)) * 4;
    this.body.setAttribute("transform", `rotate(${shake.toFixed(2)} 48 87) ${bodyTransform(-hop, 1)}`);
    this.shadow.setAttribute("transform", shadowTransform(1 - hop * 0.03));
    this.antenna.setAttribute("transform", `rotate(${(Math.sin(t * Math.PI * 22) * 20).toFixed(2)} 48 38)`);
    this.eyesOpen.setAttribute("visibility", "visible");
    this.eyesOpen.setAttribute("transform", "translate(48 60) scale(1.22) translate(-48 -60)");
    this.eyesHappy.setAttribute("visibility", "hidden");
    this.mouth.setAttribute("d", MOUTH_ALARM);
    this.mouth.setAttribute("fill", "#2b2110");
    this.sparkles.setAttribute("opacity", "0");
  }

  private renderHappy(u: number) {
    const hop = Math.abs(Math.sin(u * Math.PI * 2)); // two hops
    const squash = hop < 0.15 ? 0.92 : 1.04;
    this.body.setAttribute("transform", bodyTransform(-13 * hop, squash));
    this.shadow.setAttribute("transform", shadowTransform(1 - hop * 0.4));
    this.antenna.setAttribute("transform", `rotate(${(Math.sin(u * Math.PI * 6) * 18).toFixed(2)} 48 38)`);
    this.eyesOpen.setAttribute("visibility", "hidden");
    this.eyesHappy.setAttribute("visibility", "visible");
    this.mouth.setAttribute("d", MOUTH_HAPPY);
    this.mouth.setAttribute("fill", "#ff6f91");
    this.sparkles.setAttribute("opacity", Math.sin(u * Math.PI).toFixed(2));
    this.sparkles.setAttribute("transform", `translate(0 ${(-6 * u).toFixed(2)})`);
  }
}

function el(id: string): SVGElement {
  const node = document.getElementById(id);
  if (!node) throw new Error(`missing #${id}`);
  return node as unknown as SVGElement;
}

/** Translate vertically and squash around the feet (y = 87). */
function bodyTransform(dy: number, squash: number) {
  const sx = (1 / Math.sqrt(squash)).toFixed(3);
  return `translate(0 ${dy.toFixed(2)}) translate(48 87) scale(${sx} ${squash.toFixed(3)}) translate(-48 -87)`;
}

function shadowTransform(scale: number) {
  return `translate(48 89) scale(${scale.toFixed(3)} 1) translate(-48 -89)`;
}
