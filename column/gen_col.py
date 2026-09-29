#!/usr/bin/env python3
"""Column lane tool; modes >= 16 = pen down in palette slot (mode & 15).
Derived from tools/gen_spread.py: paths.json -> 8 ink-balanced
x-lanes, each lane bottom->top ordered pieces (<= SEG_H tall), 4-byte records
(mode, x.b, y.w), multi-bank layout. Writes pic.inc (PAGE blocks), stems.inc,
layout.json and the clean-trace reference raster trace_ref.npy (engine raster).
Header: 254, n, n x (off.w [bank-relative], delay.b, bank.b), pad to 4."""
import json, os, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent
ORIGIN_X = 0; SEG_H = 12; SPLIT_H = 8; PEN_UP, PEN_END, PEN_MULTI = 1, 255, 254
BANK = 16384

def bres(p0, p1):
    x0, y0 = p0[0], p0[1]; x1, y1 = p1[0], p1[1]   # v2: x = screen column 0..511
    dx = abs(x1 - x0); dy = -abs(y1 - y0); sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
    err = dx + dy; out = []
    while True:
        out.append((x0, y0))
        if x0 == x1 and y0 == y1: return out
        e2 = 2 * err
        if e2 >= dy: err += dy; x0 += sx
        if e2 <= dx: err += dx; y0 += sy

def prim_pixels(pr):
    k, pts = pr[0], pr[1]
    return [(pts[0][0], pts[0][1])] if k == 'dot' else bres(*pts)

def make_prims(paths):
    prims = []; seq = 0
    for pid, p in enumerate(paths):
        pts = [tuple(q) for q in p['pts']]; m = p['mode']
        if len(pts) == 1:
            prims.append(('dot', [pts[0]], m, pid, seq)); seq += 1; continue
        for a, b in zip(pts, pts[1:]):
            # a single tall segment cannot finish inside the band (its far end
            # has scrolled on meanwhile): split into <= SPLIT_H-line sub-segments
            n = max(1, -(-abs(b[1] - a[1]) // SPLIT_H))
            q = [a] + [(int(round(a[0] + (b[0] - a[0]) * k / n)), int(round(a[1] + (b[1] - a[1]) * k / n))) for k in range(1, n)] + [b]
            for u, v in zip(q, q[1:]):
                if u != v: prims.append(('seg', [u, v], m, pid, seq)); seq += 1
    return prims

def main():
    cfg = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    nl = cfg.get('lanes', 8); delays = cfg.get('delays', [0, 16, 32, 48, 56, 40, 24, 8])
    pic_bank = cfg.get('pic_bank', 1)
    P = json.load(open(HERE / 'paths.json')); paths = P['paths']
    prims = make_prims(paths)
    for pr in prims:
        for x, y in pr[1]: assert 0 <= x <= 511 and 0 <= y < 32768, pr
    # ink-balanced lane bounds
    w = []
    for pr in prims:
        xs = [x for x, _ in pr[1]]
        w.append((sum(xs) / len(xs), len(prim_pixels(pr))))
    w.sort(); tot = sum(v for _, v in w); acc = 0; bounds = [0]; k = 1
    for mx, v in w:
        acc += v
        while k < nl and acc >= tot * k / nl: bounds.append(int(mx) + 1); k += 1
    bounds.append(512)
    # FINAL: keep the approved vine ROM's lane split so everything outside the cleaned
    # section is drawn by the same pen, in the same order, as before
    if os.environ.get('LANE_BOUNDS'): bounds = [int(v) for v in os.environ['LANE_BOUNDS'].split(',')]
    if 'bounds' in P: bounds = P['bounds']          # v2: lanes/delays chosen by the trace's lane-aware budget
    def lane_of(pr):
        xs = [x for x, _ in pr[1]]; mx = sum(xs) / len(xs)
        for i, bb in enumerate(bounds[1:]):
            if mx < bb: return i
        return nl - 1
    # colour-overlap pixels: last prim (seq) wins; keep them in one lane
    pix = defaultdict(list)
    for i, pr in enumerate(prims):
        for q in prim_pixels(pr): pix[q].append(i)
    conf = [(q, ids) for q, ids in pix.items() if len(set(prims[i][2] for i in ids)) > 1]
    lane_ix = [lane_of(pr) for pr in prims]
    par = list(range(len(prims)))
    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for q, ids in conf:
        for i in ids[1:]: par[f(i)] = f(ids[0])
    glane = {}
    for q, ids in conf:
        wv = max(ids, key=lambda i: prims[i][4]); glane.setdefault(f(wv), lane_ix[wv])
    for q, ids in conf:
        for i in ids: lane_ix[i] = glane[f(i)]
    lanes = [[] for _ in range(nl)]
    for i, pr in enumerate(prims): lanes[lane_ix[i]].append(pr + (i,))
    lane_pieces = []
    for L in lanes:
        pieces = []; cur = None
        for kind, pts, m, p, s, pid in L:
            if (cur is not None and kind == 'seg' and cur['pen'] == p and cur['last_seq'] == s - 1
                    and cur['pts'][-1] == pts[0]
                    and max(cur['ymax'], pts[1][1]) - min(cur['ymin'], pts[1][1]) <= SEG_H):
                cur['pts'].append(pts[1]); cur['modes'].append(m)
                cur['ymax'] = max(cur['ymax'], pts[1][1]); cur['ymin'] = min(cur['ymin'], pts[1][1])
                cur['last_seq'] = s; cur['ids'].append(pid); continue
            if cur: pieces.append(cur)
            if kind == 'dot': cur = dict(pen=p, last_seq=s, pts=[pts[0]], modes=[m], dot=True, ids=[pid])
            else: cur = dict(pen=p, last_seq=s, pts=[pts[0], pts[1]], modes=[m, m], dot=False, ids=[pid])
            ys = [q[1] for q in cur['pts']]; cur['ymin'], cur['ymax'] = min(ys), max(ys)
        if cur: pieces.append(cur)
        pieces.sort(key=lambda c: (c['ymin'], c['last_seq']))
        lane_pieces.append(pieces)
    # v2: permute the (unchanged) delay set so the densest lanes get the smallest delay = most runway
    Hh_ = max(y for pr in prims for _, y in pr[1]) + 2
    peak = []
    for pieces in lane_pieces:
        ld = np.zeros(Hh_)
        for c in pieces:
            for pid in c['ids']:
                for x, y in prim_pixels(prims[pid]): ld[y] += 1
            for x, y in c['pts']: ld[y] += 2
        peak.append(np.convolve(ld, np.ones(40) / 40, 'valid').max())
    ds = sorted(delays); order = sorted(range(nl), key=lambda k: -peak[k])
    delays = [0] * nl
    for rank, k in enumerate(order): delays[k] = ds[rank]
    if 'delays' in P: delays = P['delays']
    print(' lane peaks(w40)', [round(v, 1) for v in peak], '-> delays', delays)
    # IMG3: no fix dots (a dot can only sit on an even column, so odd-column conflicts
    # could not be fixed). Conflicting prims already share one lane, so their order is the
    # lane-stream order; the reference below is rasterised in exactly that order.
    nfix = 0
    def rec(m, x, y): return [m, x >> 1, y & 255, (y >> 8) | ((x & 1) << 7)]   # v2: x LSB in y bit 15
    streams = []
    for pieces in lane_pieces:
        b = []
        for c in pieces:
            x0, y0 = c['pts'][0]
            b += rec(PEN_UP, x0, y0)
            b += rec(c['modes'][0] if c['dot'] else c['modes'][1], x0, y0)
            for (x, y), m in zip(c['pts'][1:], c['modes'][1:]): b += rec(m, x, y)
        b += [PEN_END, 0, 0, 0]
        assert len(b) < 48000, 'lane stream too long for 16-bit linear offset'
        streams.append(b)
    hdr = [PEN_MULTI, nl] + [0] * (4 * nl); hdr += [0] * (-len(hdr) % 4)
    out = list(hdr); starts = []
    for s_ in streams: starts.append(len(out)); out += s_
    for k_ in range(nl):
        L0 = starts[k_]; off = L0 % BANK; bank = pic_bank + L0 // BANK
        assert off + len(streams[k_]) < 65536
        out[2 + 4 * k_: 6 + 4 * k_] = [off & 255, off >> 8, delays[k_], bank]
    nbanks = (len(out) + BANK - 1) // BANK
    stem_bank = pic_bank + nbanks
    # stems: convert framework 5-byte stems -> 4-byte, own bank at $8000
    t = (HERE / 'stems_src.inc').read_text()
    def db(label, end=None):
        s = t[t.index(label + ':') + len(label) + 1:(t.index(end + ':') if end else len(t))]
        v = []
        for line in s.splitlines():
            line = line.split(';')[0]
            if 'db' in line: v += [int(x) for x in line.replace('db', '').replace(',', ' ').split()]
        return v
    def conv(g):
        o = []; i = 0
        while g[i] != PEN_END:
            m, x, y = g[i], g[i+1] | g[i+2] << 8, g[i+3] | g[i+4] << 8; i += 5
            assert x < 256; o += [m, x, y & 255, y >> 8]   # stems: engine loc_x = 2*x (unchanged bytes)
        return o + [PEN_END, 0, 0, 0]
    s0 = conv(db('tmpl_stem0', 'tmpl_stem1')); s1 = conv(db('tmpl_stem1'))
    def pages(data, first):
        txt = ''
        for bi in range(0, len(data), BANK):
            chunk = data[bi:bi + BANK]
            txt += f'\n    PAGE {first + bi // BANK}\n    ORG $4000\n'
            for i in range(0, len(chunk), 16): txt += '    db ' + ', '.join(map(str, chunk[i:i+16])) + '\n'
        return txt
    (HERE / 'pic.inc').write_text('; img4 column picture (column/gen_col.py)' + pages(out, pic_bank) + pages(s0 + s1, stem_bank))
    lay = dict(pic_bank=pic_bank, pic_bytes=len(out), pic_banks=nbanks, stem_bank=stem_bank,
               stem0=0x8000, stem1=0x8000 + len(s0), stem_bytes=len(s0) + len(s1), bounds=bounds,
               delays=delays, lane_starts=starts, lane_bytes=[len(s_) for s_ in streams],
               prims=len(prims), conflicts=len(conf), fix_dots=nfix, LH=P["H"],
               slots=sorted(set((p['mode'] & 15) if p['mode'] >= 16 else {0: 1, 2: 6, 3: 2}[p['mode']] for p in paths)))
    json.dump(lay, open(HERE / 'layout.json', 'w'), indent=1)
    # clean-trace reference raster (what VRAM must show): rows = local y (0 = bottom)
    H = max(y for pr in prims for _, y in pr[1]) + 1
    ref = np.zeros((H, 512), np.uint8)
    col = {0: 1, 2: 6, 3: 2}
    for pieces in lane_pieces:
        for c in pieces:
            for pid in c['ids']:
                pr = prims[pid]
                for x, y in prim_pixels(pr): ref[y, x] = (pr[2] & 15) if pr[2] >= 16 else col[pr[2]]
    np.save(HERE / 'trace_ref.npy', ref)
    print(json.dumps({k: v for k, v in lay.items() if k not in ('lane_starts',)}))
    for k_ in range(nl):
        pcs = lane_pieces[k_]
        print(f' lane {k_}: x[{bounds[k_]},{bounds[k_+1]}) pieces={len(pcs)} bytes={len(streams[k_])} ink={sum(len(prim_pixels(prims[i])) for c in pcs for i in c["ids"])}')
    print('ink px', int((ref > 0).sum()), 'ref rows', H)
main()
