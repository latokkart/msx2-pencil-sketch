;----- INTRO (power-on only): serif title, palette fade in / hold 5 s / fade out ----
; Called from init after the first clear_vram/sat_terminate, before display ON.
; Title pixels use palette 13/14/15 (AA levels), which the sketch never uses.
; On return: display blanked, all 128KB VRAM cleared again, sketch palette
; restored (init_palette), SAT terminator rewritten, R#23 = 0, page2 bank = 1,
; H.TIMI = RET. The sketch init that follows is byte-identical to the vine ROM.
INTRO_BANK    EQU 5
intro_idx     EQU $C280      ; 16-bit frame index into intro_palseq (free RAM)

intro:
    di
    call music_init          ; MUSIC: detect MSX-MUSIC, start the song (plays from the black lead-in)
    ld  a,13                 ; palette 13..15 -> black before anything is shown
    out (VDPCTRL),a
    ld  a,16+128
    out (VDPCTRL),a
    xor a
    ld  b,6
.pb:
    out (VDPPAL),a
    djnz .pb
    xor a                    ; R#23 = 0 (explicit; already 0 from init)
    out (VDPCTRL),a
    ld  a,23+128
    out (VDPCTRL),a
    ld  a,INTRO_BANK
    ld  (ASC16_B1),a
    ; VRAM write address INTRO_TOP*256 on page 0 (display still blanked)
    ld  a,(INTRO_TOP*256)>>14
    out (VDPCTRL),a
    ld  a,14+128
    out (VDPCTRL),a
    ld  a,(INTRO_TOP*256)&$FF
    out (VDPCTRL),a
    ld  a,(((INTRO_TOP*256)>>8)&$3F)|$40
    out (VDPCTRL),a
    ld  hl,intro_bitmap
    ld  de,INTRO_ROWS*256
    ld  c,VDPDRAM
.bl:
    outi
    dec de
    ld  a,d
    or  e
    jr  nz,.bl
    ld  hl,0
    ld  (intro_idx),hl
    ld  a,$C3                ; H.TIMI -> intro_isr
    ld  (HTIMI),a
    ld  hl,intro_isr
    ld  (HTIMI+1),hl
    ld  a,$60                ; display ON, IE0 (palette 13..15 still black)
    out (VDPCTRL),a
    ld  a,1+128
    out (VDPCTRL),a
    xor a                    ; read S#0 once: drop any stale VBlank flag so the
    out (VDPCTRL),a          ; first intro_isr call is a real VBlank
    ld  a,15+128
    out (VDPCTRL),a
    in  a,(VDPCTRL)
    ei
.wait:
    halt
    ld  hl,(intro_idx)
    ld  de,INTRO_FRAMES
    or  a
    sbc hl,de
    jr  c,.wait
    di
    ld  hl,music_isr         ; MUSIC: H.TIMI -> music only while VRAM is cleared
    ld  (HTIMI+1),hl
    ld  a,$20                ; display BLANK (IE0 on) while VRAM is cleared
    out (VDPCTRL),a
    ld  a,1+128
    out (VDPCTRL),a
    call init_palette        ; restore sketch palette (0 black,1 white,2 green,6 magenta,...)
    call clear_vram_mus      ; all 128KB -> 0, interrupts on so the music keeps playing
    call sat_terminate
    ld  a,1
    ld  (ASC16_B1),a
    ret

; H.TIMI handler during the intro: one palette step per VBlank (C-BIOS calls us under DI)
intro_isr:
    push af
    push bc
    push de
    push hl
    ld  hl,(intro_idx)
    ld  de,INTRO_FRAMES
    or  a
    sbc hl,de
    jr  nc,.done             ; sequence finished: nothing more to write
    add hl,de
    ld  d,h
    ld  e,l
    add hl,hl
    add hl,de                ; *3
    add hl,hl                ; *6
    ld  de,intro_palseq
    add hl,de
    ld  a,13
    out (VDPCTRL),a
    ld  a,16+128
    out (VDPCTRL),a
    ld  bc,6*256+VDPPAL
    otir
    ld  hl,(intro_idx)
    inc hl
    ld  (intro_idx),hl
.done:
    call music_tick          ; MUSIC
    pop hl
    pop de
    pop bc
    pop af
    ret
