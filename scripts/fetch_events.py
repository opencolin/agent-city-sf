"""Pull upcoming Bay Area events from eventhunt.ai's public ask endpoint into public/events.json.

The public endpoint is rate limited per hour; questions that get a 429 are skipped
and the previous events.json entries are kept.
"""
import json
import pathlib
import re
import urllib.error
import urllib.request

OUT = pathlib.Path(__file__).resolve().parent.parent / "public" / "events.json"
API = "https://eventhunt.ai/api/ask/public"
BAY = re.compile(r"San Francisco|Berkeley|Oakland|Palo Alto|Mountain View|Sunnyvale|San Jose|Menlo|Redwood|San Mateo", re.I)

QUESTIONS = [
    ("hackathon", "Hackathons this weekend"),
    ("hackathon", "Hackathons in San Francisco in the next two weeks"),
    ("demo", "Demo days and pitch nights in San Francisco in the next month"),
    ("talk", "AI talks and meetups in San Francisco next week"),
]


def ask(q):
    req = urllib.request.Request(API, data=json.dumps({"question": q}).encode(),
                                 headers={"content-type": "application/json", "user-agent": "agent-city-sf"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"  {e.code} for {q!r}, skipped")
        return None


def main():
    old = {e["link"]: e for e in json.loads(OUT.read_text())} if OUT.exists() else {}
    events = dict(old)
    for kind, q in QUESTIONS:
        j = ask(q)
        if not j:
            continue
        n = 0
        for e in j.get("events", []):
            if not BAY.search(e.get("location") or ""):
                continue
            n += 1
            events[e["link"]] = {
                "name": e["name"], "date": e["date"], "time": e.get("time"),
                "location": e["location"], "hosts": e.get("hosts", [])[:4],
                "link": e["link"], "source": e.get("source"), "score": e.get("score", 0),
                "kind": events.get(e["link"], {}).get("kind", kind),
            }
        print(f"  {n:3d} Bay Area events for {q!r}")
    rows = sorted(events.values(), key=lambda e: (e["date"], e["time"] or ""))
    OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f"{len(rows)} events -> {OUT}")


if __name__ == "__main__":
    main()
