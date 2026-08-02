"""Analysis helpers for the market survey notebooks.

Logic lives here rather than in notebook cells so it can be tested, reused,
and diffed. Notebooks narrate; this module computes.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pandas as pd

from . import fees

# Below this, shipping and the per-order fee exceed the card's entire value.
# 76% of the modern catalog sits here. It is bulk, not inventory.
BULK_CEILING = 3.00

# Minimum net profit worth the handling: sourcing, listing, packing, shipping,
# and the risk of a return. Under this, a "profitable" trade is a donation of
# your time.
MIN_WORTHWHILE_PROFIT = 1.50


def load_tradeable(
    conn: sqlite3.Connection,
    min_price: float = BULK_CEILING,
    max_price: float = 40.0,
) -> pd.DataFrame:
    """Singles with a live market price in a bankroll-appropriate band."""
    return pd.read_sql(
        """
        SELECT product_id, name, set_abbr, set_name, era, rarity,
               sub_type_name, as_of_date,
               low_price, mid_price, market_price, high_price
        FROM v_tradeable
        WHERE market_price BETWEEN ? AND ?
          AND low_price IS NOT NULL AND low_price > 0
        """,
        conn,
        params=(min_price, max_price),
    )


def add_edge_columns(df: pd.DataFrame, your_rate: float | None = None) -> pd.DataFrame:
    """Attach the fee-model columns that drive every ranking.

    Models buying at the lowest listing and selling at market price.

    THIS IS AN OPTIMISTIC SCREEN, NOT A TRADE. See `spread_is_suspicious`.
    `low_price` is the cheapest *listing*, which is frequently a damaged,
    misdescribed, or non-English copy. `market_price` is a rolling average of
    *completed sales*. You cannot buy at low and sell at market on the same
    venue anyway — you would be relisting into the book you just bought from.
    Treat the output as a shortlist to verify against another venue, never as
    a signal to buy.
    """
    rate = fees.EBAY_FVF_RATE if your_rate is None else your_rate
    out = df.copy()

    out["breakeven_fvf"] = [
        fees.breakeven_fvf(m, l) for m, l in zip(out.market_price, out.low_price)
    ]
    out["edge_zone"] = [fees.edge_zone(b, rate) for b in out.breakeven_fvf]

    out["net_at_your_rate"] = [
        fees.net_proceeds(m, fvf_rate=rate) for m in out.market_price
    ]
    out["net_at_retail"] = [
        fees.net_proceeds(m, fvf_rate=fees.RETAIL_EBAY_FVF) for m in out.market_price
    ]
    out["profit_at_your_rate"] = out.net_at_your_rate - out.low_price
    out["profit_at_retail"] = out.net_at_retail - out.low_price

    # What the fee discount alone is worth on this trade.
    out["fee_advantage"] = out.profit_at_your_rate - out.profit_at_retail

    # Dispersion. A wide low-to-market gap means either an opportunity or,
    # far more often, a data artifact.
    out["spread_pct"] = (out.market_price - out.low_price) / out.market_price
    out["spread_is_suspicious"] = out.spread_pct > 0.50

    return out


def price_band_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """How the whole priced universe distributes across value bands."""
    return pd.read_sql(
        """
        SELECT CASE
                 WHEN market_price < 1   THEN 'under $1'
                 WHEN market_price < 3   THEN '$1-3'
                 WHEN market_price < 5   THEN '$3-5'
                 WHEN market_price < 20  THEN '$5-20'
                 WHEN market_price < 100 THEN '$20-100'
                 ELSE '$100+'
               END                AS band,
               COUNT(*)           AS cards,
               ROUND(MIN(market_price), 2) AS min_price,
               ROUND(MAX(market_price), 2) AS max_price
        FROM v_tradeable
        GROUP BY band
        ORDER BY MIN(market_price)
        """,
        conn,
    )


def rarity_summary(df: pd.DataFrame, min_count: int = 20) -> pd.DataFrame:
    """Median value and edge by rarity, for rarities with enough cards."""
    g = (
        df.groupby("rarity")
        .agg(
            cards=("product_id", "count"),
            median_price=("market_price", "median"),
            median_spread=("spread_pct", "median"),
            median_profit=("profit_at_your_rate", "median"),
        )
        .query("cards >= @min_count")
        .sort_values("median_profit", ascending=False)
    )
    return g.round(3)


def edge_zone_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Card counts and economics per edge zone — the §3 thesis, quantified."""
    g = df.groupby("edge_zone").agg(
        cards=("product_id", "count"),
        median_profit=("profit_at_your_rate", "median"),
        max_profit=("profit_at_your_rate", "max"),
        clearing_threshold=(
            "profit_at_your_rate",
            lambda s: int((s >= MIN_WORTHWHILE_PROFIT).sum()),
        ),
    )
    return g.round(2)


def candidates(
    df: pd.DataFrame,
    min_profit: float = MIN_WORTHWHILE_PROFIT,
    exclude_suspicious: bool = True,
) -> pd.DataFrame:
    """Shortlist: profitable at your rate, worth the handling, not obviously fake.

    `exclude_suspicious` drops spreads over 50%. Those are not gifts. A $30
    card listed at $9 is a damaged copy, a misidentified print, a non-English
    version, or a listing that has already sold. Filtering them out is the
    difference between a screen and a fantasy.
    """
    out = df[df.profit_at_your_rate >= min_profit]
    if exclude_suspicious:
        out = out[~out.spread_is_suspicious]
    return out.sort_values("profit_at_your_rate", ascending=False)


def write_watchlist(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    discount_to_market: float = 0.15,
    note: str = "notebook 01 market survey",
) -> int:
    """Persist a shortlist to the `watchlist` table.

    `target_buy_price` is set below the current low rather than at it — if you
    pay the current low you have captured nothing, because that price is
    already public and already competed for.
    """
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (int(r.product_id), round(float(r.low_price) * (1 - discount_to_market), 2),
         note, now)
        for r in df.itertuples()
    ]
    conn.executemany(
        """
        INSERT INTO watchlist (product_id, target_buy_price, notes, added_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(product_id) DO UPDATE SET
            target_buy_price=excluded.target_buy_price,
            notes=excluded.notes,
            added_at=excluded.added_at
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def history_depth(conn: sqlite3.Connection) -> int:
    """Distinct snapshot days collected. Trend work needs several."""
    return conn.execute(
        "SELECT COUNT(DISTINCT as_of_date) FROM price_snapshots"
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# Trend and persistence — requires several snapshot days
# ---------------------------------------------------------------------------

def load_series(
    conn: sqlite3.Connection,
    min_price: float = BULK_CEILING,
    max_price: float = 40.0,
) -> pd.DataFrame:
    """Full price history for the tradeable band, one row per card-day."""
    df = pd.read_sql(
        """
        SELECT ps.product_id, ps.sub_type_name, ps.as_of_date,
               ps.low_price, ps.market_price
        FROM price_snapshots ps
        JOIN products p ON p.product_id = ps.product_id
        WHERE p.is_single = 1
          AND ps.market_price BETWEEN ? AND ?
          AND ps.low_price > 0
        """,
        conn,
        params=(min_price, max_price),
    )
    df["spread_pct"] = (df.market_price - df.low_price) / df.market_price
    return df


def volatility(series: pd.DataFrame) -> pd.DataFrame:
    """Per-card price movement across the collected window."""
    v = series.groupby(["product_id", "sub_type_name"]).market_price.agg(
        n_distinct="nunique", p_first="first", p_last="last",
        p_std="std", p_mean="mean",
    )
    v = v[v.p_mean > 0].copy()
    v["net_change"] = (v.p_last - v.p_first) / v.p_first
    v["cv"] = v.p_std / v.p_mean
    return v


def spread_persistence(
    series: pd.DataFrame, wide_threshold: float = 0.30
) -> dict[str, float]:
    """Do wide low-to-market spreads close, or do they just sit there?

    This is the decisive test for whether the TCGplayer-internal spread is an
    opportunity or an artifact. A genuine mispricing gets taken within a day
    or two in a liquid market. One that persists for a week is telling you
    the two prices describe different things — a damaged copy versus a Near
    Mint one, or a misidentified print.
    """
    pivot = series.pivot_table(
        index=["product_id", "sub_type_name"], columns="as_of_date",
        values="spread_pct",
    )
    if pivot.shape[1] < 2:
        return {"days": pivot.shape[1]}

    d0, d1 = pivot.columns[0], pivot.columns[-1]
    both = pivot[[d0, d1]].dropna()
    wide = both[both[d0] > wide_threshold]

    return {
        "days": pivot.shape[1],
        "first_date": d0,
        "last_date": d1,
        "wide_at_start": len(wide),
        "still_wide_at_end": int((wide[d1] > wide_threshold).sum()),
        "persistence_rate": float((wide[d1] > wide_threshold).mean()) if len(wide) else 0.0,
        "median_spread_start": float(wide[d0].median()) if len(wide) else 0.0,
        "median_spread_end": float(wide[d1].median()) if len(wide) else 0.0,
        "spread_correlation": float(both[d0].corr(both[d1])),
    }


# ---------------------------------------------------------------------------
# Cross-venue — what Phase 3 exists to compute
# ---------------------------------------------------------------------------

def cross_venue_edge(
    conn: sqlite3.Connection,
    min_confidence: float = 0.5,
    your_rate: float | None = None,
) -> pd.DataFrame:
    """Buy an active eBay listing, sell at the TCGplayer reference price.

    This is a genuine two-venue comparison, unlike the single-book screen in
    Notebook 1: the buy price is a real amount someone will accept right now
    on one venue, and the sell price is a trailing average of completed sales
    on another.

    `min_confidence` gates on title-match quality. Low-confidence matches are
    the ones most likely to be pricing one card off another card's comp.
    """
    rate = fees.EBAY_FVF_RATE if your_rate is None else your_rate

    df = pd.read_sql(
        """
        SELECT e.listing_id, e.raw_title, e.price, e.shipping_cost,
               e.condition_parsed, e.grade_parsed, e.listing_type,
               e.end_time, e.match_confidence,
               p.name, p.number, s.abbreviation AS set_abbr,
               v.market_price, v.sub_type_name
        FROM ebay_listings e
        JOIN products p ON p.product_id = e.product_id
        JOIN sets s     ON s.group_id   = p.group_id
        JOIN v_latest_prices v ON v.product_id = e.product_id
        WHERE e.match_confidence >= ?
          AND e.grade_parsed IS NULL
          AND v.market_price > 0
        """,
        conn,
        params=(min_confidence,),
    )
    if df.empty:
        return df

    # A listing's true cost includes shipping; comparing item price alone
    # overstates edge by a dollar or more on cards worth ten.
    df["total_cost"] = df.price + df.shipping_cost

    # Condition discount: TCGCSV prices are Near Mint equivalents, so a played
    # copy must be marked down before comparison.
    df["condition_mult"] = (
        df.condition_parsed.map(fees.CONDITION_MULTIPLIERS).fillna(1.0)
    )
    df["adj_market"] = df.market_price * df.condition_mult

    df["net_if_sold"] = [
        fees.net_proceeds(m, fvf_rate=rate) for m in df.adj_market
    ]
    df["edge"] = df.net_if_sold - df.total_cost
    df["breakeven_fvf"] = [
        fees.breakeven_fvf(m, c) for m, c in zip(df.adj_market, df.total_cost)
    ]
    df["edge_zone"] = [fees.edge_zone(b, rate) for b in df.breakeven_fvf]

    return df.sort_values("edge", ascending=False)
