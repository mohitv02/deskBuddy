"""Build every clip into lottie/ and svg/, validate loops/base pose, write index.json."""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import *
from rig import build_rig
import clips as C

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else 'dist/penguin-pet'

def close(a, b, tol=1e-3):
    if isinstance(a, tuple):
        return all(abs(x - y) < tol for x, y in zip(a, b))
    return abs(a - b) < tol

def validate(c):
    issues = []
    N = c.N
    base = build_rig()
    for lay in c.layers.values():
        hidden_ends = 'o' in lay.tr and close(sample(lay.tr['o'], 0, 'o' in lay.step), 0) and \
            close(sample(lay.tr['o'], N, 'o' in lay.step), 0)
        for pr, ks in lay.tr.items():
            if hidden_ends and pr != 'o':
                continue
            step = pr in lay.step
            v0, vN = sample(ks, 0, step), sample(ks, N, step)
            if c.loop and not close(v0, vN):
                issues.append(f'seam {lay.name}.{pr}: {v0} != {vN}')
            if not c.loop and not close(sample(ks, N - 1, step), vN):
                issues.append(f'last-frame {lay.name}.{pr}: f{N - 1}={sample(ks, N - 1, step)} f{N}={vN}')
            if c.loop and not c.holds:
                rest = lay.rest(pr)
                if not close(v0, rest):
                    issues.append(f'base {lay.name}.{pr}: {v0} != rest {rest}')
    return issues

def main():
    os.makedirs(f'{OUTDIR}/lottie', exist_ok=True)
    os.makedirs(f'{OUTDIR}/svg', exist_ok=True)
    index = []
    bad = 0
    for fn in C.CLIPS:
        c = fn()
        c.finalize()
        iss = validate(c)
        if iss:
            bad += 1
            print(f'!! {c.name}:'); [print('   ', i) for i in iss[:12]]
        lj = to_lottie(c)
        with open(f'{OUTDIR}/lottie/{c.name}.json', 'w') as f:
            json.dump(lj, f, separators=(',', ':'))
        with open(f'{OUTDIR}/svg/{c.name}.svg', 'w') as f:
            f.write(to_svg(c))
        entry = {'name': c.name, 'category': c.cat, 'frames': c.N, 'seconds': round(c.N / FPS, 3), 'loop': c.loop,
                 'lottie': f'lottie/{c.name}.json', 'svg': f'svg/{c.name}.svg'}
        if c.holds:
            entry['holds_pose'] = True
        if c.note:
            entry['note'] = c.note
        if c.name == 'idle_breathe':
            entry['default'] = True
        index.append(entry)
    with open(f'{OUTDIR}/index.json', 'w') as f:
        json.dump({'fps': FPS, 'width': W, 'height': H, 'clips': index}, f, indent=2)
    print(f'built {len(index)} clips, {bad} with validation notes')

if __name__ == '__main__':
    main()
