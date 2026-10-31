// Render key frames of every clip in both formats and pixel-diff them.
const fs = require('fs'); const path = require('path');
const { PNG } = require('pngjs'); const pixelmatch = require('pixelmatch');
const H = require('./harness');
const dist = path.join(__dirname, '../dist/otter-pet');
(async () => {
  const out = process.argv[2]; fs.mkdirSync(out, { recursive: true });
  const index = JSON.parse(fs.readFileSync(path.join(dist, 'index.json'))).clips;
  const h = await H.open();
  const report = []; const sheetCells = [];
  for (const c of index) {
    const svg = fs.readFileSync(path.join(dist, 'svg', c.name + '.svg'), 'utf8');
    const lot = JSON.parse(fs.readFileSync(path.join(dist, 'lottie', c.name + '.json')));
    const frames = [0, 0.2, 0.4, 0.6, 0.8, 1].map((q) => Math.min(c.frames - 1, Math.round(q * (c.frames - 1))));
    const rows = [];
    for (const f of frames) {
      const a = await h.svgFrame(svg, f), b = await h.lottieFrame(lot, f);
      const A = PNG.sync.read(a), B = PNG.sync.read(b);
      const diff = new PNG({ width: A.width, height: A.height });
      const n = pixelmatch(A.data, B.data, diff.data, A.width, A.height, { threshold: 0.1, includeAA: false });
      let painted = 0; for (let i = 3; i < A.data.length; i += 4) if (A.data[i] > 0 || B.data[i] > 0) painted++;
      rows.push({ frame: f, diffPixels: n, pctOfPainted: +(100 * n / Math.max(1, painted)).toFixed(3) });
      if (f === frames[2]) sheetCells.push({ png: a, label: `${c.name} f${f} SVG` }, { png: b, label: `${c.name} f${f} Lottie` }, { png: PNG.sync.write(diff), label: `diff ${n}px` });
    }
    const worst = rows.reduce((m, r) => (r.pctOfPainted > m.pctOfPainted ? r : m));
    report.push({ clip: c.name, frames_checked: frames, worst_frame: worst.frame, worst_diff_pixels: worst.diffPixels, worst_pct_of_painted: worst.pctOfPainted });
    console.log(c.name.padEnd(26), 'worst', worst.diffPixels, 'px', worst.pctOfPainted + '%', '@f' + worst.frame);
  }
  fs.writeFileSync(path.join(out, 'verify_report.json'), JSON.stringify(report, null, 2));
  for (let i = 0; i < sheetCells.length; i += 36) await h.sheet(sheetCells.slice(i, i + 36), 6, path.join(out, `compare_${String(i / 36).padStart(2, '0')}.png`), { size: 200 });
  await h.close();
})();
