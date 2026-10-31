// Base poses as overrides of the rig defaults (rig defaults = sitting).
const HEAD_A = [256, 262], HEAD_C = [256, 150];
const PAW_L = 50; // shoulder -> mitten centre
const rad = (d) => d * Math.PI / 180;
// head position so that the head centre lands on (cx,cy) with rotation r
function headAt(cx, cy, r) {
  const ox = HEAD_C[0] - HEAD_A[0], oy = HEAD_C[1] - HEAD_A[1];
  const c = Math.cos(rad(r)), s = Math.sin(rad(r));
  return { p: [cx - (ox * c - oy * s), cy - (ox * s + oy * c)], r };
}
// paw whose shoulder sits at (sx,sy) and whose mitten centre points at (tx,ty)
function pawTo(sx, sy, tx, ty, extra = {}) {
  const dx = tx - sx, dy = ty - sy;
  const r = Math.atan2(-dx, dy) * 180 / Math.PI;
  const len = Math.hypot(dx, dy);
  return { p: [sx, sy], r: Math.round(r * 10) / 10, ...(extra.stretch ? { s: [100, Math.round(len / PAW_L * 100)] } : {}) };
}
// mitten centre for a paw pose
function pawTip(p, r, s = [100, 100], d = PAW_L) {
  const L = d * s[1] / 100;
  return [p[0] - L * Math.sin(rad(r)), p[1] + L * Math.cos(rad(r))];
}

const sit = {};

const float = {
  shadow: { o: 0 },
  water: { o: 100 },
  body: { p: [334, 340], r: -90, s: [84, 118] },
  head: headAt(146, 286, -10),
  footL: { p: [408, 254], r: 206 },
  footR: { p: [450, 262], r: 158 },
  tail1: { p: [462, 360], r: -36 },
  tail2: { r: -24 },
  tail3: { r: -30 },
  pebble: { p: [384, 306] },
  pawL: pawTo(302, 280, 350, 292),
  pawR: pawTo(302, 352, 350, 330),
};

const poses = { sit, float };

// ---- derived poses ----
poses.sleep = {
  ...float,
  pawL: pawTo(124, 356, 104, 306),
  pawR: pawTo(212, 346, 194, 292),
  pebble: { p: [378, 310] },
  mouth_smile: { o: 0 }, mouth_o: { o: 100, s: [70, 70] },
  eyeL_open: { o: 0 }, eyeR_open: { o: 0 }, eyeL_sleepy: { o: 100 }, eyeR_sleepy: { o: 100 },
};

poses.walk = {
  shadow: { o: 100 },
  body: { p: [300, 386], r: -90, s: [80, 108] },
  belly: { o: 0 },
  head: headAt(170, 298, -4),
  footL: { p: [396, 458], r: 0 },
  footR: { p: [372, 462], r: 0 },
  tail1: { p: [418, 396], r: 8 },
  tail2: { r: 10 }, tail3: { r: 8 },
  pawL: pawTo(232, 392, 226, 440),
  pawR: pawTo(262, 398, 262, 444),
  pebble: { p: [300, 340], o: 0 },
};

poses.swim = {
  shadow: { o: 0 }, water: { o: 100 },
  char: { p: [256, 500] },
  body: { p: [306, 386], r: -90, s: [80, 112] },
  belly: { o: 0 },
  head: headAt(166, 290, -6),
  footL: { p: [430, 404], r: -60 },
  footR: { p: [416, 418], r: -100 },
  tail1: { p: [440, 382], r: 0 }, tail2: { r: 4 }, tail3: { r: 6 },
  pawL: pawTo(236, 382, 206, 420),
  pawR: pawTo(262, 392, 246, 432),
  pebble: { o: 0 },
};


// sitting variants
const SH_L = [210, 290], SH_R = [302, 290];
poses.dragged = {
  shadow: { o: 0 },
  char: { p: [256, 404] },
  body: { s: [96, 128] },
  footL: { p: [226, 494], r: 20 }, footR: { p: [288, 494], r: -20 },
  tail1: { p: [300, 470], r: 84 }, tail2: { r: 14 }, tail3: { r: 16 },
  pebble: { p: [256, 334] },
  pawL: pawTo(214, 286, 240, 334), pawR: pawTo(298, 286, 272, 334),
  mouth_smile: { o: 0 }, mouth_o: { o: 100 },
  eyeL_open: { s: [112, 112] }, eyeR_open: { s: [112, 112] },
  brow_worried: { o: 100 },
};
poses.peekHidden = { shadow: { o: 0 }, water: { o: 100 }, char: { p: [256, 930] } };
poses.notify = { ...float, pebble: { p: [384, 306], o: 0 }, badge: { p: [398, 304], o: 100 }, mouth_smile: { o: 0 }, mouth_open: { o: 100 } };
const DIRS = { up: [0, -1], up_right: [0.75, -0.75], right: [1, 0], down_right: [0.75, 0.75], down: [0, 1], down_left: [-0.75, 0.75], left: [-1, 0], up_left: [-0.75, -0.75] };
for (const [k, [dx, dy]] of Object.entries(DIRS)) {
  poses['look_' + k] = {
    eyeL: { p: [210 + 10 * dx, 160 + 8 * dy] }, eyeR: { p: [302 + 10 * dx, 160 + 8 * dy] },
    faceShift: { p: [6 * dx, 4 * dy] },
    head: { p: [256 + 3 * dx, 262], r: 4 * dx },
    whiskerL: { r: 5 * dy }, whiskerR: { r: -5 * dy },
  };
}
module.exports = { poses, headAt, pawTo, pawTip, PAW_L, DIRS, SH_L, SH_R };
