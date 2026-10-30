"""Path -> Lottie shape items (shared with the earlier dragon converter)."""
import re
def rgb(h):
    h = h.lstrip('#'); return [round(int(h[i:i+2], 16) / 255, 4) for i in (0, 2, 4)] + [1]
def parse_path(d):
    toks = re.findall(r'[MmLlCcQqZz]|-?\d*\.?\d+(?:e-?\d+)?', d)
    subs, cur, i, cmd, pos = [], None, 0, None, (0, 0)
    def num():
        nonlocal i; v = float(toks[i]); i += 1; return v
    while i < len(toks):
        if re.match(r'[A-Za-z]', toks[i]): cmd = toks[i]; i += 1
        if cmd == 'M':
            pos = (num(), num()); cur = dict(v=[pos], i=[(0, 0)], o=[(0, 0)], c=False); subs.append(cur); cmd = 'L'
        elif cmd == 'L':
            p = (num(), num()); cur['v'].append(p); cur['i'].append((0, 0)); cur['o'].append((0, 0)); pos = p
        elif cmd == 'C':
            c1 = (num(), num()); c2 = (num(), num()); p = (num(), num())
            cur['o'][-1] = (c1[0] - pos[0], c1[1] - pos[1]); cur['v'].append(p); cur['i'].append((c2[0] - p[0], c2[1] - p[1])); cur['o'].append((0, 0)); pos = p
        elif cmd == 'Q':
            q = (num(), num()); p = (num(), num())
            c1 = (pos[0] + 2/3*(q[0]-pos[0]), pos[1] + 2/3*(q[1]-pos[1])); c2 = (p[0] + 2/3*(q[0]-p[0]), p[1] + 2/3*(q[1]-p[1]))
            cur['o'][-1] = (c1[0] - pos[0], c1[1] - pos[1]); cur['v'].append(p); cur['i'].append((c2[0] - p[0], c2[1] - p[1])); cur['o'].append((0, 0)); pos = p
        elif cmd in 'Zz':
            cur['c'] = True; v = cur['v']
            if len(v) > 1 and abs(v[-1][0]-v[0][0]) < 1e-6 and abs(v[-1][1]-v[0][1]) < 1e-6:
                cur['i'][0] = cur['i'][-1]; v.pop(); cur['i'].pop(); cur['o'].pop()
            pos = v[0]
        else: raise ValueError(cmd)
    return subs
def path_items(d):
    r = lambda pts: [[round(x, 3), round(y, 3)] for x, y in pts]
    return [{"ty": "sh", "ks": {"a": 0, "k": {"i": r(s['i']), "o": r(s['o']), "v": r(s['v']), "c": s['c']}}} for s in parse_path(d)]
