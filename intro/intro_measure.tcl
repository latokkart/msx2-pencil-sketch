# Intro timing: log every intro_isr call (palette 13..15, R#23, R#1, time), then dump VRAM+palette
# at the first engine ISR exit and stop.
set throttle off
set ::log [open $::out_log w]
proc w16 {a} { expr {[peek $a]+256*[peek [expr {$a+1}]]} }
proc pal {} { set s {}; for {set k 26} {$k < 32} {incr k} { lappend s [debug read {VDP palette} $k] }; return $s }
debug set_bp $::bp_intro {} { puts $::log [format "INTRO_ENTER t=%.6f r23=%d" [machine_info time] [vdpreg 23]] }
debug set_bp $::bp_iisr_done {} {
  puts $::log [format "F idx=%d t=%.6f r23=%d r1=%d pal=%s" [w16 0xC280] [machine_info time] [vdpreg 23] [vdpreg 1] [pal]]
}
set ::first 1
debug set_bp $::bp_exit {} {
  if {$::first} {
    set ::first 0
    set t [machine_info time]
    save_debuggable VRAM $::out_vram
    set pf [open $::out_pal w]; fconfigure $pf -translation binary
    for {set k 0} {$k < 32} {incr k} { puts -nonewline $pf [binary format c [debug read {VDP palette} $k]] }
    close $pf
    puts $::log [format "ENGINE_FIRST_ISR t=%.6f isr=%d tot=%d r23=%d r1=%d bank2=?" $t [w16 0xC0E3] [w16 0xC003] [vdpreg 23] [vdpreg 1]]
    close $::log; exit
  }
}
after time 60 { puts $::log TIMEOUT; close $::log; exit }
