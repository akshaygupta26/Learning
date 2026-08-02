#!/usr/bin/env python3
"""Scaffold a new session log.

    python3 scripts/new_session.py "trend-analysis"

Creates sessions/YYYY-MM-DD-NN-slug.md with the next sequence number, from a
template. Refuses to overwrite: session logs are append-only by design.

After filling it in, update sessions/STATE.md — the log records what happened,
STATE.md records what is now true. Only the second one gets read every session.
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"

TEMPLATE = """# Session {number:02d} — {title}

**Date:** {date}

## Goal

<!-- What this session set out to do, in a sentence or two. -->

## What happened

<!-- Narrative. What was attempted, what the data said, what broke. -->

## Decisions

<!-- Each with its basis. These get promoted into STATE.md § Settled decisions. -->

## Measurements

<!-- Numbers, with sample sizes. These get promoted into STATE.md § Findings.
     Record the number even when it is discouraging — especially then. -->

## Gotchas

<!-- Anything that cost time or would cost money to re-learn.
     Promote into STATE.md § Gotchas. -->

## Open at end of session

<!-- What is blocked, on whom, and by when. -->
"""


def next_number() -> int:
    existing = [
        int(m.group(1))
        for p in SESSIONS_DIR.glob("*.md")
        if (m := re.match(r"\d{4}-\d{2}-\d{2}-(\d+)-", p.name))
    ]
    return max(existing, default=0) + 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", help="short kebab-case topic, e.g. trend-analysis")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today, UTC)")
    args = ap.parse_args()

    slug = re.sub(r"[^a-z0-9-]+", "-", args.slug.lower()).strip("-")
    if not slug:
        print("slug must contain letters or digits")
        return 1

    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    number = next_number()
    path = SESSIONS_DIR / f"{date}-{number:02d}-{slug}.md"

    if path.exists():
        print(f"{path} already exists — session logs are append-only")
        return 1

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        TEMPLATE.format(
            number=number, title=slug.replace("-", " "), date=date
        )
    )

    print(f"created {path.relative_to(SESSIONS_DIR.parent)}")
    print("\nWhen done, update sessions/STATE.md and add a row to its index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
