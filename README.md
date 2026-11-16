# San Francisco Build Week

Every hackathon, demo night and free lunch in San Francisco, ranked for you. Live at [buildweek.ai](https://buildweek.ai).

`public/` is the whole site. `index.html` is the newspaper-style front page (events from `events.json`). `map.html` is a real, north-up MapLibre map (OpenFreeMap vector tiles in a warm cartoon palette with 3D buildings) with hand-painted sprites in `sprites/` for landmarks, venues and sponsor blimps, and pins for every event placed at its real coordinates. `sf-painted.webp` on the front page was painted with GPT Image 2.5 over a real map from `scripts/make_reference.py`. `api/news.js` is a Vercel function serving Hacker News, YC launches and HackerNoon.

Refresh events from [eventhunt.ai](https://eventhunt.ai) (public endpoint, rate limited per hour; re-run to fill skipped queries):

```bash
python3 scripts/fetch_events.py   # public/events.json
python3 scripts/fetch_venues.py   # adds venue, address, neighborhood and coordinates from each Luma page
python3 scripts/fetch_covers.py     # adds each event's flyer (Luma cover, or og:image elsewhere)
python3 scripts/fetch_calendars.py  # adds events from host Luma calendars (South Park Commons, AI Collective, Bond AI, Accelr8) and the aicollective.com/events feed; re-run fetch_venues.py after
```

## Daily agent

`scripts/daily_agent.py` runs every morning at 6 AM Pacific on a Tenki runner (`.github/workflows/daily-agent.yml`) and commits what changed, which redeploys the site. It:

1. reruns the event fetchers above;
2. searches the web with [Tavily](https://tavily.com), and X with [AIsa](https://aisa.one), for Bay Area hackathons, demo days and meetups we're missing, and for posts tagged #buildweek, #buildswag and #brunchlife;
3. adds new Bay Area events in the next 30 days, reading Luma pages directly and other pages with Claude;
4. puts Bay Area posts in `public/social.json` for the Style and Brunch sections, drops past events, and writes a run report to `public/agent.json`, which the front page shows in the dateline.

Setup: install the Tenki GitHub App on this repo, then add the repo secrets `TAVILY_API_KEY`, `AISA_API_KEY` and `ANTHROPIC_API_KEY`. Run it from the Actions tab ("Daily agent", with "dry run" to only log), or locally:

```bash
python3 scripts/daily_agent.py --dry-run
```

## Run locally

```bash
python3 -m http.server 5173 -d public
```

## Earlier pixel map

The `scripts/` and `data/` folders still hold the pipeline for the original isometric pixel map (company data from The Agent Benchmark, streets from OpenStreetMap). Its page was removed from the site; it is in git history before the commit that removed `public/classic.html`.

## Credits

Map data © OpenStreetMap contributors, tiles by OpenFreeMap. Events: [eventhunt.ai](https://eventhunt.ai), originally listed on Luma. Weather: Open-Meteo and the National Weather Service. News: Hacker News and HackerNoon. Swag photos in `public/swag/` are Build Week's own, plus three from Wikimedia Commons (Mind Booster Noori, CC0; Ainali, CC BY 4.0; Prtksxna, CC BY-SA 4.0), credited on each tile.
