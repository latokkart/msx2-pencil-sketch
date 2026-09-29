#!/usr/bin/env python3
"""Trace match for img2: paper strip (residue_audit_spread output, one row per
scroll step) vs the clean-trace raster trace_ref.npy (gen_vine.py, engine raster).
Per picture: exact pixel+colour comparison over the picture rows.
Usage: vine_match.py audit_prefix dumpdir"""
import re, sys
from pathlib import Path
import numpy as np
pref, d = sys.argv[1], Path(sys.argv[2])
strip = np.load(f'{pref}_paper.npy')
ref = np.load(Path(__file__).resolve().parent.parent / 'trace_ref.npy')
H = ref.shape[0]
starts = []; last = None
for mp in sorted(d.glob('s7_t*.meta'), key=lambda p: int(re.search(r'_t(\d+)', p.name).group(1))):
    m = dict(kv.split('=') for kv in mp.read_text().split())
    if m['busy'] == '1' and int(m['gstart']) != last: last = int(m['gstart']); starts.append(last)
def view(g, c):   # strip rows for local y = 0..H-1
    idx = g + c + np.arange(H)
    return strip[idx] if idx.max() < len(strip) and idx.min() >= 0 else None
g0 = starts[0]; best = None
for c in range(-100, 300):
    v = view(g0, c)
    if v is None: continue
    n = int(((v != 0) & (ref != 0)).sum())
    if best is None or n > best[0]: best = (n, c)
c = best[1]
print(f'pictures start at tots {starts}; alignment strip row = start + {c} + local_y ; ref ink={int((ref!=0).sum())}')
for k, g in enumerate(starts):
    v = view(g, c)
    if v is None: print(f'  picture {k+1} @tot {g}: incomplete in run'); continue
    a, b = v != 0, ref != 0
    print(f'  picture {k+1} @tot {g}: ink={int(a.sum())} recall={(a&b).sum()/b.sum():.4%} precision={(a&b).sum()/max(1,a.sum()):.4%} '
          f'extra={int((a&~b).sum())} missing={int((~a&b).sum())} colour-mismatch={int(((v!=ref)&a&b).sum())} exact={np.array_equal(v, ref)}')
