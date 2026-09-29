# ---------------------------------------------------------------- load budget
def load_vec(p):
    v = np.zeros(H); pts = p['pts']
    def ad(y, a): v[H - 1 - min(H - 1, max(0, y))] += a
    ad(pts[0][1], 4); ymin = ymax = pts[0][1]
    for a, b in zip(pts, pts[1:]):
        n = max(1, math.ceil(abs(b[1] - a[1]) / 8))
        for k in range(1, n + 1):
            y = round(a[1] + (b[1] - a[1]) * k / n); ad(y, 2)
            ymin, ymax = min(ymin, y), max(ymax, y)
            if ymax - ymin > 12: ad(y, 4); ymin = ymax = y
        npx = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        for k in range(npx): ad(round(a[1] + (b[1] - a[1]) * k / max(1, npx)), 1)
    return v
LWT = P['layer_weight']; TW = P['tone_weight']
def importance(p):
    w = TW[str(p['tone'])] * math.sqrt(C.length(p['pts']) + 1) * LWT.get(p['layer'], 1.0)
    if p.get('zone') == 'face': w *= P['face_weight']
    return w
chunks = []
for p in final:
    base = importance(p); pts = p['pts']
    if len(pts) == 1: chunks.append(dict(p, imp=base)); continue
    cur = [pts[0]]; cl = 0
    for a, b in zip(pts, pts[1:]):
        cur.append(b); cl += math.dist(a, b)
        if cl >= P['chunk_len']: chunks.append(dict(p, pts=cur, imp=base)); cur = [b]; cl = 0
    if len(cur) >= 2: chunks.append(dict(p, pts=cur, imp=base))
final = chunks
V = np.array([load_vec(p) for p in final]); alive = np.ones(len(final), bool)
imp = np.array([p['imp'] for p in final]); dropped = 0
tot = V.sum(0)
def grp(t): return 0 if t == 7 else (1 if t >= 4 else 2)
GT = np.array(P['share_target'])
gid = np.array([grp(p['tone']) for p in final])
def npx(p):
    pts = [tuple(v) for v in p['pts']]
    return 1 if len(pts) == 1 else len(set(q for a_, b_ in zip(pts, pts[1:]) for q in bres(a_, b_)))
pix = np.array([npx(p) for p in final], float)
G = np.array([pix[gid == g].sum() for g in range(3)])
# lane model (same rule as gen: ink-balanced x bounds, 8 lanes; delay set permuted densest -> smallest)
NL = 8; DSET = [0, 8, 16, 24, 32, 40, 48, 56]
mx = np.array([np.mean([v[0] for v in p['pts']]) for p in final])
# lane bounds that minimise the worst windowed lane peak (dense crest spread over more pens)
colx = np.clip(mx.astype(int), 0, W - 1)
VX = np.zeros((W, V.shape[1]))
np.add.at(VX, colx, V)
box = np.ones(40) / 40
def greedy(Tp):
    bnd = [0]; cur = np.zeros(V.shape[1])
    for x in range(W):
        nxt = cur + VX[x]
        if np.convolve(nxt, box, 'valid').max() > Tp and cur.any():
            bnd.append(x); cur = VX[x].copy()
            if len(bnd) > NL: return None
        else: cur = nxt
    return bnd + [W]
lo, hi = 1.0, 80.0
for _ in range(30):
    mid_ = (lo + hi) / 2
    if greedy(mid_) is None: lo = mid_
    else: hi = mid_
bounds = greedy(hi)
while len(bounds) < NL + 1:          # split the widest lane if fewer lanes were needed
    k = int(np.argmax(np.diff(bounds))); bounds.insert(k + 1, (bounds[k] + bounds[k + 1]) // 2)
lane = np.clip(np.searchsorted(bounds, mx, side='right') - 1, 0, NL - 1)
LL = np.array([V[lane == k].sum(0) for k in range(NL)])
LW_ = np.array([(V[lane == k] * (1 + P['white_delay_w'] * (gid[lane == k] == 0))[:, None]).sum(0) for k in range(NL)])
pk = [np.convolve(LW_[k], np.ones(40) / 40, 'valid').max() for k in range(NL)]
delays = [0] * NL
for rank, k in enumerate(sorted(range(NL), key=lambda k: -pk[k])): delays[k] = DSET[rank]
LIM = np.array([P['lane_a'] - P['lane_b'] * d for d in delays])
WD = []
ishand = np.array([p.get('zone') == 'face' and p['layer'] in ('blob', 'eye') for p in final])   # eyes are never pruned
while True:
    worst = None
    for w, lim in ((100, P['max100']), (40, P['max40'])):
        k = np.convolve(tot, np.ones(w) / w, mode='valid'); i = int(k.argmax())
        if k[i] > lim and (worst is None or k[i] / lim > worst[0]): worst = (k[i] / lim, i, w)
    for k in range(NL):
        kk = np.convolve(LL[k], np.ones(40) / 40, mode='valid'); i = int(kk.argmax())
        if kk[i] > LIM[k] and (worst is None or kk[i] / LIM[k] > worst[0]): worst = (kk[i] / LIM[k], i, 40, k)
    if worst is None or '--nobudget' in sys.argv: break
    i, w = worst[1], worst[2]
    inwin = V[:, i:i + w].sum(1)
    cand = np.nonzero(alive & (inwin > 0) & ((lane == worst[3]) if len(worst) > 3 else True))[0]
    nh = cand[~ishand[cand]]
    if len(nh): cand = nh
    f = (G / G.sum() / GT) ** P['share_k']
    j = cand[np.argmin(imp[cand] / inwin[cand] / f[gid[cand]])]
    if gid[j] == 0: WD.append((len(worst) > 3, worst[2], worst[1], int(lane[j]), int(pix[j])))
    alive[j] = False; tot -= V[j]; LL[lane[j]] -= V[j]; G[gid[j]] -= pix[j]; dropped += 1
kept = [p for p, a in zip(final, alive) if a]
print('white drops (lanewin?, w, row, lane, px):', Counter((a, w, r // 20 * 20, l) for a, w, r, l, n in WD).most_common(8))
print('group px before', [int(pix[gid == g].sum()) for g in range(3)], 'dropped px', [int(pix[(gid == g) & ~alive].sum()) for g in range(3)])
V0 = V.sum(0)
print('load before prune per 60 rows (top first):', [int(V0[i:i+60].mean()) for i in range(0, H, 60)])
print('dropped by layer', dict(Counter(p['layer'] for p, a in zip(final, alive) if not a)), 'kept', dict(Counter(p['layer'] for p, a in zip(final, alive) if a)))
final = []
for p in kept:
    q = final[-1] if final else None
    if q is not None and q['tone'] == p['tone'] and q['layer'] == p['layer'] and q['pts'][-1] == p['pts'][0] and len(p['pts']) > 1:
        q['pts'] = q['pts'] + p['pts'][1:]
    else: final.append(dict(p))
for p in final:
    p.pop('imp', None); p.pop('zone', None); p['mode'] = 16 | P['slot'][str(p['tone'])]; p['pts'] = [list(v) for v in p['pts']]
tot = np.array([load_vec(p) for p in final]).sum(0)
print('lanes', bounds, 'delays', delays, 'lane peak w40', [round(float(np.convolve(LL[k], np.ones(40)/40, 'valid').max()), 1) for k in range(NL)], 'lim', LIM.tolist())
print(f'budget: dropped {dropped} chunks; load mean {tot.mean():.1f} max100 {np.convolve(tot, np.ones(100)/100, "valid").max():.1f} max40 {np.convolve(tot, np.ones(40)/40, "valid").max():.1f}')
json.dump(dict(W=W, H=H, crop=[X0, X1, Y0, Y1], S=S, bounds=bounds, delays=delays, paths=final), open(HERE / P.get('out', 'paths.json'), 'w'))
ink = Counter()
for p in final:
    pts = [tuple(v) for v in p['pts']]
    px = set(pts) if len(pts) == 1 else set(q for a, b in zip(pts, pts[1:]) for q in bres(a, b))
    ink[p['tone']] += len(px)
n = sum(ink.values()); nv = sum(len(p['pts']) for p in final)
print(f'H={H} strokes={len(final)} vertices={nv} ink~{n}  layers', dict(Counter(p['layer'] for p in final)))
print(' ink share by tone', {t: f'{ink[t] / n:.1%}' for t in sorted(ink, reverse=True)},
      f" white {ink[7]/n:.0%} mid {(ink[6]+ink[5]+ink[4])/n:.0%} dark {(ink[3]+ink[2]+ink[1])/n:.0%}")
if '--zstat' in sys.argv:
    zc = Counter()
    for p in kept:
        pts = [tuple(v) for v in p['pts']]
        zc[(p['zone'], p['tone'], p['layer'])] += 1 if len(pts) == 1 else len(set(q for a, b in zip(pts, pts[1:]) for q in bres(a, b)))
    for k, v in sorted(zc.items(), key=lambda kv: -kv[1]): print('  ', k, v)
