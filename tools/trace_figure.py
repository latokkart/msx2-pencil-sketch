#!/usr/bin/env python3
"""High-fidelity figure tracer → multipen stroke data (16-bit local Y).

Default: NUM_PENS=4, multipen header, feet-first bands of BAND_H local lines.
Verify image: reference and trace at the SAME displayed size/aspect.
"""
from __future__ import annotations
import argparse, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageDraw, ImageOps
from skimage.filters import threshold_local
from skimage.morphology import skeletonize, closing, disk, remove_small_objects
from skimage.measure import approximate_polygon
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
DARK, UP, MAG, GRN, END, MULTI = 0, 1, 2, 3, 255, 0xFE
NUM_PENS = 4
BAND_H = 112  # <=128

def load_preprocess(path: Path) -> np.ndarray:
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    im = Image.alpha_composite(bg, im).convert("L")
    im = ImageEnhance.Contrast(im).enhance(2.6)
    im = ImageOps.autocontrast(im)
    im = ImageEnhance.Sharpness(im).enhance(1.8)
    arr = np.asarray(im).astype(np.float32)
    thr = threshold_local(arr, block_size=25, offset=5)
    binary = (arr < thr) & (arr < 210)
    binary = closing(binary, disk(1))
    # remove speckles but keep fine face/hand detail
    binary = remove_small_objects(binary, min_size=12)
    # drop faint vertical guide lines: long thin vertical components
    labeled, n = ndi.label(binary)
    keep = np.zeros_like(binary)
    for i in range(1, n + 1):
        ys, xs = np.where(labeled == i)
        if len(xs) < 12:
            continue
        h = ys.max() - ys.min() + 1
        w = xs.max() - xs.min() + 1
        # kill tall hairline guides (very thin & very tall)
        if w <= 2 and h > 80 and len(xs) < h * 2.5:
            continue
        keep[labeled == i] = True
    return keep

def skeleton_paths(skel: np.ndarray, min_len=4):
    H, W = skel.shape
    neigh = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
    def nbrs(y, x):
        out = []
        for dy, dx in neigh:
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and skel[ny, nx]:
                out.append((ny, nx))
        return out
    coords = list(zip(*np.where(skel)))
    if not coords:
        return []
    deg = {p: len(nbrs(*p)) for p in coords}
    visited = set()
    paths = []

    def walk(start, first_step=None):
        path = [start]
        visited.add(start)
        prev, cur = None, start
        if first_step is not None:
            path.append(first_step)
            visited.add(first_step)
            prev, cur = start, first_step
        while True:
            opts = [n for n in nbrs(*cur) if n != prev and n not in visited]
            if not opts:
                # allow revisit junction once to branch? stop.
                break
            if len(opts) == 1:
                nxt = opts[0]
            else:
                if prev is None:
                    nxt = opts[0]
                else:
                    vx, vy = cur[1] - prev[1], cur[0] - prev[0]
                    best, bs = -1e9, None
                    for n in opts:
                        wx, wy = n[1] - cur[1], n[0] - cur[0]
                        sc = vx * wx + vy * wy
                        if sc > best:
                            best, bs = sc, n
                    nxt = bs
            path.append(nxt)
            visited.add(nxt)
            if deg[nxt] != 2 and len(path) > 2:
                break
            prev, cur = cur, nxt
        return path

    for ep in sorted([p for p, d in deg.items() if d == 1], key=lambda p: (p[0], p[1])):
        if ep not in visited:
            paths.append(walk(ep))
    changed = True
    while changed:
        changed = False
        for j in sorted([p for p, d in deg.items() if d >= 3], key=lambda p: (p[0], p[1])):
            for n in nbrs(*j):
                if n not in visited:
                    paths.append(walk(j, n))
                    changed = True
    leftover = sorted(p for p in coords if p not in visited)
    while leftover:
        paths.append(walk(leftover[0]))
        leftover = sorted(p for p in coords if p not in visited)
    return [p for p in paths if len(p) >= min_len]

def simplify(paths, tol):
    out = []
    for path in paths:
        # path is (row,col)=(y,x) image space
        pts = np.array([(p[1], p[0]) for p in path], dtype=float)  # x,y
        if len(pts) < 3:
            out.append([(float(x), float(y)) for x, y in pts])
            continue
        approx = approximate_polygon(pts, tolerance=tol)
        if len(approx) < 2:
            approx = pts
        out.append([(float(x), float(y)) for x, y in approx])
    return out

def scale_to_height(paths, target_h, screen, max_doubled_w=500, max_s5_w=250):
    """Fit target height; also keep on-screen width (S7: doubled <= max_doubled_w)."""
    xs = [p[0] for s in paths for p in s]
    ys = [p[1] for s in paths for p in s]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    bw, bh = maxx - minx, maxy - miny
    if bh < 1:
        bh = 1
    if bw < 1:
        bw = 1
    scale = target_h / bh
    if screen == "s7":
        max_w = max_doubled_w / 2.0  # undoubled local
        if bw * scale > max_w:
            # anisotropic: keep height, compress X
            sx = max_w / bw
            sy = scale
            out = []
            for s in paths:
                out.append([((x - minx) * sx, (y - miny) * sy) for x, y in s])
            return out, (sx, sy)
    else:
        if bw * scale > max_s5_w:
            scale = max_s5_w / bw
    out = []
    for s in paths:
        out.append([((x - minx) * scale, (y - miny) * scale) for x, y in s])
    return out, scale

def invert_y_bottom(paths):
    ys = [p[1] for s in paths for p in s]
    ymax = max(ys)
    return [[(x, ymax - y) for x, y in s] for s in paths]

def cluster_pens(paths, k=NUM_PENS):
    """Spatial k-means on path centroids (x,y)."""
    if not paths:
        return []
    cents = np.array([[np.mean([p[0] for p in s]), np.mean([p[1] for p in s])] for s in paths])
    # init: spread by x within lower/upper halves for legs vs body
    rng = np.random.default_rng(42)
    centers = cents[rng.choice(len(cents), size=min(k, len(cents)), replace=False)].astype(float)
    while len(centers) < k:
        centers = np.vstack([centers, cents.mean(axis=0)])
    labels = np.zeros(len(paths), dtype=int)
    for _ in range(20):
        d = ((cents[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = d.argmin(axis=1)
        for j in range(k):
            memb = cents[labels == j]
            if len(memb):
                centers[j] = memb.mean(axis=0)
    regions = [[] for _ in range(k)]
    for i, s in enumerate(paths):
        regions[labels[i]].append(s)
    # order regions by mean-y ascending (feet first) for band scheduling;
    # within region NN order from bottom
    def cy(plist):
        if not plist:
            return 0
        return float(np.mean([p[1] for s in plist for p in s]))
    order = sorted(range(k), key=lambda r: cy(regions[r]))
    ordered = []
    for r in order:
        plist = regions[r][:]
        if not plist:
            ordered.append([])
            continue
        used = [False] * len(plist)
        start = min(range(len(plist)), key=lambda i: min(p[1] for p in plist[i]))
        seq = [plist[start]]
        used[start] = True
        cur = plist[start][-1]
        for _ in range(len(plist) - 1):
            best, bi, rev = 1e18, None, False
            for i, s in enumerate(plist):
                if used[i]:
                    continue
                d0 = math.hypot(cur[0] - s[0][0], cur[1] - s[0][1])
                d1 = math.hypot(cur[0] - s[-1][0], cur[1] - s[-1][1])
                if d0 < best:
                    best, bi, rev = d0, i, False
                if d1 < best:
                    best, bi, rev = d1, i, True
            if bi is None:
                break
            s = plist[bi][::-1] if rev else plist[bi]
            seq.append(s)
            used[bi] = True
            cur = s[-1]
        ordered.append(seq)
    return ordered

SEG_H = 12  # chop paths into ~SEG_H-tall pieces for frontier pacing

def _chop_path_xy(path, mode, seg_h=SEG_H):
    """Split a polyline into short Y-monotone chunks (max height seg_h)."""
    if len(path) < 2:
        return []
    if path[0][1] > path[-1][1]:
        path = list(reversed(path))
    chunks = []
    cur = [path[0]]
    y_lo = y_hi = path[0][1]
    for pt in path[1:]:
        x, y = pt
        # break on Y drop (non-monotone) or span too tall
        if y < cur[-1][1] - 1 or (max(y_hi, y) - min(y_lo, y) > seg_h and len(cur) >= 2):
            chunks.append((mode, cur))
            # Duplicate joint so next segment's first stroke starts at previous end
            # (PEN_UP alone would leave a 1px gap at every chop).
            cur = [cur[-1], pt]
            y_lo = min(cur[0][1], y)
            y_hi = max(cur[0][1], y)
        else:
            cur.append(pt)
            y_lo = min(y_lo, y)
            y_hi = max(y_hi, y)
    if len(cur) >= 2:
        chunks.append((mode, cur))
    elif cur and chunks:
        # single leftover point: append to previous if close
        chunks[-1][1].append(cur[0])
    return chunks

def colorize_regions(region_paths):
    """Per-pen streams: short Y-monotone segments, ordered by min local_y (feet first).

    Chopping to ~SEG_H lines lets frontier pacing release work in step with scroll
    instead of blocking a pen on a tall stroke while later low-Y work goes PAST.
    """
    streams = []
    n = len(region_paths)
    for ri, region in enumerate(region_paths):
        paths = [p for p in region if len(p) >= 2]
        segs = []  # (min_y, mode, xy_list)
        for pi, path in enumerate(paths):
            mode = MAG if (ri == n - 1 and pi % 4 == 1) else DARK
            for m, xy in _chop_path_xy(path, mode):
                ys = [p[1] for p in xy]
                segs.append((min(ys), m, xy))
        segs.sort(key=lambda s: s[0])
        pts = []
        for _ymin, mode, xy in segs:
            x0, y0 = xy[0]
            pts.append((UP, x0, y0))
            pts.append((mode, x0, y0))
            for x, y in xy[1:]:
                pts.append((mode, x, y))
        streams.append(pts)
    return streams

def emit_stream_16(pts):
    """5-byte records: mode, xlo, xhi, ylo, yhi."""
    raw = []
    for mode, x, y in pts:
        xi = int(round(x))
        yi = int(round(y))
        xi = max(0, min(65535, xi))
        yi = max(0, min(65535, yi))
        raw.extend([mode & 255, xi & 255, (xi >> 8) & 255, yi & 255, (yi >> 8) & 255])
    raw.extend([END, 0, 0, 0, 0])
    return raw

def emit_multipen(streams):
    n = len(streams)
    assert n == NUM_PENS or n > 0
    while len(streams) < NUM_PENS:
        streams.append([])
    streams = streams[:NUM_PENS]
    bodies = [emit_stream_16(s) for s in streams]
    hdr_len = 2 + NUM_PENS * 2
    raw = [MULTI, NUM_PENS]
    cursor = hdr_len
    for b in bodies:
        raw.extend([cursor & 255, (cursor >> 8) & 255])
        cursor += len(b)
    for b in bodies:
        raw.extend(b)
    return raw

def format_db(raw):
    lines = []
    for i in range(0, len(raw), 12):
        chunk = raw[i:i + 12]
        lines.append("    db " + ", ".join(str(b) for b in chunk))
    return "\n".join(lines)

def render_verify(region_paths, ref_path, out_png, screen):
    """Side-by-side at SAME displayed size and aspect.
    For G6: stretch reference width ×2 (or draw trace with x×2) so both match
    the on-screen pixel aspect after runtime X-doubling.
    """
    ref = Image.open(ref_path).convert("RGBA")
    bg = Image.new("RGBA", ref.size, (255, 255, 255, 255))
    ref = Image.alpha_composite(bg, ref).convert("RGB")
    all_pts = [p for reg in region_paths for s in reg for p in s]
    if not all_pts:
        return
    maxx = max(p[0] for p in all_pts)
    maxy = max(p[1] for p in all_pts)
    DISP_H = 560
    # Build trace at on-screen aspect (x*2 for s7)
    scale_x = 2.0 if screen == "s7" else 1.0
    tw = int(maxx * scale_x) + 20
    th = int(maxy) + 20
    trace = Image.new("RGB", (tw, th), (245, 240, 230))
    draw = ImageDraw.Draw(trace)
    cols = [(30, 30, 35), (200, 40, 160), (40, 140, 70), (50, 90, 180)]
    for ri, reg in enumerate(region_paths):
        col = cols[ri % 4]
        for s in reg:
            if len(s) < 2:
                continue
            xy = [(x * scale_x + 10, (maxy - y) + 10) for x, y in s]
            draw.line(xy, fill=col, width=1)
    # Stretch reference to same aspect as on-screen G6 figure
    if screen == "s7":
        ref_asp = ref.resize((ref.width * 2, ref.height), Image.Resampling.NEAREST)
    else:
        ref_asp = ref
    # Scale both to same height
    ref_disp = ref_asp.copy(); ref_disp.thumbnail((1000, DISP_H))
    trace_disp = trace.copy(); trace_disp.thumbnail((1000, DISP_H))
    # Force exact same height
    def fit_h(im, h):
        w = max(1, int(im.width * h / im.height))
        return im.resize((w, h), Image.Resampling.BILINEAR)
    H = min(ref_disp.height, trace_disp.height)
    ref_disp = fit_h(ref_disp, H)
    trace_disp = fit_h(trace_disp, H)
    canvas = Image.new("RGB", (ref_disp.width + trace_disp.width + 30, H + 36), (255, 255, 255))
    canvas.paste(ref_disp, (10, 28))
    canvas.paste(trace_disp, (ref_disp.width + 20, 28))
    d = ImageDraw.Draw(canvas)
    d.text((10, 6), "reference (G6 aspect)", fill=(0, 0, 0))
    d.text((ref_disp.width + 20, 6), "trace (same size/aspect)", fill=(0, 0, 0))
    canvas.save(out_png)
    print(f"Wrote {out_png} ({canvas.size[0]}x{canvas.size[1]})")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=Path)
    ap.add_argument("--height", type=float, default=450)
    ap.add_argument("--screen", choices=["s7", "s5"], default="s7")
    ap.add_argument("--pens", type=int, default=NUM_PENS)
    ap.add_argument("--tol", type=float, default=0.45)
    ap.add_argument("--out-name", default="girl")
    args = ap.parse_args()

    print("preprocess…")
    binary = load_preprocess(args.image)
    skel = skeletonize(binary)
    print(f"skel pixels {int(skel.sum())}")
    raw_paths = skeleton_paths(skel, min_len=4)
    print(f"raw paths {len(raw_paths)}")
    simp = simplify(raw_paths, tol=args.tol)
    scaled, scale = scale_to_height(simp, args.height, args.screen)
    print(f"scale={scale if not isinstance(scale,tuple) else (round(scale[0],4), round(scale[1],4))}")
    local = invert_y_bottom(scaled)
    minx = min(p[0] for s in local for p in s)
    local = [[(x - minx, y) for x, y in s] for s in local]
    region_paths = cluster_pens(local, k=args.pens)
    print(f"regions: {[len(r) for r in region_paths]}")
    streams = colorize_regions(region_paths)
    raw = emit_multipen(streams)
    nvert = sum(max(0, len(s)) for s in streams)
    ys = [p[2] for s in streams for p in s]
    xs = [p[1] for s in streams for p in s]
    h = int(max(ys)) if ys else 0
    w = int(max(xs)) if xs else 0
    nbands = (h + BAND_H - 1) // BAND_H
    print(f"vertices≈{nvert} bytes={len(raw)} bbox={w}x{h} bands≈{nbands} (BAND_H={BAND_H})")
    print(f"S7 on-screen ≈{w*2}x{h}" if args.screen == "s7" else f"S5 on-screen ≈{w}x{h}")

    verify = ROOT / "verify"
    verify.mkdir(exist_ok=True)
    render_verify(region_paths, args.image, verify / "figure_trace.png", args.screen)

    out = ROOT / f"stroke_{args.out_name}.inc"
    label = f"tmpl_{args.out_name}"
    out.write_text(
        f"; Auto-traced multipen 16-bit-Y from {args.image.name}\n"
        f"; format: FE,n, offs… then records mode,xlo,xhi,ylo,yhi (END=255)\n"
        f"; bands of {BAND_H} local Y; feet-first; NUM_PENS={NUM_PENS}\n"
        f"{label}:\n{format_db(raw)}\n"
    )
    print(f"Wrote {out}")
    # npz for debugging
    pass  # optional debug dump skipped

if __name__ == "__main__":
    main()
