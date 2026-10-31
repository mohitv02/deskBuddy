// Alarm effect overlay. The window is click-through and only exists while an
// alarm rings; Rust centres it on the effect origin and passes the config in
// window.__FX__ (effect name, origin x/y in CSS px, horizontal direction ±1).
import { effects, type Effect } from "./effects";

declare global {
  interface Window {
    __FX__?: { effect: string; x: number; y: number; dir: 1 | -1; text?: string | null; size?: number };
  }
}

const cfg = window.__FX__ ?? { effect: "sparks", x: innerWidth / 2, y: innerHeight * 0.6, dir: -1 };
const canvas = document.getElementById("fx") as HTMLCanvasElement;
const ctx = canvas.getContext("2d")!;
const dpr = window.devicePixelRatio || 1;
canvas.width = innerWidth * dpr;
canvas.height = innerHeight * dpr;
ctx.scale(dpr, dpr);

const make = effects[cfg.effect] ?? effects.sparks;
const effect: Effect = make({ x: cfg.x, y: cfg.y, dir: cfg.dir, text: cfg.text ?? undefined, size: cfg.size });

let last = performance.now();
function frame(now: number) {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  effect.step(dt);
  effect.draw(ctx);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
