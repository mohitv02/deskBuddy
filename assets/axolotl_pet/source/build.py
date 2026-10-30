import json, os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import export_svg, export_lottie, FPS
import clips

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
only = sys.argv[2].split(',') if len(sys.argv) > 2 else None
os.makedirs(f'{OUT}/lottie', exist_ok=True); os.makedirs(f'{OUT}/svg', exist_ok=True)
index = []
for fn in clips.CLIPS:
    c = fn()
    if only and c.name not in only:
        continue
    probs = c.check(c.rig)
    if probs:
        print('LOOP WARN', c.name, probs)
    open(f'{OUT}/svg/{c.name}.svg', 'w').write(export_svg(c))
    json.dump(export_lottie(c), open(f'{OUT}/lottie/{c.name}.json', 'w'), separators=(',', ':'))
    index.append({'name': c.name, 'category': c.category, 'base_pose': c.base_pose, 'start_pose': c.start_pose,
                  'end_pose': c.end_pose, 'frames': c.frames, 'fps': FPS, 'seconds': round(c.frames / FPS, 3),
                  'loop': c.loop, 'description': c.desc,
                  'lottie': f'lottie/{c.name}.json', 'svg': f'svg/{c.name}.svg'})
if not only:
    json.dump({'character': 'Axolotl desktop pet', 'canvas': [512, 512], 'fps': FPS, 'default_clip': 'idle_breathe',
               'clips': index}, open(f'{OUT}/index.json', 'w'), indent=2)
print(len(index), 'clips')
