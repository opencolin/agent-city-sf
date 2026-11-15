# San Francisco Build Week

Every hackathon, demo night and free lunch in San Francisco, ranked for you. Live at [buildweek.ai](https://buildweek.ai).

`public/` is the whole site. `index.html` is the newspaper-style front page (events from `events.json`). `map.html` is a real, north-up MapLibre map (OpenFreeMap vector tiles in a warm cartoon palette with 3D buildings) with hand-painted sprites in `sprites/` for landmarks, venues and sponsor blimps, and pins for every event placed at its real coordinates. `sf-painted.webp` on the front page was painted with GPT Image 2.5 over a real map from `scripts/make_reference.py`. `api/news.js` is a Vercel function serving Hacker News, YC launches and HackerNoon.

Refresh events from [eventhunt.ai](https://eventhunt.ai) (public endpoint, rate limited per hour; re-run to fill skipped queries):

```bash
python3 scripts/fetch_events.py   # public/events.json
python3 scripts/fetch_venues.py   # adds venue, address, neighborhood and coordinates from each Luma page
python3 scripts/fetch_calendars.py  # adds events from host Luma calendars (South Park Commons, AI Collective, Bond AI, Accelr8) and the aicollective.com/events feed; re-run fetch_venues.py after
```

## Run locally

```bash
python3 -m http.server 5173 -d public
```

## Earlier pixel map

The `scripts/` and `data/` folders still hold the pipeline for the original isometric pixel map (company data from The Agent Benchmark, streets from OpenStreetMap). Its page was removed from the site; it is in git history before the commit that removed `public/classic.html`.

## Credits

Map data © OpenStreetMap contributors, tiles by OpenFreeMap. Events: [eventhunt.ai](https://eventhunt.ai), originally listed on Luma. Weather: Open-Meteo and the National Weather Service. News: Hacker News and HackerNoon.
