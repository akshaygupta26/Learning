# Session 03 — twelve day trends

**Date:** 2026-08-06

## Goal

Re-examine the trend picture now that the daily ingest has accumulated 12 days,
up from the 8 that session 02 analysed.

## What happened

Pulled first — the stale-clone lesson from session 02 held, and three new
snapshots (Aug 03–05) came down. Rebuilt to 177,220 price rows across 12 days.

The headline numbers appeared to soften against session 02:

| Measure | 8 days | 12 days |
| --- | --- | --- |
| Spread persistence >30% | 70.2% | 63.7% |
| First-vs-last spread correlation | 0.703 | 0.588 |
| Median absolute move | 3.11% | 3.50% |
| Moved >10% | 9.0% | 13.4% |

Taken at face value that reads as the spread thesis weakening. It is not, and
the reason is a measurement artifact: **first-vs-last correlation conflates
decay with window length.** A longer window mechanically produces a lower
number regardless of the underlying process, and the 11-day figure rests on a
single pair of observations.

Re-measured as autocorrelation at fixed lags, which is not confounded:

| Lag | Mean r | Pairs |
| --- | --- | --- |
| 1 day | 0.842 | 11 |
| 2 days | 0.757 | 10 |
| 3 days | 0.689 | 9 |
| 5 days | 0.707 | 7 |
| 7 days | 0.731 | 5 |

Correlation falls for the first three days and then **plateaus around 0.70**
rather than continuing toward zero. That shape is the informative part: the
initial fall is measurement noise washing out, and the plateau is a structural
component that does not decay. Roughly 70% of a card's spread is a fixed
property of that card.

So the session 02 conclusion survives, better characterised than before.

### The finding that actually changes a decision

Checked market-wide drift, which had not been measured before and matters
directly because the strategy holds inventory across Aug 17.

Equal-weight index over the window: **−0.97%**. Down on 8 of 11 days, 2 up, 1
flat. Median per-card change −0.56%, with 54.5% of cards down. The magnitude is
small but the monotonicity is hard to read as noise — a random walk rarely
produces 8 of 11 in one direction.

At about −0.08%/day, holding two to three weeks across the pivot costs roughly
1.5–2% of position value. On $100 that is $1.50–2.00, against a measured fee
advantage of about $8. **Drift consumes roughly a quarter of the edge.**

## Decisions

- **Sell promptly after Aug 17, do not wait for a better price.** Drift is
  mild but consistently negative, and waiting is a losing trade against it.
  This does not break buy-before-sell-after; it bounds the hold.
- **Prefer fixed-lag autocorrelation over first-vs-last comparisons** for any
  future persistence measurement in this project.

## Measurements

12 days, 2026-07-25 → 2026-08-05, 1,978 card-printings in the $3–40 band,
177,220 price rows.

Volatility: median absolute net move 3.50%; 1.3% never changed; 13.4% moved
>10%; median CV 0.021.

Spread persistence: 548 wide at start, 349 (63.7%) still wide at end, median
38.5% → 34.1%. Autocorrelation plateau ~0.70.

Drift: −0.97% over the window, −0.56% median per card, 54.5% of cards down.

## Gotchas

- **First-vs-last correlation is confounded by window length.** Comparing a
  0.703 measured over 8 days against a 0.588 measured over 12 days is not a
  like-for-like comparison and briefly looked like a real change in the
  market. Use fixed lags.
- **Watch sample size on the longest lag.** The lag-11 figure rests on one
  pair of observations and should not be read as a trend.

## Open at end of session

Unchanged and increasingly urgent — 11 days to the pivot, and the **Aug 10 buy
decision is 4 days out**:

1. **eBay developer keys** — still blocking all of Phase 3.
2. **Trading Cards category selling limits** — still unchecked.
3. **Exact employee fee discount** — Aug 17.
4. **Hours per week** — still unanswered.

Phase 3 has never run against the live API. If the keys do not arrive in time
to scan, measure, and buy by Aug 10, the honest outcome is to buy nothing this
cycle and let the system keep collecting data.
