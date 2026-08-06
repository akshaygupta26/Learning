#!/usr/bin/env python3
"""Validate the eBay integration end to end. Run this first when keys arrive.

    python3 scripts/ebay_smoke.py
    python3 scripts/ebay_smoke.py --query "charizard ex 223/197"

pokedb/ebay.py was written from documentation and has never touched the live
API, so something probably breaks on first contact. This isolates *where*:
credentials, OAuth, the search call, response parsing, or title matching — in
that order, so the first failure tells you which layer to fix.

Nothing here writes to the database. It is safe to run repeatedly, and costs
one or two calls against the 5,000/day budget.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pokedb import db, ebay, fees, titles  # noqa: E402

OK, BAD, WARN = "  ok  ", " FAIL ", " warn "


def load_dotenv() -> None:
    """Minimal .env loader so this works without extra dependencies."""
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    import os

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query", default="pokemon charizard ex 223/197")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    load_dotenv()

    # 1. Credentials present ------------------------------------------------
    client = ebay.EbayClient()
    if not client.client_id or not client.client_secret:
        print(f"{BAD} credentials missing")
        print("       Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in .env")
        print("       (copy .env.example). See docs/SECRETS.md.")
        return 1
    print(f"{OK} credentials present "
          f"(id ends ...{client.client_id[-4:]}, secret is set)")

    # 2. OAuth --------------------------------------------------------------
    try:
        token = client.token()
    except ebay.EbayError as exc:
        print(f"{BAD} OAuth: {exc}")
        print("       Most common cause: a NEW production keyset ships")
        print("       DISABLED. You must subscribe to, or explicitly opt out")
        print("       of, marketplace account deletion notifications on the")
        print("       developer portal before it will authenticate.")
        return 1
    print(f"{OK} OAuth token acquired (length {len(token)}, "
          f"expires in ~{int(client._token_expires_at - __import__('time').time())}s)")

    # 3. Search -------------------------------------------------------------
    try:
        listings = client.search(args.query, limit=args.limit)
    except ebay.EbayError as exc:
        print(f"{BAD} Browse search: {exc}")
        print("       If this is a 400, suspect the filter syntax in")
        print("       ebay.EbayClient.search — that is the least-verified part.")
        return 1

    if not listings:
        print(f"{WARN} search returned 0 listings for {args.query!r}")
        print("       Not necessarily a bug. Check you are on PRODUCTION —")
        print("       sandbox Browse runs on mock data and returns nothing")
        print("       useful for real queries.")
        return 1
    print(f"{OK} search returned {len(listings)} listings")

    # 4. Response parsing ---------------------------------------------------
    priced = [x for x in listings if x.price > 0]
    with_ship = [x for x in listings if x.shipping_cost > 0]
    print(f"{OK} parsed: {len(priced)}/{len(listings)} have a price, "
          f"{len(with_ship)} have shipping cost")
    if not priced:
        print(f"{BAD} no listing had a usable price — response shape differs")
        print(f"       from what _to_listing expects. Raw title of first: "
              f"{listings[0].title!r}")
        return 1

    # 5. Title parsing and catalog matching ---------------------------------
    print("\n--- title parsing against live listings ---")
    matched = rejected = unmatched = 0
    with db.session() as conn:
        for lst in listings:
            parsed = titles.parse_title(lst.title)
            if not parsed.is_usable:
                rejected += 1
                print(f"  reject[{parsed.reject_reason}]  {lst.title[:60]}")
                continue

            pid, conf = titles.match_to_catalog(conn, parsed)
            if not pid:
                unmatched += 1
                print(f"  no match  (num={parsed.number}) {lst.title[:56]}")
                continue

            row = conn.execute(
                """SELECT p.name, s.abbreviation a, v.market_price
                   FROM products p JOIN sets s ON s.group_id = p.group_id
                   LEFT JOIN v_latest_prices v ON v.product_id = p.product_id
                   WHERE p.product_id = ? LIMIT 1""",
                (pid,),
            ).fetchone()
            matched += 1

            market = row["market_price"]
            edge = ""
            if market:
                net = fees.net_proceeds(market)
                edge = f"  edge ${net - lst.total_cost:+.2f}"
            print(f"  match {conf:.2f}  ${lst.total_cost:6.2f} -> "
                  f"{row['a']} {row['name'][:30]}{edge}")

    print(f"\nmatched {matched} · rejected {rejected} · unmatched {unmatched}")
    print(f"API calls used: {client.call_count} of {ebay.DAILY_CALL_BUDGET}/day")

    if matched == 0:
        print(f"\n{WARN} nothing matched the catalog. Check whether these")
        print("       listings are for cards in the modern era we ingested,")
        print("       and whether the collector number appears in the title.")
        return 1

    print("\nIntegration works. Next: python3 -c \"from pokedb import db, ebay; "
          "ebay.scan_watchlist(db.connect(), ebay.EbayClient())\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
