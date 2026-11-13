# Agent City SF

An isometric pixel-art San Francisco with a signboard for every SF-based company on [The Agent Benchmark](https://theagentbenchmark.com/). Companies based elsewhere are listed in a side panel.

`public/` is the whole site: a static page that draws `city.png` on a canvas and overlays signs, flags, walkers, cars, boats and fog.

## Run locally

```bash
python3 -m http.server 5173 -d public
```

## Rebuild the data and the city

Requires Python 3 with Pillow and NumPy.

```bash
python3 scripts/scrape_list.py path/to/theagentbenchmark.html   # data/list.json
python3 scripts/scrape_details.py                                # data/agents.json, public/logos/
python3 scripts/render_map.py                                     # masks from OSM + DataSF
python3 scripts/place_logos.py                                    # public/agents.json, logo atlas
python3 scripts/render_iso.py                                     # public/city.png, depth.png, iso.json
```

`render_map.py` also needs `data/osm.json` and `data/osm_water.json`, Overpass API extracts (not checked in) of highways, parks, woods, beaches, piers and `natural=water` inside the bounding box 37.70,-122.53,37.84,-122.35. `data/neighborhoods.geojson` is DataSF's Analysis Neighborhoods.

`data/sf_addresses.json` holds hand-researched street addresses for the top 80 SF companies (47 exact, 7 neighborhood-level). Everyone else is placed within a typical startup neighborhood, so their block is approximate.

## Credits

Company data: The Agent Benchmark (October 2026). Streets and parks © OpenStreetMap contributors. Neighborhood boundaries: DataSF.
