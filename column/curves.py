"""Curve tools for the v2 trace: skeleton -> graph -> long strokes (junctions joined by the
smoothest continuation), contour extraction, arc-length Gaussian smoothing, hand wobble and
Douglas-Peucker simplification in output-pixel units."""
import math
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from skimage.measure import find_contours, approximate_polygon

N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

def skeleton_strokes(mask, min_len=6, spur=5, join_cos=0.35):
    """mask bool -> list of (N,2) float arrays (x, y) of long centreline strokes."""
    sk = skeletonize(mask)
    H, W = sk.shape
    cnt = ndi.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode='constant') - 1
    deg = np.where(sk, cnt, 0)
    node = sk & (deg != 2)
    nlab, nn = ndi.label(node, structure=np.ones((3, 3)))
    ys, xs = np.nonzero(sk)
    S = set(zip(ys.tolist(), xs.tolist()))
    def nb(p):
        y, x = p
        return [(y + dy, x + dx) for dy, dx in N8 if (y + dy, x + dx) in S]
    edges = []          # (nodeA, nodeB, pixel list)
    vis = set()
    for p in zip(*np.nonzero(node)):
        p = (int(p[0]), int(p[1])); a = nlab[p]
        for q in nb(p):
            if node[q] or q in vis:
                continue
            path = [p, q]; vis.add(q); prev, cur = p, q
            while True:
                nx = [r for r in nb(cur) if r != prev]
                nodes = [r for r in nx if node[r] and r != p]
                if nodes and len(path) > 2 or (nodes and nlab[nodes[0]] != a):
                    path.append(nodes[0]); break
                nx = [r for r in nx if not node[r] and r not in vis]
                if not nx:
                    break
                prev, cur = cur, nx[0]; path.append(cur); vis.add(cur)
            b = nlab[path[-1]] if node[path[-1]] else 0
            edges.append([a, b, path])
    # pure loops (no node pixels)
    used = set(q for e in edges for q in e[2])
    for p in S:
        if p in used or node[p]:
            continue
        path = [p]; prev, cur = None, p; used.add(p)
        while True:
            nxt = [r for r in nb(cur) if r != prev and r not in used]
            if not nxt: break
            prev, cur = cur, nxt[0]; path.append(cur); used.add(cur)
        if len(path) >= min_len:
            edges.append([-1, -1, path + [path[0]]])
    # node degree in the edge graph, drop short spurs (one free end)
    from collections import defaultdict
    def ndeg():
        d = defaultdict(int)
        for a, b, _ in edges:
            if a > 0: d[a] += 1
            if b > 0: d[b] += 1
        return d
    for _ in range(2):
        d = ndeg()
        keep = []
        for e in edges:
            a, b, pth = e
            free = (a > 0 and d[a] == 1) or (b > 0 and d[b] == 1) or b == 0
            junct = (a > 0 and d[a] >= 3) or (b > 0 and d[b] >= 3)
            if free and junct and len(pth) < spur:
                continue
            keep.append(e)
        edges = keep
    # join at junctions: pair edge ends with the straightest continuation
    def end_dir(pth, at_start):
        seg = pth[:8] if at_start else pth[::-1][:8]
        (y0, x0), (y1, x1) = seg[0], seg[-1]
        v = np.array([x1 - x0, y1 - y0], float); n = np.linalg.norm(v)
        return v / n if n else v            # pointing away from the node
    ends = defaultdict(list)
    for i, (a, b, pth) in enumerate(edges):
        if a > 0: ends[a].append((i, 0))
        if b > 0: ends[b].append((i, 1))
    link = {}
    for n, L in ends.items():
        pairs = []
        for u in range(len(L)):
            for v in range(u + 1, len(L)):
                (i, si), (j, sj) = L[u], L[v]
                if i == j: continue
                di = end_dir(edges[i][2], si == 0); dj = end_dir(edges[j][2], sj == 0)
                c = -float(di @ dj)       # 1 = straight through
                if c > join_cos: pairs.append((c, L[u], L[v]))
        pairs.sort(reverse=True); done = set()
        for c, eu, ev in pairs:
            if eu in done or ev in done: continue
            done.add(eu); done.add(ev); link[eu] = ev; link[ev] = eu
    strokes = []; vis = set()
    for i in range(len(edges)):
        if i in vis: continue
        # walk to one end of the chain
        cur, side = i, 0; guard = 0
        while (cur, side) in link and guard < len(edges):
            j, sj = link[(cur, side)]
            if j == i: break
            cur, side = j, 1 - sj; guard += 1
        # now traverse from (cur, side) end
        pts = []; e, s = cur, side; guard = 0
        while True:
            if e in vis: break
            vis.add(e); pth = edges[e][2]
            seq = pth if s == 0 else pth[::-1]
            pts += seq if not pts else seq[1:]
            nxt = link.get((e, 1 - s))
            if nxt is None: break
            e, s = nxt; guard += 1
        if len(pts) >= min_len:
            strokes.append(np.array([(x, y) for y, x in pts], float))
    return strokes

def contour_strokes(f, lvl=0.5, min_len=6, border=2.5):
    out = []
    for c in find_contours(np.pad(f, 1), lvl):
        c = c - 1
        onb = (c[:, 0] < border) | (c[:, 0] > f.shape[0] - 1 - border) | (c[:, 1] < border) | (c[:, 1] > f.shape[1] - 1 - border)
        closed = np.allclose(c[0], c[-1]) and not onb.any()
        if closed:
            out.append((c[:, ::-1].copy(), True)); continue
        run = []
        for q, b in zip(c, onb):
            if b:
                if len(run) >= min_len: out.append((np.array(run)[:, ::-1], False))
                run = []
            else: run.append(q)
        if len(run) >= min_len: out.append((np.array(run)[:, ::-1], False))
    return out

def resample(p, step=1.0):
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
    if d[-1] < step: return p.copy()
    s = np.linspace(0, d[-1], max(2, int(d[-1] / step) + 1))
    return np.c_[np.interp(s, d, p[:, 0]), np.interp(s, d, p[:, 1])]

def smooth(p, sigma, closed=False):
    if len(p) < 3 or sigma <= 0: return p
    q = resample(p, 1.0)
    mode = 'wrap' if closed else 'nearest'
    x = ndi.gaussian_filter1d(q[:, 0], sigma, mode=mode); y = ndi.gaussian_filter1d(q[:, 1], sigma, mode=mode)
    if not closed:          # keep the true end points (pencil lands where the line ends)
        w = np.minimum(1, np.minimum(np.arange(len(q)), np.arange(len(q))[::-1]) / max(1, 1.5 * sigma))
        x = w * x + (1 - w) * q[:, 0]; y = w * y + (1 - w) * q[:, 1]
        x = ndi.gaussian_filter1d(x, max(0.7, sigma / 3), mode='nearest'); y = ndi.gaussian_filter1d(y, max(0.7, sigma / 3), mode='nearest')
    return np.c_[x, y]

def wobble(p, rng, amp, corr):
    """low-frequency hand wobble (perpendicular offset), p in output px, dense."""
    if len(p) < 4 or amp <= 0: return p
    q = resample(p, 0.5)
    n = rng.normal(0, 1, len(q)); n = ndi.gaussian_filter1d(n, corr * 2, mode='nearest')
    n = n / (np.abs(n).max() + 1e-9) * amp
    t = np.gradient(q, axis=0); t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-9
    nrm = np.c_[-t[:, 1], t[:, 0]]
    return q + nrm * n[:, None]

def simplify_int(p, tol, W, H):
    """dense float curve (output px) -> integer vertex list; DP in pixel units, dedupe."""
    if len(p) >= 3: p = approximate_polygon(p, tolerance=tol)
    q = []
    for x, y in p:
        v = (int(min(W - 1, max(0, round(x)))), int(min(H - 1, max(0, round(y)))))
        if not q or q[-1] != v: q.append(v)
    return q

def length(p): return float(np.hypot(*np.diff(np.asarray(p, float), axis=0).T).sum()) if len(p) > 1 else 0.0
