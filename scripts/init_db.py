#!/usr/bin/env python3
"""Create the database and apply schema.sql. Safe to re-run."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pokedb import config, db  # noqa: E402


def main() -> int:
    print(f"database: {config.DB_PATH}")
    with db.session() as conn:
        db.init_schema(conn)
        counts = db.table_counts(conn)

    print("schema applied.\n")
    width = max(len(t) for t in counts)
    for table, n in counts.items():
        print(f"  {table:<{width}}  {n:>8,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
