"""Place SF companies on the map grid and build a pixelated logo atlas."""
import json, os, sys, hashlib, math
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from geo import proj, W, H

agents = json.load(open('data/agents.json'))
addrs = json.load(open('data/sf_addresses.json'))
land = np.load('data/land.npy'); blocked = np.load('data/blocked.npy'); park = np.load('data/park.npy')
names = list(np.load('data/nhood_names.npy')); stack = np.load('data/nhood_stack.npy')
free = land & ~blocked & ~park

def hsh(s, k=0):
    return int(hashlib.md5(f'{s}:{k}'.encode()).hexdigest()[:8], 16) / 0xffffffff

def is_sf(a):
    loc = (a.get('location') or '').lower()
    return 'san francisco' in loc

WEIGHTS = {
    'South of Market': 20, 'Financial District/South Beach': 16, 'Mission': 9, 'Mission Bay': 6,
    'Potrero Hill': 5, 'Hayes Valley': 5, 'North Beach': 4, 'Tenderloin': 3, 'Nob Hill': 3,
    'Russian Hill': 3, 'Chinatown': 2, 'Western Addition': 3, 'Castro/Upper Market': 3, 'Noe Valley': 2,
    'Haight Ashbury': 2, 'Marina': 3, 'Pacific Heights': 3, 'Bayview Hunters Point': 2,
    'Inner Richmond': 2, 'Inner Sunset': 2, 'Japantown': 1, 'Bernal Heights': 2, 'Presidio Heights': 1,
}
wn = list(WEIGHTS); wv = np.array([WEIGHTS[n] for n in wn], float); wv /= wv.sum()

def nhood_at(x, y):
    xi, yi = int(x), int(y)
    if 0 <= xi < W and 0 <= yi < H:
        hit = np.nonzero(stack[:, yi, xi])[0]
        if len(hit): return names[hit[0]]
    return None

def random_point(slug):
    r = hsh(slug, 1); n = wn[int(np.searchsorted(np.cumsum(wv), r))]
    m = stack[names.index(n)] & free
    ys, xs = np.nonzero(m)
    i = int(hsh(slug, 2) * len(xs)) % len(xs)
    return float(xs[i]), float(ys[i]), n

occ = np.zeros((H, W), bool)

def fits(x, y, s):
    if x < 1 or y < 1 or x + s + 1 >= W or y + s + 1 >= H: return False
    if not free[y:y + s, x:x + s].all(): return False
    return not occ[y - 1:y + s + 1, x - 1:x + s + 1].any()

def place(tx, ty, s):
    cx, cy = int(round(tx - s / 2)), int(round(ty - s / 2))
    for r in range(0, 160):
        cands = []
        for dy in range(-r, r + 1):
            for dx in (-r, r) if abs(dy) != r else range(-r, r + 1):
                cands.append((dx * dx + dy * dy, cx + dx, cy + dy))
        for _, x, y in sorted(cands):
            if fits(x, y, s):
                occ[y:y + s, x:x + s] = True
                return x, y
    raise RuntimeError('no room')

sf = sorted([a for a in agents if is_sf(a)], key=lambda a: a['rank'])
others = [a for a in agents if not is_sf(a)]
out = []
for a in sf:
    s = 11 if a['rank'] <= 10 else 9 if a['rank'] <= 60 else 7
    ad = addrs.get(a['slug']) or {}
    if ad.get('lat'):
        tx, ty = proj(ad['lon'], ad['lat']); prec = ad['precision']; addr = ad.get('address')
        nh = nhood_at(tx, ty)
    else:
        tx, ty, nh = random_point(a['slug']); prec = None; addr = None
    x, y = place(tx, ty, s)
    out.append(dict(slug=a['slug'], name=a['name'], job=a['job'], cat=a['cat'], batch=a['batch'],
                    maker=a['maker'], line=a['line'], score=a['score'], rank=a['rank'], site=a.get('site'),
                    x=x, y=y, s=s, addr=addr, prec=prec,
                    nhood=(nhood_at(x + s / 2, y + s / 2) or nh or '').replace('Financial District/South Beach', 'FiDi / South Beach')))

# ---- logo atlas: 16x16 pixelated, 32-colour quantised
T = 32; cols = 32
rows = math.ceil(len(out) / cols)
atlas = Image.new('RGBA', (cols * T, rows * T), (0, 0, 0, 0))
for i, a in enumerate(out):
    try:
        im = Image.open(f"public/logos/{a['slug']}.webp").convert('RGBA')
    except Exception:
        im = Image.new('RGBA', (64, 64), (200, 200, 200, 255))
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
    sm = bg.convert('RGB').resize((T, T), Image.LANCZOS).convert('RGBA')
    atlas.paste(sm, ((i % cols) * T, (i // cols) * T))
    a['i'] = i
atlas.save('public/logo-atlas.png')

json.dump(dict(W=W, H=H, tile=T, cols=cols, agents=out), open('public/agents.json', 'w'), separators=(',', ':'))
oth = [dict(slug=a['slug'], name=a['name'], job=a['job'], cat=a['cat'], score=a['score'], rank=a['rank'],
            location=a.get('location') or 'Unknown', site=a.get('site')) for a in sorted(others, key=lambda a: a['rank'])]
json.dump(oth, open('public/others.json', 'w'), separators=(',', ':'))
print(len(out), 'placed;', len(oth), 'elsewhere;', sum(1 for a in out if a['prec']), 'with address/nhood')
