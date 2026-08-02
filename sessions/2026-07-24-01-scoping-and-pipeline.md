# Session 01 — scoping and pipeline

**Date:** 2026-07-24 → 2026-07-25

> Backfilled 2026-08-02, when the sessions system was introduced. Reconstructed
> from commit history and the plan's revision trail.

## Goal

Take "I want a database with Pokémon card prices so I can trade before I start
at eBay on Aug 17" from a one-line idea to a scoped plan and a working
pipeline.

## What happened

### Scoping by interrogation

Two rounds of questions before any code. The answers that mattered:

- Goal is **learning the process** (job-relevant) plus profit, with **$100**
  that can be lost.
- **Modern era only**, raw singles **and** graded slabs.
- **Free data sources only** — then revised to paying, once the graded gap
  became clear.
- Venues: eBay and TCGplayer. Stack: Python + SQLite + Jupyter.

### Research established what data actually exists

- **TCGCSV** — free nightly TCGplayer mirror, no API key. Better than most paid
  options for raw singles. Became the backbone.
- **eBay Marketplace Insights** (sold comps) — Limited Release, individual
  developers denied. This is *why* free graded pricing is impossible.
- **PokemonPriceTracker** — free tier excludes PSA and eBay-sold data; the
  $9.99/mo tier includes both.
- **eBay Browse** — free, 5,000 calls/day, active listings only.

### Two operational constraints found by research

- eBay holds new-seller payouts until delivery or up to 21–30 days.
- TCGplayer seller approval takes 1–2 weeks.

Together these made profitable round-trips before Aug 17 unlikely, so success
was redefined as *a working pipeline plus a predicted-vs-actual reconciliation*
rather than trading profit.

### The employee discount changed the strategy

Mid-session the owner revealed they **can** sell after joining, at a **reduced
fee rate**. This removed the forced-liquidation constraint entirely and turned
Aug 17 from a deadline into a pivot. Strategy became **buy before, sell after**.

It also produced the project's central idea: on thin margins the fee rate
dominates, so **the edge is cost structure, not card selection**. Hence
`breakeven_fvf` and the open/exclusive/dead edge zones.

### Built Phases 0–2

Schema, fee model, TCGCSV ingester, market survey notebook, GitHub Actions
scheduling, CSV snapshot durability, secrets documentation.

## Decisions

- **Modern era = ME + SV + SWSH**, not just SV + SWSH. Mega Evolution
  superseded Scarlet & Violet as the current 2026 era.
- **Era selection matches set-name prefixes**, not `publishedOn`, which the
  feed reports unreliably.
- **Fee rate is a config parameter** with a sensitivity view, so Aug 17 is a
  one-line change rather than a rewrite.
- **The DB is a build artifact; committed CSV is the record.** Committing
  SQLite directly would mean hundreds of MB of undiffable binary within a year.
- **GitHub Actions over local cron**, because the container running the work is
  ephemeral and a laptop is not always awake.
- **Credentials are never shared.** Everything reads from env vars.

## Measurements

First snapshot: 46 sets, 10,378 products, 14,766 price rows, 93 requests
against a 10,000/day cap.

Price distribution across 13,379 priced singles — **76% worth under $1**, below
the $1.25 cost of shipping one card. Realistic universe is ~1,100 cards in the
$5–20 band.

Market survey at an assumed 5% rate, 1,901 cards in the $3–40 band:

| Edge zone | Cards | Median profit | Clearing $1.50 |
| --- | --- | --- | --- |
| `open` | 271 | $2.13 | 182 |
| `exclusive` | 355 | $0.41 | 31 |
| `dead` | 1,275 | −$0.90 | 0 |

Median fee advantage **$0.73/trade**, ~$8 across the bankroll. **Median profit
negative in every rarity.**

## Gotchas

- **The schema was wrong on first design.** It specified a `skus` table keyed
  by condition (NM/LP/MP/HP). TCGCSV publishes at `product × printing` only —
  there is no condition axis. Found by hitting the real endpoint. Would have
  failed on first contact.
- **`publishedOn` is unreliable** — POP Series 1, a 2004 set, reports as
  published 2026-07-24.
- **New sets ship with sparse metadata** — ME05 launched with only CardText and
  UPC, so its cards briefly looked like sealed product.
- **TCGCSV cannot be backfilled.** Every day the ingest does not run is history
  that will never exist.

## Open at end of session

- eBay developer keys needed for Phase 3.
- Trading Cards category selling limits unchecked.
- Exact employee fee discount unknown until onboarding.

**Structural finding carried forward:** buying at TCGplayer low and selling at
TCGplayer market is not an arbitrage — it is one order book. Real edge requires
a second venue. This promoted Phase 3 from a component to the critical path.
