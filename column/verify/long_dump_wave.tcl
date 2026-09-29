# Natural C-BIOS boot. At the END of every ISR that performed a scroll step,
# dump VRAM + state. Runs until scroll_tot >= ::max_tot. Emulated-time based.
set throttle off
set outdir $::dump_outdir
set prefix $::dump_prefix
file mkdir $outdir
set ::last_tot -1
set ::nd 0
proc w16 {a} { expr {[peek $a]+256*[peek [expr {$a+1}]]} }
proc onexit {} {
  set sd [peek 0xC002]; if {$sd != 4 && $sd != 5} return
  set tot [w16 0xC003]
  if {$tot == $::last_tot} return
  set ::last_tot $tot
  set name [format "%s_t%05d" $::prefix $tot]
  save_debuggable VRAM [format "%s/%s.vram" $::outdir $name]
  set mf [open [format "%s/%s.meta" $::outdir $name] w]
  puts $mf [format "r23=%d tot=%d busy=%d anchor=%d gstart=%d ox=%d skip=%d plots=%d isr=%d ovr=%d t=%.4f sp=%04X r8=%d r7=%d" [vdpreg 23] $tot [peek 0xC00C] [peek 0xC0B7] [w16 0xC0B8] [w16 0xC008] [w16 0xC0CC] [w16 0xC0CE] [w16 0xC0E3] [w16 0xC0E1] [machine_info time] [reg SP] [vdpreg 8] [vdpreg 7]]
  close $mf
  incr ::nd
  if {$tot % 250 == 0} { puts stderr "DUMP $name t=[machine_info time]" }
  if {$tot >= $::max_tot} {
    set pf [open [format "%s/palette.bin" $::outdir] w]
    fconfigure $pf -translation binary
    for {set i 0} {$i < 32} {incr i} { puts -nonewline $pf [binary format c [debug read {VDP palette} $i]] }
    close $pf
    puts stderr [format "DONE dumps=%d tot=%d t=%.3f frames~%d isr=%d ovr=%d" $::nd $tot [machine_info time] [expr {int([machine_info time]*59.94)}] [w16 0xC0E3] [w16 0xC0E1]]
    exit
  }
}
debug set_bp $::bp_exit {} onexit
after time 2000 { puts stderr "TIMEOUT tot=[w16 0xC003]"; exit }
