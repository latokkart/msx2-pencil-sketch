"""screen_at.py TOT OUT : the 512x424 screen as shown at dump TOT of verify/final"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
D = Path('verify/final'); t = int(sys.argv[1])
pb = (D / 'palette.bin').read_bytes()
pal = np.array([[((pb[2*i] >> 4) & 7) * 255 // 7, (pb[2*i+1] & 7) * 255 // 7, (pb[2*i] & 7) * 255 // 7] for i in range(16)], np.uint8)
m = dict(kv.split('=') for kv in (D / f's7_t{t:05d}.meta').read_text().split())
v = np.frombuffer((D / f's7_t{t:05d}.vram').read_bytes()[:65536], np.uint8).reshape(256, 256)
rows = v[(int(m['r23']) + np.arange(212)) & 255]
px = np.empty((212, 512), np.uint8); px[:, 0::2] = rows >> 4; px[:, 1::2] = rows & 15
Image.fromarray(pal[px]).resize((512, 424), Image.NEAREST).save(sys.argv[2]); print(t, 't=', m['t'])
