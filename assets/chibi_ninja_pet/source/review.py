import json, sys, os
import numpy as np
from PIL import Image, ImageDraw
from verify import Renderer, diff, checker
OUT = sys.argv[1]; dst = sys.argv[2]; names = sys.argv[3].split(',') if len(sys.argv) > 3 and sys.argv[3] else None
nframes = int(sys.argv[4]) if len(sys.argv) > 4 else 8
both = len(sys.argv) > 5 and sys.argv[5] == 'both'
os.makedirs(dst, exist_ok=True)
idx = json.load(open(f'{OUT}/index.json'))['clips']
r = Renderer(); report = []
for c in idx:
    if names and not any(c['name'].startswith(n) for n in names): continue
    L = json.load(open(f"{OUT}/{c['lottie']}")); S = open(f"{OUT}/{c['svg']}").read()
    r.load(L, S)
    N = c['frames']; fr = sorted(set([round(i * (N - 1) / (nframes - 1)) for i in range(nframes)]))
    rowL, rowS, worst = [], [], (0, 0, 0)
    for f in fr:
        a, b = r.frame(f); d = diff(a, b)
        if d[0] > worst[0]: worst = (d[0], d[1], f)
        ta = Image.fromarray(checker(a)).resize((192, 192), Image.LANCZOS); dr = ImageDraw.Draw(ta); dr.text((4, 2), f'f{f}', fill=(200, 0, 0))
        rowL.append(ta)
        if both: rowS.append(Image.fromarray(checker(b)).resize((192, 192), Image.LANCZOS))
    rows = [rowL] + ([rowS] if both else [])
    sheet = Image.new('RGB', (192 * len(fr), 192 * len(rows) + 18), 'white')
    for j, row in enumerate(rows):
        for i, t in enumerate(row): sheet.paste(t, (i * 192, 18 + j * 192))
    ImageDraw.Draw(sheet).text((4, 3), f"{c['name']}  ({N}f, loop={c['loop']})  top=Lottie" + (" bottom=SVG" if both else ""), fill=(0, 0, 0))
    sheet.save(f"{dst}/{c['name']}.png")
    report.append((c['name'], worst))
    print(c['name'], 'max %%px diff %.3f mean %.3f at f%d' % worst, flush=True)
r.close()
json.dump([{'clip': n, 'worst_frame': w[2], 'pct_pixels_differing': round(w[0], 4), 'mean_abs_diff': round(w[1], 4)} for n, w in report], open(f'{dst}/report.json', 'w'), indent=1)
