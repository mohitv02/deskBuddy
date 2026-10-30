"""Render key frames of both formats with Playwright, diff them, build contact sheets."""
import json, os, sys, subprocess
import numpy as np
from PIL import Image, ImageDraw

PKG = sys.argv[1]
OUTD = sys.argv[2]
only = sys.argv[3].split(',') if len(sys.argv) > 3 and sys.argv[3] else None
NF = int(sys.argv[4]) if len(sys.argv) > 4 else 6
os.makedirs(OUTD + '/frames', exist_ok=True)
idx = json.load(open(f'{PKG}/index.json'))['clips']
if only:
    idx = [c for c in idx if c['name'] in only]
jobs = []
plan = {}
for c in idx:
    N = c['frames']
    fr = sorted(set(int(round(i * (N - 1) / (NF - 1))) for i in range(NF)))
    plan[c['name']] = fr
    for kind, f in (('svg', c['svg']), ('lottie', c['lottie'])):
        jobs.append({'kind': kind, 'file': f'{PKG}/{f}', 'frames': fr, 'out': f'{OUTD}/frames/{c["name"]}_{kind}'})
json.dump(jobs, open(f'{OUTD}/jobs.json', 'w'))
subprocess.run(['node', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'render.js'), f'{OUTD}/jobs.json'], check=True)

def checker(w, h, s=12):
    a = ((np.arange(w)[None, :] // s + np.arange(h)[:, None] // s) % 2)
    im = np.where(a[..., None] == 1, np.array([228, 226, 234, 255]), np.array([255, 255, 255, 255])).astype(np.uint8)
    return Image.fromarray(im, 'RGBA')

report = []
T = 200
for c in idx:
    fr = plan[c['name']]
    sheet = checker(T * len(fr), T * 2 + 22)
    d = ImageDraw.Draw(sheet)
    worst = 0; worst_px = 0
    for j, f in enumerate(fr):
        a = Image.open(f'{OUTD}/frames/{c["name"]}_svg_{f:03d}.png').convert('RGBA')
        b = Image.open(f'{OUTD}/frames/{c["name"]}_lottie_{f:03d}.png').convert('RGBA')
        A = np.asarray(a).astype(int); B = np.asarray(b).astype(int)
        diff = np.abs(A - B).max(axis=2)
        mean = float(np.abs(A - B).mean())
        px = int((diff > 40).sum())
        worst = max(worst, mean); worst_px = max(worst_px, px)
        sheet.alpha_composite(a.resize((T, T), Image.LANCZOS), (T * j, 22))
        sheet.alpha_composite(b.resize((T, T), Image.LANCZOS), (T * j, 22 + T))
        d.text((T * j + 4, 4), f'f{f}  diff px>{40}: {px}', fill=(60, 40, 60, 255))
    sheet.save(f'{OUTD}/{c["name"]}.png')
    report.append({'clip': c['name'], 'frames_checked': fr, 'max_mean_abs_diff': round(worst, 4), 'max_pixels_over_40': worst_px})
    print(f'{c["name"]:24s} mean={worst:.4f} px>40={worst_px}')
json.dump(report, open(f'{OUTD}/report.json', 'w'), indent=1)
