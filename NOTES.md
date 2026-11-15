# Product Vision Notes

_Captured 2026-11-14 (dictated; AI note taker was down)._

## Core experience
- Land on the site → see a **map of San Francisco** plus a **calendar** of hackathons and events.
- Filter by event type: hackathons, investor demo days, pitch nights, etc.

## Sponsor banners (monetization)
- Companies that sponsor hackathons get their **banner/ad shown on the map** next to their events.
- Pitch to sponsors: sponsoring a hackathon = visibility on the map → encourages more hackathon sponsorship.

## Free credits resource
- Search for a company (e.g. a tool you want credits for) → find its upcoming hackathon → sign up → get free credits.
- Positions the site as the go-to place for free credits.

## Nomads / travelers
- Show where to get good **food, Wi-Fi, and co-working** space.
- Venues to feature on the map:
  - AWS Builder Loft
  - Frontier Tower
  - Shack 15 (occasional hackathons)
  - Entrepreneurs First
  - European Startup Embassy
  - Founders Inc.
  - HF0

## Founders / fundraising
- Show **investor demo days** and **pitch nights** on the map.
- Messaging: "Not getting much out of hackathons? You're going to the wrong events" — route founders to demo days/pitch nights.

## Artifacts page (build showcase)
- After building something (demo video, artifact), users can **share it on our artifacts page**.
- Or post anywhere with **#buildweek** and drop the social link in.
- We **auto-scrape** #buildweek posts from X/Twitter and LinkedIn.

## Event data & personalized recommendations
- Use **eventhunt.ai** to pull in events already scraped from **Luma**.
- Analyze the user's **LinkedIn + GitHub** → recommend which events they should attend.

## Sign-up: persona builder
- Sign-up should be a **very cool, interactive persona-creation page**.
- Collect **as much data as possible, but every field optional**.
- Why: match each user to events they'll **like** and where they're **most likely to be accepted**.

### Personas
1. **Broke hacker / engineer** — wants free food, a free place to work, even a place to sleep.
2. **Busy CTO / founder** — doesn't want to waste time on events where only ~10% of Luma sign-ups show up and the prizes are bad. Wants high-signal events only.
3. **Hosts** — struggle with distribution and get banned on Luma.
4. **Investors** — want to know if an event is worth the money, time, and merch they put in.
5. **Enterprise partners / sponsors** — companies that promote events or give out free credits and swag; same ROI question as investors.

## Event creation (for hosts)
- Hosts can **create their own events** on our platform.
- Hosts get access to **their contacts / attendee list**.
- We help **promote the event to the right people** (targeted by profile data).

## Open questions
- Event data sources beyond Luma via eventhunt.ai (Eventbrite, Cerebral Valley, manual)?
- Do we need eventhunt.ai partnership/API access, or do we scrape directly?
- How do we ask for LinkedIn/GitHub access (OAuth vs. pasting profile URLs)?
- Sponsor banner pricing / self-serve flow?
- How credits sign-up is tracked (affiliate links? partner API?)
- Venue data: who curates food/Wi-Fi/co-working ratings?
