"""Compose a north-up reference map from label-free Esri basemap tiles for a bounding box.

The painted maps are generated on top of these so the coastline and streets match the
real world, and the same bounds are used to place pins (Web Mercator, north up).

  python3 scripts/make_reference.py sf  out.png
  python3 scripts/make_reference.py bay out.png
"""
import io
import json
import math
import sys
import time
import urllib.request

from PIL import Image

# West/east are derived so the Web Mercator crop has exactly the given aspect ratio.
VIEWS = {
    "sf": {"south": 37.700, "north": 37.835, "center_lng": -122.4300, "zoom": 13, "aspect": 16 / 9},
    "bay": {"south": 37.250, "north": 37.930, "center_lng": -122.2200, "zoom": 11, "aspect": 4 / 3},
}
TILE = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"  # Esri, no labels
UA = "buildweek-map-reference/1.0"


def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def bounds(v):
    """West/east so the crop has the view's aspect ratio in Web Mercator."""
    h = merc_y(v["north"]) - merc_y(v["south"])
    w_deg = math.degrees(h * v["aspect"])
    return v["center_lng"] - w_deg / 2, v["center_lng"] + w_deg / 2


def to_px(lat, lng, z):
    n = 256 * 2 ** z
    x = (lng + 180) / 360 * n
    y = (1 - merc_y(lat) / math.pi) / 2 * n
    return x, y


def main():
    name, out = sys.argv[1], sys.argv[2]
    v = VIEWS[name]
    west, east = bounds(v)
    z = v["zoom"]
    x0, y0 = to_px(v["north"], west, z)
    x1, y1 = to_px(v["south"], east, z)
    canvas = Image.new("RGB", (math.ceil(x1) // 256 * 256 + 256 - math.floor(x0) // 256 * 256,
                               math.ceil(y1) // 256 * 256 + 256 - math.floor(y0) // 256 * 256))
    tx0, ty0 = math.floor(x0) // 256, math.floor(y0) // 256
    for ty in range(ty0, math.ceil(y1) // 256 + 1):
        for tx in range(tx0, math.ceil(x1) // 256 + 1):
            req = urllib.request.Request(TILE.format(z=z, x=tx, y=ty), headers={"user-agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                canvas.paste(Image.open(io.BytesIO(r.read())).convert("RGB"), ((tx - tx0) * 256, (ty - ty0) * 256))
            time.sleep(0.05)
    crop = canvas.crop((round(x0 - tx0 * 256), round(y0 - ty0 * 256), round(x1 - tx0 * 256), round(y1 - ty0 * 256)))
    crop.save(out)
    print(json.dumps({"view": name, "north": v["north"], "south": v["south"], "west": round(west, 5), "east": round(east, 5), "size": crop.size}))


if __name__ == "__main__":
    main()
