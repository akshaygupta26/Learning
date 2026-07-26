#!/usr/bin/env python3
"""Export a day's prices and the current catalog to committed CSV files.

The SQLite database is a local build artifact, not the record. The record is
this directory of gzipped CSVs, which is small, diffable, durable, and
reconstructible on any machine:

    data/catalog.csv.gz            current catalog, overwritten each run
    data/prices/YYYY-MM-DD.csv.gz  one file per snapshot day, append-only

Why not just commit the .sqlite? At ~15k price rows a day, a year of history
is several million rows and a few hundred MB of binary that git cannot diff.
Gzipped CSV is ~150KB/day and rebuilds in seconds.
"""

import argparse
import csv
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pokedb import db  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRICES_DIR = DATA_DIR / "prices"

PRICE_COLUMNS = [
    "product_id", "sub_type_name", "as_of_date", "source",
    "low_price", "mid_price", "high_price", "market_price", "direct_low_price",
]
CATALOG_COLUMNS = [
    "product_id", "group_id", "set_abbr", "set_name", "era",
    "name", "clean_name", "is_single", "number", "rarity", "card_type",
]


def _write_gz(path: Path, columns: list[str], rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(columns)
        for row in rows:
            w.writerow([row[c] for c in columns])
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="snapshot date to export (default: latest in DB)")
    args = ap.parse_args()

    with db.session() as conn:
        date = args.date or conn.execute(
            "SELECT MAX(as_of_date) FROM price_snapshots"
        ).fetchone()[0]
        if not date:
            print("no price data in database — run scripts/ingest_tcgcsv.py first")
            return 1

        prices = conn.execute(
            f"SELECT {','.join(PRICE_COLUMNS)} FROM price_snapshots WHERE as_of_date=?",
            (date,),
        )
        n_prices = _write_gz(PRICES_DIR / f"{date}.csv.gz", PRICE_COLUMNS, prices)

        catalog = conn.execute(
            """
            SELECT p.product_id, p.group_id,
                   s.abbreviation AS set_abbr, s.name AS set_name, s.era,
                   p.name, p.clean_name, p.is_single, p.number, p.rarity,
                   p.card_type
            FROM products p JOIN sets s ON s.group_id = p.group_id
            ORDER BY p.product_id
            """
        )
        n_catalog = _write_gz(DATA_DIR / "catalog.csv.gz", CATALOG_COLUMNS, catalog)

    print(f"{date}: {n_prices:,} prices -> data/prices/{date}.csv.gz")
    print(f"catalog: {n_catalog:,} products -> data/catalog.csv.gz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
