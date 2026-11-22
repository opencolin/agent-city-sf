"""The Build Week daily agent: refreshes events, finds ones we're missing, and fills the social pages.

Runs once a day on a Tenki runner (.github/workflows/daily-agent.yml) and commits what changed,
which redeploys buildweek.ai. Steps:

  1. Refresh the known sources: eventhunt.ai, the host Luma calendars and the AI Collective feed.
  2. Discover: Tavily web searches for Bay Area builder events, and AIsa X searches for
     #buildweek and event links people are sharing.
  3. Read each new event link. Luma pages are parsed directly; other pages go to an LLM that
     pulls out the name, date, time and place. Only Bay Area events in the next 30 days are kept.
  4. Pick the Bay Area posts tagged #buildweek, #buildswag or #brunchlife for public/social.json.
  5. Drop past events, add venues and flyers, and write public/agent.json (what ran, what was added).

Environment:
  TAVILY_API_KEY     web search (tavily.com)
  AISA_API_KEY       X search, and the model that reads non-Luma event pages and picks relevant
                     posts (aisa.one; without it only Luma links are added and posts are picked by keyword)
  AGENT_MODEL        model id on AIsa (default claude-sonnet-5-5)

  python3 scripts/daily_agent.py            # full run
  python3 scripts/daily_agent.py --dry-run  # discover and print, write nothing
"""
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_calendars import BAY, PT, UA, is_dupe, kind_of, row  # noqa: E402

EVENTS = ROOT / "public" / "events.json"
SOCIAL = ROOT / "public" / "social.json"
REPORT = ROOT / "public" / "agent.json"
DAYS = 30
DRY = "--dry-run" in sys.argv
TODAY = dt.datetime.now(PT).date()
UNTIL = TODAY + dt.timedelta(days=DAYS)
MONTH = TODAY.strftime("%B %Y")

EVENT_HOSTS = ("luma.com", "lu.ma", "partiful.com", "eventbrite.com", "meetup.com", "cerebralvalley.ai", "devpost.com")
EVENT_PATH = {"eventbrite.com": r"^/e/", "partiful.com": r"^/e/", "meetup.com": r"/events/\d+"}
TAVILY_QUERIES = [
    f"AI hackathon San Francisco {MONTH}",
    f"hackathon Bay Area this weekend {MONTH}",
    f"demo day San Francisco {MONTH} startups",
    f"pitch night San Francisco {MONTH}",
    f"AI meetup San Francisco this week {MONTH}",
    f"builder events SoMa San Francisco {MONTH} luma",
    f"agents hackathon Palo Alto OR Berkeley OR Oakland {MONTH}",
    "#buildweek San Francisco",
    "Cafe Compute San Francisco luma",
    "Cursor Cafe San Francisco",
    f"founder brunch OR builders breakfast San Francisco {MONTH}",
]
X_QUERIES = [
    ("#buildweek", "social"),
    ("#buildswag", "social"),
    ("#brunchlife (hackathon OR builders OR founders)", "social"),
    ('(hackathon OR "demo day" OR "pitch night") ("San Francisco" OR SF) (url:lu.ma OR url:luma.com) -filter:replies', "events"),
    ('("AI meetup" OR "builders dinner" OR hackathon) "Bay Area" (url:lu.ma OR url:luma.com OR url:partiful.com) -filter:replies', "events"),
]
SOCIAL_TAGS = {"buildweek", "buildswag", "brunchlife", "sfbuildweek"}

log = []


def say(msg):
    print(msg, flush=True)
    log.append(msg)


def http(url, data=None, headers=None, timeout=45):
    body = json.dumps(data).encode() if data is not None else None
    h = {"user-agent": UA["user-agent"], **({"content-type": "application/json"} if body else {}), **(headers or {})}
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ── 1. Known sources ─────────────────────────────────────────────────────────

def refresh_known():
    for script in ["fetch_events.py", "fetch_calendars.py"]:
        if DRY:
            continue
        try:
            out = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], capture_output=True, text=True, timeout=600)
            say(f"{script}: {(out.stdout.strip().splitlines() or ['no output'])[-1]}")
            if out.returncode:
                say(f"  {script} failed: {out.stderr.strip()[-300:]}")
        except Exception as err:
            say(f"{script} failed: {err}")


# ── 2. Discovery ─────────────────────────────────────────────────────────────

def tavily(query):
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return []
    d = json.loads(http("https://api.tavily.com/search", {
        "query": query, "search_depth": "advanced", "max_results": 15, "time_range": "month",
        "include_domains": list(EVENT_HOSTS) + ["x.com", "linkedin.com"], "include_domains_mode": "prefer",
        "include_raw_content": "text", "chunks_per_source": 3,
    }, {"authorization": f"Bearer {key}"}))
    return d.get("results", [])


def aisa_x(query):
    key = os.environ.get("AISA_API_KEY")
    if not key:
        return []
    q = urllib.parse.urlencode({"query": query, "queryType": "Latest"})
    d = json.loads(http(f"https://api.aisa.one/apis/v1/twitter/tweet/advanced_search?{q}", headers={"authorization": f"Bearer {key}"}))
    return d.get("tweets") or (d.get("data") or {}).get("tweets") or []


def event_link(url):
    """Canonical event URL, or None if it isn't an event page we can read."""
    u = urllib.parse.urlsplit(url.strip())
    host = u.netloc.lower().removeprefix("www.")
    if host in ("lu.ma", "luma.com"):
        slug = u.path.strip("/").split("/")[0]
        # Skip Luma's own pages and calendars we already read.
        if not slug or slug in {"discover", "home", "signin", "create", "explore", "sf", "pricing", "user", "calendar"} or "/" in u.path.strip("/"):
            return None
        return "https://luma.com/" + slug
    if any(host == h or host.endswith("." + h) for h in EVENT_HOSTS):
        # A single event, not a search or directory page (eventbrite.com/d/..., meetup.com/find/...).
        shape = EVENT_PATH.get(host.split(".", host.count(".") - 1)[-1])
        if shape and not re.search(shape, u.path):
            return None
        return urllib.parse.urlunsplit(("https", host, u.path.rstrip("/"), "", ""))
    return None


def tweet_urls(t):
    out = [u.get("expanded_url") or "" for u in (t.get("entities") or {}).get("urls") or []]
    card = (t.get("card") or {}).get("url") or ""
    return [u for u in out + [card] if u]


def discover():
    candidates, tweets = {}, []
    for q in TAVILY_QUERIES if os.environ.get("TAVILY_API_KEY") else []:
        try:
            res = tavily(q)
        except Exception as err:
            say(f"tavily {q!r} failed: {err}")
            continue
        n = 0
        for r in res:
            link = event_link(r.get("url", ""))
            if link and link not in candidates:
                candidates[link] = {"title": r.get("title"), "text": (r.get("raw_content") or r.get("content") or "")[:6000], "via": "tavily"}
                n += 1
        say(f"tavily {q!r}: {len(res)} results, {n} event links")
        time.sleep(0.3)
    for q, purpose in X_QUERIES if os.environ.get("AISA_API_KEY") else []:
        try:
            res = aisa_x(q)
        except Exception as err:
            say(f"aisa {q!r} failed: {err}")
            continue
        n = 0
        for t in res:
            t["_purpose"] = purpose
            tweets.append(t)
            for u in tweet_urls(t):
                link = event_link(u)
                if link and link not in candidates:
                    candidates[link] = {"title": None, "text": t.get("text", ""), "via": "x"}
                    n += 1
        say(f"aisa {q!r}: {len(res)} posts, {n} event links")
    return candidates, tweets


# ── 3. Reading event pages ───────────────────────────────────────────────────

def luma_event(link):
    html = http(link)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    data = json.loads(m.group(1))["props"]["pageProps"].get("initialData", {}).get("data") or {}
    if not data.get("event"):
        return None
    hosts = data.get("hosts") or []
    source = (data.get("calendar") or {}).get("name") or (hosts[0]["name"] if hosts else "Luma")
    r = row({"event": data["event"], "hosts": hosts}, source)
    if r:
        r["found_by"] = "agent"
    return r


def llm(prompt, max_tokens=4000):
    key = os.environ.get("AISA_API_KEY")
    if not key:
        return None
    d = json.loads(http("https://api.aisa.one/v1/messages", {  # AIsa serves the Anthropic Messages API
        "model": os.environ.get("AGENT_MODEL", "claude-sonnet-5-5"), "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }, {"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout=180))
    text = "".join(b.get("text", "") for b in d.get("content", []))
    m = re.search(r"\[.*\]|\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else None


def extract_events(pages):
    """LLM pass over non-Luma event pages. pages: {link: {title, text}} -> list of rows."""
    if not pages or not os.environ.get("AISA_API_KEY"):
        return []
    items = [{"id": i, "url": u, "title": p["title"], "text": p["text"][:4000]} for i, (u, p) in enumerate(pages.items())]
    out = []
    for i in range(0, len(items), 12):
        batch = items[i:i + 12]
        res = llm(f"""Today is {TODAY.isoformat()} in San Francisco. Below are web pages that may be event listings.
For each one that is a single in-person event for builders (hackathon, demo day, pitch night, tech talk, meetup,
founder dinner) happening in the San Francisco Bay Area between {TODAY.isoformat()} and {UNTIL.isoformat()},
return an object. Skip online-only events, recurring series pages, past events and anything you are not sure about.
Never guess a date or a city: if the page doesn't state it, skip the page.

Return only a JSON array of objects with keys: id, name, date (YYYY-MM-DD), time (like "6:00 PM" or null),
city, venue (or null), hosts (array of org names, up to 4), kind ("hackathon", "demo" or "talk").

Pages:
{json.dumps(batch, ensure_ascii=False)}""") or []
        for e in res if isinstance(res, list) else []:
            src = next((b for b in batch if b["id"] == e.get("id")), None)
            if not src or not e.get("date") or not BAY.search(e.get("city") or ""):
                continue
            out.append({k: v for k, v in {
                "name": e["name"].strip(), "date": e["date"], "time": e.get("time"), "location": f"{e['city']}, CA",
                "hosts": e.get("hosts") or [], "link": src["url"], "source": (e.get("hosts") or [urllib.parse.urlsplit(src["url"]).netloc])[0],
                "score": 0, "kind": e.get("kind") if e.get("kind") in ("hackathon", "demo", "talk") else kind_of(e["name"]),
                "venue": e.get("venue"), "city": e["city"], "venue_visibility": "public" if e.get("venue") else "guests-only",
                "found_by": "agent",
            }.items() if v is not None})
    return out


def add_events(candidates):
    events = {e["link"]: e for e in json.loads(EVENTS.read_text())}
    new = {u: c for u, c in candidates.items() if u not in events}
    say(f"{len(candidates)} event links found, {len(new)} not on the site yet")
    rows = []
    for link in [u for u in new if "luma.com/" in u]:
        try:
            r = luma_event(link)
            if r:
                rows.append(r)
        except Exception as err:
            say(f"  could not read {link}: {err}")
        time.sleep(0.5)
    luma_rows = len(rows)
    rows += extract_events({u: c for u, c in new.items() if "luma.com/" not in u})
    added, dated_out, dupes = [], 0, 0
    for r in rows:
        if not (TODAY.isoformat() <= r["date"] <= UNTIL.isoformat()):
            dated_out += 1
            continue
        if is_dupe(r, events):
            dupes += 1
            continue
        events[r["link"]] = r
        added.append(r)
    luma_new = sum("luma.com/" in u for u in new)
    say(f"  {luma_new} Luma links -> {luma_rows} Bay Area events; {len(new) - luma_new} other pages -> {len(rows) - luma_rows} events; "
        f"{dated_out} outside the next {DAYS} days, {dupes} already listed under another link")
    for r in added:
        say(f"  + {r['date']} {r['name'][:70]} ({r['link']})")
    return events, added


# ── 4. Social ────────────────────────────────────────────────────────────────

def post_of(t):
    media = ((t.get("extendedEntities") or {}).get("media") or (t.get("entities") or {}).get("media") or [])
    image = next((m.get("media_url_https") for m in media if m.get("type") in (None, "photo") and m.get("media_url_https")), None)
    tags = sorted({h["text"].lower() for h in (t.get("entities") or {}).get("hashtags") or []})
    text = re.sub(r"\s*https://t\.co/\S+", "", t.get("text", "")).strip()
    author = (t.get("author") or {}).get("userName")
    created = t.get("createdAt")
    try:
        created = dt.datetime.strptime(created, "%a %b %d %H:%M:%S %z %Y").isoformat()
    except Exception:
        pass
    return {"url": t.get("url"), "author": f"@{author}" if author else None, "caption": text[:180], "image": image,
            "tags": tags, "at": created, "likes": t.get("likeCount", 0)}


def pick_posts(tweets):
    """Posts about the Bay Area builder scene with one of our tags."""
    posts = {}
    for t in tweets:
        if t.get("_purpose") != "social" or t.get("retweeted_tweet") or t.get("isReply"):
            continue
        p = post_of(t)
        if p["url"] and SOCIAL_TAGS & set(p["tags"]):
            posts[p["url"]] = p
    posts = list(posts.values())
    if not posts:
        return []
    if os.environ.get("AISA_API_KEY"):
        keep = llm(f"""These X posts use #buildweek, #buildswag or #brunchlife. "Build Week" is also the name of unrelated
programs in other cities and countries. Keep only posts about the San Francisco Bay Area builder scene: hackathons, demos,
builders, swag, or brunch with builders in SF or the Bay Area. Drop spam, ads, crypto shilling, and anything elsewhere.
Return only a JSON array of the kept post urls.

{json.dumps([{"url": p["url"], "author": p["author"], "text": p["caption"]} for p in posts], ensure_ascii=False)}""", 2000)
        keep = set(keep or [])
        return [p for p in posts if p["url"] in keep]
    # Without an LLM, require an explicit Bay Area mention.
    return [p for p in posts if BAY.search(p["caption"]) or re.search(r"\bSF\b|Bay Area", p["caption"])]


def merge_social(picked):
    old = json.loads(SOCIAL.read_text()) if SOCIAL.exists() else []
    by = {p["url"]: p for p in old}
    added = [p for p in picked if p["url"] not in by]
    for p in picked:
        by[p["url"]] = {**by.get(p["url"], {}), **p}
    rows = sorted(by.values(), key=lambda p: p.get("at") or "", reverse=True)[:80]
    return rows, added


# ── 5. Write ─────────────────────────────────────────────────────────────────

def main():
    started = dt.datetime.now(PT)
    say(f"Build Week agent, {started:%a %b %-d %Y %-I:%M %p} PT{' (dry run)' if DRY else ''}")
    for k in ["TAVILY_API_KEY", "AISA_API_KEY"]:
        if not os.environ.get(k):
            say(f"note: {k} is not set; that step is skipped")
    refresh_known()
    candidates, tweets = discover()
    events, added = add_events(candidates)
    keep_from = (TODAY - dt.timedelta(days=1)).isoformat()
    rows = sorted((e for e in events.values() if e["date"] >= keep_from), key=lambda e: (e["date"], e.get("time") or ""))
    dropped = len(events) - len(rows)
    social, social_added = merge_social(pick_posts(tweets))
    say(f"{len(added)} events added, {dropped} past events dropped, {len(rows)} on the site; {len(social_added)} new posts, {len(social)} in social.json")
    if DRY:
        return
    EVENTS.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    SOCIAL.write_text(json.dumps(social, indent=1, ensure_ascii=False))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_venues.py")], timeout=900)  # only reads events without one
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_covers.py")], timeout=900)  # flyers for anything new
    REPORT.write_text(json.dumps({
        "ran_at": started.isoformat(timespec="minutes"), "events": len(rows), "added": [
            {k: e.get(k) for k in ("name", "date", "link", "source")} for e in added],
        "dropped": dropped, "posts_added": len(social_added), "log": log,
    }, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
