# Session 04 — eBay keys and smoke test

**Date:** 2026-08-06

Second working block on the same day as session 03, which was already written
and committed when this work began. Logs are append-only, so this is a separate
entry rather than an edit.

## Goal

Prepare for eBay credentials arriving, and close out the session.

## What happened

The owner registered for the eBay Developer Program. Identity check expected
back in **a day**, so keys land ~Aug 7–8. An initial reading of "a week" was
corrected mid-session; the difference matters, because a week would have made
the Aug 10 buy decision impossible and a day keeps it intact.

Researched what arrival day actually looks like and found two traps worth
recording before they cost an evening:

1. **A new production keyset ships disabled.** eBay requires subscribing to, or
   explicitly opting out of, marketplace account deletion/closure notifications
   before the keyset authenticates. The symptom is a generic auth failure that
   points nowhere near the cause.
2. **Sandbox cannot answer this project's question.** Sandbox Browse search
   runs on mock data and returns little or nothing for real queries. It can
   validate OAuth, headers and response parsing — but cross-venue edge is only
   measurable against production. A sandbox result is not evidence about the
   market.

Also confirmed that Browse search returns only `FIXED_PRICE` listings unless
`buyingOptions` is set explicitly. `pokedb/ebay.py` already passes it, but this
is easy to lose in a refactor, and auctions ending at bad hours are precisely
the mispricing this project is hunting.

### Built `scripts/ebay_smoke.py`

`pokedb/ebay.py` was written from documentation and has never touched the live
API, so first contact will probably break somewhere. The smoke test walks the
layers in order — credentials, OAuth, search, response parsing, title matching
— so the first failure names the layer to fix rather than leaving a blind
debug session. It writes nothing to the database and costs one or two calls
against the 5,000/day budget. Verified it fails cleanly and informatively with
no credentials present, which is its state today.

### Housekeeping

`STATE.md` had grown to 225 lines against a stated ~200 budget. Compressed the
findings section — every number and conclusion retained, prose tightened —
back to 208. The rule exists because an unread state file is worse than none.

## Decisions

- **Do the account-deletion compliance step before debugging any code** when
  keys arrive. It is the most likely cause of a first-run auth failure.
- **Do not measure against sandbox.** Validate mechanics there if convenient;
  measure only against production.

## Measurements

None new. Session 03 holds the current numbers.

## Gotchas

Both promoted to `STATE.md`: keyset ships disabled pending compliance, and
sandbox Browse returns mock data only.

## Open at end of session

1. **eBay developer keys** — expected Aug 7–8. Run `scripts/ebay_smoke.py`
   first thing.
2. **Trading Cards category selling limits** — still unchecked. Two minutes in
   Seller Hub, worth doing while the portal is already open.
3. **Exact employee fee discount** — Aug 17.
4. **Hours per week** — still unanswered across four sessions.

Sequence from here: keys → compliance step → smoke test → fix breakage →
`scan_watchlist` → measure cross-venue edge → **buy decision by Aug 10, on
evidence**. If the measurement does not support a trade, buy nothing and let
the collector keep running. That remains a legitimate outcome, not a failure.
