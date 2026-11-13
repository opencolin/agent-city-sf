"""Render San Francisco as an isometric pixel-art city.

Reads the masks written by render_map.py (data/masks.npz) and the placed agents
(public/agents.json, base-grid coordinates) and writes:
  public/city.png   the whole city, 1 world px = 1 image px
  public/iso.json   projection constants, sign anchors, labels, ambient data
"""
import json, math, os, sys, base64, random
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
from geo import proj

random.seed(7)
M = np.load('data/masks.npz')
BW, BH = M['water'].shape[1], M['water'].shape[0]
CS = 3                                   # base px per cell (~60 m)
CW, CH = math.ceil(BW / CS), math.ceil(BH / CS)
TW, TH = 16, 8                           # tile diamond size
TOP = 190                                # headroom for tall towers
OX = CH * TW // 2 + 8
OY = TOP
IW = (CW + CH) * TW // 2 + 16
IH = (CW + CH) * TH // 2 + TOP + 24
E = 3                                    # land height above water

def iso(gx, gy, z=0):
    return ((gx - gy) * TW / 2 + OX, (gx + gy) * TH / 2 + OY - z)

def cell_of_lonlat(lon, lat):
    x, y = proj(lon, lat); return x / CS, y / CS

# ------------------------------------------------------------------ classify cells
def down(mask, thresh, pad=0.0):
    m = np.full((CH * CS, CW * CS), pad, np.float32); m[:BH, :BW] = mask
    return m.reshape(CH, CS, CW, CS).mean(axis=(1, 3)) >= thresh

water = down(M['water'] & ~M['pier'], 0.5, pad=1.0)
lake = down(M['lake'], 0.5)
pier = down(M['pier'], 0.34) & ~down(M['land'], 0.5)
land = ~water | lake
park = down(M['park'], 0.5)
wood = down(M['wood'], 0.5)
beach = down(M['beach'], 0.4)
outside = down(M['outside'], 0.5)
roadpx = M['res'] | M['maj'] | M['hwy']
# streets rasterised straight onto the cell grid from OSM, 1 cell wide
osm = json.load(open('data/osm.json'))
rimg = {k: Image.new('L', (CW, CH), 0) for k in ('res', 'maj', 'hwy')}
rd = {k: ImageDraw.Draw(v) for k, v in rimg.items()}
for e in osm['elements']:
    hw = e.get('tags', {}).get('highway')
    if hw not in ('residential', 'tertiary', 'secondary', 'primary', 'motorway', 'trunk') or 'geometry' not in e: continue
    pts = [tuple(v / CS for v in proj(p['lon'], p['lat'])) for p in e['geometry']]
    key = 'res' if hw == 'residential' else 'hwy' if hw in ('motorway', 'trunk') else 'maj'
    rd[key].line(pts, fill=1)
R_, M_, H_ = (np.array(rimg[k], bool) for k in ('res', 'maj', 'hwy'))
road = (R_ | M_ | H_) & land & ~lake & ~park
major = (M_ | H_) & road
hwy = H_ & road

names = list(np.load('data/nhood_names.npy')); stack = np.load('data/nhood_stack.npy')
nh = np.full((CH, CW), -1, int)
for i in range(len(names)):
    m = np.zeros((CH * CS, CW * CS), bool); m[:BH, :BW] = stack[i]
    c = m.reshape(CH, CS, CW, CS).mean(axis=(1, 3)) >= 0.5
    nh[c & (nh < 0)] = i
NH = lambda cx, cy: names[nh[cy, cx]] if nh[cy, cx] >= 0 else ''

DOWNTOWN = {'Financial District/South Beach', 'South of Market', 'Tenderloin', 'Mission Bay', 'Nob Hill'}
INDUSTRIAL = {'Bayview Hunters Point', 'Treasure Island'}

kind = np.full((CH, CW), 'water', object)
for cy in range(CH):
    for cx in range(CW):
        if water[cy, cx] and not pier[cy, cx]: k = 'water'
        elif pier[cy, cx]: k = 'pier'
        elif lake[cy, cx]: k = 'lake'
        elif beach[cy, cx]: k = 'beach'
        elif park[cy, cx]: k = 'wood' if wood[cy, cx] else 'park'
        elif outside[cy, cx]: k = 'hill'
        elif road[cy, cx]: k = 'hwy' if hwy[cy, cx] else 'major' if major[cy, cx] else 'road'
        else: k = 'lot'
        kind[cy, cx] = k

# ------------------------------------------------------------------ palette
def hx(h): h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def shade(c, f): return tuple(max(0, min(255, int(v * f))) for v in c)
K = {k: hx(v) for k, v in dict(
    water='#2e93dc', water2='#2c8fd8', shallow='#55b4ee', wave='#c9ecff', foam='#e8f7ff',
    wall='#7a6a55', wall2='#5e5142', sand='#f3c96a', sand2='#e8b955',
    grass='#52b043', grass2='#46a03a', grass3='#63c152', hill='#93b95a', hill2='#86ad4f',
    asphalt='#8a8c96', asphalt2='#7f818b', lane='#f2d14b', walk='#c9c6be', walk2='#bdb9b0',
    pier='#b4774a', pier2='#96613b', outline='#2b2233',
).items()}
VIC = ['#ef8fa6', '#f2c94c', '#6fa8dc', '#8fd3b6', '#b39ddb', '#f3e3c3', '#a9c08a', '#f4a582', '#e9eef2', '#7fc8c8', '#e57373']
ROOF = ['#4a4e69', '#c0503a', '#7a4b3a', '#3d6b7a', '#d9732e', '#5b5f73', '#8e3b46']
TOWER = [('#7fb2e5', '#cfe8ff'), ('#9b3f45', '#e3a0a0'), ('#d8c4a0', '#7c6a52'), ('#e9e9ee', '#7891b3'), ('#5d6f8f', '#a9c7ee'), ('#c77a52', '#f2d4b0')]

im = Image.new('RGB', (IW, IH), K['water'])
dr = ImageDraw.Draw(im)
pa = im.load()

def put(x, y, c):
    x, y = int(round(x)), int(round(y))
    if 0 <= x < IW and 0 <= y < IH: pa[x, y] = c

def diamond(cx, cy, col, z=0):
    pts = [iso(cx, cy, z), iso(cx + 1, cy, z), iso(cx + 1, cy + 1, z), iso(cx, cy + 1, z)]
    dr.polygon(pts, fill=col)

# ------------------------------------------------------------------ landmarks reserve cells
LM = {}
def lm(name, lon, lat, r=1):
    gx, gy = cell_of_lonlat(lon, lat)
    LM[name] = (gx, gy)
    for yy in range(int(gy) - r, int(gy) + r + 1):
        for xx in range(int(gx) - r, int(gx) + r + 1):
            if 0 <= xx < CW and 0 <= yy < CH and kind[yy, xx] in ('lot',):
                kind[yy, xx] = 'plaza'
    return gx, gy

lm('transamerica', -122.4028, 37.7952, 1)
lm('salesforce', -122.3969, 37.7897, 1)
lm('coit', -122.4058, 37.8024, 2)
lm('ferry', -122.3937, 37.7955, 2)
lm('sutro', -122.4528, 37.7552, 1)
lm('cityhall', -122.4193, 37.7793, 2)
lm('fineArts', -122.4484, 37.8029, 2)
lm('oracle', -122.3893, 37.7786, 2)
lm('windmill', -122.5092, 37.7703, 0)
lm('conservatory', -122.4602, 37.7714, 1)
lm('lombard', -122.4187, 37.8021, 1)
lm('alcatraz', -122.4228, 37.8268, 0)
for k in ('coit', 'lombard'):
    gx, gy = LM[k]
    for yy in range(int(gy) - 2, int(gy) + 3):
        for xx in range(int(gx) - 2, int(gx) + 3):
            if kind[yy, xx] in ('lot', 'plaza', 'road'): kind[yy, xx] = 'park'
for k in ('coit', 'lombard', 'conservatory', 'windmill'):
    gx, gy = LM[k]; kind[int(gy), int(gx)] = 'plaza'
# Alcatraz island cells
ax_, ay_ = LM['alcatraz']
for yy in range(int(ay_) - 1, int(ay_) + 2):
    for xx in range(int(ax_) - 3, int(ax_) + 4):
        if abs(xx - ax_) / 4 + abs(yy - ay_) / 1.6 < 1.2: kind[yy, xx] = 'rock'
kind[int(ay_), int(ax_)] = 'plaza'

isLand = np.vectorize(lambda k: k not in ('water', 'pier'))(kind)

# ------------------------------------------------------------------ pass 1: ground
def dil(m):
    p = np.pad(m, 1); o = np.zeros_like(m)
    for dy in (0, 1, 2):
        for dx in (0, 1, 2): o |= p[dy:dy + m.shape[0], dx:dx + m.shape[1]]
    return o
shore = dil(isLand); shore2 = dil(shore)

for cy in range(CH):
    for cx in range(CW):
        k = kind[cy, cx]; r = random.random()
        if k in ('water', 'lake'):
            col = K['shallow'] if (k == 'water' and shore[cy, cx]) else K['water2'] if r < .15 else K['water']
            diamond(cx, cy, col)
            if r < 0.06 and not shore[cy, cx]:
                x, y = iso(cx + .5, cy + .5); [put(x + i, y + (i // 2), K['wave']) for i in range(-2, 3)]
        elif k == 'pier':
            diamond(cx, cy, K['pier'])
            x, y = iso(cx, cy + .5)
            for i in range(0, 16, 3): put(x + i, y + i / 2 - 2, K['pier2']); put(x + i, y + i / 2 + 1, K['pier2'])
        elif k == 'beach':
            diamond(cx, cy, K['sand'])
            if r < .4: x, y = iso(cx + .5, cy + .5); put(x + random.randint(-4, 4), y + random.randint(-1, 1), K['sand2'])
        elif k in ('park', 'wood', 'hill', 'rock'):
            base = K['hill'] if k in ('hill', 'rock') else K['grass2'] if r < .3 else K['grass']
            diamond(cx, cy, base)
            x, y = iso(cx + .5, cy + .5)
            for _ in range(2): put(x + random.randint(-5, 5), y + random.randint(-2, 2), K['grass3'] if k != 'hill' else K['hill2'])
        elif k in ('road', 'major', 'hwy'):
            diamond(cx, cy, K['asphalt'] if r > .2 else K['asphalt2'])
        else:  # lot / plaza: pavement
            diamond(cx, cy, K['walk'] if r > .3 else K['walk2'])

# lane markings: dashes along major roads
for cy in range(CH):
    for cx in range(CW):
        if kind[cy, cx] in ('major', 'hwy') and (cx + cy) % 2 == 0:
            x, y = iso(cx + .5, cy + .5)
            horiz = kind[cy, min(CW - 1, cx + 1)] in ('major', 'hwy') or kind[cy, max(0, cx - 1)] in ('major', 'hwy')
            for i in (-1, 0, 1):
                put(x + i * 2, y + i, K['lane']) if horiz else put(x + i * 2, y - i, K['lane'])

# ------------------------------------------------------------------ pass 2: shore walls
for cy in range(CH):
    for cx in range(CW):
        if not isLand[cy, cx]: continue
        col = K['sand2'] if kind[cy, cx] == 'beach' else K['wall']
        if cx + 1 < CW and not isLand[cy, cx + 1]:
            a, b = iso(cx + 1, cy), iso(cx + 1, cy + 1)
            dr.polygon([a, b, (b[0], b[1] + E), (a[0], a[1] + E)], fill=shade(col, .9))
            put(b[0], b[1] + E + 1, K['foam']); put(a[0], a[1] + E + 1, K['foam'])
        if cy + 1 < CH and not isLand[cy + 1, cx]:
            a, b = iso(cx, cy + 1), iso(cx + 1, cy + 1)
            dr.polygon([a, b, (b[0], b[1] + E), (a[0], a[1] + E)], fill=shade(col, .75))

# ------------------------------------------------------------------ primitives
def prism(gx0, gy0, gx1, gy1, h, face, top=None, z=0, outline=True):
    """Box on grid rect [gx0,gx1]x[gy0,gy1], height h px, base raised z px. Returns top corners."""
    A, B, C_, D = iso(gx0, gy0, z), iso(gx1, gy0, z), iso(gx1, gy1, z), iso(gx0, gy1, z)
    up = lambda p: (p[0], p[1] - h)
    ol = shade(face, .45) if outline else None
    dr.polygon([D, C_, up(C_), up(D)], fill=shade(face, .78), outline=ol)       # +y face (left)
    dr.polygon([C_, B, up(B), up(C_)], fill=face, outline=ol)                   # +x face (right)
    if top is not None:
        dr.polygon([up(A), up(B), up(C_), up(D)], fill=top, outline=ol)
    return up(A), up(B), up(C_), up(D)

def face_pts(gx0, gy0, gx1, gy1, z=0):
    return (iso(gx0, gy1, z), iso(gx1, gy1, z)), (iso(gx1, gy1, z), iso(gx1, gy0, z))

def windows(gx0, gy0, gx1, gy1, h, glass, frame=None, step_x=3, step_y=4, start=3, z=0, top_margin=2):
    for (p0, p1), f in zip(face_pts(gx0, gy0, gx1, gy1, z), (.8, 1.0)):
        L = abs(p1[0] - p0[0])
        n = int((L - 2) // step_x)
        if n <= 0: continue
        for i in range(n):
            u = (2 + i * step_x) / L
            x = p0[0] + (p1[0] - p0[0]) * u; y = p0[1] + (p1[1] - p0[1]) * u
            v = start
            while v + 2 <= h - top_margin:
                g = shade(glass, f)
                put(x, y - v, g); put(x, y - v - 1, g)
                if frame: put(x, y - v - 2, frame)
                v += step_y

def hip_roof(A, B, C_, D, apex_h, col):
    cx = (A[0] + C_[0]) / 2; cy = (A[1] + C_[1]) / 2 - apex_h
    P = (cx, cy); ol = shade(col, .45)
    dr.polygon([A, B, P], fill=shade(col, 1.15), outline=ol)
    dr.polygon([D, A, P], fill=shade(col, 1.0), outline=ol)
    dr.polygon([B, C_, P], fill=shade(col, .85), outline=ol)
    dr.polygon([C_, D, P], fill=shade(col, .7), outline=ol)
    return P

def gable_roof(A, B, C_, D, rise, col, along_x=True):
    ol = shade(col, .45)
    if along_x:   # ridge parallel to grid x: midpoints of A-D and B-C
        m1 = ((A[0] + D[0]) / 2, (A[1] + D[1]) / 2 - rise); m2 = ((B[0] + C_[0]) / 2, (B[1] + C_[1]) / 2 - rise)
        dr.polygon([A, B, m2, m1], fill=shade(col, 1.12), outline=ol)
        dr.polygon([D, C_, m2, m1], fill=shade(col, .8), outline=ol)
        dr.polygon([B, C_, m2], fill=shade(col, .95), outline=ol)
    else:
        m1 = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2 - rise); m2 = ((D[0] + C_[0]) / 2, (D[1] + C_[1]) / 2 - rise)
        dr.polygon([A, D, m2, m1], fill=shade(col, 1.05), outline=ol)
        dr.polygon([B, C_, m2, m1], fill=shade(col, .85), outline=ol)
        dr.polygon([D, C_, m2], fill=shade(col, .75), outline=ol)

DB = 4
DEPTH = np.zeros((IH // DB + 1, IW // DB + 1), np.uint16)
CUR_S = 0
def mark(x0, y0, x1, y1, sv=None):
    sv = CUR_S if sv is None else sv
    x0, x1 = max(0, int(x0) // DB), min(DEPTH.shape[1] - 1, int(x1) // DB)
    y0, y1 = max(0, int(y0) // DB), min(DEPTH.shape[0] - 1, int(y1) // DB)
    if x1 < x0 or y1 < y0: return
    blk = DEPTH[y0:y1 + 1, x0:x1 + 1]; np.maximum(blk, sv, out=blk)

def tree(gx, gy, big=False):
    _x, _y = iso(gx, gy); mark(_x - 4, _y - 12, _x + 4, _y - 1)
    x, y = iso(gx, gy)
    r = 5 if big else 4
    trunk = hx('#6b4226')
    for i in range(3): put(x, y - i, trunk); put(x + 1, y - i, shade(trunk, .8))
    cyy = y - 3 - r
    for dy in range(-r - 1, r + 2):
        for dx in range(-r - 1, r + 2):
            d = (dx * dx) / (r * r) + (dy * dy) / ((r * .9) ** 2)
            if d <= 1.0:
                c = hx('#2f8a3a')
                if dx + dy < -r * 0.6: c = hx('#6cc85a')
                elif dx + dy < 0: c = hx('#46a646')
                elif dx + dy > r * 0.9: c = hx('#23692c')
                put(x + dx, cyy + dy, c)
            elif d <= 1.35:
                put(x + dx, cyy + dy, hx('#1d4d24'))

def person_pixels(x, y, rnd):
    skin = random.choice(['#f1c27d', '#e0ac69', '#c68642', '#8d5524', '#ffdbac'])
    shirt = random.choice(['#e04a2a', '#29adff', '#ffd23f', '#00a86b', '#7e57c2', '#ffffff', '#333333'])
    hair = random.choice(['#2b1d14', '#5a3825', '#d4a017', '#111111', '#a52a2a'])
    for i in range(2): put(x, y - i, hx('#2d3047')); put(x + 1, y - i, hx('#2d3047'))
    for i in range(2, 5): put(x, y - i, hx(shirt)); put(x + 1, y - i, hx(shirt))
    put(x, y - 5, hx(skin)); put(x + 1, y - 5, hx(skin)); put(x, y - 6, hx(hair)); put(x + 1, y - 6, hx(hair))

# ------------------------------------------------------------------ building generators
sf_gx, sf_gy = LM['salesforce']; ta_gx, ta_gy = LM['transamerica']
alamo = cell_of_lonlat(-122.4330, 37.7762)
roof_top = {}

def building(cx, cy):
    n = NH(cx, cy); r = random.random()
    d = min(math.hypot(cx - sf_gx, cy - sf_gy), math.hypot(cx - ta_gx, cy - ta_gy) * 1.2)
    if n == 'Chinatown':
        face = hx(random.choice(['#c8443a', '#f0e0c0', '#d9a441', '#b8433a']))
        h = random.randint(10, 16)
        A, B, C_, D = prism(cx + .08, cy + .08, cx + .92, cy + .92, h, face)
        windows(cx + .08, cy + .08, cx + .92, cy + .92, h, hx('#3a2a1a'), hx('#ffd23f'))
        P = hip_roof(*[(p[0] + dx, p[1] + dy) for p, (dx, dy) in zip((A, B, C_, D), ((0, -1), (1, 0), (0, 1), (-1, 0)))], 6, hx('#2e9a5a'))
        for p in (B, D):
            put(p[0], p[1] + 2, hx('#ff3b3b')); put(p[0], p[1] + 3, hx('#ff3b3b'))
        return P[1]
    if n in DOWNTOWN and d < 22:
        base = 85 if n == 'Financial District/South Beach' else 70 if n == 'South of Market' else 40
        h = int(12 + base * math.exp(-d / 9) * random.uniform(.45, 1.15) + random.uniform(0, 10))
        h = max(14, min(h, 120))
        face, glass = random.choice(TOWER)
        i = .14 if h > 30 else .08
        A, B, C_, D = prism(cx + i, cy + i, cx + 1 - i, cy + 1 - i, h, hx(face), top=shade(hx(face), 1.2))
        windows(cx + i, cy + i, cx + 1 - i, cy + 1 - i, h, hx(glass), step_x=2, step_y=3)
        if h > 40 and random.random() < .5:     # setback crown
            k = .18
            A2, B2, C2, D2 = prism(cx + i + k, cy + i + k, cx + 1 - i - k, cy + 1 - i - k, 6, shade(hx(face), .95), top=shade(hx(face), 1.25), z=h)
            return A2[1]
        if random.random() < .4:
            prism(cx + .4, cy + .4, cx + .62, cy + .62, 3, hx('#9aa0a8'), top=hx('#c4c8cc'), z=h)
        return A[1]
    if n in INDUSTRIAL or (n == 'Potrero Hill' and cx > 200):
        face = hx(random.choice(['#d8d2c4', '#c9bba3', '#e0cfae', '#b9c4cc', '#d6a77a']))
        h = random.randint(7, 11)
        A, B, C_, D = prism(cx + .05, cy + .05, cx + .95, cy + .95, h, face)
        gable_roof(A, B, C_, D, 3, hx(random.choice(['#9aa3ad', '#b86b4b', '#7f95a8', '#c9c2b5'])), along_x=random.random() < .5)
        windows(cx + .05, cy + .05, cx + .95, cy + .95, h, hx('#40536a'), step_x=4, step_y=5)
        return A[1] - 3
    # residential Victorians / row houses
    near_alamo = math.hypot(cx - alamo[0], cy - alamo[1]) < 2.5
    face = hx(random.choice(['#ef8fa6', '#6fa8dc', '#f2c94c', '#8fd3b6', '#b39ddb']) if near_alamo else random.choice(VIC))
    floors = 2 if n in ('Sunset/Parkside', 'Outer Richmond', 'Inner Richmond', 'Outer Mission', 'Excelsior', 'Oceanview/Merced/Ingleside', 'Visitacion Valley', 'Portola') else random.choice([2, 3, 3])
    h = floors * 4 + 2
    inset = .04
    A, B, C_, D = prism(cx + inset, cy + inset, cx + 1 - inset, cy + 1 - inset, h, face)
    windows(cx + inset, cy + inset, cx + 1 - inset, cy + 1 - inset, h, hx('#2c4a74'), frame=hx('#ffffff'), step_x=3, step_y=4, start=3)
    # door
    p0, p1 = face_pts(cx + inset, cy + inset, cx + 1 - inset, cy + 1 - inset)[1]
    dx_, dy_ = p0[0] + (p1[0] - p0[0]) * .5, p0[1] + (p1[1] - p0[1]) * .5
    for k in range(3): put(dx_, dy_ - k, hx('#5a3a2a'))
    roof = hx(random.choice(ROOF))
    if near_alamo or random.random() < .55:
        P = hip_roof(A, B, C_, D, 6 if near_alamo else random.randint(4, 6), roof); return P[1]
    gable_roof(A, B, C_, D, 4, roof, along_x=random.random() < .5)
    return A[1] - 4

# ------------------------------------------------------------------ landmarks
def draw_transamerica(gx, gy):
    g0, g1 = gx - .75, gx + .75
    A, B, C_, D = iso(g0, gy - .75), iso(g1, gy - .75), iso(g1, gy + .75), iso(g0, gy + .75)
    apex = (iso(gx, gy)[0], iso(gx, gy)[1] - 120)
    dr.polygon([D, C_, apex], fill=hx('#e6e1d8'), outline=hx('#6b6358'))
    dr.polygon([C_, B, apex], fill=hx('#f6f3ec'), outline=hx('#6b6358'))
    for t in np.linspace(.08, .92, 26):     # window rows
        for (p, q), col in (((D, C_), hx('#9fb4c8')), ((C_, B), hx('#b8cadb'))):
            a = (p[0] + (apex[0] - p[0]) * t, p[1] + (apex[1] - p[1]) * t)
            b = (q[0] + (apex[0] - q[0]) * t, q[1] + (apex[1] - q[1]) * t)
            L = int(abs(b[0] - a[0]))
            for i in range(1, L, 2): put(a[0] + (b[0] - a[0]) * i / L, a[1] + (b[1] - a[1]) * i / L, col)
    for i in range(8): put(apex[0], apex[1] - i, hx('#6b6358'))
    return apex[1] - 8

def draw_salesforce(gx, gy):
    g = .55
    h = 150
    A, B, C_, D = prism(gx - g, gy - g, gx + g, gy + g, h, hx('#c9d6e3'), top=None)
    windows(gx - g, gy - g, gx + g, gy + g, h - 10, hx('#8fb0cf'), step_x=2, step_y=3)
    # rounded crown
    cx, cy = (A[0] + C_[0]) / 2, (A[1] + C_[1]) / 2
    for k in range(12):
        w = int(9 * math.sqrt(max(0, 1 - (k / 12) ** 2)))
        for i in range(-w, w + 1):
            put(cx + i, cy - k, hx('#e3ebf3') if i < 0 else hx('#c4d2e0'))
    for i in range(-9, 10): put(cx + i, cy, hx('#7f93a8'))
    return cy - 12

def draw_coit(gx, gy):
    tree(gx - .9, gy + .2, True); tree(gx + .2, gy - .9, True)
    A, B, C_, D = prism(gx - .28, gy - .28, gx + .28, gy + .28, 48, hx('#efe6d2'), top=hx('#fffaf0'))
    windows(gx - .28, gy - .28, gx + .28, gy + .28, 48, hx('#8c7f6a'), step_x=2, step_y=48, start=40)
    prism(gx - .45, gy - .45, gx + .45, gy + .45, 5, hx('#d8ccb4'), top=hx('#e9dfca'))
    return A[1]

def draw_ferry(gx, gy):
    A, B, C_, D = prism(gx - 2.2, gy - .5, gx + .6, gy + .5, 12, hx('#dfe4ea'), top=None)
    gable_roof(A, B, C_, D, 4, hx('#6f7f95'), along_x=True)
    windows(gx - 2.2, gy - .5, gx + .6, gy + .5, 12, hx('#5f7896'), step_x=3, step_y=5)
    A2, B2, C2, D2 = prism(gx - .9, gy - .3, gx - .3, gy + .3, 46, hx('#eef1f4'), top=hx('#ffffff'))
    P = hip_roof(A2, B2, C2, D2, 8, hx('#9aa6b5'))
    # clock faces
    for p0, p1 in face_pts(gx - .9, gy - .3, gx - .3, gy + .3):
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - 36
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1): put(mx + dx, my + dy, hx('#ffffff'))
        put(mx, my, hx('#222222')); put(mx, my - 1, hx('#222222'))
    for i in range(6): put(P[0], P[1] - i, hx('#333333'))
    for i in range(3):
        for j in range(4): put(P[0] + 1 + j, P[1] - 5 + i, hx('#e04a2a'))
    return P[1] - 6

def draw_sutro(gx, gy):
    base = [iso(gx - .6, gy + .3), iso(gx + .5, gy + .5), iso(gx + .2, gy - .6)]
    top = iso(gx, gy, 95)
    for b in base:
        n = 12
        for s in range(n):
            a = (b[0] + (top[0] - b[0]) * s / n, b[1] + (top[1] - b[1]) * s / n)
            c = (b[0] + (top[0] - b[0]) * (s + 1) / n, b[1] + (top[1] - b[1]) * (s + 1) / n)
            dr.line([a, c], fill=hx('#e0302a') if s % 2 == 0 else hx('#f4f4f4'), width=2)
    for z in (30, 60, 80):
        pts = [((b[0] + (top[0] - b[0]) * z / 95), (b[1] + (top[1] - b[1]) * z / 95)) for b in base]
        dr.line(pts + [pts[0]], fill=hx('#e0302a'), width=1)
    for dx in (-6, 0, 6):
        dr.line([(top[0] + dx, top[1]), (top[0] + dx, top[1] - 22)], fill=hx('#e0302a'), width=1)
        for k in range(0, 22, 6): put(top[0] + dx, top[1] - k, hx('#f4f4f4'))
    dr.line([(top[0] - 7, top[1] - 4), (top[0] + 7, top[1] - 4)], fill=hx('#e0302a'))
    return top[1] - 22

def draw_cityhall(gx, gy):
    A, B, C_, D = prism(gx - 1.5, gy - .8, gx + 1.2, gy + .8, 14, hx('#e8e1cf'), top=hx('#f2ece0'))
    windows(gx - 1.5, gy - .8, gx + 1.2, gy + .8, 14, hx('#8a8070'), step_x=2, step_y=5)
    cx, cy = iso(gx - .15, gy, 14)
    prism(gx - .55, gy - .55, gx + .25, gy + .25, 10, hx('#e8e1cf'), top=hx('#f2ece0'), z=14)
    cy -= 10 + 4
    for k in range(14):
        w = int(9 * math.sqrt(max(0, 1 - (k / 14) ** 2)))
        for i in range(-w, w + 1):
            put(cx + i, cy - k, hx('#e8c25a') if i < -2 else hx('#d4a83a') if i < 4 else hx('#b88a26'))
    for i in range(6): put(cx, cy - 14 - i, hx('#d4a83a'))
    return cy - 20

def draw_fine_arts(gx, gy):
    prism(gx - 1.1, gy - 1.1, gx + 1.1, gy + 1.1, 3, hx('#d9b58c'), top=hx('#e8c9a0'))
    for t in np.linspace(0, 2 * math.pi, 14, endpoint=False):
        px_, py_ = iso(gx + math.cos(t) * .9, gy + math.sin(t) * .9, 3)
        dr.line([(px_, py_), (px_, py_ - 12)], fill=hx('#c79a6c'))
    cx, cy = iso(gx, gy, 18)
    for k in range(12):
        w = int(11 * math.sqrt(max(0, 1 - (k / 12) ** 2)))
        for i in range(-w, w + 1): put(cx + i, cy - k, hx('#e0a36e') if i < 0 else hx('#c4875a'))
    return cy - 12

def draw_oracle(gx, gy):
    for yy in range(-2, 2):
        for xx in range(-2, 2):
            diamond(int(gx) + xx, int(gy) + yy, K['grass'])
    diamond(int(gx), int(gy), hx('#d9a066'))
    prism(gx - 2, gy - 2, gx + 2, gy - 1.6, 12, hx('#7d8796'), top=hx('#a7b0bd'))
    prism(gx - 2, gy - 2, gx - 1.6, gy + 2, 12, hx('#6f7987'), top=hx('#9aa3b0'))
    for p in (iso(gx - 2, gy - 2, 12), iso(gx + 2, gy - 2, 12), iso(gx - 2, gy + 2, 12)):
        dr.line([p, (p[0], p[1] - 12)], fill=hx('#555555'))
        for i in range(-2, 3): put(p[0] + i, p[1] - 12, hx('#fff6b0'))
    return iso(gx, gy, 24)[1]

def draw_windmill(gx, gy):
    A, B, C_, D = prism(gx - .25, gy - .25, gx + .25, gy + .25, 20, hx('#8a5a3c'), top=None)
    P = hip_roof(A, B, C_, D, 6, hx('#5a3a2a'))
    hub = (P[0] + 2, P[1] + 6)
    for ang in (35, 125, 215, 305):
        a = math.radians(ang)
        end = (hub[0] + math.cos(a) * 14, hub[1] + math.sin(a) * 14)
        dr.line([hub, end], fill=hx('#4a2f20'), width=1)
        dr.line([(hub[0] + math.cos(a) * 4, hub[1] + math.sin(a) * 4 + 1), (end[0], end[1] + 1)], fill=hx('#f4efe6'), width=2)
    return hub[1] - 14

def draw_conservatory(gx, gy):
    A, B, C_, D = prism(gx - 1, gy - .35, gx + 1, gy + .35, 8, hx('#e8f2fb'), top=None)
    gable_roof(A, B, C_, D, 5, hx('#f5fbff'), along_x=True)
    cx, cy = iso(gx, gy, 12)
    for k in range(9):
        w = int(7 * math.sqrt(max(0, 1 - (k / 9) ** 2)))
        for i in range(-w, w + 1): put(cx + i, cy - k, hx('#ffffff') if (i + k) % 3 else hx('#b9d3ea'))
    return cy - 9

def draw_lombard(gx, gy):
    pts = []
    for k in range(9):
        t = k / 8
        x = gx - 1.6 + 3.2 * t
        y = gy + (.6 if k % 2 else -.6)
        pts.append(iso(x, y))
    dr.line(pts, fill=hx('#b5473a'), width=3)
    dr.line(pts, fill=hx('#d4685a'), width=1)
    return None

def draw_alcatraz(gx, gy):
    A, B, C_, D = prism(gx - 1.2, gy - .4, gx + .8, gy + .4, 9, hx('#b8b3a8'), top=hx('#d2cdc2'))
    windows(gx - 1.2, gy - .4, gx + .8, gy + .4, 9, hx('#4a4a4a'), step_x=2, step_y=4)
    A2, B2, C2, D2 = prism(gx + .9, gy - .15, gx + 1.15, gy + .1, 24, hx('#f4f4f4'), top=hx('#ffffff'))
    for i in range(-2, 3): put(A2[0] + i, A2[1] - 2, hx('#ffd23f'))
    return A2[1] - 3

LM_DRAW = dict(transamerica=draw_transamerica, salesforce=draw_salesforce, coit=draw_coit, ferry=draw_ferry,
               sutro=draw_sutro, cityhall=draw_cityhall, fineArts=draw_fine_arts, oracle=draw_oracle,
               windmill=draw_windmill, conservatory=draw_conservatory, lombard=draw_lombard, alcatraz=draw_alcatraz)
LM_NAMES = dict(transamerica='Transamerica Pyramid', salesforce='Salesforce Tower', coit='Coit Tower', ferry='Ferry Building',
                sutro='Sutro Tower', cityhall='City Hall', fineArts='Palace of Fine Arts', oracle='Oracle Park', windmill='Dutch Windmill',
                conservatory='Conservatory of Flowers', lombard='Lombard Street', alcatraz='Alcatraz')
lm_at = {}
for k, (gx, gy) in LM.items(): lm_at[(int(gx), int(gy))] = k

# ------------------------------------------------------------------ pass 3: objects in painter's order
landmark_tops = {}
for s in range(CW + CH - 1):
    for cx in range(max(0, s - CH + 1), min(CW, s + 1)):
        cy = s - cx
        CUR_S = s + 1
        k = kind[cy, cx]
        if (cx, cy) in lm_at:
            name = lm_at[(cx, cy)]; gx, gy = LM[name]
            top = LM_DRAW[name](gx, gy)
            landmark_tops[name] = top
            if top is not None:
                half = dict(transamerica=10, salesforce=8, coit=4, ferry=20, sutro=10, cityhall=20, fineArts=14, oracle=24, windmill=10, conservatory=14, alcatraz=14).get(name, 12)
                bx, by = iso(gx, gy); mark(bx - half, top, bx + half, by + 2)
            continue
        r = random.random()
        if k == 'lot':
            roof_top[(cx, cy)] = building(cx, cy)
            bx, _ = iso(cx, cy); mark(bx - 6, roof_top[(cx, cy)] + 2, bx + 6, iso(cx + 1, cy + 1)[1] - 3)
        elif k == 'wood' and r < .75:
            tree(cx + .5 + random.uniform(-.2, .2), cy + .5 + random.uniform(-.2, .2), r < .4)
        elif k == 'park' and r < .3:
            tree(cx + .5, cy + .5, r < .1)
        elif k == 'hill' and r < .25:
            tree(cx + .5, cy + .5)
        elif k == 'plaza' and r < .15:
            tree(cx + .5, cy + .5)

# ------------------------------------------------------------------ bridges (drawn last, they span water)
def suspension(S, N, deck_z, tower_ts, tower_h, col, dark, deck_col, legs=3.0):
    s0, n0 = iso(*S, deck_z), iso(*N, deck_z)
    # deck
    for off, c in ((2, dark), (1, col), (0, col), (-1, deck_col), (-2, dark)):
        dr.line([(s0[0], s0[1] + off), (n0[0], n0[1] + off)], fill=c, width=1)
    # piers to water
    towers = []
    for t in tower_ts:
        gx = S[0] + (N[0] - S[0]) * t; gy = S[1] + (N[1] - S[1]) * t
        base = iso(gx, gy, deck_z)
        pair = []
        for side in (-1, 1):
            x = base[0] + side * legs; y = base[1] + side * legs / 2
            dr.rectangle([x - 1, y - tower_h, x + 1, y + deck_z + E], fill=col, outline=dark)
            pair.append((x, y - tower_h))
        for frac in (0.0, .35, .7):
            yy = lambda p: p[1] + tower_h * frac
            dr.line([(pair[0][0], yy(pair[0]) + 1), (pair[1][0], yy(pair[1]) + 1)], fill=dark, width=2)
        towers.append(pair)
    # cables: ends -> towers -> sag between
    ends = [s0, n0]
    for side in (0, 1):
        pts = [ends[0]] + [tw[side] for tw in towers] + [ends[1]]
        for a, b in zip(pts, pts[1:]):
            mid_sag = 0 if a in ends or b in ends else tower_h * .8
            seg = []
            for i in range(21):
                t = i / 20
                x = a[0] + (b[0] - a[0]) * t; y = a[1] + (b[1] - a[1]) * t + mid_sag * 4 * t * (1 - t) if mid_sag else a[1] + (b[1] - a[1]) * t
                if not mid_sag and (a in ends or b in ends):
                    y += 6 * math.sin(math.pi * t)
                seg.append((x, y))
            dr.line(seg, fill=col, width=1)
            for i in range(1, 20, 2):
                x, y = seg[i]
                dy_deck = s0[1] + (n0[1] - s0[1]) * ((x - s0[0]) / (n0[0] - s0[0] + 1e-6))
                if y < dy_deck - 1: dr.line([(x, y), (x, dy_deck - 2)], fill=shade(col, .9))

gg_s = cell_of_lonlat(-122.4772, 37.8095); gg_n = cell_of_lonlat(-122.4787, 37.8290)
suspension(gg_s, gg_n, 14, (.18, .82), 70, hx('#e0402a'), hx('#8c2414'), hx('#5a5a5a'))
bb_w = cell_of_lonlat(-122.3890, 37.7880); bb_e = cell_of_lonlat(-122.3660, 37.8090)
suspension(bb_w, bb_e, 12, (.22, .5, .78), 42, hx('#c6cbd3'), hx('#5b6270'), hx('#6a6a6a'))

im.save('public/city.png', optimize=True)

# ------------------------------------------------------------------ signs: one building per company
data = json.load(open('public/agents.json'))
used = set()
def free_lot(cx, cy):
    return 0 <= cx < CW and 0 <= cy < CH and kind[cy, cx] == 'lot' and (cx, cy) not in used

for a in sorted(data['agents'], key=lambda a: a['rank']):
    tx, ty = (a['x'] + a['s'] / 2) / CS, (a['y'] + a['s'] / 2) / CS
    best = None
    for r in range(0, 60):
        cands = [(dx * dx + dy * dy, int(tx) + dx, int(ty) + dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if max(abs(dx), abs(dy)) == r]
        cands = [c for c in sorted(cands) if free_lot(c[1], c[2])]
        if cands: best = cands[0]; break
    _, cx, cy = best
    used.add((cx, cy))
    sx, _ = iso(cx + .5, cy + .5)
    a['wx'] = round(sx, 1); a['wy'] = round(roof_top[(cx, cy)], 1)
    a['gy'] = round(iso(cx + .5, cy + .5)[1], 1)   # ground y (for depth sorting)

# ------------------------------------------------------------------ labels, ambient, roads bitmap
labels = []
for i, n in enumerate(names):
    ys, xs = np.nonzero(nh == i)
    if len(xs) < 4: continue
    x, y = iso(xs.mean() + .5, ys.mean() + .5)
    labels.append(dict(name=n.replace('Financial District/South Beach', 'FiDi'), x=round(x), y=round(y) - 20, area=int(len(xs))))
for k, (gx, gy) in LM.items():
    x, y = iso(gx, gy)
    labels.append(dict(name=LM_NAMES[k], x=round(x), y=round(landmark_tops.get(k) or y) - 6, landmark=True, area=0))

wc = [(cx, cy) for cy in range(CH) for cx in range(CW) if kind[cy, cx] == 'water' and not shore2[cy, cx]]
random.shuffle(wc)
sparks = [[round(iso(cx + .5, cy + .5)[0]), round(iso(cx + .5, cy + .5)[1])] for cx, cy in wc[:700]]
dimg = np.zeros(DEPTH.shape + (3,), np.uint8); dimg[..., 0] = DEPTH >> 8; dimg[..., 1] = DEPTH & 255
Image.fromarray(dimg).save('public/depth.png', optimize=True)
majbits = np.packbits(np.vectorize(lambda k: k in ('major', 'hwy'))(kind).astype(np.uint8).ravel())
roadbits = np.packbits(np.vectorize(lambda k: k in ('road', 'major', 'plaza', 'park'))(kind).astype(np.uint8).ravel())

def path(*lonlats): return [[round(v, 1) for v in iso(*cell_of_lonlat(*p))] for p in lonlats]
json.dump(dict(
    W=IW, H=IH, CW=CW, CH=CH, OX=OX, OY=OY, TW=TW, TH=TH,
    labels=labels, sparks=sparks,
    roads=base64.b64encode(roadbits.tobytes()).decode(), majors=base64.b64encode(majbits.tobytes()).decode(), DB=DB,
    blimp=path((-122.425, 37.800), (-122.400, 37.788), (-122.385, 37.775), (-122.410, 37.770), (-122.440, 37.785)),
    boats=[
        dict(path=path((-122.3925, 37.7965), (-122.405, 37.812), (-122.420, 37.8245), (-122.405, 37.812)), kind='ferry'),
        dict(path=path((-122.3910, 37.7950), (-122.375, 37.800), (-122.360, 37.812), (-122.375, 37.800)), kind='ferry2'),
        dict(path=path((-122.445, 37.812), (-122.465, 37.818), (-122.455, 37.825), (-122.435, 37.818)), kind='sail'),
        dict(path=path((-122.512, 37.790), (-122.512, 37.760), (-122.513, 37.735), (-122.512, 37.760)), kind='sail'),
    ],
    sealions=path((-122.4103, 37.8093)),
    start=[round(v) for v in iso(*cell_of_lonlat(-122.4010, 37.7915))],
), open('public/iso.json', 'w'), separators=(',', ':'))
json.dump(data, open('public/agents.json', 'w'), separators=(',', ':'))
print('city', IW, IH, 'lots', int((kind == 'lot').sum()), 'signs', len(used))
