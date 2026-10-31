// Builds the self-contained preview page (embeds every SVG and Lottie file).
const fs = require('fs'); const path = require('path');
const dist = path.join(__dirname, '../dist/otter-pet');
const idx = JSON.parse(fs.readFileSync(path.join(dist, 'index.json')));
const esc = (s) => s.replace(/<\//g, '<\\/');
const svgs = {}, lots = {};
for (const c of idx.clips) {
  svgs[c.name] = fs.readFileSync(path.join(dist, 'svg', c.name + '.svg'), 'utf8');
  lots[c.name] = JSON.parse(fs.readFileSync(path.join(dist, 'lottie', c.name + '.json')));
}
const data = `const CLIPS = ${JSON.stringify(idx.clips)};\nconst DEFAULT = ${JSON.stringify(idx.default)};\nconst SVGS = ${esc(JSON.stringify(svgs))};\nconst LOTTIES = ${esc(JSON.stringify(lots))};`;
const body = fs.readFileSync(path.join(__dirname, 'preview_template.html'), 'utf8').replace('/*__DATA__*/', data);
// artifact version (wrapped by the host) and a standalone version for the zip
fs.writeFileSync(process.argv[2], body);
fs.mkdirSync(path.join(dist, 'vendor'), { recursive: true });
fs.copyFileSync(require.resolve('lottie-web/build/player/lottie.min.js'), path.join(dist, 'vendor/lottie.min.js'));
const local = body.replace('<script src="https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js"></script>', '<script src="vendor/lottie.min.js"></script>');
fs.writeFileSync(path.join(dist, 'preview.html'), `<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n${local}\n</html>\n`);
console.log((fs.statSync(process.argv[2]).size / 1e6).toFixed(2), 'MB');
