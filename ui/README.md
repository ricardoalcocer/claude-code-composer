# composer-ui — an audition layer

An experiment. A local React/Vite app that lets you **hear and browse** what
`composer.py` wrote, without opening a DAW.

```bash
python3 ui/server.py          # terminal 1 — bridge + API on :8722
cd ui && npm install && npm run dev   # terminal 2 — open http://localhost:5173
```

Or build it once and run a single process:

```bash
cd ui && npm install && npm run build
python3 ui/server.py          # now serves the built app on :8722
```

---

## What it is not

**It is not a spec builder, and shouldn't become one.**

Every musical decision in this project — key, form, arrangement archetype,
voicings, which of the 127 mood progressions to reach for — happens inside
Claude, guided by the 150KB of catalogs in [`SKILL.md`](../SKILL.md). A form
with a "feel" dropdown and a chord-picker would be a strictly worse interface
for those decisions than a sentence like *"modal-cinematic Zimmer build in C
minor, no V chord, glacial harmonic rhythm."* Building one would quietly
relocate the taste from the catalogs into a widget, and land you back at
`I-V-vi-IV` — the thing SKILL.md spends a section warning against.

So the UI deliberately does none of that. **Claude still writes the spec.**

## What it is

The loop today is: brief → Claude writes `spec.json` → `composer.py` writes MIDI
→ *open a DAW to find out whether it was any good*. That last step is the
expensive one, and it's the one worth removing.

- **Archive browser** — every folder under `output_root` with a `spec.json`,
  newest first, filterable by key/BPM/name. The archive is already well
  organised on disk; it just has no window.
- **Form at a glance** — the timeline draws each form position at its true
  width, one colour per section, so a 48-bar through-composed piece is a shape
  you can read instead of a folder listing.
- **Playback in the browser** — a small Web Audio synth plays the actual
  `full.mid`, one timbre per role. It is not meant to sound good. It's meant to
  answer "is this worth opening in REAPER" in two seconds.
- **Mute / solo per layer** — the point of the whole thing. Mute the lead, hit
  loop on the chorus, pick up the guitar. The `improv:` scale line sits right
  under the chord grid where you can read it while playing.
- **Loop a section** — select a block, hit ⟳.
- **Small edits, then hear them** — the raw `spec.json` is editable and
  `Regenerate` shells out to `composer.py`. For nudging a tempo or swapping one
  chord. Anything bigger is a sentence to Claude, not a form.
- **Vocabulary panel** — a read-only index of the style packs, forms,
  archetypes and moves parsed out of `SKILL.md`, so the names are in front of
  you while you listen. You can't pick from it; you name it in your next brief.

## How it fits together

```
ui/server.py          stdlib-only bridge. Walks output_root, serves spec.json
                      and .mid to the browser, shells out to composer.py for
                      regenerate. Localhost only; every browser-supplied path
                      is resolved and checked against output_root.

src/midi/parseSmf.ts  reads the real full.mid rather than re-synthesising the
                      spec in TypeScript — re-implementing voice_bass and the
                      drum patterns here would drift from composer.py, and then
                      the UI would be lying about what's on disk.

src/audio/engine.ts   lookahead scheduler over Web Audio (setInterval decides
                      when to think, AudioContext.currentTime decides when
                      things sound). Per-role voices, mute/solo, section loop.
```

No new Python dependencies — `server.py` is stdlib, same as `composer.py`.
Node is only needed to build the front end.

### Config

`server.py` reads `output_root` from the repo's `config.json`, same as
`composer.py`. Override with `--root`, and the port with `--port`.

## Status

Exploration on a branch. Playback is a toy synth, not a mixdown. Fill mode
(REAPER-only) isn't represented. `melody` lines are played but not drawn.
