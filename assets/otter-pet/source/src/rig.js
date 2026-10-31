// Otter rig: every part is a node {id, a, p, r, s, o, items}. Coordinates are "design space"
// (512 canvas at 100%); the root node scales the character to 80% around the feet (256,470).
const G = require('./geom');
const { P, ellipse, capsule, rrect, heart, star, sparkle } = G;

const C = {
  OL: '#4a2a1c', FUR: '#a66d45', FUR_D: '#8f5a37', CREAM: '#f9e8cf', PEACH: '#f5bf9c', CHEEK: '#f3a1a1',
  NOSE: '#3a2018', EYE: '#2b1810', W: '#ffffff', PEB: '#bab2d2', PEB_D: '#a79fc2', TONGUE: '#f08690', MOUTH: '#7b3a35',
  WATER: '#a9dcf3', WATER_EDGE: '#6db7e0', WAVE: '#ffffff', CLAM: '#f7c9ad', CLAM_L: '#fde3d2', MEAT: '#f59fae',
  HEART: '#f47f93', SPARK: '#ffd25e', Z: '#8e9cd8', BADGE: '#ffd35c', ANGER: '#ee6b6b', TEAR: '#9fd5f4', BUBBLE: '#cfeefc',
};
const OLW = 7.5;      // 6px on canvas after the 80% root scale
const DW = 4.5;       // inner detail lines

const shape = (paths, fill, stroke, sw = OLW, extra = {}) => ({ shape: true, paths: paths.toLottie ? paths.toLottie() : paths, fill, stroke, sw, ...extra });
const node = (id, opts = {}, items = []) => ({ id, a: opts.a || [0, 0], p: opts.p || (opts.a ? opts.a.slice() : [0, 0]), r: opts.r || 0, s: opts.s || [100, 100], o: opts.o ?? 100, items });
const fillOnly = (p, c, extra) => shape(p, c, null, 0, extra);
const line = (p, c = C.OL, w = DW) => shape(p, null, c, w);
const both = (p, fill, w = OLW) => shape(p, fill, C.OL, w);

// ---------- tail: 3 tapered segments, children behind parents, no seam lines -----
function tailSeg(id, len, r1, r2, last, child, opts) {
  const fill = capsule(0, 0, 0, len, r1, r2);
  let outline;
  if (last) outline = capsule(0, 0, 0, len, r1, r2);
  else outline = new P().M(len, -r2).L(0, -r1).A(0, 0, r1, -90, -270).L(len, r2);
  const items = [];
  if (child) items.push(child);
  items.push(fillOnly(fill, C.FUR));
  items.push(line(outline, C.OL, OLW));
  return node(id, opts, items);
}

function eyeVariants(side) {
  const m = side === 'L' ? 1 : -1;
  const open = node(`eye${side}_open`, {}, [
    fillOnly(ellipse(0, 0, 18, 22), C.EYE),
    fillOnly(ellipse(5, -9, 7.5, 7.5), C.W),
    fillOnly(ellipse(-6, 8, 3.6, 3.6), C.W),
  ]);
  const sleepy = node(`eye${side}_sleepy`, { o: 0 }, [line(new P().M(-16, -1).C(-10, 11, 10, 11, 16, -1), C.OL, 5.5)]);
  const happy = node(`eye${side}_happy`, { o: 0 }, [line(new P().M(-16, 6).C(-10, -11, 10, -11, 16, 6), C.OL, 5.5)]);
  const squint = node(`eye${side}_squint`, { o: 0 }, [line(new P().M(-13 * m, -10).L(11 * m, 0).L(-13 * m, 10), C.OL, 5.5)]);
  const wink = node(`eye${side}_wink`, { o: 0 }, [line(new P().M(-16, 3).C(-8, -7, 8, -7, 16, 3).M(-16 * m, 3).L(-22 * m, -3), C.OL, 5)]);
  const hrt = node(`eye${side}_heart`, { o: 0 }, [both(heart(0, 1, 21), C.HEART, 4), fillOnly(ellipse(-7, -5, 3.5, 2.5), C.W)]);
  const sp = new P().M(0, 0);
  for (let k = 1; k <= 16; k++) { const a = k * 45 * Math.PI / 180, rr = k * 1.15; sp.L(rr * Math.cos(a), rr * Math.sin(a)); }
  const dizzy = node(`eye${side}_dizzy`, { o: 0 }, [line(sp, C.OL, 4)]);
  return [open, sleepy, happy, squint, wink, hrt, dizzy];
}

function buildRig() {
  // ---------- head ----------
  const hx = 256, hy = 150, hrx = 130, hry = 118;
  const ear = (id, x, y) => node(id, { a: [x, y + 10] }, [both(ellipse(x, y, 24, 22), C.FUR), fillOnly(ellipse(x + (x < hx ? 3 : -3), y + 2, 11, 10), C.PEACH)]);
  // cream face mask: bottom follows head ellipse (inset by half stroke), top is a soft double hump around the eyes
  const ia = hrx - 3.6, ib = hry - 3.6;
  const ep = (t) => [hx + ia * Math.cos(t * Math.PI / 180), hy + ib * Math.sin(t * Math.PI / 180)];
  const [rx0, ry0] = ep(14), [lx0, ly0] = ep(166);
  const faceMask = new P().M(rx0, ry0).A(hx, hy, ia, 14, 166, ib)
    .C(lx0 - 2, ly0 - 40, 160, 104, 204, 104).C(232, 104, 244, 120, 256, 124).C(268, 120, 280, 104, 308, 104).C(352, 104, rx0 + 2, ry0 - 40, rx0, ry0).Z();

  const whiskerGroup = (id, side) => {
    const m = side === 'L' ? -1 : 1, x0 = 256 + m * 40;
    const p = new P()
      .M(x0, 199).C(x0 + m * 22, 192, x0 + m * 44, 188, x0 + m * 64, 189)
      .M(x0 + m * 2, 207).C(x0 + m * 24, 206, x0 + m * 46, 207, x0 + m * 66, 209)
      .M(x0, 215).C(x0 + m * 22, 220, x0 + m * 42, 225, x0 + m * 60, 229);
    return node(id, { a: [x0, 207] }, [line(p, C.OL, 3.6)]);
  };
  const mouthV = (id, items, o = 0, a = [256, 214]) => node(id, { a, o }, items);
  const mouthOpenD = new P().M(242, 209).L(270, 209).C(270, 233, 242, 233, 242, 209).Z();
  const mouthGrinD = new P().M(236, 209).L(276, 209).C(276, 236, 236, 236, 236, 209).Z();
  const yawnD = ellipse(256, 228, 15, 20);
  const mouths = node('mouth', { a: [256, 214] }, [
    mouthV('mouth_smile', [line(new P().M(256, 201).L(256, 213).M(240, 210).C(242, 219, 252, 220, 256, 213).C(260, 220, 270, 219, 272, 210), C.OL, 4.2)], 100),
    mouthV('mouth_open', [fillOnly(mouthOpenD, C.MOUTH), fillOnly(new P().M(247, 228).C(249, 220, 263, 220, 265, 228).C(261, 232, 251, 232, 247, 228).Z(), C.TONGUE), line(mouthOpenD, C.OL, 4.2)]),
    mouthV('mouth_o', [both(ellipse(256, 218, 6.5, 8), C.MOUTH, 4)], 0, [256, 218]),
    mouthV('mouth_yawn', [fillOnly(yawnD, C.MOUTH), fillOnly(new P().M(245, 240).C(248, 231, 264, 231, 267, 240).C(262, 246, 250, 246, 245, 240).Z(), C.TONGUE), line(yawnD, C.OL, 4.2)], 0, [256, 210]),
    mouthV('mouth_frown', [line(new P().M(243, 222).C(248, 212, 264, 212, 269, 222), C.OL, 4.5)]),
    mouthV('mouth_grin', [fillOnly(mouthGrinD, C.MOUTH), fillOnly(new P().M(244, 231).C(248, 224, 264, 224, 268, 231).C(262, 235, 250, 235, 244, 231).Z(), C.TONGUE),
      both(rrect(248.5, 209, 7.5, 9, 2.5), C.W, 2.5), both(rrect(256, 209, 7.5, 9, 2.5), C.W, 2.5), line(mouthGrinD, C.OL, 4.2)]),
  ]);
  const brow = (id, pts) => node(id, { o: 0 }, [line(new P().M(...pts[0]).L(...pts[1]).M(...pts[2]).L(...pts[3]), C.OL, 5.5)]);
  const eyeL = node('eyeL', { p: [210, 160] }, eyeVariants('L'));
  const eyeR = node('eyeR', { p: [302, 160] }, eyeVariants('R'));
  const faceShift = node('faceShift', {}, [
    node('muzzle', { a: [256, 206] }, [fillOnly(ellipse(256, 206, 31, 19), C.PEACH)]),
    node('cheekL', { a: [176, 204] }, [fillOnly(ellipse(176, 204, 19, 11), C.CHEEK)]),
    node('cheekR', { a: [336, 204] }, [fillOnly(ellipse(336, 204, 19, 11), C.CHEEK)]),
    node('blush', { o: 0 }, [line(new P().M(166, 210).L(172, 198).M(176, 211).L(182, 199).M(186, 211).L(192, 199)
      .M(326, 211).L(332, 199).M(336, 211).L(342, 199).M(346, 210).L(352, 198), '#e9787c', 3)]),
    whiskerGroup('whiskerL', 'L'), whiskerGroup('whiskerR', 'R'),
    eyeL, eyeR,
    brow('brow_worried', [[190, 128], [222, 117], [322, 117], [290, 128]].map(([x, y]) => [x - (x < 256 ? 2 : -2), y])),
    brow('brow_angry', [[192, 116], [224, 128], [320, 116], [288, 128]].map(([x, y]) => [x - (x < 256 ? 2 : -2), y])),
    mouths,
    node('nose', { a: [256, 193] }, [fillOnly(new P().M(243, 189).C(243, 182, 269, 182, 269, 189).C(269, 197, 261, 202, 256, 202).C(251, 202, 243, 197, 243, 189).Z(), C.NOSE),
      fillOnly(ellipse(251, 187, 3.6, 2), C.W)]),
    node('tear', { a: [196, 182], o: 0 }, [both(new P().M(196, 176).C(200, 184, 203, 188, 203, 192).C(203, 197, 189, 197, 189, 192).C(189, 188, 192, 184, 196, 176).Z(), C.TEAR, 3)]),
    node('snot', { a: [258, 200], p: [258, 200], s: [0, 0] }, [both(ellipse(266, 213, 15, 14), C.BUBBLE, 3, { fo: 0.85 }), fillOnly(ellipse(271, 207, 4.5, 2.8), C.W)]),
  ]);
  const head = node('head', { a: [256, 262] }, [
    ear('earL', 160, 66), ear('earR', 352, 66),
    both(ellipse(hx, hy, hrx, hry), C.FUR),
    fillOnly(faceMask, C.CREAM),
    faceShift,
  ]);

  // ---------- body ----------
  const bodyD = new P().M(256, 236).C(322, 236, 354, 290, 358, 352).C(362, 424, 330, 474, 256, 474).C(182, 474, 150, 424, 154, 352).C(158, 290, 190, 236, 256, 236).Z();
  const bellyD = new P().M(256, 282).C(298, 282, 318, 326, 318, 376).C(318, 432, 292, 462, 256, 462).C(220, 462, 194, 432, 194, 376).C(194, 326, 214, 282, 256, 282).Z();
  const body = node('body', { a: [256, 354] }, [both(bodyD, C.FUR), node('belly', {}, [fillOnly(bellyD, C.CREAM)])]);

  // ---------- limbs ----------
  const paw = (id, x, y, r, held = []) => node(id, { p: [x, y], r }, [
    ...held,
    both(capsule(0, 0, 90, 50, 17, 22), C.FUR),
    line(new P().M(-7, 71).L(-7, 62).M(7, 71).L(7, 62), C.OL, 3.6),
  ]);
  const foot = (id, x, y, r = 0) => node(id, { p: [x, y], r }, [
    both(new P().M(-30, 2).C(-30, -16, 30, -16, 30, 2).C(30, 14, 20, 18, 0, 18).C(-20, 18, -30, 14, -30, 2).Z(), C.FUR),
    line(new P().M(-10, 17).L(-10, 9).M(10, 17).L(10, 9), C.OL, 3.6),
  ]);
  const tail = tailSeg('tail1', 42, 25, 20, false, tailSeg('tail2', 36, 20, 14, false, tailSeg('tail3', 28, 14, 5, true, null, { p: [36, 0], r: -32 }), { p: [42, 0], r: -30 }), { p: [334, 446], r: -12 });

  const pebbleShape = (id, o = 100) => node(id, { o }, [both(ellipse(0, 0, 25, 19), C.PEB, 6.5), fillOnly(ellipse(0, -9, 9, 3.6), C.W), fillOnly(ellipse(-13, 3, 3.5, 2.2), C.PEB_D), fillOnly(ellipse(12, 6, 2.6, 1.8), C.PEB_D),
    node('pebbleHeart', { o: 0, a: [0, 2], p: [0, 2] }, [fillOnly(heart(0, 2, 8.5), C.HEART), fillOnly(ellipse(-3.5, -1.5, 1.8, 1.3), C.W)])]);
  const pebble = node('pebble', { p: [328, 350] }, [node('pebbleY', {}, [node('pebbleRot', {}, [pebbleShape('pebbleBody')])])]);
  const pebbleHeld = node('pebbleHeld', { p: [0, 66], r: -6, o: 0 }, [both(ellipse(0, 0, 25, 19), C.PEB, 6.5), fillOnly(ellipse(0, -9, 9, 3.6), C.W), fillOnly(ellipse(-13, 3, 3.5, 2.2), C.PEB_D), fillOnly(ellipse(12, 6, 2.6, 1.8), C.PEB_D)]);
  const pebbleBack = node('pebbleBack', { p: [328, 350], o: 0 }, [both(ellipse(0, 0, 25, 19), C.PEB, 6.5), fillOnly(ellipse(0, -9, 9, 3.6), C.W)]);

  const clam = node('clam', { p: [0, 74], r: 76, o: 0, s: [0, 0] }, [
    fillOnly(ellipse(0, -1, 17, 8), C.MEAT),
    both(new P().M(-23, 0).C(-23, 17, 23, 17, 23, 0).Z(), C.CLAM, 5),
    node('clamTop', { a: [-23, 0] }, [both(new P().M(-23, 0).C(-23, -24, 23, -24, 23, 0).Z(), C.CLAM_L, 5),
      line(new P().M(0, -2).L(0, -14).M(-9, -2).L(-12, -12).M(9, -2).L(12, -12), C.OL, 3)]),
  ]);
  const badge = node('badge', { p: [322, 300], o: 0 }, [both(ellipse(0, 0, 28, 28), C.BADGE, 6.5),
    fillOnly(rrect(-4.5, -17, 9, 21, 4.5), C.OL), fillOnly(ellipse(0, 12, 5, 5), C.OL)]);

  const spin = node('spin', { a: [256, 300] }, [
    tail, pebbleBack, body,
    foot('footL', 214, 458), foot('footR', 298, 458),
    head,
    paw('pawL', 210, 290, -14, [clam]), paw('pawR', 302, 290, 6, [pebbleHeld]),
    pebble, badge,
  ]);
  const char = node('char', { a: [256, 470] }, [spin]);
  const character = node('character', { a: [256, 470], s: [80, 80] }, [char]);

  // ---------- canvas-space layers ----------
  const shadow = node('shadow', { a: [256, 471] }, [fillOnly(ellipse(256, 471, 96, 11), C.OL, { fo: 0.16 })]);
  const wavy = (y0, x0, x1, amp, wl) => {
    const p = new P().M(x0, y0); let x = x0, up = true;
    while (x < x1 - 0.1) { const nx = Math.min(x + wl, x1); p.Q((x + nx) / 2, y0 + (up ? -amp : amp), nx, y0); x = nx; up = !up; }
    return p;
  };
  const surface = wavy(420, -16, 528, 5, 34);
  const strip = new P().M(-16, 420); { let x = -16, up = true; while (x < 527.9) { const nx = x + 34; strip.Q((x + nx) / 2, 420 + (up ? -5 : 5), nx, 420); x = nx; up = !up; } }
  strip.L(528, 528).L(-16, 528).Z();
  const water = node('water', { o: 0 }, [
    fillOnly(strip, C.WATER, { fo: 0.94 }),
    line(surface, C.WATER_EDGE, 4.5),
    node('waves', {}, [line(wavy(458, 36, 230, 4, 24), C.WAVE, 4), line(wavy(458, 292, 476, 4, 23), C.WAVE, 4), line(wavy(490, 96, 416, 4, 26.7), C.WAVE, 4)]),
  ]);
  const fx = node('fx', {}, []);
  return { layers: [shadow, character, water, fx], C };
}

// effect prop factories (canvas space, drawn around origin)
const FX = {
  heart: (id, s = 14) => node(id, { s: [0, 0] }, [both(heart(0, 0, s), C.HEART, 3.5), fillOnly(ellipse(-s * 0.45, -s * 0.4, s * 0.17, s * 0.12), C.W)]),
  sparkle: (id, s = 16) => node(id, { s: [0, 0] }, [both(sparkle(0, 0, s), C.SPARK, 3)]),
  star: (id, s = 11) => node(id, { s: [0, 0] }, [both(star(0, 0, s, s * 0.48), C.SPARK, 3)]),
  z: (id, s = 10) => node(id, { s: [0, 0] }, [line(new P().M(-s, -s).L(s, -s).L(-s, s).L(s, s), C.Z, s * 0.45)]),
  bang: (id) => node(id, { s: [0, 0] }, [both(new P().M(-6, -24).C(-6, -30, 6, -30, 6, -24).L(3.5, 4).C(3.2, 7, -3.2, 7, -3.5, 4).Z(), C.SPARK, 3.5), both(ellipse(0, 15, 5.5, 5.5), C.SPARK, 3.5)]),
  question: (id) => node(id, { s: [0, 0] }, [line(new P().M(-9, -12).C(-9, -24, 11, -24, 11, -12).C(11, -4, 0, -4, 0, 5), C.OL, 9), line(new P().M(-9, -12).C(-9, -24, 11, -24, 11, -12).C(11, -4, 0, -4, 0, 5), C.SPARK, 4.5), both(ellipse(0, 17, 4.5, 4.5), C.SPARK, 3.5)]),
  drop: (id, s = 7) => node(id, { s: [0, 0] }, [both(new P().M(0, -s * 1.6).C(s * 0.5, -s * 0.6, s, 0, s, s * 0.45).C(s, s * 1.1, -s, s * 1.1, -s, s * 0.45).C(-s, 0, -s * 0.5, -s * 0.6, 0, -s * 1.6).Z(), C.TEAR, 2.5)]),
  bubble: (id, s = 7) => node(id, { s: [0, 0] }, [both(ellipse(0, 0, s, s), C.BUBBLE, 2.5, { fo: 0.9 }), fillOnly(ellipse(-s * 0.35, -s * 0.35, s * 0.25, s * 0.18), C.W)]),
  ripple: (id, rx = 40, ry = 9) => node(id, { s: [0, 0] }, [line(ellipse(0, 0, rx, ry), C.W, 4)]),
  anger: (id) => node(id, { s: [0, 0] }, [line(new P().M(-12, -4).C(-5, -4, -4, -5, -4, -12).M(4, -12).C(4, -5, 5, -4, 12, -4).M(12, 4).C(5, 4, 4, 5, 4, 12).M(-4, 12).C(-4, 5, -5, 4, -12, 4), C.ANGER, 4.5)]),
  thought: (id) => node(id, { s: [0, 0] }, [
    both(ellipse(-38, 52, 6, 6), C.W, 3.5), both(ellipse(-26, 36, 9, 9), C.W, 3.5),
    both(new P().M(-30, 4).C(-46, 4, -46, -22, -28, -22).C(-26, -38, 0, -40, 6, -28).C(18, -40, 44, -32, 38, -14).C(52, -8, 46, 16, 30, 14).C(24, 28, -2, 28, -6, 16).C(-18, 26, -38, 18, -30, 4).Z(), C.W, 3.5),
    // clam inside the bubble
    both(new P().M(-14, -4).C(-14, 7, 14, 7, 14, -4).Z(), C.CLAM, 3), both(new P().M(-14, -4).C(-14, -20, 14, -20, 14, -4).Z(), C.CLAM_L, 3),
    line(new P().M(0, -6).L(0, -14).M(-6, -6).L(-8, -12).M(6, -6).L(8, -12), C.OL, 2)]),
  splash: (id, n = 5, R = 34) => { // fan of droplets around origin pointing up
    const items = [];
    for (let k = 0; k < n; k++) {
      const ang = -90 + (k - (n - 1) / 2) * (120 / (n - 1));
      const a = ang * Math.PI / 180, x = R * Math.cos(a), y = R * Math.sin(a) * 0.9;
      const s = 6 + (k % 2) * 2;
      items.push(both(new P().M(x + Math.cos(a) * s * 1.7, y + Math.sin(a) * s * 1.7).C(x + Math.cos(a + 1.2) * s, y + Math.sin(a + 1.2) * s, x + Math.cos(a + 1.6) * s, y + Math.sin(a + 1.6) * s, x - Math.cos(a) * s, y - Math.sin(a) * s)
        .C(x + Math.cos(a - 1.6) * s, y + Math.sin(a - 1.6) * s, x + Math.cos(a - 1.2) * s, y + Math.sin(a - 1.2) * s, x + Math.cos(a) * s * 1.7, y + Math.sin(a) * s * 1.7).Z(), C.TEAR, 2.5));
    }
    return node(id, { s: [0, 0] }, items);
  },
  badgeGlow: (id) => node(id, { s: [0, 0] }, [line(new P().M(-34, -26).L(-42, -34).M(0, -40).L(0, -50).M(34, -26).L(42, -34), C.SPARK, 5)]),
  hand: (id) => node(id, { o: 0 }, [both(new P().M(-60, -30).C(-60, -52, 60, -52, 60, -30).C(60, -14, 44, -8, 30, -8).L(-30, -8).C(-44, -8, -60, -14, -60, -30).Z(), '#fde8d8', 5)]),
};

module.exports = { buildRig, FX, C, node, shape, OLW };
