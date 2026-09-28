#!/usr/bin/env python3
"""EXPERIMENTAL build: tools/_asm_code_body_spread.asm + test/stroke_spread.inc
-> test/spread_pens_s7_v2.rom (Screen 7). Never touches orchard_* or final/."""
import re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from preprocess_screen import apply
inc = (ROOT / 'test' / 'stroke_spread.inc').read_text()
def db_len(label, end):
    s = inc[inc.index(label + ':'):inc.index(end + ':')]
    return sum(len(l.split(';')[0].replace('db', '').replace(',', ' ').split()) for l in s.splitlines()[1:] if 'db' in l)
girl = db_len('tmpl_girl', 'tmpl_stem0'); s0 = db_len('tmpl_stem0', 'tmpl_stem1')
stem0 = 0x8000 + girl; stem1 = stem0 + s0
body = (ROOT / 'tools' / '_asm_code_body_spread.asm').read_text()
body = re.sub(r"STEM0_ADDR\s+EQU\s+\d+", f"STEM0_ADDR       EQU {stem0}", body)
body = re.sub(r"STEM1_ADDR\s+EQU\s+\d+", f"STEM1_ADDR       EQU {stem1}", body)
parts = ["; EXPERIMENTAL spread-pens build\n", "    DEFDEVICE ASCII16_1024, $4000, 64\n", "    DEVICE   ASCII16_1024\n\n",
         body, "\n    PAGE 1\n    ORG  $4000\n", '    include "test/stroke_spread.inc"\n']
for pg in range(2, 16):
    parts.append(f"\n    PAGE {pg}\n    ORG $4000\n    ds 16384, $FF\n")
parts.append('\n    SAVEDEV "test/spread_pens_s7_v2.rom", 0, 0, 262144\n')
asm = apply("".join(parts), "s7")
(ROOT / 'test' / 'spread_s7.asm').write_text(asm)
r = subprocess.run(['sjasmplus', '--sym=test/spread_s7.sym', '--lst=test/spread_s7.lst', 'test/spread_s7.asm'],
                   cwd=ROOT, capture_output=True, text=True)
print([l for l in r.stdout.splitlines() if 'rror' in l][-1:], f'girl={girl} stem0={stem0:#x}')
if r.returncode: print(r.stdout[-2000:]); sys.exit(1)
