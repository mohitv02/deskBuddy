#!/usr/bin/env python3
"""Turn animated GIF / WebP / APNG files into a DeskBuddy sprite sheet.

    scripts/gif-to-sprite.py idle.gif [--happy happy.gif] [--alarm alarm.gif]
                             [--size 128] [--effect flames] [--origin 90,40]
                             [--pause-ms 2500] [--pixelated] [--out DIR]

Writes sheet.png + sprite.json into DIR (default ~/.config/deskbuddy/mascot);
restart DeskBuddy to load it. Frames are scaled to fit a --size square,
bottom-centred, keeping transparency. --origin is where the alarm effect
starts, in pixels of the --size frame (e.g. a dragon's mouth).
Requires Pillow (sudo apt install python3-pil).
"""
import argparse
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageSequence
except ImportError:
    sys.exit("Pillow is required: sudo apt install python3-pil")

EFFECTS = ["sparks", "flames", "webs", "shuriken", "none"]
COLUMNS = 8
MAX_FRAMES = 240


def frames_of(path: Path, size: int, pixelated: bool):
    """Return (frames, fps). Each frame is an RGBA size x size image."""
    im = Image.open(path)
    out, durations = [], []
    for frame in ImageSequence.Iterator(im):
        rgba = frame.convert("RGBA")
        scale = min(size / rgba.width, size / rgba.height)
        w, h = max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale))
        rgba = rgba.resize((w, h), Image.NEAREST if pixelated else Image.LANCZOS)
        cell = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        cell.paste(rgba, ((size - w) // 2, size - h), rgba)  # bottom-centred
        out.append(cell)
        durations.append(frame.info.get("duration", 100) or 100)
    if not out:
        sys.exit(f"{path}: no frames")
    avg_ms = sum(durations) / len(durations)
    fps = round(min(60.0, max(1.0, 1000.0 / avg_ms)), 2)
    return out, fps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("idle", type=Path, help="idle animation (loops)")
    ap.add_argument("--happy", type=Path, help="plays once when a todo is completed")
    ap.add_argument("--alarm", type=Path, help="loops while an alarm rings")
    ap.add_argument("--size", type=int, default=128, help="frame size in px (default 128)")
    ap.add_argument("--effect", choices=EFFECTS, help="alarm overlay effect")
    ap.add_argument("--origin", help="effect start point in frame px, e.g. 90,40")
    ap.add_argument("--pause-ms", type=int, default=2500, help="hold between idle loops (0 = loop continuously)")
    ap.add_argument("--pixelated", action="store_true", help="nearest-neighbour scaling for pixel art")
    ap.add_argument("--out", type=Path, default=Path(os.path.expanduser("~/.config/deskbuddy/mascot")))
    args = ap.parse_args()

    if not 16 <= args.size <= 512:
        sys.exit("--size must be between 16 and 512")
    origin = None
    if args.origin:
        try:
            x, y = (float(v) for v in args.origin.split(","))
        except ValueError:
            sys.exit("--origin must look like 90,40")
        origin = [x, y]

    animations, all_frames = {}, []
    for name, path in (("idle", args.idle), ("happy", args.happy), ("alarm", args.alarm)):
        if not path:
            continue
        frames, fps = frames_of(path, args.size, args.pixelated)
        anim = {"start": len(all_frames), "frames": len(frames), "fps": fps}
        if name == "idle":
            anim["pauseMs"] = args.pause_ms
        animations[name] = anim
        all_frames += frames
        print(f"{name}: {len(frames)} frames at {fps} fps from {path}")
    if len(all_frames) > MAX_FRAMES:
        sys.exit(f"{len(all_frames)} frames is too many (max {MAX_FRAMES}); trim the animations")

    cols = min(COLUMNS, len(all_frames))
    rows = -(-len(all_frames) // cols)
    sheet = Image.new("RGBA", (cols * args.size, rows * args.size), (0, 0, 0, 0))
    for i, f in enumerate(all_frames):
        sheet.paste(f, ((i % cols) * args.size, (i // cols) * args.size))

    args.out.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out / "sheet.png", optimize=True)
    manifest = {
        "image": "sheet.png",
        "frameWidth": args.size,
        "frameHeight": args.size,
        "pixelated": args.pixelated,
        "animations": animations,
    }
    if args.effect:
        manifest["alarmEffect"] = args.effect
    if origin:
        manifest["effectOrigin"] = origin
    (args.out / "sprite.json").write_text(json.dumps(manifest, indent=2) + "\n")
    size_kb = (args.out / "sheet.png").stat().st_size // 1024
    print(f"wrote {args.out}/sheet.png ({sheet.width}x{sheet.height}, {size_kb} KB) and sprite.json")
    if size_kb > 8 * 1024:
        print("warning: DeskBuddy loads sheets up to 8 MB; use a smaller --size or fewer frames")
    print("Restart DeskBuddy to load it.")


if __name__ == "__main__":
    main()
