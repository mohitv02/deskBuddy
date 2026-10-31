"""Build every clip to lottie/ and svg/ plus index.json."""
import json, os, sys
from anim import to_lottie, to_svg, FPS
import clips

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
SEAM = {"move_climb": "climbing (held)", "int_dragged": "dangling from scruff (held)",
        "fun_peek": "hidden off-canvas (held)"}
SEAM.update({f"int_look_{d}": "looking (held)" for d in
             ["up", "up_right", "right", "down_right", "down", "down_left", "left", "up_left"]})
END = {"sleep_fall_asleep": "draped", "sleep_wake_up": "sitting", "move_fall_land": "sitting"}


def main(only=None):
    os.makedirs(f"{OUT}/lottie", exist_ok=True)
    os.makedirs(f"{OUT}/svg", exist_ok=True)
    index = []
    for fn in clips.CLIPS:
        if only and fn.__name__ not in only:
            continue
        c = fn()
        lot = to_lottie(c)
        with open(f"{OUT}/lottie/{c.name}.json", "w") as f:
            json.dump(lot, f, separators=(",", ":"))
        with open(f"{OUT}/svg/{c.name}.svg", "w") as f:
            f.write(to_svg(c))
        index.append({"name": c.name, "category": c.category, "base_pose": c.base, "frames": c.frames,
                      "seconds": round(c.frames / FPS, 3), "loop": c.loop,
                      "seam_pose": ("n/a (plays once)" if not c.loop else
                                    SEAM.get(c.name, c.base)),
                      "end_pose": END.get(c.name, c.base if c.loop else "sitting"),
                      "description": c.desc,
                      "lottie": f"lottie/{c.name}.json", "svg": f"svg/{c.name}.svg"})
    if not only:
        with open(f"{OUT}/index.json", "w") as f:
            json.dump({"fps": FPS, "width": 512, "height": 512, "clips": index}, f, indent=2)
    return index




def bundle(out=OUT):
    """clips.js: every clip inlined so the preview works from file:// as well as when hosted."""
    idx = json.load(open(f"{out}/index.json"))
    data = {"index": idx, "lottie": {}, "svg": {}}
    for c in idx["clips"]:
        data["lottie"][c["name"]] = json.load(open(f"{out}/{c['lottie']}"))
        data["svg"][c["name"]] = open(f"{out}/{c['svg']}").read()
    with open(f"{out}/clips.js", "w") as f:
        f.write("window.PANDA=" + json.dumps(data, separators=(",", ":")) + ";\n")


if __name__ == "__main__":
    idx = main(sys.argv[2:] or None)
    if not sys.argv[2:]:
        bundle()
    print(len(idx), "clips")
