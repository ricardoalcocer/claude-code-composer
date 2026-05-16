# Contributing

Thanks for considering a contribution. This skill is meant as a **bandmate** — an idea incubator that hands you sketches you can play over — so changes that widen the musical vocabulary (more idioms, more moves, more chord types, more transition recipes) are especially welcome.

## Local setup

```bash
git clone https://github.com/ricardoalcocer/claude-code-composer.git
cd claude-code-composer

# Local config (gitignored)
cp config.example.json config.json
cp style.example.md style.md
$EDITOR config.json   # point template_path at your Reaper template
```

You'll need a Reaper project template with the track names listed in [the README's Template setup section](README.md#template-setup), or you can edit `TRACK_TARGETS` near the top of `composer.py` to match whatever names you've already got.

## Testing a change

There's no automated test suite for the musical output — by design, the script's job is mechanical (JSON spec → MIDI + `.RPP`), so verification is "did the right notes land on the right tracks at the right times" which is best done by ear in Reaper.

Quick round-trip to sanity-check a change:

```bash
# Compose a tiny test song
cat > /tmp/test_spec.json <<'JSON'
{
  "song_name": "test", "key": "Em", "tempo": 120, "time_sig": [4, 4],
  "sections": [{
    "name": "verse", "feel": "halftime",
    "chords": [
      {"name": "Em9", "beats": 4}, {"name": "D", "beats": 4},
      {"name": "Cmaj7", "beats": 4}, {"name": "B7", "beats": 4}
    ]
  }],
  "form": ["verse"]
}
JSON
python3 composer.py compose /tmp/test_spec.json /tmp/test_out

# Open /tmp/test_out/test.RPP in Reaper, listen
```

For fill-mode changes: add a `COMPOSER` region to a composed `.RPP`, then `python3 composer.py analyze` it (verify the JSON output) and `fill` it with a hand-written spec.

## Kinds of contributions welcome

| Type | Notes |
|---|---|
| **Bug fixes in `composer.py`** | The Python is mechanical — bugs usually show as wrong MIDI, wrong .RPP structure, or parse errors. Most welcome. |
| **New chord qualities** | Add to `CHORD_QUALITIES` near the top of `composer.py`. Common requests: `7sus4`, `add11`, `maj7#11`, `13`. Just need a name and an interval list. |
| **New `feel` patterns** | Add to `FEEL_BAR_PATTERNS`. Each pattern is a list of `(offset_beats, duration_beats, velocity_delta)` tuples. |
| **New `chugg` patterns** | Add to `CHUGG_PATTERNS` (same shape as feel patterns). |
| **New drum patterns** | Add to `DRUM_BAR_PATTERNS`. Tuples of `(offset_beats, drum_name, velocity)` where `drum_name` is a key in `GM_DRUMS`. |
| **New style packs** | Edit `SKILL.md`. Add a new pack under "Style packs" with tempo range, key defaults, role recommendations, moves to reach for, voicings, what to avoid, and touchstone artists. Also add it to the decision-tree list. |
| **New transition idioms** | Edit `SKILL.md` under "Fill mode" → "Transition idioms catalog". |
| **README polish, examples, typos** | Always welcome. |

## Things to be careful with

1. **`SKILL.md` is the prompt Claude reads.** Edits there change *how the AI thinks*, not just how the code runs. A change like "remove the variety-rotation requirement" or "default to Em" can cascade across every future composition. Treat SKILL.md edits more like API changes than code refactors — explain the *why* in the PR description, ideally with a before/after example of what the skill would produce.

2. **The breadcrumb format is a contract.** Once a `.RPP` is composed, its EXTSTATE block and NOTES structure are the source of truth for future `analyze`/`fill` operations. Changes to the breadcrumb format need backward compatibility (the reader should accept the old format) or a clearly-documented migration. The 4-tier resolution chain (EXTSTATE → sidecar → notes_block → midi_parse) exists specifically so old projects keep working.

3. **No new dependencies in `composer.py`.** Pure stdlib is a feature — drop-in install, no `pip install`, no venv. If you need something exotic, build it inline.

4. **Don't commit `config.json` or `style.md`.** Both are gitignored; verify with `git status` before pushing.

## PR description

Use the template that pops up when you open a PR. Three things really help review:

- A short before/after — what the skill produced before your change, what it produces after, ideally with a one-line example.
- For musical changes: a sentence about *why this sounds right* (the touchstone artist or idiom you're matching).
- For breadcrumb / spec format changes: which tier(s) you touched and how older projects still work.

## License

By contributing, you agree your contribution is licensed under [MIT](https://alco.mit-license.org).
