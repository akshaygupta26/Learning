"""TCGCSV ingestion — the backbone price feed.

TCGCSV (https://tcgcsv.com) is a nightly mirror of TCGplayer's catalog and
pricing. Free, no API key, no signup. It is the best free source available for
raw single prices, and better than most paid options.

GRAIN WARNING
TCGCSV publishes prices at *product x printing*, not at SKU level. There is no
NM/LP/MP/HP breakdown — that lives behind the real TCGplayer API, which is
closed to new applicants. Treat these numbers as Near Mint and apply
fees.CONDITION_MULTIPLIERS for anything else.

Price history cannot be backfilled. TCGCSV serves today's snapshot only, so
every day this job does not run is a day of history that does not exist later.
Run it daily.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterator

from . import config


class TCGCSVError(RuntimeError):
    pass


class TCGCSVClient:
    """Throttled JSON client honouring TCGCSV's published usage rules."""

    def __init__(self, user_agent: str | None = None) -> None:
        self.user_agent = user_agent or config.USER_AGENT
        self.request_count = 0
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < config.REQUEST_DELAY_SEC:
            time.sleep(config.REQUEST_DELAY_SEC - elapsed)

    def get(self, path: str) -> dict[str, Any]:
        """GET a TCGCSV path, with throttling and retry on transient failure."""
        url = f"{config.TCGCSV_BASE}/{path.lstrip('/')}"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})

        last_error: Exception | None = None
        for attempt in range(config.MAX_RETRIES):
            self._throttle()
            try:
                with urllib.request.urlopen(
                    req, timeout=config.REQUEST_TIMEOUT_SEC
                ) as resp:
                    payload = json.load(resp)
                self._last_request_at = time.monotonic()
                self.request_count += 1

                if not payload.get("success", True):
                    raise TCGCSVError(f"{url}: {payload.get('errors')}")
                return payload

            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                self._last_request_at = time.monotonic()
                # 429 means we tripped the IP throttle; back off hard.
                status = getattr(exc, "code", None)
                backoff = config.RETRY_BACKOFF_SEC * (2**attempt)
                if status == 429:
                    backoff = max(backoff, 60.0)
                if attempt < config.MAX_RETRIES - 1:
                    time.sleep(backoff)

        raise TCGCSVError(f"{url} failed after {config.MAX_RETRIES} attempts: {last_error}")

    def groups(self, category_id: int = config.POKEMON_CATEGORY_ID) -> list[dict]:
        return self.get(f"{category_id}/groups")["results"]

    def products(self, group_id: int, category_id: int = config.POKEMON_CATEGORY_ID) -> list[dict]:
        return self.get(f"{category_id}/{group_id}/products")["results"]

    def prices(self, group_id: int, category_id: int = config.POKEMON_CATEGORY_ID) -> list[dict]:
        return self.get(f"{category_id}/{group_id}/prices")["results"]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def classify_era(group_name: str) -> str | None:
    """Map a set name to its era, or None if outside our scope."""
    for era, pattern in config.ERA_PATTERNS.items():
        if re.match(pattern, group_name):
            return era
    return None


def _extended(product: dict) -> dict[str, str]:
    return {e["name"]: e["value"] for e in product.get("extendedData") or []}


def parse_product(product: dict) -> dict[str, Any]:
    """Flatten a TCGCSV product into a row for the `products` table.

    Singles carry a "Number" field in extendedData; sealed product does not.
    That presence check is the only reliable single/sealed discriminator in
    the feed.

    Newly released sets ship with sparse extendedData — ME05 launched with
    only CardText and UPC, no Rarity or Number — so a brand-new set's cards
    can look like sealed product for a few days until TCGplayer backfills.
    Re-running the ingest picks up the corrections.
    """
    ext = _extended(product)
    number = ext.get("Number")
    return {
        "product_id": product["productId"],
        "group_id": product["groupId"],
        "name": product["name"],
        "clean_name": product.get("cleanName"),
        "is_single": 1 if number else 0,
        "number": number,
        "rarity": ext.get("Rarity"),
        "card_type": ext.get("Card Type"),
        "hp": ext.get("HP"),
        "image_url": product.get("imageUrl"),
        "url": product.get("url"),
        "modified_on": product.get("modifiedOn"),
    }


def select_groups(groups: list[dict]) -> Iterator[tuple[dict, str]]:
    """Yield (group, era) for every in-scope set."""
    for g in groups:
        era = classify_era(g["name"])
        if era:
            yield g, era


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest(conn, client: TCGCSVClient | None = None, limit: int | None = None,
           verbose: bool = True) -> dict[str, int]:
    """Pull the modern-era catalog and today's prices into the database.

    Idempotent: products upsert, and price rows are keyed by
    (product_id, printing, date, source), so a same-day re-run replaces rather
    than duplicates.
    """
    client = client or TCGCSVClient()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    started = datetime.now(timezone.utc).isoformat()

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ingest_runs (source, started_at) VALUES (?, ?)",
        ("tcgcsv", started),
    )
    run_id = cur.lastrowid
    conn.commit()

    stats = {"sets_seen": 0, "products_upserted": 0, "prices_written": 0}

    try:
        selected = list(select_groups(client.groups()))
        if limit:
            selected = selected[:limit]

        if verbose:
            print(f"{len(selected)} sets in scope; snapshot date {today}")

        for i, (group, era) in enumerate(selected, 1):
            gid = group["groupId"]

            cur.execute(
                """
                INSERT INTO sets (group_id, abbreviation, name, era,
                                  published_on, is_supplemental, modified_on)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    abbreviation=excluded.abbreviation,
                    name=excluded.name,
                    era=excluded.era,
                    published_on=excluded.published_on,
                    is_supplemental=excluded.is_supplemental,
                    modified_on=excluded.modified_on
                """,
                (gid, group.get("abbreviation"), group["name"], era,
                 group.get("publishedOn"), int(bool(group.get("isSupplemental"))),
                 group.get("modifiedOn")),
            )
            stats["sets_seen"] += 1

            rows = [parse_product(p) for p in client.products(gid)]
            cur.executemany(
                """
                INSERT INTO products (product_id, group_id, name, clean_name,
                                      is_single, number, rarity, card_type, hp,
                                      image_url, url, modified_on)
                VALUES (:product_id, :group_id, :name, :clean_name, :is_single,
                        :number, :rarity, :card_type, :hp, :image_url, :url,
                        :modified_on)
                ON CONFLICT(product_id) DO UPDATE SET
                    name=excluded.name,
                    clean_name=excluded.clean_name,
                    is_single=excluded.is_single,
                    number=excluded.number,
                    rarity=excluded.rarity,
                    card_type=excluded.card_type,
                    hp=excluded.hp,
                    image_url=excluded.image_url,
                    url=excluded.url,
                    modified_on=excluded.modified_on
                """,
                rows,
            )
            stats["products_upserted"] += len(rows)

            known = {r["product_id"] for r in rows}
            # Guard against price rows for products this group didn't return —
            # the foreign key would reject them and abort the batch.
            price_rows = [
                (pr["productId"], pr["subTypeName"], today, "tcgcsv",
                 pr.get("lowPrice"), pr.get("midPrice"), pr.get("highPrice"),
                 pr.get("marketPrice"), pr.get("directLowPrice"))
                for pr in client.prices(gid)
                if pr["productId"] in known
            ]
            cur.executemany(
                """
                INSERT INTO price_snapshots
                    (product_id, sub_type_name, as_of_date, source,
                     low_price, mid_price, high_price, market_price,
                     direct_low_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, sub_type_name, as_of_date, source)
                DO UPDATE SET
                    low_price=excluded.low_price,
                    mid_price=excluded.mid_price,
                    high_price=excluded.high_price,
                    market_price=excluded.market_price,
                    direct_low_price=excluded.direct_low_price
                """,
                price_rows,
            )
            stats["prices_written"] += len(price_rows)
            conn.commit()

            if verbose:
                print(f"  [{i:>2}/{len(selected)}] {era:<4} "
                      f"{(group.get('abbreviation') or '')[:6]:<6} "
                      f"{group['name'][:38]:<38} "
                      f"{len(rows):>4} products  {len(price_rows):>4} prices")

        cur.execute(
            """
            UPDATE ingest_runs
               SET finished_at=?, status='ok', sets_seen=?, products_upserted=?,
                   prices_written=?, requests_made=?
             WHERE run_id=?
            """,
            (datetime.now(timezone.utc).isoformat(), stats["sets_seen"],
             stats["products_upserted"], stats["prices_written"],
             client.request_count, run_id),
        )
        conn.commit()

    except Exception as exc:
        cur.execute(
            """
            UPDATE ingest_runs
               SET finished_at=?, status='failed', error=?, sets_seen=?,
                   products_upserted=?, prices_written=?, requests_made=?
             WHERE run_id=?
            """,
            (datetime.now(timezone.utc).isoformat(), str(exc)[:500],
             stats["sets_seen"], stats["products_upserted"],
             stats["prices_written"], client.request_count, run_id),
        )
        conn.commit()
        raise

    stats["requests_made"] = client.request_count
    return stats
