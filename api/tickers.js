// Vercel function: GET /api/tickers
// Latest price and day change for the companies that matter to builders, from Yahoo Finance's chart
// endpoint (no key; not readable from the browser because of CORS). Cached at the edge for 5 minutes.

export const TICKERS = [
  ["NVDA", "NVIDIA"], ["AMD", "AMD"], ["META", "Meta"], ["SPCX", "SpaceX"], ["MSFT", "Microsoft"],
  ["GOOGL", "Alphabet"], ["AAPL", "Apple"], ["AMZN", "Amazon"], ["TSLA", "Tesla"], ["TSM", "TSMC"],
  ["AVGO", "Broadcom"], ["ORCL", "Oracle"], ["PLTR", "Palantir"], ["CRWV", "CoreWeave"], ["ARM", "Arm"],
  ["^IXIC", "Nasdaq"], ["^GSPC", "S&P 500"], ["BTC-USD", "Bitcoin"],
];

async function quote([symbol, name]) {
  const r = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=1d&interval=1d`, {
    headers: { "user-agent": "Mozilla/5.0 (compatible; buildweek-tickers/1.0)" },
  });
  if (!r.ok) throw new Error(`${symbol}: ${r.status}`);
  const m = (await r.json()).chart.result[0].meta;
  const price = m.regularMarketPrice, prev = m.chartPreviousClose ?? m.previousClose;
  return { symbol: symbol.replace(/^\^/, "").replace("-USD", ""), name, price, change: prev ? (price - prev) / prev * 100 : null, at: m.regularMarketTime };
}

export default async function handler(req, res) {
  const results = await Promise.allSettled(TICKERS.map(quote));
  const quotes = results.filter(r => r.status === "fulfilled").map(r => r.value);
  res.setHeader("cache-control", quotes.length ? "public, s-maxage=300, stale-while-revalidate=900" : "no-store");
  res.status(quotes.length ? 200 : 502).json({ quotes });
}
