"""Real-time clip of one full pass from the per-scroll-step VRAM dumps (verify/final), timed by meta t."""
import re, subprocess
from pathlib import Path
import numpy as np
from PIL import Image
D = Path('verify/out/final'); O = Path('verify/clipframes'); O.mkdir(exist_ok=True)
pb = (D / 'palette.bin').read_bytes()
pal = np.array([[((pb[2*i] >> 4) & 7) * 255 // 7, (pb[2*i+1] & 7) * 255 // 7, (pb[2*i] & 7) * 255 // 7] for i in range(16)], np.uint8)
M = []
for t in range(1, 1600):
    m = dict(kv.split('=') for kv in (D / f's7_t{t:05d}.meta').read_text().split()); M.append((float(m['t']), t, int(m['r23'])))
T = np.array([x[0] for x in M])
t0, t1 = 14.5, 126.0
cache = {}
def frame(i):
    if i < 0: return np.zeros((424, 512, 3), np.uint8)
    if i not in cache:
        _, t, r23 = M[i]
        v = np.frombuffer((D / f's7_t{t:05d}.vram').read_bytes()[:65536], np.uint8).reshape(256, 256)
        rows = v[(r23 + np.arange(212)) & 255]
        px = np.empty((212, 512), np.uint8); px[:, 0::2] = rows >> 4; px[:, 1::2] = rows & 15
        cache.clear(); cache[i] = np.repeat(pal[px], 2, axis=0)
    return cache[i]
n = int((t1 - t0) * 30)
for k in range(n):
    i = int(np.searchsorted(T, t0 + k / 30, side='right')) - 1
    Image.fromarray(frame(i)).save(O / f'f{k:05d}.png')
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '30', '-i', str(O / 'f%05d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', 'sketch_column_drawing.mp4'], check=True)
print('frames', n, 'clip t=%.1f..%.1f s after power-on' % (t0, t1))
