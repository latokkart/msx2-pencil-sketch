"""Deliverable stills from the verified long-run dump (verify/final)."""
import json, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
D = Path('verify/out/final')
pb = (D / 'palette.bin').read_bytes()
pal = np.zeros((16, 3), np.uint8)
for i in range(16):
    b0, b1 = pb[2*i], pb[2*i+1]
    pal[i] = [((b0 >> 4) & 7) * 255 // 7, (b1 & 7) * 255 // 7, (b0 & 7) * 255 // 7]
strip = np.load('verify/out/final_a_paper.npy'); ref = np.load('trace_ref.npy')
H = ref.shape[0]; c = 48
pic = strip[0 + c: 0 + c + H]
assert np.array_equal(pic, ref)
pic = pic[::-1]   # strip rows run in scroll order (picture bottom first); flip to display order
full = Image.fromarray(pal[pic]).resize((512, 2 * H), Image.NEAREST)   # x2 rows = display aspect
full.save('column_finished_vram.png')
# single screen at the moment the drawing completes (last busy=2 dump with new plots)
def meta(t): return dict(kv.split('=') for kv in (D / f's7_t{t:05d}.meta').read_text().split())
done = next(t for t in range(2, 1439) if meta(t)['busy'] != '1')   # first dump after the figure phase
m = meta(done); r23 = int(m['r23'])
v = np.frombuffer((D / f's7_t{done:05d}.vram').read_bytes()[:65536], np.uint8).reshape(256, 256)
rows = v[(r23 + np.arange(212)) & 255]
px = np.empty((212, 512), np.uint8); px[:, 0::2] = rows >> 4; px[:, 1::2] = rows & 15
Image.fromarray(pal[px]).resize((512, 424), Image.NEAREST).save('column_screen_at_completion.png')
print('completion dump tot', done, 't=%s' % m['t'], 'plots', m['plots'])
# side by side: source crop | VRAM-stitched picture (same display aspect)
P = json.load(open('paths.json')); X0, X1, Y0, Y1 = P['crop']
src = Image.open('source.jpg').crop((X0, Y0, X1, Y1)).resize((512, 2 * P['H']), Image.LANCZOS)
fv = full.resize((512, 2 * P['H']), Image.NEAREST) if P['H'] != H else full
sb = Image.new('RGB', (512 * 2 + 12, 2 * P['H'] + 28), (60, 60, 60)); sb.paste(src, (0, 28)); sb.paste(fv, (524, 28))
d = ImageDraw.Draw(sb); d.text((6, 8), 'Source (user picture), crop to content', fill=(230, 230, 230)); d.text((530, 8), 'Trace as drawn (VRAM, openMSX)', fill=(230, 230, 230))
sb.save('column_side_by_side.png')
# palette swatch
sw = Image.new('RGB', (16 * 40, 40)); dd = ImageDraw.Draw(sw)
for i in range(16): dd.rectangle((i * 40, 0, i * 40 + 39, 39), fill=tuple(int(x) for x in pal[i])); dd.text((i*40+3, 3), str(i), fill=(255, 0, 0))
print('palette RGB0-7:', [(int(pb[2*i] >> 4) & 7, pb[2*i+1] & 7, pb[2*i] & 7) for i in range(16)])
print('colour px counts in picture:', {int(k): int((pic == k).sum()) for k in np.unique(pic)})
