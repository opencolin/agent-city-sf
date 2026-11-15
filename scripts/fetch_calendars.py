"""Add upcoming Bay Area events from host Luma calendars to public/events.json.

eventhunt.ai misses some hosts, so this reads their Luma calendars directly. Venue
fields come from the same calendar response, so fetch_venues.py isn't needed for them.

  python3 scripts/fetch_calendars.py
"""
import datetime as dt
import json
import pathlib
import re
import time
import urllib.request
from zoneinfo import ZoneInfo

OUT = pathlib.Path(__file__).resolve().parent.parent / "public" / "events.json"
UA = {"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}
PT = ZoneInfo("America/Los_Angeles")
DAYS = 30
BAY = re.compile(r"San Francisco|Berkeley|Oakland|Palo Alto|Mountain View|Sunnyvale|San Jose|Menlo|Redwood|San Mateo|Stanford|Cupertino|Santa Clara|Burlingame", re.I)

# Luma calendar slug -> the source name used on the site (matches eventhunt's naming where it overlaps).
CALENDARS = {
    "southparkcommons-events": "South Park Commons",
    "genai-collective": "The AI Collective",
    "genai-sf": "Bond AI SF",
    "accelr8": "Accelr8",
}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def kind_of(name):
    if re.search(r"hack", name, re.I):
        return "hackathon"
    if re.search(r"demo|pitch|showcase|show-and-tell", name, re.I):
        return "demo"
    return "talk"


def row(entry, source):
    ev = entry["event"]
    geo = ev.get("geo_address_info") or {}
    city = geo.get("city") or ""
    if not BAY.search(" ".join([city, geo.get("full_address") or "", geo.get("city_state") or ""])):
        return None
    start = dt.datetime.fromisoformat(ev["start_at"].replace("Z", "+00:00")).astimezone(PT)
    coord = ev.get("coordinate") or geo.get("place_coordinate") or {}
    out = {
        "name": ev["name"].strip(),
        "date": start.strftime("%Y-%m-%d"),
        "time": start.strftime("%-I:%M %p"),
        "location": geo.get("city_state") or (city + ", CA"),
        "hosts": [h["name"] for h in entry.get("hosts") or [] if h.get("name")][:4],
        "link": "https://luma.com/" + ev["url"],
        "source": source,
        "score": 0,
        "kind": kind_of(ev["name"]),
        "venue": geo.get("address"),
        "address": geo.get("full_address"),
        "short_address": geo.get("short_address"),
        "neighborhood": geo.get("sublocality"),
        "city": city or None,
        "place_id": geo.get("place_id"),
        "lat": coord.get("latitude"),
        "lng": coord.get("longitude"),
        "venue_visibility": ev.get("geo_address_visibility"),
    }
    return {k: v for k, v in out.items() if v is not None}


def main():
    events = {e["link"]: e for e in json.loads(OUT.read_text())} if OUT.exists() else {}
    until = dt.datetime.now(PT).date() + dt.timedelta(days=DAYS)
    for slug, source in CALENDARS.items():
        html = get("https://luma.com/" + slug)
        data = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S).group(1))
        cal = data["props"]["pageProps"]["initialData"]["data"]["calendar"]["api_id"]
        entries = json.loads(get(f"https://api.lu.ma/calendar/get-items?calendar_api_id={cal}&period=future&pagination_limit=100"))["entries"]
        n = 0
        for entry in entries:
            r = row(entry, source)
            if not r or r["date"] > until.isoformat():
                continue
            old = events.get(r["link"], {})
            events[r["link"]] = {**r, "kind": old.get("kind", r["kind"]), "score": old.get("score", 0)}
            n += 1
        print(f"  {n:3d} Bay Area events from {source}")
        time.sleep(0.5)
    rows = sorted(events.values(), key=lambda e: (e["date"], e.get("time") or ""))
    OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f"{len(rows)} events -> {OUT}")


if __name__ == "__main__":
    main()
