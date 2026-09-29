import json, sys
from collections import Counter
P = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'paths.json'))
def bres(a, b):
    x0, y0 = a; x1, y1 = b; dx = abs(x1 - x0); dy = -abs(y1 - y0); sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
    err = dx + dy; o = []
    while True:
        o.append((x0, y0))
        if x0 == x1 and y0 == y1: return o
        e2 = 2 * err
        if e2 >= dy: err += dy; x0 += sx
        if e2 <= dx: err += dx; y0 += sy
c = Counter()
for p in P['paths']:
    pts = [tuple(v) for v in p['pts']]
    n = 1 if len(pts) == 1 else sum(len(bres(a, b)) - 1 for a, b in zip(pts, pts[1:])) + 1
    c[(p['tone'], p['layer'])] += n
for k in sorted(c, key=lambda k: (-k[0], -c[k])): print(k, c[k])
