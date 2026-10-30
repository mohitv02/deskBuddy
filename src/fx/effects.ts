// Particle effects for alarms. Each is self-contained and loops until the
// overlay window is closed. All drawing is relative to an origin point (the
// mascot's mouth/hand/antenna) and a horizontal direction toward open space.

export interface Origin {
  x: number;
  y: number;
  dir: 1 | -1;
}

export interface Effect {
  step(dt: number): void;
  draw(ctx: CanvasRenderingContext2D): void;
}

const rand = (a: number, b: number) => a + Math.random() * (b - a);

/** Breath of fire: bursts of glowing particles that cool from white to smoke. */
function flames(o: Origin): Effect {
  type P = { x: number; y: number; vx: number; vy: number; age: number; life: number; size: number };
  const ps: P[] = [];
  let t = 0;
  let carry = 0;
  return {
    step(dt) {
      t += dt;
      const breathing = t % 1.9 < 1.3; // breathe 1.3 s, pause 0.6 s
      carry += breathing ? dt * 160 : 0;
      for (; carry >= 1; carry--) {
        const angle = rand(-0.22, 0.12); // slightly upward cone
        const speed = rand(190, 270);
        ps.push({
          x: o.x,
          y: o.y,
          vx: Math.cos(angle) * speed * o.dir,
          vy: Math.sin(angle) * speed,
          age: 0,
          life: rand(0.55, 0.9),
          size: rand(4, 7),
        });
      }
      for (const p of ps) {
        p.age += dt;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.vx *= 1 - 0.9 * dt;
        p.vy -= 60 * dt; // hot air rises
      }
      for (let i = ps.length - 1; i >= 0; i--) if (ps[i].age > ps[i].life) ps.splice(i, 1);
    },
    draw(ctx) {
      for (const p of ps) {
        const k = p.age / p.life;
        const r = p.size + k * 20;
        if (k > 0.65) {
          ctx.globalCompositeOperation = "source-over";
          ctx.fillStyle = `rgba(70,70,70,${(0.35 * (1 - k)) / 0.35})`;
        } else {
          ctx.globalCompositeOperation = "lighter";
          const g = Math.round(240 - k * 300);
          ctx.fillStyle = `rgba(255,${Math.max(40, g)},${Math.max(0, 120 - k * 400)},${0.55 * (1 - k)})`;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
    },
  };
}

/** Web shots: a strand flies out, then a web unfurls where it lands and fades. */
function webs(o: Origin): Effect {
  type W = { tx: number; ty: number; age: number; radius: number; spin: number };
  const ws: W[] = [];
  let next = 0;
  const FLY = 0.18;
  const OPEN = 0.25;
  const HOLD = 1.4;
  const FADE = 0.5;
  return {
    step(dt) {
      next -= dt;
      if (next <= 0) {
        next = rand(0.7, 1.0);
        const angle = rand(-0.9, 0.35);
        const dist = rand(130, 230);
        ws.push({ tx: o.x + Math.cos(angle) * dist * o.dir, ty: o.y + Math.sin(angle) * dist, age: 0, radius: rand(26, 40), spin: rand(0, Math.PI) });
      }
      for (const w of ws) w.age += dt;
      for (let i = ws.length - 1; i >= 0; i--) if (ws[i].age > FLY + OPEN + HOLD + FADE) ws.splice(i, 1);
    },
    draw(ctx) {
      const strokeTwice = (draw: () => void, alpha: number) => {
        // Dark halo then bright line, so webs read on light and dark desktops.
        ctx.strokeStyle = `rgba(0,0,0,${0.35 * alpha})`;
        ctx.lineWidth = 3;
        draw();
        ctx.strokeStyle = `rgba(255,255,255,${0.95 * alpha})`;
        ctx.lineWidth = 1.3;
        draw();
      };
      for (const w of ws) {
        const fade = w.age > FLY + OPEN + HOLD ? 1 - (w.age - FLY - OPEN - HOLD) / FADE : 1;
        const fly = Math.min(1, w.age / FLY);
        const hx = o.x + (w.tx - o.x) * fly;
        const hy = o.y + (w.ty - o.y) * fly;
        strokeTwice(() => {
          ctx.beginPath();
          ctx.moveTo(o.x, o.y);
          ctx.quadraticCurveTo((o.x + hx) / 2, Math.min(o.y, hy) - 18, hx, hy);
          ctx.stroke();
        }, fade * (w.age < FLY + OPEN ? 1 : 0.6));
        if (w.age < FLY) continue;
        const open = Math.min(1, (w.age - FLY) / OPEN);
        const r = w.radius * (0.4 + 0.6 * open);
        const spokes = 8;
        const pt = (i: number, rr: number): [number, number] => {
          const a = w.spin + (i / spokes) * Math.PI * 2;
          return [w.tx + Math.cos(a) * rr, w.ty + Math.sin(a) * rr];
        };
        strokeTwice(() => {
          ctx.beginPath();
          for (let i = 0; i < spokes; i++) {
            const [x, y] = pt(i, r);
            ctx.moveTo(w.tx, w.ty);
            ctx.lineTo(x, y);
          }
          for (let ring = 1; ring <= 4; ring++) {
            const rr = (r * ring) / 4;
            for (let i = 0; i <= spokes; i++) {
              // Sag each segment toward the centre like real silk.
              const [x1, y1] = pt(i, rr);
              const [x2, y2] = pt(i + 1, rr);
              const [mx, my] = pt(i + 0.5, rr * 0.86);
              if (i === 0) ctx.moveTo(x1, y1);
              ctx.quadraticCurveTo(mx, my, x2, y2);
            }
          }
          ctx.stroke();
        }, fade * open);
      }
    },
  };
}

/** Throwing stars: spinning shuriken on ballistic arcs. */
function shuriken(o: Origin): Effect {
  type S = { x: number; y: number; vx: number; vy: number; a: number; age: number };
  const ss: S[] = [];
  let next = 0;
  return {
    step(dt) {
      next -= dt;
      if (next <= 0) {
        next = rand(0.28, 0.45);
        ss.push({ x: o.x, y: o.y, vx: rand(260, 360) * o.dir, vy: rand(-220, -60), a: 0, age: 0 });
      }
      for (const s of ss) {
        s.age += dt;
        s.x += s.vx * dt;
        s.y += s.vy * dt;
        s.vy += 380 * dt;
        s.a += 16 * dt * o.dir;
      }
      for (let i = ss.length - 1; i >= 0; i--) if (ss[i].age > 1.3) ss.splice(i, 1);
    },
    draw(ctx) {
      for (const s of ss) {
        const alpha = s.age > 1 ? 1 - (s.age - 1) / 0.3 : 1;
        ctx.save();
        ctx.translate(s.x, s.y);
        ctx.rotate(s.a);
        ctx.globalAlpha = alpha;
        ctx.beginPath();
        for (let i = 0; i < 8; i++) {
          const r = i % 2 === 0 ? 11 : 3.5;
          const a = (i / 8) * Math.PI * 2;
          ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r);
        }
        ctx.closePath();
        ctx.fillStyle = "#c9ced8";
        ctx.strokeStyle = "#2b2f3a";
        ctx.lineWidth = 1.5;
        ctx.fill();
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(0, 0, 2.2, 0, Math.PI * 2);
        ctx.fillStyle = "#2b2f3a";
        ctx.fill();
        ctx.restore();
      }
    },
  };
}

/** Electric bolts crackling out of the origin (built-in character's default). */
function sparks(o: Origin): Effect {
  type B = { pts: [number, number][]; age: number };
  const bs: B[] = [];
  let next = 0;
  return {
    step(dt) {
      next -= dt;
      if (next <= 0) {
        next = rand(0.12, 0.22);
        const angle = rand(-Math.PI * 0.95, -Math.PI * 0.05); // anywhere above
        const len = rand(70, 170);
        const pts: [number, number][] = [[o.x, o.y]];
        const n = 7;
        for (let i = 1; i <= n; i++) {
          const d = (len * i) / n;
          const jitter = i === n ? 0 : rand(-14, 14);
          pts.push([o.x + Math.cos(angle) * d - Math.sin(angle) * jitter, o.y + Math.sin(angle) * d + Math.cos(angle) * jitter]);
        }
        bs.push({ pts, age: 0 });
      }
      for (const b of bs) b.age += dt;
      for (let i = bs.length - 1; i >= 0; i--) if (bs[i].age > 0.28) bs.splice(i, 1);
    },
    draw(ctx) {
      for (const b of bs) {
        const alpha = 1 - b.age / 0.28;
        const path = () => {
          ctx.beginPath();
          b.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
          ctx.stroke();
        };
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.shadowColor = "rgba(255,200,40,0.9)";
        ctx.shadowBlur = 14;
        ctx.strokeStyle = `rgba(255,190,40,${alpha})`;
        ctx.lineWidth = 5;
        path();
        ctx.shadowBlur = 0;
        ctx.strokeStyle = `rgba(255,255,235,${alpha})`;
        ctx.lineWidth = 1.8;
        path();
      }
    },
  };
}

export const effects: Record<string, (o: Origin) => Effect> = { flames, webs, shuriken, sparks };
