# Pokémon Card Price Database — Scope & Plan

**Owner:** akshaygupta26
**Created:** 2026-07-24
**Hard deadline:** 2026-08-17 (eBay start date) — **24 days out**

---

## 1. What this is

A price database and decision-support tool for **modern-era Pokémon singles**, built to:

1. **Learn the market-data → trade-decision → P&L-reconciliation loop.** This is the primary goal. It is directly relevant to working at eBay: ingesting marketplace data, modeling fees, predicting net proceeds, and measuring prediction error against reality.
2. **Execute a small number of real trades** with a **$100 bankroll** that can be lost without consequence.

The system is the deliverable. The trading is how you pressure-test it.

## 2. Scope (decided)

| Dimension | Decision |
| --- | --- |
| Era | Modern only — Scarlet & Violet + Sword & Shield (~2020–present) |
| Product | Raw singles **and** graded slabs |
| Language | English only |
| Sealed | Out of scope for v1 |
| Buy/sell venues | eBay, TCGplayer |
| Bankroll | $100, treated as tuition |
| Stack | Python + SQLite + Jupyter |
| Data budget | ~$10/month |

**Explicitly out of scope for v1:** Japanese cards, sealed product, vintage/WOTC, non-English sets, automated purchasing, any form of scraping.

---

## 3. Data sources (researched and confirmed 2026-07-24)

| Source | Cost | Gives us | Role |
| --- | --- | --- | --- |
| [TCGCSV](https://tcgcsv.com/) | Free, no API key | Nightly full mirror of TCGplayer catalog + prices, per-condition SKUs, low/mid/market/high. Refreshes ~20:00 UTC daily | **Backbone.** Raw single prices |
| [PokemonPriceTracker](https://www.pokemonpricetracker.com/pokemon-card-price-api) API tier | $9.99/mo | PSA graded values derived from eBay sales, 6 months price history, 20k credits/day, 60 req/min | **Graded layer** |
| [eBay Browse API](https://developer.ebay.com/api-docs/buy/browse/overview.html) | Free, 5,000 calls/day | Active listings — asking prices, titles, sellers, end times | **Sourcing feed** (buy side) |
| [pokemontcg.io](https://publicapis.io/pokemon-tcg-api) | Free | Card metadata, images, set data | Enrichment (optional) |

### Sources rejected, and why

- **eBay Marketplace Insights API** (the sold-comps one) — Limited Release. 2025–26 developer forum threads show individual applicants flatly denied; access is for approved partners only. This is *the* reason free graded pricing doesn't work.
- **PokemonPriceTracker free tier** — 100 credits/day, but PSA and eBay-sold data are excluded from free. Only the paid tier unlocks them.
- **Scraping eBay or TCGplayer** — against both platforms' terms. Do not do this. You are 24 days from being an eBay employee; starting the job with a ToS violation attached to your name is an unforced error, and the official APIs cover what we need anyway.

### On the $9.99/month

That is **10% of your bankroll per month**. It cannot be justified as a trading expense — no $100 position generates $10/mo of edge. It is justified *only* as a learning expense, because the graded-vs-raw spread analysis is genuinely interesting and job-relevant. Budget it as tuition, not as cost of goods. If after one month the graded data isn't teaching you anything, cancel it.

---

## 4. The two constraints that reshape everything

Discovered during research. Both are load-bearing.

### 4.1 eBay holds new-seller funds

[eBay's payout policy](https://www.ebay.com/help/selling/getting-paid/payouts-work-managed-payments-sellers/payments-hold?id=4816): new sellers, or sellers without an established track record, have payouts held **until delivery is confirmed, or up to 21–30 days**. The hold lifts after roughly 10 completed sales totaling $150+ with a clean record.

**Implication:** a sale on Aug 5 may not pay out until after Aug 17.

### 4.2 TCGplayer seller approval takes 1–2 weeks

[Per TCGplayer's own help docs](https://help.tcgplayer.com/hc/en-us/articles/201318336-How-do-I-sell-my-collectibles-on-TCGplayer). Applying on Jul 24 means selling in early-to-mid August at best.

### 4.3 What this means

A full cycle is: buy → ship to you (3–5d) → receive/verify → list → sell (7d auction, or BIN of unknown duration) → ship out (3–5d) → funds settle (up to 21d as a new seller).

**Realistic completed cycles before Aug 17: one, possibly two, and the money may not clear in time.**

This is not a reason to abandon the project. It is a reason to define success correctly:

> **Success on Aug 17 = a working pipeline, a fee-aware valuation model, and a reconciliation notebook comparing predicted net proceeds to actual. Trades executed are evidence the model works, not the goal itself.**

Cash settling after your start date is fine. Holding *inventory* past your start date may not be — see open item #1.

---

## 5. Schema (SQLite)

Design principle: **fees are first-class**. The single most common beginner error is comparing a $12 buy to an $18 market price and seeing "+$6." The real math is 13.25% final value fee + per-order fee + shipping + supplies, netting closer to +$2.80 before your time is counted. **This database never displays a gross spread — every opportunity is shown net of fees.**

### Reference / catalog

```sql
sets(
  set_id PK, name, series, release_date, tcgcsv_group_id, card_count
)

cards(
  card_id PK, set_id FK, number, name, rarity,
  tcgplayer_product_id, ppt_id, image_url
)

-- TCGplayer's SKU model: one card has many sellable variants
skus(
  sku_id PK, card_id FK, condition,      -- NM / LP / MP / HP / DMG
  printing,                              -- Normal / Holofoil / Reverse Holofoil
  language
)
```

### Price facts (time series)

```sql
-- One row per SKU per source per day. The core fact table.
price_snapshots(
  sku_id FK, source, as_of_date,
  market, low, mid, high, direct_low,
  PRIMARY KEY (sku_id, source, as_of_date)
)

graded_prices(
  card_id FK, grader,                    -- PSA / CGC / BGS
  grade, as_of_date, sale_price, sample_size, source,
  PRIMARY KEY (card_id, grader, grade, as_of_date)
)

-- Active eBay listings, fuzzy-matched to catalog. Asking prices, NOT sales.
ebay_listings(
  listing_id PK, card_id FK, raw_title,
  price, shipping_cost, condition_parsed, grade_parsed,
  seller, listing_type, end_time, observed_at,
  match_confidence                       -- title parsing is lossy; track it
)
```

### Trading

```sql
watchlist(card_id FK, target_buy_price, notes, added_at)

inventory(
  lot_id PK, card_id FK, sku_id FK,
  acquired_date, acquired_price, acquired_fees, acquired_venue,
  status                                 -- held / listed / sold
)

sales(
  lot_id FK, sold_date, venue, gross_price,
  platform_fee, payment_fee, shipping_cost, shipping_charged,
  supplies_cost, net_proceeds
)
```

### Derived views

- `v_current_prices` — latest snapshot per SKU
- `v_price_trend` — 7d / 30d change per SKU
- `v_opportunities` — active eBay listings ranked by **net** edge vs TCGplayer market
- `v_pnl` — realized and unrealized P&L per lot, **predicted vs actual**

`v_pnl` is the one that matters for your job. It is where the model gets graded.

---

## 6. Fee model

Lives in a config file, not hardcoded — these rates change and must be verified against current published schedules before you trade.

- **eBay:** ~13.25% final value fee on item + shipping, plus a per-order fee (~$0.30–0.40)
- **TCGplayer:** ~10.25% commission + ~2.5% payment processing
- **Shipping:** PWE with tracking ~$1.10–1.40; bubble mailer with tracking ~$5
- **Supplies:** sleeve + toploader + team bag ~$0.30

**Worked example — why this matters:**

Buy a card for $12. TCGplayer market says $18. Naive read: +$6, a 50% gain.

Actual, selling on eBay:
```
Gross                    $18.00
eBay FVF (13.25%)        -$2.39
Per-order fee            -$0.40
Shipping (PWE)           -$1.25
Supplies                 -$0.30
                        --------
Net proceeds             $13.66
Cost basis              -$12.00
                        --------
Profit                    $1.66   (13.8%, not 50%)
```

One return, one lost PWE, or one card that grades LP instead of NM wipes out several of these. **This is the single most important thing the database exists to show you.**

---

## 7. Build phases

Day numbers are from 2026-07-24.

### Phase 0 — Day 1 (~2 hrs)
- Repo skeleton, SQLite schema, config file, `.env` for API keys
- **Apply for TCGplayer seller account today** — 1–2 week approval is the long pole; every day of delay is a day off the back end
- Check eBay employee conflict-of-interest policy in your onboarding docs (open item #1)
- Sign up for PokemonPriceTracker API tier

### Phase 1 — Days 2–3
- TCGCSV ingester: Pokémon category → SV/SWSH groups → products → prices
- Load into `sets`, `cards`, `skus`, `price_snapshots`
- Idempotent, re-runnable daily. Ship this as a cron/manual script
- **Start it running immediately** — price history only accumulates in wall-clock time, and you cannot backfill TCGCSV

### Phase 2 — Days 4–5
- **Notebook 1: What does the modern market look like?** Price distributions, which rarities hold value, volatility by set, how many cards are even liquid enough to trade
- Build the watchlist from what you find, not from vibes

### Phase 3 — Days 6–8
- eBay Browse API integration (OAuth, search, pagination)
- **Title parsing** — extract set, card number, condition, grade from freeform listing titles. This is the hardest and most interesting engineering in the project. Real listings look like `"Charizard ex 223/197 SV Obsidian Flames SIR PSA 10 GEM MINT 🔥"`
- Fuzzy-match listings to catalog, with a confidence score you can filter on

### Phase 4 — Days 9–10
- Fee engine: `net_proceeds(gross, venue) -> float`
- Edge calculation: `edge = net_proceeds(market_price) - (listing_price + listing_shipping)`
- `v_opportunities` ranked view. **The database becomes a tool at this point**

### Phase 5 — Days 11–12
- PokemonPriceTracker ingestion for graded prices
- **Notebook 2: Is the raw→PSA grading spread real?** Compute raw price vs PSA 9 vs PSA 10 across the watchlist, subtract grading cost and turnaround time
- Expected finding: with $100 and PSA turnaround measured in months, grading arbitrage is closed to you. Proving that rigorously is worth more than assuming it

### Phase 6 — Days 13–24
- **Execute.** Buy 5–10 raw singles in the $3–20 range. Diversify — you want repetitions, not one bet
- Log every purchase in `inventory` with real fees, real shipping
- List them. Sell what sells
- **Notebook 3: Predicted vs actual.** For every completed sale, compare what the model said you'd net against what eBay actually paid. Categorize the gaps: fee model wrong? condition misgraded? shipping underestimated? This notebook is the actual portfolio artifact

---

## 8. Honest expected outcome

- **Financial:** somewhere between **-$40 and +$25**. The expected value of a beginner flipping modern raw singles, after fees, is roughly zero minus mistakes. Modern singles are the most efficient, most liquid, most picked-over corner of this market. There is no free money in Scarlet & Violet commons.
- **Cash timing:** some or all proceeds likely settle after Aug 17 due to the new-seller hold.
- **What you actually get:** a working ingestion pipeline against three real APIs, a fee-aware valuation model, a title-parsing/entity-matching problem solved, and a reconciliation notebook that shows you measured your own model's error. For a job at eBay, that is worth considerably more than the $100.

If the goal were purely to make money, the correct advice would be "don't." The goal is to learn the loop, so: proceed, spend little, measure everything.

---

## 9. Open items — I need answers on these

1. **eBay employee policy.** Check your offer/onboarding docs for conflict-of-interest and employee trading rules. Determines whether you must fully exit positions before Aug 17, or can hold and sell after. **Current working assumption: you must close out.** This is the single biggest unknown in the plan.
2. **Do you already own any Pokémon cards?** Free inventory to test the sell side with, without spending bankroll. Would meaningfully de-risk the timeline.
3. **Do you have an existing eBay account with selling history?** An account with 10+ completed sales and $150+ in volume skips the payout hold entirely. A brand-new account does not.
4. **Confirm the $9.99/mo** PokemonPriceTracker spend, understanding it's 10% of bankroll and justified as learning, not trading.
5. **Hours per week available.** The phase plan assumes evenings and weekends. If you have less, Phases 5 and 6 compress and graded gets deferred.

---

## 10. Decision needed before I write code

Given the timeline constraints in §4, pick one:

- **(A) Build the full system, trade small, accept late settlement.** Follow the plan as written. Highest learning, money possibly arrives after Aug 17.
- **(B) Build the system, skip trading entirely before Aug 17.** Pure data/analysis project. Trade later once the employee-policy question is resolved. Zero financial risk, zero mechanics learned.
- **(C) Trade immediately with minimal tooling, build the system around it.** Buy cards this week using manual research, build the DB to explain what happened. Fastest to real experience, worst engineering.

**Recommendation: (A).** It's the only option that exercises the whole loop, and late-settling cash is a non-issue when the amount is $100 you've already written off.
