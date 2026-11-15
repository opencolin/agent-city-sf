# San Francisco Build Week

Every hackathon, demo night and free lunch in San Francisco, ranked for you. Live at [buildweek.ai](https://buildweek.ai).

`public/` is the whole site. `index.html` is the newspaper-style front page (events from `events.json`). `map.html` is the hand-painted map: a Bay Area view (`bay-painted.webp`) with events pinned by city, and a San Francisco view (`sf-painted.webp`) with venues and landmarks. Both paintings were generated with GPT Image 2.5. `api/news.js` is a Vercel function serving Hacker News, YC launches and HackerNoon.

Refresh events from [eventhunt.ai](https://eventhunt.ai) (public endpoint, rate limited per hour; re-run to fill skipped queries):

```bash
python3 scripts/fetch_events.py   # public/events.json
python3 scripts/fetch_venues.py   # adds venue, address, neighborhood and coordinates from each Luma page
```

## Run locally

```bash
python3 -m http.server 5173 -d public
```

## Earlier pixel map

The `scripts/` and `data/` folders still hold the pipeline for the original isometric pixel map (company data from The Agent Benchmark, streets from OpenStreetMap). Its page was removed from the site; it is in git history before the commit that removed `public/classic.html`.

## Credits

Events: [eventhunt.ai](https://eventhunt.ai), originally listed on Luma. Weather: Open-Meteo and the National Weather Service. News: Hacker News and HackerNoon.
