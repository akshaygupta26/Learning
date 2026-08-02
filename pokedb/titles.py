"""Parse freeform eBay listing titles into structured card identities.

This is the hardest part of the project and the part that decides whether
cross-venue arbitrage is measurable at all. TCGplayer has clean structured
data; eBay has whatever the seller typed. Real titles look like:

    Charizard ex 223/197 SV Obsidian Flames SIR PSA 10 GEM MINT
    Pokemon Umbreon VMAX Alt Art 215/203 Evolving Skies NM
    pokemon card rare holo lot of 5 charizard
    Mew ex 216/091 Paldean Fates SIR NM/M

The parser's job is to extract what can be extracted, and — more importantly —
to *refuse* confidently on titles that cannot be matched safely. A wrong match
prices one card off another card's comp, which is worse than no match at all.

Design bias: high precision over high recall. Skipping a real opportunity
costs nothing. Buying a proxy because the title parsed cleanly costs the
bankroll.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Collector numbers, in rough order of specificity. These carry most of the
# matching signal — a card number plus a set is nearly a unique key, while a
# name alone is not ("Pikachu" appears in hundreds of products).
NUMBER_PATTERNS = [
    # Trainer/Galarian Gallery: TG12/TG30, GG01/GG70
    re.compile(r"\b((?:TG|GG)\d{1,3})\s*/\s*(?:TG|GG)?\d{1,3}\b", re.I),
    # Standard: 223/197, 016/091
    re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b"),
    # Promos: SWSH147, SVP123, XY42
    re.compile(r"\b((?:SWSH|SVP|SV|XY|SM|BW)\s?\d{1,3})\b", re.I),
]

GRADE_PATTERN = re.compile(
    r"\b(PSA|CGC|BGS|SGC|ACE)\s*[-:]?\s*(10|9\.5|9|8\.5|8|7|6|5|4|3|2|1)\b", re.I
)

# Condition abbreviations and their spelled-out forms.
CONDITION_PATTERNS = [
    # The trailing "/M" is optional: bare "NM" is by far the commonest form.
    ("NM", re.compile(r"\b(NM(?:[\s/\-]?MT?)?|NEAR\s*MINT|MINT)\b", re.I)),
    ("LP", re.compile(r"\b(LP|LIGHTLY\s*PLAYED|EXCELLENT)\b", re.I)),
    ("MP", re.compile(r"\b(MP|MODERATELY\s*PLAYED|GOOD)\b", re.I)),
    ("HP", re.compile(r"\b(HP|HEAVILY\s*PLAYED|POOR)\b", re.I)),
    ("DMG", re.compile(r"\b(DMG|DAMAGED)\b", re.I)),
]

PRINTING_PATTERNS = [
    ("Reverse Holofoil", re.compile(r"\b(REVERSE\s*HOLO(?:FOIL)?|REV\.?\s*HOLO)\b", re.I)),
    ("Holofoil", re.compile(r"\b(HOLO(?:FOIL)?|FOIL)\b", re.I)),
]

# Any hit here disqualifies the listing. Each is a way to lose money that
# looks like a bargain.
REJECT_PATTERNS = [
    # Multi-card listings: the price is for the group, not the card we priced.
    ("lot", re.compile(
        r"\b(LOT|BUNDLE|BULK|COLLECTION|SET\s+OF|\d+\s*(?:X|PCS|CARDS)\b|"
        r"\bX\s*\d{2,}|JOB\s*LOT|MYSTERY|RANDOM|REPACK)\b", re.I)),
    # Not real cards.
    ("proxy", re.compile(
        r"\b(PROXY|CUSTOM|ORICA|FAN\s*ART|REPLICA|proxy|proxies|"
        r"NOT\s*REAL|proxy\s*card|METAL\s*CARD|GOLD\s*(?:PLATED|METAL))\b", re.I)),
    # Separate market with separate prices; our catalog is English.
    ("japanese", re.compile(r"\b(JAPANESE|JAPAN|JPN|JP\s*VER|KOREAN|CHINESE)\b", re.I)),
    # Sealed product, not a single.
    ("sealed", re.compile(
        r"\b(BOOSTER\s*(?:BOX|PACK|BUNDLE)|ETB|ELITE\s*TRAINER|SEALED|"
        r"TIN|BLISTER|COLLECTION\s*BOX|PREMIUM\s*COLLECTION)\b", re.I)),
    # A listing for a card that will exist later, or a stand-in image.
    ("presale", re.compile(r"\b(PRE[\s\-]?(?:SALE|ORDER)|PROXY\s*IMAGE|STOCK\s*PHOTO)\b", re.I)),
]

# Stripped before name extraction — noise that appears in nearly every title.
NOISE = re.compile(
    r"\b(POKEMON|POKÉMON|TCG|CARD|CARDS|ENGLISH|ENG|NEW|RARE|ULTRA|SECRET|"
    r"FULL\s*ART|ALT(?:ERNATE)?\s*ART|SIR|IR|SAR|AR|VSTAR|MINT|GEM|FAST|"
    r"SHIP(?:PING|S)?|FREE|NIB|WOTC|VINTAGE|GRADED|SLAB|PACK\s*FRESH)\b",
    re.I,
)


@dataclass
class ParsedTitle:
    """Structured extraction from one listing title."""

    raw: str
    name_tokens: list[str] = field(default_factory=list)
    number: str | None = None
    set_total: str | None = None
    grader: str | None = None
    grade: float | None = None
    condition: str | None = None
    printing: str | None = None
    reject_reason: str | None = None

    @property
    def is_usable(self) -> bool:
        return self.reject_reason is None

    @property
    def is_graded(self) -> bool:
        return self.grader is not None

    @property
    def name_guess(self) -> str:
        return " ".join(self.name_tokens)

    def confidence(self) -> float:
        """How much to trust a match built from this parse, in [0, 1].

        A collector number is worth far more than a name, because names are
        ambiguous across sets and reprints while numbers are nearly unique
        within one. Nothing here reaches 1.0 — eBay titles never justify
        certainty.
        """
        if not self.is_usable:
            return 0.0
        score = 0.0
        if self.number:
            score += 0.55
        if self.set_total:
            score += 0.15
        if self.name_tokens:
            score += min(0.20, 0.07 * len(self.name_tokens))
        if self.condition or self.grader:
            score += 0.10
        return round(min(score, 0.95), 2)


def parse_title(title: str) -> ParsedTitle:
    """Extract card identity from a listing title.

    Rejection is checked first and short-circuits: there is no point parsing
    a name out of a bundle of 50 cards.
    """
    out = ParsedTitle(raw=title)

    for reason, pattern in REJECT_PATTERNS:
        if pattern.search(title):
            out.reject_reason = reason
            return out

    working = title

    m = GRADE_PATTERN.search(working)
    if m:
        out.grader = m.group(1).upper()
        out.grade = float(m.group(2))
        working = working[: m.start()] + " " + working[m.end():]

    for pattern in NUMBER_PATTERNS:
        m = pattern.search(working)
        if m:
            out.number = m.group(1).upper().replace(" ", "")
            if m.lastindex and m.lastindex >= 2:
                out.set_total = m.group(2)
            working = working[: m.start()] + " " + working[m.end():]
            break

    # Graded slabs carry a numeric grade instead of a condition abbreviation;
    # reading "MINT" off "GEM MINT 10" as a raw condition would be wrong.
    if not out.is_graded:
        for label, pattern in CONDITION_PATTERNS:
            m = pattern.search(working)
            if m:
                out.condition = label
                working = working[: m.start()] + " " + working[m.end():]
                break

    for label, pattern in PRINTING_PATTERNS:
        m = pattern.search(working)
        if m:
            out.printing = label
            working = working[: m.start()] + " " + working[m.end():]
            break

    working = NOISE.sub(" ", working)
    # Keep alphanumerics and the hyphens/apostrophes real card names use.
    working = re.sub(r"[^\w\s'\-]", " ", working)
    out.name_tokens = [
        t for t in working.split()
        if len(t) > 1 and not t.isdigit() and t.lower() not in {"the", "and", "for", "with"}
    ][:6]

    return out


# Catalog names carry qualifiers the seller rarely repeats:
#   "Charizard ex - 223/197"
#   "Umbreon VMAX (Alternate Art Secret)"
#   "Rillaboom - SWSH006 (Prerelease) [Staff]"
# The card's actual name is what precedes all of that.
# Applied in order: qualifiers first, because the number suffix is only at
# end-of-string once "(Prerelease) [Staff]" and friends are gone.
CATALOG_QUALIFIER = re.compile(r"\([^)]*\)|\[[^\]]*\]")
CATALOG_NUMBER_SUFFIX = re.compile(r"\s*[-–]\s*[\w/]+\s*$")


def core_name_tokens(catalog_name: str) -> set[str]:
    """The card's name proper, stripped of number and qualifier suffixes."""
    core = CATALOG_QUALIFIER.sub(" ", catalog_name)
    core = CATALOG_NUMBER_SUFFIX.sub(" ", core.strip())
    tokens = {
        t.lower() for t in re.findall(r"\w+", core)
        if len(t) > 1 and not t.isdigit()
    }
    # Fall back to the full name if stripping removed everything.
    return tokens or {
        t.lower() for t in re.findall(r"\w+", catalog_name)
        if len(t) > 1 and not t.isdigit()
    }


def number_variants(number: str, set_total: str | None) -> list[str]:
    """Candidate catalog spellings of a collector number.

    The catalog stores full numbers with zero padding — "223/197", "001/131" —
    while sellers type "223/197" or "1/131" interchangeably. Promo sets are the
    exception and store bare identifiers like "SWSH147".

    Matching on the numerator alone is what made an early version of this
    match "Charizard ex 223/197" to a Professor's Research promo numbered 223.
    The denominator is most of the signal: it identifies the set size, which
    narrows the catalog enormously.
    """
    if set_total is None:
        return [number.upper()]

    try:
        n, t = int(number), int(set_total)
    except ValueError:
        return [f"{number}/{set_total}".upper()]

    return [f"{n:0{wn}d}/{t:0{wt}d}" for wn in (1, 2, 3) for wt in (1, 2, 3)]


def match_to_catalog(
    conn, parsed: ParsedTitle, min_overlap: float = 0.34
) -> tuple[int | None, float]:
    """Resolve a parsed title to a product_id.

    Returns (product_id, confidence), or (None, 0.0) when no match is safe.

    Two rules keep this honest:

    1. **A collector number alone is never enough.** The name must corroborate
       it, even when only one catalog row carries that number. Numbers repeat
       across sets and promos, and an unverified single hit is exactly how you
       end up pricing a Charizard off a Professor's Research promo.
    2. **Name-only matching is not attempted.** "Pikachu" matches hundreds of
       products; a confident wrong answer is worse than no answer.
    """
    if not parsed.is_usable or not parsed.number:
        return None, 0.0

    tokens = {t.lower() for t in parsed.name_tokens}
    if not tokens:
        return None, 0.0

    variants = number_variants(parsed.number, parsed.set_total)
    placeholders = ",".join("?" * len(variants))
    rows = conn.execute(
        f"""
        SELECT product_id, name, number
        FROM products
        WHERE is_single = 1
          AND UPPER(REPLACE(number, ' ', '')) IN ({placeholders})
        """,
        variants,
    ).fetchall()

    if not rows:
        return None, 0.0

    scored = []
    for r in rows:
        core = core_name_tokens(r["name"] or "")
        if not core:
            continue
        # Coverage of the *card's* name by the title, not the reverse. Titles
        # carry set names, hype words and seller filler that no catalog name
        # contains; scoring against them punishes correct matches.
        overlap = len(tokens & core) / len(core)
        scored.append((overlap, r["product_id"]))

    if not scored:
        return None, 0.0
    scored.sort(key=lambda x: (-x[0], x[1]))

    best_overlap, best_id = scored[0]
    if best_overlap < min_overlap:
        return None, 0.0

    # An ambiguous winner is penalised: if the runner-up scored nearly as
    # well, we are guessing between reprints of the same card.
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    margin = best_overlap - runner_up
    penalty = 1.0 if margin > 0.3 else 0.75 if margin > 0.1 else 0.5

    return best_id, round(parsed.confidence() * best_overlap * penalty, 2)
