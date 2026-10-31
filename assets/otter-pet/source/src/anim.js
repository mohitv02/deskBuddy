// Keyframe model + Lottie (bodymovin 5.7) and SMIL SVG exporters driven by the same data.
const { svgD, r2 } = require('./geom');

const EASE = [0.42, 0, 0.58, 1];
const EASES = { io: EASE, soft: [0.37, 0, 0.63, 1], strong: [0.65, 0, 0.35, 1] };
const PROPS = ['p', 's', 'r', 'o'];
const clone = (v) => (Array.isArray(v) ? v.slice() : v);
const add = (a, b) => (Array.isArray(a) ? a.map((x, i) => x + b[i]) : a + b);
const eq = (a, b) => (Array.isArray(a) ? a.every((x, i) => Math.abs(x - b[i]) < 1e-6) : Math.abs(a - b) < 1e-6);

function bez(e, x) { // cubic-bezier timing (x->y)
  const [x1, y1, x2, y2] = e;
  const B = (a, b, t) => 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3;
  let lo = 0, hi = 1, t = x;
  for (let k = 0; k < 40; k++) { t = (lo + hi) / 2; if (B(x1, x2, t) < x) lo = t; else hi = t; }
  return B(y1, y2, t);
}

function indexNodes(layers) {
  const map = {};
  const walk = (n, parent) => { if (map[n.id]) throw new Error('dup id ' + n.id); map[n.id] = n; n.parent = parent; for (const it of n.items) if (!it.shape) walk(it, n); };
  layers.forEach((l) => walk(l, null));
  return map;
}

class Clip {
  constructor(rig, poses, meta) {
    this.rig = rig; this.poses = poses; this.meta = meta; this.N = meta.frames;
    this.basePose = poses[meta.base] || {};
    this.tracks = {}; this.fx = [];
    this.nodes = indexNodes(rig.layers);
  }
  base(id, prop) {
    const n = this.nodes[id]; if (!n) throw new Error(`${this.meta.name}: no node ${id}`);
    const o = this.basePose[id];
    return clone(o && o[prop] !== undefined ? o[prop] : n[prop]);
  }
  poseVal(pose, id, prop) { const o = this.poses[pose][id]; const n = this.nodes[id]; return clone(o && o[prop] !== undefined ? o[prop] : n[prop]); }
  track(path, mode) {
    const [id, prop] = path.split('.');
    if (!this.nodes[id]) throw new Error(`${this.meta.name}: no node ${id}`);
    let t = this.tracks[path];
    if (!t) t = this.tracks[path] = { id, prop, mode, keys: [] };
    if (t.mode !== mode) throw new Error(`${this.meta.name}: mixed modes on ${path}`);
    return t;
  }
  _put(t, key) { const i = t.keys.findIndex((k) => Math.abs(k.t - key.t) < 1e-6); if (i >= 0) t.keys[i] = key; else t.keys.push(key); t.keys.sort((a, b) => a.t - b.t); }
  // absolute eased keys: [[t, v, ease?], ...]
  k(path, keys) { const t = this.track(path, 'ease'); for (const [tt, v, e] of keys) this._put(t, { t: tt, v: clone(v), e: typeof e === 'string' ? EASES[e] : e || EASE }); return this; }
  // relative to base
  rk(path, keys) { const [id, prop] = path.split('.'); const b = this.base(id, prop); return this.k(path, keys.map(([t, v, e]) => [t, add(b, v), e])); }
  h(path, keys) { const t = this.track(path, 'hold'); for (const [tt, v] of keys) this._put(t, { t: tt, v: clone(v) }); return this; }
  // value of a property at time t given current keys (or base)
  at(path, time) {
    const [id, prop] = path.split('.'); const t = this.tracks[path];
    if (!t || !t.keys.length) return this.base(id, prop);
    const ks = t.keys;
    if (time <= ks[0].t) return clone(ks[0].v);
    if (time >= ks[ks.length - 1].t) return clone(ks[ks.length - 1].v);
    let i = 0; while (ks[i + 1].t < time) i++;
    const a = ks[i], b = ks[i + 1];
    if (t.mode === 'hold') return clone(a.v);
    const y = bez(a.e, (time - a.t) / (b.t - a.t));
    return Array.isArray(a.v) ? a.v.map((x, j) => x + (b.v[j] - x) * y) : a.v + (b.v - a.v) * y;
  }
  // ease every prop that differs between current state and pose `name` from t0 to t1.
  // opacity props switch (hold) at `swap` (default t1).
  toPose(name, t0, t1, { e, swap, only, except } = {}) {
    const target = this.poses[name];
    const trackIds = Object.values(this.tracks).map((t) => t.id).filter((id) => !this.fx.includes(this.nodes[id]));
    const ids = new Set([...Object.keys(target), ...Object.keys(this.basePose), ...trackIds]);
    for (const id of ids) {
      if (only && !only.includes(id)) continue; if (except && except.includes(id)) continue;
      for (const prop of PROPS) {
        const path = `${id}.${prop}`;
        const goal = this.poseVal(name, id, prop), cur = this.at(path, t0);
        if (eq(goal, cur)) continue;
        if (prop === 'o') this.h(path, [[t0, cur], [swap ?? t1, goal]]);
        else this.k(path, [[t0, cur, e], [t1, goal]]);
      }
    }
    return this;
  }
  poseAt(name, t) {
    const target = this.poses[name];
    const trackIds = Object.values(this.tracks).map((x) => x.id).filter((id) => !this.fx.includes(this.nodes[id]));
    const ids = new Set([...Object.keys(target), ...Object.keys(this.basePose), ...trackIds]);
    for (const id of ids) for (const prop of PROPS) {
      const goal = this.poseVal(name, id, prop), cur = this.at(`${id}.${prop}`, t);
      if (eq(goal, cur) && !this.tracks[`${id}.${prop}`]) continue;
      if (prop === 'o') this.h(`${id}.${prop}`, [[t, goal]]); else this.k(`${id}.${prop}`, [[t, goal]]);
    }
    return this;
  }
  // face state switches at time t: {eyes, eyeL, eyeR, mouth, brows}
  face(t, st) {
    const EYES = ['open', 'sleepy', 'happy', 'squint', 'wink', 'heart', 'dizzy'];
    const MOUTHS = ['smile', 'open', 'o', 'yawn', 'frown', 'grin'];
    const set = (prefix, list, v) => { for (const x of list) this.h(`${prefix}${x}.o`, [[t, x === v ? 100 : 0]]); };
    const eL = st.eyeL || st.eyes, eR = st.eyeR || st.eyes;
    if (eL) set('eyeL_', EYES, eL);
    if (eR) set('eyeR_', EYES, eR);
    if (st.mouth) set('mouth_', MOUTHS, st.mouth);
    if (st.brows !== undefined) { this.h('brow_worried.o', [[t, st.brows === 'worried' ? 100 : 0]]); this.h('brow_angry.o', [[t, st.brows === 'angry' ? 100 : 0]]); }
    return this;
  }
  // keep a face state in place at frame 0 (so later switches have a defined start)
  faceStart(st) { return this.face(0, st); }
  blink(t, d = 3) { for (const s of ['L', 'R']) { const v = this.at(`eye${s}_open.s`, t); this.k(`eye${s}_open.s`, [[t, v], [t + d, [v[0], v[1] * 0.08]], [t + 2 * d, v]]); } return this; }
  addFx(n) { this.fx.push(n); this.nodes[n.id] = n; n.parent = null; return n; }

  finalize() {
    const N = this.N; const errs = [];
    for (const [path, t] of Object.entries(this.tracks)) {
      const ks = t.keys;
      if (ks[0].t > 0) ks.unshift({ t: 0, v: t.mode === 'hold' ? this.base(t.id, t.prop) : clone(ks[0].v), e: EASE });
      if (ks[ks.length - 1].t < N) ks.push({ t: N, v: clone(ks[ks.length - 1].v), e: EASE });
      for (const k of ks) if (k.t < 0 || k.t > N) throw new Error(`${this.meta.name}: key out of range ${path} ${k.t}`);
      if (this.meta.loop) {
        const b = this.base(t.id, t.prop);
        const eqm = (a, c) => (t.prop === 'r' ? Math.abs(((a - c) % 360 + 360) % 360) < 1e-6 || Math.abs(((a - c) % 360 + 360) % 360 - 360) < 1e-6 : eq(a, c));
        if (!this.fx.includes(this.nodes[t.id]) && (!eqm(ks[0].v, b) || !eqm(ks[ks.length - 1].v, b))) {
          errs.push(`${this.meta.name}: loop track ${path} doesn't start/end at base (${JSON.stringify(ks[0].v)} / ${JSON.stringify(ks[ks.length - 1].v)} vs ${JSON.stringify(b)})`); continue;
        }
        if (!eqm(ks[0].v, ks[ks.length - 1].v)) errs.push(`${this.meta.name}: loop seam on ${path} ${JSON.stringify(ks[0].v)} / ${JSON.stringify(ks[ks.length - 1].v)}`);
      }
    }
    if (errs.length) throw new Error(errs.join('\n'));
    return this;
  }
}

// ---------------- exporters ----------------
const hex = (h) => [1, 3, 5].map((i) => r2(parseInt(h.slice(i, i + 2), 16) / 255 * 1000) / 1000);
const R3 = (n) => Math.round(n * 1000) / 1000;

function layersFor(clip) {
  const [shadow, character, water, fx] = clip.rig.layers;
  const fxNode = { ...fx, items: clip.fx };
  return [shadow, character, water, fxNode];
}

function valOf(clip, id, prop) { return clip.base(id, prop); }

function toLottie(clip) {
  const N = clip.N;
  const tr = (n) => {
    const P = (prop, dim) => {
      const t = clip.tracks[`${n.id}.${prop}`];
      const conv = (v) => (Array.isArray(v) ? v.map(R3) : [R3(v)]);
      if (!t) { const v = valOf(clip, n.id, prop); return { a: 0, k: Array.isArray(v) ? v.map(R3) : R3(v) }; }
      const ks = t.keys;
      return {
        a: 1, k: ks.map((k, i) => {
          if (i === ks.length - 1) return { t: R3(k.t), s: conv(k.v) };
          const o = { t: R3(k.t), s: conv(k.v) };
          if (t.mode === 'hold') o.h = 1;
          else { o.o = { x: Array(dim).fill(k.e[0]), y: Array(dim).fill(k.e[1]) }; o.i = { x: Array(dim).fill(k.e[2]), y: Array(dim).fill(k.e[3]) }; }
          return o;
        }),
      };
    };
    return { ty: 'tr', p: P('p', 2), a: { a: 0, k: n.a.map(R3) }, s: P('s', 2), r: P('r', 1), o: P('o', 1), sk: { a: 0, k: 0 }, sa: { a: 0, k: 0 }, nm: 'Transform' };
  };
  const idTr = () => ({ ty: 'tr', p: { a: 0, k: [0, 0] }, a: { a: 0, k: [0, 0] }, s: { a: 0, k: [100, 100] }, r: { a: 0, k: 0 }, o: { a: 0, k: 100 }, sk: { a: 0, k: 0 }, sa: { a: 0, k: 0 }, nm: 'Transform' });
  const shapeItem = (s) => {
    const it = s.paths.map((p, i) => ({ ty: 'sh', ind: i, ks: { a: 0, k: p }, nm: 'Path ' + (i + 1), hd: false }));
    if (s.stroke) it.push({ ty: 'st', c: { a: 0, k: [...hex(s.stroke), 1] }, o: { a: 0, k: 100 }, w: { a: 0, k: s.sw }, lc: 2, lj: 2, bm: 0, nm: 'Stroke', hd: false });
    if (s.fill) it.push({ ty: 'fl', c: { a: 0, k: [...hex(s.fill), 1] }, o: { a: 0, k: R3((s.fo ?? 1) * 100) }, r: 1, bm: 0, nm: 'Fill', hd: false });
    it.push(idTr());
    return { ty: 'gr', it, nm: 'shape', np: it.length - 1, bm: 0, hd: false };
  };
  const group = (n) => {
    const it = n.items.slice().reverse().map((x) => (x.shape ? shapeItem(x) : group(x)));
    it.push(tr(n));
    return { ty: 'gr', it, nm: n.id, np: it.length - 1, bm: 0, hd: false };
  };
  const layers = layersFor(clip).reverse().map((n, i) => ({
    ddd: 0, ind: i + 1, ty: 4, nm: n.id, sr: 1,
    ks: { o: { a: 0, k: 100 }, r: { a: 0, k: 0 }, p: { a: 0, k: [0, 0, 0] }, a: { a: 0, k: [0, 0, 0] }, s: { a: 0, k: [100, 100, 100] } },
    ao: 0, shapes: [group(n)], ip: 0, op: N, st: 0, bm: 0,
  }));
  return JSON.parse(JSON.stringify({ v: '5.7.4', fr: 30, ip: 0, op: N, w: 512, h: 512, nm: clip.meta.name, ddd: 0, assets: [], layers, markers: [] }));
}

function toSVG(clip) {
  const N = clip.N, dur = `${R3(N / 30)}s`, loop = clip.meta.loop;
  const timing = `begin="0s" dur="${dur}" ${loop ? 'repeatCount="indefinite"' : 'fill="freeze"'}`;
  const f = (n) => String(R3(n));
  const vstr = (prop, v) => {
    if (prop === 'p') return `${f(v[0])} ${f(v[1])}`;
    if (prop === 's') return `${f(v[0] / 100)} ${f(v[1] / 100)}`;
    if (prop === 'r') return f(v);
    return f(v / 100);
  };
  const anim = (t) => {
    const ks = t.keys;
    const kt = ks.map((k) => f(k.t / N)).join(';');
    const vals = ks.map((k) => vstr(t.prop, k.v)).join(';');
    const mode = t.mode === 'hold' ? 'calcMode="discrete"' : `calcMode="spline" keySplines="${ks.slice(0, -1).map((k) => k.e.join(' ')).join(';')}"`;
    if (t.prop === 'o') return `<animate attributeName="opacity" ${timing} ${mode} keyTimes="${kt}" values="${vals}"/>`;
    const type = { p: 'translate', s: 'scale', r: 'rotate' }[t.prop];
    return `<animateTransform attributeName="transform" type="${type}" additive="sum" ${timing} ${mode} keyTimes="${kt}" values="${vals}"/>`;
  };
  const shapeEl = (s) => {
    const d = svgD(s.paths);
    let a = `d="${d}"`;
    a += s.fill ? ` fill="${s.fill}"` : ' fill="none"';
    if (s.fill && s.fo !== undefined && s.fo !== 1) a += ` fill-opacity="${s.fo}"`;
    if (s.stroke) a += ` stroke="${s.stroke}" stroke-width="${s.sw}"`;
    return `<path ${a}/>`;
  };
  const nodeEl = (n, isLayer) => {
    const T = (prop) => clip.tracks[`${n.id}.${prop}`];
    const p = valOf(clip, n.id, 'p'), r = valOf(clip, n.id, 'r'), s = valOf(clip, n.id, 's'), o = valOf(clip, n.id, 'o');
    const ops = [];
    ops.push({ prop: 'p', anim: T('p'), str: (p[0] || p[1]) ? `translate(${f(p[0])} ${f(p[1])})` : '' });
    ops.push({ prop: 'r', anim: T('r'), str: r ? `rotate(${f(r)})` : '' });
    ops.push({ prop: 's', anim: T('s'), str: (s[0] !== 100 || s[1] !== 100) ? `scale(${f(s[0] / 100)} ${f(s[1] / 100)})` : '' });
    ops.push({ prop: 'a', anim: null, str: (n.a[0] || n.a[1]) ? `translate(${f(-n.a[0])} ${f(-n.a[1])})` : '' });
    const groups = [{ st: [], anim: null }];
    for (const op of ops) {
      let g = groups[groups.length - 1];
      if (g.anim) { g = { st: [], anim: null }; groups.push(g); }
      if (op.anim) g.anim = op.anim; else if (op.str) g.st.push(op.str);
    }
    const oT = T('o');
    let open = '', close = '';
    groups.forEach((g, i) => {
      let attrs = '';
      if (i === 0 && isLayer) attrs += ` id="${n.id}"`;
      if (i === 0 && !oT && o !== 100) attrs += ` opacity="${f(o / 100)}"`;
      if (g.st.length) attrs += ` transform="${g.st.join(' ')}"`;
      const inner = (i === 0 && oT ? anim(oT) : '') + (g.anim ? anim(g.anim) : '');
      if (!attrs && !inner && !(i === 0)) return;
      open += `<g${attrs}>${inner}`; close = '</g>' + close;
    });
    const kids = n.items.map((x) => (x.shape ? shapeEl(x) : nodeEl(x, false))).join('');
    return open + kids + close;
  };
  const body = layersFor(clip).map((l) => nodeEl(l, true)).join('\n');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" stroke-linecap="round" stroke-linejoin="round">\n<title>${clip.meta.name}</title>\n${body}\n</svg>\n`;
}

module.exports = { Clip, toLottie, toSVG, EASE, EASES, bez, indexNodes };
