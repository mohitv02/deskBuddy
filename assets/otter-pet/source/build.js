const fs = require('fs');
const path = require('path');
const { buildRig } = require('./src/rig');
const { Clip, toLottie, toSVG } = require('./src/anim');
const { buildClips } = require('./src/clips');
const OUT = process.env.OUT || path.join(__dirname, 'dist/otter-pet');
fs.mkdirSync(path.join(OUT, 'lottie'), { recursive: true });
fs.mkdirSync(path.join(OUT, 'svg'), { recursive: true });
const only = process.argv.slice(2);
const clips = buildClips(buildRig, Clip).filter((c) => !only.length || only.includes(c.meta.name));
const index = [];
for (const c of clips) {
  const L = toLottie(c), S = toSVG(c);
  fs.writeFileSync(path.join(OUT, 'lottie', c.meta.name + '.json'), JSON.stringify(L));
  fs.writeFileSync(path.join(OUT, 'svg', c.meta.name + '.svg'), S);
  const fam = { sit: 'sit', float: 'float', sleep: 'float', notify: 'float', swim: 'float', peekHidden: 'float', walk: 'sit', dragged: 'sit' }[c.meta.base] || (c.meta.base.startsWith('look_') ? 'sit' : c.meta.base);
  const ends = c.meta.loop ? c.meta.base : (c.meta.name === 'float_to_sit' ? 'sit' : 'float');
  index.push({ name: c.meta.name, category: c.meta.cat, base_pose: fam, start_pose: c.meta.name === 'move_fall_land' ? 'off_canvas_above' : c.meta.base, end_pose: c.meta.name === 'sleep_fall_asleep' ? 'sleep' : ends, frames: c.N, seconds: +(c.N / 30).toFixed(3), loop: c.meta.loop });
}
if (!only.length) fs.writeFileSync(path.join(OUT, 'index.json'), JSON.stringify({ fps: 30, width: 512, height: 512, default: 'float_idle', clips: index }, null, 2));
console.log(clips.length, 'clips');
