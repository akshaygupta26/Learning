# Project State

**Last updated:** 2026-08-06 (session 04)

Read this before doing anything. It is the distilled current state — decisions
already settled, numbers already measured, traps already hit. Session logs hold
the reasoning; this holds the conclusions.

---

## What this is

A price database and decision-support tool for modern-era Pokémon singles.
Two goals, in priority order:

1. Learn the market-data → trade-decision → P&L-reconciliation loop. Relevant
   to the owner's job at eBay, starting **2026-08-17**.
2. Trade a **$100 bankroll** against it. Money is written off as tuition.

The system is the deliverable. Trading is the pressure test.

## Where things stand

| Phase | State |
| --- | --- |
| 0–1 · schema, fee model, TCGCSV ingester | Complete |
| 2 · market survey, 189-card watchlist | Complete |
| 3 · eBay Browse + title parsing | Built, **blocked on API credentials** |
| 5 · graded prices | Deferred, see Decisions |
| 6–7 · trade and reconcile | Not started |

Daily ingest runs unattended via GitHub Actions. 12 days of snapshots as of
2026-08-05. It works; leave it alone.

---

## Settled decisions

Do not relitigate these without new evidence.

- **Scope:** modern era only — Mega Evolution + Scarlet & Violet + Sword &
  Shield, 46 sets, English, raw singles. No Japanese, no sealed, no vintage.
- **Stack:** Python + SQLite + Jupyter. Pipeline is standard-library only, so
  it runs anywhere with no install step.
- **Aug 17 is a pivot, not a deadline.** The owner may sell after joining eBay
  and gets a reduced final value fee. Strategy is therefore **buy before,
  sell after** — accumulate now, sell at the discounted rate.
- **Fee rate is a config parameter, never a constant.** Retail is 13.25%; the
  employee rate is unknown until onboarding. `EBAY_FVF_RATE` in `.env`.
- **The DB is a build artifact, not the record.** The record is committed
  gzipped CSV in `data/`. ~143KB/day. Rebuild with
  `scripts/rebuild_from_snapshots.py`.
- **Graded subscription ($9.99/mo PokemonPriceTracker) deferred.** Graded fits
  a $100 bankroll badly, PSA turnaround fits no relevant window, and the live
  question moved to cross-venue matching. Schema and parser already support
  graded, so this is deferral not removal.
- **Public documented APIs only.** No scraping — the owner joins eBay in two
  weeks.
- **Credentials are never shared, including with Claude.** Env vars only.

---

## Measured findings

Numbers, not impressions. Do not re-derive these.

Base: 12 days of snapshots (2026-07-25 → 08-05), 1,978 card-printings in the
$3–40 band. Source: `sessions/2026-08-06-03-twelve-day-trends.md`.

### The market is efficient and static

Median absolute move over the window **3.50%**; 1.3% never changed price;
13.4% moved >10%; median CV 0.021.

### Wide spreads are artifacts, not opportunities

Of 548 cards with spread >30% on day 1, **349 (64%) were still >30% twelve
days later** (median 38.5% → 34.1%).

Spread autocorrelation by fixed lag — 1d 0.842 · 2d 0.757 · 3d 0.689 ·
5d 0.707 · 7d 0.731. **It drops then plateaus at ~0.70 rather than decaying
to zero.** The plateau is structural: ~70% of a card's spread is a fixed
property of that card, the rest is noise. The cheap listing is a damaged copy,
a misidentified print, or non-English — and TCGCSV publishes no condition to
tell them apart.

**Conclusion: no arbitrage inside TCGplayer.** Confirmed at 12 days.
Follows: **a real mispricing is new.** Weight newly-listed and ending-soon
items; treat long-standing listings as suspect.

### Downward drift costs ~a quarter of the edge

Equal-weight index **−0.97%** over the window, down 8 of 11 days (2 up, 1
flat); median per-card −0.56%, 54.5% of cards down. Small, but too monotone
to read as noise.

At ~−0.08%/day, a two-to-three week hold costs **$1.50–2.00 on $100** against
a fee advantage of ~$8. **Sell promptly after Aug 17 — waiting is a losing
trade.** The Sep 16 release would likely accelerate it.

### The tradeable universe is small

Of 13,379 priced singles, **76% are worth under $1** — below the $1.25 cost of
shipping one card, so bulk rather than inventory. Real universe: the ~1,100
cards in the $5–20 band.

### The fee discount is real and small

At an assumed 5% rate, 1,901 cards in the $3–40 band:

| Edge zone | Cards | Median profit | Clearing $1.50 |
| --- | --- | --- | --- |
| `open` (works at retail too) | 271 | $2.13 | 182 |
| `exclusive` (only works for you) | 355 | $0.41 | 31 |
| `dead` | 1,275 | −$0.90 | 0 |

Median fee advantage **$0.73/trade** on a median $8.87 card — ~**$8 across the
bankroll**. Median profit is negative in *every* rarity.

### Expected outcome

**−$25 to +$25.** Open question: does cross-venue mispricing exist at a size
worth capturing? Phase 3 answers it.

---

## Gotchas

Hard-won. Re-learning these costs money or hours.

- **TCGCSV has no condition axis.** Prices are `product × printing`
  (Normal/Holofoil/Reverse Holofoil), not SKU-level. Treat all prices as Near
  Mint. `fees.CONDITION_MULTIPLIERS` are **rules of thumb, not measurements** —
  validate against real sales before trusting them.
- **The catalog stores full collector numbers** (`223/197`), except promo sets
  which store bare ones (`SWSH147`). Matching on the numerator alone once
  resolved "Charizard ex 223/197" to a Professor's Research promo at 0.95
  confidence. **A number alone is never sufficient — the name must corroborate
  it.** Regression tests in `tests/test_titles.py`.
- **`publishedOn` in the TCGCSV group feed is unreliable** — it reports POP
  Series 1 (a 2004 set) as published in 2026. Era selection matches on set-name
  prefixes instead.
- **Brand-new sets ship with sparse metadata.** ME05 launched with only
  CardText and UPC — no Rarity or Number — so its cards briefly look like
  sealed product. Re-running the ingest picks up backfills.
- **TCGCSV cannot be backfilled.** It serves only the current day. A missed day
  is gone permanently.
- **`pokedb/ebay.py` has never run against the live API.** Written from docs.
  Expect response-shape or filter-syntax breakage on first contact.
- **A new production keyset arrives disabled.** eBay requires subscribing to
  *or explicitly opting out of* marketplace account deletion/closure
  notifications before the keyset works. Symptom is a "Your Keyset is
  currently disabled" message on the portal, and auth failures until the
  compliance step is done. Do this first, before debugging any code.
- **eBay Sandbox is useless for this project's measurement.** Sandbox Browse
  search runs on mock data and returns little or nothing for real queries.
  It can validate OAuth, headers and response parsing, but **cross-venue edge
  can only be measured against production.** Do not read a sandbox result as
  evidence about the market.
- **Browse search returns only `FIXED_PRICE` listings by default.** Auctions
  require an explicit `buyingOptions` filter — already handled in
  `pokedb/ebay.py`, but easy to lose in a refactor. Auctions ending at bad
  hours are a prime source of the mispricing this project is hunting.
- **Scheduled GitHub Actions are disabled after 60 days of repo inactivity,**
  and bot commits don't reliably reset the timer.

---

## Open items

Blocking, in order:

1. **eBay developer keys** → `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` in `.env`.
   Registered 2026-08-06; identity check expected back in a day, so keys
   ~**Aug 7–8**. This keeps the Aug 10 buy decision achievable. Two traps on
   arrival — see Gotchas: the keyset ships **disabled**, and **sandbox is
   useless for measurement**.
2. **Trading Cards category selling limits.** The owner's eBay account has
   selling history but never in trading cards; category limits may apply to
   first-time category sellers. Check Seller Hub before spending bankroll.
3. **Exact employee fee discount** — unknown until onboarding on Aug 17. Get
   the number *and* the terms (immediate? capped? category-restricted?).
4. **Hours per week available** — never answered. Phase plan assumes evenings
   and weekends.

## Timeline

| By | What |
| --- | --- |
| Aug 4 | eBay keys in `.env` |
| Aug 5–6 | First live scan; fix breakage; measure cross-venue edge |
| **Aug 10** | Buy decision — last safe date for delivery before the pivot |
| Aug 15 | Inventory in hand, listings drafted |
| **Aug 17** | Real fee rate in; re-rank; list |
| Sep 16 | ME: 30th Celebration releases — soft deadline to be flat |

**If cross-venue edge does not exist, the correct move is to buy nothing.**
The measurement was always the deliverable.

---

## Session log index

| Session | Date | Covered |
| --- | --- | --- |
| [01](2026-07-24-01-scoping-and-pipeline.md) | 2026-07-24 → 07-25 | Scoping, plan, Phases 0–2, cron + secrets infra |
| [02](2026-08-02-02-trend-and-phase-3.md) | 2026-08-02 | 8-day trend analysis, Phase 3 build, graded deferral |
| [03](2026-08-06-03-twelve-day-trends.md) | 2026-08-06 | 12-day trends, autocorrelation plateau, downward drift |
| [04](2026-08-06-04-ebay-keys-and-smoke-test.md) | 2026-08-06 | eBay registration, smoke test, keyset/sandbox traps |
