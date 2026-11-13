"""Render the 8-bit San Francisco base map at native pixel resolution.

Outputs:
  public/map.png        base map (W x H), scaled up with nearest-neighbour in the browser
  data/blocked.npy      pixels where logos must not be placed (water, landmarks)
  data/land.npy         land mask
"""
import json, sys, os
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
from geo import proj, W, H

def hexc(h):
    h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

C = {k: hexc(v) for k, v in dict(
    deep='#1b3b6f', water='#21518f', shallow='#2f6fb5', foam='#7fc4f0', wave='#4f95d9', spark='#cfefff',
    edge='#5b5240', sand='#efd893', sand2='#e2c77a',
    roof1='#b9b19a', roof2='#aea78f', roof3='#c3bba3', street='#e6dfc8', major='#f6f1df',
    hwy='#f0a63a', hwyedge='#9a5a1c',
    park='#5fae3f', park2='#55a238', tree='#2f6e2a', treehi='#86cf55',
    pier='#8a6a48', hill='#a9a77a', hill2='#9c9a6d', pierhi='#a8865e', lake='#2d78c4',
).items()}

def rings_of(geom):
    t = geom['type']
    polys = geom['coordinates'] if t == 'MultiPolygon' else [geom['coordinates']]
    return polys

def poly_px(ring):
    return [proj(lon, lat) for lon, lat in ring]

def draw_mask(polys_lonlat, holes=True):
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    for poly in polys_lonlat:
        d.polygon(poly_px(poly[0]), fill=1)
        if holes:
            for h in poly[1:]: d.polygon(poly_px(h), fill=0)
    return np.array(im, bool)

def h2(x, y, s=0):
    v = (x * 374761393 + y * 668265263 + s * 2246822519) & 0xffffffff
    v = ((v ^ (v >> 13)) * 1274126177) & 0xffffffff
    return (v ^ (v >> 16)) / 0xffffffff

# ---------------------------------------------------------------- land
nh = json.load(open('data/neighborhoods.geojson'))
land_polys, nhood_masks, greens = [], {}, {}
for f in nh['features']:
    ps = rings_of(f['geometry']); land_polys += ps
    nhood_masks[f['properties']['nhood']] = draw_mask(ps)

MARIN = [(-122.53, 37.85), (-122.53, 37.818), (-122.52, 37.8165), (-122.505, 37.823), (-122.49, 37.826),
         (-122.4785, 37.8255), (-122.4745, 37.8305), (-122.472, 37.8335), (-122.466, 37.845), (-122.53, 37.85)]
land = draw_mask(land_polys)
im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
d.polygon(poly_px(MARIN), fill=1)
ax, ay = proj(-122.4228, 37.8268)
d.ellipse([ax - 13, ay - 4, ax + 13, ay + 4], fill=1)  # Alcatraz
DALY = [(-122.5040, 37.7088), (-122.3925, 37.7088), (-122.3900, 37.6990), (-122.5060, 37.6990)]
d.polygon(poly_px(DALY), fill=1)
outside = np.array(im, bool) & ~land
land |= np.array(im, bool)

# lakes
wj = json.load(open('data/osm_water.json'))
lake = np.zeros((H, W), bool)
for e in wj['elements']:
    rings = []
    if e['type'] == 'way' and 'geometry' in e: rings = [e['geometry']]
    elif e['type'] == 'relation':
        rings = [m['geometry'] for m in e.get('members', []) if m.get('role') == 'outer' and 'geometry' in m]
    for g in rings:
        if len(g) > 3 and g[0] == g[-1]:
            lake |= draw_mask([[[(p['lon'], p['lat']) for p in g]]])
lake &= land

# ---------------------------------------------------------------- osm features
osm = json.load(open('data/osm.json'))
img = Image.new('RGB', (W, H), C['water'])
px = np.zeros((H, W, 3), np.uint8)

park = np.zeros((H, W), bool); wood = np.zeros((H, W), bool); beach = np.zeros((H, W), bool)
for name in ['Golden Gate Park', 'Presidio', 'McLaren Park', 'Lincoln Park']:
    park |= nhood_masks[name]
wood |= nhood_masks['Presidio']
road_im = {k: Image.new('L', (W, H), 0) for k in ('res', 'maj', 'hwy', 'pier')}
road_d = {k: ImageDraw.Draw(v) for k, v in road_im.items()}
for e in osm['elements']:
    tags = e.get('tags', {})
    geoms = [e['geometry']] if 'geometry' in e else [m['geometry'] for m in e.get('members', []) if 'geometry' in m and m.get('role') == 'outer']
    for g in geoms:
        pts = [proj(p['lon'], p['lat']) for p in g]
        if len(pts) < 2: continue
        closed = g[0] == g[-1] and len(g) > 3
        hw = tags.get('highway')
        if hw == 'residential': road_d['res'].line(pts, fill=1)
        elif hw in ('tertiary', 'secondary', 'primary'): road_d['maj'].line(pts, fill=1)
        elif hw in ('motorway', 'trunk'): road_d['hwy'].line(pts, fill=1, width=2)
        elif tags.get('man_made') == 'pier':
            if closed: road_d['pier'].polygon(pts, fill=1)
            else: road_d['pier'].line(pts, fill=1, width=2)
        elif closed and tags.get('leisure') == 'park':
            park |= draw_mask([[[(p['lon'], p['lat']) for p in g]]])
        elif closed and tags.get('natural') == 'wood':
            m = draw_mask([[[(p['lon'], p['lat']) for p in g]]]); park |= m; wood |= m
        elif closed and tags.get('natural') in ('beach', 'sand'):
            beach |= draw_mask([[[(p['lon'], p['lat']) for p in g]]])

res, maj, hwy, pier = (np.array(road_im[k], bool) for k in ('res', 'maj', 'hwy', 'pier'))
pier &= ~land

def dilate(m, r=1):
    o = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx or dy: o |= np.roll(np.roll(m, dy, 0), dx, 1)
    return o

landish = land | pier
water = ~landish
near1 = dilate(landish, 1) & water
near3 = dilate(landish, 3) & water
coast = land & dilate(water, 1)

# ---------------------------------------------------------------- paint
Y, X = np.mgrid[0:H, 0:W]
hv = np.vectorize(h2)
R = hv(X // 2, Y // 2, 1); R1 = hv(X, Y, 2); R3 = hv(X // 3, Y, 3)

def paint(mask, col): px[mask] = C[col]

paint(np.ones((H, W), bool), 'water')
paint(water & (R1 < 0.10), 'deep')
paint(near3, 'shallow')
waves = water & ~near3 & (R3 < 0.02) & ((X % 3) != 2)
paint(waves, 'wave')
paint(water & ~near3 & (R1 < 0.0012), 'spark')
paint(near1, 'foam')

blocks = land & ~park & ~beach
paint(blocks & (R < 0.4), 'roof1'); paint(blocks & (R >= 0.4) & (R < 0.75), 'roof2'); paint(blocks & (R >= 0.75), 'roof3')
paint(land & park, 'park'); paint(land & park & (R1 < 0.25), 'park2')
trees = land & park & (R1 < np.where(wood, 0.40, 0.14))
paint(trees, 'tree')
paint(np.roll(trees, -1, 0) & land & park & ~trees, 'treehi')
paint(land & beach, 'sand'); paint(land & beach & (R1 < 0.2), 'sand2')
paint(land & res & ~park, 'street')
paint(land & maj, 'major')
paint(dilate(hwy, 1) & land & ~hwy, 'hwyedge') if False else None
paint(hwy & landish, 'hwy')
paint(pier, 'pier'); paint(pier & (R1 < 0.3), 'pierhi')
paint(lake, 'lake'); paint(lake & (R3 < 0.05), 'wave')
paint(outside & ~res & ~maj & ~hwy, 'hill'); paint(outside & ~res & ~maj & ~hwy & (R1 < 0.2), 'hill2')
paint(coast & ~beach, 'edge')

blocked = water.copy() | lake

# ---------------------------------------------------------------- landmark sprites
P = {'k': '#1a1c2c', 'w': '#f4f4f4', 'g': '#c2c3c7', 'G': '#7d7f8c', 'r': '#e04a2a', 'R': '#9c2a14',
     'b': '#8fb8dc', 'B': '#4a6f9a', 'c': '#29adff', 'y': '#ffd23f', 'n': '#8a5a3c', 'o': '#e8a860',
     'O': '#b8763a', 'p': '#ff77a8', 'l': '#a8e061', 'v': '#a07ad0', 'e': '#3b9d3a', 'E': '#2a6e2a', 's': '#e8cf96'}

def sprite(rows):
    w = max(len(r) for r in rows)
    return [r.center(w, '.').replace(' ', '.') for r in rows]

def stamp(rows, lon, lat, block=True, anchor='bottom'):
    rows = sprite(rows); h, w = len(rows), len(rows[0])
    x0, y0 = proj(lon, lat)
    x0 = int(round(x0 - w / 2)); y0 = int(round(y0 - (h if anchor == 'bottom' else h / 2)))
    for j, r in enumerate(rows):
        for i, ch in enumerate(r):
            if ch == '.': continue
            yy, xx = y0 + j, x0 + i
            if 0 <= yy < H and 0 <= xx < W:
                px[yy, xx] = hexc(P[ch])
    if block:
        blocked[max(0, y0 - 1):y0 + h + 1, max(0, x0 - 1):x0 + w + 1] = True
    return (x0, y0, w, h)

def line(p0, p1, col, width=1, block=True):
    x0, y0 = proj(*p0); x1, y1 = proj(*p1)
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for t in np.linspace(0, 1, n):
        x = int(round(x0 + (x1 - x0) * t)); y = int(round(y0 + (y1 - y0) * t))
        for k in range(width):
            for xx, yy in ((x + k, y),):
                if 0 <= yy < H and 0 <= xx < W:
                    px[yy, xx] = hexc(P[col[k % len(col)]])
                    if block: blocked[yy, xx] = True

# Golden Gate Bridge: deck + towers
GG_S, GG_N = (-122.4772, 37.8105), (-122.4787, 37.8270)
line(GG_S, GG_N, 'krrRk', width=5)
GG_TOWER = ['kk.kk', 'rR.rR', 'rRkrR', 'rrrrR', 'rR.rR', 'rR.rR', 'rRrrR', 'rR.rR', 'rR.rR', 'rR.rR', 'rRrrR', 'rR.rR', 'rR.rR', 'kkkkk']
stamp(GG_TOWER, -122.4774, 37.8125)
stamp(GG_TOWER, -122.4785, 37.8250)

# Bay Bridge (west span) to Yerba Buena
BB_W, BB_E = (-122.3885, 37.7885), (-122.3670, 37.8085)
line(BB_W, BB_E, 'kgGk', width=4)
BB_TOWER = ['k.k', 'GgG', 'G.G', 'GgG', 'G.G', 'GgG', 'G.G', 'kkk']
for t in (0.2, 0.5, 0.8):
    stamp(BB_TOWER, BB_W[0] + (BB_E[0] - BB_W[0]) * t, BB_W[1] + (BB_E[1] - BB_W[1]) * t + 0.0004)

LANDMARKS = [
    ('Transamerica Pyramid', -122.4028, 37.7952, ['k', 'kwk', 'kwk', 'kwk', 'kwgk', 'kwwgk', 'kwwgk', 'kwwgk', 'kwwwggk', 'kwwwggk', 'kwwgwggk', 'kwwwgwggk', 'kkkkkkkkk']),
    ('Salesforce Tower', -122.3969, 37.7897, ['kkk', 'kbbbk', 'kbbcbk'] + ['kbbbbBk', 'kbcbbBk'] * 8 + ['kkkkkkk']),
    ('Coit Tower', -122.4058, 37.8024, ['kkk', 'kgwgk', 'kwwgk', 'kwkgk', 'kwwgk', 'kwwgk', 'kwwgk', 'kwwgk', 'kwwgk', 'keeeeek', 'kkkkkkk']),
    ('Ferry Building', -122.3937, 37.7955, ['k', 'kwk', 'kwk', 'kwwgk', 'kwyGk', 'kwwgk', 'kwwgk', 'kkkkwwgkkkk', 'kwwwwwwwwgk', 'kwkwkwkwkgk', 'kwwwwwwwwgk', 'kkkkkkkkkkk']),
    ('Sutro Tower', -122.4528, 37.7552, ['r.r.r', 'w.w.w', 'rkkkr', 'w.w.w', 'r.r.r', 'w.w.w', '.rkr.', '.w.w.', '.r.r.', '.w.w.', 'kr.rk', 'k...k']),
    ('Painted Ladies', -122.4330, 37.7762, ['.k..k..k..k..k.', 'kpkkckklkkykkvk', 'pwppwccwllwyywv', 'pppcccllllyyyvv'.replace('pppcccllllyyyvv', 'ppp' + 'ccc' + 'lll' + 'yyy' + 'vvv'), 'pwpcwclwlywyvwv', 'kkkkkkkkkkkkkkk']),
    ('Palace of Fine Arts', -122.4484, 37.8029, ['kkk', 'koook', 'kooOok', 'koooOk', 'kkkkkkk', 'kskskskk', 'kskskskk', 'kkkkkkkkk']),
    ('Oracle Park', -122.3893, 37.7786, ['kkkkkkkkkkkkk', 'kGGGGGGGGGGGk', 'kGeeeeeeeeeGk', 'kGeEeeeeeEeGk', 'kGeeesssseeGk', '.kGeesssseGk.', '..kGeeseeGk..', '...kGGGGGk...', '....kkkkk....']),
    ('Windmill', -122.5092, 37.7703, ['w.....w', '.w...w.', '..wnw..', '..nwn..', '.wnnnw.', 'w.nnn.w', '..nnn..', '.nnknn.', '.nnknn.', '.kkkkk.']),
    ('Alcatraz', -122.4222, 37.8270, ['y', 'kwk', 'w', 'w', 'gw.gg', 'kkkkkk']),
    ('City Hall', -122.4193, 37.7793, ['y', 'kyk', 'kwwwk', 'kwgwgwk', 'kkkkkkkkkk', 'kwwwwwwwwk', 'kwkwkwkwgk', 'kkkkkkkkkk']),
    ('Twin Peaks', -122.4475, 37.7525, ['..E...E..', '.EeE.EeE.', 'EeeeEeeeE']),
]
landmarks_out = []
for name, lon, lat, rows in LANDMARKS:
    x0, y0, w, h = stamp(rows, lon, lat)
    landmarks_out.append(dict(name=name, x=x0, y=y0, w=w, h=h))

Image.fromarray(px).save('public/map.png')
np.save('data/blocked.npy', blocked); np.save('data/land.npy', land & ~lake & ~outside)
np.save('data/park.npy', park)
json.dump(dict(W=W, H=H, landmarks=landmarks_out), open('data/map_meta.json', 'w'))
# neighbourhood label anchors (centroids of the mask)
labels = []
for name, m in nhood_masks.items():
    ys, xs = np.nonzero(m)
    if len(xs): labels.append(dict(name=name.replace('Financial District/South Beach', 'FiDi'), x=float(xs.mean()), y=float(ys.mean()), area=int(m.sum())))
for lm in landmarks_out:
    labels.append(dict(name=lm['name'], x=lm['x'] + lm['w'] / 2, y=lm['y'] - 4, landmark=True, bx=lm['x'], by=lm['y'], bw=lm['w'], bh=lm['h'], area=0))
json.dump(labels, open('public/labels.json', 'w'))
np.save('data/nhood_names.npy', np.array(list(nhood_masks.keys())))
np.save('data/nhood_stack.npy', np.stack(list(nhood_masks.values())))
print('ok', W, H)

# masks for the isometric renderer
np.savez_compressed('data/masks.npz', water=water, lake=lake, land=land, park=park, wood=wood, beach=beach,
                    outside=outside, res=res, maj=maj, hwy=hwy, pier=pier)
