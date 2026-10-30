"""Rig sheet, preview pages, README, verification copy and zip."""
import json, os, sys, shutil, subprocess, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import *
from rig import *
import clips as C

SRC = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(SRC, '..'))
LOTTIE_JS = os.environ.get('LOTTIE_JS', 'node_modules/lottie-web/build/player/lottie.min.js')
VER = sys.argv[1] if len(sys.argv) > 1 else None


# ------------------------------------------------------------------ rig sheet
def sheet_svg():
    W, H = 1280, 820
    rig = build_rig()
    lines = []
    cells = []

    def place(node, x, y, sc, label):
        cells.append((Node('cell_' + label.replace(' ', '_'), [node], p=(x, y), s=(sc, sc)), x, y, label))

    # character
    char_wrap = Node('character', rig.children, p=(10, 120), s=(1.0, 1.0))
    # variants
    vx = 640
    eyes = ['open', 'sleepy', 'happy', 'squint', 'wink', 'heart']
    for k, v in enumerate(eyes):
        e = copy.deepcopy(rig.find('eyeR_' + v)); e.o = 1.0
        place(e, vx + k * 100, 150, 1.25, 'eye ' + v)
    mouths = ['smile', 'open', 'o', 'yawn', 'frown', 'wobbly', 'tight']
    for k, v in enumerate(mouths):
        m = copy.deepcopy(rig.find('mouth_' + v)); m.o = 1.0
        place(m, vx + k * 88, 290, 1.25, 'mouth ' + v)
    for k, v in enumerate(['worried', 'angry']):
        b = copy.deepcopy(rig.find('brow_' + v)); b.o = 1.0
        b2 = Node('bw', [b], p=(0, 315))
        place(b2, vx + 60 + k * 230, 420, 1.0, 'brows ' + v)
    fr = copy.deepcopy(rig.find('gR2')); fr.p = (-40, 0); fr.r = 0
    place(fr, vx + 520, 410, 1.0, 'gill frond x6')
    # props
    px, py = 640, 560
    props = [
        (bubble('pb_s', BUBBLE_R['s'], o=1), 1.2, 'bubble S'), (bubble('pb_m', BUBBLE_R['m'], o=1), 1.2, 'bubble M'),
        (bubble('pb_l', BUBBLE_R['l'], o=1), 1.2, 'bubble L'), (shrimp('sh', 1.0), 1.05, 'shrimp'),
        (heart('ht', 1.2, o=1), 1.4, 'heart'), (sparkle('sp', 1.2, o=1), 1.4, 'sparkle'),
        (star5('st', 1.2, o=1), 1.4, 'dizzy star'),
    ]
    for k, (n, sc, lab) in enumerate(props):
        place(n, px + k * 88, py, sc, lab)
    props2 = [(letter_z('z', 1.3, o=1), 1.4, 'z'), (bang('bg', o=1), 1.3, '!'), (question('q', o=1), 1.3, '?'),
              (anger('an', o=1), 1.4, 'anger mark'), (teardrop('td', o=1), 1.5, 'teardrop'), (badge('bd'), 1.0, 'badge'),
              (burst('bu', o=1), 1.0, 'pop burst')]
    for k, (n, sc, lab) in enumerate(props2):
        place(n, px + k * 88, py + 150, sc, lab)
    clip = Clip('rig_sheet', 'x', 30, True, Node('r', []))
    out = SVGOut(clip)
    out.lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
    out.lines.append('<rect width="100%" height="100%" fill="#FFFFFF"/>')
    out.lines.append('<style>text{font-family:Nunito,ui-rounded,system-ui,sans-serif;fill:#4A2C3A}.h{font-size:22px;font-weight:700}.l{font-size:12px;fill:#86707B}</style>')
    out.lines.append('<text class="h" x="40" y="48">Axolotl rig, sitting pose</text>')
    out.lines.append('<text class="l" x="40" y="70">Part ids in every SVG and group names in every Lottie: root, shadow, world, move, pose, squash, char,</text>')
    out.lines.append('<text class="l" x="40" y="86">tail1-3, legFL/FR/BL/BR, body, headRig, gR1-3, gL1-3, face, eyes, eyeL/eyeR, mouth, brows, cheekL/R, flower, noseBubble</text>')
    out.lines.append(f'<text class="h" x="{vx - 20}" y="110">Face variants</text>')
    out.lines.append(f'<text class="h" x="{px - 20}" y="500">Props and effects</text>')
    svg_node(out, char_wrap, '')
    for node, x, y, label in cells:
        svg_node(out, node, '')
        out.lines.append(f'<text class="l" x="{x}" y="{y + 54}" text-anchor="middle">{label}</text>')
    out.lines.append('</svg>')
    return '\n'.join(out.lines)


# ------------------------------------------------------------------ previews
def clip_payload():
    idx = json.load(open(f'{PKG}/index.json'))
    for c in idx['clips']:
        c['svgText'] = open(f'{PKG}/{c["svg"]}').read()
        c['lottieData'] = json.load(open(f'{PKG}/{c["lottie"]}'))
    return json.dumps(idx, separators=(',', ':')).replace('</', '<\\/')


def page(view, inline_lottie, payload):
    t = open(f'{SRC}/preview_template.html').read()
    if inline_lottie:
        js = open(LOTTIE_JS).read().replace('</script', '<\\/script')
        tag = f'<script>{js}</script>'
    else:
        tag = '<script src="https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js"></script>'
    t = t.replace('<!--LOTTIE_SCRIPT-->', tag).replace('/*DATA*/', payload).replace("'/*VIEW*/'", f"'{view}'")
    return t


def standalone(html):
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            '<style>[hidden]{display:none!important}</style></head><body>\n' + html + '\n</body></html>\n')


if __name__ == '__main__':
    os.makedirs(f'{PKG}/rig', exist_ok=True)
    open(f'{PKG}/rig/rig_sheet.svg', 'w').write(sheet_svg())
    payload = clip_payload()
    open(f'{PKG}/preview.html', 'w').write(standalone(page('clips', True, payload)))
    open(f'{PKG}/cursor_follow.html', 'w').write(standalone(page('follow', True, payload)))
    print('extras ok')
