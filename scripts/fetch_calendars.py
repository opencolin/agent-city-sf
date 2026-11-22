"""Add upcoming Bay Area events from host Luma calendars and aicollective.com to public/events.json.

eventhunt.ai misses some hosts, so this reads their Luma calendars directly, plus the
AI Collective's event feed (its own chapter events and the nearby events it aggregates
from Luma, Meetup and Eventbrite). Run fetch_venues.py afterwards to fill in venues for
the Luma events from the feed.

  python3 scripts/fetch_calendars.py
"""
import datetime as dt
import json
import pathlib
import re
import time
import urllib.parse
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
    "cerebras": "Cerebras",  # hosts Cafe Compute
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
        "link": ev["url"] if ev["url"].startswith("http") else "https://luma.com/" + ev["url"],  # some list an outside page
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
        "image": ev.get("cover_url"),
    }
    return {k: v for k, v in out.items() if v is not None}


AIC = "https://www.aicollective.com/api/trpc/{}?batch=1&input={}"
AIC_QUERY = {"upcoming": True, "isOnline": False, "withinMiles": 50, "latitude": 37.6, "longitude": -122.25, "limit": 50}
CITY_FIX = {"Stanford": "Palo Alto"}


def link_of(url):
    return re.sub(r"^https?://(www\.)?lu\.ma/", "https://luma.com/", url.split("?")[0])


def aic(proc):
    """Every page of an AI Collective feed query."""
    out, offset = [], 0
    while True:
        q = urllib.parse.quote(json.dumps({"0": {"json": {**AIC_QUERY, "offset": offset}}}))
        d = json.loads(get(AIC.format(proc, q)))[0]["result"]["data"]["json"]
        out += d["events"]
        offset += AIC_QUERY["limit"]
        if not d["events"] or offset >= d.get("totalCount", 0):
            return out


def aic_row(e, source):
    start = dt.datetime.fromisoformat(e["startAt"].replace("Z", "+00:00")).astimezone(PT)
    city = CITY_FIX.get(e.get("city"), e.get("city")) or ("San Francisco" if e.get("chapterId") == "sf" else None)
    lat, lng = e.get("latitude") or e.get("geoLatitude"), e.get("longitude") or e.get("geoLongitude")
    out = {
        "name": e["title"].strip(), "date": start.strftime("%Y-%m-%d"), "time": start.strftime("%-I:%M %p"),
        "location": f"{city}, CA" if city else "Bay Area", "hosts": [], "link": link_of(e["url"]),
        "source": source, "score": 0, "kind": kind_of(e["title"] + " " + (e.get("format") or "")), "city": city,
    }
    if "luma.com/" not in out["link"]:  # no Luma page to read the venue from later
        out.update({"venue": e.get("venue"), "lat": lat, "lng": lng, "venue_visibility": "public" if e.get("venue") else "guests-only"})
    return {k: v for k, v in out.items() if v is not None}


DATE_WORD = re.compile(
    r"^(\d+(st|nd|rd|th)?|(mon|tues|wednes|thurs|fri|satur|sun)day|january|february|march|april|june|july|"
    r"august|september|october|november|december|sept)$"
)
FILLER = {"francisco", "event", "events", "night", "demo", "networking", "startup", "startups", "meetup",
          "with", "community", "tech", "business", "founders", "meeting", "social", "builders", "mixer"}


def words(name):
    return {w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) > 3}


def core(ws):
    """The words that say what the event is: no dates, weekdays or filler."""
    return {w for w in ws if w not in FILLER and not DATE_WORD.match(w)}


def overlap(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0


def is_dupe(r, events):
    """Within a day and most of the shorter title's words in the other: one event listed twice.
    At the same start time on the same day, half the core words is enough."""
    a, day = words(r["name"]), dt.date.fromisoformat(r["date"])
    for e in events.values():
        if abs((dt.date.fromisoformat(e["date"]) - day).days) <= 1:
            b = words(e["name"])
            if overlap(a, b) >= 0.6:
                return True
            if e["date"] == r["date"] and r.get("time") and e.get("time") == r["time"] and overlap(core(a), core(b)) >= 0.5:
                return True
    return False


def main():
    events = {e["link"]: e for e in json.loads(OUT.read_text())} if OUT.exists() else {}
    until = dt.datetime.now(PT).date() + dt.timedelta(days=DAYS)
    seen = {(e["date"], re.sub(r"\W", "", e["name"].lower())[:30]) for e in events.values()}
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
    for proc, source in [("events.getAll", "The AI Collective"), ("externalEvents.getAll", "aicollective.com")]:
        n = 0
        for e in aic(proc):
            r = aic_row(e, source)
            key = (r["date"], re.sub(r"\W", "", r["name"].lower())[:30])
            if r["date"] > until.isoformat() or r["link"] in events or key in seen or is_dupe(r, events):
                continue
            events[r["link"]] = r
            seen.add(key)
            n += 1
        print(f"  {n:3d} new events from {source} ({proc})")
    rows = sorted(events.values(), key=lambda e: (e["date"], e.get("time") or ""))
    OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f"{len(rows)} events -> {OUT}")


if __name__ == "__main__":
    main()
