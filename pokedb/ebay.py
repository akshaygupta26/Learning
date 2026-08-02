"""eBay Browse API client — the second venue, and the whole point of Phase 3.

Phase 2 established that buying at TCGplayer low and selling at TCGplayer
market is not an arbitrage: it is one order book, and the 8-day snapshot
series showed 70% of wide spreads persisting unchanged. A spread that sits
still for eight days is a property of the card, not an opportunity.

Real edge needs a second, less efficient venue. This is it. TCGplayer is the
reference price; eBay is where the mispricing lives — bad titles, missing set
names, no card number, auctions ending at 3am.

STATUS: written against eBay's published documentation but NOT yet executed
against the live API, because that requires credentials. Expect to fix
something on first contact — response shapes and filter syntax are the usual
culprits. Every field access here is defensive for that reason.

Credentials come from the environment and are never hardcoded. See
docs/SECRETS.md.

Rate limit: 5,000 calls/day on the free tier, tied to your keyset.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from . import titles

OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
# The base application scope, which is what Browse requires.
SCOPE = "https://api.ebay.com/oauth/api_scope"
MARKETPLACE = "EBAY_US"

DAILY_CALL_BUDGET = 5000


class EbayError(RuntimeError):
    pass


class MissingCredentials(EbayError):
    pass


@dataclass
class Listing:
    """One active eBay listing, normalised."""

    listing_id: str
    title: str
    price: float
    shipping_cost: float
    condition: str | None
    seller: str | None
    buying_options: str
    end_time: str | None
    url: str | None

    @property
    def total_cost(self) -> float:
        """What you actually pay. Shipping is not a rounding error at this size."""
        return self.price + self.shipping_cost


class EbayClient:
    """Browse API client with client-credentials OAuth and token caching."""

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self.client_id = client_id or os.environ.get("EBAY_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("EBAY_CLIENT_SECRET", "")
        self._token: str | None = None
        self._token_expires_at = 0.0
        self.call_count = 0

    def _require_credentials(self) -> None:
        if not self.client_id or not self.client_secret:
            raise MissingCredentials(
                "EBAY_CLIENT_ID and EBAY_CLIENT_SECRET must be set. "
                "Copy .env.example to .env and fill them in — see docs/SECRETS.md."
            )

    def token(self) -> str:
        """A valid application access token, refreshed when near expiry.

        Tokens last ~2 hours. Refreshed 60s early to avoid racing the clock.
        """
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        self._require_credentials()
        basic = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        body = urllib.parse.urlencode(
            {"grant_type": "client_credentials", "scope": SCOPE}
        ).encode()

        req = urllib.request.Request(
            OAUTH_URL,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as exc:
            # Deliberately does not echo the request — the Authorization
            # header carries your secret.
            raise EbayError(
                f"OAuth failed with HTTP {exc.code}. Check that the keyset is a "
                f"*production* keyset and that both values are correct."
            ) from None

        self._token = payload["access_token"]
        self._token_expires_at = time.time() + float(payload.get("expires_in", 7200))
        return self._token

    def search(
        self,
        query: str,
        *,
        min_price: float = 3.0,
        max_price: float = 40.0,
        limit: int = 50,
        buying_options: tuple[str, ...] = ("FIXED_PRICE", "AUCTION"),
        us_only: bool = True,
    ) -> list[Listing]:
        """Search active listings. Returns normalised Listings.

        Filters are applied server-side where possible: every listing excluded
        by eBay is one that doesn't consume the daily call budget on our side.
        """
        filters = [
            f"price:[{min_price}..{max_price}]",
            "priceCurrency:USD",
            f"buyingOptions:{{{'|'.join(buying_options)}}}",
        ]
        if us_only:
            filters.append("itemLocationCountry:US")

        params = urllib.parse.urlencode({
            "q": query,
            "filter": ",".join(filters),
            "limit": str(min(limit, 200)),
        })

        req = urllib.request.Request(
            f"{BROWSE_SEARCH_URL}?{params}",
            headers={
                "Authorization": f"Bearer {self.token()}",
                "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise EbayError("rate limited — daily call budget likely exhausted") from None
            raise EbayError(f"Browse search failed: HTTP {exc.code}") from None

        self.call_count += 1
        return [_to_listing(it) for it in payload.get("itemSummaries") or []]


def _to_listing(item: dict) -> Listing:
    """Normalise one itemSummary. Defensive: eBay omits fields freely."""
    price = float((item.get("price") or {}).get("value") or 0)

    shipping = 0.0
    for opt in item.get("shippingOptions") or []:
        cost = (opt.get("shippingCost") or {}).get("value")
        if cost is not None:
            shipping = float(cost)
            break

    return Listing(
        listing_id=item.get("itemId", ""),
        title=item.get("title", ""),
        price=price,
        shipping_cost=shipping,
        condition=item.get("condition"),
        seller=(item.get("seller") or {}).get("username"),
        buying_options=",".join(item.get("buyingOptions") or []),
        end_time=item.get("itemEndDate"),
        url=item.get("itemWebUrl"),
    )


def build_query(product_name: str, number: str | None) -> str:
    """Search string for one catalog product.

    Includes the collector number when available: it is the highest-signal
    token a seller can type, and its presence in a title correlates with a
    seller who knows what they have (and therefore prices it correctly). The
    mispricings live in titles *without* numbers — which is exactly why the
    parser must handle both.
    """
    core = titles.CATALOG_QUALIFIER.sub(" ", product_name)
    core = titles.CATALOG_NUMBER_SUFFIX.sub(" ", core.strip())
    parts = ["pokemon", core.strip()]
    if number:
        parts.append(number)
    return " ".join(p for p in parts if p)


def scan_watchlist(conn, client: EbayClient, limit_products: int | None = None,
                   verbose: bool = True) -> dict[str, int]:
    """Search eBay for every watchlist card and store matched listings.

    One API call per product. The watchlist is ~190 cards, so a full scan is
    ~190 of the 5,000 daily calls.
    """
    products = conn.execute(
        """
        SELECT p.product_id, p.name, p.number
        FROM watchlist w JOIN products p ON p.product_id = w.product_id
        ORDER BY p.product_id
        """
    ).fetchall()
    if limit_products:
        products = products[:limit_products]

    stats = {"searched": 0, "listings_seen": 0, "matched": 0, "rejected": 0}
    now = datetime.now(timezone.utc).isoformat()

    for row in products:
        listings = client.search(build_query(row["name"], row["number"]))
        stats["searched"] += 1
        stats["listings_seen"] += len(listings)

        for lst in listings:
            parsed = titles.parse_title(lst.title)
            if not parsed.is_usable:
                stats["rejected"] += 1
                continue

            matched_id, confidence = titles.match_to_catalog(conn, parsed)
            # Only store listings that resolve to the product we searched for.
            # A match to a *different* card is a parser success but a scan
            # miss, and storing it would silently corrupt the comparison.
            if matched_id != row["product_id"]:
                continue

            conn.execute(
                """
                INSERT INTO ebay_listings
                    (listing_id, product_id, raw_title, price, shipping_cost,
                     condition_parsed, grade_parsed, seller, listing_type,
                     end_time, observed_at, match_confidence)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(listing_id) DO UPDATE SET
                    price=excluded.price,
                    shipping_cost=excluded.shipping_cost,
                    observed_at=excluded.observed_at,
                    match_confidence=excluded.match_confidence
                """,
                (lst.listing_id, matched_id, lst.title, lst.price,
                 lst.shipping_cost, parsed.condition,
                 f"{parsed.grader} {parsed.grade}" if parsed.is_graded else None,
                 lst.seller, lst.buying_options, lst.end_time, now, confidence),
            )
            stats["matched"] += 1

        conn.commit()
        if verbose and stats["searched"] % 25 == 0:
            print(f"  {stats['searched']}/{len(products)} products, "
                  f"{stats['matched']} listings matched")

    return stats
