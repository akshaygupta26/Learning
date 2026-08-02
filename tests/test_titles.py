"""Tests for eBay title parsing.

Run with: python3 -m pytest tests/ -q     (or: python3 tests/test_titles.py)

The fixtures are written to look like real eBay titles, including the noise,
inconsistent casing, emoji, and seller filler that make this hard. Precision
matters more than recall here: a false match prices one card off another
card's comp, which loses money silently.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pokedb.titles import (  # noqa: E402
    core_name_tokens,
    number_variants,
    parse_title,
)


def test_extracts_number_and_grade():
    p = parse_title("Charizard ex 223/197 SV Obsidian Flames SIR PSA 10 GEM MINT")
    assert p.is_usable
    assert p.number == "223"
    assert p.set_total == "197"
    assert p.grader == "PSA"
    assert p.grade == 10.0
    assert p.is_graded
    assert "Charizard" in p.name_guess


def test_raw_condition_parsed():
    p = parse_title("Pokemon Umbreon VMAX Alt Art 215/203 Evolving Skies NM")
    assert p.is_usable
    assert p.number == "215"
    assert p.condition == "NM"
    assert not p.is_graded


def test_graded_slab_does_not_get_a_raw_condition():
    # "GEM MINT" must not be read as a raw NM condition on a graded slab.
    p = parse_title("Mew ex 216/091 Paldean Fates CGC 9.5 GEM MINT")
    assert p.grader == "CGC"
    assert p.grade == 9.5
    assert p.condition is None


def test_promo_number_format():
    p = parse_title("Pokemon Rayquaza V SWSH147 Promo Holo NM")
    assert p.is_usable
    assert p.number == "SWSH147"


def test_trainer_gallery_number_format():
    p = parse_title("Pikachu VMAX TG17/TG30 Silver Tempest Trainer Gallery")
    assert p.is_usable
    assert p.number == "TG17"


def test_reverse_holo_detected_before_holo():
    p = parse_title("Magikarp 129/185 Vivid Voltage Reverse Holo NM")
    assert p.printing == "Reverse Holofoil"


def test_plain_holo_detected():
    assert parse_title("Snorlax 141/198 Holofoil NM").printing == "Holofoil"


# --- rejections: each of these is a distinct way to lose money -------------

def test_rejects_lots():
    for title in [
        "pokemon card rare holo lot of 5 charizard",
        "Pokemon Bundle 50 Cards Vintage Rare",
        "Charizard 4/102 x10 cards",
        "Mystery repack pokemon slab hit",
    ]:
        assert parse_title(title).reject_reason == "lot", title


def test_rejects_proxies():
    for title in [
        "Charizard 4/102 Base Set PROXY Card Custom",
        "Umbreon VMAX Alt Art ORICA Custom Art",
        "Pikachu Gold Metal Card Collectible",
    ]:
        assert parse_title(title).reject_reason == "proxy", title


def test_rejects_japanese():
    p = parse_title("Pokemon Japanese Charizard ex 223/197 Obsidian Flames NM")
    assert p.reject_reason == "japanese"


def test_rejects_sealed():
    for title in [
        "Pokemon Obsidian Flames Booster Box 36 Packs Sealed",
        "Scarlet Violet 151 Elite Trainer Box ETB",
    ]:
        assert parse_title(title).reject_reason == "sealed", title


def test_rejects_presale():
    assert parse_title("Mega Evolution 30th Celebration Pre-Order").reject_reason in (
        "presale", "sealed",
    )


# --- confidence ------------------------------------------------------------

def test_confidence_rewards_a_number():
    with_num = parse_title("Charizard ex 223/197 Obsidian Flames NM")
    without = parse_title("Charizard ex Obsidian Flames NM")
    assert with_num.confidence() > without.confidence()


def test_rejected_titles_have_zero_confidence():
    assert parse_title("pokemon lot of 100 cards").confidence() == 0.0


def test_confidence_never_certain():
    # eBay titles never justify certainty.
    p = parse_title("Charizard ex 223/197 Obsidian Flames PSA 10 Holo")
    assert p.confidence() <= 0.95


def test_junk_title_yields_nothing_usable():
    p = parse_title("pokemon card rare holo good condition")
    assert p.number is None
    assert p.confidence() < 0.5


# --- regression: matching on the numerator alone -------------------------
# An early version matched "Charizard ex 223/197" to a Professor's Research
# promo numbered 223, at 0.95 confidence, because it queried the catalog on
# the numerator only and skipped name verification when exactly one row came
# back. The denominator identifies the set and is most of the signal.

def test_number_variants_uses_the_full_number():
    v = number_variants("223", "197")
    assert "223/197" in v
    assert "223" not in v


def test_number_variants_covers_zero_padding():
    # Catalog stores "001/131"; sellers type "1/131".
    v = number_variants("1", "131")
    assert "1/131" in v
    assert "001/131" in v


def test_number_variants_passes_promos_through():
    assert number_variants("SWSH147", None) == ["SWSH147"]


def test_core_name_tokens_strips_number_suffix():
    assert core_name_tokens("Charizard ex - 223/197") == {"charizard", "ex"}


def test_core_name_tokens_strips_qualifiers():
    assert core_name_tokens("Umbreon VMAX (Alternate Art Secret)") == {
        "umbreon", "vmax",
    }
    assert core_name_tokens("Rillaboom - SWSH006 (Prerelease) [Staff]") == {
        "rillaboom",
    }


def test_core_name_tokens_never_empty():
    # Stripping must not erase a name made entirely of qualifiers.
    assert core_name_tokens("(Prerelease)")


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
