# Pokémon Card Price Database — Scope & Plan

**Owner:** akshaygupta26
**Created:** 2026-07-24 · **Revised:** 2026-07-24 (employee fee discount confirmed)
**Pivot date:** 2026-08-17 (eBay start date) — **24 days out**

> **Revision note:** Aug 17 was previously a hard deadline requiring full liquidation. It is now a **pivot date**: the day the sell side opens at a better fee rate. This changed the strategy from "flip fast and exit" to "accumulate now, sell after." Sections 4, 6, 7 and 8 were rewritten accordingly.

---

## 1. What this is

A price database and decision-support tool for **modern-era Pokémon singles**, built to:

1. **Learn the market-data → trade-decision → P&L-reconciliation loop.** Primary goal. Directly relevant to working at eBay: ingesting marketplace data, modeling fees, predicting net proceeds, measuring prediction error against reality.
2. **Execute real trades** with a **$100 bankroll** that can be lost without consequence.

The system is the deliverable. The trading pressure-tests it.

## 2. Scope (decided)

| Dimension | Decision |
| --- | --- |
| Era | Modern only — **Mega Evolution + Scarlet & Violet + Sword & Shield** (46 sets, ~2020–present) |
| Product | Raw singles **and** graded slabs |
| Language | English only |
| Buy/sell venues | eBay, TCGplayer |
| Bankroll | $100, treated as tuition |
| Stack | Python + SQLite + Jupyter |
| Data budget | ~$10/month |

**Out of scope for v1:** Japanese cards, sealed product, vintage/WOTC, grading submissions, automated purchasing, any form of scraping. Sealed and grading submissions are the most likely v2 additions now that the horizon is open-ended — both were rejected on timeline, not merit.

---

## 3. The core strategic insight

**Your edge is your cost structure, not your card selection.**

As an eBay employee you will pay a reduced final value fee. On modern raw singles — the most liquid, most efficient, most picked-over corner of this market — margins are thin and everyone reads the same TCGplayer market price. You will not out-pick experienced traders on which card appreciates.

But there is a band of trades that **lose money at 13.25% and make money at your rate.** Nobody at retail fees is competing for those, because for them they aren't trades at all.

Worked example — buy at $8, sell at $11:

```
                        Retail (13.25%)    Employee (5%)
Gross                        $11.00           $11.00
Final value fee              -$1.46           -$0.55
Per-order fee                -$0.40           -$0.40
Shipping (PWE)               -$1.25           -$1.25
Supplies                     -$0.30           -$0.30
                            -------          -------
Net proceeds                  $7.59            $8.50
Cost basis                   -$8.00           -$8.00
                            -------          -------
Profit                       -$0.41           +$0.50
                             LOSS             PROFIT
```

**Breakeven FVF for this trade: 9.55%.** Below that rate it's profitable; above it, it isn't.

This makes `breakeven_fvf` the most important derived column in the entire database. Every candidate trade gets one, and the opportunity ranking is built on it:

- `breakeven_fvf > 13.25%` → profitable for anyone. Competitive, thin, crowded.
- `your_rate < breakeven_fvf < 13.25%` → **your exclusive edge zone.** This is where to hunt.
- `breakeven_fvf < your_rate` → not a trade at any accessible rate.

Everything in §6 and §7 is built to surface that middle band.

### Fee sensitivity

The discount amount is unknown until onboarding, so it is a **config parameter**, not a constant. On the $12 → $18 example from §6:

| Your FVF | Fee | Net | Profit | vs. retail |
| --- | --- | --- | --- | --- |
| 13.25% (retail) | $2.39 | $13.66 | $1.66 | — |
| 10% | $1.80 | $14.25 | $2.25 | +36% |
| 5% | $0.90 | $15.15 | $3.15 | +90% |
| 0% | $0.00 | $16.05 | $4.05 | +144% |

On thin margins the fee rate is *the* dominant variable. This is why the model is parameterized: on Aug 17 you plug in the real number and instantly see which held inventory flipped from unviable to viable.

---

## 4. Timeline and sequencing

**Strategy: buy before Aug 17, sell after.** Source and accumulate during the build window using free time; hold across the pivot date; sell at the discounted rate.

| Window | Activity |
| --- | --- |
| Jul 24 – Aug 5 | Build pipeline. Data accumulates daily |
| Aug 5 – Aug 17 | Source and buy. Log every acquisition with real costs |
| Aug 17 | Plug in actual employee fee rate. Re-rank all held inventory |
| Aug 17 onward | List and sell. Reconcile predicted vs actual |

### Constraints that still apply

- **[TCGplayer seller approval: 1–2 weeks.](https://help.tcgplayer.com/hc/en-us/articles/201318336-How-do-I-sell-my-collectibles-on-TCGplayer)** Apply immediately. It's free optionality and the approval clock runs regardless of what else you're doing.
- **[eBay new-seller payout hold: up to 21–30 days](https://www.ebay.com/help/selling/getting-paid/payouts-work-managed-payments-sellers/payments-hold?id=4816)**, lifting after ~10 sales totaling $150+. No longer schedule-critical, but it means your first few sales won't pay out fast. Don't plan on recycling capital quickly.

### The risk this strategy introduces

Holding inventory 3–4 weeks means **price risk**. Modern singles are supply-sensitive, and a new set release floods the market and depresses prices on chase cards from prior sets.

**Resolved from the TCGCSV group feed:** the next release is **ME: 30th Celebration on 2026-09-16**. A 30th-anniversary set is likely to be a heavily-printed, heavily-hyped one.

That lands roughly four weeks after the pivot date, which is good news and bad news. Good: your Aug 17 – mid-September selling window is clear of a supply flood. Bad: anything still unsold by mid-September gets marked down as attention and supply rotate to the new set. **Treat 2026-09-16 as a soft deadline to be flat.** Recorded in `config.UPCOMING_RELEASES`.

### One guardrail

This pipeline uses only public, documented APIs, and should stay that way. Once you're inside eBay you'll have access to internal tools and non-public data; using any of it to inform personal trading is a categorically different thing from anything in this plan. Worth being deliberate about the line now, before it's ambiguous.

---

## 5. Data sources (researched and confirmed 2026-07-24)

| Source | Cost | Gives us | Role |
| --- | --- | --- | --- |
| [TCGCSV](https://tcgcsv.com/) | Free, no API key | Nightly full mirror of TCGplayer catalog + prices, per-condition SKUs, low/mid/market/high. Refreshes ~20:00 UTC daily | **Backbone.** Raw single prices |
| [PokemonPriceTracker](https://www.pokemonpricetracker.com/pokemon-card-price-api) API tier | $9.99/mo | PSA graded values from eBay sales, 6mo history, 20k credits/day, 60 req/min | **Graded layer** |
| [eBay Browse API](https://developer.ebay.com/api-docs/buy/browse/overview.html) | Free, 5,000 calls/day | Active listings — asking prices, titles, sellers, end times | **Sourcing feed** (buy side) |
| [pokemontcg.io](https://publicapis.io/pokemon-tcg-api) | Free | Card metadata, images, set data | Enrichment (optional) |

### Rejected, and why

- **eBay Marketplace Insights API** (sold comps) — Limited Release. 2025–26 developer forum threads show individual applicants flatly denied; approved partners only. This is *the* reason free graded pricing doesn't work.
- **PokemonPriceTracker free tier** — 100 credits/day, but PSA and eBay-sold data are excluded from free.
- **Scraping either marketplace** — against both platforms' terms, and a bad thing to have attached to your name 24 days before starting there. The official APIs cover what we need.

### On the $9.99/month

10% of bankroll per month. Not justifiable as a trading expense — no $100 position generates $10/mo of edge. Justified only as a learning expense, because the graded-vs-raw spread analysis is job-relevant. Budget as tuition. Cancel after a month if it isn't teaching you anything.

---

## 6. Schema (SQLite)

Design principle: **fees are first-class.** The most common beginner error is comparing a $12 buy to an $18 market price and seeing "+$6." Real math nets closer to +$1.66 at retail fees. **This database never displays a gross spread — every opportunity is net of fees, at your configured rate.**

**Live in [`schema.sql`](schema.sql).** Tables: `sets`, `products`, `price_snapshots`, `graded_prices`, `ebay_listings`, `watchlist`, `inventory`, `sales`, `ingest_runs`.

### Correction: there is no condition-level pricing

The original draft of this plan specified a `skus` table keyed by condition (NM/LP/MP/HP). **That was wrong, and building against it would have failed on first contact with the data.**

TCGCSV publishes prices at **product × printing**, not SKU level:

```json
{"productId": 692938, "subTypeName": "Normal",
 "lowPrice": 19.0, "midPrice": 25.0, "highPrice": 59.99,
 "marketPrice": 22.52, "directLowPrice": null}
```

`subTypeName` is the printing — Normal / Holofoil / Reverse Holofoil. There is no condition axis at all. Condition-level pricing lives behind the real TCGplayer API, which is closed to new applicants for the same reason eBay's sold-comps API is.

Consequences, all load-bearing:

1. Feed prices are **effectively Near Mint**. Condition is a property of things you *buy* and *see listed*, never of the reference price feed.
2. Condition discounts are modeled separately in `fees.CONDITION_MULTIPLIERS` (LP 0.85, MP 0.70, HP 0.55). **These are rules of thumb, not measurements.** They are flagged as unvalidated in the code and are a specific thing Notebook 3 should correct against real sales.
3. Buying anything below NM means your cost basis is real but your comp is not. Early on, prefer NM to avoid compounding a modeled discount with a modeled price.

### Grain

`price_snapshots` is keyed `(product_id, sub_type_name, as_of_date, source)`. That primary key is what makes the daily job idempotent — a same-day re-run replaces rather than duplicates.

Singles and sealed both live in `products`, split by `is_single`. The only reliable discriminator in the feed is the presence of a `Number` field in `extendedData`. Note that brand-new sets ship with sparse metadata — ME05 launched with only `CardText` and `UPC`, no `Rarity` or `Number` — so a new set's cards look like sealed product for a few days until TCGplayer backfills. Re-running the ingest picks up the corrections.

### Derived views

- `v_current_prices` — latest snapshot per SKU
- `v_price_trend` — 7d / 30d change per SKU
- `v_opportunities` — active listings ranked by net edge **at your fee rate**, with `breakeven_fvf` and an `edge_zone` flag (`open` / `exclusive` / `dead`) per §3
- `v_pnl` — realized and unrealized P&L per lot, **predicted vs actual**

`v_pnl` is the one that matters for your job. It's where the model gets graded.

---

## 7. Fee model

Config file, not hardcoded. Rates change and must be verified against current published schedules before trading.

```python
FEES = {
    "ebay": {
        "fvf_rate": 0.1325,      # OVERRIDE ON AUG 17 with employee rate
        "per_order": 0.40,
        "applies_to_shipping": True,
    },
    "tcgplayer": {
        "commission": 0.1025,
        "payment_processing": 0.025,
    },
}
SHIPPING = {"pwe_tracked": 1.25, "bmwt": 5.00}
SUPPLIES = 0.30
```

Two functions carry the model:

- `net_proceeds(gross, venue, fvf_rate) -> float`
- `breakeven_fvf(gross, cost_basis, venue) -> float` — the rate at which a trade breaks even, per §3

Everything downstream is built on those two.

---

## 8. Build phases

Day numbers from 2026-07-24.

### Phase 0 — Day 1 (~2 hrs)
- Repo skeleton, SQLite schema, config, `.env` for API keys
- **Apply for TCGplayer seller account today** — 1–2 week approval, runs in background
- Sign up for PokemonPriceTracker API tier
- Check the Pokémon set release calendar through mid-September (§4 risk)

### Phase 1 — Days 2–3
- TCGCSV ingester: Pokémon category → SV/SWSH groups → products → prices
- Load into `sets`, `cards`, `skus`, `price_snapshots`
- Idempotent, re-runnable daily
- **Start it running immediately.** Price history accumulates in wall-clock time and TCGCSV cannot be backfilled. Data not collected this week does not exist later

### Phase 2 — Days 4–5
- **Notebook 1: What does the modern market look like?** Price distributions, which rarities hold value, volatility by set, how many cards are liquid enough to trade at all
- Build the watchlist from findings, not vibes

### Phase 3 — Days 6–8
- eBay Browse API integration (OAuth, search, pagination)
- **Title parsing** — extract set, number, condition, grade from freeform titles. Hardest and most interesting engineering here. Real listings look like `"Charizard ex 223/197 SV Obsidian Flames SIR PSA 10 GEM MINT 🔥"`
- Fuzzy-match to catalog with a confidence score you can filter on

### Phase 4 — Days 9–10
- Fee engine: `net_proceeds()` and `breakeven_fvf()`
- `v_opportunities` with edge-zone classification
- **Sensitivity view: which opportunities are viable at 13.25% / 10% / 5% / 0%.** Built now so Aug 17 is a one-line config change, not a rewrite
- The database becomes a tool at this point

### Phase 5 — Days 11–13
- PokemonPriceTracker ingestion for graded prices
- **Notebook 2: Is the raw→PSA spread real?** Raw vs PSA 9 vs PSA 10 across the watchlist, net of grading cost and turnaround. Now that the horizon is open-ended this is a live v2 strategy rather than a thought experiment — evaluate it properly

### Phase 6 — Days 14–24 (buy window)
- **Source and buy.** 5–10 raw singles, $3–20 range. Diversify — you want repetitions, not one bet
- Prioritize the **exclusive edge zone** from §3: trades that don't work at retail fees but work at yours
- Record `predicted_net_at_purchase` on every lot. This is what gets graded later
- Log every real cost: item, shipping paid, taxes

### Phase 7 — Aug 17 onward (sell window)
- Plug in the actual employee fee rate. Re-rank held inventory
- List and sell
- **Notebook 3: Predicted vs actual.** For every completed sale, compare model-predicted net against what eBay actually paid. Categorize the gaps: fee model wrong? condition misgraded? shipping underestimated? demand overestimated?

Notebook 3 is the portfolio artifact. A pipeline that ingests data is common; one where the author measured their own model's error and explained it is not.

---

## 9. Honest expected outcome

- **Financial:** roughly **-$30 to +$40**. The fee discount genuinely improves this — it's the difference between fighting for scraps at retail rates and having a structural advantage. But $100 across 5–10 cards caps the absolute upside at pocket change regardless of how good the model is. There is no free money in Scarlet & Violet commons; there is a small, real, fee-driven edge.
- **Cash timing:** first sales won't pay out quickly due to the new-seller hold. Don't plan on recycling capital.
- **What you actually get:** a working ingestion pipeline against three real APIs, a fee-aware valuation model with a genuine strategic insight behind it, a title-parsing/entity-matching problem solved, and a reconciliation notebook showing you measured your own error. Worth considerably more than the $100.

---

## 10. Open items

1. ~~eBay employee policy~~ — **Resolved.** Selling permitted; employee fee discount applies.
2. **Exact fee discount** — unknown until onboarding. Modeled as a config parameter with sensitivity analysis. Get the number, and the terms (immediate? capped? category-restricted? store subscription required?) on Aug 17.
3. ~~Set release calendar~~ — **Resolved.** ME: 30th Celebration lands 2026-09-16. Selling window is clear; treat mid-September as a soft deadline to be flat. See §4.
4. ~~Do you already own any Pokémon cards?~~ — **Resolved: no.** Consequence: there is no free inventory to rehearse the sell side on. Every test of listing, packing, shipping and fee reconciliation costs bankroll. See "tuition lots" below.
5. ~~Existing eBay account with selling history?~~ — **Resolved: yes, but never in trading cards.** Account-level history should reduce or remove the payout hold, since that test is account-wide. But eBay applies **category-based selling limits to sellers listing in a category for the first time**, and account history does not necessarily carry over.

   **Action before spending any bankroll: check Seller Hub → selling limits for the Trading Cards category.** If you are capped at a handful of listings per month, that dictates how many cards to buy. Cheap to check, expensive to discover after you own inventory.
6. **Hours per week available.** Phase plan assumes evenings and weekends. Less than that and Phase 5 defers.

### Tuition lots

With no cards on hand, the first purchases have to do double duty: prove the model *and* teach you the mechanics you've never performed (PWE packing, tracked shipping, listing quality, fee reconciliation).

Keep those goals separate in the data. Buy 2–3 deliberately cheap cards purely as mechanics rehearsal, expect to lose money on them, and tag them in `inventory.notes` as tuition lots so Notebook 3 can exclude them. Otherwise deliberate loss-leaders pollute the measurement of whether the edge model actually works.

---

## 11. Build status

**Phases 0–1 complete (2026-07-24).** Schema, fee model, and TCGCSV ingester are live and verified. First snapshot captured: 46 sets, 10,378 products, 14,766 price rows, 93 requests against a 10,000/day cap. Re-run confirmed idempotent (zero duplicate keys).

The fee model reproduces both worked examples in §3 exactly — breakeven FVF of 9.55% on the $8→$11 trade, 22.50% on $12→$18.

### What the first snapshot revealed

Of **13,379 priced tradeable singles**:

| Price band | Count | Share |
| --- | --- | --- |
| under $1 | 10,120 | 76% |
| $1–5 | 1,437 | 11% |
| $5–20 | 1,101 | 8% |
| $20–100 | 583 | 4% |
| $100+ | 138 | 1% |

**Three quarters of the modern catalog is worth less than a dollar.** Shipping alone is $1.25, so those cards can never be traded individually at any fee rate — they are bulk, not inventory.

The realistic universe for a $100 bankroll is the **~1,100 cards in the $5–20 band**, plus the upper part of $1–5. That is the hunting ground, and it is 8% of what's in the database. Notebook 1 should filter to it immediately rather than surveying all 13,379.

This also sharpens the §3 thesis. In the $5–20 band, per-order and shipping costs are 8–30% of gross — which is *why* the fee rate dominates, and why the exclusive edge zone exists at all. At $200 a card, a few points of FVF barely matter. At $8, it's the whole trade.

## 12. Phase 2 findings — the thesis, measured

`notebooks/01_market_survey.ipynb` applies the fee model to the first snapshot: buy at the lowest listing, sell at market price. Results at an assumed 5% employee rate, across 1,901 cards in the $3–40 band:

| Edge zone | Cards | Median profit | Clearing $1.50 |
| --- | --- | --- | --- |
| `open` (works at retail too) | 271 | $2.13 | 182 |
| `exclusive` (works only for you) | 355 | $0.41 | 31 |
| `dead` | 1,275 | −$0.90 | 0 |

**The exclusive zone is real, and much thinner than §3 hoped.** 355 cards, median profit $0.41, only 31 clearing the handling threshold.

**The fee discount is worth a median $0.73 per trade** on a median $8.87 card — about 8%. Across a $100 bankroll (~11 cards) that's roughly **$8 of total edge**. A genuine structural advantage that improves trades you were already making; not something that converts a losing strategy into a winning one.

**Median profit is negative in every single rarity.** The typical card in the tradeable band loses money on this round trip after fees and shipping. Modern singles are efficiently priced, which is what should be expected of the most liquid corner of the hobby.

### The structural problem, and what it changes

The largest apparent opportunities are nearly all `open` zone — profitable at retail too. A trade that good, visible to everyone, has already been taken; its survival on the screen is evidence something is wrong with it (damaged copy, misidentified print, non-English, already sold). 90 of 1,901 cards show spreads over 50% and are filtered as artifacts.

More fundamentally:

> **Buying at TCGplayer low and selling at TCGplayer market is not an arbitrage.** It is one order book. Relisting into the venue you just bought from puts you behind the same low listings you were competing with, and market price is a trailing average of completed sales — not a price anyone owes you.

Real edge requires **a price difference between two venues**, where one side is genuinely less efficient. That is eBay, specifically its badly-listed corners: missing set names, misspellings, no card number, auctions ending at 3am, a $20 card titled "pokemon card rare holo".

**This promotes Phase 3 from a component to the critical path.** eBay Browse ingestion and title parsing are not a layer on top of the TCGplayer data — without a second venue there is no arbitrage to measure at all. The TCGplayer feed is the *reference price*; eBay is where the mispricing lives.

The 189-card watchlist this notebook produced is not a buy list. It is the search universe for Phase 3.

## 13. Revised expected outcome

Tightening §9 with measured numbers rather than estimates: **-$25 to +$25**, with the distribution centred slightly below zero before the fee discount and slightly above it after.

The reasoning is now concrete rather than intuitive: the median trade in this band is a loser, the fee discount is worth ~$8 across the bankroll, and any profit beyond that has to come from cross-venue mispricing that hasn't been measured yet. Whether that mispricing exists at a size worth capturing is the open empirical question, and Phase 3 is what answers it.

That is a better position to be in than the plan started from. The question went from "can I make money flipping cards" to "does exploitable cross-venue mispricing exist in the $5–20 band, and is it larger than my costs" — which is answerable with data.

## 14. Next action

**Phase 3: eBay Browse API ingestion and title parsing**, now the critical path. Search the 189-card watchlist against active eBay listings, parse freeform titles into catalog matches, and compute genuine cross-venue spreads.

Two things needed first:
- eBay developer keys (`EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` in `.env`)
- Trading Cards category selling limits checked (§10 item 5)

And the daily ingest needs to be running, or none of the trend work in §12 ever becomes possible:

```
0 22 * * *  cd /path/to/Learning && python3 scripts/ingest_tcgcsv.py --quiet >> ingest.log 2>&1
```
