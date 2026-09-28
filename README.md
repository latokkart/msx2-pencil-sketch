# MSX2 Pencil Sketch (Screen 7)

A pencil-sketch cartridge for MSX2 computers, inspired by the drawing scroll in *Baltak Rampage*. Eight pens draw a line picture at the same time, spread across the screen, while the paper scrolls down. The finished drawing slides out at the bottom and the next one starts. It loops forever.

![Pens drawing](media/drawing.png)

## Download

`rom/pencil_sketch_s7.rom` (also attached to the latest release): 256KB, ASCII16 mapper.

## Running it

- **Emulator:** `openmsx -machine C-BIOS_MSX2 -cart rom/pencil_sketch_s7.rom -romtype ASCII16`
- **Real hardware:** an MSX2 with a flash cartridge that supports 256KB ASCII16 ROMs (for example Carnivore2 or MegaFlashROM SCC+). Tested on a real MSX.

## How it looks

- Screen 7 (512×212, 16 colours), white lines on black.
- 8 pens, each working in its own lane across the width at a slightly different height.
- Drawing happens in the upper half of the screen, so each finished part stays visible for about 8 seconds before scrolling off.
- About 55.6 seconds per picture at 60 Hz, with no dropped frames.
- Leftover pixels are cleared continuously, so no residue builds up.

## Source

- `src/engine_s7.asm`: Z80 engine (sjasmplus). It handles the scroll interrupt, pen scheduling, line drawing and screen clean-up.
- `src/strokes.inc`: the stroke data for the current picture.
- `tools/`: Python scripts that trace a line drawing into strokes, split them into pen lanes (`gen_spread.py`), and build the ROM (`build_spread.py`).

Built with sjasmplus. The build scripts expect the original project layout, so treat them as a reference.
