#!/usr/bin/env python3
"""EXPERIMENTAL: re-partition tmpl_girl (from stroke_b01.inc, the verified
trace) into NLANES x-lanes, one pen per lane, each lane feet->head ordered.

Pixel identity: the engine's primitives (dots and Bresenham segments, with
their direction and colour) are replayed exactly as the 4-pen stream would
draw them; only their grouping/order changes. A piece that starts mid-stroke
is encoded UP p, DOWN p (dot at p = the segment's own first pixel).
Output: test/stroke_spread.inc (tmpl_girl + original stems).
Template format (test engine only): 254, n, n x (offset.w, delay.b), verts...
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ORIGIN_X = 8
SEG_H = 12
PEN_UP, PEN_END, PEN_MULTI = 1, 255, 254

def db(t, label, end):
    s = t[t.index(label + ':') + len(label) + 1:t.index(end + ':')]
    out = []
    for line in s.splitlines():
        line = line.split(';')[0]
        if 'db' in line:
            out += [int(x) for x in line.replace('db', '').replace(',', ' ').split()]
    return out

def parse_prims(g):
    """Replay the engine semantics of each original pen stream -> primitives."""
    n = g[1]
    offs = [g[2 + 2 * i] | g[3 + 2 * i] << 8 for i in range(n)]
    prims = []   # (kind, pts, colour, orig_pen, seq)
    seq = 0
    for p in range(n):
        i = offs[p]; prev = None
        while g[i] != PEN_END:
            m, x, y = g[i], g[i + 1] | g[i + 2] << 8, g[i + 3] | g[i + 4] << 8
            i += 5
            sx = (ORIGIN_X + x) * 2
            if sx >= 512:          # engine rejects OOB vertex, clears have_prev
                prev = None; continue
            if m == PEN_UP:
                if prev is not None and prev == (x, y):
                    continue       # chop joint: keep have_prev
                prev = None; continue
            if prev is None:
                prims.append(('dot', [(x, y)], m, p, seq))
            else:
                prims.append(('seg', [prev, (x, y)], m, p, seq))
            seq += 1
            prev = (x, y)
    return prims

def bres(p0, p1):
    """Engine line raster in screen px (x doubled), local y."""
    x0, y0 = (ORIGIN_X + p0[0]) * 2, p0[1]; x1, y1 = (ORIGIN_X + p1[0]) * 2, p1[1]
    dx = abs(x1 - x0); dy = -abs(y1 - y0); sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
    err = dx + dy; out = []
    while True:
        out.append((x0, y0))
        if x0 == x1 and y0 == y1: return out
        e2 = 2 * err
        if e2 >= dy: err += dy; x0 += sx
        if e2 <= dx: err += dx; y0 += sy

def conflicts(prims):
    """Pixels painted by prims of different colours. In the original single
    hair-pen stream the LAST prim (max seq) wins; returns [(pixel, ids)]."""
    from collections import defaultdict
    pix = defaultdict(list)
    for i, (k, pts, m, p, s) in enumerate(prims):
        for q in ([((ORIGIN_X + pts[0][0]) * 2, pts[0][1])] if k == 'dot' else bres(*pts)):
            pix[q].append(i)
    return [(q, ids) for q, ids in pix.items() if len(set(prims[i][2] for i in ids)) > 1]

def lane_of(pr, bounds):
    xs = [(ORIGIN_X + x) * 2 for x, _ in pr[1]]
    mx = sum(xs) / len(xs)
    for k, b in enumerate(bounds[1:]):
        if mx < b:
            return k
    return len(bounds) - 2

def build(nl, delays, bounds):
    t = (ROOT / 'stroke_b01.inc').read_text()
    g = db(t, 'tmpl_girl', 'tmpl_stem0')
    prims = parse_prims(g)
    # colour-overlap pixels: keep every prim touching one in ONE lane (lane of
    # the winning = last prim) so the in-lane order can guarantee the colour.
    conf = conflicts(prims)
    lane_ix = [lane_of(pr, bounds) for pr in prims]
    par = list(range(len(prims)))
    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for q, ids in conf:
        for i in ids[1:]: par[f(i)] = f(ids[0])
    glane = {}
    for q, ids in conf:
        w = max(ids, key=lambda i: prims[i][4]); glane.setdefault(f(w), lane_ix[w])
    for q, ids in conf:
        for i in ids: lane_ix[i] = glane[f(i)]
    lanes = [[] for _ in range(nl)]
    for i, pr in enumerate(prims):
        lanes[lane_ix[i]].append(pr + (i,))
    # chain consecutive (same original pen, contiguous) primitives into pieces
    lane_pieces = []
    for L in lanes:
        pieces = []
        cur = None
        for kind, pts, m, p, s, pid in L:
            if (cur is not None and kind == 'seg' and cur['pen'] == p and cur['last_seq'] == s - 1
                    and cur['pts'][-1] == pts[0]
                    and max(cur['ymax'], pts[1][1]) - min(cur['ymin'], pts[1][1]) <= SEG_H):
                cur['pts'].append(pts[1]); cur['modes'].append(m)
                cur['ymax'] = max(cur['ymax'], pts[1][1]); cur['ymin'] = min(cur['ymin'], pts[1][1])
                cur['last_seq'] = s; cur['ids'].append(pid)
                continue
            if cur: pieces.append(cur)
            if kind == 'dot':
                cur = dict(pen=p, last_seq=s, pts=[pts[0]], modes=[m], dot=True, ids=[pid])
            else:
                cur = dict(pen=p, last_seq=s, pts=[pts[0], pts[1]], modes=[m, m], dot=False, ids=[pid])
            ys = [q[1] for q in cur['pts']]
            cur['ymin'], cur['ymax'] = min(ys), max(ys)
        if cur: pieces.append(cur)
        pieces.sort(key=lambda c: (c['ymin'], c['last_seq']))
        lane_pieces.append(pieces)
    # enforce overlap colours: winner must be painted last in its lane; if the
    # sorted order breaks that, append a 1-pixel dot of the winner colour right
    # after the last piece that touches the pixel (same pixel, no new ink).
    nfix = 0
    for q, ids in conf:
        L = lane_ix[ids[0]]; pcs = lane_pieces[L]
        order = {}
        for pi, c in enumerate(pcs):
            for j, pid in enumerate(c['ids']): order[pid] = (pi, j)
        w = max(ids, key=lambda i: prims[i][4])
        last = max(ids, key=lambda i: order[i])
        if last == w: continue
        lx = q[0] // 2 - ORIGIN_X
        pcs.insert(order[last][0] + 1, dict(pen=-1, last_seq=-1, pts=[(lx, q[1])], modes=[prims[w][2]],
                                            dot=True, ids=[], ymin=q[1], ymax=q[1]))
        nfix += 1
    print(f'colour-overlap pixels={len(conf)} fix-dots={nfix}')
    # encode
    streams = []
    for pieces in lane_pieces:
        b = []
        for c in pieces:
            x0, y0 = c['pts'][0]
            b += [PEN_UP, x0 & 255, x0 >> 8, y0 & 255, y0 >> 8]
            # first DOWN at p0: dot (colour of the segment / dot itself)
            first_mode = c['modes'][0] if c['dot'] else c['modes'][1]
            b += [first_mode, x0 & 255, x0 >> 8, y0 & 255, y0 >> 8]
            for (x, y), m in zip(c['pts'][1:], c['modes'][1:]):
                b += [m, x & 255, x >> 8, y & 255, y >> 8]
        b.append(PEN_END)
        streams.append(b)
    hdr_len = 2 + 3 * nl
    out = [PEN_MULTI, nl]
    off = hdr_len
    for k in range(nl):
        out += [off & 255, off >> 8, delays[k]]
        off += len(streams[k])
    for s_ in streams: out += s_
    stats = [dict(lane=k, pieces=len(lane_pieces[k]),
                  prims=sum(len(c['pts']) - (0 if c['dot'] else 1) for c in lane_pieces[k]),
                  ymin=min((c['ymin'] for c in lane_pieces[k]), default=-1),
                  ymax=max((c['ymax'] for c in lane_pieces[k]), default=-1),
                  delay=delays[k]) for k in range(nl)]
    return out, stats, len(prims)

def fmt(label, raw):
    lines = [f'{label}:']
    for i in range(0, len(raw), 16):
        lines.append('    db ' + ', '.join(str(v) for v in raw[i:i + 16]))
    return '\n'.join(lines) + '\n'

if __name__ == '__main__':
    cfg = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    nl = cfg.get('lanes', 8)
    delays = cfg.get('delays', [0] * nl)
    bounds = cfg.get('bounds') or [16 + round(k * 496 / nl) for k in range(nl)] + [512]
    if cfg.get('balance'):
        # lane bounds at equal cumulative drawing work (pixel length)
        tt = (ROOT / 'stroke_b01.inc').read_text()
        pr = parse_prims(db(tt, 'tmpl_girl', 'tmpl_stem0'))
        w = []
        for kind, pts, m, pp, s in pr:
            xs = [(ORIGIN_X + x) * 2 for x, _ in pts]; ys = [y for _, y in pts]
            w.append((sum(xs) / len(xs), 1 + max(max(xs) - min(xs), max(ys) - min(ys))))
        w.sort(); tot = sum(v for _, v in w); acc = 0; bounds = [0]; k = 1
        for mx, v in w:
            acc += v
            while k < nl and acc >= tot * k / nl:
                bounds.append(int(mx) + 1); k += 1
        bounds.append(512)
    raw, stats, nprims = build(nl, delays, bounds)
    t = (ROOT / 'stroke_b01.inc').read_text()
    stems = t[t.index('tmpl_stem0:'):]
    (ROOT / 'test').mkdir(exist_ok=True)
    (ROOT / 'test' / 'stroke_spread.inc').write_text('; EXPERIMENTAL lane-split girl (tools/gen_spread.py)\n'
                                                     + fmt('tmpl_girl', raw) + stems)
    print(f'prims={nprims} tmpl_girl bytes={len(raw)} bounds={bounds}')
    for s in stats: print(s)
