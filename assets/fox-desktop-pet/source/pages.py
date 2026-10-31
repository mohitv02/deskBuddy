"""Generate preview.html and cursor.html from index.json."""
import json, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/foxpet/out'
idx = json.load(open(OUT + '/index.json'))
CL = json.dumps(idx['clips'], separators=(',', ':'))

HEAD_FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
              '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600&'
              'family=Figtree:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap">')

TOKENS = """
/* Layout: control bar, then a large stage that compares SVG and Lottie side by side, then the clip shelf by category */
:root{
  --bg:#eef1ec; --panel:#ffffff; --ink:#1f2a22; --muted:#5d6b60; --line:#d6ddd4;
  --accent:#2f6b45; --fur:#e9802f; --chk1:#ffffff; --chk2:#e4e8e1; --chip:#e2e9e1;
  --display:"Fredoka","Baloo 2",ui-rounded,"Segoe UI",system-ui,sans-serif;
  --body:"Figtree",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#141915; --panel:#1d241f; --ink:#e7ece5; --muted:#9aa89c; --line:#2f3a32;
  --accent:#7cc493; --fur:#f39a4d; --chk1:#2a322c; --chk2:#222925; --chip:#26302a; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#141915; --panel:#1d241f; --ink:#e7ece5; --muted:#9aa89c; --line:#2f3a32;
  --accent:#7cc493; --fur:#f39a4d; --chk1:#2a322c; --chk2:#222925; --chip:#26302a; color-scheme:dark}
body.dark-checker{--chk1:#3a3f3b; --chk2:#2c312d}
body.light-checker{--chk1:#ffffff; --chk2:#e4e8e1}
"""

PREVIEW_CSS = TOKENS + """
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--body);font-size:15px;line-height:1.5;margin:0;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:20px 48px}
.wrap{max-width:1180px;margin:0 auto;display:flex;flex-direction:column;gap:22px}
header{display:flex;flex-wrap:wrap;align-items:end;justify-content:space-between;gap:14px}
h1{font-family:var(--display);font-weight:600;font-size:clamp(1.7rem,3.5vw,2.4rem);line-height:1.05;margin:0;text-wrap:balance}
h1 span{color:var(--fur)}
.sub{color:var(--muted);margin:4px 0 0;max-width:62ch}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.seg{display:inline-flex;background:var(--chip);border-radius:999px;padding:3px}
.seg button{border:0;background:transparent;color:var(--muted);font:600 13px var(--body);padding:6px 13px;border-radius:999px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--panel);color:var(--ink);box-shadow:0 1px 2px rgb(0 0 0/.12)}
a.link{color:var(--accent);font-weight:600;text-decoration:none;border-bottom:2px solid currentColor;padding-bottom:1px}
button:focus-visible,a:focus-visible{outline:3px solid var(--fur);outline-offset:2px}
.chk{background-color:var(--chk1);background-image:conic-gradient(var(--chk2) 25%,transparent 0 50%,var(--chk2) 0 75%,transparent 0);
  background-size:24px 24px}
.stage{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:18px;background:var(--panel);border:1px solid var(--line);
  border-radius:20px;padding:16px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.view{display:flex;flex-direction:column;gap:6px;min-width:0}
.view .box{aspect-ratio:1;max-width:100%;border-radius:14px;overflow:hidden;position:relative}
.view .box img,.view .box .lot{position:absolute;inset:0;width:100%;height:100%}
.tag{font:500 11px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.info{display:flex;flex-direction:column;gap:12px;min-width:0}
.info h2{font-family:var(--display);font-weight:600;font-size:1.6rem;margin:0;word-break:break-word}
dl{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;margin:0;font-variant-numeric:tabular-nums}
dt{color:var(--muted)} dd{margin:0;font-family:var(--mono);font-size:13.5px}
.note{color:var(--muted);margin:0}
.btns{display:flex;gap:8px;flex-wrap:wrap}
.btn{border:1px solid var(--line);background:var(--chip);color:var(--ink);font:600 13px var(--body);padding:8px 14px;border-radius:10px;cursor:pointer}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--panel)}
.msg{font-size:13px;color:var(--muted)}
section h3{font-family:var(--display);font-weight:500;font-size:1.15rem;margin:0 0 10px;display:flex;gap:10px;align-items:baseline}
section h3 small{font:500 12px var(--mono);color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
.tile{display:flex;flex-direction:column;gap:6px;text-align:left;border:2px solid transparent;background:transparent;padding:0;cursor:pointer;color:inherit;
  border-radius:16px}
.tile .box{aspect-ratio:1;max-width:100%;border-radius:14px;overflow:hidden;position:relative;border:1px solid var(--line)}
.tile .box img,.tile .box .lot{position:absolute;inset:0;width:100%;height:100%}
.tile[aria-current="true"] .box{outline:3px solid var(--fur);outline-offset:-1px}
.tile .nm{font:500 12.5px var(--mono);word-break:break-all;padding-inline:2px}
.tile .mt{font-size:12px;color:var(--muted);padding-inline:2px;display:flex;gap:6px;align-items:center;font-variant-numeric:tabular-nums}
.pill{font:600 10.5px var(--body);letter-spacing:.04em;text-transform:uppercase;padding:1px 7px;border-radius:999px;background:var(--chip);color:var(--muted)}
.pill.once{background:var(--fur);color:var(--panel)}
.filters{display:flex;flex-wrap:wrap;gap:6px}
.filters button{border:1px solid var(--line);background:transparent;color:var(--ink);font:600 12.5px var(--body);padding:5px 12px;border-radius:999px;cursor:pointer}
.filters button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
@media (max-width:760px){.stage{grid-template-columns:1fr}}
@media (max-width:420px){.pair{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""

PREVIEW_BODY = """
<div class="wrap">
<header>
  <div><h1>Fox <span>Desktop Pet</span></h1>
  <p class="sub">37 clips, 512&times;512 at 30&nbsp;fps on a transparent background. Every clip ships as SMIL SVG and Lottie with the same motion. Pick a clip to compare both formats at full size.</p></div>
  <div class="controls">
    <div class="seg" role="group" aria-label="Shelf format"><button id="fmt-svg" aria-pressed="true">SVG</button><button id="fmt-lot" aria-pressed="false">Lottie</button></div>
    <div class="seg" role="group" aria-label="Backdrop"><button id="bg-l" aria-pressed="true">Light</button><button id="bg-d" aria-pressed="false">Dark</button></div>
    <a class="link" href="cursor.html">Cursor demo &rarr;</a>
  </div>
</header>
<div class="stage">
  <div class="pair">
    <div class="view"><span class="tag">Animated SVG &middot; SMIL</span><div class="box chk"><img id="st-svg" alt=""></div></div>
    <div class="view"><span class="tag">Lottie &middot; bodymovin 5.7</span><div class="box chk"><div id="st-lot" class="lot"></div></div></div>
  </div>
  <div class="info">
    <span class="tag" id="st-cat"></span>
    <h2 id="st-name"></h2>
    <dl><dt>Frames</dt><dd id="st-fr"></dd><dt>Length</dt><dd id="st-sec"></dd><dt>Playback</dt><dd id="st-loop"></dd></dl>
    <p class="note" id="st-note"></p>
    <div class="btns"><button class="btn primary" id="replay">Replay both</button></div>
    <p class="msg" id="lotmsg" hidden></p>
  </div>
</div>
<div class="filters" id="filters" role="group" aria-label="Category"></div>
<div id="shelf" style="display:flex;flex-direction:column;gap:26px"></div>
</div>
"""

PREVIEW_JS = """
const CLIPS = __CLIPS__;
const CATS = [['idle','Idle'],['sleep','Sleep'],['movement','Movement'],['interaction','Interaction'],['mood','Moods'],['fun','Fun']];
let fmt = 'svg', cat = 'all', sel = 'idle_breathe', stageAnim = null, tileAnims = [];
const $ = s => document.querySelector(s);
const hasLottie = () => typeof window.lottie !== 'undefined';
const bust = u => u + '?r=' + Date.now();
function lottieInto(el, c, autoplay=true){
  try { return lottie.loadAnimation({container: el, renderer: 'svg', loop: c.loop, autoplay, path: c.lottie,
    rendererSettings:{preserveAspectRatio:'xMidYMid meet'}}); } catch(e){ return null; }
}
function select(name, restart){
  sel = name; const c = CLIPS.find(x => x.name === name);
  $('#st-name').textContent = c.name;
  $('#st-cat').textContent = c.category;
  $('#st-fr').textContent = c.frames;
  $('#st-sec').textContent = c.seconds.toFixed(2) + ' s';
  $('#st-loop').textContent = c.loop ? 'loops' : 'plays once, holds last pose';
  $('#st-note').textContent = c.note || '';
  $('#st-svg').src = bust(c.svg); $('#st-svg').alt = c.name + ' (SVG)';
  const box = $('#st-lot'); box.innerHTML = '';
  if (stageAnim) { stageAnim.destroy(); stageAnim = null; }
  if (hasLottie()) {
    stageAnim = lottieInto(box, c);
    if (stageAnim) stageAnim.addEventListener('data_failed', lotFail);
  } else lotFail();
  document.querySelectorAll('.tile').forEach(t => t.setAttribute('aria-current', t.dataset.name === name));
}
function lotFail(){
  const m = $('#lotmsg'); m.hidden = false;
  m.textContent = 'Lottie could not load here. Opened straight from disk, browsers block the JSON files: run "python3 -m http.server" in this folder and open the page from localhost.';
}
function shelf(){
  tileAnims.forEach(a => a && a.destroy()); tileAnims = [];
  const root = $('#shelf'); root.innerHTML = '';
  for (const [k, label] of CATS) {
    if (cat !== 'all' && cat !== k) continue;
    const list = CLIPS.filter(c => c.category === k);
    const s = document.createElement('section');
    s.innerHTML = `<h3>${label} <small>${list.length} clips</small></h3><div class="grid"></div>`;
    const g = s.querySelector('.grid');
    for (const c of list) {
      const b = document.createElement('button'); b.className = 'tile'; b.dataset.name = c.name;
      b.setAttribute('aria-current', c.name === sel);
      b.innerHTML = `<div class="box chk"></div><span class="nm">${c.name}</span>
        <span class="mt">${c.frames} f &middot; ${c.seconds.toFixed(1)} s <span class="pill ${c.loop?'':'once'}">${c.loop?'loop':'once'}</span></span>`;
      const box = b.querySelector('.box');
      if (fmt === 'lot' && hasLottie()) { const d = document.createElement('div'); d.className = 'lot'; box.appendChild(d); tileAnims.push(lottieInto(d, c)); }
      else { const im = document.createElement('img'); im.src = c.svg; im.alt = c.name; im.loading = 'lazy'; box.appendChild(im); }
      b.addEventListener('click', () => { select(c.name); window.scrollTo({top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'}); });
      g.appendChild(b);
    }
    root.appendChild(s);
  }
}
function filters(){
  const f = $('#filters'); f.innerHTML = '';
  for (const [k, label] of [['all','All'], ...CATS]) {
    const b = document.createElement('button'); b.textContent = label; b.setAttribute('aria-pressed', k === cat);
    b.onclick = () => { cat = k; filters(); shelf(); }; f.appendChild(b);
  }
}
function seg(a, b, on){ $(a).setAttribute('aria-pressed', on); $(b).setAttribute('aria-pressed', !on); }
$('#fmt-svg').onclick = () => { fmt = 'svg'; seg('#fmt-svg', '#fmt-lot', true); shelf(); };
$('#fmt-lot').onclick = () => { if (!hasLottie()) { lotFail(); return; } fmt = 'lot'; seg('#fmt-svg', '#fmt-lot', false); shelf(); };
$('#bg-l').onclick = () => { document.body.classList.add('light-checker'); document.body.classList.remove('dark-checker'); seg('#bg-l', '#bg-d', true); };
$('#bg-d').onclick = () => { document.body.classList.add('dark-checker'); document.body.classList.remove('light-checker'); seg('#bg-l', '#bg-d', false); };
$('#replay').onclick = () => select(sel);
document.body.classList.add(matchMedia('(prefers-color-scheme: dark)').matches ? 'dark-checker' : 'light-checker');
if (document.body.classList.contains('dark-checker')) seg('#bg-l', '#bg-d', false);
filters(); shelf(); select(sel);
"""

CURSOR_CSS = TOKENS + """
*{box-sizing:border-box}
html,body{height:100%}
body{background:var(--bg);color:var(--ink);font-family:var(--body);margin:0;display:flex;flex-direction:column;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:16px;gap:12px}
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 16px;max-width:1100px;width:100%;margin:0 auto}
h1{font-family:var(--display);font-weight:600;font-size:1.5rem;margin:0}
h1 span{color:var(--fur)}
p{margin:0;color:var(--muted);font-size:14px;max-width:70ch}
a{color:var(--accent);font-weight:600}
#field{flex:1;min-height:420px;border-radius:20px;border:1px solid var(--line);position:relative;overflow:hidden;max-width:1100px;width:100%;margin:0 auto;
  background-color:var(--chk1);background-image:conic-gradient(var(--chk2) 25%,transparent 0 50%,var(--chk2) 0 75%,transparent 0);background-size:28px 28px;
  touch-action:none}
#pet{position:absolute;left:50%;top:50%;width:min(300px,60vw);aspect-ratio:1;transform:translate(-50%,-50%);cursor:pointer}
#pet img{position:absolute;inset:0;width:100%;height:100%}
#state{position:absolute;left:12px;bottom:10px;font:500 12px var(--mono);color:var(--muted);background:var(--panel);padding:4px 9px;border-radius:8px;border:1px solid var(--line)}
"""

CURSOR_BODY = """
<header><h1>Fox <span>Cursor Demo</span></h1>
<p>Move the pointer around the fox and it follows with the eight look clips. Hover over it to settle, click it to pet it, and leave the pointer still for 8 seconds to watch it fall asleep. <a href="preview.html">All clips</a></p></header>
<div id="field"><div id="pet" role="img" aria-label="Animated fox"></div><span id="state">idle_breathe</span></div>
"""

CURSOR_JS = """
const CLIPS = __CLIPS__;
const by = Object.fromEntries(CLIPS.map(c => [c.name, c]));
const pet = document.getElementById('pet'), field = document.getElementById('field'), label = document.getElementById('state');
const imgs = {};
const DIRS = ['right','down_right','down','down_left','left','up_left','up','up_right'];
for (const n of ['idle_breathe','int_petted','sleep_fall_asleep','sleep_loop','sleep_wake_up', ...DIRS.map(d => 'int_look_' + d)]) {
  const im = new Image(); im.src = by[n].svg; im.alt = ''; im.hidden = true; pet.appendChild(im); imgs[n] = im;
}
let cur = null, busyUntil = 0, mode = 'awake', lastMove = performance.now(), timer = null;
function show(n, restart){
  if (cur === n && !restart) return;
  if (restart) imgs[n].src = by[n].svg + '?r=' + Date.now();
  for (const k in imgs) imgs[k].hidden = k !== n;
  cur = n; label.textContent = n;
}
function playOnce(n, then){
  show(n, true); clearTimeout(timer);
  busyUntil = performance.now() + by[n].seconds * 1000;
  timer = setTimeout(then, by[n].seconds * 1000);
}
function wake(){
  if (mode === 'asleep') { mode = 'waking'; playOnce('sleep_wake_up', () => { mode = 'awake'; show('idle_breathe'); }); }
}
function onMove(x, y){
  lastMove = performance.now();
  if (mode === 'asleep' || mode === 'falling') { wake(); return; }
  if (performance.now() < busyUntil) return;
  const r = pet.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height * 0.45;
  const dx = x - cx, dy = y - cy;
  if (Math.hypot(dx, dy) < r.width * 0.32) { show('idle_breathe'); return; }
  const a = (Math.atan2(dy, dx) * 180 / Math.PI + 360 + 22.5) % 360;
  show('int_look_' + DIRS[Math.floor(a / 45)]);
}
field.addEventListener('pointermove', e => onMove(e.clientX, e.clientY));
field.addEventListener('pointerleave', () => { if (mode === 'awake' && performance.now() >= busyUntil) show('idle_breathe'); });
pet.addEventListener('click', () => {
  lastMove = performance.now();
  if (mode !== 'awake') { wake(); return; }
  playOnce('int_petted', () => show('idle_breathe'));
});
setInterval(() => {
  if (mode === 'awake' && performance.now() >= busyUntil && performance.now() - lastMove > 8000) {
    mode = 'falling';
    playOnce('sleep_fall_asleep', () => { if (mode === 'falling') { mode = 'asleep'; show('sleep_loop'); } });
  }
}, 500);
show('idle_breathe');
"""


def page(title, css, body, js, full, lottie_src=None):
    scripts = ''
    if lottie_src:
        scripts = ''.join('<script src="%s"></script>' % s for s in lottie_src)
    inner = ('<title>%s</title><meta name="claude:viewport-fit-sides" content="cover">%s<style>%s</style>%s%s<script>%s</script>'
             % (title, HEAD_FONTS, css, body, scripts, js.replace('__CLIPS__', CL)))
    if not full:
        return inner
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            'initial-scale=1,viewport-fit=cover"><title>%s</title>%s<style>%s</style></head><body>%s%s<script>%s</script></body></html>'
            % (title, HEAD_FONTS, css, body, scripts, js.replace('__CLIPS__', CL)))


if __name__ == '__main__':
    lot = ['vendor/lottie.min.js']
    open(OUT + '/preview.html', 'w').write(page('Fox Desktop Pet', PREVIEW_CSS, PREVIEW_BODY, PREVIEW_JS, True, lot))
    open(OUT + '/cursor.html', 'w').write(page('Fox Cursor Demo', CURSOR_CSS, CURSOR_BODY, CURSOR_JS, True))
    # artifact variant (skeleton added by the host); lottie from cdnjs
    open(OUT + '/preview_artifact.html', 'w').write(
        page('Fox Desktop Pet', PREVIEW_CSS, PREVIEW_BODY, PREVIEW_JS, False,
             ['https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js']))
    print('ok')
