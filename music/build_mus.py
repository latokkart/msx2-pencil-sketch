#!/usr/bin/env python3
"""Build music/sketch_music_s7.rom (v1.2 "Sunflower column with MSX-MUSIC"): the v1.1 build
(column/ picture, palette, layout; intro/ data) with music/engine_mus.asm, music/intro_mus.asm,
music/music_glue.asm and the adapted MoonBlaster 1.4 replayer (music/mbplay_rom.asm) + song
(music/song.mbm) in bank MUS_BANK. ASCII16, 256KB. Run from the repository root:
    python3 music/build_mus.py"""
import json, re, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'tools'))
from preprocess_screen import apply
COL = ROOT / 'column'
lay = json.load(open(COL / 'layout.json'))
PAL = json.load(open(COL / 'palette.json'))
INTRO_BANK = lay['stem_bank'] + 1
ROM_PAGES = 16 if INTRO_BANK < 16 else 32   # 256KB or 512KB
body = (HERE / 'engine_mus.asm').read_text()
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
hang = "    ei\n.hang:\n    halt\n    call music_main          ; MUSIC: replayer steps for the VBLANKs just counted\n    jr  .hang\n"
assert body.count(hang) == 1
intro = (HERE / 'intro_mus.asm').read_text()
assert intro.count("INTRO_BANK    EQU 5") == 1
intro = intro.replace("INTRO_BANK    EQU 5", f"INTRO_BANK    EQU {INTRO_BANK}")
MUS_BANK = INTRO_BANK + 1
body = body.replace(hang, hang + "\n" + (ROOT / 'intro/intro_consts.inc').read_text() + intro + f"\nMUS_BANK EQU {MUS_BANK}\n" + (HERE / 'music_glue.asm').read_text())
used = set(range(lay['pic_bank'], lay['pic_bank'] + lay['pic_banks'])) | {lay['stem_bank']}
assert INTRO_BANK not in used and MUS_BANK not in used and max(used | {INTRO_BANK, MUS_BANK}) < ROM_PAGES
parts = ["; v1.2 Sunflower column + intro + MSX-MUSIC build\n", "    DEFDEVICE ASCII16_1024, $4000, 64\n", "    DEVICE   ASCII16_1024\n\n",
         body, '\n    include "column/pic.inc"\n', '\n    include "intro/intro_data.inc"\n',
         f'\n    PAGE {MUS_BANK}\n    ORG $4000\nmus_img:\n    MODULE mb\n    DISP $D000\n    include "music/mbplay_rom.asm"\n    ENT\n    ENDMODULE\nmus_img_end:\nsong_img:\n    incbin "music/song.mbm"\nsong_img_end:\n    ds $8000-$, $FF\n    ASSERT mus_img_end-mus_img <= $E000-$D000\n    ASSERT song_img_end-song_img <= $E800-$E000\n']
for pg in range(1, ROM_PAGES):
    if pg not in used and pg not in (INTRO_BANK, MUS_BANK): parts.append(f"\n    PAGE {pg}\n    ORG $4000\n    ds 16384, $FF\n")
parts.append(f'\n    SAVEDEV "music/sketch_music_s7.rom", 0, 0, {ROM_PAGES * 16384}\n')
asm = apply("".join(parts), "s7")
(HERE / 'sketch_music_s7.asm').write_text(asm)
r = subprocess.run(['sjasmplus', '--sym=music/sketch_music_s7.sym', '--lst=music/sketch_music_s7.lst', 'music/sketch_music_s7.asm'],
                   cwd=ROOT, capture_output=True, text=True)
print([l for l in r.stdout.splitlines() if 'rror' in l or 'arning' in l][-3:])
if r.returncode: print(r.stdout[-3000:]); sys.exit(1)
rom = (HERE / 'sketch_music_s7.rom').read_bytes()
ok = len(rom) == ROM_PAGES * 16384
inc = (COL / 'pic.inc').read_text()
blocks = re.split(r'\n    PAGE (\d+)\n    ORG \$4000\n', inc)
for i in range(1, len(blocks), 2):
    pg = int(blocks[i]); data = bytes(int(v) for l in blocks[i+1].splitlines() if l.strip().startswith('db') for v in l.strip()[2:].split(','))
    m = rom[pg*16384: pg*16384+len(data)] == data; ok &= m
    print(f' page {pg}: {len(data)} bytes @ {pg*16384:#07x} match={m}')
idata = bytes(int(v) for l in (ROOT / 'intro/intro_data.inc').read_text().splitlines() if l.strip().startswith('db') for v in l.strip()[2:].split(','))
m = rom[INTRO_BANK*16384: INTRO_BANK*16384+len(idata)] == idata; ok &= m
print(f' page {INTRO_BANK} (intro): {len(idata)} bytes @ {INTRO_BANK*16384:#07x} match={m}')
song = (HERE / 'song.mbm').read_bytes(); mb = rom[MUS_BANK*16384:(MUS_BANK+1)*16384]; k = mb.find(song)
m = k > 0 and mb[k+len(song):] == b'\xff' * (16384-k-len(song)); ok &= m
print(f' page {MUS_BANK} (music): replayer {k} bytes + song {len(song)} bytes @ {MUS_BANK*16384:#07x} match={m}')
# every page except code (0) and music (MUS_BANK) identical to the v1.1 ROM
v11 = (ROOT / 'rom/sketch_column_s7.rom').read_bytes()
diff = [p for p in range(ROM_PAGES) if v11[p*16384:(p+1)*16384] != rom[p*16384:(p+1)*16384]]
same = set(diff) <= {0, MUS_BANK}; print(f' pages differing from v1.1: {diff} (expected [0, {MUS_BANK}])'); ok &= same
print('ROM', len(rom), 'bytes;', ROM_PAGES, 'pages; bank mapping', 'OK' if ok else 'MISMATCH', '; GIRL_SPAN', span, '; INTRO_BANK', INTRO_BANK)
sym = (HERE / 'sketch_music_s7.sym').read_text()
for k in ('isr_ok.no_ovr', 'intro', 'intro_isr.done', 'isr', 'init', 'music_tick', 'mb.musint', 'mb.strmus', 'mb.busply', 'mb.einde', 'music_init'):
    mm = re.search(rf'^{re.escape(k)}: EQU (\S+)', sym, re.M); print(k, mm.group(1) if mm else None)
code_end = max(int(v, 16) for v in re.findall(r': EQU 0x0000([4-7][0-9A-F]{3})', sym)); print('page0 last label', hex(code_end))
