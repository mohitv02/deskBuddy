// Sprite-sheet mascot: plays frames from a user-supplied sheet described by
// ~/.config/deskbuddy/mascot/sprite.json. Same pause rules as the SVG animator:
// nothing runs while paused, hidden or when a fullscreen app is focused, and an
// idle `pauseMs` holds the first frame between loops to keep CPU low.
import type { SpriteAnimation, SpriteSheet } from "../lib/ipc";

export class SpriteAnimator {
  private paused = false;
  private fullscreen = false;
  private ringing = false;
  private timer: number | undefined;
  private current: SpriteAnimation;
  private frame = 0;
  private columns = 1;
  private scale = 1;

  constructor(
    private el: HTMLElement,
    private url: string,
    private sheet: SpriteSheet,
  ) {
    this.current = sheet.animations.idle;
    document.addEventListener("visibilitychange", () => this.sync());
  }

  /** Resolves once the sheet is loaded and laid out. */
  async start() {
    const img = new Image();
    img.src = this.url;
    await img.decode();
    const { frameWidth: fw, frameHeight: fh } = this.sheet;
    this.columns = Math.max(1, Math.floor(img.naturalWidth / fw));
    this.scale = Math.min(window.innerWidth / fw, window.innerHeight / fh);
    Object.assign(this.el.style, {
      width: `${fw * this.scale}px`,
      height: `${fh * this.scale}px`,
      backgroundImage: `url("${this.url}")`,
      backgroundSize: `${img.naturalWidth * this.scale}px ${img.naturalHeight * this.scale}px`,
      imageRendering: this.sheet.pixelated ? "pixelated" : "auto",
    });
    this.el.hidden = false;
    this.show(this.sheet.animations.idle, 0);
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

  happy() {
    const happy = this.sheet.animations.happy;
    if (happy && this.running && !this.ringing) this.play(happy);
  }

  /** Loops `animations.alarm` (or shakes the idle pose) until switched off. */
  setAlarm(on: boolean) {
    if (on === this.ringing) return;
    this.ringing = on;
    const alarm = this.sheet.animations.alarm;
    this.el.classList.toggle("shake", on && !alarm);
    this.stop();
    if (on) this.play(alarm ?? this.sheet.animations.idle);
    else this.sync();
  }

  private get running() {
    return !this.paused && !this.fullscreen && !document.hidden;
  }

  private stop() {
    clearInterval(this.timer);
    clearTimeout(this.timer);
    this.timer = undefined;
  }

  private sync() {
    if (this.ringing) return;
    if (!this.running) {
      this.stop();
      this.show(this.sheet.animations.idle, 0);
    } else if (this.timer === undefined) {
      this.play(this.sheet.animations.idle);
    }
  }

  private play(anim: SpriteAnimation) {
    this.stop();
    this.show(anim, 0);
    if (anim.frames <= 1) return; // a single idle frame needs no timer
    this.timer = window.setInterval(() => this.advance(), 1000 / anim.fps);
  }

  private advance() {
    const anim = this.current;
    if (this.frame + 1 < anim.frames) {
      this.show(anim, this.frame + 1);
      return;
    }
    const idle = this.sheet.animations.idle;
    if (this.ringing) {
      this.show(anim, 0); // alarm loops until stopped
    } else if (anim !== idle) {
      this.play(idle); // one-shot finished
    } else if (idle.pauseMs > 0) {
      this.stop();
      this.show(idle, 0);
      this.timer = window.setTimeout(() => {
        this.timer = undefined;
        if (this.running) this.play(idle);
      }, idle.pauseMs);
    } else {
      this.show(idle, 0);
    }
  }

  private show(anim: SpriteAnimation, frame: number) {
    this.current = anim;
    this.frame = frame;
    const index = anim.start + frame;
    const x = (index % this.columns) * this.sheet.frameWidth * this.scale;
    const y = Math.floor(index / this.columns) * this.sheet.frameHeight * this.scale;
    this.el.style.backgroundPosition = `-${x}px -${y}px`;
  }
}
