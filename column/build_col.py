#!/usr/bin/env python3
"""Build column/sketch_column_s7.rom (v1.1 "Sunflower column"): spread-pens engine (engine_col.asm:
wrap-safe counter fix, tonal pen modes = palette slots, 9-bit x for the full 512 width) + power-on
intro (intro/intro.asm) + picture (column/pic.inc from gen_col.py) + 7-grey palette (palette.json).
ASCII16, 256KB. Run from the repository root: python3 column/build_col.py"""
import json, re, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'tools'))
from preprocess_screen import apply
lay = json.load(open(HERE / 'layout.json'))
PAL = json.load(open(HERE / 'palette.json'))
INTRO_BANK = lay['stem_bank'] + 1
ROM_PAGES = 16 if INTRO_BANK < 16 else 32   # 256KB or 512KB
body = (HERE / 'engine_col.asm').read_text()
body = re.sub(r"STEM0_ADDR\s+EQU\s+\d+", f"STEM0_ADDR       EQU {lay['stem0']}", body)
body = re.sub(r"STEM1_ADDR\s+EQU\s+\d+", f"STEM1_ADDR       EQU {lay['stem1']}", body)
body = re.sub(r"STEM_BANK\s+EQU\s+\d+", f"STEM_BANK  EQU {lay['stem_bank']}", body)
span = lay['LH'] - 1 + 144                      # vine: 2936-line picture -> 3080
body = re.sub(r"GIRL_SPAN\s+EQU\s+\d+\s*;[^\n]*", f"GIRL_SPAN        EQU {span}    ; IMG3: {lay['LH']-1}-line picture (H-1+144)", body)
# palette table (R,G,B 0..7 per slot)
a = body.index('pal_tab:\n'); b = body.index('\nclear_vram:')
rows = ['pal_tab:']
for i, (r, g, bl, name) in enumerate(PAL['slots']):
    rows.append(f"    db  %0{r:03b}0{bl:03b},%00000{g:03b}   ; {i:2d} {name} R{r} G{g} B{bl}")
body = body[:a] + '\n'.join(rows) + '\n' + body[b:]
anchor = "    call sat_terminate       ; sprite Y=216 terminator (sprites also SPD-off)\n"
assert body.count(anchor) == 1
body = body.replace(anchor, anchor + "    call intro               ; FINAL: power-on intro (returns blanked, VRAM clean)\n")
hang = "    ei\n.hang:\n    halt\n    jr  .hang\n"
assert body.count(hang) == 1
intro = (ROOT / 'intro/intro.asm').read_text()
assert intro.count("INTRO_BANK    EQU 5") == 1
intro = intro.replace("INTRO_BANK    EQU 5", f"INTRO_BANK    EQU {INTRO_BANK}")
body = body.replace(hang, hang + "\n" + (ROOT / 'intro/intro_consts.inc').read_text() + intro)
used = set(range(lay['pic_bank'], lay['pic_bank'] + lay['pic_banks'])) | {lay['stem_bank']}
assert INTRO_BANK not in used and max(used | {INTRO_BANK}) < ROM_PAGES
parts = ["; v1.1 Sunflower column + intro build\n", "    DEFDEVICE ASCII16_1024, $4000, 64\n", "    DEVICE   ASCII16_1024\n\n",
         body, '\n    include "column/pic.inc"\n', '\n    include "intro/intro_data.inc"\n']
for pg in range(1, ROM_PAGES):
    if pg not in used and pg != INTRO_BANK: parts.append(f"\n    PAGE {pg}\n    ORG $4000\n    ds 16384, $FF\n")
parts.append(f'\n    SAVEDEV "column/sketch_column_s7.rom", 0, 0, {ROM_PAGES * 16384}\n')
asm = apply("".join(parts), "s7")
(HERE / 'sketch_column_s7.asm').write_text(asm)
r = subprocess.run(['sjasmplus', '--sym=column/sketch_column_s7.sym', '--lst=column/sketch_column_s7.lst', 'column/sketch_column_s7.asm'],
                   cwd=ROOT, capture_output=True, text=True)
print([l for l in r.stdout.splitlines() if 'rror' in l or 'arning' in l][-3:])
if r.returncode: print(r.stdout[-3000:]); sys.exit(1)
rom = (HERE / 'sketch_column_s7.rom').read_bytes()
ok = len(rom) == ROM_PAGES * 16384
inc = (HERE / 'pic.inc').read_text()
blocks = re.split(r'\n    PAGE (\d+)\n    ORG \$4000\n', inc)
for i in range(1, len(blocks), 2):
    pg = int(blocks[i]); data = bytes(int(v) for l in blocks[i+1].splitlines() if l.strip().startswith('db') for v in l.strip()[2:].split(','))
    m = rom[pg*16384: pg*16384+len(data)] == data; ok &= m
    print(f' page {pg}: {len(data)} bytes @ {pg*16384:#07x} match={m}')
idata = bytes(int(v) for l in (ROOT / 'intro/intro_data.inc').read_text().splitlines() if l.strip().startswith('db') for v in l.strip()[2:].split(','))
m = rom[INTRO_BANK*16384: INTRO_BANK*16384+len(idata)] == idata; ok &= m
print(f' page {INTRO_BANK} (intro): {len(idata)} bytes @ {INTRO_BANK*16384:#07x} match={m}')
print('ROM', len(rom), 'bytes;', ROM_PAGES, 'pages; bank mapping', 'OK' if ok else 'MISMATCH', '; GIRL_SPAN', span, '; INTRO_BANK', INTRO_BANK)
sym = (HERE / 'sketch_column_s7.sym').read_text()
for k in ('isr_ok.no_ovr', 'intro', 'intro_isr.done', 'isr', 'init'):
    mm = re.search(rf'^{re.escape(k)}: EQU (\S+)', sym, re.M); print(k, mm.group(1) if mm else None)
code_end = max(int(v, 16) for v in re.findall(r': EQU 0x0000([4-7][0-9A-F]{3})', sym)); print('page0 last label', hex(code_end))
