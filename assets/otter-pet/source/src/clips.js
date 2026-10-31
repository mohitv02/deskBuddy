// All clip choreography. Times are frames @30fps. Design coords unless noted "canvas".
const { FX, node } = require('./rig');
const { poses, headAt, pawTo, pawTip, DIRS } = require('./poses');

const add = (a, b) => a.map((x, i) => x + b[i]);
const cv = (x, y) => [256 + 0.8 * (x - 256), 470 + 0.8 * (y - 470)]; // design -> canvas (character at rest)

// ---------- helpers ----------
// ease every given prop from its current value at t0 to the target at t1
function go(c, t0, t1, obj, e) {
  for (const [id, props] of Object.entries(obj)) {
    for (const [prop, v] of Object.entries(props)) {
      const path = `${id}.${prop}`;
      if (prop === 'o') { c.h(path, [[t0, v]]); continue; }
      c.k(path, [[t0, c.at(path, t0), e], [t1, v]]);
    }
  }
}
// oscillation around the value the property has at t0; returns to it after the last value
function wig(c, path, t0, step, vals, e) {
  const center = c.at(path, t0);
  const A = (v) => (Array.isArray(center) ? center.map((x, i) => x + v[i]) : center + v);
  const keys = [[t0, center, e]];
  vals.forEach((v, i) => keys.push([t0 + step * (i + 1), A(v), e]));
  keys.push([t0 + step * (vals.length + 1), center]);
  c.k(path, keys);
}
const alt = (n, a, b = -a) => Array.from({ length: n }, (_, i) => (i % 2 ? b : a));
function look(c, t0, t1, d, k = 1) {
  const [dx, dy] = d;
  go(c, t0, t1, {
    eyeL: { p: add(c.base('eyeL', 'p'), [10 * dx * k, 8 * dy * k]) },
    eyeR: { p: add(c.base('eyeR', 'p'), [10 * dx * k, 8 * dy * k]) },
    faceShift: { p: add(c.base('faceShift', 'p'), [5 * dx * k, 3 * dy * k]) },
  });
}
function lookBack(c, t0, t1) { go(c, t0, t1, { eyeL: { p: c.base('eyeL', 'p') }, eyeR: { p: c.base('eyeR', 'p') }, faceShift: { p: c.base('faceShift', 'p') } }); }
const pawState = (c, id, t) => ({ p: c.at(`${id}.p`, t), r: c.at(`${id}.r`, t), s: c.at(`${id}.s`, t) });
// world position of the pebble held in the right mitten at time t
function heldPos(c, t) { const s = pawState(c, 'pawR', t); return pawTip(s.p, s.r, s.s, 66); }
function grabR(c, t0, t1) { // free pebble glides into the right paw, then swaps to the held copy
  go(c, t0, t1, { pebble: { p: heldPos(c, t1) } });
  c.h('pebble.o', [[t1, 0]]); c.h('pebbleHeld.o', [[t1, 100]]);
}
function releaseR(c, t, t1, target) {
  c.k('pebble.p', [[t, heldPos(c, t)]]);
  c.h('pebble.o', [[t, 100]]); c.h('pebbleHeld.o', [[t, 0]]);
  if (target) go(c, t, t1, { pebble: { p: target } });
}

let fxn = 0;
function fx(c, make, at, t0, t1, o = {}) {
  const id = `${make.name || 'fx'}${++fxn}`;
  const n = c.addFx(make(id));
  n.p = at.slice(); n.a = [0, 0];
  const size = o.size || 100, pin = o.pin || 5, pout = o.pout || 5;
  const s = Array.isArray(size) ? size : [size, size];
  const keys = [[t0, [0, 0]], [t0 + pin, s]];
  if (o.pulse) { let t = t0 + pin; let up = true; while (t + o.pulse < t1 - pout) { t += o.pulse; keys.push([t, up ? s.map((x) => x * 1.15) : s]); up = !up; } }
  keys.push([t1 - pout, s], [t1, [0, 0]]);
  c.k(`${n.id}.s`, keys);
  const N = c.N;
  if (o.drift) {
    c.k(`${n.id}.p`, [[t0, at], [t1, add(at, o.drift)]]);
    if (t1 + 0.5 <= N) c.k(`${n.id}.p`, [[t1 + 0.5, at]]);
  }
  if (o.rot) {
    c.k(`${n.id}.r`, [[t0, -o.rot], [t1, o.rot]]);
    if (t1 + 0.5 <= N) c.k(`${n.id}.r`, [[t1 + 0.5, -o.rot]]);
  }
  return n;
}
function ripple(c, at, t0, t1, rx = 46, ry = 9) {
  const id = `ripple${++fxn}`;
  const n = c.addFx(FX.ripple(id, rx, ry)); n.p = at.slice(); n.o = 0; n.s = [35, 35];
  c.k(`${id}.s`, [[t0, [35, 35]], [t1, [125, 125]]]);
  if (t1 + 0.5 <= c.N) c.k(`${id}.s`, [[t1 + 0.5, [35, 35]]]);
  c.k(`${id}.o`, [[t0, 0], [t0 + 5, 100], [t1, 0]]);
}
function splash(c, at, t0, t1, n = 5, R = 34, size = 100) {
  fx(c, (id) => FX.splash(id, n, R), at, t0, t1, { drift: [0, -18], pin: 4, pout: 6, size });
}
// elliptical orbit using two nested nodes (x and y oscillate a quarter period apart)
function orbitStar(c, center, rx, ry, t0, t1, T, phase) {
  const id = `star${++fxn}`;
  const star = FX.star(id + 'i', 9);
  const outer = node(id, { p: center.slice() }, [star]);
  c.addFx(outer); c.nodes[star.id] = star; star.parent = outer;
  const xs = [], ys = [];
  const X = (t) => center[0] + rx * Math.cos(2 * Math.PI * (t - t0) / T + phase);
  const Y = (t) => ry * Math.sin(2 * Math.PI * (t - t0) / T + phase);
  xs.push([t0, [X(t0), center[1]]]); ys.push([t0, [0, Y(t0)]]);
  for (let m = -4; m < 40; m++) {
    const tx = t0 + (m * Math.PI - phase) / (2 * Math.PI) * T; // x extremes
    if (tx > t0 + 0.5 && tx < t1 - 0.5) xs.push([tx, [X(tx), center[1]]]);
    const ty = t0 + ((m + 0.5) * Math.PI - phase) / (2 * Math.PI) * T; // y extremes
    if (ty > t0 + 0.5 && ty < t1 - 0.5) ys.push([ty, [0, Y(ty)]]);
  }
  xs.push([t1, [X(t1), center[1]]]); ys.push([t1, [0, Y(t1)]]);
  c.k(`${id}.p`, xs.sort((a, b) => a[0] - b[0]));
  c.k(`${star.id}.p`, ys.sort((a, b) => a[0] - b[0]));
  c.k(`${star.id}.s`, [[t0, [0, 0]], [t0 + 5, [100, 100]], [t1 - 5, [100, 100]], [t1, [0, 0]]]);
  c.k(`${star.id}.r`, [[t0, 0], [t1, 360 * Math.round((t1 - t0) / 30)]]);
}
// sitting helpers
const SIT = { pawL: { p: [210, 290], r: -14 }, pawR: { p: [302, 290], r: 6 } };
const SIT_ = SIT;
const LAP = [256, 446];
const HUG = { pebble: { p: [256, 318] }, pawL: pawTo(212, 292, 234, 340), pawR: pawTo(300, 292, 278, 340) };
const ARMS_UP = { pawL: { p: [190, 282], r: 128, s: [100, 118] }, pawR: { p: [322, 282], r: -128, s: [100, 118] } };
const ARMS_DOWN = { pawL: { ...SIT_.pawL, s: [100, 100] }, pawR: { ...SIT_.pawR, s: [100, 100] } };
const FL = poses.float;

// ============================================================================================
const defs = [];
const clip = (name, cat, base, frames, loop, fn, desc) => defs.push({ name, cat, base, frames, loop, fn, desc });

// ---------------- FLOATING ----------------
clip('float_idle', 'floating', 'float', 120, true, (c) => {
  c.rk('char.p', [[0, [0, 0]], [30, [0, -5]], [60, [0, 0]], [90, [0, -5]], [120, [0, 0]]]);
  c.rk('head.r', [[0, 0], [30, -2.5], [60, 0], [90, -2.5], [120, 0]]);
  c.rk('body.s', [[0, [0, 0]], [30, [2, 0]], [60, [0, 0]], [90, [2, 0]], [120, [0, 0]]]);
  // turn the pebble over, and back
  for (const [a, b, from, to] of [[26, 44, 100, -100], [76, 94, -100, 100]]) {
    c.k('pebbleRot.s', [[a, [from, 100]], [b, [to, 100]]]);
    c.rk('pebbleY.p', [[a - 2, [0, 0]], [a + 7, [0, -9]], [b, [0, 0]]]);
    c.rk('pawL.r', [[a - 2, 0], [a + 7, -7], [b, 0]]);
    c.rk('pawR.r', [[a - 2, 0], [a + 7, 7], [b, 0]]);
  }
  c.blink(58);
  c.rk('tail1.r', [[0, 0], [15, 7], [45, -5], [75, 7], [105, -5], [120, 0]]);
  c.rk('tail2.r', [[0, 0], [20, 9], [50, -7], [80, 9], [110, -6], [120, 0]]);
  c.rk('tail3.r', [[0, 0], [25, 12], [55, -9], [85, 12], [113, -6], [120, 0]]);
  c.rk('footL.r', [[0, 0], [30, -6], [60, 0], [90, -6], [120, 0]]);
  c.rk('footR.r', [[0, 0], [30, 6], [60, 0], [90, 6], [120, 0]]);
  ripple(c, [112, 423], 4, 60); ripple(c, [430, 423], 60, 116);
});

clip('float_crack_shell', 'floating', 'float', 150, true, (c) => {
  const up = pawTo(312, 248, 330, 198), high = pawTo(318, 236, 342, 190), hit = pawTo(326, 238, 364, 266);
  const mouth = pawTo(232, 318, 186, 330);
  const clamR = (pr, tilt = 0) => -pr + tilt;
  const P = (t0, t1, pose, tilt) => { go(c, t0, t1, { pawL: pose }); go(c, t0, t1, { clam: { r: clamR(pose.r, tilt) } }); };
  c.k('clam.r', [[0, clamR(FL.pawL.r)]]);
  c.h('clam.o', [[0, 0], [4, 100], [136, 0]]);
  c.k('clam.s', [[4, [0, 0]], [12, [130, 130]]]);
  P(0, 12, up, 0);
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  // two bangs
  for (const [a, b] of [[14, 24], [30, 38]]) {
    P(a, a + 6, high, -10); P(a + 6, b, hit, 8);
    c.k('pebbleRot.s', [[b - 1, [100, 100]], [b + 1, [110, 88]], [b + 5, [100, 100]]]);
    c.rk('char.p', [[b - 1, [0, 0]], [b + 2, [0, 4]], [b + 7, [0, 0]]]);
    c.face(b, { eyes: 'squint' }); c.face(b + 6, { eyes: 'open' });
    fx(c, FX.star, cv(366, 262), b, b + 9, { size: 90, pin: 2, pout: 4, rot: 30 });
  }
  // pops open
  P(44, 54, up, 0);
  c.k('clamTop.r', [[46, 0], [54, -78]]);
  fx(c, FX.sparkle, cv(342, 160), 50, 64, { size: 90 });
  c.face(50, { eyes: 'happy', mouth: 'open' });
  // to the mouth, nibble with puffed cheeks
  P(56, 68, mouth, -6);
  c.face(68, { mouth: 'o', eyes: 'happy' });
  for (const id of ['cheekL', 'cheekR']) c.k(`${id}.s`, [[64, [100, 100]], [70, [135, 135]], [110, [135, 135]], [118, [100, 100]]]);
  c.k('mouth_o.s', [[68, [100, 100]], ...Array.from({ length: 8 }, (_, i) => [72 + i * 5, i % 2 ? [100, 100] : [80, 55]]), [112, [100, 100]]]);
  c.k('head.r', [[68, FL.head.r], [80, FL.head.r - 3], [92, FL.head.r], [104, FL.head.r - 3], [114, FL.head.r]]);
  c.k('clam.s', [[66, [130, 130]], [112, [112, 112]], [126, [0, 0]]]);
  c.k('clamTop.r', [[112, -78], [124, 0]]);
  fx(c, FX.heart, cv(214, 170), 80, 108, { drift: [10, -30], size: 80 });
  c.face(114, { mouth: 'smile', eyes: 'happy' });
  P(118, 138, FL.pawL, 0);
  c.face(130, { eyes: 'open' });
  ripple(c, [404, 423], 22, 60);
});

clip('float_roll', 'floating', 'float', 100, true, (c) => {
  c.rk('char.s', [[0, [0, 0]], [8, [4, -5]], [14, [0, 0]]]);
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.face(8, { eyes: 'squint', mouth: 'o' });
  c.rk('spin.r', [[10, 0], [48, -360]]);
  c.rk('char.p', [[10, [0, 0]], [28, [0, 118]], [48, [0, 0]], [56, [0, -10]], [64, [0, 0]]]);
  c.rk('pawL.r', [[10, 0], [28, -12], [48, 0]]);
  c.rk('pawR.r', [[10, 0], [28, 12], [48, 0]]);
  c.rk('tail1.r', [[10, 0], [26, 24], [42, -14], [56, 0]]);
  splash(c, [180, 412], 14, 30); splash(c, [380, 412], 44, 62);
  ripple(c, [256, 423], 46, 90, 70, 12);
  c.face(48, { eyes: 'happy', mouth: 'open' });
  fx(c, FX.drop, [150, 360], 50, 70, { drift: [-12, 46], size: 80 });
  fx(c, FX.drop, [380, 350], 52, 72, { drift: [14, 50], size: 70 });
  c.face(80, { eyes: 'open', mouth: 'smile' });
  c.blink(86, 2.5);
});

clip('float_wave', 'floating', 'float', 90, true, (c) => {
  const upW = pawTo(304, 264, 318, 214);
  go(c, 0, 12, { pawL: upW });
  wig(c, 'pawL.r', 12, 6, [22, -10, 22, -10, 22], 'soft');
  c.k('pawL.r', [[12, upW.r]]); // keep anchor
  go(c, 48, 66, { pawL: FL.pawL });
  c.rk('head.r', [[0, 0], [12, 4], [44, 4], [66, 0]]);
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.face(10, { mouth: 'open' });
  c.face(52, { eyeR: 'wink', eyeL: 'open', mouth: 'open' });
  fx(c, FX.sparkle, cv(214, 210), 54, 74, { size: 80, rot: 20 });
  c.face(74, { eyes: 'open', mouth: 'smile' });
  c.rk('char.p', [[0, [0, 0]], [22, [0, -4]], [44, [0, 0]], [66, [0, -4]], [90, [0, 0]]]);
});

clip('sit_to_float', 'floating', 'sit', 80, false, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.h('water.o', [[0, 100]]);
  c.k('water.p', [[0, [0, 130]], [14, [0, 0]]]);
  c.k('shadow.s', [[6, [100, 100]], [16, [40, 40]]]); c.h('shadow.o', [[16, 0]]);
  c.rk('char.s', [[0, [0, 0]], [8, [8, -10]], [14, [-6, 8]], [20, [0, 0]]]);
  go(c, 0, 8, { pawL: { r: 30 }, pawR: { r: -24 } });
  c.face(6, { eyes: 'happy', mouth: 'open' });
  c.rk('char.p', [[8, [0, 0]], [18, [0, -110]], [30, [0, 360]]]);
  c.rk('spin.r', [[12, 0], [28, -120]]);
  go(c, 8, 16, ARMS_UP);
  splash(c, [256, 418], 27, 44, 7, 86, 105);
  ripple(c, [256, 423], 26, 60, 64, 12);
  // under water: swap to the floating layout
  c.toPose('float', 30, 40);
  c.k('spin.r', [[30, -120], [40, -360]]);
  c.face(38, { eyes: 'squint', mouth: 'o' });
  c.rk('char.p', [[40, [0, 360]], [52, [0, -14]], [60, [0, 0]]]);
  fx(c, FX.bubble, [210, 436], 44, 60, { drift: [-6, -30], size: 90 });
  fx(c, FX.bubble, [320, 446], 46, 62, { drift: [6, -34], size: 70 });
  ripple(c, [140, 423], 52, 76); ripple(c, [400, 423], 54, 78);
  c.face(52, { eyes: 'happy', mouth: 'open' });
  c.face(66, { eyes: 'open', mouth: 'smile' });
});

clip('float_to_sit', 'floating', 'float', 80, false, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.rk('char.s', [[0, [0, 0]], [8, [5, -6]], [12, [0, 0]]]);
  c.face(6, { eyes: 'happy', mouth: 'open' });
  c.rk('char.p', [[10, [0, 0]], [22, [0, -150]], [32, [0, 0]]]);
  c.toPose('sit', 10, 24, { except: ['water', 'shadow', 'char'] });
  splash(c, [256, 414], 12, 28, 5, 38);
  ripple(c, [256, 423], 12, 40, 60, 11);
  c.k('water.p', [[18, [0, 0]], [30, [0, 140]]]); c.h('water.o', [[30, 0]]);
  c.h('shadow.o', [[24, 100]]); c.k('shadow.s', [[24, [0, 0]], [32, [100, 100]]]);
  c.k('char.s', [[30, [100, 100]], [33, [112, 88]], [38, [96, 104]], [42, [100, 100]]]);
  c.face(34, { eyes: 'squint', mouth: 'o' });
  // shake off water
  wig(c, 'spin.r', 40, 3, alt(6, 9), 'soft');
  wig(c, 'head.r', 40, 3, alt(6, -6), 'soft');
  wig(c, 'pawL.r', 40, 3, alt(6, 12), 'soft');
  wig(c, 'pawR.r', 40, 3, alt(6, -12), 'soft');
  for (const [x, y, dx, dy, t] of [[150, 250, -48, 30, 42], [370, 240, 48, 26, 44], [130, 330, -50, 44, 47], [390, 330, 52, 40, 49], [200, 170, -30, -16, 51], [320, 168, 34, -18, 53]]) fx(c, FX.drop, [x, y], t, t + 14, { drift: [dx, dy], size: 75, pin: 3 });
  c.face(62, { eyes: 'happy', mouth: 'smile' });
  c.face(72, { eyes: 'open' });
});

// ---------------- IDLE (sitting) ----------------
clip('idle_breathe', 'idle', 'sit', 120, true, (c) => {
  c.rk('char.s', [[0, [0, 0]], [30, [-1.5, 2.5]], [60, [0, 0]], [90, [-1.5, 2.5]], [120, [0, 0]]]);
  c.blink(74);
  wig(c, 'whiskerL.r', 28, 3, [-8, 5, -3]); wig(c, 'whiskerR.r', 28, 3, [8, -5, 3]);
  c.rk('tail1.r', [[0, 0], [40, 10], [80, -4], [120, 0]]);
  c.rk('tail2.r', [[0, 0], [50, 12], [92, -6], [120, 0]]);
  c.rk('tail3.r', [[0, 0], [60, 14], [102, -8], [120, 0]]);
  c.rk('pawL.r', [[0, 0], [30, -2], [60, 0], [90, -2], [120, 0]]);
  c.rk('pawR.r', [[0, 0], [30, 2], [60, 0], [90, 2], [120, 0]]);
});

clip('idle_look_left_right', 'idle', 'sit', 120, true, (c) => {
  look(c, 4, 14, [-1, 0]);
  c.rk('head.r', [[4, 0], [14, -4], [40, -4], [54, 4], [90, 4], [104, 0]]);
  wig(c, 'whiskerL.r', 12, 3, [-7, 4]); wig(c, 'whiskerR.r', 12, 3, [-7, 4]);
  look(c, 40, 54, [1, 0]);
  wig(c, 'whiskerL.r', 52, 3, [7, -4]); wig(c, 'whiskerR.r', 52, 3, [7, -4]);
  c.blink(46, 2.5);
  lookBack(c, 90, 104);
  fx(c, FX.question, cv(392, 110), 92, 116, { size: 80, pulse: 6 });
});

clip('idle_yawn', 'idle', 'sit', 90, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.rk('head.r', [[2, 0], [14, -6], [46, -6], [60, 0]]);
  c.rk('head.p', [[2, [0, 0]], [14, [0, -6]], [46, [0, -6]], [60, [0, 0]]]);
  c.rk('char.s', [[2, [0, 0]], [16, [-2, 4]], [46, [-2, 4]], [60, [0, 0]]]);
  c.face(10, { eyes: 'squint', mouth: 'yawn' });
  c.k('mouth_yawn.s', [[0, [100, 100]], [9, [80, 25]], [24, [105, 105]], [34, [100, 96]], [44, [104, 104]], [56, [80, 25]], [64, [100, 100]]]);
  go(c, 6, 18, { pawL: { r: 18 }, pawR: { r: -12 } });
  go(c, 48, 62, { pawL: SIT.pawL, pawR: SIT.pawR });
  c.face(57, { eyes: 'sleepy', mouth: 'smile' });
  c.face(74, { eyes: 'open' });
  wig(c, 'whiskerL.r', 22, 4, [-6, 3]); wig(c, 'whiskerR.r', 22, 4, [6, -3]);
});

clip('idle_stretch', 'idle', 'sit', 96, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.k('pebble.p', [[2, [328, 350]], [12, LAP]]);
  c.rk('char.s', [[0, [0, 0]], [10, [5, -6]], [28, [-5, 11]], [56, [-5, 11]], [70, [3, -3]], [78, [0, 0]]]);
  go(c, 10, 28, { pawL: { ...ARMS_UP.pawL, r: 140, s: [100, 128] }, pawR: { ...ARMS_UP.pawR, r: -140, s: [100, 128] } });
  wig(c, 'pawL.r', 30, 6, [6, 0, 6], 'soft');
  wig(c, 'pawR.r', 30, 6, [-6, 0, -6], 'soft');
  go(c, 56, 74, ARMS_DOWN);
  go(c, 12, 28, { tail1: { r: -96 }, tail2: { r: 0 }, tail3: { r: -4 } });
  go(c, 56, 74, { tail1: { r: -12 }, tail2: { r: -30 }, tail3: { r: -32 } });
  c.face(14, { eyes: 'happy', mouth: 'o' });
  c.k('mouth_o.s', [[14, [100, 100]], [26, [130, 140]], [54, [130, 140]], [62, [100, 100]]]);
  c.rk('head.r', [[14, 0], [28, 0], [40, 3], [52, -3], [62, 0]]);
  c.face(64, { eyes: 'open', mouth: 'smile' });
  c.k('pebble.p', [[74, LAP], [86, [328, 350]]]);
});

clip('idle_groom', 'idle', 'sit', 96, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.k('pebble.p', [[0, [328, 350]], [10, LAP]]);
  const gl = pawTo(192, 292, 182, 236), gr = pawTo(320, 292, 330, 236);
  go(c, 4, 16, { pawL: gl, pawR: gr });
  c.face(14, { eyes: 'squint', mouth: 'o' });
  wig(c, 'pawL.r', 16, 3, alt(15, -16, 10)); c.k('pawL.r', [[16, gl.r]]);
  wig(c, 'pawR.r', 16, 3, alt(15, 16, -10)); c.k('pawR.r', [[16, gr.r]]);
  wig(c, 'pawL.p', 16, 3, alt(15, [4, -8], [-2, 6])); c.k('pawL.p', [[16, gl.p]]);
  wig(c, 'pawR.p', 16, 3, alt(15, [-4, 6], [2, -8])); c.k('pawR.p', [[16, gr.p]]);
  wig(c, 'head.r', 16, 6, alt(7, 3));
  wig(c, 'whiskerL.r', 16, 4, alt(11, -9, 6)); wig(c, 'whiskerR.r', 16, 4, alt(11, 9, -6));
  go(c, 66, 80, { pawL: SIT.pawL, pawR: SIT.pawR });
  c.face(70, { eyes: 'happy', mouth: 'smile' });
  c.face(84, { eyes: 'open' });
  c.k('pebble.p', [[76, LAP], [88, [328, 350]]]);
  fx(c, FX.sparkle, cv(130, 120), 60, 78, { size: 70 });
  fx(c, FX.sparkle, cv(388, 96), 66, 84, { size: 90 });
});

clip('idle_juggle_pebble', 'idle', 'sit', 150, true, (c) => {
  const cl = pawTo(210, 290, 226, 338), cr = pawTo(302, 290, 286, 338);
  const PL = [226, 318], PR = [288, 318];
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  go(c, 0, 10, { pawL: cl, pawR: cr, pebble: { p: PR } });
  let t = 14, from = PR, to = PL, rot = 0;
  for (let i = 0; i < 4; i++) {
    const thrower = from === PR ? 'pawR' : 'pawL', catcher = from === PR ? 'pawL' : 'pawR';
    c.rk(`${thrower}.r`, [[t - 4, 0], [t, thrower === 'pawR' ? 14 : -14], [t + 6, 0]]);
    c.k('pebble.p', [[t, from], [t + 18, to]]);
    c.rk('pebbleY.p', [[t, [0, 0]], [t + 9, [0, -74]], [t + 18, [0, 0]]]);
    c.k('pebbleRot.r', [[t, rot], [t + 18, rot + 180]]); rot += 180;
    c.rk(`${catcher}.r`, [[t + 17, 0], [t + 20, catcher === 'pawR' ? -10 : 10], [t + 25, 0]]);
    const d = to === PL ? -1 : 1;
    c.k('eyeL.p', [[t, c.at('eyeL.p', t)], [t + 9, [210 + 3 * d, 155]], [t + 18, [210 + 9 * d, 164]]]);
    c.k('eyeR.p', [[t, c.at('eyeR.p', t)], [t + 9, [302 + 3 * d, 155]], [t + 18, [302 + 9 * d, 164]]]);
    t += 22; [from, to] = [to, from];
  }
  // hug
  lookBack(c, t, t + 10);
  go(c, t, t + 12, { pebble: HUG.pebble, pawL: HUG.pawL, pawR: HUG.pawR });
  c.face(t + 8, { eyes: 'happy', mouth: 'open' });
  c.k('pebbleRot.s', [[t + 12, [100, 100]], [t + 18, [108, 92]], [t + 24, [100, 100]]]);
  fx(c, FX.heart, cv(256, 250), t + 10, t + 34, { drift: [0, -34], size: 80 });
  go(c, t + 26, 144, { pebble: { p: [328, 350] }, pawL: SIT.pawL, pawR: SIT.pawR });
  c.face(t + 32, { eyes: 'open', mouth: 'smile' });
});

// ---------------- SLEEP ----------------
clip('sleep_fall_asleep', 'sleep', 'float', 100, false, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.face(8, { eyes: 'squint', mouth: 'yawn' });
  c.k('mouth_yawn.s', [[8, [80, 25]], [20, [105, 105]], [32, [100, 100]], [38, [80, 25]]]);
  c.rk('head.r', [[4, 0], [18, -6], [34, -6], [44, 0]]);
  c.face(40, { eyes: 'sleepy', mouth: 'smile' });
  c.toPose('sleep', 46, 66, { only: ['pawL', 'pawR', 'pebble'] });
  c.face(62, { mouth: 'o' });
  c.k('mouth_o.s', [[62, [70, 70]]]);
  c.rk('char.p', [[60, [0, 0]], [72, [0, -4]], [84, [0, 0]]]);
  c.rk('body.s', [[66, [0, 0]], [80, [3, 1]], [94, [0, 0]]]);
});

clip('sleep_loop', 'sleep', 'sleep', 120, true, (c) => {
  c.rk('char.p', [[0, [0, 0]], [30, [0, -4]], [60, [0, 0]], [90, [0, -4]], [120, [0, 0]]]);
  c.rk('body.s', [[0, [0, 0]], [30, [4, 1]], [60, [0, 0]], [90, [4, 1]], [120, [0, 0]]]);
  c.rk('head.r', [[0, 0], [30, -1.5], [60, 0], [90, -1.5], [120, 0]]);
  c.k('snot.s', [[0, [0, 0]], [12, [35, 35]], [30, [70, 70]], [45, [55, 55]], [60, [90, 90]], [75, [70, 70]], [92, [100, 100]], [108, [60, 60]], [117, [0, 0]]]);
  c.rk('tail1.r', [[0, 0], [60, 6], [120, 0]]);
  // z z z (vector paths)
  const h = cv(212, 170);
  fx(c, FX.z, add(h, [0, 0]), 4, 92, { drift: [22, -60], size: 70, pin: 8, pout: 10 });
  fx(c, FX.z, add(h, [26, -26]), 16, 100, { drift: [26, -62], size: 90, pin: 8, pout: 10 });
  fx(c, FX.z, add(h, [56, -56]), 28, 108, { drift: [28, -62], size: 115, pin: 8, pout: 10 });
});

clip('sleep_wake_up', 'sleep', 'sleep', 110, false, (c) => {
  c.faceStart({ eyes: 'sleepy', mouth: 'o' });
  c.rk('char.p', [[0, [0, 0]], [4, [0, -16]], [10, [0, 0]]]);
  go(c, 2, 10, { pawL: pawTo(196, 330, 160, 280), pawR: pawTo(250, 330, 262, 270) });
  c.face(4, { eyes: 'open', mouth: 'o', brows: 'worried' });
  c.k('eyeL_open.s', [[4, [100, 100]], [8, [120, 120]], [12, [100, 8]], [14, [120, 120]], [17, [100, 8]], [20, [110, 110]], [56, [110, 110]], [62, [100, 100]]]);
  c.k('eyeR_open.s', [[4, [100, 100]], [8, [120, 120]], [12, [100, 8]], [14, [120, 120]], [17, [100, 8]], [20, [110, 110]], [56, [110, 110]], [62, [100, 100]]]);
  fx(c, FX.bang, cv(140, 150), 4, 26, { size: 85, pin: 3 });
  // the pebble rolls off and sinks
  c.k('pebble.p', [[10, poses.sleep.pebble.p], [20, [432, 352]]]);
  c.k('pebbleRot.r', [[10, 0], [20, 60], [34, 100]]);
  c.rk('pebbleY.p', [[20, [0, 0]], [34, [0, 62]]]);
  look(c, 12, 20, [1, 0.6]);
  // dive with the right paw and catch it
  const reach = pawTo(390, 362, 432, 414);
  go(c, 22, 32, { pawR: reach, pawL: pawTo(300, 282, 350, 270) });
  c.rk('head.r', [[20, 0], [32, 8], [44, 0]]);
  splash(c, cv(434, 412), 31, 46, 4, 26, 80);
  ripple(c, cv(434, 418), 32, 60, 34, 7);
  // catch at 34: held copy swaps in
  c.k('pebble.p', [[34, [432, 352]]]);
  c.h('pebble.o', [[34, 0]]); c.h('pebbleHeld.o', [[34, 100]]);
  c.k('pebbleHeld.r', [[34, -reach.r + 100], [52, -60]]);
  c.face(36, { eyes: 'squint', mouth: 'o', brows: null });
  // bring it back and hug
  const hugR = pawTo(318, 350, 360, 316), hugL = pawTo(310, 276, 356, 296);
  go(c, 38, 52, { pawR: hugR, pawL: hugL });
  lookBack(c, 40, 50);
  const hp = pawTip(hugR.p, hugR.r, [100, 100], 66);
  c.h('pebble.o', [[52, 100]]); c.h('pebbleHeld.o', [[52, 0]]);
  c.k('pebble.p', [[34, [432, 352]], [51.9, [432, 352]], [52, hp]]);
  c.rk('pebbleY.p', [[34, [0, 62]], [51.9, [0, 62]], [52, [0, 0]]]);
  c.k('pebbleRot.r', [[51.9, 100], [52, -60 + hugR.r]]);
  c.face(54, { eyes: 'happy', mouth: 'open' });
  c.k('pebbleRot.s', [[56, [100, 100]], [62, [110, 92]], [68, [100, 100]], [74, [110, 92]], [80, [100, 100]]]);
  c.rk('char.s', [[56, [0, 0]], [62, [3, -3]], [68, [0, 0]]]);
  fx(c, FX.heart, cv(330, 220), 58, 84, { drift: [6, -30], size: 80 });
  fx(c, FX.drop, cv(232, 160), 60, 82, { drift: [0, 18], size: 60 });
  // settle into the floating base pose
  c.toPose('float', 82, 98, { except: ['eyeL_sleepy', 'eyeR_sleepy', 'eyeL_open', 'eyeR_open', 'mouth_o', 'mouth_smile', 'mouth_open'] });
  c.k('pebbleRot.r', [[82, -60 + hugR.r], [98, 0]]);
  c.face(92, { eyes: 'open', mouth: 'smile' });
});

// ---------------- MOVEMENT ----------------
clip('move_walk', 'movement', 'walk', 30, true, (c) => {
  c.rk('char.p', [[0, [0, 0]], [8, [0, -18]], [15, [0, 0]], [23, [0, -6]], [30, [0, 0]]]);
  c.rk('body.r', [[0, 0], [8, -5], [15, 2], [23, 4], [30, 0]]);
  c.rk('body.s', [[0, [0, 0]], [8, [7, -6]], [15, [-6, 6]], [23, [2, -2]], [30, [0, 0]]]);
  c.rk('head.p', [[0, [0, 0]], [10, [-4, -6]], [17, [0, 3]], [30, [0, 0]]]);
  c.rk('head.r', [[0, 0], [9, -3], [17, 2], [30, 0]]);
  c.rk('pawL.r', [[0, 0], [8, 34], [15, -22], [30, 0]]);
  c.rk('pawR.r', [[0, 0], [8, 24], [15, -30], [30, 0]]);
  c.rk('footL.p', [[0, [0, 0]], [8, [-10, -16]], [15, [14, 0]], [30, [0, 0]]]);
  c.rk('footR.p', [[0, [0, 0]], [9, [-14, -12]], [16, [10, 0]], [30, [0, 0]]]);
  c.rk('footL.r', [[0, 0], [8, -20], [15, 10], [30, 0]]);
  c.rk('footR.r', [[0, 0], [9, -16], [16, 12], [30, 0]]);
  c.rk('tail1.r', [[0, 0], [9, 12], [17, -6], [24, 6], [30, 0]]);
  c.rk('tail2.r', [[0, 0], [11, 14], [19, -8], [26, 6], [30, 0]]);
  c.rk('tail3.r', [[0, 0], [13, 16], [21, -10], [27, 6], [30, 0]]);
  c.k('shadow.s', [[0, [100, 100]], [8, [84, 84]], [15, [100, 100]], [23, [94, 94]], [30, [100, 100]]]);
});

clip('move_hop', 'movement', 'sit', 48, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.k('char.s', [[0, [100, 100]], [8, [110, 88]], [14, [92, 110]], [20, [100, 100]], [28, [96, 106]], [31, [114, 86]], [36, [96, 104]], [42, [100, 100]]]);
  c.rk('char.p', [[8, [0, 0]], [20, [0, -120]], [30, [0, 0]]]);
  go(c, 0, 8, { pawL: { r: 22 }, pawR: { r: -18 } });
  go(c, 8, 16, ARMS_UP);
  go(c, 26, 36, ARMS_DOWN);
  // pebble rides along in the right paw
  c.k('pebble.p', [[0, [328, 350]], [6, heldPos(c, 6)]]);
  c.h('pebble.o', [[6, 0], [40, 100]]); c.h('pebbleHeld.o', [[6, 100], [40, 0]]);
  c.k('pebble.p', [[39.9, heldPos(c, 39.9)], [40, heldPos(c, 40)], [46, [328, 350]]]);
  go(c, 8, 16, { footL: { r: 16 }, footR: { r: -16 }, tail1: { r: 30 } });
  go(c, 24, 32, { footL: { r: 0 }, footR: { r: 0 }, tail1: { r: -12 } });
  c.k('shadow.s', [[0, [100, 100]], [8, [104, 104]], [20, [55, 55]], [30, [100, 100]], [32, [112, 112]], [40, [100, 100]]]);
  c.face(12, { eyes: 'happy', mouth: 'open' });
  c.face(32, { eyes: 'squint', mouth: 'o' });
  c.face(40, { eyes: 'open', mouth: 'smile' });
});

clip('move_swim', 'movement', 'swim', 40, true, (c) => {
  c.rk('char.p', [[0, [0, 0]], [10, [0, -5]], [20, [0, 0]], [30, [0, -5]], [40, [0, 0]]]);
  c.rk('head.r', [[0, 0], [10, -2], [20, 0], [30, -2], [40, 0]]);
  c.rk('tail1.r', [[0, 0], [5, -18], [15, 16], [25, -18], [35, 16], [40, 0]]);
  c.rk('tail2.r', [[0, 0], [7, -18], [17, 18], [27, -18], [37, 18], [40, 0]]);
  c.rk('tail3.r', [[0, 0], [9, -22], [19, 22], [29, -22], [38, 18], [40, 0]]);
  c.rk('footL.r', [[0, 0], [5, 20], [15, -20], [25, 20], [35, -20], [40, 0]]);
  c.rk('footR.r', [[0, 0], [5, -20], [15, 20], [25, -20], [35, 20], [40, 0]]);
  c.rk('pawL.r', [[0, 0], [10, 34], [20, 0], [30, 34], [40, 0]]);
  c.rk('pawR.r', [[0, 0], [10, -10], [20, 26], [30, -10], [40, 0]]);
  ripple(c, [348, 422], 0, 22, 30, 7); ripple(c, [348, 422], 20, 39, 30, 7);
  fx(c, FX.drop, [410, 410], 4, 18, { drift: [24, -8], size: 55 });
  fx(c, FX.drop, [420, 412], 24, 38, { drift: [26, -6], size: 55 });
  fx(c, FX.bubble, [230, 470], 2, 30, { drift: [4, -36], size: 70 });
});

clip('move_fall_land', 'movement', 'float', 96, false, (c) => {
  c.poseAt('sit', 0);
  c.h('water.o', [[0, 100]]); c.h('shadow.o', [[0, 0]]);
  c.faceStart({ eyes: 'open', mouth: 'o', brows: 'worried' });
  c.k('eyeL_open.s', [[0, [118, 118]], [20, [118, 118]], [22, [100, 100]]]);
  c.k('eyeR_open.s', [[0, [118, 118]], [20, [118, 118]], [22, [100, 100]]]);
  c.k('char.p', [[0, [256, -230]], [18, [256, 560]], [24, [256, 880]]]);
  c.k('pawL.p', [[0, ARMS_UP.pawL.p]]); c.k('pawR.p', [[0, ARMS_UP.pawR.p]]); c.k('pawL.s', [[0, ARMS_UP.pawL.s]]); c.k('pawR.s', [[0, ARMS_UP.pawR.s]]);
  c.k('pawL.r', [[0, 128], [3, 100], [6, 140], [9, 100], [12, 140], [15, 100], [18, 128]]);
  c.k('pawR.r', [[0, -100], [3, -140], [6, -100], [9, -140], [12, -100], [15, -140], [18, -128]]);
  c.k('footL.r', [[0, 20], [4, -10], [8, 20], [12, -10], [16, 20]]);
  c.k('footR.r', [[0, -10], [4, 20], [8, -10], [12, 20], [16, -10]]);
  c.k('tail1.r', [[0, 60], [6, 30], [12, 60], [18, 40]]);
  c.k('pebble.p', [[0, [328, 350]]]);
  splash(c, [256, 418], 19, 38, 7, 92, 110);
  ripple(c, [256, 423], 17, 56, 80, 14);
  ripple(c, [256, 423], 24, 64, 50, 9);
  fx(c, FX.drop, [170, 360], 18, 38, { drift: [-40, 40], size: 80 });
  fx(c, FX.drop, [350, 350], 19, 39, { drift: [44, 46], size: 80 });
  // under water -> float layout, then bob up
  c.toPose('float', 24, 34);
  c.k('char.p', [[34, [256, 880]], [48, [256, 458]], [56, [256, 474]], [62, [256, 470]]]);
  c.face(34, { eyes: 'dizzy', mouth: 'frown', brows: null });
  fx(c, FX.bubble, [220, 440], 36, 52, { drift: [0, -24], size: 80 });
  ripple(c, [256, 423], 48, 82, 70, 12);
  wig(c, 'head.r', 50, 8, [-5, 4, -5, 4]);
  c.k('head.r', [[50, FL.head.r]]);
  const hc = cv(146, 206);
  for (let i = 0; i < 3; i++) orbitStar(c, hc, 56, 14, 48, 82, 30, i * 2 * Math.PI / 3);
  c.face(80, { eyes: 'open', mouth: 'smile' });
  c.blink(84, 2.5);
});

// ---------------- INTERACTION ----------------
clip('int_dragged', 'interaction', 'dragged', 60, true, (c) => {
  c.rk('spin.r', [[0, 0], [15, 6], [45, -6], [60, 0]]);
  c.rk('head.r', [[0, 0], [17, -3], [47, 3], [60, 0]]);
  c.rk('footL.r', [[0, 0], [19, 10], [49, -10], [60, 0]]);
  c.rk('footR.r', [[0, 0], [20, 12], [50, -8], [60, 0]]);
  c.rk('footL.p', [[0, [0, 0]], [19, [-4, 0]], [49, [4, 0]], [60, [0, 0]]]);
  c.rk('footR.p', [[0, [0, 0]], [20, [-4, 0]], [50, [4, 0]], [60, [0, 0]]]);
  c.rk('tail1.r', [[0, 0], [20, -10], [50, 10], [60, 0]]);
  c.rk('tail2.r', [[0, 0], [23, -12], [53, 12], [60, 0]]);
  c.rk('tail3.r', [[0, 0], [26, -14], [56, 14], [60, 0]]);
  c.rk('body.s', [[0, [0, 0]], [15, [-2, 3]], [30, [0, 0]], [45, [-2, 3]], [60, [0, 0]]]);
  c.rk('pebbleRot.r', [[0, 0], [16, -5], [46, 5], [60, 0]]);
  c.rk('whiskerL.r', [[0, 0], [15, -8], [45, 4], [60, 0]]);
  c.rk('whiskerR.r', [[0, 0], [15, 8], [45, -4], [60, 0]]);
  c.blink(36, 2.5);
});

clip('int_petted', 'interaction', 'sit', 100, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.face(6, { eyes: 'happy', mouth: 'smile' });
  c.h('blush.o', [[8, 100], [86, 0]]);
  for (const id of ['cheekL', 'cheekR']) c.k(`${id}.s`, [[4, [100, 100]], [14, [125, 125]], [80, [125, 125]], [90, [100, 100]]]);
  c.rk('head.r', [[2, 0], [14, -10], [22, -6], [30, -11], [38, -6], [46, -11], [78, -8], [92, 0]]);
  c.rk('head.p', [[2, [0, 0]], [14, [-5, -6]], [78, [-5, -6]], [92, [0, 0]]]);
  c.rk('char.s', [[2, [0, 0]], [14, [-2, 3]], [78, [-2, 3]], [92, [0, 0]]]);
  const reach = pawTo(190, 282, 128, 232);
  go(c, 40, 56, { pawL: reach });
  c.k('pawL.s', [[40, [100, 100]], [56, [100, 116]], [76, [100, 116]], [90, [100, 100]]]);
  wig(c, 'pawL.r', 56, 5, [6, -2, 6]);
  c.k('pawL.r', [[56, reach.r]]);
  go(c, 76, 90, { pawL: SIT.pawL });
  c.face(46, { mouth: 'open' }); c.face(80, { mouth: 'smile' });
  c.face(90, { eyes: 'open' });
  fx(c, FX.heart, cv(150, 90), 20, 50, { drift: [-10, -40], size: 85 });
  fx(c, FX.heart, cv(380, 110), 36, 66, { drift: [12, -40], size: 70 });
  fx(c, FX.heart, cv(110, 40), 56, 86, { drift: [-6, -30], size: 100 });
});

clip('int_poked', 'interaction', 'sit', 84, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.k('char.s', [[0, [100, 100]], [3, [106, 93]], [8, [98, 102]], [12, [100, 100]]]);
  c.face(1, { eyes: 'squint', mouth: 'o' });
  c.face(9, { eyes: 'open', mouth: 'o', brows: 'angry' });
  c.k('mouth_o.s', [[9, [100, 100]], [14, [80, 55]], [64, [80, 55]], [70, [100, 100]]]);
  for (const id of ['cheekL', 'cheekR']) c.k(`${id}.s`, [[8, [100, 100]], [16, [145, 145]], [62, [145, 145]], [70, [100, 100]]]);
  // turn away a little, nose up
  c.rk('spin.r', [[6, 0], [18, 5], [60, 5], [72, 0]]);
  c.rk('head.r', [[6, 0], [18, -9], [60, -9], [72, 0]]);
  look(c, 8, 18, [-1, -0.3], 0.8);
  lookBack(c, 60, 70);
  // hide the pebble behind its back
  c.k('pebble.p', [[6, [328, 350]], [14, [352, 340]]]);
  c.h('pebble.o', [[14, 0], [62, 100]]); c.h('pebbleBack.o', [[14, 100], [62, 0]]);
  c.k('pebbleBack.p', [[0, [328, 350]], [13, [328, 350]], [14, [352, 340]], [22, [306, 332]], [54, [306, 332]], [62, [352, 340]], [63, [328, 350]]]);
  c.k('pebble.p', [[62, [352, 340]], [70, [328, 350]]]);
  go(c, 8, 18, { pawR: { r: -18 }, pawL: { r: -26 } });
  go(c, 60, 70, { pawR: SIT.pawR, pawL: SIT.pawL });
  fx(c, FX.anger, cv(366, 74), 12, 64, { size: 110, pulse: 5 });
  c.face(68, { eyes: 'open', mouth: 'smile', brows: null });
});

clip('int_tickled', 'interaction', 'sit', 60, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.face(2, { eyes: 'squint', mouth: 'grin' });
  for (let t = 8; t < 50; t += 6) c.face(t, { mouth: (t / 6) % 2 ? 'open' : 'grin' });
  c.face(50, { mouth: 'grin' });
  c.face(54, { eyes: 'happy', mouth: 'smile' });
  c.face(59, { eyes: 'open' });
  c.h('blush.o', [[4, 100], [54, 0]]);
  wig(c, 'spin.r', 4, 4, alt(11, 7));
  wig(c, 'head.r', 4, 4, alt(11, -5));
  c.rk('char.p', [[2, [0, 0]], [8, [0, -8]], [14, [0, 0]], [20, [0, -8]], [26, [0, 0]], [32, [0, -8]], [38, [0, 0]], [44, [0, -8]], [50, [0, 0]]]);
  wig(c, 'footL.r', 4, 4, alt(11, -28, 6)); wig(c, 'footR.r', 4, 4, alt(11, 6, 28));
  wig(c, 'footL.p', 4, 4, alt(11, [-4, -10], [0, 0])); wig(c, 'footR.p', 4, 4, alt(11, [0, 0], [4, -10]));
  wig(c, 'pawL.r', 4, 4, alt(11, 22, -6)); wig(c, 'pawR.r', 4, 4, alt(11, 6, -18));
  wig(c, 'tail1.r', 4, 4, alt(11, 14));
  fx(c, FX.sparkle, cv(120, 160), 10, 30, { size: 80 });
  fx(c, FX.sparkle, cv(392, 130), 24, 44, { size: 70 });
});

for (const [k, d] of Object.entries(DIRS)) {
  clip('int_look_' + k, 'interaction', 'look_' + k, 60, true, (c) => {
    c.rk('char.s', [[0, [0, 0]], [30, [-1, 1.8]], [60, [0, 0]]]);
    c.rk('pawL.r', [[0, 0], [30, -2], [60, 0]]);
    c.rk('pawR.r', [[0, 0], [30, 2], [60, 0]]);
  });
}

// ---------------- MOODS ----------------
clip('mood_happy', 'moods', 'sit', 64, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.face(4, { eyes: 'happy', mouth: 'open' });
  c.face(58, { eyes: 'open', mouth: 'smile' });
  c.k('pebble.p', [[0, [328, 350]], [8, LAP], [54, LAP], [62, [328, 350]]]);
  const open = { pawL: pawTo(206, 290, 180, 330), pawR: pawTo(306, 290, 332, 330) };
  const shut = { pawL: pawTo(214, 290, 252, 316), pawR: pawTo(298, 290, 260, 316) };
  go(c, 2, 8, open);
  for (let i = 0; i < 4; i++) {
    const t = 8 + i * 11;
    go(c, t, t + 5, shut); go(c, t + 5, t + 11, open);
    c.rk('char.p', [[t, [0, 0]], [t + 5, [0, -16]], [t + 11, [0, 0]]]);
    c.k('char.s', [[t, [100, 100]], [t + 2, [96, 104]], [t + 9, [100, 100]], [t + 11, [104, 96]]]);
  }
  c.k('char.s', [[52, [104, 96]], [56, [100, 100]]]);
  go(c, 52, 60, SIT);
  fx(c, FX.sparkle, cv(120, 120), 6, 26, { size: 90, rot: 30 });
  fx(c, FX.sparkle, cv(396, 92), 18, 38, { size: 110, rot: 30 });
  fx(c, FX.sparkle, cv(400, 300), 30, 50, { size: 70, rot: 30 });
  fx(c, FX.sparkle, cv(110, 300), 40, 58, { size: 80, rot: 30 });
});

clip('mood_sad', 'moods', 'sit', 96, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.face(8, { mouth: 'frown', brows: 'worried' });
  c.rk('head.p', [[2, [0, 0]], [16, [0, 9]], [74, [0, 9]], [88, [0, 0]]]);
  c.rk('head.r', [[2, 0], [16, -5], [74, -5], [88, 0]]);
  c.k('eyeL_open.s', [[4, [100, 100]], [14, [100, 88]], [76, [100, 88]], [86, [100, 100]]]);
  c.k('eyeR_open.s', [[4, [100, 100]], [14, [100, 88]], [76, [100, 88]], [86, [100, 100]]]);
  look(c, 6, 16, [0, 0.5]); lookBack(c, 74, 86);
  c.rk('earL.r', [[2, 0], [16, -24], [74, -24], [88, 0]]);
  c.rk('earR.r', [[2, 0], [16, 24], [74, 24], [88, 0]]);
  c.rk('whiskerL.r', [[2, 0], [16, -16], [74, -16], [88, 0]]);
  c.rk('whiskerR.r', [[2, 0], [16, 16], [74, 16], [88, 0]]);
  go(c, 4, 18, HUG); go(c, 72, 88, { pebble: { p: [328, 350] }, ...SIT });
  c.rk('char.s', [[4, [0, 0]], [18, [3, -4]], [44, [2, -2]], [60, [3, -4]], [76, [0, 0]]]);
  c.h('tear.o', [[22, 100], [70, 0]]);
  c.k('tear.s', [[0, [100, 100]], [21, [0, 0]], [28, [100, 100]], [62, [90, 110]], [69, [0, 0]], [72, [100, 100]]]);
  c.k('tear.p', [[0, [196, 182]], [28, [196, 182]], [64, [192, 214]], [70, [192, 214]], [72, [196, 182]]]);
  c.face(86, { mouth: 'smile', brows: null });
});

clip('mood_surprised', 'moods', 'sit', 64, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.k('char.s', [[0, [100, 100]], [4, [106, 94]], [10, [94, 108]], [16, [100, 100]], [22, [108, 92]], [28, [100, 100]]]);
  c.rk('char.p', [[4, [0, 0]], [12, [0, -56]], [22, [0, 0]]]);
  c.face(6, { mouth: 'o' });
  c.k('mouth_o.s', [[6, [100, 100]], [12, [140, 150]], [40, [140, 150]], [50, [100, 100]]]);
  c.k('eyeL_open.s', [[4, [100, 100]], [10, [126, 126]], [42, [126, 126]], [52, [100, 100]]]);
  c.k('eyeR_open.s', [[4, [100, 100]], [10, [126, 126]], [42, [126, 126]], [52, [100, 100]]]);
  c.k('whiskerL.s', [[4, [100, 100]], [9, [130, 130]], [12, [118, 118]], [42, [118, 118]], [52, [100, 100]]]);
  c.k('whiskerR.s', [[4, [100, 100]], [9, [130, 130]], [12, [118, 118]], [42, [118, 118]], [52, [100, 100]]]);
  c.rk('whiskerL.r', [[4, 0], [9, 8], [12, 4], [42, 4], [52, 0]]);
  c.rk('whiskerR.r', [[4, 0], [9, -8], [12, -4], [42, -4], [52, 0]]);
  c.rk('earL.r', [[4, 0], [10, 14], [42, 14], [52, 0]]);
  c.rk('earR.r', [[4, 0], [10, -14], [42, -14], [52, 0]]);
  go(c, 4, 12, { pawL: { r: 54 }, pawR: { r: -52 } });
  go(c, 40, 54, SIT);
  fx(c, FX.bang, cv(372, -12), 8, 46, { size: 110, pin: 4, pulse: 6 });
  c.face(50, { mouth: 'smile' });
});

clip('mood_hungry', 'moods', 'sit', 100, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  const rub = pawTo(212, 296, 238, 350);
  go(c, 2, 12, { pawL: rub });
  for (let i = 0; i < 6; i++) {
    const t = 12 + i * 10;
    c.k('pawL.p', [[t, rub.p], [t + 5, add(rub.p, [10, 6])], [t + 10, rub.p]]);
    c.k('pawL.r', [[t, rub.r], [t + 5, rub.r - 14], [t + 10, rub.r]]);
  }
  go(c, 74, 88, { pawL: SIT.pawL });
  look(c, 10, 20, [0.8, -0.8]); lookBack(c, 80, 90);
  c.rk('head.r', [[10, 0], [20, 5], [80, 5], [90, 0]]);
  c.face(20, { mouth: 'o' }); c.face(46, { mouth: 'open' }); c.face(84, { mouth: 'smile' });
  c.k('mouth_o.s', [[20, [100, 100]], [26, [80, 70]], [32, [100, 100]], [38, [80, 70]], [44, [100, 100]]]);
  c.rk('char.s', [[10, [0, 0]], [30, [1, -1.5]], [50, [0, 0]], [70, [1, -1.5]], [90, [0, 0]]]);
  const b = fx(c, FX.thought, cv(470, 82), 12, 86, { size: 92, pin: 8, pout: 8 });
  c.k(`${b.id}.p`, [[12, cv(470, 82)], [30, add(cv(470, 82), [0, -5])], [50, cv(470, 82)], [70, add(cv(470, 82), [0, -5])], [86, cv(470, 82)]]);
});

clip('mood_love', 'moods', 'sit', 100, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  go(c, 2, 14, HUG);
  c.face(8, { eyes: 'heart', mouth: 'open' });
  c.k('eyeL_heart.s', [[8, [100, 100]], ...Array.from({ length: 8 }, (_, i) => [16 + i * 8, i % 2 ? [100, 100] : [115, 115]]), [86, [100, 100]]]);
  c.k('eyeR_heart.s', [[8, [100, 100]], ...Array.from({ length: 8 }, (_, i) => [16 + i * 8, i % 2 ? [100, 100] : [115, 115]]), [86, [100, 100]]]);
  c.h('pebbleHeart.o', [[14, 100], [84, 0]]);
  c.k('pebbleHeart.s', [[0, [100, 100]], [13, [0, 0]], [14, [0, 0]], [20, [120, 120]], [26, [100, 100]], [78, [100, 100]], [84, [0, 0]], [86, [100, 100]]]);
  c.h('blush.o', [[10, 100], [88, 0]]);
  c.rk('spin.r', [[10, 0], [26, -4], [44, 4], [62, -4], [78, 4], [90, 0]]);
  c.rk('head.r', [[10, 0], [28, -3], [46, 3], [64, -3], [80, 3], [90, 0]]);
  c.k('pebbleRot.s', [[14, [100, 100]], [20, [108, 92]], [26, [100, 100]]]);
  go(c, 82, 94, { pebble: { p: [328, 350] }, ...SIT });
  c.face(88, { eyes: 'open', mouth: 'smile' });
  fx(c, FX.heart, cv(140, 120), 16, 50, { drift: [-12, -46], size: 90, rot: 10 });
  fx(c, FX.heart, cv(380, 100), 30, 64, { drift: [12, -46], size: 110, rot: 10 });
  fx(c, FX.heart, cv(120, 300), 46, 80, { drift: [-10, -46], size: 70, rot: 10 });
  fx(c, FX.heart, cv(400, 280), 58, 90, { drift: [10, -46], size: 85, rot: 10 });
});

clip('mood_smile_wink', 'moods', 'sit', 64, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.rk('head.r', [[2, 0], [12, 8], [44, 8], [56, 0]]);
  c.rk('char.s', [[2, [0, 0]], [10, [3, -3]], [16, [0, 0]]]);
  c.face(6, { mouth: 'open' });
  c.k('mouth_open.s', [[6, [100, 100]], [12, [122, 122]], [44, [122, 122]], [52, [100, 100]]]);
  for (const id of ['cheekL', 'cheekR']) c.k(`${id}.s`, [[6, [100, 100]], [12, [120, 120]], [46, [120, 120]], [54, [100, 100]]]);
  c.face(14, { eyeR: 'wink', eyeL: 'open' });
  c.face(42, { eyes: 'open' });
  c.face(54, { mouth: 'smile' });
  go(c, 10, 18, { pawR: { r: -30 } }); go(c, 40, 52, { pawR: SIT.pawR });
  fx(c, FX.sparkle, cv(372, 110), 14, 40, { size: 110, rot: 25, pin: 4 });
  fx(c, FX.sparkle, cv(400, 160), 20, 38, { size: 60, rot: 25, pin: 4 });
});

// ---------------- FUN ----------------
clip('fun_spin', 'fun', 'sit', 64, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  grabR(c, 0, 6);
  c.k('char.s', [[6, [100, 100]], [10, [110, 88]], [16, [96, 106]], [22, [100, 100]], [36, [100, 100]], [39, [114, 86]], [44, [97, 103]], [50, [100, 100]]]);
  c.rk('char.p', [[10, [0, 0]], [22, [0, -120]], [37, [0, 0]]]);
  c.rk('spin.r', [[12, 0], [36, 360]]);
  go(c, 8, 14, { pawL: { r: 70 }, pawR: { r: -70 }, footL: { r: 20 }, footR: { r: -20 } });
  c.rk('tail1.r', [[12, 0], [18, 50], [26, -40], [32, 30], [40, 0]]);
  c.rk('tail2.r', [[12, 0], [20, 30], [28, -30], [34, 20], [42, 0]]);
  go(c, 34, 44, { pawL: SIT.pawL, pawR: SIT.pawR, footL: { r: 0 }, footR: { r: 0 } });
  c.face(12, { eyes: 'squint', mouth: 'open' });
  c.face(38, { eyes: 'happy', mouth: 'open' });
  c.face(56, { eyes: 'open', mouth: 'smile' });
  releaseR(c, 50, 58, [328, 350]);
  fx(c, FX.sparkle, cv(120, 330), 38, 54, { size: 80 });
  fx(c, FX.sparkle, cv(400, 320), 40, 56, { size: 70 });
  c.k('shadow.s', [[10, [100, 100]], [22, [55, 55]], [37, [100, 100]]]);
});

clip('fun_peek', 'fun', 'peekHidden', 96, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  c.k('char.p', [[4, [256, 930]], [18, [256, 650]], [24, [256, 664]], [28, [256, 660]], [62, [256, 660]], [78, [256, 930]]]);
  splash(c, [256, 414], 14, 30, 5, 36, 90);
  ripple(c, [256, 423], 16, 46, 60, 11);
  fx(c, FX.bubble, [220, 470], 2, 18, { drift: [0, -40], size: 70 });
  fx(c, FX.bubble, [290, 488], 6, 22, { drift: [4, -54], size: 90 });
  wig(c, 'whiskerL.r', 30, 3, [-9, 5, -4]); wig(c, 'whiskerR.r', 30, 3, [9, -5, 4]);
  wig(c, 'whiskerL.r', 46, 3, [-9, 5]); wig(c, 'whiskerR.r', 46, 3, [9, -5]);
  look(c, 30, 38, [-1, 0]); look(c, 40, 48, [1, 0]); lookBack(c, 52, 58);
  c.blink(56, 2.5);
  c.rk('earL.r', [[28, 0], [32, -14], [38, 0]]); c.rk('earR.r', [[28, 0], [32, 14], [38, 0]]);
  c.face(62, { eyes: 'squint', mouth: 'o' });
  c.face(82, { eyes: 'open', mouth: 'smile' });
  ripple(c, [256, 423], 72, 94, 50, 10);
  for (const [x, t, d] of [[230, 66, -50], [270, 72, -60], [248, 78, -44], [286, 82, -40]]) fx(c, FX.bubble, [x, 480], t, t + 12, { drift: [0, d], size: 60 + (x % 40) });
});

clip('fun_notify', 'fun', 'notify', 60, true, (c) => {
  c.rk('char.p', [[0, [0, 0]], [15, [0, -5]], [30, [0, 0]], [45, [0, -5]], [60, [0, 0]]]);
  c.k('badge.s', [[0, [100, 100]], [6, [116, 116]], [12, [100, 100]], [30, [100, 100]], [36, [116, 116]], [42, [100, 100]]]);
  c.rk('badge.r', [[0, 0], [5, -10], [10, 10], [15, -6], [20, 0], [30, 0], [35, -10], [40, 10], [45, -6], [50, 0]]);
  c.rk('pawL.r', [[0, 0], [5, -8], [10, 0], [30, 0], [35, -8], [40, 0]]);
  c.rk('pawR.r', [[0, 0], [5, 8], [10, 0], [30, 0], [35, 8], [40, 0]]);
  c.rk('head.r', [[0, 0], [15, 3], [30, 0], [45, 3], [60, 0]]);
  const bp = cv(396, 304);
  fx(c, FX.badgeGlow, bp, 2, 20, { size: 90, pin: 3 });
  fx(c, FX.badgeGlow, bp, 32, 50, { size: 90, pin: 3 });
  c.blink(48, 2.5);
});

clip('fun_pebble_gift', 'fun', 'sit', 120, true, (c) => {
  c.faceStart({ eyes: 'open', mouth: 'smile' });
  go(c, 2, 16, HUG);
  c.h('blush.o', [[6, 100], [110, 0]]);
  for (const id of ['cheekL', 'cheekR']) c.k(`${id}.s`, [[4, [100, 100]], [14, [132, 132]], [104, [132, 132]], [112, [100, 100]]]);
  look(c, 4, 14, [-0.8, 0.7]);
  c.rk('head.r', [[4, 0], [14, -8], [30, -4], [56, -4], [66, -2], [100, -2], [112, 0]]);
  c.rk('spin.r', [[4, 0], [14, -3], [30, 0]]);
  // offer it toward the viewer
  const offL = pawTo(220, 292, 234, 300), offR = pawTo(292, 292, 278, 300);
  go(c, 20, 34, { pawL: { ...offL, s: [114, 114] }, pawR: { ...offR, s: [114, 114] }, pebble: { p: [256, 300] } });
  c.k('pebbleRot.s', [[20, [100, 100]], [34, [138, 138]], [56, [138, 138]], [66, [100, 100]]]);
  c.rk('char.s', [[20, [0, 0]], [34, [2, -2]], [56, [2, -2]], [66, [0, 0]]]);
  look(c, 26, 34, [0.1, -0.3]);
  c.face(30, { mouth: 'o' });
  c.k('mouth_o.s', [[28, [100, 100]], [30, [70, 60]], [60, [70, 60]], [62, [100, 100]]]);
  fx(c, FX.sparkle, cv(300, 220), 36, 54, { size: 70, rot: 20 });
  // pull back and hug
  go(c, 56, 66, { pawL: { ...HUG.pawL, s: [100, 100] }, pawR: { ...HUG.pawR, s: [100, 100] }, pebble: HUG.pebble });
  lookBack(c, 56, 64);
  c.face(60, { eyes: 'happy', mouth: 'open' });
  c.k('pebbleRot.r', [[66, 0], [72, -6], [78, 6], [84, -6], [90, 0]]);
  fx(c, FX.heart, cv(256, 240), 66, 96, { drift: [0, -40], size: 85 });
  go(c, 96, 110, { pebble: { p: [328, 350] }, ...SIT });
  c.face(104, { eyes: 'open', mouth: 'smile' });
});

function buildClips(buildRig, Clip) {
  const errs = [];
  const out = defs.map((d) => {
    const c = new Clip(buildRig(), poses, { name: d.name, cat: d.cat, base: d.base, frames: d.frames, loop: d.loop });
    try { d.fn(c); c.finalize(); } catch (e) { errs.push(e.message); }
    return c;
  });
  if (errs.length) throw new Error('\n' + errs.join('\n'));
  return out;
}
module.exports = { defs, buildClips };
