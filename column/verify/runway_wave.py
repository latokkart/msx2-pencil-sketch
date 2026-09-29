#!/usr/bin/env python3
"""Runway metric from per-scroll-step VRAM dumps (long_dump).
For every scroll step, rows that GAINED ink (screen row relative to the scroll
in force while plotting) are recorded. A paper line keeps id = row - tot.
  lowest drawing row  : largest screen row where ink was added
  last-stroke runway  : seconds from the girl's final figure plot (girl phase, busy=1; stem phase = busy 2) until
                        that stroke's lowest row passes row 212 (scrolls off)
  per-line runway     : for each inked paper line, seconds from its last ink
                        to scrolling off (min / median over the girl)
Usage: runway.py dumpdir label"""
import re, sys
from pathlib import Path
import numpy as np
d = Path(sys.argv[1]); lab = sys.argv[2] if len(sys.argv) > 2 else str(d)
metas = sorted(d.glob('s7_t*.meta'), key=lambda p: int(re.search(r'_t(\d+)', p.name).group(1)))
def nib(v):
    o = np.empty((256, 512), np.uint8); o[:, 0::2] = v >> 4; o[:, 1::2] = v & 15; return o
T = {}; G = {}; B = {}; ev = []   # (tot_prev, tot_new, row, fig_px, stem_px)
prev = None
for mp in metas:
    m = dict(kv.split('=') for kv in mp.read_text().split())
    tot = int(m['tot']); S = int(m['r23']); T[tot] = float(m['t']); B[tot] = int(m['busy'])
    if m['busy'] == '1': G[tot] = int(m['gstart'])
    px = nib(np.frombuffer(mp.with_suffix('.vram').read_bytes()[:65536], np.uint8).reshape(256, 256))
    if prev and prev[0] == tot - 1:
        add = (px != prev[2]) & (px != 0)
        rows = np.nonzero(add.any(1))[0]
        for vr in rows:
            r = (vr - prev[1]) & 255
            n = int(add[vr].sum()); ph = B.get(tot - 1, B[tot])   # phase while plotting
            ev.append((tot - 1, tot, r, n if ph == 1 else 0, n if ph == 2 else 0))
    prev = (tot, S, px)
ev = np.array(ev)
starts = sorted(set(G.values()))
fpl = (T[max(T)] - T[min(T)]) / (max(T) - min(T))
print(f'== {lab}: steps={len(T)} seconds/scroll-line={fpl:.4f} (= {fpl*59.922:.3f} frames)')
res = []
for k, g in enumerate(starts):
    e = ev[(ev[:, 0] >= g) & (ev[:, 0] < (starts[k+1] if k + 1 < len(starts) else 10**9))]
    fig = e[e[:, 3] > 0]; stem = e[e[:, 4] > 0]
    if not len(fig) or (k + 1 >= len(starts)): continue
    last_t = fig[:, 1].max(); lastrows = fig[fig[:, 1] == last_t][:, 2]
    rlow = lastrows.max(); off = int(last_t + (212 - rlow))
    if off not in T: continue
    lr = T[off] - T[last_t]
    ids = {}
    for tp, tn, r, a, b in fig: ids[r - tp] = (tn, r)
    per = [T[int(tn - 1 + 212 - r)] - T[int(tn)] for tn, r in ids.values() if int(tn - 1 + 212 - r) in T]
    res.append((lr, np.min(per), np.median(per), fig[:, 2].max(), np.percentile(fig[:, 2], 99), stem[:, 2].max() if len(stem) else -1))
    print(f'  girl {k+1} @tot {g}: figure done tot {last_t - g} (+{T[last_t]-T.get(g, T[min(T)]-fpl):.2f}s) last stroke rows {lastrows.min()}..{rlow} '
          f'-> runway {lr:.2f}s | per-line runway min {np.min(per):.2f}s median {np.median(per):.2f}s | '
          f'lowest drawing row fig {fig[:, 2].max()} (99%: {np.percentile(fig[:, 2], 99):.0f}) stem {stem[:, 2].max() if len(stem) else -1}')
