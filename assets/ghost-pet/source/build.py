import json, os, sys
from engine import to_lottie, to_svg
import rig, clips

OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
os.makedirs(OUT + '/lottie', exist_ok=True)
os.makedirs(OUT + '/svg', exist_ok=True)
index = []
only = sys.argv[2].split(',') if len(sys.argv) > 2 else None
for c in clips.CLIPS:
    if only and c.name not in only:
        continue
    layers = rig.build(c)
    lj = to_lottie(c.name, c.N, layers)
    sv = to_svg(c.name, c.N, layers, c.loop)
    with open('%s/lottie/%s.json' % (OUT, c.name), 'w') as f:
        json.dump(lj, f, separators=(',', ':'))
    with open('%s/svg/%s.svg' % (OUT, c.name), 'w') as f:
        f.write(sv)
    index.append({'name': c.name, 'category': c.cat, 'frames': c.N, 'seconds': round(c.N / 30, 3),
                  'loop': c.loop, 'description': c.desc})
with open(OUT + '/index.json', 'w') as f:
    json.dump({'fps': 30, 'width': 512, 'height': 512, 'clips': index}, f, indent=2)
print(len(index), 'clips')
