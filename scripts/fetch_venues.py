"""Add venue details from each event's Luma page to public/events.json.

For every event, reads the page's __NEXT_DATA__ and keeps the venue name, address,
neighborhood and coordinates when the host made them public. Events already
enriched are skipped unless --refresh is passed.
"""
import json
import pathlib
import re
import sys
import time
import urllib.request

EVENTS = pathlib.Path(__file__).resolve().parent.parent / "public" / "events.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def find(obj, key):
    """First value for key anywhere in a nested dict/list."""
    if isinstance(obj, dict):
        if key in obj and obj[key]:
            return obj[key]
        for v in obj.values():
            r = find(v, key)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find(v, key)
            if r:
                return r
    return None


def venue_for(url):
    req = urllib.request.Request(url, headers={"user-agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return {"venue_status": "no-data"}
    data = json.loads(m.group(1))
    event = find(data, "event") or {}
    geo = event.get("geo_address_info") or find(data, "geo_address_info") or {}
    coord = event.get("coordinate") or geo.get("place_coordinate") or {}
    vis = event.get("geo_address_visibility") or find(data, "geo_address_visibility")
    out = {
        "venue": geo.get("address"),
        "address": geo.get("full_address"),
        "short_address": geo.get("short_address"),
        "neighborhood": geo.get("sublocality"),
        "city": geo.get("city"),
        "place_id": geo.get("place_id"),
        "lat": coord.get("latitude"),
        "lng": coord.get("longitude"),
        "venue_visibility": vis,
    }
    return {k: v for k, v in out.items() if v is not None}


def main():
    refresh = "--refresh" in sys.argv
    rows = json.loads(EVENTS.read_text())
    for i, e in enumerate(rows):
        if not refresh and "venue_visibility" in e:
            continue
        try:
            e.update(venue_for(e["link"]))
        except Exception as err:  # keep going; one bad page shouldn't stop the run
            e["venue_status"] = f"error: {err}"
        print(f"{i + 1:3d}/{len(rows)} {e.get('venue') or '-':40.40} {e.get('neighborhood') or '':22.22} {e['name'][:50]}")
        time.sleep(0.6)
    EVENTS.write_text(json.dumps(rows, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
