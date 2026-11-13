import re, json, html, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
UA = {'User-Agent': 'Mozilla/5.0 (map-project)'}
BASE = 'https://theagentbenchmark.com'
os.makedirs('data/pages', exist_ok=True)
L = json.load(open('data/list.json'))
def get(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0: return True
    for i in range(3):
        try:
            d = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
            open(path, 'wb').write(d); time.sleep(0.25); return True
        except Exception as e: time.sleep(2 + 3*i)
    return False
def work(a):
    get(f"{BASE}/agents/{a['slug']}/", f"data/pages/{a['slug']}.html")
    get(BASE + a['logo'], 'public/logos/' + os.path.basename(a['logo']))
with ThreadPoolExecutor(4) as ex: list(ex.map(work, L))
for a in L:
    p = f"data/pages/{a['slug']}.html"
    if not os.path.exists(p): continue
    s = open(p, encoding='utf-8', errors='ignore').read()
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S)
    t = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t)))
    m = re.search(r' Location (.+?) (?:Status|Team|Hiring|YC profile|LinkedIn|X |The job)', t)
    a['location'] = m.group(1).strip() if m else None
    m = re.search(r'<a[^>]*href="(https?://[^"]+)"[^>]*>\s*Visit site', s)
    a['site'] = m.group(1) if m else None
    m = re.search(r'href="(https://www\.ycombinator\.com/companies/[^"]+)"', s); a['yc'] = m.group(1) if m else None
json.dump(L, open('data/agents.json', 'w'), indent=1)
from collections import Counter
print(Counter(a.get('location') for a in L).most_common(25))
