#!/bin/bash
# usage (from anywhere): column/verify/runtest.sh NAME [STEPS]   (build first; 3100 steps = 2 full passes)
# Runs the ROM in openMSX (C-BIOS MSX2, throttle off), dumps VRAM every scroll step to column/verify/out/NAME,
# then checks: skipped steps, residue/band audit, exact trace match per picture, pass timing.
set -e
cd "$(dirname "$0")/../.."
N=$1; MT=${2:-3100}; O=column/verify/out
rm -rf $O/$N; mkdir -p $O
BP=$(grep "^isr_ok.no_ovr:" column/sketch_column_s7.sym | sed "s/.*0x0000/0x/")
TCL=$(mktemp --suffix=.tcl)
cat > $TCL << EOT
set ::dump_outdir $PWD/$O/$N
set ::dump_prefix s7
set ::max_tot $MT
set ::bp_exit $BP
source $PWD/column/verify/long_dump_wave.tcl
EOT
timeout 1800 openmsx -machine C-BIOS_MSX2 -cart column/sketch_column_s7.rom -romtype ASCII16 -script $TCL > $O/$N.log 2>&1 || true
rm -f $TCL
grep DONE $O/$N.log
python3 -c "
import glob
print('max skip', max(int(dict(kv.split('=') for kv in open(f).read().split())['skip']) for f in glob.glob('$O/$N/s7_t*.meta')))"
python3 column/verify/residue_audit_wave.py s7 $O/$N $O/${N}_a 150 151 16 | tail -3
python3 column/verify/col_match.py $O/${N}_a $O/$N
python3 column/verify/runway_wave.py $O/$N $N
