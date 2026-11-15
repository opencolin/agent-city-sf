"""Animated satellite loop of fog and low clouds over the Bay Area, as a WebP.

Takes the last two hours of NOAA GOES-West GeoColor frames for the Pacific Southwest
sector (public domain, NOAA/NESDIS/STAR), crops them to the Bay Area and stamps the
local time on each frame. GeoColor shows low clouds and fog in blue-white at night.
Cached at the edge for 10 minutes; a new frame arrives every 5.
"""
import io
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

BASE = "https://cdn.star.nesdis.noaa.gov/GOES18/ABI/SECTOR/psw/GEOCOLOR/"
UA = {"user-agent": "buildweek-fog-loop/1.0"}
CROP = (500, 1000, 860, 1290)  # Bay Area, from Point Reyes to San Jose, in the 2400x2400 frame
SCALE = 2
FRAMES = 12  # every other 5-minute frame: two hours
PT = ZoneInfo("America/Los_Angeles")


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def stamp(name):
    """20263192046_GOES18-... -> datetime (year, day of year, HHMM, UTC)."""
    m = re.match(r"(\d{4})(\d{3})(\d{2})(\d{2})_", name)
    y, doy, hh, mm = map(int, m.groups())
    return datetime(y, 1, 1, hh, mm, tzinfo=timezone.utc) + timedelta(days=doy - 1)


def frame(name):
    im = Image.open(io.BytesIO(get(BASE + name))).convert("RGB").crop(CROP)
    im = im.resize((im.width * SCALE, im.height * SCALE), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    label = stamp(name).astimezone(PT).strftime("%-I:%M %p").lower()
    font = ImageFont.load_default(size=22)
    x, y = 14, im.height - 38
    box = d.textbbox((x, y), label, font=font)
    d.rectangle((box[0] - 8, box[1] - 6, box[2] + 8, box[3] + 6), fill=(20, 18, 16))
    d.text((x, y), label, font=font, fill=(240, 236, 226))
    return im


def build():
    names = sorted(set(re.findall(r'href="(\d{11}_GOES18-ABI-psw-GEOCOLOR-2400x2400\.jpg)"', get(BASE).decode())))
    names = names[-FRAMES * 2::2]
    with ThreadPoolExecutor(6) as pool:
        frames = list(pool.map(frame, names))
    out = io.BytesIO()
    durations = [350] * (len(frames) - 1) + [1600]  # pause on the latest frame
    frames[0].save(out, "WEBP", save_all=True, append_images=frames[1:], duration=durations, loop=0, quality=72, method=4)
    return out.getvalue()


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            body, status = build(), 200
        except Exception as err:  # NOAA unreachable: let the page show its fallback
            body, status = str(err).encode(), 502
        self.send_response(status)
        self.send_header("content-type", "image/webp" if status == 200 else "text/plain")
        self.send_header("cache-control", "public, s-maxage=600, stale-while-revalidate=1800" if status == 200 else "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    import sys
    open(sys.argv[1] if len(sys.argv) > 1 else "fog.webp", "wb").write(build())
