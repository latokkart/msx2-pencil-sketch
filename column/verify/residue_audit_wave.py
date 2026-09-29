#!/usr/bin/env python3
"""Residue / artifact audit over a long run of per-scroll VRAM dumps.

Dumps are taken at the end of every ISR that performed a scroll step
(tools/long_dump.tcl). Checks:
  A  top rows    : screen rows 1..39 (above tip band) are pure background.
  B  hidden band : ring lines at screen_off 212..255 (the recycle area that
                   wraps in via R#23) are pure background.
  C  VRAM diff   : between consecutive dumps, ink may only APPEAR inside the
                   tip band (screen rows 39..71) and may only be REMOVED inside
                   the clear zone (rows 0..39 / 212..255). Anything else is
                   residue or damage.
  D  colours     : only the allowed nibbles (IMG3: 7th arg, default = palette slots used by
                   the wave picture (layout.json 'slots') + 0 black + 2 green stems).
Also builds the "paper" strip: each ring line captured when it is at screen
row 73 (already final, it never changes again), one row per scroll step.
SPREAD variant: tall drawing band [BAND_TOP-1, BAND_BOT) (default 40..200);
paper captured at screen row CAP (default 205, below the band, final) and
shifted by CAP-73 steps so the strip indexes like the original (row 73) one.
Usage: residue_audit_spread.py s7 dumpdir outprefix [BAND_BOT] [CAP] [BAND_TOP]
(v1: 208 209 40 ; v2: 150 151 16)
"""
import re, sys
from pathlib import Path
import numpy as np

sc, d, outp = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
BAND_BOT = int(sys.argv[4]) if len(sys.argv) > 4 else 200
CAP = int(sys.argv[5]) if len(sys.argv) > 5 else 205
BAND_TOP = int(sys.argv[6]) if len(sys.argv) > 6 else 40   # v2: 16
assert BAND_BOT <= CAP < 212
bpl = 256 if sc == 's7' else 128
import json
ALLOWED = set(int(v) for v in sys.argv[7].split(',')) if len(sys.argv) > 7 else \
    {0, 2} | set(json.load(open(Path(__file__).resolve().parent.parent / 'layout.json'))['slots'])
metas = sorted(d.glob(f'{sc}_t*.meta'), key=lambda p: int(re.search(r'_t(\d+)', p.name).group(1)))
def load(mp):
    m = dict(kv.split('=') for kv in mp.read_text().split())
    v = np.frombuffer(mp.with_suffix('.vram').read_bytes()[:256 * bpl], np.uint8).reshape(256, bpl)
    return m, v
def nib(v):  # (256, bpl) -> (256, 2*bpl) pixel nibbles
    out = np.empty((v.shape[0], v.shape[1] * 2), np.uint8)
    out[:, 0::2] = v >> 4; out[:, 1::2] = v & 15
    return out

A = B = C_add = C_del = 0
A_frames = B_frames = C_frames = 0
colours = set()
strip = []
examples = []
prev = None
tots = []
for mp in metas:
    m, v = load(mp)
    S = int(m['r23']); tot = int(m['tot']); tots.append(tot)
    px = nib(v)
    colours |= set(np.unique(px).tolist())
    off = (np.arange(256) - S) & 255          # screen_off of each ring line
    top = px[(off >= 1) & (off < BAND_TOP)]
    hid = px[off >= 212]
    a = int(np.count_nonzero(top)); b = int(np.count_nonzero(hid))
    A += a; B += b; A_frames += a > 0; B_frames += b > 0
    if (a or b) and len(examples) < 8: examples.append(f'tot={tot} top_ink={a} hidden_ink={b}')
    strip.append(px[(S + CAP) & 255].copy())
    if prev is not None and tot == prev[0] + 1:
        Sp, pv = prev[1], prev[2]
        offp = (np.arange(256) - Sp) & 255     # rel. previous scroll
        offn = off                             # rel. new scroll
        changed = pv != px
        added = changed & (px != 0)
        removed = changed & (pv != 0) & (px == 0)
        band_ok = ((offp >= BAND_TOP - 1) & (offp < BAND_BOT))[:, None]
        clr_ok = ((offn < BAND_TOP) | (offn >= 212))[:, None]
        ca = int(np.count_nonzero(added & ~band_ok)); cd = int(np.count_nonzero(removed & ~clr_ok))
        C_add += ca; C_del += cd
        if ca or cd:
            C_frames += 1
            if len(examples) < 8:
                rows = sorted(set(offp[np.nonzero((added & ~band_ok) | (removed & ~clr_ok))[0]].tolist()))
                examples.append(f'tot={tot} bad_add={ca} bad_del={cd} rows={rows[:10]}')
    prev = (tot, S, px)

strip = np.array(strip)[CAP - 73:]   # align: row i <-> same ring line the row-73 capture would give
np.save(f'{outp}_paper.npy', strip)
print(f'{sc}: dumps={len(metas)} tot={tots[0]}..{tots[-1]} contiguous={tots == list(range(tots[0], tots[-1]+1))}')
print(f'  A top rows 1..{BAND_TOP-1} ink pixels      = {A} (frames {A_frames})')
print(f'  B hidden band 212..255 ink pixels = {B} (frames {B_frames})')
print(f'  C band=[{BAND_TOP-1},{BAND_BOT}) cap_row={CAP}; new ink outside band       = {C_add}; ink erased outside clear zone = {C_del} (frames {C_frames})')
print(f'  D nibble values present           = {sorted(colours)}  allowed = {sorted(ALLOWED)}  ok = {colours <= ALLOWED}')
for e in examples: print('   ', e)
ok = A == 0 and B == 0 and C_add == 0 and C_del == 0 and colours <= ALLOWED
print('  RESULT', 'PASS' if ok else 'FAIL')
