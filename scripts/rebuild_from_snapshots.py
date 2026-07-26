#!/usr/bin/env python3
"""Rebuild the SQLite database from committed CSV snapshots.

The database is disposable; the CSVs in data/ are the record. Use this to
reconstruct full price history on a new machine, or after deleting the .sqlite:

    git pull
    python3 scripts/rebuild_from_snapshots.py

Sets are reconstructed from the catalog export, which carries the group_id,
abbreviation, name and era for every product.
"""

import csv
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pokedb import db  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRICES_DIR = DATA_DIR / "prices"
CATALOG = DATA_DIR / "catalog.csv.gz"


def _rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        yield from csv.DictReader(fh)


def _num(v):
    """CSV has no NULL — empty string means missing."""
    return float(v) if v not in ("", None) else None


def main() -> int:
    if not CATALOG.exists():
        print(f"missing {CATALOG} — nothing to rebuild from")
        return 1

    with db.session() as conn:
        db.init_schema(conn)
        cur = conn.cursor()

        catalog = list(_rows(CATALOG))

        sets = {
            r["group_id"]: (int(r["group_id"]), r["set_abbr"], r["set_name"], r["era"])
            for r in catalog
        }
        cur.executemany(
            """INSERT INTO sets (group_id, abbreviation, name, era) VALUES (?,?,?,?)
               ON CONFLICT(group_id) DO UPDATE SET
                 abbreviation=excluded.abbreviation, name=excluded.name,
                 era=excluded.era""",
            list(sets.values()),
        )

        cur.executemany(
            """INSERT INTO products (product_id, group_id, name, clean_name,
                                     is_single, number, rarity, card_type)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(product_id) DO UPDATE SET
                 name=excluded.name, clean_name=excluded.clean_name,
                 is_single=excluded.is_single, number=excluded.number,
                 rarity=excluded.rarity, card_type=excluded.card_type""",
            [
                (int(r["product_id"]), int(r["group_id"]), r["name"],
                 r["clean_name"] or None, int(r["is_single"]),
                 r["number"] or None, r["rarity"] or None, r["card_type"] or None)
                for r in catalog
            ],
        )
        conn.commit()
        print(f"catalog: {len(sets):,} sets, {len(catalog):,} products")

        total = 0
        for path in sorted(PRICES_DIR.glob("*.csv.gz")):
            rows = [
                (int(r["product_id"]), r["sub_type_name"], r["as_of_date"],
                 r["source"], _num(r["low_price"]), _num(r["mid_price"]),
                 _num(r["high_price"]), _num(r["market_price"]),
                 _num(r["direct_low_price"]))
                for r in _rows(path)
            ]
            cur.executemany(
                """INSERT INTO price_snapshots
                     (product_id, sub_type_name, as_of_date, source,
                      low_price, mid_price, high_price, market_price,
                      direct_low_price)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(product_id, sub_type_name, as_of_date, source)
                   DO UPDATE SET
                     low_price=excluded.low_price, mid_price=excluded.mid_price,
                     high_price=excluded.high_price,
                     market_price=excluded.market_price,
                     direct_low_price=excluded.direct_low_price""",
                rows,
            )
            conn.commit()
            total += len(rows)
            print(f"  {path.name}: {len(rows):,} prices")

        days = conn.execute(
            "SELECT COUNT(DISTINCT as_of_date) FROM price_snapshots"
        ).fetchone()[0]

    print(f"\nrebuilt: {total:,} price rows across {days} day(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
