"""Add each event's flyer (cover image) to public/events.json as "image".

Luma pages: the event's cover_url from __NEXT_DATA__ (the flyer itself, not Luma's social card).
Everything else (Meetup, Eventbrite, ...): the page's og:image. Events that already have an
image are skipped unless --refresh is passed.

  python3 scripts/fetch_covers.py
"""
import html as htmllib
import json
import pathlib
import re
import sys
import time
import urllib.request

EVENTS = pathlib.Path(__file__).resolve().parent.parent / "public" / "events.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def cover_for(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"user-agent": UA}), timeout=30) as r:
        page = r.read().decode("utf-8", "replace")
    if "luma.com/" in url:
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
        if m:
            data = json.loads(m.group(1))["props"]["pageProps"].get("initialData", {}).get("data") or {}
            cover = (data.get("event") or {}).get("cover_url")
            if cover:
                return cover
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', page) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', page)
    return htmllib.unescape(m.group(1)) if m else None


def main():
    refresh = "--refresh" in sys.argv
    rows = json.loads(EVENTS.read_text())
    n = 0
    for e in rows:
        if e.get("image") and not refresh or e.get("image_status") == "none" and not refresh:
            continue
        try:
            img = cover_for(e["link"])
        except Exception as err:
            print(f"  could not read {e['link']}: {err}")
            continue
        if img:
            e["image"] = img
            e.pop("image_status", None)
            n += 1
        else:
            e["image_status"] = "none"
        time.sleep(0.4)
    EVENTS.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f"{n} flyers added; {sum(1 for e in rows if e.get('image'))}/{len(rows)} events have one")


if __name__ == "__main__":
    main()
