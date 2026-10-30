import json, os, sys, io, time
import numpy as np
from PIL import Image, ImageDraw
from core import to_lottie, to_svg, FPS
from rig import build_scene
import clips as CL
OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
os.makedirs(f'{OUT}/lottie', exist_ok=True); os.makedirs(f'{OUT}/svg', exist_ok=True)
scene = build_scene(clones=False); scene_cl = build_scene(clones=True)
index = []
only = sys.argv[2].split(',') if len(sys.argv) > 2 else None
for c in CL.CLIPS:
    if only and not any(c.name.startswith(o) for o in only): continue
    sc = scene_cl if 'clone' in c.name else scene
    L = to_lottie(c, sc); S = to_svg(c, sc)
    json.dump(L, open(f'{OUT}/lottie/{c.name}.json', 'w'), separators=(',', ':'))
    open(f'{OUT}/svg/{c.name}.svg', 'w').write(S)
    index.append(dict(name=c.name, category=c.cat, frames=c.N, seconds=round(c.N / FPS, 3), loop=c.loop, description=c.desc,
                      lottie=f'lottie/{c.name}.json', svg=f'svg/{c.name}.svg'))
if not only:
    json.dump(dict(fps=FPS, width=512, height=512, clips=index), open(f'{OUT}/index.json', 'w'), indent=1)
tot = sum(os.path.getsize(f'{OUT}/lottie/{x["name"]}.json') for x in index); tots = sum(os.path.getsize(f'{OUT}/svg/{x["name"]}.svg') for x in index)
print(len(index), 'clips; lottie KB', tot // 1024, 'svg KB', tots // 1024)
