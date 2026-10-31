// Headless renderer for SVG (SMIL seek) and Lottie (lottie-web goToAndStop) frames.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const LOTTIE = fs.readFileSync(require.resolve('lottie-web/build/player/lottie.min.js'), 'utf8');

async function open() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
  await page.setContent(`<html><body style="margin:0;background:transparent">
    <div id="s" style="width:512px;height:512px;position:absolute;left:0;top:0"></div>
    <div id="l" style="width:512px;height:512px;position:absolute;left:0;top:600px"></div>
    <script>${LOTTIE}</script></body></html>`);
  await page.evaluate(() => {
    window.loadSvg = (txt) => { const s = document.getElementById('s'); s.innerHTML = txt; const svg = s.querySelector('svg'); svg.pauseAnimations(); window._svg = svg; };
    window.seekSvg = (t) => { window._svg.setCurrentTime(t); };
    window.loadLottie = (data) => {
      if (window._anim) window._anim.destroy();
      window._anim = lottie.loadAnimation({ container: document.getElementById('l'), renderer: 'svg', loop: false, autoplay: false, animationData: data });
    };
    window.seekLottie = (f) => window._anim.goToAndStop(f, true);
  });
  return {
    browser, page,
    async svgFrame(svgText, frame) {
      await page.evaluate((t) => { if (window._svgTxt !== t) { window._svgTxt = t; window.loadSvg(t); } }, svgText);
      await page.evaluate((t) => window.seekSvg(t), frame / 30 + 1e-4);
      await page.waitForTimeout(30);
      return page.locator('#s').screenshot({ omitBackground: true });
    },
    async lottieFrame(json, frame) {
      await page.evaluate((j) => { if (window._ljson !== j.nm + j.op) { window._ljson = j.nm + j.op; window.loadLottie(j); } }, json);
      await page.evaluate((f) => window.seekLottie(f), frame);
      await page.waitForTimeout(30);
      return page.locator('#l').screenshot({ omitBackground: true });
    },
    async sheet(cells, cols, file, { size = 256, bg = 'checker' } = {}) {
      // cells: [{png:Buffer, label}]
      const p2 = await browser.newPage({ viewport: { width: cols * (size + 8) + 8, height: 200 } });
      const html = `<html><body style="margin:0;padding:4px;background:#fff;font:12px sans-serif;display:flex;flex-wrap:wrap;width:${cols * (size + 8)}px">${cells.map((c) => `<div style="margin:4px;width:${size}px"><div style="width:${size}px;height:${size}px;${bg === 'checker' ? 'background:repeating-conic-gradient(#e9e9ef 0 25%,#fff 0 50%) 0 0/24px 24px' : 'background:' + bg}"><img style="width:${size}px;height:${size}px" src="data:image/png;base64,${c.png.toString('base64')}"></div><div>${c.label || ''}</div></div>`).join('')}</body></html>`;
      await p2.setContent(html);
      await p2.screenshot({ path: file, fullPage: true });
      await p2.close();
    },
    close: () => browser.close(),
  };
}
module.exports = { open };
