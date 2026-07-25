"""Fee model — the thesis of this project.

Edge on modern raw singles comes from cost structure, not card selection.
Everyone reads the same TCGplayer market price; nobody out-picks the market
on which Charizard appreciates. But a reduced final value fee opens a band of
trades that *lose money at retail rates and profit at yours* — trades no
retail flipper is competing for, because for them they are not trades at all.

`breakeven_fvf` is the function that finds them.

Worked example, buy at $8 and sell at $11:

                        Retail (13.25%)    Employee (5%)
    Gross                     $11.00           $11.00
    Final value fee           -$1.46           -$0.55
    Per-order fee             -$0.40           -$0.40
    Shipping (PWE)            -$1.25           -$1.25
    Supplies                  -$0.30           -$0.30
                             -------          -------
    Net proceeds               $7.59            $8.50
    Cost basis                -$8.00           -$8.00
                             -------          -------
    Profit                    -$0.41           +$0.50
                              LOSS             PROFIT

Breakeven FVF is 9.55%: below it the trade works, above it it doesn't.

WARNING: every rate below must be verified against the current published fee
schedule before trading. They change, and a stale rate here silently corrupts
every ranking the database produces.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# eBay's standard final value fee for trading cards. The number a retail
# flipper pays, and the benchmark an employee rate is measured against.
RETAIL_EBAY_FVF = 0.1325

# Your rate. Defaults to retail so the model is never accidentally optimistic.
# OVERRIDE ON AUG 17 with the real employee rate — see PLAN.md section 3.
EBAY_FVF_RATE = float(os.environ.get("EBAY_FVF_RATE", RETAIL_EBAY_FVF))


@dataclass(frozen=True)
class VenueFees:
    """Fee structure for one selling venue."""

    name: str
    rate: float                    # proportional fee on gross
    per_order: float = 0.0         # flat fee per order
    rate_applies_to_shipping: bool = True


VENUES = {
    "ebay": VenueFees(
        name="ebay",
        rate=EBAY_FVF_RATE,
        per_order=0.40,
        rate_applies_to_shipping=True,
    ),
    "tcgplayer": VenueFees(
        name="tcgplayer",
        rate=0.1025 + 0.025,  # commission + payment processing
        per_order=0.0,
        rate_applies_to_shipping=False,
    ),
}

# Shipping options. PWE (plain white envelope) with tracking is the standard
# for cards under ~$20; bubble mailers above that, where loss risk matters.
SHIPPING = {
    "pwe_tracked": 1.25,
    "bmwt": 5.00,
}

# Sleeve + toploader + team bag.
SUPPLIES_COST = 0.30

# UNVALIDATED ASSUMPTION — do not treat as fact.
# TCGCSV exposes no condition breakdown, so its prices are effectively Near
# Mint. These multipliers approximate what other conditions fetch. They are
# rules of thumb, not measurements. Validate them against real sales in
# Notebook 3 and correct them here.
CONDITION_MULTIPLIERS = {
    "NM": 1.00,
    "LP": 0.85,
    "MP": 0.70,
    "HP": 0.55,
    "DMG": 0.35,
}


def net_proceeds(
    gross: float,
    venue: str = "ebay",
    *,
    fvf_rate: float | None = None,
    shipping_charged: float = 0.0,
    shipping_cost: float = SHIPPING["pwe_tracked"],
    supplies: float = SUPPLIES_COST,
) -> float:
    """What actually lands in your account after selling at `gross`.

    `fvf_rate` overrides the venue's configured rate — used by the sensitivity
    analysis to price the same trade at 13.25% / 10% / 5% / 0%.
    """
    v = VENUES[venue]
    rate = v.rate if fvf_rate is None else fvf_rate

    fee_base = gross + shipping_charged if v.rate_applies_to_shipping else gross
    fee = fee_base * rate

    return gross + shipping_charged - fee - v.per_order - shipping_cost - supplies


def breakeven_fvf(
    gross: float,
    cost_basis: float,
    venue: str = "ebay",
    *,
    shipping_charged: float = 0.0,
    shipping_cost: float = SHIPPING["pwe_tracked"],
    supplies: float = SUPPLIES_COST,
) -> float:
    """The fee rate at which this trade exactly breaks even.

    Above this rate the trade loses money, below it the trade profits. The
    single most important derived number in the database: it converts "is this
    a good trade?" into "is this a good trade *for me*?".

    Returns a rate, e.g. 0.0955 for 9.55%. May be negative, meaning the trade
    loses money even with zero fees.
    """
    v = VENUES[venue]
    fee_base = gross + shipping_charged if v.rate_applies_to_shipping else gross
    if fee_base <= 0:
        return float("-inf")

    affordable_fee = (
        gross + shipping_charged - cost_basis - v.per_order - shipping_cost - supplies
    )
    return affordable_fee / fee_base


def edge_zone(breakeven: float, your_rate: float = EBAY_FVF_RATE) -> str:
    """Classify a trade by who can profitably make it.

    - "open"      : profitable at retail rates too. Crowded and thin.
    - "exclusive" : profitable for you, not for a retail flipper. Hunt here.
    - "dead"      : unprofitable at any rate you can access.
    """
    if breakeven > RETAIL_EBAY_FVF:
        return "open"
    if breakeven > your_rate:
        return "exclusive"
    return "dead"


def sensitivity(gross: float, cost_basis: float, venue: str = "ebay") -> dict:
    """Profit on one trade across candidate fee rates.

    Built now so that on Aug 17 plugging in the real employee rate is a config
    change rather than a rewrite.
    """
    rates = [RETAIL_EBAY_FVF, 0.10, 0.05, 0.0]
    return {
        rate: net_proceeds(gross, venue, fvf_rate=rate) - cost_basis
        for rate in rates
    }
