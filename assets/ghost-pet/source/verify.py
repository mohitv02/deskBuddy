"""Render key frames of every clip in both formats (SMIL SVG in Chromium, Lottie via lottie-web)
and compare pixel-by-pixel."""
import json, subprocess, os
import numpy as np
from PIL import Image, ImageDraw
idx = json.load(open('out/index.json'))['clips']
os.makedirs('tmp/vf', exist_ok=True)
jobs, frames = [], {}
for c in idx:
    N = c['frames']
    fr = sorted(set([0, round(N * .2), round(N * .4), round(N * .6), round(N * .8), N - 1]))
    frames[c['name']] = fr
    for f in fr:
        for k in ('svg', 'lottie'):
            jobs.append({'kind': k, 'file': 'out/%s/%s.%s' % (k, c['name'], 'svg' if k == 'svg' else 'json'),
                         'frame': f, 'out': 'tmp/vf/%s_%s_%d.png' % (k, c['name'], f)})
json.dump(jobs, open('tmp/vfj.json', 'w'))
subprocess.run(['node', 'render.js', 'tmp/vfj.json'], check=True)
rows = []
worst = 0
for c in idx:
    for f in frames[c['name']]:
        a = np.asarray(Image.open('tmp/vf/svg_%s_%d.png' % (c['name'], f)).convert('RGBA')).astype(int)
        b = np.asarray(Image.open('tmp/vf/lottie_%s_%d.png' % (c['name'], f)).convert('RGBA')).astype(int)
        d = np.abs(a - b).max(axis=2)
        mean = float(d.mean())
        bad = float((d > 64).mean() * 100)
        cover = float((a[..., 3] > 0).mean() * 100)
        rows.append({'clip': c['name'], 'frame': f, 'mean_abs_diff': round(mean, 4), 'pct_px_diff_gt64': round(bad, 4),
                     'coverage_pct': round(cover, 2)})
        worst = max(worst, bad)
json.dump({'frames_compared': len(rows), 'worst_pct_px_diff_gt64': worst, 'results': rows}, open('out/verification.json', 'w'), indent=1)
print('compared', len(rows), 'frame pairs; worst %% pixels differing >64/255: %.4f' % worst)
for r in sorted(rows, key=lambda r: -r['pct_px_diff_gt64'])[:8]:
    print(r)
