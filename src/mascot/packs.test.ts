// @vitest-environment happy-dom
// The bundled pets' data: every gesture has clips, zones sit on the pet, and
// the generated throw clips (scripts/make-throw-clips.py) animate validly.
import { describe, expect, test } from "vitest";

// Through Vite rather than node:fs, so this typechecks with the app (browser types).
const MANIFESTS = import.meta.glob<string>("../../assets/*/mascot.json", { query: "?raw", import: "default", eager: true });
const SVGS = import.meta.glob<string>(["../../assets/*/svg/*.svg", "../../assets/dragon/*.svg"], { query: "?raw", import: "default", eager: true });
const PACKS = Object.keys(MANIFESTS).map((path) => path.split("/")[3]);
const THROWS = ["thrown", "thrownLanded", "thrownUp", "thrownUpLanded", "thrownDown", "thrownDownLanded"];

interface Manifest {
  svgDir?: string;
  states: Record<string, string | string[]>;
  idleVariants?: string[];
  throwEffect?: boolean;
  zones?: { name: string; box: [number, number, number, number] }[];
}

function pack(id: string) {
  const m = JSON.parse(MANIFESTS[`../../assets/${id}/mascot.json`]) as Manifest;
  const dir = `../../assets/${id}/${m.svgDir ? `${m.svgDir}/` : ""}`;
  const list = (v: string | string[]) => (Array.isArray(v) ? v : [v]);
  const path = (entry: string) => dir + entry.split("@")[0];
  const svg = (entry: string) => SVGS[path(entry)] ?? "";
  return { m, dir, list, path, svg };
}

function viewBox(text: string): number[] {
  return (text.match(/viewBox="([^"]+)"/)?.[1] ?? "0 0 100 100").split(/[\s,]+/).map(Number);
}

test("there are pets to check", () => {
  expect(PACKS.length).toBeGreaterThanOrEqual(13);
});

describe.each(PACKS)("%s", (id) => {
  const { m, list, path, svg } = pack(id);

  test("every clip it names exists", () => {
    const entries = [...Object.values(m.states).flatMap(list), ...(m.idleVariants ?? [])];
    for (const e of entries) expect(path(e) in SVGS, e).toBe(true);
  });

  test("reacts to throws in every direction", () => {
    for (const s of THROWS) expect(m.states[s], s).toBeDefined();
  });

  test("a random mix of landings doesn't fire the effect timed to one clip", () => {
    const landings = list(m.states.thrownLanded ?? []);
    if (landings.length > 1) expect(m.throwEffect).toBe(false);
  });

  test("its body parts sit on the canvas and are known parts", () => {
    const vb = viewBox(svg(list(m.states.idle)[0]));
    for (const z of m.zones ?? []) {
      expect(["head", "belly", "tail", "feet"]).toContain(z.name);
      const [x0, y0, x1, y1] = z.box;
      expect(x0 < x1 && y0 < y1, z.name).toBe(true);
      expect(x0 >= vb[0] && y0 >= vb[1] && x1 <= vb[0] + vb[2] && y1 <= vb[1] + vb[3], `${z.name} inside the viewBox`).toBe(true);
      // A hover state for a part that's never marked out would never play, and vice versa.
      const state = `hover${z.name[0].toUpperCase()}${z.name.slice(1)}`;
      expect(m.states[state], state).toBeDefined();
    }
    for (const s of Object.keys(m.states).filter((k) => /^hover./.test(k))) {
      expect(m.zones?.some((z) => s === `hover${z.name[0].toUpperCase()}${z.name.slice(1)}`), `${s} needs a zone`).toBe(true);
    }
  });

  test("throw clips share the pet's canvas and parse", () => {
    const vb = viewBox(svg(list(m.states.idle)[0])).join(" ");
    for (const s of THROWS) {
      for (const e of list(m.states[s] ?? [])) {
        const text = svg(e);
        const doc = new DOMParser().parseFromString(text, "image/svg+xml");
        expect(doc.querySelector("parsererror"), e).toBeNull();
        expect(viewBox(text).join(" "), e).toBe(vb);
        expect(text.slice(0, 400), `${e} has its timing`).toMatch(/data-frames="[\d.]+"/);
      }
    }
  });
});

describe("generated throw clips", () => {
  const files = PACKS.flatMap((id) => {
    const { dir } = pack(id);
    return Object.entries(SVGS)
      .filter(([path]) => path.startsWith(dir) && /^(throw_|land_)\w+\.svg$/.test(path.slice(dir.length)))
      .map(([path, text]) => [`${id}/${path.slice(dir.length)}`, text] as const);
  });

  test("every pet has its set (the ninja its hand-made ones)", () => {
    expect(files.length).toBeGreaterThanOrEqual(12 * 7);
  });

  test.each(files)("%s animates validly", (_, text) => {
    const loop = /data-loop="true"/.test(text);
    expect(loop, "flights loop, landings play once").toBe(/(\/|^)throw_/.test(_) || /thrown_/.test(text.slice(0, 200)));
    for (const tag of text.match(/<animate(Transform)?\b[^>]*>/g) ?? []) {
      const attr = (n: string) => tag.match(new RegExp(`${n}="([^"]*)"`))?.[1];
      const times = attr("keyTimes")?.split(";").map(Number);
      const values = attr("values")?.split(";");
      if (!times || !values) continue;
      expect(times.length, tag).toBe(values.length);
      expect(times[0], tag).toBe(0);
      // Discrete steps may stop short of the end; interpolated ones must reach it.
      if (attr("calcMode") !== "discrete") expect(times[times.length - 1], tag).toBe(1);
      expect(times[times.length - 1], tag).toBeLessThanOrEqual(1);
      for (let i = 1; i < times.length; i++) expect(times[i] >= times[i - 1], tag).toBe(true);
      if (attr("calcMode") === "spline") expect(attr("keySplines")!.split(";").length, tag).toBe(values.length - 1);
      for (const v of values) expect(v, tag).not.toMatch(/NaN|Infinity/);
    }
  });
});
