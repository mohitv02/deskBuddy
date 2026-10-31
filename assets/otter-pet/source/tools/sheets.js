// Contact sheets of SVG frames for reviewing choreography: node tools/sheets.js outdir [clip...]
const fs = require('fs'); const path = require('path');
const H = require('./harness');
const dist = path.join(__dirname, '../dist/otter-pet');
(async () => {
  const out = process.argv[2]; fs.mkdirSync(out, { recursive: true });
  const index = JSON.parse(fs.readFileSync(path.join(dist, 'index.json'))).clips;
  const only = process.argv.slice(3);
  const list = index.filter((c) => !only.length || only.includes(c.name));
  const h = await H.open();
  const per = Number(process.env.PER || 4), cols = Number(process.env.COLS || 8);
  for (let g = 0; g < list.length; g += per) {
    const cells = [];
    for (const c of list.slice(g, g + per)) {
      const svg = fs.readFileSync(path.join(dist, 'svg', c.name + '.svg'), 'utf8');
      for (let i = 0; i < cols; i++) {
        const f = Math.round(i * (c.frames - 1) / (cols - 1));
        cells.push({ png: await h.svgFrame(svg, f), label: `${c.name} f${f}` });
      }
    }
    await h.sheet(cells, cols, path.join(out, `sheet_${String(g / per).padStart(2, '0')}.png`), { size: 170 });
  }
  await h.close();
})();
