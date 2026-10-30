import sys, cairo
import rig, anims, front, anims_front as af, anims_tricks as at

def sheet(name, poses, out, scale=1.0, cols=None):
    cols = cols or len(poses)
    rows = (len(poses) + cols - 1) // cols
    fw, fh = int(rig.W * scale), int(rig.H * scale)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, fw * cols, fh * rows + 18)
    c = cairo.Context(surf)
    c.set_source_rgb(0.93, 0.94, 0.96); c.paint()
    for i, P in enumerate(poses):
        x, y = (i % cols) * fw, (i // cols) * fh + 18
        c.set_source_rgb(0.85, 0.87, 0.9) if (i % 2) else c.set_source_rgb(0.9, 0.92, 0.95)
        c.rectangle(x, y, fw, fh); c.fill()
        fr = front.render_front(P, scale) if 'squish' in P else rig.render(P, scale)
        c.set_source_surface(fr, x, y); c.paint()
        c.set_source_rgb(0.3, 0.3, 0.3); c.move_to(x + 4, y + 12); c.show_text(str(i))
    c.set_source_rgb(0, 0, 0); c.move_to(4, 13); c.show_text(name)
    surf.write_to_png(out)

if __name__ == '__main__':
    which = sys.argv[1:]
    table = {
        'idle': lambda: anims.idle(),
        'walk': lambda: anims.walk(),
        'fly': lambda: anims.fly(),
        'takeoff': lambda: anims.takeoff(),
        'land': lambda: anims.land(),
        'fire': lambda: anims.fire()[0],
        'lie_down': lambda: anims.lie_down(),
        'sleep': lambda: anims.sleep(),
        'dragged': lambda: anims.dragged(),
        'fall': lambda: anims.fall(),
        'front_idle': lambda: af.idle_front(),
        'front_walk': lambda: af.walk_front(),
        'approach_walk': lambda: af.approach_walk(),
        'approach_fly': lambda: af.approach_fly(),
        'fly_front': lambda: af.fly_front(),
        'head_tilt': lambda: af.head_tilt(),
        'front_fire': lambda: af.front_fire()[0],
        'boop': lambda: af.boop(),
        'sit': lambda: at.sit(),
        'sit_idle': lambda: at.sit_idle(),
        'roll_over': lambda: at.roll_over(),
        'belly_up': lambda: at.belly_up(),
        'pounce': lambda: at.pounce(),
        'play_bow': lambda: at.play_bow(),
        'shake_off': lambda: at.shake_off(),
        'happy_hop': lambda: at.happy_hop(),
        'stretch_yawn': lambda: at.stretch_yawn(),
        'sniff': lambda: at.sniff(),
        'barrel_roll': lambda: at.barrel_roll(),
        'fireball': lambda: at.fireball(),
    }
    for n in which:
        sheet(n, table[n](), f'/home/claude/dragon/pv_{n}.png', scale=0.75, cols=4)
