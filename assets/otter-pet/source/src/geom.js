// Path model shared by both exporters: Lottie-style vertices with relative in/out tangents.
const K = 0.5522847498;
const r2 = (n) => Math.round(n * 100) / 100;

class P {
  constructor() { this.subs = []; this.cur = null; }
  M(x, y) { this.cur = { start: [x, y], segs: [], closed: false }; this.subs.push(this.cur); this.pt = [x, y]; return this; }
  L(x, y) { this.cur.segs.push([this.pt.slice(), [x, y], [x, y]]); this.pt = [x, y]; return this; }
  C(x1, y1, x2, y2, x, y) { this.cur.segs.push([[x1, y1], [x2, y2], [x, y]]); this.pt = [x, y]; return this; }
  Q(qx, qy, x, y) { const [px, py] = this.pt; return this.C(px + 2 / 3 * (qx - px), py + 2 / 3 * (qy - py), x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y), x, y); }
  // arc around (cx,cy) radius r from angle a0 to a1 (deg, screen coords, clockwise positive). Current point assumed at a0.
  A(cx, cy, r, a0, a1, ry) {
    ry = ry ?? r;
    const n = Math.max(1, Math.ceil(Math.abs(a1 - a0) / 90 - 1e-9));
    const d = (a1 - a0) / n;
    for (let k = 0; k < n; k++) {
      const s = (a0 + d * k) * Math.PI / 180, e = (a0 + d * (k + 1)) * Math.PI / 180;
      const h = 4 / 3 * Math.tan((e - s) / 4);
      const p0 = [cx + r * Math.cos(s), cy + ry * Math.sin(s)], p3 = [cx + r * Math.cos(e), cy + ry * Math.sin(e)];
      const c1 = [p0[0] - h * r * Math.sin(s), p0[1] + h * ry * Math.cos(s)];
      const c2 = [p3[0] + h * r * Math.sin(e), p3[1] - h * ry * Math.cos(e)];
      this.C(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1]);
    }
    return this;
  }
  Z() { this.cur.closed = true; return this; }
  // convert to list of Lottie paths
  toLottie() {
    return this.subs.map((s) => {
      const v = [s.start], ii = [[0, 0]], oo = [];
      for (const [c1, c2, p] of s.segs) {
        const prev = v[v.length - 1];
        oo.push([c1[0] - prev[0], c1[1] - prev[1]]);
        v.push(p); ii.push([c2[0] - p[0], c2[1] - p[1]]);
      }
      oo.push([0, 0]);
      if (s.closed) {
        const last = v[v.length - 1];
        if (v.length > 1 && Math.hypot(last[0] - s.start[0], last[1] - s.start[1]) < 0.01) {
          ii[0] = ii[ii.length - 1]; v.pop(); ii.pop(); oo.pop(); // the final segment closes onto vertex 0
          // oo[n-1] already holds c1 of closing segment
        }
      }
      const R = (a) => a.map((q) => [r2(q[0]), r2(q[1])]);
      return { i: R(ii), o: R(oo), v: R(v), c: s.closed };
    });
  }
}

function svgD(paths) {
  const f = (n) => String(r2(n));
  let d = '';
  for (const p of paths) {
    const { v, i, o, c } = p; const n = v.length;
    d += `M${f(v[0][0])} ${f(v[0][1])}`;
    const seg = (a, b) => {
      const z = o[a][0] === 0 && o[a][1] === 0 && i[b][0] === 0 && i[b][1] === 0;
      if (z) d += `L${f(v[b][0])} ${f(v[b][1])}`;
      else d += `C${f(v[a][0] + o[a][0])} ${f(v[a][1] + o[a][1])} ${f(v[b][0] + i[b][0])} ${f(v[b][1] + i[b][1])} ${f(v[b][0])} ${f(v[b][1])}`;
    };
    for (let k = 0; k < n - 1; k++) seg(k, k + 1);
    if (c) { seg(n - 1, 0); d += 'Z'; }
  }
  return d;
}

const ellipse = (cx, cy, rx, ry = rx) => new P().M(cx + rx, cy).A(cx, cy, rx, 0, 360, ry).Z();
// tapered capsule from (x,y) along angle (deg, 0 = +x) of length len, radii r1 (base) r2 (tip)
function capsule(x, y, ang, len, r1, r2_) {
  const a = ang * Math.PI / 180, ux = Math.cos(a), uy = Math.sin(a), nx = -uy, ny = ux;
  const tx = x + ux * len, ty = y + uy * len;
  const p = new P().M(x + nx * r1, y + ny * r1).L(tx + nx * r2_, ty + ny * r2_)
    .A(tx, ty, r2_, ang + 90, ang - 90).L(x - nx * r1, y - ny * r1).A(x, y, r1, ang - 90, ang - 270).Z();
  return p;
}
function rrect(x, y, w, h, r) {
  return new P().M(x + r, y).L(x + w - r, y).A(x + w - r, y + r, r, -90, 0).L(x + w, y + h - r).A(x + w - r, y + h - r, r, 0, 90)
    .L(x + r, y + h).A(x + r, y + h - r, r, 90, 180).L(x, y + r).A(x + r, y + r, r, 180, 270).Z();
}
function heart(cx, cy, s) { // s ~ half width
  const k = s / 10;
  return new P().M(cx, cy + 9 * k).C(cx - 4 * k, cy + 5 * k, cx - 10 * k, cy + 1 * k, cx - 10 * k, cy - 4 * k)
    .C(cx - 10 * k, cy - 8.5 * k, cx - 6.5 * k, cy - 10 * k, cx - 4.8 * k, cy - 10 * k)
    .C(cx - 2.5 * k, cy - 10 * k, cx - 0.8 * k, cy - 8.5 * k, cx, cy - 6.5 * k)
    .C(cx + 0.8 * k, cy - 8.5 * k, cx + 2.5 * k, cy - 10 * k, cx + 4.8 * k, cy - 10 * k)
    .C(cx + 6.5 * k, cy - 10 * k, cx + 10 * k, cy - 8.5 * k, cx + 10 * k, cy - 4 * k)
    .C(cx + 10 * k, cy + 1 * k, cx + 4 * k, cy + 5 * k, cx, cy + 9 * k).Z();
}
function star(cx, cy, R, r, n = 5, rot = -90) {
  const p = new P();
  for (let k = 0; k < n * 2; k++) {
    const a = (rot + k * 180 / n) * Math.PI / 180, rr = k % 2 ? r : R;
    const x = cx + rr * Math.cos(a), y = cy + rr * Math.sin(a);
    k ? p.L(x, y) : p.M(x, y);
  }
  return p.Z();
}
function sparkle(cx, cy, R) { // 4-point curved star
  const r = R * 0.22;
  return new P().M(cx, cy - R).Q(cx + r, cy - r, cx + R, cy).Q(cx + r, cy + r, cx, cy + R).Q(cx - r, cy + r, cx - R, cy).Q(cx - r, cy - r, cx, cy - R).Z();
}
module.exports = { P, svgD, ellipse, capsule, rrect, heart, star, sparkle, r2 };
