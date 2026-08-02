# Instructions for Claude

## Read this first, every session

**Before doing anything else, read [`sessions/STATE.md`](sessions/STATE.md).**

It carries the whole project's current state: decisions already settled,
findings already measured, gotchas already hit, and what is blocked on what.
Reading it prevents the two failure modes that matter — relitigating settled
decisions, and re-deriving numbers that are already written down.

If you need to know *why* something was decided, read the session log it came
from. `STATE.md` cites them. Don't read all of them; they are long by design
and `STATE.md` exists so you don't have to.

## Project

A price database and decision-support tool for modern-era Pokémon singles,
built to learn the market-data → trade-decision → P&L-reconciliation loop.
Full scope and strategy in [`PLAN.md`](PLAN.md).

## Writing session notes

At the end of a working session, or when a phase completes:

1. **Create a session log** — `python3 scripts/new_session.py "short-slug"`
   creates `sessions/YYYY-MM-DD-NN-short-slug.md` from the template.
   Fill it in. Session logs are **append-only**: once written, don't edit
   them. They are the record of what was believed when.

2. **Update `sessions/STATE.md`** — this one *is* edited, every time. It is a
   living synthesis, not a log. Move new decisions into Decisions, new numbers
   into Findings, resolved blockers out of Open. Delete what is no longer
   true. If STATE.md and a session log disagree, STATE.md wins.

The split is the point: logs are immutable and cheap to write, STATE.md is
distilled and cheap to read. Keep STATE.md under ~200 lines. When it grows
past that, the fix is to compress it, not to let it sprawl.

## Working conventions

- **Verify against real data before designing around an assumption.** Two
  schema errors so far came from designing against imagined API shapes. Hit
  the endpoint first.
- **Record measurements, not impressions.** "Median profit is −$0.90 across
  1,275 cards" beats "the market looks efficient."
- **When a finding contradicts the plan, change the plan and say so.** The
  plan has been substantially rewritten twice from measurements. That is the
  process working.
- **Never share or echo API credentials.** Everything reads from environment
  variables. See [`docs/SECRETS.md`](docs/SECRETS.md).
- **Public documented APIs only.** No scraping.

## Repo map

```
PLAN.md              scope, strategy, phase plan, findings
sessions/STATE.md    current state — read first
sessions/*.md        per-session logs, append-only
pokedb/              config, db, fees, tcgcsv, titles, ebay, analysis
scripts/             init_db, ingest_tcgcsv, export_snapshot,
                     rebuild_from_snapshots, new_session
notebooks/           analysis narratives
tests/               python3 tests/test_titles.py
data/                committed CSV record (the DB is a build artifact)
```
