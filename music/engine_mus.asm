;==============================================================================
; Girl-only multipen pencil scroll — Screen 7/G6 or Screen 5/G4
; Build: ./build.sh s7 | ./build.sh s5
; 16-bit local X/Y; NUM_PENS=4; scroll-DOWN (R#23--); tip at TOP (TIP_PREFER).
; Feet→head; pens paced to frontier+FRONTIER_SLACK.
; ONLY tmpl_girl + short green stems. enable_cart_page2 kept.
;==============================================================================
; Define SCREEN5 via preprocess for S5 builds.

WRTVDP  EQU $0047
CLRSPR  EQU $0069
HTIMI   EQU $FD9F
VDPDRAM EQU $98
VDPCTRL EQU $99
VDPPAL  EQU $9A
VDPREGI EQU $9B
ASC16_B0 EQU $6000
ASC16_B1 EQU $7000
RSLREG  EQU $0138
ENASLT  EQU $0024
EXPTBL  EQU $FCC1

SCROLL_PERIOD    EQU 4
PIXELS_PER_FRAME EQU 12     ; SPREAD: shared line-pixel budget (14 = max with 0 drops, 16 drops; 12 kept for margin)
TIP_PREFER       EQU 24     ; SPREAD v2: was 48 (band moved up)
BAND_TOP         EQU TIP_PREFER-FRONTIER_SLACK ; = 16. plots allowed in rows [BAND_TOP, BAND_BOT)
SCRUB_N          EQU 44+BAND_TOP   ; scrub zone: hidden 212..255 + rows 0..BAND_TOP-1
PEN_WAIT         EQU 27     ; SPREAD: pen+27/28 = scroll_tot at which a waiting pen wakes
CATCH_BURST      EQU 8      ; SPREAD: px per turn for a lagging pen
RATE_DIV         EQU 4      ; SPREAD: on-schedule pen steps every RATE_DIV frames
CATCH_LAG        EQU 32     ; SPREAD: rows behind nominal before full speed
STEM_SHIFT       EQU 0      ; SPREAD v2: girl ends at tot 528 vs 444 in the final (stem anchor offset, see start_stem)
BAND_BOT         EQU 150    ; SPREAD v2: hard skip limit; clear zone rows 0..15 + 212..255
BAND_H           EQU 112    ; legacy (unlocked window was this; tip height ~)
FRONTIER_SLACK   EQU 8      ; pens may draw only up to frontier+this
CLEAR_AFTER      EQU 100    ; scroll lines after girl span before next girl
NUM_PENS         EQU 8      ; SPREAD: 8 lanes (set by template)
LINE_BURST       EQU 1      ; max pixels one pen steps per RR turn
VERT_COST        EQU 2      ; budget units per consumed vertex
STEM0_ADDR       EQU 44063  ; auto
STEM1_ADDR       EQU 44389  ; auto
PEN_STRIDE       EQU 32
PAST_BELOW       EQU 150    ; skip only if screen_off > TIP+this (far below tip)
PAST_SLACK       EQU 150    ; legacy name = PAST_BELOW (frontier fallback)
GIRL_SPAN        EQU 3080    ; IMG2: 2936-line picture; next starts at +GIRL_SPAN+CLEAR_AFTER

COL_PAPER   EQU 0      ; paper/backdrop = BLACK (palette 0)
COL_DARK    EQU 1      ; main line = WHITE (palette 1)
COL_GREEN   EQU 2
COL_MAGENTA EQU 6

PEN_DOWN_D EQU 0
PEN_UP     EQU 1
PEN_DOWN_M EQU 2
PEN_DOWN_G EQU 3
PEN_END    EQU 255
REC_SIZE   EQU 4        ; IMG2: vertex record = mode, x.b, y.w (never straddles a bank)
PEN_BANK   EQU 29       ; IMG2: pen+29 = lane base ROM bank
PIC_BANK   EQU 1        ; IMG2: picture template starts at bank 1 ($8000)
STEM_BANK  EQU 1        ; auto (build)
PEN_MULTI  EQU $FE

; ---- RAM ----
scroll_y      EQU $C000      ; R#23 value (8-bit ring)
frame         EQU $C001
scroll_div    EQU $C002
scroll_tot_lo EQU $C003      ; 16-bit total scroll (window gate)
scroll_tot_hi EQU $C004
path_ptr      EQU $C005      ; base of current template
path_bank     EQU $C007
origin_x_lo   EQU $C008
origin_x_hi   EQU $C009
origin_y_lo   EQU $C00A      ; 16-bit world origin (= scroll_tot+TIP at spawn)
origin_y_hi   EQU $C00B
busy          EQU $C00C      ; 0=idle 1=girl 2=stem
have_tip      EQU $C00D
tip_x_lo      EQU $C00E
tip_x_hi      EQU $C00F
tip_y_lo      EQU $C010
tip_y_hi      EQU $C011
band_base_lo  EQU $C012
band_base_hi  EQU $C013
girl_start_lo EQU $C0B8
girl_start_hi EQU $C0B9
anchor_page_y EQU $C0B7   ; VRAM Y of tip at girl/stem spawn (fixed)
frontier_lo   EQU $C0BA
frontier_hi   EQU $C0BB
scroll_y_snap EQU $C0D8   ; scroll_y frozen for this stroke_tick
skip_count_lo EQU $C0CC   ; verts skipped by past gate (per girl)
skip_count_hi EQU $C0CD
plot_count_lo EQU $C0CE   ; pixels plotted (per girl)
plot_count_hi EQU $C0CF
unlock_lo    EQU $C0BC
unlock_hi    EQU $C0BD
past_lo      EQU $C0BE
past_hi      EQU $C0BF
clear_tot_lo EQU $C0CA     ; next girl allowed at scroll_tot >= this
clear_tot_hi EQU $C0CB
cur_pen       EQU $C014
rng           EQU $C015
phase         EQU $C016      ; 0=want girl 1=want stem
pix_color     EQU $C017
plot_xlo      EQU $C018
plot_xhi      EQU $C019
plot_y        EQU $C01A
; per-pen at pens_base (stride 32):
; +0  si.w  +2 region_off.w  +4 have_prev  +5 prev_lx.w  +7 prev_ly.w
; +9  done  +10 delay (lane pacing offset) +11 ln_active
; +12 ln_cx.w  +14 ln_cy  +15 ln_x1.w  +17 ln_y1
; +18 ln_dx.w  +20 ln_dy  +21 ln_sx  +22 ln_sy  +23 ln_err.w  +25 ln_color
pens_base     EQU $C300   ; SPREAD: room for 8 pens x 32

    SLOT 1
    PAGE 0
    ORG  $4000

    db  "AB"
    dw  init
    dw  0
    dw  0
    dw  0

;----- cart page2 -----------------------------------------------------------
enable_cart_page2:
    call RSLREG
    rrca
    rrca
    and 3
    ld  c,a
    ld  b,0
    ld  hl,EXPTBL
    add hl,bc
    ld  a,(hl)
    and $80
    or  c
    ld  c,a
    inc hl
    inc hl
    inc hl
    inc hl
    ld  a,(hl)
    and $0C
    or  c
    ld  h,$80
    call ENASLT
    di
    ret

;----- init -----------------------------------------------------------------
init:
    di
    call enable_cart_page2
    xor a
    ld  (ASC16_B0),a
    ld  a,1
    ld  (ASC16_B1),a
    ld  (path_bank),a

; [[S5_START]]
    ld  b,$06
    ld  c,0
    call WRTVDP
    ld  b,$20            ; IE0 on, display BLANK until VRAM clean
    ld  c,1
    call WRTVDP
; [[S5_END]]
; [[S7_START]]
    ld  b,$0A
    ld  c,0
    call WRTVDP
    ld  b,$20            ; IE0 on, display BLANK until VRAM clean
    ld  c,1
    call WRTVDP
; [[S7_END]]
    ld  b,$1F
    ld  c,2
    call WRTVDP
    ld  b,$80
    ld  c,3
    call WRTVDP
    ld  b,$01
    ld  c,4
    call WRTVDP
    ld  b,$F7
    ld  c,5
    call WRTVDP
    ld  b,$03            ; SAT -> $1FA00, outside the displayed 256-line page
    ld  c,11
    call WRTVDP
    ld  b,$20
    ld  c,6
    call WRTVDP
    ld  b,COL_PAPER
    ld  c,7
    call WRTVDP
    ld  b,$2A            ; TP=1 VR=1 SPD=1 (sprites disabled)
    ld  c,8
    call WRTVDP
    ld  b,$80
    ld  c,9
    call WRTVDP
    ld  b,$00
    ld  c,23
    call WRTVDP

    call init_palette
    call clear_vram          ; all 128KB -> 0 (black)
    call sat_terminate       ; sprite Y=216 terminator (sprites also SPD-off)
    ; display ON only after VRAM is clean
; [[S5_START]]
    ld  b,$60
    ld  c,1
    call WRTVDP
; [[S5_END]]
; [[S7_START]]
    ld  b,$60
    ld  c,1
    call WRTVDP
; [[S7_END]]
    xor a
    ld  (scrub_k),a
    ld  (overrun_lo),a
    ld  (overrun_hi),a
    ld  (isr_cnt_lo),a
    ld  (isr_cnt_hi),a
    ld  (exit_guard),a
    ld  (exit_guard+1),a

    xor a
    ld  (scroll_y),a
    ld  (scroll_y_snap),a
    ld  (scroll_tot_lo),a
    ld  (scroll_tot_hi),a
    ld  (frame),a
    ld  (busy),a
    ld  (in_isr),a
    ld  (have_tip),a
    ld  (phase),a
    ld  (cur_pen),a
    ld  (clear_tot_lo),a
    ld  (clear_tot_hi),a
    ld  (scroll_alt),a       ; SPREAD v2: 4/5 alternation phase
    ld  a,SCROLL_PERIOD
    ld  (scroll_div),a
    ld  a,$A5
    ld  (rng),a

    ; install HTIMI hook: JP isr
    ld  a,$C3
    ld  (HTIMI),a
    ld  hl,isr
    ld  (HTIMI+1),hl
    call music_line_on       ; MUSIC: line interrupt that paces the replayer (FM only)
    ei
.hang:
    halt
    call music_main          ; MUSIC: replayer steps for the VBLANKs just counted
    jr  .hang

;----- correct MSX2 palette via R#16 / port $9A -----------------------------
; byte0 = 0rrr0bbb, byte1 = 00000ggg
init_palette:
    ; Explicit palette (C-BIOS defaults differ from real MSX2).
    ; byte0 = 0rrr0bbb, byte1 = 00000ggg
    xor a
    out (VDPCTRL),a
    ld  a,16+128
    out (VDPCTRL),a
    ld  hl,pal_tab
    ld  b,32
.p:
    ld  a,(hl)
    out (VDPPAL),a
    inc hl
    djnz .p
    ret
pal_tab:
    db  %00000000,%00000000   ; 0 paper   BLACK
    db  %01110111,%00000111   ; 1 ink     WHITE
    db  %00100010,%00000110   ; 2 stem    bright green R2 G6 B2
    db  %00110011,%00000011   ; 3 unused  dark grey (visible if ever used)
    db  %00110011,%00000011   ; 4
    db  %00110011,%00000011   ; 5
    db  %01110111,%00000011   ; 6 hair    bright magenta R7 G3 B7
    db  %00110011,%00000011   ; 7..15 dark grey
    db  %00110011,%00000011
    db  %00110011,%00000011
    db  %00110011,%00000011
    db  %00110011,%00000011
    db  %00110011,%00000011
    db  %00110011,%00000011
    db  %00110011,%00000011
    db  %00110011,%00000011

clear_vram:
    ; 128KB CPU fill from $00000 (auto-increment carries into R#14 in G4..G7).
    xor a
    out (VDPCTRL),a
    ld  a,14+128
    out (VDPCTRL),a
    xor a
    out (VDPCTRL),a
    ld  a,$40
    out (VDPCTRL),a
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
    ret

; Sprite attribute table at $1FA00 (R#11=3,R#5=$F7): Y=216 ends the list.
sat_terminate:
    ld  a,7                  ; A16..A14 of $1FA00 = 111
    out (VDPCTRL),a
    ld  a,14+128
    out (VDPCTRL),a
    xor a                    ; A7..A0
    out (VDPCTRL),a
    ld  a,$3A|$40            ; A13..A8 = $3A, write
    out (VDPCTRL),a
    ld  a,216
    out (VDPDRAM),a
    ret

;----- ISR ------------------------------------------------------------------
isr:
    di
    ld  a,(in_isr)
    or  a
    ret nz               ; nested — stay DI, BIOS will EI
isr_ok:
    ld  a,1
    ld  (in_isr),a
    ; BIOS stack — private switch reintroduced late tot corruption in testing
    push af
    push bc
    push de
    push hl
    push ix
    push iy
    ld  hl,mus_pend          ; MUSIC: count this VBLANK for the main-loop replayer
    inc (hl)
    ld  a,(frame)
    inc a
    ld  (frame),a
    ld  hl,(isr_cnt_lo)
    inc hl
    ld  (isr_cnt_lo),hl
    ld  a,(scroll_div)
    dec a
    ld  (scroll_div),a
    jr  nz,.nos
    ; SPREAD v2: alternate SCROLL_PERIOD / SCROLL_PERIOD+1 frames per line
    ; (4,5,4,5 = 4.5 average, ~12% slower). Pens pace on scroll_tot.
    ld  a,(scroll_alt)
    xor 1
    ld  (scroll_alt),a
    add a,SCROLL_PERIOD
    ld  (scroll_div),a
    ; Paper moves DOWN: R#23--, new blank enters at top.
    ld  a,(scroll_y)
    dec a
    ld  (scroll_y),a
    out (VDPCTRL),a
    ld  a,23+128
    out (VDPCTRL),a
    ld  hl,(scroll_tot_lo)
    inc hl
    ld  (scroll_tot_lo),hl
    ; Ring wrap fix (scroll DOWN):
    ; 1) Clear the line that just LEFT the bottom -> enters hidden band.
    ;    After S'=scroll_y, that line is S'+212 (= old bottom S+211).
    ; 2) Clear the new TOP (S') so nothing can wrap back in.
    ; Never clear tip-zone lines (screen_off 40..71) - that would erase live ink.
    ld  a,(scroll_y)
    ld  (scroll_y_snap),a
    add a,212
    call hmmv_line
    ld  a,(scroll_y)
    call hmmv_line
    jr  .scr_done
.nos:
    ; Residue scrubber (non-scroll frames): re-clear one line of the
    ; no-ink zone screen_off = 212..255 (hidden band) and 0..BAND_TOP-1
    ; (above the drawing band) = SCRUB_N lines. SPREAD v2: plots are gated
    ; to [BAND_TOP, BAND_BOT) so this never touches live ink.
    ld  a,(scrub_k)
    inc a
    cp  SCRUB_N
    jr  c,.sk
    xor a
.sk:
    ld  (scrub_k),a
    add a,212
    ld  b,a
    ld  a,(scroll_y)
    add a,b
    call hmmv_line
.scr_done:
    ld  a,(mus_on)           ; MUSIC: keep the replayer line interrupt at display line
    or  a                    ; MUS_LINE whatever the scroll offset (R#19 = line + R#23)
    jr  z,.nol
    ld  a,(scroll_y)
    add a,MUS_LINE
    out (VDPCTRL),a
    ld  a,19+128
    out (VDPCTRL),a
.nol:
    ld  a,(busy)
    or  a
    jr  nz,.draw
    call plan_next
.draw:
    call stroke_tick
    pop iy
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    xor a
    ld  (in_isr),a
    ; Ack VDP S#0 / R#15=0 so BIOS status IN sees S#0.
    out (VDPCTRL),a
    ld  a,15+128
    out (VDPCTRL),a
    in  a,(VDPCTRL)
    ; F (bit7) set => another VBlank arrived while we were busy = lost frame.
    rlca
    jr  nc,.no_ovr
    ld  hl,(overrun_lo)
    inc hl
    ld  (overrun_lo),hl
.no_ovr:
    ; Do NOT ei — C-BIOS called us under DI and will ei+ret itself.
    ret

save_sp       EQU $C0D0
in_isr        EQU $C0D2
scrub_k       EQU $C0E0
overrun_lo    EQU $C0E1   ; lost VBlanks (ISR overran a frame)
overrun_hi    EQU $C0E2
isr_cnt_lo    EQU $C0E3   ; ISR entries (16-bit)
isr_cnt_hi    EQU $C0E4
isr_stack     EQU $E800
isr_stack_top EQU $F0A0

; Wait until VDP command engine idle (S#2 CE=0). Safe no-op if no cmd running.
vdp_wait_ce:
    ld  a,2
    out (VDPCTRL),a
    ld  a,15+128
    out (VDPCTRL),a
.vw:
    in  a,(VDPCTRL)
    rra
    jr  c,.vw                ; CE set → busy
    xor a
    out (VDPCTRL),a
    ld  a,15+128
    out (VDPCTRL),a          ; restore S#0
    ret



; VDP HMMV clear of one full scanline (A = VRAM Y in page 0) to colour 0.
; CPU cost ~250T; the VDP fills in the background. Waits only for a previous
; command. Plots never target the clear zone (rows 0..39 / 212..255 of the
; ring relative to R#23), so pixel RMW needs no CE wait.
hmmv_line:
    ld  h,a
    call vdp_wait_ce
    ld  a,36             ; R#17 = 36, auto-increment
    out (VDPCTRL),a
    ld  a,17+128
    out (VDPCTRL),a
    ld  c,VDPREGI
    xor a
    out (c),a            ; R#36 DX lo = 0
    out (c),a            ; R#37 DX hi = 0
    out (c),h            ; R#38 DY lo = Y
    out (c),a            ; R#39 DY hi = 0 (page 0)
; [[S7_START]]
    out (c),a            ; R#40 NX lo = 0  (0 => full 512-dot line)
    out (c),a            ; R#41 NX hi = 0
; [[S7_END]]
; [[S5_START]]
    out (c),a            ; R#40 NX lo = 0
    ld  a,1
    out (c),a            ; R#41 NX hi = 1  => 256 dots
    xor a
; [[S5_END]]
    inc a
    out (c),a            ; R#42 NY lo = 1
    dec a
    out (c),a            ; R#43 NY hi = 0
    out (c),a            ; R#44 CLR = 0 (black both nibbles)
    out (c),a            ; R#45 ARG = 0
    ld  a,$C0
    out (c),a            ; R#46 CMD = HMMV
    ret

clear_scanline:
    ; A = vram Y. Save in H before vdp_wait_ce (clobbers A).
    ld  h,a
    call vdp_wait_ce
; [[S7_START]]
    ld  a,h
    rlca
    rlca
    and 3
    out (VDPCTRL),a
    ld  a,14+128
    out (VDPCTRL),a
    xor a
    out (VDPCTRL),a
    ld  a,h
    and $3F
    or  $40
    out (VDPCTRL),a
    ld  b,0
.s7c:
    xor a
    out (VDPDRAM),a
    nop
    nop
    djnz .s7c
    ret
; [[S7_END]]
; [[S5_START]]
    ; Y is in H (A destroyed by vdp_wait_ce). Old ld l,a always cleared Y=0.
    ld  l,h
    ld  h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl              ; HL = Y * 128
    ld  a,h
    rlca
    rlca
    and 3
    out (VDPCTRL),a
    ld  a,14+128
    out (VDPCTRL),a
    ld  a,l
    out (VDPCTRL),a
    ld  a,h
    and $3F
    or  $40
    out (VDPCTRL),a
    ld  b,128
.s5c:
    xor a
    out (VDPDRAM),a
    nop
    nop
    djnz .s5c
    ret
; [[S5_END]]

;----- planner: girl ↔ stem only -------------------------------------------
; phase=0 want girl, phase=1 want stem.
; After a girl finishes, clear_tot = girl_start+GIRL_SPAN+TIP so her head
; leaves the tip zone before the next girl; stems bridge the wait.
plan_next:
    ld  a,(phase)
    or  a
    jr  nz,start_stem
    ; want girl — only if previous top has cleared tip
    ld  hl,(scroll_tot_lo)
    ld  de,(clear_tot_lo)
    or  a
    sbc hl,de
    bit 7,h                    ; IMG2: wrap-safe (scroll_tot wraps after ~20 pictures)
    ret nz                     ; still waiting → idle (one stem only)
    ; fall through to start_girl

start_girl:
    ld  a,PIC_BANK
    ld  (ASC16_B1),a
    ld  (path_bank),a
    ld  hl,$8000
    ld  (path_ptr),hl
    ; origin X: fixed at 8 for EVERY girl. (Following the previous tip moved
    ; girls 2+ to x=24, which pushed the right edge of the wide figure past
    ; the screen and clipped ~150 px.)
    ld  hl,0                  ; IMG2: origin x 0 -> local x 0..255 = screen 0..510 (full width)
    jr  .ox
    ld  hl,(tip_x_lo)
    ; clamp 8..40 undoubled-ish
    ld  a,h
    or  a
    jr  z,.oxok
    ld  hl,24
.oxok:
    ld  a,l
    cp  8
    jr  nc,.ox2
    ld  l,8
.ox2:
    ld  a,l
    cp  40
    jr  c,.ox
    ld  l,24
.ox:
    ld  (origin_x_lo),hl
    ; origin Y = scroll_tot + TIP_PREFER
    ld  hl,(scroll_tot_lo)
    ld  bc,TIP_PREFER
    add hl,bc
    ld  (origin_y_lo),hl
    xor a
    ld  (band_base_lo),a
    ld  (band_base_hi),a
    ld  hl,(scroll_tot_lo)
    ld  (girl_start_lo),hl
    ; Fixed paper anchor: VRAM line at tip zone NOW — never recomputed
    ld  a,(scroll_y)
    add a,TIP_PREFER
    ld  (anchor_page_y),a
    call init_multipen
    xor a
    ld  (skip_count_lo),a
    ld  (skip_count_hi),a
    ld  (plot_count_lo),a
    ld  (plot_count_hi),a
    ld  a,1
    ld  (busy),a
    ld  a,1
    ld  (phase),a        ; next: stem
    ret

start_stem:
    ld  a,STEM_BANK
    ld  (ASC16_B1),a
    ld  (path_bank),a
    ld  a,(rng)
    rrca
    ld  (rng),a
    and 1
    jr  z,.s0
    ld  hl,STEM1_ADDR
    jr  .sp
.s0:
    ld  hl,STEM0_ADDR
.sp:
    ld  (path_ptr),hl
    ; Stem origin: ALWAYS park at far-right undoubled so the vine
    ; runs in the empty margin past hands/skirt (never across figure).
    ; origin 246 + stem local x<=5 → world<=251 → *2 <=502 < 512.
    ld  hl,246
    ld  (origin_x_lo),hl
    ld  hl,(tip_y_lo)
    ld  (origin_y_lo),hl
    ; SPREAD: the lane delays make the girl finish STEM_SHIFT scroll steps
    ; later than in the final, so the stem is anchored STEM_SHIFT lines lower
    ; (virtual earlier spawn) and lands on the same paper spot as the final.
    ld  hl,(scroll_tot_lo)
    ld  de,STEM_SHIFT
    or  a
    sbc hl,de
    ld  (girl_start_lo),hl
    ld  a,(scroll_y)
    add a,TIP_PREFER+STEM_SHIFT
    ld  (anchor_page_y),a
    call init_single
    ld  a,2
    ld  (busy),a
    xor a
    ld  (phase),a        ; next: girl
    ret

init_single:
    ; Treat as 1 pen at offset 0
    ld  a,1
    ld  (cur_pen),a      ; misuse: store num as 1 in a temp — use band
    ; Clear pen0
    ld  hl,pens_base
    ld  b,PEN_STRIDE
    xor a
.clp:
    ld  (hl),a
    inc hl
    djnz .clp
    ; region_off=0, stroke=0
    ; Set a flag: num pens = 1 via cur_pen high? Use phase bit
    ; Store num_pens at $C01B
    ld  a,(path_bank)    ; IMG2: stem pen reads from path_bank
    ld  (pens_base+PEN_BANK),a
    ld  a,1
    ld  ($C01B),a        ; num_pens_live
    ld  (live_pens),a
    xor a
    ld  (cur_pen),a
    ret

init_multipen:
    ld  a,(path_bank)
    ld  (ASC16_B1),a
    ld  hl,(path_ptr)
    ld  a,(hl)
    cp  PEN_MULTI
    jr  z,.mp
    jp  init_single
.mp:
    inc hl
    ld  a,(hl)           ; n
    ld  ($C01B),a
    ld  (live_pens),a
    inc hl
    ld  de,pens_base
    ld  b,a
.iloop:
    push bc
    push de
    xor a
    ld  (de),a           ; stroke_idx lo
    inc de
    ld  (de),a
    inc de
    ld  a,(hl)           ; off lo
    inc hl
    ld  (de),a
    inc de
    ld  a,(hl)
    inc hl
    ld  (de),a
    inc de
    xor a
    ld  c,PEN_STRIDE-4
.z2:
    ld  (de),a
    inc de
    dec c
    jr  nz,.z2
    pop de
    ld  a,(hl)           ; per-lane pacing delay (scroll lines)
    inc hl
    ld  c,(hl)           ; IMG2: lane base bank
    inc hl
    push hl
    ld  hl,PEN_BANK
    add hl,de
    ld  (hl),c
    ld  hl,10
    add hl,de
    ld  (hl),a           ; +10 = delay
    ld  hl,PEN_STRIDE
    add hl,de
    ex  de,hl
    pop hl
    pop bc
    djnz .iloop
    xor a
    ld  (cur_pen),a
    ret

;;----- stroke tick: PIXELS_PER_FRAME steps, RR pens, resumable lines --------
stroke_tick:
    ld  a,(busy)
    or  a
    ret z
    ld  a,(scroll_y)
    ld  (scroll_y_snap),a    ; stable for tip tests this tick
    ld  a,PIXELS_PER_FRAME
    ld  (pix_left),a
    ld  a,250            ; safety iteration cap (prevents ISR hang)
    ld  (tick_guard),a
    xor a
    ld  (idle_run),a
    ld  (defer_mask),a
    ld  (d_def),a
    ld  (d_vert),a
    ld  (d_line),a
    ld  (d_skpx),a
.more:
    ld  a,(tick_guard)
    dec a
    ld  (tick_guard),a
    jr  nz,.go
    ld  hl,(exit_guard)
    inc hl
    ld  (exit_guard),hl
    ret
.go:
    xor a
    ld  (deferred),a
    call plot_one
    ld  a,(busy)
    or  a
    ret z
    ; Early out: once every live pen has deferred in a row nothing can change
    ; until the next scroll step (gates depend only on scroll state), so stop
    ; spinning. Spinning here used to burn several frames per ISR.
    ; Early out: a pen that deferred cannot un-defer until the next scroll
    ; step (gates depend only on scroll state), so it is masked for the rest
    ; of this tick. Stop once every live pen is masked.
    ld  a,(idle_run)         ; = number of masked (deferred) pens
    ld  b,a
    ld  a,(live_pens)
    cp  b
    ret z
    ret c
    ld  a,(pix_left)
    or  a
    ret z
    jr  .more

pix_left   EQU $C0C7
burst      EQU $C0E7
d_def      EQU $C0F0
defer_mask EQU $C0F4
d_vert     EQU $C0F1
d_line     EQU $C0F2
d_skpx     EQU $C0F3
live_pens  EQU $C0E8
exit_guard EQU $C0E9   ; diag: stroke_tick exits by iteration cap (16-bit)
tick_guard EQU $C0C8
deferred   EQU $C0E5
idle_run   EQU $C0E6
scroll_alt EQU $C0F6   ; SPREAD v2: scroll 4/5 alternation
burst_cfg  EQU $C0F5   ; SPREAD: burst for the current line turn

; Budget: line pixels cost 1; successful vertex emit costs 1; pure defer costs 0
; but advances RR so we cannot spin on one pen.
plot_one:
    ld  a,($C01B)
    or  a
    ret z
    ld  a,(cur_pen)
    ld  e,a
    ld  d,0
    ld  hl,pen_bits
    add hl,de
    ld  a,(defer_mask)
    and (hl)
    jp  nz,advance_pen_rr    ; deferred earlier this tick
    call pen_ptr
    ld  de,9
    add hl,de
    ld  a,(hl)
    or  a
    jr  z,.alive
    ld  a,1
    ld  (deferred),a
    ; SPREAD: mask done pen for the rest of the tick (not counted in idle_run,
    ; live_pens already excludes it) so the RR skips it.
    ld  a,(cur_pen)
    ld  e,a
    ld  d,0
    ld  hl,pen_bits
    add hl,de
    ld  a,(defer_mask)
    or  (hl)
    ld  (defer_mask),a
    jp  advance_pen_rr
.alive:
    ; SPREAD: sleeping until wait tot? (wrap-safe signed compare)
    call pen_ptr
    ld  de,PEN_WAIT
    add hl,de
    ld  e,(hl)
    inc hl
    ld  d,(hl)
    ld  hl,(scroll_tot_lo)
    or  a
    sbc hl,de
    bit 7,h
    jr  z,.awake
    call mask_cur_pen
    jp  advance_pen_rr
.awake:
    call pen_ptr
    ld  de,11
    add hl,de
    ld  a,(hl)
    or  a
    jr  z,.need_vert
    ; active line: require budget
    ld  a,(pix_left)
    or  a
    ret z
    ; SPREAD rate limit: a pen on schedule steps LINE_BURST px only on frames
    ; where (isr + pen) % RATE_DIV == 0, then is masked for the tick. A pen
    ; that has fallen CATCH_LAG rows behind its lane's nominal row runs at
    ; full speed (no mask) until it catches up -> never reaches BAND_BOT.
    call pen_lagging
    jr  nc,.full
    ld  a,(isr_cnt_lo)
    ld  hl,cur_pen
    add a,(hl)
    and RATE_DIV-1
    jr  z,.onturn
    call mask_cur_pen
    jp  advance_pen_rr
.onturn:
    ld  a,LINE_BURST
    ld  (burst_cfg),a
    ld  hl,d_line
    inc (hl)
    call line_step_pen
    call mask_cur_pen        ; SPREAD: one turn per pen per tick
    call advance_pen_rr
    ret
.full:
    ld  a,CATCH_BURST
    ld  (burst_cfg),a
    ld  hl,d_line
    inc (hl)
    call line_step_pen
    call advance_pen_rr
    ret

.need_vert:
    call advance_vertex
    ; A consumed (non-deferred) vertex costs VERT_COST budget units so a
    ; vertex-dense line cannot blow one ISR past the frame.
    ld  a,(deferred)
    or  a
    jr  nz,.nv_free
    ld  hl,d_vert
    inc (hl)
    ld  a,(pix_left)
    sub VERT_COST
    jr  nc,.nv_set
    xor a
.nv_set:
    ld  (pix_left),a
.nv_free:
    call advance_pen_rr
    ret

; SPREAD: mark cur_pen as used for this tick (same mask as a defer), so every
; pen advances at most one turn (LINE_BURST px or one vertex) per frame and
; the budget is shared out across all lanes -> many pens move at once.
mask_cur_pen:
    ld  a,(cur_pen)
    ld  e,a
    ld  d,0
    ld  hl,pen_bits
    add hl,de
    ld  a,(defer_mask)
    ld  b,a
    and (hl)
    ret nz                   ; already masked (deferred inside this turn)
    ld  a,b
    or  (hl)
    ld  (defer_mask),a
    ld  hl,idle_run
    inc (hl)
    ret

; SPREAD: C = on schedule, NC = lagging. lag test on the active line's
; current row: (ln_cy - scroll_y) - delay >= BAND_TOP + CATCH_LAG
pen_lagging:
    call pen_ptr
    ld  de,10
    add hl,de
    ld  c,(hl)               ; delay
    inc hl
    inc hl
    inc hl
    inc hl                   ; +14 ln_cy
    ld  a,(scroll_y_snap)
    ld  b,a
    ld  a,(hl)
    sub b                    ; screen_off of pen tip
    sub c
    jr  c,.ok                ; above nominal
    cp  BAND_TOP+CATCH_LAG
    ret                      ; C if < limit (on schedule)
.ok:
    scf
    ret
advance_pen_rr:
    ; SPREAD: skip pens already masked this tick (at most n probes), so the
    ; tick loop does not spin through 7 masked pens per real turn.
    push bc
    push de
    push hl
    ld  a,($C01B)
    ld  b,a
    ld  a,(defer_mask)
    ld  c,a
    ld  a,(cur_pen)
.nx:
    inc a
    ld  hl,$C01B
    cp  (hl)
    jr  c,.nw
    xor a
.nw:
    ld  e,a
    ld  d,0
    ld  hl,pen_bits
    add hl,de
    ld  a,c
    and (hl)
    ld  a,e
    jr  z,.found
    djnz .nx
.found:
    ld  (cur_pen),a
    pop hl
    pop de
    pop bc
    ret

check_all_done:
    ld  a,($C01B)
    ld  b,a
    ld  hl,pens_base
.cd:
    push bc
    push hl
    ld  de,9
    add hl,de
    ld  a,(hl)
    pop hl
    pop bc
    or  a
    ret z                ; still active
    ld  de,PEN_STRIDE
    add hl,de
    djnz .cd
    jp  motif_done

pen_bits:
    db  1,2,4,8,16,32,64,128
pen_ptr:
    push de
    ld  a,(cur_pen)
    ld  l,a
    ld  h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld  de,pens_base
    add hl,de
    pop de
    ret

motif_done:
    xor a
    ld  (busy),a
    ld  a,1
    ld  (have_tip),a
    ; If we just finished a girl (phase already set to want-stem=1),
    ; schedule next girl only after her top scrolls clear of the tip.
    ld  a,(phase)
    cp  1
    ret nz
    ; clear_tot = max(girl_start+GIRL_SPAN+CLEAR_AFTER, scroll_tot+CLEAR_AFTER)
    ld  hl,(girl_start_lo)
    ld  de,GIRL_SPAN
    add hl,de
    ld  de,CLEAR_AFTER
    add hl,de
    ld  (clear_tot_lo),hl
    ld  de,(scroll_tot_lo)
    ld  hl,CLEAR_AFTER
    add hl,de
    ex  de,hl                 ; de = scroll_tot+CLEAR_AFTER
    ld  hl,(clear_tot_lo)
    or  a
    sbc hl,de
    bit 7,h                   ; IMG2: wrap-safe signed compare
    jr  z,.clr_ok             ; computed >= scroll+CLEAR
    ex  de,hl
    ld  (clear_tot_lo),hl     ; use scroll_tot+CLEAR_AFTER
.clr_ok:
    ret


;----- advance_vertex: gate + maybe start resumable line --------------------
; Defer (rewind) when y >= unlock or tip band not ready.
; SKIP permanently when frontier > loc_y+PAST_SLACK (page line already
; reused for loc_y+256 — drawing now would overstrike the head).
advance_vertex:
    call pen_ptr
    ld  a,(hl)
    ld  (tmp_si_lo),a
    inc hl
    ld  a,(hl)
    ld  (tmp_si_hi),a
    inc hl
    ld  a,(hl)
    ld  (tmp_off_lo),a
    inc hl
    ld  a,(hl)
    ld  (tmp_off_hi),a
    ; IMG2: linear L = (path_ptr-$8000) + off + si ; bank = pen_bank + L>>14
    ld  hl,(path_ptr)
    ld  de,$8000
    or  a
    sbc hl,de
    ld  a,(tmp_off_lo)
    ld  e,a
    ld  a,(tmp_off_hi)
    ld  d,a
    add hl,de
    ld  a,(tmp_si_lo)
    ld  e,a
    ld  a,(tmp_si_hi)
    ld  d,a
    add hl,de
    push hl
    call pen_ptr
    ld  de,PEN_BANK
    add hl,de
    ld  e,(hl)               ; lane base bank
    pop hl
    ld  a,h
    rlca
    rlca
    and 3
    add a,e
    ld  (ASC16_B1),a
    ld  a,h
    and $3F
    or  $80
    ld  h,a
    ld  a,(hl)
    cp  PEN_END
    jr  nz,av_got
    call pen_ptr
    ld  de,9
    add hl,de
    ld  a,1
    ld  (hl),a
    ld  a,(live_pens)
    dec a
    ld  (live_pens),a
    ret nz
    jp  motif_done
av_got:
    ld  (pen_mode_tmp),a
    inc hl
    ld  e,(hl)               ; IMG2: 4-byte record mode, x.b, y.w
    ld  d,0
    ld  (loc_x_lo),de
    inc hl
    ld  e,(hl)
    inc hl
    ld  d,(hl)
    ; WAVE v2: loc_x = 2*x.b + (y bit 15) = full 9-bit screen column; y &= $7FFF
    ld  a,d
    rla                      ; CY = y bit 15
    ld  hl,(loc_x_lo)
    adc hl,hl
    ld  (loc_x_lo),hl
    res 7,d
    ld  (loc_y_lo),de
    ; tentatively si += REC_SIZE
    ld  hl,(tmp_si_lo)
    ld  de,REC_SIZE
    add hl,de
    ld  (tmp_si_lo),hl
    call pen_ptr
    ld  a,(tmp_si_lo)
    ld  (hl),a
    inc hl
    ld  a,(tmp_si_hi)
    ld  (hl),a
    ; frontier / unlock
    ld  hl,(scroll_tot_lo)
    ld  de,(girl_start_lo)
    or  a
    sbc hl,de
    ld  (frontier_lo),hl
av_not_past:
    ld  hl,(frontier_lo)
    ld  de,FRONTIER_SLACK
    add hl,de
    ld  (unlock_lo),hl
    ; SPREAD: lane delay -> pen works (delay) lines lower on screen.
    ; if y+delay >= unlock: DEFER — rewind si (never skip undrawn future work)
    call pen_ptr
    ld  de,10
    add hl,de
    ld  e,(hl)
    ld  d,0
    ld  hl,(loc_y_lo)
    add hl,de
    ld  de,(unlock_lo)
    or  a
    sbc hl,de
    jr  c,av_in_band
    ; SPREAD: cache wake-up tot = scroll_tot + (y+delay-unlock) + 1 so the
    ; pen is not re-decoded every frame while it waits for paper.
    ld  de,(scroll_tot_lo)
    add hl,de
    inc hl
    ex  de,hl
    call pen_ptr
    push de
    ld  de,PEN_WAIT
    add hl,de
    pop de
    ld  (hl),e
    inc hl
    ld  (hl),d
    jp  av_rewind
av_tip_defer:
    ; Outside tip band. Below tip+24 → missed the tip (skip). Above tip-8 → wait.
    call compute_screen_off
    cp  BAND_BOT
    jr  nc,av_skip_past
    ; screen_off < TIP-8: paper not yet at tip — rewind and wait
av_rewind:
    ld  a,1
    ld  (deferred),a
    ld  a,(cur_pen)
    ld  e,a
    ld  d,0
    ld  hl,pen_bits
    add hl,de
    ld  a,(defer_mask)
    or  (hl)
    ld  (defer_mask),a
    ld  hl,idle_run
    inc (hl)
    ld  hl,d_def
    inc (hl)
    ld  hl,(tmp_si_lo)
    ld  de,REC_SIZE
    or  a
    sbc hl,de
    ld  (tmp_si_lo),hl
    call pen_ptr
    ld  a,(tmp_si_lo)
    ld  (hl),a
    inc hl
    ld  a,(tmp_si_hi)
    ld  (hl),a
    ret
av_skip_past:
    ; Count skip (target 0 per girl)
    ld  hl,(skip_count_lo)
    inc hl
    ld  (skip_count_lo),hl
    ; si already advanced — drop have_prev + any active line
    call pen_ptr
    ld  de,4
    add hl,de
    xor a
    ld  (hl),a               ; have_prev=0
    ld  de,7                 ; +4+7=+11 ln_active
    add hl,de
    xor a
    ld  (hl),a
    ret
av_in_band:
    ; page_y = (anchor - local_y) & 255
    ld  a,(anchor_page_y)
    ld  l,a
    ld  h,0
    ld  de,(loc_y_lo)
    or  a
    sbc hl,de
    ld  a,l
    ld  (plot_y),a
    ; Only draw in tip band of the scroll window so wrapped page lines
    ; (head vs hips ~256 apart) cannot overstrike uncleared content.
    ; If outside band, REWIND si (do not skip the vertex) and wait for scroll.
    call tip_band_ok
    jp  nz,av_tip_defer
    ; screen x
    ld  hl,(origin_x_lo)
    add hl,hl                ; WAVE v2: screen x = 2*origin + loc_x (loc_x already screen res)
    ld  de,(loc_x_lo)
    add hl,de
; [[S7_START]]
    ld  a,h
    cp  2
    jr  c,av_xok
    ; REJECT out of range — do not clamp (clamp caused left wrap / edge blocks)
    ; clear have_prev so we don't draw wild diagonals to OOB
    call pen_ptr
    ld  de,4
    add hl,de
    xor a
    ld  (hl),a
    ret
av_xok:
; [[S7_END]]
; [[S5_START]]
    ld  a,h
    or  a
    jr  z,av_xok5
    call pen_ptr
    ld  de,4
    add hl,de
    xor a
    ld  (hl),a
    ret
av_xok5:
; [[S5_END]]
    ld  (plot_xlo),hl
    ld  a,(pen_mode_tmp)
    cp  PEN_UP
    jr  nz,av_down
    ; Chop joints emit UP at the previous endpoint. Keep have_prev when
    ; UP lands on prev so the next vertex continues the stroke (no gap).
    call pen_ptr
    push hl
    ld  de,4
    add hl,de
    ld  a,(hl)               ; have_prev
    or  a
    jr  z,.up_clear
    pop hl
    push hl
    ld  de,5
    add hl,de
    ld  e,(hl)
    inc hl
    ld  d,(hl)               ; DE = prev_lx
    ld  hl,(loc_x_lo)
    or  a
    sbc hl,de
    jr  nz,.up_clear_pop
    pop hl
    push hl
    ld  de,7
    add hl,de
    ld  e,(hl)
    inc hl
    ld  d,(hl)               ; DE = prev_ly
    ld  hl,(loc_y_lo)
    or  a
    sbc hl,de
    jr  nz,.up_clear_pop
    pop hl
    ret                      ; same point — keep have_prev
.up_clear_pop:
    pop hl
    push hl
.up_clear:
    pop hl
    ld  de,4
    add hl,de
    xor a
    ld  (hl),a
    ret
av_down:
    cp  $10                  ; IMG3: mode 16..31 = pen down in palette slot (mode & 15)
    jr  c,av_legacy
    and $0F
    jr  av_col
av_legacy:
    cp  PEN_DOWN_M
    jr  z,av_cm
    cp  PEN_DOWN_G
    jr  z,av_cg
    ld  a,COL_DARK
    jr  av_col
av_cm:
    ld  a,COL_MAGENTA
    jr  av_col
av_cg:
    ld  a,COL_GREEN
av_col:
    ld  (pix_color),a
    call pen_ptr
    ld  de,4
    add hl,de
    ld  a,(hl)
    or  a
    jr  z,av_first
    call setup_line_pen  ; sets ln_active; first pixel plotted by steps
    jr  av_save_prev
av_first:
    ld  a,(pix_left)
    or  a
    jr  z,av_save_prev
    dec a
    ld  (pix_left),a
    call tip_band_ok
    jr  nz,av_save_prev
    ld  a,(plot_y)
    ld  b,a
    ld  a,(pix_color)
    call plot_pixel
av_save_prev:
    call pen_ptr
    ld  de,4
    add hl,de
    ld  a,1
    ld  (hl),a
    inc hl
    ld  de,(loc_x_lo)
    ld  (hl),e
    inc hl
    ld  (hl),d
    inc hl
    ld  de,(loc_y_lo)
    ld  (hl),e
    inc hl
    ld  (hl),d
    ld  hl,(origin_x_lo)
    ld  de,(loc_x_lo)
    add hl,de
    ld  (tip_x_lo),hl
    ld  a,(plot_y)
    ld  (tip_y_lo),a
    xor a
    ld  (tip_y_hi),a
    ld  a,1
    ld  (have_tip),a
    ret

;----- setup_line_pen: Bresenham state into current pen, ln_active=1 --------
setup_line_pen:
    call pen_ptr
    ld  (pen_save_setup),hl
    ; prev screen x from pen.prev_lx
    call pen_ptr
    ld  de,5
    add hl,de
    ld  e,(hl)
    inc hl
    ld  d,(hl)
    ld  hl,(origin_x_lo)
    add hl,hl                ; WAVE v2: screen x = 2*origin + prev_lx
    add hl,de
; [[S7_START]]
    ld  a,h
    cp  2
    jr  c,su_x0ok
    ret                  ; prev OOB — skip line
su_x0ok:
; [[S7_END]]
; [[S5_START]]
    ld  a,h
    or  a
    ret nz
; [[S5_END]]
    ld  (seg_x0),hl
    ; prev page y
    call pen_ptr
    ld  de,7
    add hl,de
    ld  e,(hl)
    inc hl
    ld  d,(hl)
    ld  a,(anchor_page_y)
    ld  l,a
    ld  h,0
    or  a
    sbc hl,de
    ld  a,l
    ld  (seg_y0),a
    ld  hl,(plot_xlo)
    ld  (seg_x1),hl
    ld  a,(plot_y)
    ld  (seg_y1),a
    ; dx,sx
    ld  hl,(seg_x1)
    ld  de,(seg_x0)
    or  a
    sbc hl,de
    ld  a,1
    ld  (seg_sx),a
    bit 7,h
    jr  z,su_dx
    ld  a,$FF
    ld  (seg_sx),a
    ld  a,l
    cpl
    ld  l,a
    ld  a,h
    cpl
    ld  h,a
    inc hl
su_dx:
    ld  (seg_dx),hl
    ; dy,sy (signed 8-bit page distance)
    ld  a,(seg_y1)
    ld  e,a
    ld  a,(seg_y0)
    ld  d,a
    ld  a,e
    sub d
    ld  e,1
    bit 7,a
    jr  z,su_dypos
    neg
    ld  e,$FF
su_dypos:
    ld  (seg_dy),a
    ld  a,e
    ld  (seg_sy),a
    ; err = dx - dy (Wikipedia / paper bres_xy with dy_neg=-dy)
    ld  hl,(seg_dx)
    ld  a,(seg_dy)
    ld  e,a
    ld  d,0
    or  a
    sbc hl,de                ; dx - dy
    ld  (seg_err),hl
    ; write into pen struct
    call pen_ptr
    ld  de,11
    add hl,de
    ld  a,1
    ld  (hl),a           ; ln_active
    inc hl
    ld  de,(seg_x0)
    ld  (hl),e           ; cx
    inc hl
    ld  (hl),d
    inc hl
    ld  a,(seg_y0)
    ld  (hl),a           ; cy
    inc hl
    ld  de,(seg_x1)
    ld  (hl),e
    inc hl
    ld  (hl),d
    inc hl
    ld  a,(seg_y1)
    ld  (hl),a
    inc hl
    ld  de,(seg_dx)
    ld  (hl),e
    inc hl
    ld  (hl),d
    inc hl
    ld  a,(seg_dy)
    ld  (hl),a
    inc hl
    ld  a,(seg_sx)
    ld  (hl),a
    inc hl
    ld  a,(seg_sy)
    ld  (hl),a
    inc hl
    ld  de,(seg_err)
    ld  (hl),e
    inc hl
    ld  (hl),d
    inc hl
    ld  a,(pix_color)
    ld  (hl),a
    ; ln_left at +26 = min(255, dx+dy+3)
    inc hl
    ld  hl,(seg_dx)
    ld  a,(seg_dy)
    ld  e,a
    ld  d,0
    add hl,de
    inc hl
    inc hl
    inc hl
    ld  a,h
    or  a
    jr  z,su_left_ok
    ld  a,255
    jr  su_left_set
su_left_ok:
    ld  a,l
    or  a
    jr  nz,su_left_set
    ld  a,1
su_left_set:
    ld  hl,(pen_save_setup)
    ld  de,26
    add hl,de
    ld  (hl),a
    ret

line_step_pen:
    call pen_ptr
    ld  (pen_save),hl
    ld  de,11
    add hl,de
    ld  a,(hl)
    or  a
    ret z
    ; load state
    inc hl
    ld  e,(hl)
    inc hl
    ld  d,(hl)
    ld  (seg_cx),de
    inc hl
    ld  a,(hl)
    ld  (seg_cy),a
    inc hl
    ld  e,(hl)
    inc hl
    ld  d,(hl)
    ld  (seg_x1),de
    inc hl
    ld  a,(hl)
    ld  (seg_y1),a
    inc hl
    ld  e,(hl)
    inc hl
    ld  d,(hl)
    ld  (seg_dx),de
    inc hl
    ld  a,(hl)
    ld  (seg_dy),a
    inc hl
    ld  a,(hl)
    ld  (seg_sx),a
    inc hl
    ld  a,(hl)
    ld  (seg_sy),a
    inc hl
    ld  e,(hl)
    inc hl
    ld  d,(hl)
    ld  (seg_err),de
    inc hl
    ld  a,(hl)
    ld  (pix_color),a
    ld  a,(burst_cfg)        ; SPREAD: LINE_BURST on schedule, CATCH_BURST lagging
    ld  (burst),a
ls_pixel:
    ; safety: ln_left at +26
    ld  hl,(pen_save)
    ld  de,26
    add hl,de
    ld  a,(hl)           ; ln_left
    or  a
    jp  z,ls_force_done  ; exhausted → end segment
    dec a
    ld  (hl),a
    ; plot if in range
    ld  hl,(seg_cx)
; [[S7_START]]
    ld  a,h
    cp  2
    jp  nc,ls_skip_plot
; [[S7_END]]
; [[S5_START]]
    ld  a,h
    or  a
    jp  nz,ls_skip_plot
; [[S5_END]]
    ld  (plot_xlo),hl
    ld  a,(seg_cy)
    ld  (plot_y),a
    ; Tip-band gate on EVERY pixel — mid-screen stroke steps were the
    ; overdraw-on-finished-art bug.
    call tip_band_ok
    jp  nz,ls_skip_oob
    ld  a,(seg_cy)
    ld  b,a
    ld  a,(pix_color)
    call plot_pixel
    ld  a,(pix_left)
    or  a
    jp  z,ls_store_only
    dec a
    ld  (pix_left),a
    jr  ls_skip_plot
ls_skip_oob:
    ld  hl,d_skpx
    inc (hl)
ls_skip_plot:
    ; endpoint?
    ld  hl,(seg_cx)
    ld  de,(seg_x1)
    or  a
    sbc hl,de
    jp  nz,ls_step
    ld  a,(seg_cy)
    ld  e,a
    ld  a,(seg_y1)
    cp  e
    jp  z,ls_done
ls_step:
    ; Wikipedia Bresenham (matches paper bres_xy): err=dx-dy.
    ; e2=2*err; if e2>=-dy: err-=dy,x+=sx; if e2<=dx: err+=dx,y+=sy.
    ; One plot per iteration (already done above). Screen-space X (doubled).
    ld  hl,(seg_err)
    add hl,hl
    ld  (seg_e2),hl
    ; X if e2 + dy >= 0
    ld  hl,(seg_e2)
    ld  a,(seg_dy)
    ld  e,a
    ld  d,0
    add hl,de
    bit 7,h
    jr  nz,ls_nox
    ld  hl,(seg_err)
    ld  a,(seg_dy)
    ld  e,a
    ld  d,0
    or  a
    sbc hl,de
    ld  (seg_err),hl
    ld  hl,(seg_cx)
    ld  a,(seg_sx)
    ld  e,a
    ld  d,0
    bit 7,a
    jr  z,.sxa
    dec d
.sxa:
    add hl,de
    ld  (seg_cx),hl
ls_nox:
    ; Y if e2 - dx <= 0
    ld  hl,(seg_e2)
    ld  de,(seg_dx)
    or  a
    sbc hl,de
    jr  z,ls_do_y
    jp  p,ls_noy
ls_do_y:
    ld  hl,(seg_err)
    ld  de,(seg_dx)
    add hl,de
    ld  (seg_err),hl
    ld  a,(seg_cy)
    ld  e,a
    ld  a,(seg_sy)
    add a,e
    ld  (seg_cy),a
ls_noy:
    ; Burst: keep stepping this pen (state already in RAM temps) instead of
    ; reloading/saving 15 bytes of pen state for every single pixel.
    ld  a,(burst)
    dec a
    ld  (burst),a
    jr  z,ls_store_only
    ld  a,(pix_left)
    or  a
    jp  nz,ls_pixel
ls_store_only:
    ld  hl,(pen_save)
    ld  de,12
    add hl,de
    ld  de,(seg_cx)
    ld  (hl),e
    inc hl
    ld  (hl),d
    inc hl
    ld  a,(seg_cy)
    ld  (hl),a
    ld  hl,(pen_save)
    ld  de,23
    add hl,de
    ld  de,(seg_err)
    ld  (hl),e
    inc hl
    ld  (hl),d
    ret
ls_force_done:
ls_done:
    ld  hl,(pen_save)
    ld  de,11
    add hl,de
    xor a
    ld  (hl),a
    ret

pen_save EQU $C0D4
pen_save_setup EQU $C0D6

seg_x0  EQU $C1E2
seg_y0  EQU $C1E4
seg_x1  EQU $C1E5
seg_y1  EQU $C1E7
seg_cx  EQU $C1E8
seg_cy  EQU $C1EA
seg_dx  EQU $C1EB
seg_dy  EQU $C1ED
seg_err EQU $C1EE
seg_e2  EQU $C1F0
seg_sx  EQU $C1F2
seg_sy  EQU $C1F3
seg_left EQU $C1F4

pen_mode_tmp EQU $C0B0
loc_x_lo     EQU $C0B1
loc_x_hi     EQU $C0B2
loc_y_lo     EQU $C0B3
loc_y_hi     EQU $C0B4
world_y_lo   EQU $C0B5
world_y_hi   EQU $C0B6
tmp_si_lo  EQU $C0C0
tmp_si_hi  EQU $C0C1
tmp_off_lo EQU $C0C2
tmp_off_hi EQU $C0C3


; Z=1 if plot_y is in the tip / just-below-bottom draw band.
; screen_off=(plot_y-scroll_y)&255 must be in [TIP_PREFER-24, 224).
; That is the lowest visible tip through the freshly cleared line (scroll+211).
; Mid-screen and top (where ly and ly+256 share a page line) are rejected so
; the head cannot overstrike uncleared hips; clear_scanline owns those lines first.
; A = (plot_y - scroll_y) & 255
compute_screen_off:
    ld  a,(plot_y)
    ld  l,a
    ld  a,(scroll_y_snap)
    ld  h,a
    ld  a,l
    sub h
    ret

tip_band_ok:
    ; ONLY the tip zone — never mid/lower finished paper.
    ; Window: [TIP-8, TIP+24) = [40, 72). Catch-up below tip looked like
    ; drawing over the finished figure.
    call compute_screen_off
    cp  BAND_BOT             ; SPREAD: tall band
    jr  nc,.bad
    cp  BAND_TOP
    jr  c,.bad
    xor a
    ret
.bad:
    ld  a,1
    or  a
    ret

plot_pixel:
    ; A=color, B=Y, plot_xlo/hi=X
    ; RMW must not race a VDP command (lost neighbour nibble → dashed lines).
    ld  (pix_color),a
    ld  a,b
    ld  (plot_y),a
    push hl
    ld  hl,(plot_count_lo)
    inc hl
    ld  (plot_count_lo),hl
    pop hl
; [[S7_START]]
    ld  a,(plot_y)
    ld  h,a
    ld  a,(plot_xhi)
    ld  d,a
    ld  a,(plot_xlo)
    srl d
    rr  a
    ld  l,a              ; L = X/2, H = Y
    ld  a,h
    rlca
    rlca
    and 3
    out (VDPCTRL),a
    ld  a,14+128
    out (VDPCTRL),a
    ld  a,l
    out (VDPCTRL),a
    ld  a,h
    and $3F
    out (VDPCTRL),a
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    in  a,(VDPDRAM)
    ld  e,a
    ld  a,(plot_xlo)
    and 1
    jr  nz,.odd7
    ld  a,e
    and $0F
    ld  e,a
    ld  a,(pix_color)
    and $0F
    add a,a
    add a,a
    add a,a
    add a,a
    or  e
    ld  e,a
    jr  .wr7
.odd7:
    ld  a,e
    and $F0
    ld  e,a
    ld  a,(pix_color)
    and $0F
    or  e
    ld  e,a
.wr7:
    ld  a,h
    rlca
    rlca
    and 3
    out (VDPCTRL),a
    ld  a,14+128
    out (VDPCTRL),a
    ld  a,l
    out (VDPCTRL),a
    ld  a,h
    and $3F
    or  $40
    out (VDPCTRL),a
    nop
    nop
    nop
    nop
    nop
    nop
    ld  a,e
    out (VDPDRAM),a
    ret
; [[S7_END]]
; [[S5_START]]
    ld  h,0
    ld  l,b
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld  a,(plot_xlo)
    srl a
    ld  e,a
    ld  d,0
    add hl,de
    ld  a,h
    ld  (tmp_addr_hi),a
    ld  a,l
    ld  (tmp_addr_lo),a
    ld  a,h
    rlca
    rlca
    and 3
    out (VDPCTRL),a
    ld  a,14+128
    out (VDPCTRL),a
    ld  a,l
    out (VDPCTRL),a
    ld  a,h
    and $3F
    out (VDPCTRL),a
    nop
    nop
    nop
    nop
    nop
    nop
    in  a,(VDPDRAM)
    ld  e,a
    ld  a,(plot_xlo)
    and 1
    jr  nz,.odd5
    ld  a,e
    and $0F
    ld  e,a
    ld  a,(pix_color)
    and $0F
    add a,a
    add a,a
    add a,a
    add a,a
    or  e
    ld  e,a
    jr  .wr5
.odd5:
    ld  a,e
    and $F0
    ld  e,a
    ld  a,(pix_color)
    and $0F
    or  e
    ld  e,a
.wr5:
    ld  a,(tmp_addr_hi)
    ld  h,a
    ld  a,(tmp_addr_lo)
    ld  l,a
    ld  a,h
    rlca
    rlca
    and 3
    out (VDPCTRL),a
    ld  a,14+128
    out (VDPCTRL),a
    ld  a,l
    out (VDPCTRL),a
    ld  a,h
    and $3F
    or  $40
    out (VDPCTRL),a
    nop
    nop
    nop
    nop
    nop
    nop
    ld  a,e
    out (VDPDRAM),a
    ret
; [[S5_END]]

tmp_addr_lo EQU $C0C4
tmp_addr_hi EQU $C0C5


