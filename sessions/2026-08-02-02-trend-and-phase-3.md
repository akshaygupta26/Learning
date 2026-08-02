# Session 02 — trend analysis and Phase 3

**Date:** 2026-08-02

## Goal

Pick the project back up after 8 days away, establish what the accumulated
snapshots show, and advance the critical path.

## What happened

### A false alarm worth recording

The session opened by checking whether the daily ingest had run. The local
clone showed **one** snapshot file and no new commits, and the initial
conclusion was that the Action had never fired and 8 days of trend data were
lost.

That was wrong. The local clone was simply stale — this environment is
ephemeral and had a checkout from the previous session. `git pull` produced 7
bot commits and 8 days of snapshots. The Action had run flawlessly every night.

**Lesson: on a fresh or resumed environment, `git pull` before drawing any
conclusion from working-tree state.**

### The trend analysis that was previously impossible

Rebuilt the DB from committed CSV — 118,122 price rows across 8 days — and ran
the two analyses Notebook 1 explicitly deferred: volatility and spread
persistence.

Both pointed the same way. Prices barely move, and wide spreads do not close.
The 0.703 per-card spread correlation was the decisive number: a card that is
wide stays wide, which means spread is a *characteristic* rather than an
*event*. This settled the Phase 2 hypothesis with measurement instead of
argument.

### Built Phase 3

`pokedb/titles.py` (freeform title → card identity) and `pokedb/ebay.py`
(Browse API client). The title parser is fully testable offline, so it was
built and tested despite having no API credentials — 22 tests.

`analysis.cross_venue_edge()` computes the payoff: buy a live eBay listing,
sell at the TCGplayer reference, net of fees and condition discount.

### The matcher bug

The first version of `match_to_catalog` resolved
`"Charizard ex 223/197 SV Obsidian Flames"` to a **Professor's Research promo**
at **0.95 confidence**. Two independent causes:

1. It queried the catalog on the **numerator alone** (`223`). The catalog
   stores full numbers (`223/197`); only promo sets store bare ones. So `223`
   matched exactly one row — the wrong one.
2. When exactly one row came back, it **skipped name verification entirely**
   and returned full confidence.

This is the expensive failure mode: a confident wrong match prices one card off
another card's comp and loses money silently. Fixed both, added regression
tests, and made the rule explicit in the module.

A second, smaller bug: the condition regex required `NM/M` and so failed to
match bare `NM`, by far the commonest form. Caught by the test suite.

## Decisions

- **Graded subscription deferred.** The $9.99/mo checkpoint from the plan came
  due. Measurements since made graded a worse fit, not better: one slab
  consumes the whole bankroll, PSA turnaround fits no relevant window, and the
  live question moved to cross-venue matching. Schema and parser retain graded
  support, so this is deferral not removal.
- **A collector number alone is never sufficient for a catalog match.** The
  name must corroborate it, even when only one row matches.
- **Scanner should weight newly-listed and ending-soon items.** Follows
  directly from spread persistence: a real mispricing is *new*.

## Measurements

8 days, 2026-07-25 → 2026-08-01, 1,963 card-printings in the $3–40 band.

**Volatility:**

| Measure | Value |
| --- | --- |
| Never changed price | 1.8% |
| Median absolute net move | **3.11%** |
| Moved >10% | 9.0% |

**Spread persistence**, of 551 cards with >30% spread on day 1:

| Measure | Value |
| --- | --- |
| Still >30% on day 8 | **387 (70.2%)** |
| Median spread day 1 → day 8 | 38.5% → 35.1% |
| Per-card spread correlation | **0.703** |

Concrete illustration — Meowth V held a 50% spread for eight straight days
(50% → 49%), while Toxtricity VMAX stayed tight (1% → 3%). Wide stays wide.

**Conclusion: no arbitrage exists inside TCGplayer.** Measured, not argued.

## Gotchas

- **Stale clone in a fresh environment.** Pull before concluding anything.
- **Catalog number formats differ by set type** — `223/197` for regular sets,
  bare `SWSH147` for promos. Matching must handle both, and zero-padding
  varies (`001/131` in catalog vs `1/131` in a seller's title).
- **Catalog names carry qualifiers** sellers never type: `Charizard ex -
  223/197`, `Umbreon VMAX (Alternate Art Secret)`, `Rillaboom - SWSH006
  (Prerelease) [Staff]`. Name matching must strip these, and stripping order
  matters — qualifiers first, then the trailing number, or the `$` anchor
  misses.
- **`pokedb/ebay.py` has never run live.** Written from documentation only.

## Open at end of session

1. **eBay developer keys** — blocks everything in Phase 3. Needed by ~Aug 4.
2. **Trading Cards category selling limits** — unchecked.
3. **Exact employee fee discount** — Aug 17.
4. **Hours per week** — still never answered.

15 days to the pivot. Buy decision must land by **Aug 10** for cards to arrive
before Aug 17.

**If cross-venue edge turns out not to exist either, the correct action is to
buy nothing.** The measurement was always the deliverable.
