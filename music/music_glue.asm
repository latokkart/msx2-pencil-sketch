;----- MSX-MUSIC background music glue (music/) --------------------------------------
; The MoonBlaster 1.4 replayer (mbplay_rom.asm, module mb) runs from RAM at MUSRAM (it uses
; self-modifying code); the song is copied to SONGRAM. Both are stored in ROM bank MUS_BANK.
; FM detection: every slot/sub-slot is checked for "OPLL" at 401Ch (MSX-MUSIC standard).
; "APRLOPLL" = internal MSX-MUSIC (always enabled). Any other "xxxxOPLL" (FM-PAC: "PAC2OPLL")
; is enabled by setting bit 0 of 7FF6h in its slot. Internal MSX-MUSIC is preferred.
; No FM found -> mus_on = 0: the music is never started and every tick returns at once.
RDSLT     EQU $000C
WRSLT     EQU $0014
MUSRAM    EQU $D000
SONGRAM   EQU $E000
mus_on    EQU $C290      ; 1 = FM found and song started
fm_cur    EQU $C291      ; slot id being checked
fm_int    EQU $C292      ; slot id of internal MSX-MUSIC ($FF = none)
fm_ext    EQU $C293      ; slot id of external FM-PAC  ($FF = none)
mus_pend  EQU $C294      ; VBLANKs not yet serviced by the replayer (sketch phase)
mus_line  EQU $C295      ; set by the line interrupt (display line MUS_LINE reached)
HKEYI     EQU $FD9A
RG0SAV    EQU $F3DF
MUS_LINE  EQU 180        ; replayer step at ~14.6 ms after VBLANK: after the drawing ISR
                         ; (max 15.0 ms, >14 ms in ~0.1% of frames) and before the next one

; called from intro (DI, before the first intro VBLANK): copy, detect, start the song
music_init:
    xor a
    ld  (mus_pend),a
    ld  a,MUS_BANK
    ld  (ASC16_B1),a
    ld  hl,mus_img-$4000+$8000
    ld  de,MUSRAM
    ld  bc,mus_img_end-mus_img
    ldir
    ld  hl,song_img-$4000+$8000
    ld  de,SONGRAM
    ld  bc,song_img_end-song_img
    ldir
    ld  a,1
    ld  (ASC16_B1),a
    call fm_detect
    ld  a,(mus_on)
    or  a
    ret z
    ld  a,1                  ; replayer chip mode 1 = MSX-MUSIC only
    ld  (mb.chips),a
    ld  hl,SONGRAM
    ld  (mb.musadr),hl
    call mb.strmus           ; returns with DI (hook install removed in the adaptation)
    ret

fm_detect:
    xor a
    ld  (mus_on),a
    dec a
    ld  (fm_int),a
    ld  (fm_ext),a
    ld  c,0                  ; primary slot 0..3
.pl:
    ld  hl,EXPTBL
    ld  a,l
    add a,c
    ld  l,a
    ld  a,(hl)
    and $80
    or  c                    ; slot id (E bit set when expanded)
    ld  b,1
    bit 7,a
    jr  z,.sl
    ld  b,4
.sl:
    ld  (fm_cur),a
    push bc
    ld  hl,$401C
    ld  ix,sig_opll
    call cmp_sig
    jr  nz,.nx
    ld  hl,$4018
    ld  ix,sig_aprl
    call cmp_sig
    ld  a,(fm_cur)
    jr  nz,.ext
    ld  hl,fm_int
    jr  .rec
.ext:
    ld  hl,fm_ext
.rec:
    ld  e,a                  ; keep the first one found of each kind ($FF = none yet)
    ld  a,(hl)
    cp  $FF
    jr  nz,.nx
    ld  (hl),e
.nx:
    pop bc
    ld  a,(fm_cur)
    add a,4                  ; next sub-slot
    djnz .sl
    inc c
    ld  a,c
    cp  4
    jr  c,.pl
    ld  a,(fm_int)
    cp  $FF
    jr  nz,.on
    ld  a,(fm_ext)
    cp  $FF
    ret z                    ; no MSX-MUSIC at all: stay silent
    ld  hl,$7FF6             ; FM-PAC: enable the OPLL I/O ports (bit 0 of 7FF6h)
    call RDSLT
    or  1
    ld  e,a
    ld  a,(fm_ext)
    ld  hl,$7FF6
    call WRSLT
.on:
    ld  a,1
    ld  (mus_on),a
    di
    ret

; compare 4 bytes at HL in slot (fm_cur) with IX. Z = equal
cmp_sig:
    ld  b,4
.c:
    push bc
    push hl
    ld  a,(fm_cur)
    call RDSLT
    pop hl
    pop bc
    cp  (ix+0)
    ret nz
    inc hl
    inc ix
    djnz .c
    ret
sig_opll: db "OPLL"
sig_aprl: db "APRL"

; one replayer step per VBLANK; preserves all registers incl. IX, IY and the shadow set
music_tick:
    ld  a,(mus_on)
    or  a
    ret z
    ld  a,(mb.busply)
    or  a
    ret z
    push ix
    push iy
    ex  af,af'
    push af
    exx
    push bc
    push de
    push hl
    call mb.musint
    pop hl
    pop de
    pop bc
    exx
    pop af
    ex  af,af'
    pop iy
    pop ix
    ret

; Sketch phase: the drawing ISR only counts VBLANKs (mus_pend); the main loop runs one
; replayer step per counted VBLANK with interrupts ON, right after the ISR returns. So the
; drawing ISR timing is exactly that of the approved v1.1 ROM and can never be delayed.
music_main:
    ld  a,(mus_line)
    or  a
    jr  nz,.go
    ld  a,(mus_pend)         ; fallback if the line interrupt never came: >= 2 VBLANKs owed
    cp  2
    ret c
.go:
    xor a
    ld  (mus_line),a
.lp:
    ld  a,(mus_pend)
    or  a
    ret z
    di
    ld  hl,mus_pend
    dec (hl)
    ei
    call music_tick
    ld  a,(mus_pend)         ; one step per line interrupt; only catch up if really behind
    cp  2                    ; (a step preempted by the next VBLANK must not trigger an
    jr  nc,.lp               ;  early extra step - that one waits for its own line IRQ)
    ret

; Sketch phase: enable the VDP line interrupt (IE1) at MUS_LINE and hook H.KEYI.
; Called with DI from the engine init, right after the H.TIMI hook is installed.
music_line_on:
    ld  a,(mus_on)
    or  a
    ret z
    xor a
    ld  (mus_line),a
    ld  (mus_pend),a
    ld  a,$C3
    ld  (HKEYI),a
    ld  hl,mus_keyi
    ld  (HKEYI+1),hl
    ld  b,MUS_LINE           ; R#23 = 0 here
    ld  c,19
    call WRTVDP
    ld  a,(RG0SAV)
    or  $10                  ; IE1
    ld  b,a
    ld  c,0
    call WRTVDP
    di
    ret

; H.KEYI: runs first on every interrupt (R#15 is 0 whenever interrupts are enabled).
; Reading S#1 clears FH; set mus_line if it was the line interrupt.
mus_keyi:
    ld  a,1
    out (VDPCTRL),a
    ld  a,15+128
    out (VDPCTRL),a
    in  a,(VDPCTRL)
    push af
    xor a
    out (VDPCTRL),a
    ld  a,15+128
    out (VDPCTRL),a
    pop af
    rrca
    ret nc
    ld  a,1
    ld  (mus_line),a
    ret

; H.TIMI handler while the intro clears VRAM (music only)
music_isr:
    push af
    push bc
    push de
    push hl
    call music_tick
    pop hl
    pop de
    pop bc
    pop af
    ret

; 128KB VRAM clear with interrupts ON (the VBLANK handler only touches ports 7Ch/7Dh and
; the BIOS reads S#0, which does not move the VRAM write pointer); address set up under DI.
clear_vram_mus:
    di
    xor a
    out (VDPCTRL),a
    ld  a,14+128
    out (VDPCTRL),a
    xor a
    out (VDPCTRL),a
    ld  a,$40
    out (VDPCTRL),a
    ei
    ld  d,2
.cv0:
    ld  bc,0
.cv:
    xor a
    out (VDPDRAM),a
    dec bc
    ld  a,b
    or  c
    jr  nz,.cv
    dec d
    jr  nz,.cv0
    di
    ret
