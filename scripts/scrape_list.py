import re, json, html, sys, urllib.request
src = sys.argv[1]
a = open(src).read()
rows = re.findall(r'<li data-cat="([^"]*)" data-market="([^"]*)" data-maker="([^"]*)"[^>]*>(.*?)</li>', a, re.S)
out, seen = [], set()
for cat, market, maker, body in rows:
    m = re.search(r'href="/agents/([^/"]+)/"', body)
    if not m or m.group(1) in seen: continue
    slug = m.group(1); seen.add(slug)
    g = lambda p: (lambda x: html.unescape(x.group(1)).strip() if x else None)(re.search(p, body, re.S))
    out.append(dict(slug=slug, name=g(r'class="ar-n">(.*?)<'), job=g(r'class="ar-tag">(.*?)<'),
        batch=g(r'class="ar-batch">(.*?)<'), line=g(r'class="ar-line">(.*?)<'),
        rank=int(g(r'data-rank-cell>(\d+)<') or 0), score=float(g(r'title="Score out of 10">([\d.]+)<') or 0),
        logo=g(r'<img src="([^"]+)"'), cat=cat, market=market, maker=maker))
json.dump(out, open('data/list.json','w'), indent=1)
print(len(out), out[0], out[-1], sep='\n')
