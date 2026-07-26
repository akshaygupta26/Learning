# Pokémon Card Price Database

A price database and decision-support tool for modern-era Pokémon singles.

Built to learn the market-data → trade-decision → P&L-reconciliation loop, and
to trade a small bankroll against it. See [PLAN.md](PLAN.md) for scope,
strategy, and build phases.

## The idea

Edge on modern raw singles comes from **cost structure, not card selection**.
Everyone reads the same TCGplayer market price. But a reduced final value fee
opens a band of trades that lose money at retail rates and profit at yours —
trades nobody at 13.25% is competing for, because for them they aren't trades.

`pokedb/fees.py` computes `breakeven_fvf`: the fee rate at which a given trade
breaks even. It sorts every opportunity into three buckets:

| Zone | Meaning |
| --- | --- |
| `open` | Profitable at retail rates too. Crowded and thin. |
| `exclusive` | Profitable for you, not for a retail flipper. **Hunt here.** |
| `dead` | Unprofitable at any accessible rate. |

## Setup

No install step for the pipeline — it uses only the Python standard library.

```bash
cp .env.example .env          # then edit: User-Agent, and your fee rate
python3 scripts/init_db.py    # create pokedb.sqlite
python3 scripts/ingest_tcgcsv.py
```

For the analysis notebooks (Phase 2 onward):

```bash
pip install -r requirements.txt
```

## Daily ingest

**Run this every day.** [TCGCSV](https://tcgcsv.com) serves only the current
day's snapshot and cannot be backfilled — a day missed is a day of price
history that does not exist later. Trend analysis is the whole point of
collecting it, so the clock starts now.

```bash
python3 scripts/ingest_tcgcsv.py            # full modern-era run
python3 scripts/ingest_tcgcsv.py --limit 3  # smoke test
python3 scripts/ingest_tcgcsv.py --list     # show scope, fetch nothing
```

A full run is **46 sets / ~93 requests**, against TCGCSV's published cap of
10,000 requests per day. Re-running the same day is safe: products upsert and
price rows are keyed by `(product_id, printing, date, source)`, so a re-run
replaces rather than duplicates.

### Where to run it

**Recommended: GitHub Actions** — already configured in
[`.github/workflows/daily-ingest.yml`](.github/workflows/daily-ingest.yml).
It runs at 22:00 UTC, after TCGCSV's ~20:00 refresh, and commits the day's
snapshot back to the repo. No server, no laptop uptime, no secrets required
(TCGCSV needs no API key). Enable it by pushing the workflow and checking the
Actions tab; trigger a test run with **Run workflow**.

One caveat: GitHub disables scheduled workflows after **60 days without repo
activity**. Bot commits don't reliably reset that timer, so push something
yourself occasionally, or re-enable it from the Actions tab if it stops.

**Alternative: your own machine.** Works, but only while the machine is awake.

```bash
# Linux
crontab -e
0 22 * * *  cd /path/to/Learning && python3 scripts/ingest_tcgcsv.py --quiet >> ingest.log 2>&1
```

On macOS, prefer `launchd` over cron — a `StartCalendarInterval` job runs on
wake if the scheduled time was missed, whereas cron simply skips it.

### Data durability

The `.sqlite` file is a **build artifact, not the record**. It's gitignored.
The record is the committed CSV export:

```
data/catalog.csv.gz            current catalog, overwritten each run
data/prices/YYYY-MM-DD.csv.gz  one file per day, append-only
```

At ~143KB/day that's about **51MB/year** — small, diffable, and rebuildable
anywhere:

```bash
python3 scripts/export_snapshot.py        # DB  -> CSV  (the Action does this)
python3 scripts/rebuild_from_snapshots.py # CSV -> DB   (after a fresh clone)
```

Committing the SQLite file directly would mean a few hundred MB of
undiffable binary within a year. Gzipped CSV rebuilds in seconds.

## Layout

```
schema.sql                  tables, indexes, views
pokedb/
  config.py                 era selection, throttling, paths
  db.py                     connection handling, schema init
  fees.py                   fee model, breakeven_fvf, sensitivity
  tcgcsv.py                 client + ingester (the price backbone)
scripts/
  init_db.py                create/migrate the database
  ingest_tcgcsv.py          daily price ingest
```

## Data sources

| Source | Cost | Role | Status |
| --- | --- | --- | --- |
| [TCGCSV](https://tcgcsv.com) | Free, no key | Raw single prices, catalog | **Live** |
| [eBay Browse API](https://developer.ebay.com/api-docs/buy/browse/overview.html) | Free, 5k/day | Active listings (buy side) | Phase 3 |
| [PokemonPriceTracker](https://www.pokemonpricetracker.com/pokemon-card-price-api) | $9.99/mo | PSA graded prices | Phase 5 |

Public documented APIs only. No scraping.

**API keys never need to be shared with anyone**, including an AI assistant.
All integrations read from environment variables, so code can be written and
reviewed without the key value ever being visible. Keys live in your local
`.env` (gitignored) and GitHub repository secrets — nowhere else. See
[docs/SECRETS.md](docs/SECRETS.md).

## Two things that will bite you

**TCGCSV has no condition breakdown.** Prices are published at *product ×
printing*, not SKU level — there is no NM/LP/MP/HP. Condition-level pricing
lives behind the real TCGplayer API, which is closed to new applicants. Treat
these numbers as Near Mint and apply `fees.CONDITION_MULTIPLIERS` for anything
else. Those multipliers are **rules of thumb, not measurements** — validate
them against real sales and correct them.

**Most of the catalog is not tradeable.** Of 13,379 priced singles, 10,120
(76%) are worth under $1. The realistic universe for a small bankroll is the
~1,100 cards in the $5–20 band. Filter early.

## What the data says so far

Applying the fee model to the first snapshot (1,901 cards in the $3–40 band,
at an assumed 5% rate):

- The **exclusive edge zone is real but thin** — 355 cards, median profit
  $0.41, only 31 clearing a $1.50 handling threshold.
- The **fee discount is worth ~$0.73 per trade**, about $8 across a $100
  bankroll. A real advantage; not a strategy.
- **Median profit is negative in every rarity.** Modern singles are
  efficiently priced.

The structural finding: buying at TCGplayer low and selling at TCGplayer
market **is not an arbitrage** — it's one order book. Real edge needs a second
venue. That makes eBay ingestion (Phase 3) the critical path rather than an
add-on. Full write-up in `notebooks/01_market_survey.ipynb` §4 and
[PLAN.md](PLAN.md) §12.

## Status

| Phase | State |
| --- | --- |
| 0–1 · schema, fee model, TCGCSV ingester | Complete |
| 2 · market survey, watchlist (189 cards) | Complete |
| 3 · eBay Browse + title parsing | **Next — critical path** |
| 5 · graded prices | Pending |
| 6–7 · trade and reconcile | Pending |
