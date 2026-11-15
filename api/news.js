// Vercel function: GET /api/news
// Hacker News front page, recent Launch HN posts (YC companies) and the HackerNoon feed in one response.
// HackerNoon's RSS has no CORS header, so the page can't read it directly. Cached at the edge for 15 minutes.

const ALGOLIA = "https://hn.algolia.com/api/v1";

const cdata = (block, tag) => {
  const m = block.match(new RegExp(`<${tag}[^>]*>(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?</${tag}>`));
  return m ? m[1].trim() : "";
};
const decode = s => s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'");
const hnItem = h => ({
  title: h.title,
  url: h.url || `https://news.ycombinator.com/item?id=${h.objectID}`,
  discuss: `https://news.ycombinator.com/item?id=${h.objectID}`,
  points: h.points, comments: h.num_comments, author: h.author, at: h.created_at,
  site: h.url ? new URL(h.url).hostname.replace(/^www\./, "") : "news.ycombinator.com",
});

async function hackerNews() {
  const r = await fetch(`${ALGOLIA}/search?tags=front_page&hitsPerPage=30`);
  const j = await r.json();
  return j.hits.sort((a, b) => b.points - a.points).slice(0, 12).map(hnItem);
}

async function launches() {
  const r = await fetch(`${ALGOLIA}/search_by_date?query=%22Launch%20HN%22&tags=story&hitsPerPage=20`);
  const j = await r.json();
  return j.hits.filter(h => /^Launch HN:/i.test(h.title)).slice(0, 8).map(h => {
    const m = h.title.match(/^Launch HN:\s*(.*?)\s*\((YC [A-Z]\d{2})\)\s*[–-]\s*(.*)$/i);
    return { ...hnItem(h), company: m ? m[1] : h.title.replace(/^Launch HN:\s*/i, ""), batch: m ? m[2] : "", pitch: m ? m[3] : "" };
  });
}

async function hackerNoon() {
  const r = await fetch("https://hackernoon.com/feed", { headers: { "user-agent": "buildweek-news" } });
  const xml = await r.text();
  return [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)].map(([, it]) => ({
    title: decode(cdata(it, "title")),
    url: cdata(it, "link").replace(/\?source=rss$/, ""),
    dek: decode(cdata(it, "description")).replace(/<[^>]+>/g, "").slice(0, 220),
    author: decode(cdata(it, "dc:creator")),
    at: new Date(cdata(it, "pubDate")).toISOString(),
    tags: [...it.matchAll(/<category><!\[CDATA\[(.*?)\]\]><\/category>/g)].map(m => m[1]).slice(0, 3),
  }))
    // Drop listicle roundups and newsletters
    .filter(a => !/^\d+ Blog Posts To Learn About|^The HackerNoon Newsletter|^The TechBeat/i.test(a.title))
    .slice(0, 10);
}

export default async function handler(req, res) {
  const settle = p => p.catch(() => []);
  const [hn, launch, noon] = await Promise.all([settle(hackerNews()), settle(launches()), settle(hackerNoon())]);
  res.setHeader("Cache-Control", "public, s-maxage=900, stale-while-revalidate=3600");
  res.status(200).json({ updated: new Date().toISOString(), hn, launches: launch, hackernoon: noon });
}
