import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clips, engine
OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
os.makedirs(f'{OUT}/lottie', exist_ok=True); os.makedirs(f'{OUT}/svg', exist_ok=True)
index = []
for c in clips.CLIPS:
    L = engine.to_lottie(c); S = engine.to_svg(c)
    json.dump(L, open(f'{OUT}/lottie/{c.name}.json', 'w'), separators=(',', ':'))
    open(f'{OUT}/svg/{c.name}.svg', 'w').write(S)
    e = dict(name=c.name, category=c.cat, frames=c.N, seconds=round(c.N / engine.FPS, 3), loop=c.loop,
             lottie=f'lottie/{c.name}.json', svg=f'svg/{c.name}.svg')
    if c.markers: e['markers'] = [dict(name=m[1], start_frame=m[0], frames=m[2]) for m in c.markers]
    index.append(e)
json.dump(dict(fps=engine.FPS, width=512, height=512, ground_y=470, clips=index), open(f'{OUT}/index.json', 'w'), indent=2)
tot_l = sum(os.path.getsize(f'{OUT}/lottie/{c.name}.json') for c in clips.CLIPS); tot_s = sum(os.path.getsize(f'{OUT}/svg/{c.name}.svg') for c in clips.CLIPS)
print(len(index), 'clips', tot_l // 1024, 'KB lottie', tot_s // 1024, 'KB svg')
