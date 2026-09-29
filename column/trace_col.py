#!/usr/bin/env python3
"""img4 column (sunflower / peonies / three girls) -> smooth tonal pencil strokes, 512 cols x H rows
(true display aspect: Screen 7 pixels are 2:1 tall, so H = work height / 2), y=0 bottom.
Ink is traced at output scale: close-set doubled lines are merged (small closing) and skeletonised to
single centrelines, filled shapes (irises, pupils, dark hair spots) become smooth closed outlines;
all strokes are joined through junctions, Gaussian-smoothed along arc length, given a light hand
wobble and simplified at sub-pixel tolerance. Tones: brightest for the outer silhouette of heads and
flowers plus faces/eyes, mid greys for petals, hair strands, clothing, dark greys for fine detail
(sunflower centre, short hatching strokes, sparkles). Then redundancy pass + lane-aware load budget."""
import json, math, sys
from pathlib import Path
from collections import Counter
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import disk
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import curves as C
P = json.load(open(HERE / 'params.json'))
X0, X1, Y0, Y1 = P['crop']
W = P['W']; S = W / (X1 - X0)                     # source px -> work px (square)
WH = int(round((Y1 - Y0) * S)); H = int(round(WH / P['par']))
rng = np.random.default_rng(20260929)
src = Image.open(HERE / 'source.jpg').convert('L').crop((X0, Y0, X1, Y1))
g = np.asarray(src.resize((W, WH), Image.BICUBIC), np.float32)
ink = g < P['thr']
ink = ndi.binary_closing(ink, structure=disk(P['merge_r'])) | ink        # merge doubled lines
ink = ndi.binary_opening(ink, structure=np.ones((2, 2))) | (g < P['thr'] - 60)
lab, n = ndi.label(ink); sz = np.bincount(lab.ravel()); keep = sz >= 4; keep[0] = False; ink = keep[lab]
# filled shapes vs lines
blob = ndi.binary_opening(ink, structure=disk(P['blob_r']))
lab, n = ndi.label(blob); sz = np.bincount(lab.ravel()); keep = sz >= P['blob_min']; keep[0] = False; blob = keep[lab]
thin = ink & ~ndi.binary_dilation(blob, iterations=1)
# column silhouette (exterior = paper connected to the border)
filled = ndi.binary_fill_holes(ndi.binary_closing(ink, structure=disk(6)))
ext_d = ndi.distance_transform_edt(filled)          # distance to exterior
R = []
for p in C.skeleton_strokes(thin, min_len=P['min_len'], spur=P['spur'], join_cos=P['join_cos']): R.append(dict(layer='line', pts=p, closed=False))
bf = ndi.gaussian_filter(blob.astype(np.float32), 1.0)
for p, cl in C.contour_strokes(bf, 0.5, min_len=6): R.append(dict(layer='blob', pts=p, closed=cl))
# zones (source coords -> work coords)
yy, xx = np.mgrid[0:WH, 0:W]
sx_ = X0 + xx / S; sy_ = Y0 + yy / S
Z = {}
for name, z in P['zones'].items():
    if 'ellipse' in z:
        cx, cy, rx, ry = z['ellipse']; Z[name] = ((sx_ - cx) / rx) ** 2 + ((sy_ - cy) / ry) ** 2 <= 1
    else:
        a, b, c, d = z['box']; Z[name] = (sx_ >= a) & (sx_ <= c) & (sy_ >= b) & (sy_ <= d)
head = Z['head1'] | Z['head2'] | Z['head3']; face = Z['face1'] | Z['face2'] | Z['face3']
def region(x, y):
    xi, yi = min(W - 1, max(0, int(x))), min(WH - 1, max(0, int(y)))
    if Z['sfcentre'][yi, xi]: return 'sfcentre'
    if Z['sunflower'][yi, xi]: return 'sunflower'
    if face[yi, xi]: return 'face'
    if head[yi, xi]: return 'hair'
    if Z['peony'][yi, xi]: return 'peony'
    return 'cloth'
T = P['tones']
def tone_of(s, q):
    L = C.length(q) / 1.0
    mids = q[len(q) // 2]; reg = region(*mids)
    onsil = np.mean([ext_d[min(WH - 1, int(y)), min(W - 1, int(x))] <= P['sil_d'] for x, y in q[::3]]) > 0.6
    if s['layer'] == 'blob':
        return T.get(f'{reg}_blob', T.get(f'{reg}_mid')), reg
    if onsil and L > 12:
        return (T['sil_flower'] if reg in ('sunflower', 'peony', 'sfcentre') else T['sil_head'] if reg in ('face', 'hair') else T['sil_cloth']), reg
    if L < P['short']:
        if reg == 'cloth' and L < 6 and ext_d[min(WH - 1, int(mids[1])), min(W - 1, int(mids[0]))] == 0: return T['sparkle'], reg
        return T[f'{reg}_short'], reg
    return T[f'{reg}_long'] if L >= P.get(f'long_{reg}', P['long7']) else T[f'{reg}_mid'], reg
strokes = []
for s in R:
    p = s['pts']
    t, reg = tone_of(s, p)
    sig = P['sig_blob'] if s['layer'] == 'blob' else (P['sig_face'] if reg == 'face' else P['sig_line'])
    q = C.smooth(p, sig, s['closed']) if len(p) > 3 else p
    qs = np.c_[q[:, 0], q[:, 1] / P['par']]                              # screen px (x right, y down)
    if s['layer'] == 'line': qs = C.wobble(qs, rng, P['wobble_amp'] * (0.4 if reg == 'face' else 1), P['wobble_corr'])
    v = C.simplify_int(qs, P['dp_tol'] * (0.6 if reg == 'face' else 1), W, H)
    if len(v) < 2:
        if len(v) == 1 and reg in ('sfcentre', 'cloth'): strokes.append(dict(tone=t, layer=s['layer'], zone=reg, pts=v))
        continue
    strokes.append(dict(tone=t, layer=s['layer'], zone=reg, pts=v))
# eyes: the source ink inside each eye ellipse, area-sampled to screen pixels, drawn as short runs
EYE = np.zeros((H, W), bool)
yo, xo = np.mgrid[0:H, 0:W]
for cx, cy, rx, ry in P['eyes']:
    EYE |= ((X0 + (xo + .5) / S - cx) / rx) ** 2 + ((Y0 + (yo + .5) * P['par'] / S - cy) / ry) ** 2 <= 1
gi = np.asarray(src.resize((W, H), Image.BOX), np.float32)
eyeink = EYE & (gi < P['eye_thr'])
for y in range(H):
    xs = np.nonzero(eyeink[y])[0]
    if not len(xs): continue
    for run in np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1):
        strokes.append(dict(tone=P['eye_tone'], layer='eye', zone='face', pts=[(int(run[0]), y)] if len(run) == 1 else [(int(run[0]), y), (int(run[-1]), y)]))
print('eye px', int(eyeink.sum()))
if '--dbgwin' in sys.argv:
    x0, y0, x1, y1 = [int(v) for v in sys.argv[sys.argv.index('--dbgwin') + 1].split(',')]   # work coords
    v = np.zeros((y1 - y0, x1 - x0, 3), np.uint8); v[ink[y0:y1, x0:x1]] = (70, 70, 70)
    for s_ in R:
        for x, y in s_['pts'].astype(int):
            if x0 <= x < x1 and y0 <= y < y1: v[y - y0, x - x0] = (255, 255, 0) if s_['layer'] == 'line' else (255, 0, 255)
    for s_ in strokes:
        for x, y in s_['pts']:
            yw = int(y * P['par'])
            if x0 <= x < x1 and y0 <= yw < y1: v[yw - y0, x - x0] = (0, 255, 255)
    Image.fromarray(v).resize(((x1 - x0) * 4, (y1 - y0) * 4), Image.NEAREST).save('dbgwin.png')
print('raw strokes', len(strokes), dict(Counter(s['zone'] for s in strokes)))
def bres(a, b):
    x0, y0 = a; x1, y1 = b; dx = abs(x1 - x0); dy = -abs(y1 - y0); sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
    err = dx + dy; o = []
    while True:
        o.append((x0, y0))
        if x0 == x1 and y0 == y1: return o
        e2 = 2 * err
        if e2 >= dy: err += dy; x0 += sx
        if e2 <= dx: err += dx; y0 += sy
PAD = 6
occ = np.zeros((H + 2 * PAD, W + 2 * PAD), bool)
prio = {k: i for i, k in enumerate(P['priority'])}
order = sorted(strokes, key=lambda s: (prio.get(s['layer'], 99), -s['tone'], -C.length(s['pts'])))
final = []
for s in order:
    q = s['pts']
    if len(q) == 1:
        x, y = q[0]
        if s['layer'] == 'eye' or not occ[y + PAD - 1:y + PAD + 2, x + PAD - 1:x + PAD + 2].any():
            final.append(dict(s)); occ[y + PAD, x + PAD] = True
        continue
    runs = []; cur = [q[0]]
    ry, rx = (0, 0) if s['zone'] == 'face' else P['occ_layer'].get(s['layer'], P['occ_r'])
    for a, b in zip(q, q[1:]):
        px = bres(a, b)
        fresh = sum(1 for x, y in px if not occ[y + PAD - ry:y + PAD + ry + 1, x + PAD - rx:x + PAD + rx + 1].any()) / len(px)
        if fresh > P['fresh_frac'] or '--noocc' in sys.argv or s['layer'] in ('blob', 'eye'):
            if not cur: cur = [a]
            cur.append(b)
        else:
            if len(cur) >= 2: runs.append(cur)
            cur = []
    if len(cur) >= 2: runs.append(cur)
    for r in runs:
        if C.length(r) < P['min_run'] and s['layer'] != 'eye': continue
        final.append(dict(tone=s['tone'], layer=s['layer'], zone=s['zone'], pts=r))
        for a, b in zip(r, r[1:]):
            for x, y in bres(a, b): occ[y + PAD, x + PAD] = True
for p in final: p['pts'] = [(x, H - 1 - y) for x, y in p['pts']]
exec(open(HERE / 'budget.py').read())
