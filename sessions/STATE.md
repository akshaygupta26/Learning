# Project State

**Last updated:** 2026-08-02 (session 02)

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

Daily ingest runs unattended via GitHub Actions. 8 days of snapshots as of
2026-08-01. It works; leave it alone.

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

### The market is efficient and static

From 8 days of snapshots (2026-07-25 → 08-01), 1,963 card-printings in the
$3–40 band:

- Median absolute price move over 8 days: **3.11%**
- Never changed price at all: 1.8% · Moved >10%: 9.0%

### Wide spreads are artifacts, not opportunities

Of 551 cards with a low-to-market spread >30% on day 1:

- **387 (70%) still >30% eight days later**
- Median spread 38.5% → 35.1%
- **Per-card spread correlation: 0.703**

A gap that sits untouched for 8 days in a liquid market is a property of the
card — the cheap listing is a damaged copy, a misidentified print, or
non-English. TCGCSV publishes no condition, so the catalog cannot distinguish
them. **Conclusion: there is no arbitrage inside TCGplayer.**

Reusable filter that follows: **a real mispricing is new.** Weight
newly-listed and ending-soon items; treat long-standing listings as suspect.

### The tradeable universe is small

Of 13,379 priced singles: **76% are worth under $1** — below the $1.25 cost of
shipping one card, so they are bulk, not inventory. The realistic universe is
the ~1,100 cards in the $5–20 band.

### The fee discount is real and small

At an assumed 5% employee rate, across 1,901 cards in the $3–40 band:

| Edge zone | Cards | Median profit | Clearing $1.50 |
| --- | --- | --- | --- |
| `open` (works at retail too) | 271 | $2.13 | 182 |
| `exclusive` (only works for you) | 355 | $0.41 | 31 |
| `dead` | 1,275 | −$0.90 | 0 |

Median fee advantage: **$0.73/trade** on a median $8.87 card — roughly **$8
across the whole bankroll**. Median profit is negative in *every* rarity.

### Revised expected outcome

**−$25 to +$25.** The open question is whether cross-venue mispricing exists
at a size worth capturing. Phase 3 answers it.

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
- **Scheduled GitHub Actions are disabled after 60 days of repo inactivity,**
  and bot commits don't reliably reset the timer.

---

## Open items

Blocking, in order:

1. **eBay developer keys** → `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` in `.env`.
   Everything in Phase 3 is blocked on this. Needed by **~Aug 4**.
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
