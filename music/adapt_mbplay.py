#!/usr/bin/env python3
"""Run from anywhere: python3 music/adapt_mbplay.py -> music/mbplay_rom.asm
Adapt the original MoonBlaster 1.4 replayer (mbplay.src, BiFi-updated version from the official
MB1.4 development package) for this ROM. Only integration changes, each asserted exactly:
 1. GEN80 header/BLOAD header/ORG/END removed (the build wraps the code in DISP at MUSRAM).
 2. Memory-mapper paging via port FEh removed (song is copied to fixed RAM, no mapper page).
 3. H.TIMI hook install/restore removed: the ROM's own VBLANK handlers call musint directly.
 3b. musint no longer starts with DI (it may run outside the interrupt, see music_glue.asm).
 4. MSX-AUDIO disabled: MSX-AUDIO voice init (call sinsmm) skipped and the MSX-AUDIO port
    routines (mm2out/mm3out/mmrout, ports C0h/C1h) reduced to RET, so C0h/C1h are never written.
Everything else (MSX-MUSIC FM, rhythm, PSG drums, tempo, fade, pitch/modulation) is untouched."""
from pathlib import Path
HERE = Path(__file__).resolve().parent
src = (HERE.parent / 'third_party/moonblaster/mbplay_original.src').read_bytes().decode('latin-1').replace('\r', '').split('\n')
changes = []
def rep(old, new, count=1):
    global src
    txt = '\n'.join(src); n = txt.count(old)
    assert n == count, (old, n)
    txt = txt.replace(old, new); src = txt.split('\n'); changes.append(old.strip().split('\n')[0])
rep("*u+,q-,s 6\n\n        db    0feh\n        dw    start,einde,start\n        org   0b000h\n",
    "; [ROM] GEN80 options, BLOAD header and ORG removed (assembled inside DISP MUSRAM)\n")
rep("\tld\t(busply),a\n\tin\ta,(0feh)\n\tpush\taf\n\tld\ta,(muspge)\n\tout\t(0feh),a\n\tld\thl,(musadr)",
    "\tld\t(busply),a\n; [ROM] mapper paging removed\n\tld\thl,(musadr)")
rep("\tcall\tsinsmm\n\tcall\tsinspa", "; [ROM] MSX-AUDIO start instruments skipped (no MSX-AUDIO)\n\tcall\tsinspa")
rep("\tld\t(tpval),a\n\tpop\taf\n\tout\t(0feh),a\nstrms3:\tdi\n\tld\thl,0fd9fh\n\tld\tde,oldint\n\tld\tbc,5\n\tldir\n\tld\ta,0c3h\n\tld\t(0fd9fh),a\n\tld\thl,musint\n\tld\t(0fda0h),hl\n\tei\n\tret",
    "\tld\t(tpval),a\n; [ROM] mapper restore and H.TIMI hook install removed: the ROM's VBLANK handlers call musint\nstrms3:\tret")
rep("\tjp\tz,stpms3\n\tin\ta,(0feh)\n\tpush\taf\n\tld\ta,(muspge)\n\tout\t(0feh),a\n",
    "\tjp\tz,stpms3\n; [ROM] mapper paging removed\n")
rep("endint:\tpop\taf\n\tout\t(0feh),a\n\tpop\taf\noldint:", "endint:\n; [ROM] mapper restore removed\n\tpop\taf\noldint:")
rep("stpms2:\tdi\n\tld\thl,oldint\n\tld\tde,0fd9fh\n\tld\tbc,5\n\tldir\n", "stpms2:\tdi\n; [ROM] H.TIMI restore removed (hook never installed)\n")
for lab in ('mm2out', 'mm3out', 'mmrout'):
    txt = '\n'.join(src); a = txt.index('\n' + lab + ':'); b = txt.index('\tret\n', a) + 5
    body = txt[a + 1:b]; assert '0c0h' in body and '0c1h' in body, lab
    txt = txt[:a + 1] + f'{lab}:\tret\t\t; [ROM] MSX-AUDIO port write disabled (was OUT C0h/C1h)\n' + txt[b:]
    src = txt.split('\n'); changes.append(lab)
rep("musint:\n\tdi\n\tpush\taf", "musint:\n; [ROM] DI removed: during the sketch musint runs from the main loop with interrupts on,\n; so the drawing VBLANK handler is never delayed (all its registers incl. shadows are saved)\n\tpush\taf")
rep("einde:  end", "einde:\t\t; [ROM] END removed")
out = '\n'.join(src)
assert '0c0h),a' not in out and '0c1h),a' not in out and '0feh),a' not in out and '0fd9fh' not in out
(HERE / 'mbplay_rom.asm').write_text("; MoonBlaster 1.4 replayer (Remco Schrijvers / MoonSoft; MSX fixes by BiFi), adapted by adapt_mbplay.py\n" + out)
print(len(changes), 'changes:', changes)
