// Render frames of SMIL SVGs (paused + setCurrentTime) and Lottie JSON (lottie-web goToAndStop).
// usage: node render.js jobs.json   where jobs = [{kind:'svg'|'lottie', file, frames:[..], fps, out:'prefix'}]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 512, height: 512 }, deviceScaleFactor: 1 });
  await page.setContent('<!doctype html><html><body style="margin:0;background:transparent"><div id="c" style="width:512px;height:512px;position:relative"></div></body></html>');
  await page.addScriptTag({ path: require.resolve('lottie-web/build/player/lottie.min.js') });
  const el = await page.$('#c');
  for (const job of jobs) {
    const text = fs.readFileSync(job.file, 'utf8');
    if (job.kind === 'svg') {
      await page.evaluate((t) => { document.getElementById('c').innerHTML = t; }, text);
      for (const f of job.frames) {
        await page.evaluate(async ([f, fps]) => {
          const s = document.querySelector('#c svg');
          s.pauseAnimations();
          s.setCurrentTime(f / fps);
          const c = document.getElementById('c');
          c.style.visibility = 'hidden';
          await new Promise(r => requestAnimationFrame(() => setTimeout(r, 15)));
          c.style.visibility = '';
          await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 25))));
        }, [f, job.fps || 30]);
        await el.screenshot({ path: `${job.out}_${String(f).padStart(3, '0')}.png`, omitBackground: true });
      }
    } else {
      await page.evaluate((t) => {
        const c = document.getElementById('c');
        if (window.__anim) window.__anim.destroy();
        c.innerHTML = '';
        window.__anim = lottie.loadAnimation({ container: c, renderer: 'svg', loop: false, autoplay: false,
          animationData: JSON.parse(t), rendererSettings: { preserveAspectRatio: 'xMidYMid meet' } });
      }, text);
      for (const f of job.frames) {
        await page.evaluate(async (f) => {
          window.__anim.goToAndStop(f, true);
          const c = document.getElementById('c');
          c.style.visibility = 'hidden';
          await new Promise(r => requestAnimationFrame(() => setTimeout(r, 15)));
          c.style.visibility = '';
          await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 25))));
        }, f);
        await el.screenshot({ path: `${job.out}_${String(f).padStart(3, '0')}.png`, omitBackground: true });
      }
    }
  }
  await browser.close();
})();
