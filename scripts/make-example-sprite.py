#!/usr/bin/env python3
"""Generate assets/sprite-example/ — an original sprite sheet + sprite.json
showing the layout DeskBuddy expects. Requires Pillow (python3-pil).

Layout: 8 columns x 2 rows of 96x96 frames.
  frames 0-7  idle  (bob, blink on frame 5)
  frames 8-13 happy (two hops, happy eyes)
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

F, SS = 96, 4  # frame size, supersampling factor
OUT = Path(__file__).resolve().parent.parent / "assets" / "sprite-example"
BODY, OUTLINE, BOLT, INK, CHEEK = (255, 216, 77), (107, 74, 18), (255, 159, 28), (43, 33, 16), (255, 143, 177)


def frame(dy=0.0, squash=1.0, blink=False, happy=False, sparkle=0.0):
    s = SS
    im = Image.new("RGBA", (F * s, F * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # shadow shrinks as the body rises
    sw = 22 * (1 - min(abs(dy), 14) / 30)
    d.ellipse([(48 - sw) * s, 86 * s, (48 + sw) * s, 92 * s], fill=(0, 0, 0, 60))
    rx, ry = 31 / math.sqrt(squash), 25 * squash
    cy = 87 - ry + dy
    # antenna + bolt
    d.line([48 * s, (cy - ry + 2) * s, 48 * s, (cy - ry - 8) * s], fill=OUTLINE, width=3 * s)
    bx, by = 48, cy - ry - 22
    bolt = [(51, 0), (41, 13), (47, 13), (44, 21), (56, 8), (50, 8), (53, 0)]
    d.polygon([((x - 48 + bx) * s, (y + by) * s) for x, y in bolt], fill=BOLT, outline=OUTLINE)
    # body
    d.ellipse([(48 - rx) * s, (cy - ry) * s, (48 + rx) * s, (cy + ry) * s], fill=BODY, outline=OUTLINE, width=3 * s)
    d.ellipse([28 * s, (cy - 15) * s, 46 * s, (cy - 6) * s], fill=(255, 255, 255, 110))
    ey = cy - 2
    for ex in (38, 58):
        if happy:
            d.arc([(ex - 5) * s, (ey - 4) * s, (ex + 5) * s, (ey + 6) * s], 200, 340, fill=INK, width=3 * s)
        elif blink:
            d.line([(ex - 5) * s, ey * s, (ex + 5) * s, ey * s], fill=INK, width=3 * s)
        else:
            d.ellipse([(ex - 5.5) * s, (ey - 6.5) * s, (ex + 5.5) * s, (ey + 6.5) * s], fill="white")
            d.ellipse([(ex - 2.2) * s, (ey - 2.2) * s, (ex + 4.2) * s, (ey + 4.2) * s], fill=INK)
    for cx in (29, 67):
        d.ellipse([(cx - 4.5) * s, (cy + 7.5) * s, (cx + 4.5) * s, (cy + 12.5) * s], fill=CHEEK + (190,))
    if happy:
        d.chord([40 * s, (cy + 3) * s, 56 * s, (cy + 17) * s], 0, 180, fill=(232, 86, 111), outline=INK, width=2 * s)
    else:
        d.arc([43 * s, (cy + 5) * s, 53 * s, (cy + 12) * s], 20, 160, fill=INK, width=2 * s)
    if sparkle > 0:
        a = int(255 * sparkle)
        for x, y, r in ((14, 30, 5), (82, 24, 4), (84, 58, 3)):
            pts = [(x, y - r), (x + r / 3, y - r / 3), (x + r, y), (x + r / 3, y + r / 3), (x, y + r), (x - r / 3, y + r / 3), (x - r, y), (x - r / 3, y - r / 3)]
            d.polygon([(px * s, py * s) for px, py in pts], fill=BOLT + (a,))
    return im.resize((F, F), Image.LANCZOS)


def main():
    idle = [frame(dy=-2 * math.sin(i / 8 * 2 * math.pi), squash=1 + 0.02 * math.cos(i / 8 * 2 * math.pi), blink=(i == 5)) for i in range(8)]
    happy = []
    for i in range(6):
        hop = abs(math.sin(i / 6 * 2 * math.pi))
        happy.append(frame(dy=-13 * hop, squash=0.93 if hop < 0.2 else 1.04, happy=True, sparkle=math.sin((i + 0.5) / 6 * math.pi)))
    sheet = Image.new("RGBA", (F * 8, F * 2), (0, 0, 0, 0))
    for i, im in enumerate(idle + happy):
        sheet.paste(im, ((i % 8) * F, (i // 8) * F))
    OUT.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT / "sheet.png", optimize=True)
    manifest = {
        "image": "sheet.png",
        "frameWidth": F,
        "frameHeight": F,
        "pixelated": False,
        "animations": {
            "idle": {"start": 0, "frames": 8, "fps": 8, "pauseMs": 2500},
            "happy": {"start": 8, "frames": 6, "fps": 10},
        },
    }
    (OUT / "sprite.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {OUT}/sheet.png and sprite.json")


if __name__ == "__main__":
    main()
