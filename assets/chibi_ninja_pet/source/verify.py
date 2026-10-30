"""Render frames of Lottie (lottie-web, svg renderer) and SMIL SVG (paused + setCurrentTime) in Chromium and diff them."""
import json, sys, os, io
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
LOTTIE_JS = open(os.path.join(HERE, '..', 'vendor', 'lottie.min.js')).read()
PAGE = """<html><head><style>body{margin:0;background:transparent}#a,#b{width:512px;height:512px;display:inline-block;vertical-align:top}</style></head>
<body><div id="a"></div><div id="b"></div></body></html>"""

class Renderer:
    def __init__(s):
        s.pw = sync_playwright().start(); s.br = s.pw.chromium.launch()
        s.pg = s.br.new_page(viewport={'width': 1024, 'height': 512})
        s.pg.set_content(PAGE); s.pg.add_script_tag(content=LOTTIE_JS)
    def load(s, lottie_json, svg_text):
        s.pg.evaluate("""([d, svg]) => { if (window.anim) window.anim.destroy(); document.getElementById('a').innerHTML='';
            window.anim = lottie.loadAnimation({container: document.getElementById('a'), renderer:'svg', loop:false, autoplay:false, animationData: d});
            document.getElementById('b').innerHTML = svg; const e=document.querySelector('#b svg'); e.pauseAnimations(); }""", [lottie_json, svg_text])
    def frame(s, f):
        s.pg.evaluate("""(f) => { window.anim.goToAndStop(f, true); const e=document.querySelector('#b svg'); e.setCurrentTime(f/30); }""", f)
        s.pg.wait_for_timeout(30)
        png = s.pg.screenshot(omit_background=True, clip={'x': 0, 'y': 0, 'width': 1024, 'height': 512})
        im = np.asarray(Image.open(io.BytesIO(png)).convert('RGBA'))
        return im[:, :512], im[:, 512:]
    def close(s): s.br.close(); s.pw.stop()

def diff(a, b):
    fa = a.astype(np.float32); fb = b.astype(np.float32)
    pa = np.concatenate([fa[..., :3] * fa[..., 3:] / 255, fa[..., 3:]], 2); pb = np.concatenate([fb[..., :3] * fb[..., 3:] / 255, fb[..., 3:]], 2)
    d = np.abs(pa - pb).max(2)
    return float((d > 64).mean() * 100), float(d.mean())

def checker(im, sz=16):
    h, w = im.shape[:2]; yy, xx = np.indices((h, w))
    bg = np.where(((yy // sz + xx // sz) % 2)[..., None] == 0, 236, 210).astype(np.float32).repeat(3, 2)
    a = im[..., 3:] / 255.0
    return (im[..., :3] * a + bg * (1 - a)).astype(np.uint8)
