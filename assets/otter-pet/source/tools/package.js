const fs = require('fs'); const path = require('path');
const { defs } = require('../src/clips');
const D = path.join(__dirname, '../dist/otter-pet');
const idx = JSON.parse(fs.readFileSync(path.join(D, 'index.json')));
const desc = {
  float_idle: 'Bobs on gentle waves, turns the pebble over and back, one blink, slow tail sculling. Default loop.',
  float_crack_shell: 'Bangs a clam on the pebble twice, it pops open, nibbles with puffed cheeks.',
  float_roll: 'Rolls over once through the water with small splashes, then floats again.',
  float_wave: 'Waves its left paw at the viewer, then winks with a sparkle.',
  sit_to_float: 'Hops in with a splash and pops up floating on its back.',
  float_to_sit: 'Climbs out, shakes off water droplets, sits with the pebble under its arm.',
  idle_breathe: 'Slow squash-and-stretch breathing, one blink, whisker twitch, lazy tail swish.',
  idle_look_left_right: 'Eyes glance left, hold, then right; whiskers follow; a small "?" at the end.',
  idle_yawn: 'Big yawn with squinted eyes, head tilts back.',
  idle_stretch: 'Sets the pebble down, arms up overhead, body stretches taller, tail straight up.',
  idle_groom: 'Scrubs its face and whiskers fast with both paws.',
  idle_juggle_pebble: 'Tosses the pebble paw to paw four times, then hugs it.',
  sleep_fall_asleep: 'While floating, yawns and covers its eyes with both paws; pebble rests on its belly.',
  sleep_loop: 'Asleep with paws over eyes, gentle bob, slow breathing, rising z z z, snot bubble.',
  sleep_wake_up: 'Startled blink and "!", drops the pebble, catches it just before it sinks, hugs it in relief.',
  move_walk: 'Bouncy hump-backed lope in place, tail trailing (faces left).',
  move_hop: 'Crouch, jump with arms up (pebble in paw), squash on landing.',
  move_swim: 'Belly-down swim, head up, tail kicking, ripples behind (faces left).',
  move_fall_land: 'Drops in from above flailing, big splash ring, comes up floating with dizzy stars.',
  int_dragged: 'Held under the arms, body dangling like a noodle, clutching the pebble, surprised.',
  int_petted: 'Closes its eyes and leans into the hand, reaches a paw up, hearts pop up.',
  int_poked: 'Hides the pebble behind its back, puffed cheeks, angry brows, anger mark.',
  int_tickled: 'Wriggles and laughs, eyes squeezed shut, feet kicking.',
  mood_happy: 'Claps its paws and bounces, sparkles.',
  mood_sad: 'Droopy whiskers and ears, holds the pebble close, sad brows, teardrop.',
  mood_surprised: 'Jumps, whiskers spring out, big round eyes, "!" mark.',
  mood_hungry: 'Rubs its belly, thought bubble showing a clam.',
  mood_love: 'Heart eyes, hugs the pebble (tiny heart highlight), floating hearts.',
  mood_smile_wink: 'Big open smile with tongue, playful wink with a sparkle.',
  fun_spin: 'Cartwheel spin with the tail sweeping around, lands sitting with a squash.',
  fun_peek: 'Pops its head up through the water strip, whiskers twitch, sinks back with bubbles.',
  fun_notify: 'Floats holding a round yellow "!" badge in place of the pebble, happy open mouth.',
  fun_pebble_gift: 'Shyly offers its pebble toward the viewer, blushing, then pulls it back and hugs it.',
};
const rows = idx.clips.map((c) => `| \`${c.name}\` | ${c.category} | ${c.base_pose} | ${c.frames} | ${c.seconds.toFixed(2)} | ${c.loop ? 'loop' : 'once'} | ${desc[c.name] || (c.name.startsWith('int_look_') ? 'Eyes held ' + c.name.slice(9).replace('_', '-') + ' with light breathing (sitting, for cursor following).' : '')} |`);
const table = '| clip | category | base | frames | sec | play | what happens |\n|---|---|---|---|---|---|---|\n' + rows.join('\n');
const rep = JSON.parse(fs.readFileSync(path.join(D, 'verification/verify_report.json')));
const worst = rep.reduce((m, r) => (r.worst_pct_of_painted > m.worst_pct_of_painted ? r : m));
const zero = rep.filter((r) => r.worst_diff_pixels === 0).length;
const ver = `\n- ${rep.length} clips × 6 frames = ${rep.length * 6} frame pairs compared\n- ${zero} clips matched with 0 differing pixels on every checked frame\n- Worst frame anywhere: \`${worst.clip}\` f${worst.worst_frame}, ${worst.worst_diff_pixels} px (${worst.worst_pct_of_painted}% of drawn pixels)\n`;
let md = fs.readFileSync(path.join(__dirname, '../README_template.md'), 'utf8').replace('__CLIPTABLE__', table).replace('__VERIFY__', ver);
fs.writeFileSync(path.join(D, 'README.md'), md);
// source copy
const S = path.join(D, 'source');
fs.rmSync(S, { recursive: true, force: true });
for (const f of ['src/geom.js', 'src/rig.js', 'src/poses.js', 'src/anim.js', 'src/clips.js', 'build.js', 'tools/harness.js', 'tools/verify.js', 'tools/sheets.js', 'tools/preview.js', 'tools/preview_template.html', 'tools/package.js', 'README_template.md']) {
  fs.mkdirSync(path.dirname(path.join(S, f)), { recursive: true }); fs.copyFileSync(path.join(__dirname, '..', f), path.join(S, f));
}
fs.writeFileSync(path.join(S, 'package.json'), JSON.stringify({ name: 'otter-pet-generator', private: true, dependencies: { 'lottie-web': '5.12.2', pngjs: '^7.0.0', pixelmatch: '^5.3.0', playwright: '*' } }, null, 2));
console.log('readme ok', zero, worst);
