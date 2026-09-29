# MSX2 Pencil Sketch (Screen 7)

A pencil-sketch cartridge for MSX2 computers, inspired by the drawing scroll in *Baltak Rampage*. Eight pens draw a line picture at the same time, spread across the screen, while the paper scrolls down. The finished drawing slides out at the bottom and the next one starts. It loops forever.

![Pens drawing](media/drawing.png)

## What's new in v1.2: "Sunflower column with MSX-MUSIC"

The v1.1 Sunflower column, now with background music.

- **Music:** "Song in B", composed by Anne de Raad (Latok), 2019. It is a MoonBlaster 1.4 song played by the original MoonBlaster 1.4 replayer.
- **MSX-MUSIC (OPLL) only:** 6 FM voices plus the OPLL rhythm section (bass drum, hi-hat, cymbal). There is no MSX-AUDIO support and the PSG is not used.
- **Starts with the intro:** the music begins at the black lead-in of the power-on intro and plays without a break through the title fades, the screen clear and the drawing. It loops about every 58 seconds (496 steps at tempo 7, 60 Hz).
- **Auto-detect:** built-in MSX-MUSIC is used if present; otherwise an FM-PAC (or compatible) cartridge is found and switched on. Without an FM chip the cartridge runs silently.
- **Drawing timing unchanged:** the picture, pace and frame timing are the same as v1.1 (no dropped frames).
- **ROM:** `rom/sketch_music_s7.rom`, 256KB, ASCII16 mapper, sha256 `7cd1ae5d540f8aff847b132c802ef86fb49d54868cfd5f40d0b5f511a8903dbe`.
- **Testing:** v1.2 is tested in openMSX only: C-BIOS MSX2 with an emulated FM-PAC, C-BIOS MSX2+ with built-in MSX-MUSIC, and without FM. The music register writes match an independent MoonBlaster replayer frame for frame; see `music/verify/verify_v1.2.txt`. The real FM-PAC ROM was not available, so an emulated FM-PAC with a stand-in ROM was used. It has not been tested on real hardware yet.

## What's new in v1.1: "Sunflower column"

![Source and trace side by side](media/column_side_by_side.png)

- **New picture:** a tall line-art column with a sunflower, peonies and three anime girl portraits, the last one seated and hugging her knees.
- **Power-on intro:** a title card ("Latok presents ~Sketch~") fades in, holds, and fades out before the drawing starts.
- **7 greys on black:** brightest for the outlines of faces, hair and flowers, mid greys for petals, clothing and inner lines, dark greys (down to RGB 2,2,2) for fine detail such as the sunflower centre, hatching and sparkles. The stem interlude between pictures stays grey.
- **Full 512-pixel width:** the engine now supports 9-bit x coordinates, so the picture uses the whole Screen 7 width. The picture is 512×1196 pixels, cropped to the content and scaled without distortion (Screen 7 pixels are twice as tall as wide).
- **Cleaner eyes and smoother lines:** single smoothed strokes with doubled lines merged; eyes are drawn from the source at screen resolution.
- **Timing:** about 108 seconds per pass (1439 scroll lines at 4.5 frames each, 60 Hz); the figure is drawn in about 93 s of each pass. The same 8-pen pace and density limiter as v1.0 are used, with the wrap-safe counter fix.
- **ROM:** `rom/sketch_column_s7.rom`, 256KB, ASCII16 mapper, sha256 `4e01b1b4b9a3d7237ebfa0ec27ad5722a7bcb469752bc94b15ebc8af2a8dd70a`.
- **Testing:** v1.1 is tested in openMSX (C-BIOS MSX2) only: 2 full passes with no dropped frames, no skipped steps, an exact pixel match with the trace and no residue (see `column/verify/verify_v1.1.txt`). It has not been tested on real hardware yet. Earlier builds ran on a real MSX2.

![Screen during drawing](media/column_screen.png) ![Intro](media/intro.png)

## Download

- `rom/sketch_music_s7.rom` (v1.2, Sunflower column with MSX-MUSIC): 256KB, ASCII16 mapper.
- `rom/sketch_column_s7.rom` (v1.1, Sunflower column): 256KB, ASCII16 mapper.
- `rom/pencil_sketch_s7.rom` (v1.0 framework): 256KB, ASCII16 mapper.

Each is also attached to its GitHub release.

## Running it

- **Emulator:** `openmsx -machine C-BIOS_MSX2 -cart rom/sketch_column_s7.rom -romtype ASCII16` (or `rom/pencil_sketch_s7.rom` for v1.0)
- **Emulator with music (v1.2):** `openmsx -machine C-BIOS_MSX2+ -cart rom/sketch_music_s7.rom -romtype ASCII16` (built-in MSX-MUSIC), or an MSX2 machine with an FM-PAC extension (`-ext fmpac`, needs the FM-PAC system ROM)
- **Real hardware:** an MSX2 with a flash cartridge that supports 256KB ASCII16 ROMs (for example Carnivore2 or MegaFlashROM SCC+). v1.0 was tested on a real MSX; v1.1 is emulator-tested only so far.

## How it looks (v1.0)

- Screen 7 (512×212, 16 colours), white lines on black.
- 8 pens, each working in its own lane across the width at a slightly different height.
- Drawing happens in the upper half of the screen, so each finished part stays visible for about 8 seconds before scrolling off.
- About 55.6 seconds per picture at 60 Hz, with no dropped frames.
- Leftover pixels are cleared continuously, so no residue builds up.

## Source (v1.2)

Everything needed to rebuild `rom/sketch_music_s7.rom` byte for byte. It reuses the v1.1 picture data in `column/` and `intro/`. Run from the repository root; needs Python 3 and sjasmplus:

```
python3 music/adapt_mbplay.py   # optional: third_party/moonblaster/mbplay_original.src -> music/mbplay_rom.asm
python3 music/build_mus.py      # -> music/sketch_music_s7.rom (checks that only pages 0 and 5 differ from v1.1)
```

- `music/engine_mus.asm`, `music/intro_mus.asm`: the v1.1 engine and intro with the music hooks added.
- `music/music_glue.asm`: FM detection (the "OPLL" signature; FM-PAC enabled via 7FF6h), start-up, and replayer timing (VBLANK during the intro, a display-line interrupt during drawing).
- `music/mbplay_rom.asm`: the MoonBlaster 1.4 replayer adapted for the ROM by `music/adapt_mbplay.py`. Only integration changes: no file header/ORG, no mapper paging, no hook install, MSX-AUDIO output disabled. The FM, rhythm and PSG-drum code is unchanged.
- `music/song.mbm`: the song.
- `third_party/moonblaster/`: the original replayer source and the MoonSoft readmes (see Credits).

## Source (v1.1)

Everything needed to rebuild `rom/sketch_column_s7.rom` byte for byte. Run from the repository root; needs Python 3 with numpy, Pillow, scipy and scikit-image, plus sjasmplus:

```
python3 column/trace_col.py    # source.jpg + params.json -> paths.json (strokes, tones, load budget)
python3 column/gen_col.py      # paths.json -> pic.inc, layout.json (8 pen lanes, banked records)
python3 column/build_col.py    # engine + intro + picture + palette -> column/sketch_column_s7.rom
column/verify/runtest.sh final 3100   # optional: 2-pass openMSX check (writes ~400MB of dumps to column/verify/out)
```

- `column/engine_col.asm`: the Z80 engine for v1.1: tonal pens (palette slots), 9-bit x, wrap-safe counters.
- `column/palette.json`: the 7-grey palette. `column/params.json`: trace settings.
- `column/source.jpg`: the source line drawing. `column/stems_src.inc`: stem interlude strokes.
- `intro/`: the power-on intro (`intro.asm`, data generated by `make_title.py` and `make_intro_data.py`; `make_title.py` needs the EB Garamond fonts, which are not included).
- `column/verify/`: openMSX dump script and checks (residue audit, trace match, pass timing, intro timing).
- `tools/preprocess_screen.py` is shared with v1.0.

## Source (v1.0)

- `src/engine_s7.asm`: Z80 engine (sjasmplus). It handles the scroll interrupt, pen scheduling, line drawing and screen clean-up.
- `src/strokes.inc`: the stroke data for the current picture.
- `tools/`: Python scripts that trace a line drawing into strokes, split them into pen lanes (`gen_spread.py`), and build the ROM (`build_spread.py`).

Built with sjasmplus. The build scripts expect the original project layout, so treat them as a reference.

## Credits

- **Music:** "Song in B", composed by Anne de Raad (Latok), 2019, the author of this repository. Title and year as stored in `music/song.mbm`.
- **Replayer:** MoonBlaster 1.4 replayer by Remco Schrijvers / MoonSoft, with MSX compatibility fixes by Albert Beevendorp (BiFi), from the official MoonBlaster 1.4 development package. It is used under the terms in the included readmes (`third_party/moonblaster/`). The 1997 readme allows use of the sources for new public-domain music programs; a note dated July 1, 2012 says the restrictions on using the sources were removed. This is not a formal open-source license. The replayer (`third_party/moonblaster/mbplay_original.src` and the adapted `music/mbplay_rom.asm`) remains under MoonSoft's terms and is not covered by any license of this repository's own code.
