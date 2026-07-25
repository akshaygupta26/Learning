"""Configuration for the Pokémon price database.

Anything that might reasonably change — fee rates, which sets count as
"modern", request throttling — lives here rather than being scattered through
the code.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("POKEDB_PATH", REPO_ROOT / "pokedb.sqlite"))
SCHEMA_PATH = REPO_ROOT / "schema.sql"


# ---------------------------------------------------------------------------
# TCGCSV
# ---------------------------------------------------------------------------
# Published usage rules (https://tcgcsv.com/docs):
#   - data refreshes exactly once per day, ~20:00 UTC
#   - sleep >= 100ms between requests
#   - <= 10,000 requests per 24h, or risk a ban
#   - a descriptive User-Agent is required; generic ones may be blocked
#
# A full modern-era run is ~90 requests, so we are two orders of magnitude
# inside the daily cap.

TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
POKEMON_CATEGORY_ID = 3  # 85 is "Pokemon Japan", deliberately out of scope

USER_AGENT = os.environ.get(
    "POKEDB_USER_AGENT", "pokemon-price-db/0.1 (+akkiannu@gmail.com)"
)
REQUEST_DELAY_SEC = 0.15  # above the 100ms floor, with margin
REQUEST_TIMEOUT_SEC = 30
MAX_RETRIES = 4
RETRY_BACKOFF_SEC = 2.0  # doubles each attempt


# ---------------------------------------------------------------------------
# Era selection
# ---------------------------------------------------------------------------
# Matched against TCGplayer group names, which are reliably prefixed
# ("SV03: Obsidian Flames", "SWSH01: Sword & Shield Base Set").
#
# Why not filter on publishedOn? Because it is not trustworthy — TCGCSV
# reports POP Series 1 (a 2004 set) as published 2026-07-24. Name prefixes
# are stable; that date field is not.
#
# "Modern" as of 2026 means three eras, not two. Mega Evolution superseded
# Scarlet & Violet as the current standard-legal era.

ERA_PATTERNS = {
    "ME": r"^MEE?\d*[:\s]",          # Mega Evolution — current era (2026)
    "SV": r"^SVE?\d*[A-Z]?[:\s]",    # Scarlet & Violet
    "SWSH": r"^SWSH\d*[:\s]",        # Sword & Shield
}


# ---------------------------------------------------------------------------
# Known release calendar
# ---------------------------------------------------------------------------
# Relevant to hold risk: a new set floods supply and tends to depress chase
# cards from prior sets. Sourced from the TCGCSV group list.

UPCOMING_RELEASES = {
    "2026-09-16": "ME: 30th Celebration",
}
