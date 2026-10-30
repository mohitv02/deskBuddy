import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rig import to_lottie, to_svg
from clips import CLIPS

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
for d in ('lottie', 'svg'):
    os.makedirs(os.path.join(root, d), exist_ok=True)

index = []
for c in CLIPS:
    with open(os.path.join(root, 'lottie', c.name + '.json'), 'w') as f:
        json.dump(to_lottie(c), f, separators=(',', ':'))
    with open(os.path.join(root, 'svg', c.name + '.svg'), 'w') as f:
        f.write(to_svg(c))
    index.append({'name': c.name, 'category': c.cat, 'description': c.desc, 'frames': c.T,
                  'seconds': round(c.T / 30, 2), 'loop': not c.once})
with open(os.path.join(root, 'index.json'), 'w') as f:
    json.dump(index, f, indent=1)
print(len(CLIPS), 'clips')
