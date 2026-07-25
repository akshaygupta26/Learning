#!/usr/bin/env python3
"""Daily TCGCSV ingest.

Pulls the modern-era catalog and today's prices into the local database.

    python3 scripts/ingest_tcgcsv.py
    python3 scripts/ingest_tcgcsv.py --limit 3     # smoke test, 3 sets
    python3 scripts/ingest_tcgcsv.py --list        # show scope, fetch nothing

Run daily. TCGCSV serves only today's snapshot and cannot be backfilled, so a
day missed is a day of price history permanently lost.

    0 22 * * *  cd /path/to/Learning && python3 scripts/ingest_tcgcsv.py >> ingest.log 2>&1
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pokedb import config, db, tcgcsv  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, help="only ingest the first N sets")
    ap.add_argument("--list", action="store_true",
                    help="list in-scope sets and exit without ingesting")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    client = tcgcsv.TCGCSVClient()

    if args.list:
        selected = list(tcgcsv.select_groups(client.groups()))
        print(f"{len(selected)} sets in scope "
              f"(eras: {', '.join(config.ERA_PATTERNS)})\n")
        for group, era in sorted(selected, key=lambda x: (x[1], x[0]["name"])):
            print(f"  {era:<4} {group['groupId']:>6}  "
                  f"{(group.get('abbreviation') or '')[:6]:<6}  {group['name']}")
        return 0

    with db.session() as conn:
        db.init_schema(conn)
        stats = tcgcsv.ingest(conn, client=client, limit=args.limit,
                              verbose=not args.quiet)

        print(f"\n{stats['sets_seen']} sets | "
              f"{stats['products_upserted']:,} products | "
              f"{stats['prices_written']:,} prices | "
              f"{stats['requests_made']} requests")

        days = conn.execute(
            "SELECT COUNT(DISTINCT as_of_date) FROM price_snapshots"
        ).fetchone()[0]
        tradeable = conn.execute("SELECT COUNT(*) FROM v_tradeable").fetchone()[0]
        print(f"{days} day(s) of history | {tradeable:,} tradeable singles priced")
        if days < 2:
            print("\nOnly one snapshot so far — trend analysis needs several "
                  "days. Keep this running daily.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
