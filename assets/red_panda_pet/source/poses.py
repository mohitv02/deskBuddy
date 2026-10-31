"""Key poses for the red panda rig (values are deltas over the rest/sitting pose)."""
import copy
from anim import place, tail_dirs, world, apply, BASES, TAIL_REST_DIRS

ALL_POSE_NODES = ["shadow", "lift", "char", "squash", "legL", "legR", "torso", "body", "head", "earL", "earR",
                  "eyes", "eyeL", "eyeR", "brows", "mouth", "cheekL", "cheekR", "armL", "armR",
                  "tail0", "tail1", "tail2", "tail3", "bamboo", "flag", "branch"]


def merge(*poses):
    out = {}
    for p in poses:
        for n, props in p.items():
            out.setdefault(n, {}).update(copy.deepcopy(props))
    return out


def tail(dirs, torso_rot=0.0):
    return tail_dirs({}, dirs, parent_rot=torso_rot)


def tail_offset(base, d):
    """Add rotation offsets d=[a,b,c,e] to the tail rotations in pose `base`."""
    out = {}
    for k in range(4):
        out[f"tail{k}"] = {"r": base.get(f"tail{k}", {}).get("r", 0.0) + d[k]}
    return out


SIT = {}

# tail swung up beside the body (used for transitions / wag)
TAIL_UP = tail([-12, -42, -84, -96])
TAIL_STRAIGHT_UP = tail([-28, -72, -88, -92])


def stand(h=56, arms=116, head_up=24):
    p = {
        "torso": {"p": (0, -h), "s": (0.97, 1.08)},
        "head": {"p": (0, -head_up)},
        "armL": {"r": arms, "p": (-14, -6), "s": (1, 1.22)}, "armR": {"r": -arms, "p": (14, -6), "s": (1, 1.22)},
        "earL": {"r": 12}, "earR": {"r": -12},
        "shadow": {"s": (0.92, 1)},
    }
    p.update(tail([-22, -58, -86, -100]))
    return p


STAND = stand()


def draped():
    pose = {"torso": {"r": -90}}
    place(pose, "torso", (0, -85), (88, -152))
    place(pose, "head", (0, -252), (-96, -188), rot_world=-8)
    place(pose, "armL", (-50, -128), (-92, -90), rot_world=10)
    place(pose, "armR", (50, -128), (-34, -86), rot_world=-4)
    place(pose, "legL", (-46, -12), (118, -50), rot_world=8)
    place(pose, "legR", (46, -12), (152, -42), rot_world=-6)
    pose.update(tail_dirs(pose, [18, 68, 96, 132]))
    pose["earL"] = {"r": -10}
    pose["earR"] = {"r": 4}
    pose["shadow"] = {"p": (-10, 0), "s": (0.95, 1)}
    return pose


DRAPED = draped()
BASES["draped"]["nodes"] = DRAPED


# tail wrapped across the front of the body (front layer), paws hugging it
def hug_pose(head_tilt=-9):
    p = tail([-70, -170, -170, -100])
    p.update({
        "armL": {"r": -16, "p": (4, 4)}, "armR": {"r": 22, "p": (-2, 2)},
        "head": {"r": head_tilt, "p": (-4, 6)},
    })
    return p


HUG = hug_pose()
