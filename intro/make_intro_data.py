"""Generate intro data page (bank INTRO_BANK): 4bpp title bitmap rows + per-frame palette sequence.
Levels 1/2/3 of the anti-aliased title -> palette indices 13/14/15 (unused by the sketch)."""
import json, numpy as np
blk = np.load('title_block.npy'); meta = json.load(open('title_block.json'))
IDX = np.array([0, 13, 14, 15], np.uint8)
px = IDX[blk]                                   # (rows, 512)
packed = (px[:, 0::2] << 4) | px[:, 1::2]       # (rows, 256) G7: 2 px/byte, left = high nibble
LEAD, FADE, HOLD, TAIL = 30, 60, 300, 10
W = [0.35, 0.68, 1.0]                           # brightness of AA levels 1..3
b = [0.0]*LEAD + [i/(FADE+1) for i in range(1, FADE+1)] + [1.0]*HOLD + [(FADE+1-i)/(FADE+1) for i in range(1, FADE+1)] + [0.0]*TAIL
def entry(v):                                   # v on 0..14 half-step grey scale (G leads by half a step)
    r = bl = v // 2; g = (v + 1) // 2
    return [(r << 4) | bl, g]
seq = []; vs = []
for bb in b:
    row = []; vv = []
    # c: 0 black, 14 full; strictly between during fades so the top index is full ONLY in the hold
    c = 0.0 if bb == 0 else 14.0 if bb == 1 else 1 + bb * 12.999
    for w in W:
        v = int(c) if w == 1.0 else 2 * int(round(w * c / 2)); vv.append(v); row += entry(v)   # AA levels: pure greys only (no green tint)
    seq.append(row); vs.append(vv)
seq = np.array(seq, np.uint8)
assert packed.size + seq.size <= 16384
data = packed.tobytes() + seq.tobytes()
lines = [f"\nintro_bitmap  EQU $8000\nintro_palseq  EQU $8000+{packed.size}\n    PAGE INTRO_BANK\n    ORG $4000\n"]
for i in range(0, len(packed.tobytes()), 32):
    lines.append("    db " + ",".join(str(x) for x in packed.tobytes()[i:i+32]) + "\n")
for r in seq: lines.append("    db " + ",".join(str(x) for x in r) + "\n")
open('intro_data.inc', 'w').write("".join(lines))
consts = dict(INTRO_TOP=meta['top'], INTRO_ROWS=int(blk.shape[0]), INTRO_FRAMES=len(b), LEAD=LEAD, FADE=FADE, HOLD=HOLD, TAIL=TAIL)
json.dump(dict(consts, v_top=[v[2] for v in vs], bitmap_bytes=int(packed.size), palseq_bytes=int(seq.size)), open('intro_data.json', 'w'))
open('intro_consts.inc', 'w').write("".join(f"{k:<14}EQU {v}\n" for k, v in consts.items() if k.startswith('INTRO')))
print(consts, 'bitmap', packed.size, 'palseq', seq.size, 'distinct top levels', sorted(set(v[2] for v in vs)))
