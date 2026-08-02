# Sessions

Persistent memory for this project, so a new chat starts informed instead of
re-deriving everything. Follows the LLM-wiki pattern: **durable synthesis over
immutable sources**, rather than re-reading raw transcripts each time.

## Two layers

| File | Mutable? | Purpose | Read when |
| --- | --- | --- | --- |
| `STATE.md` | **Yes** — edited every session | Distilled current state: settled decisions, measured findings, gotchas, blockers | **Always, first** |
| `YYYY-MM-DD-NN-slug.md` | **No** — append-only | What happened in one session, and why | Only when you need the reasoning behind a conclusion |

The split is the whole design. Logs are cheap to write and never revisited
wholesale. `STATE.md` is expensive to maintain and cheap to read — which is
the right trade, because it is read every single session and written rarely.

If `STATE.md` and a session log disagree, **`STATE.md` wins.** Logs record what
was believed at the time; several beliefs in them have since been measured and
found wrong. That is intentional and worth preserving — a superseded belief
with its reasoning intact is more useful than a silently corrected one.

## Writing a session log

```bash
python3 scripts/new_session.py "trend-analysis"
```

Creates the next-numbered file from a template. Fill in what happened, what
was decided, what was measured, what broke.

Then **update `STATE.md`**: move new decisions into Decisions, new numbers into
Findings, resolved blockers out of Open Items, and delete anything no longer
true. Add a row to the session index at the bottom.

## What belongs where

**Session log** — the narrative. What was attempted, what the data said, what
broke and why, what was decided and on what basis. Long is fine.

**STATE.md** — only what a future session needs to act correctly. A measured
number, a settled decision, a trap that costs money. Not the journey.

Keep `STATE.md` under ~200 lines. Past that, compress it — do not let it
sprawl, or it stops being read, and an unread state file is worse than none.

## What counts as a gotcha

Anything that cost real time or would cost money to re-learn. Two schema
designs in this project were built against imagined API shapes and had to be
rewritten after hitting the real endpoint. Both are recorded in `STATE.md`
under Gotchas, and both should have been avoided by checking first.
