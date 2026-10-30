// node render.js jobs.json  — jobs: [{kind:'svg'|'lottie', file, frame, out}]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 512, height: 512 } });
  const lottieSrc = fs.readFileSync(path.join(__dirname, 'node_modules/lottie-web/build/player/lottie.min.js'), 'utf8');
  let loaded = null;
  for (const j of jobs) {
    if (j.kind === 'svg') {
      if (loaded !== 'svg:' + j.file) {
        const svg = fs.readFileSync(j.file, 'utf8');
        await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
        loaded = 'svg:' + j.file;
      }
      await page.evaluate((f) => { const s = document.querySelector('svg'); s.pauseAnimations(); s.setCurrentTime(f / 30); }, j.frame);
    } else {
      if (loaded !== 'lottie:' + j.file) {
        const data = fs.readFileSync(j.file, 'utf8');
        await page.setContent(`<html><body style="margin:0;background:transparent"><div id="c" style="width:512px;height:512px"></div></body></html>`);
        await page.addScriptTag({ content: lottieSrc });
        await page.evaluate((d) => {
          window.anim = lottie.loadAnimation({ container: document.getElementById('c'), renderer: 'svg', loop: false, autoplay: false, animationData: JSON.parse(d) });
        }, data);
        loaded = 'lottie:' + j.file;
      }
      await page.evaluate((f) => window.anim.goToAndStop(f, true), j.frame);
    }
    await page.waitForTimeout(15);
    await page.screenshot({ path: j.out, omitBackground: true, clip: { x: 0, y: 0, width: 512, height: 512 } });
  }
  await browser.close();
})();
