// @vitest-environment happy-dom
// The pet's state machine, driven the way main.ts drives it from the Rust
// events: hover and body parts, drags and throws, clicks, alarms, sleep.
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { SvgStateAnimator } from "./svgstates";
import type { MascotZone } from "../lib/ipc";

/** A clip that is 1 s long (30 frames) unless told otherwise. */
function clip(name: string, { frames = 30, loop = true } = {}) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" data-clip="${name}" data-frames="${frames}" data-fps="30" data-loop="${loop}"><rect width="10" height="10"><animate attributeName="x" values="0;5;0" dur="1s" repeatCount="indefinite"/></rect></svg>`;
}

const FULL: Record<string, string[]> = {
  idle: ["idle.svg"],
  hover: ["hover.svg"],
  hoverHead: ["head_a.svg", "head_b.svg", "head_c.svg"],
  hoverBelly: ["belly.svg"],
  hoverTail: ["tail.svg"],
  doubleClick: ["double.svg"],
  clicks: ["clicks.svg"],
  done: ["done.svg"],
  alarm: ["alarm.svg"],
  alarmClosed: ["alarm_closed.svg"],
  dragged: ["dragged.svg"],
  falling: ["falling.svg"],
  dropped: ["land.svg@0.5"],
  thrown: ["tumble.svg"],
  thrownLanded: ["land_side.svg"],
  thrownUp: ["whee.svg"],
  thrownUpLanded: ["land_up.svg"],
  thrownDown: ["dive.svg"],
  thrownDownLanded: ["splat.svg"],
  fallAsleep: ["fall_asleep.svg"],
  sleep: ["sleep.svg"],
  wakeUp: ["wake_up.svg"],
  lookLeft: ["look_left.svg"],
};
const ONE_SHOT = new Set(["land.svg", "land_side.svg", "land_up.svg", "splat.svg", "fall_asleep.svg", "wake_up.svg"]);

/** Head on top, belly below, tail on the right (overlapping the belly, so listed first). */
const ZONES: MascotZone[] = [
  { name: "tail", box: [80, 50, 100, 100] },
  { name: "head", box: [10, 0, 90, 50] },
  { name: "belly", box: [10, 50, 80, 100] },
];

function clipsFor(states: Record<string, string[]>) {
  const files = new Set(Object.values(states).flat().map((e) => e.split("@")[0]));
  return Object.fromEntries([...files].map((f) => [f, clip(f.replace(".svg", ""), ONE_SHOT.has(f) ? { frames: 60, loop: false } : {})]));
}

let el: HTMLElement;

function pet(states = FULL, { zones = ZONES, sleepAfter = 0 } = {}) {
  return new SvgStateAnimator(el, clipsFor(states), states, [], sleepAfter, () => null, zones);
}

/** The clip on screen: the newest layer (an older one may still be fading out under it). */
function shown(): string {
  const layers = el.querySelectorAll(".clip svg");
  return layers[layers.length - 1]?.getAttribute("data-clip") ?? "";
}
const flipped = () => el.classList.contains("flipped");
const wait = (ms: number) => vi.advanceTimersByTime(ms);

/** The window is 200 px showing the 100-unit viewBox; CSS mirroring flips it. */
function screenMapping() {
  vi.spyOn(SVGSVGElement.prototype, "getScreenCTM").mockImplementation(() =>
    el.classList.contains("flipped") ? new DOMMatrix([-2, 0, 0, 2, 200, 0]) : new DOMMatrix([2, 0, 0, 2, 0, 0]),
  );
}
// Window px for a viewBox point, unmirrored.
const at = (x: number, y: number): [number, number] => [x * 2, y * 2];

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "performance"] });
  el = document.createElement("div");
  document.body.append(el);
  screenMapping();
});
afterEach(() => {
  el.remove();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("resting", () => {
  test("idles when nothing happens", () => {
    pet();
    expect(shown()).toBe("idle");
    wait(60_000);
    expect(shown()).toBe("idle");
  });

  test("an intro plays first, then idle", () => {
    pet({ ...FULL, intro: ["fall_asleep.svg"] });
    expect(shown()).toBe("fall_asleep");
    wait(2100);
    expect(shown()).toBe("idle");
  });

  test("eyes follow a nearby pointer, but hover wins", () => {
    const p = pet();
    p.look("lookLeft");
    expect(shown()).toBe("look_left");
    p.setHover(true);
    expect(shown()).toBe("hover");
    p.look("");
    p.setHover(false);
    wait(300);
    expect(shown()).toBe("idle");
  });
});

describe("hover and body parts", () => {
  test("plain hover, and a short leave-and-return counts as one hover", () => {
    const p = pet(FULL, { zones: [] });
    p.setHover(true);
    expect(shown()).toBe("hover");
    p.setHover(false);
    wait(100);
    p.setHover(true);
    wait(500);
    expect(shown()).toBe("hover");
    p.setHover(false);
    wait(249);
    expect(shown()).toBe("hover");
    wait(2);
    expect(shown()).toBe("idle");
  });

  test("the first position reacts straight away", () => {
    const p = pet();
    p.setHover(true);
    p.pointer(...at(85, 80));
    expect(shown()).toBe("tail");
  });

  test("the tail wins where it overlaps the belly", () => {
    const p = pet();
    p.setHover(true);
    p.pointer(...at(85, 60));
    expect(shown()).toBe("tail");
  });

  test("off every part: the plain hover", () => {
    const p = pet();
    p.setHover(true);
    p.pointer(...at(2, 2));
    expect(shown()).toBe("hover");
  });

  test("moving to another part switches after the pointer settles there", () => {
    const p = pet();
    p.setHover(true);
    p.pointer(...at(50, 20));
    expect(shown()).toMatch(/^head_/);
    p.pointer(...at(40, 80));
    wait(149);
    expect(shown()).toMatch(/^head_/);
    wait(1);
    expect(shown()).toBe("belly");
  });

  test("brushing across a border and back doesn't flicker", () => {
    const p = pet();
    p.setHover(true);
    p.pointer(...at(50, 45));
    const head = shown();
    p.pointer(...at(50, 55));
    wait(100);
    p.pointer(...at(50, 45));
    wait(500);
    expect(shown()).toBe(head);
  });

  test("a part without its own clips falls back to the plain hover", () => {
    const { hoverBelly: _, ...noBelly } = FULL;
    const p = pet(noBelly);
    p.setHover(true);
    p.pointer(...at(40, 80));
    expect(shown()).toBe("hover");
  });

  test("a pet without zones ignores the pointer", () => {
    const p = pet(FULL, { zones: [] });
    p.setHover(true);
    p.pointer(...at(85, 80));
    wait(500);
    expect(shown()).toBe("hover");
  });

  test("leaving forgets the part; coming back on another reacts to that one", () => {
    const p = pet();
    p.setHover(true);
    p.pointer(...at(85, 80));
    p.setHover(false);
    wait(300);
    expect(shown()).toBe("idle");
    p.setHover(true);
    p.pointer(...at(40, 80));
    expect(shown()).toBe("belly");
  });

  test("a part's clips are picked at random, never the same twice in a row", () => {
    const p = pet();
    const seen: string[] = [];
    for (let i = 0; i < 12; i++) {
      p.setHover(true);
      p.pointer(...at(50, 20));
      seen.push(shown());
      p.setHover(false);
      wait(300);
    }
    for (let i = 1; i < seen.length; i++) expect(seen[i]).not.toBe(seen[i - 1]);
    expect(new Set(seen).size).toBeGreaterThan(1);
  });

  test("a reaction (double-click) plays over the part's clip, then it comes back", () => {
    const p = pet();
    p.setHover(true);
    p.pointer(...at(85, 80));
    p.clicks(2);
    expect(shown()).toBe("double");
    wait(2100);
    expect(shown()).toBe("tail");
  });
});

describe("dragging and throwing", () => {
  test("picked up, put down", () => {
    const p = pet();
    p.dragStart();
    expect(shown()).toBe("dragged");
    p.landed();
    expect(shown()).toBe("land");
    wait(1600);
    expect(shown()).toBe("idle");
  });

  test("let go up high: falls, then lands", () => {
    const p = pet();
    p.dragStart();
    p.falling();
    expect(shown()).toBe("falling");
    p.landed();
    expect(shown()).toBe("land");
  });

  test("thrown right: tumbles facing right, lands facing back (left)", () => {
    const p = pet();
    p.dragStart();
    p.thrown(1, "side");
    expect([shown(), flipped()]).toEqual(["tumble", false]);
    p.landed();
    expect([shown(), flipped()]).toEqual(["land_side", true]);
    wait(2100);
    expect([shown(), flipped()]).toEqual(["idle", false]);
  });

  test("thrown left: mirrored in the air, lands facing right", () => {
    const p = pet();
    p.dragStart();
    p.thrown(-1, "side");
    expect([shown(), flipped()]).toEqual(["tumble", true]);
    p.landed();
    expect([shown(), flipped()]).toEqual(["land_side", false]);
  });

  test("thrown straight up: whee, then its own landing, never mirrored", () => {
    const p = pet();
    p.dragStart();
    p.thrown(0, "up");
    expect([shown(), flipped()]).toEqual(["whee", false]);
    p.landed();
    expect([shown(), flipped()]).toEqual(["land_up", false]);
  });

  test("thrown up-left: mirrored in the air, lands facing back", () => {
    const p = pet();
    p.dragStart();
    p.thrown(-1, "up");
    expect([shown(), flipped()]).toEqual(["whee", true]);
    p.landed();
    expect([shown(), flipped()]).toEqual(["land_up", false]);
  });

  test("thrown down-right: dives, then splats facing back", () => {
    const p = pet();
    p.dragStart();
    p.thrown(1, "down");
    expect([shown(), flipped()]).toEqual(["dive", false]);
    p.landed();
    expect([shown(), flipped()]).toEqual(["splat", true]);
  });

  test("a pet without up/down clips falls back to falling and the plain landing", () => {
    const only = Object.fromEntries(Object.entries(FULL).filter(([k]) => !/^thrown(Up|Down)/.test(k)));
    const p = pet(only);
    p.dragStart();
    p.thrown(0, "up");
    expect([shown(), flipped()]).toEqual(["falling", false]);
    p.landed();
    expect(shown()).toBe("land");
    p.dragStart();
    p.thrown(1, "down");
    expect(shown()).toBe("falling");
  });

  test("a pet with nothing for carrying stays on idle and lands plainly", () => {
    const p = pet({ idle: ["idle.svg"], dropped: ["land.svg"] });
    p.dragStart();
    p.thrown(1, "up");
    expect(shown()).toBe("idle");
    p.landed();
    expect(shown()).toBe("land");
  });

  test("throw and landing events without a drag are ignored", () => {
    const p = pet();
    p.thrown(1, "side");
    p.landed();
    expect(shown()).toBe("idle");
  });

  test("an unknown kind of throw counts as sideways", () => {
    const p = pet();
    p.dragStart();
    p.thrown(1, "sideways?" as never);
    expect(shown()).toBe("tumble");
  });

  test("picked up again mid-landing: the landing stops", () => {
    const p = pet();
    p.dragStart();
    p.thrown(-1, "side");
    p.landed();
    p.dragStart();
    expect([shown(), flipped()]).toEqual(["dragged", false]);
  });

  test("a landing played as a chat reaction faces forward, even after a throw", () => {
    const p = pet();
    p.dragStart();
    p.thrown(1, "side");
    p.landed();
    wait(2100);
    p.react("thrownLanded");
    expect([shown(), flipped()]).toEqual(["land_side", false]);
  });

  test("a landing previewed from Settings faces forward", () => {
    const p = pet();
    p.dragStart();
    p.thrown(1, "down");
    p.landed();
    wait(2100);
    p.preview("thrownDownLanded");
    expect([shown(), flipped()]).toEqual(["splat", false]);
  });

  test("hovering a mirrored landing reads the parts mirrored, and re-reads them when it turns back", () => {
    const p = pet();
    p.dragStart();
    p.thrown(1, "side");
    p.landed();
    expect(flipped()).toBe(true);
    // The tail is drawn on the left now: x 85 of the viewBox is at window px 30.
    p.setHover(true);
    p.pointer(30, 160);
    wait(2100);
    expect(flipped()).toBe(false);
    // Same pointer spot, pet facing right again: that's the belly.
    expect(shown()).toBe("belly");
  });
});

describe("poked by a friend", () => {
  test("plays the pet's poke reaction, then goes back to what it was doing", () => {
    const p = pet({ ...FULL, poke: ["poke_jump.svg"] });
    p.react("poke");
    expect(shown()).toBe("poke_jump");
    wait(3100);
    expect(shown()).toBe("idle");
  });

  test("a pet without a poke clip uses its click reaction", () => {
    const p = pet();
    p.react("poke");
    expect(shown()).toBe("clicks");
  });

  test("…or its double-click one", () => {
    const { clicks: _, ...noClicks } = FULL;
    const p = pet(noClicks);
    p.react("poke");
    expect(shown()).toBe("double");
  });

  test("wakes a sleeping pet", () => {
    const p = pet({ ...FULL, poke: ["poke_jump.svg"] }, { sleepAfter: 20 });
    wait(23_000);
    expect(shown()).toBe("sleep");
    p.react("poke");
    expect(shown()).toBe("poke_jump");
  });
});

describe("clicks, alarms and sleep", () => {
  test("double click and a click spree", () => {
    const p = pet();
    p.clicks(1);
    expect(shown()).toBe("idle");
    p.clicks(2);
    expect(shown()).toBe("double");
    p.clicks(3);
    expect(shown()).toBe("clicks");
  });

  test("an alarm beats being carried and hovered; stopping it plays its reaction", () => {
    const p = pet();
    p.setHover(true);
    p.dragStart();
    p.setAlarm(true);
    expect(shown()).toBe("alarm");
    p.landed();
    p.setAlarm(false);
    expect(shown()).toBe("alarm_closed");
  });

  test("dozes off when left alone, wakes on a 1.5 s hover only", () => {
    const p = pet(FULL, { sleepAfter: 20 });
    wait(20_000);
    expect(shown()).toBe("fall_asleep");
    wait(2100);
    expect(shown()).toBe("sleep");
    p.setHover(true);
    wait(1000);
    p.setHover(false);
    wait(1000);
    expect(shown()).toBe("sleep");
    p.setHover(true);
    wait(1500);
    expect(shown()).toBe("wake_up");
  });

  test("a click wakes it at once", () => {
    const p = pet(FULL, { sleepAfter: 20 });
    wait(23_000);
    expect(shown()).toBe("sleep");
    p.clicks(1);
    expect(shown()).toBe("wake_up");
  });

  test("doesn't doze off while hovered or carried", () => {
    const p = pet(FULL, { sleepAfter: 20 });
    p.setHover(true);
    wait(45_000);
    expect(shown()).not.toMatch(/sleep/);
    p.setHover(false);
    p.dragStart();
    wait(45_000);
    expect(shown()).toBe("dragged");
  });
});
