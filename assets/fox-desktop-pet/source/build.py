import json, os, sys
from fox import build
from model import Exporter, FPS
import clips as C

OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/foxpet/out'


def run(names=None):
    rig = build()
    os.makedirs(OUT + '/lottie', exist_ok=True)
    os.makedirs(OUT + '/svg', exist_ok=True)
    idx = []
    for c in C.CLIPS:
        if names and c.name not in names:
            continue
        e = Exporter(rig, c)
        open('%s/svg/%s.svg' % (OUT, c.name), 'w').write(e.svg())
        json.dump(e.lottie(), open('%s/lottie/%s.json' % (OUT, c.name), 'w'), separators=(',', ':'))
        idx.append({'name': c.name, 'category': c.cat, 'frames': c.frames, 'seconds': round(c.frames / FPS, 3),
                    'loop': c.loop, 'fps': FPS, 'lottie': 'lottie/%s.json' % c.name, 'svg': 'svg/%s.svg' % c.name,
                    **({'note': c.note} if c.note else {})})
    if not names:
        json.dump({'character': 'Fox desktop pet', 'canvas': [512, 512], 'fps': FPS, 'default': 'idle_breathe',
                   'clips': idx}, open(OUT + '/index.json', 'w'), indent=2)
    return idx


if __name__ == '__main__':
    idx = run()
    print(len(idx), 'clips')
