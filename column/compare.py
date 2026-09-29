"""source crop | trace (display aspect: rows x2). usage: compare.py out.png [y0 y1 zoom]  (y in output rows)"""
import json, sys
import numpy as np
from PIL import Image
from pathlib import Path
HERE = Path(__file__).resolve().parent
P = json.load(open(HERE / 'paths.json')); H, W = P['H'], P['W']; X0, X1, Y0, Y1 = P['crop']
pal = json.load(open(HERE / 'palette.json'))['slots']
def bres(a, b):
    x0, y0 = a; x1, y1 = b; dx = abs(x1 - x0); dy = -abs(y1 - y0); sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
    err = dx + dy; o = []
    while True:
        o.append((x0, y0))
        if x0 == x1 and y0 == y1: return o
        e2 = 2 * err
        if e2 >= dy: err += dy; x0 += sx
        if e2 <= dx: err += dx; y0 += sy
g = np.zeros((H, W, 3), np.uint8)
for p in P['paths']:
    c = [v * 255 // 7 for v in pal[p['mode'] & 15][:3]]
    pts = [tuple(v) for v in p['pts']]
    px = pts if len(pts) == 1 else [q for a, b in zip(pts, pts[1:]) for q in bres(a, b)]
    for x, y in px: g[H - 1 - y, x] = c
tr = Image.fromarray(g).resize((W, 2 * H), Image.NEAREST)
src = Image.open(HERE / 'source.jpg').convert('RGB').crop((X0, Y0, X1, Y1)).resize((W, 2 * H), Image.LANCZOS)
if len(sys.argv) > 3:
    y0, y1 = int(sys.argv[2]), int(sys.argv[3]); Z = float(sys.argv[4]) if len(sys.argv) > 4 else 1
    x0, x1 = (int(sys.argv[5]), int(sys.argv[6])) if len(sys.argv) > 6 else (0, W)
    tr = tr.crop((x0, 2 * y0, x1, 2 * y1)); src = src.crop((x0, 2 * y0, x1, 2 * y1))
    tr = tr.resize((int(tr.width * Z), int(tr.height * Z)), Image.NEAREST); src = src.resize(tr.size, Image.LANCZOS)
c = Image.new('RGB', (tr.width * 2 + 8, tr.height), (70, 70, 70)); c.paste(src, (0, 0)); c.paste(tr, (tr.width + 8, 0)); c.save(sys.argv[1])
