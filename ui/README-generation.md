# The generation loop

The audition layer (see [README.md](README.md)) answers *"is this sketch worth
opening in REAPER?"*. This layer makes new sketches cheap enough that the
question gets asked constantly. Everything below is measured, not estimated —
the numbers were taken on this repo with `claude -p` headless.

## The cost model

Four timed generation turns, warm session, SKILL.md cached:

| ask | output tokens | measured |
|---|---:|---:|
| one chord progression | 924 | 13.0s |
| one section, scoped | 2,039 | 25.3s |
| one section, full spec rewrite | 5,356 | 55.8s |
| transpose, full spec rewrite | 17,110 | 171.6s |

Fit: **latency ≈ 4.3s + output_tokens / 102** (R² = 0.9999). Latency is
*emission*, not thinking — context reads were 200–370k tokens and free.
So the architecture makes the model emit as little as possible, and for a
large class of edits, not run at all.

## The three tiers

**Tier 0 — `transforms.py` (~0.3ms, no model).** Deterministic spec math:
transpose, tempo, re-bar (4/4↔7/8 preserving bar counts), form surgery
(repeat/remove entries), role changes, feel swaps, `thin` (bass + one harmony
layer + drums — the "does the writing survive stripped down?" audition).
Every output re-parses through composer.py's own chord/pitch parsers before
it's returned; a transform that would break `composer.py` refuses instead.
The measured comparison: transposing a 7-section spec deterministically takes
0.27ms; asking the model took 171.6s for the same result.

`transpose` intentionally drops `scales` text — it's prose about the old key,
and stale improv guidance is worse than none. A Tier 1 patch restores it.

**Tier 1 — scoped patches (~15–30s + one ~30s prime).** A persistent
`claude -p --input-format stream-json` session per song, primed once on
SKILL.md + the current spec. Asks return *only the changed object* (one
section, or one chords array); `agent._splice()` merges it and the validation
gate runs before rendering. Results render as a **sibling** folder
(`…-p2`), never overwriting — a patch is a variant to audition next to the
original.

**Tier 2 — cold briefs (~2–3min each).** A fresh `claude` process per brief;
emission dominates, so warmth buys nothing here and fresh processes fan out
trivially. `POST /api/generate {brief, count}` launches N takes in parallel,
each nudged to differ in form/archetype/harmony. Jobs land in the archive as
they finish; the UI keeps auditioning meanwhile.

## The loop

```
brief ──▶ Tier 2 (N takes, async, --midi-only 54ms renders)
                       │  SSE
                       ▼
            audition in the browser
             │ instant buttons (Tier 0 siblings)
             │ "darker bridge" box (Tier 1 sibling)
             ▼
        keep? ──no──▶ bin (cost: nothing — no .RPP was ever rendered)
             │yes
             ▼
        promote → REAPER (renders .RPP + template + NOTES, 67ms)
```

Generation is `--midi-only` on purpose: sketches are disposable, and the
`.RPP` render is the *promotion* act, done once for the keeper.

## Live updates

`GET /api/events` (SSE) pushes a version bump whenever the archive or the job
registry changes. Server-side writes bump instantly; a 2s filesystem watcher
catches songs written by **Claude in a terminal** — so you can keep briefing
conversationally in Claude Code and sketches appear in the UI as they land,
with no browser-driven generation required at all.

## Endpoints

| endpoint | tier | what |
|---|---|---|
| `POST /api/transform {rel, op, arg}` | 0 | render sibling variant, ~60ms end-to-end |
| `POST /api/patch {rel, ask}` | 1 | scoped patch through the warm session |
| `POST /api/generate {brief, count}` | 2 | fan out N cold briefs |
| `POST /api/promote {rel}` | — | render the .RPP for a keeper |
| `GET /api/jobs` | — | job registry snapshot |
| `GET /api/events` | — | SSE: library + jobs change stream |

`transforms.py` is also a CLI: `python3 ui/transforms.py transpose+7 tempo=96 thin spec.json`.

## Trust boundary

The model never touches the archive directly. It writes to a staging file;
the spec is parsed, run through `transforms.validate()` (composer.py's own
parsers), and only then rendered by `composer.py` into the archive. Rendered
output is the only thing the UI trusts. If `claude` isn't on PATH the
generation surface disables itself and audition keeps working.
