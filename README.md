<p align="center">
  <img src="assets/logo.png" alt="claude-composer — AI · CODE · MUSIC" width="480">
</p>

<p align="center">
  <em>requires</em><br>
  <a href="https://www.reaper.fm/"><img src="assets/reaper-logo.jpg" alt="REAPER — Digital Audio Workstation" height="90"></a><br>
  <sub><a href="https://www.reaper.fm/">REAPER</a> — the script writes <code>.RPP</code> project files you open directly in REAPER</sub>
</p>

<p align="center"><em>A bandmate that hands you sketches.</em></p>

<p align="center">
  Tell Claude what you want to play over — a style, a mood, a chord change — and get back a Reaper project with bass, drums, guitars, pad, and MIDI laid out across sections, regions, and tracks. Open it. Improvise over it. Mine it for ideas. Throw it away. Ask for another.
</p>

---

## What it feels like

You're in Claude Code. You type:

> *Give me a Plini-style instrumental in Bm — through-composed, no lead, leave room for me to play over it.*

A few seconds later you have `~/Documents/MIDI-SONGS/_2026/.../blue-meridian.RPP` on disk — 48 bars across six unique sections, drums entering at the halftime setup, full band at the climb, a sparse bridge break in the middle, and a NOTES pane in Reaper that documents every chord and the scale to solo over it.

Then you decide the bridge needs more. In Reaper you drag a region named `COMPOSER` over 16 empty bars and ask:

> *Fill the COMPOSER region with a cinematic key mod.*

Claude reads what comes before and after the gap, picks a chromatic-mediant lift to D major then drops to Bb-major territory before walking back through B Aeolian, and writes the MIDI items into your project on bass, pad, clean, and synth pad — no drums, no rhythm guitars, because the brief said *cinematic*. The fill lands cleanly into the next chord on the other side.

That's the whole skill: a bandmate that hands you sketches.

## Two modes

| Mode | When | What you say | What you get |
|---|---|---|---|
| **Compose** | Starting fresh | *"a sad piano piece in 6/8"* · *"Polyphia-style loop"* · *"synthwave in Am"* | A fresh `.RPP` + per-section `.mid` files + `full.mid` + `spec.json`, in a dated output folder |
| **Fill** | Filling a gap in an existing project | *"fill the COMPOSER region"* · *"do a key mod here"* · *"arpeggiated guitars, 65bpm feel"* | MIDI items injected into the existing `.RPP` in place — only the tracks the fill needs, none of the others touched |

Both modes share the same musical vocabulary (style packs, song forms, arrangement archetypes, transition idioms — all documented in [`SKILL.md`](SKILL.md)). The Python script does the mechanical RPP/MIDI work; the musical decisions happen inside Claude.

## Requirements

- **Reaper** (any recent version). The script writes a Reaper project file directly.
- **Python 3.8+** — stdlib only, zero external dependencies.
- **A Reaper project template** with specific track names (see [Template setup](#template-setup)).
- **Claude Code** as the driver. The Python script can also be run standalone with a hand-written JSON spec — see [Standalone usage](#standalone-usage).

## Install

```bash
# 1. Clone into your Claude Code skills directory.
git clone https://github.com/<you>/claude-composer.git ~/.claude/skills/composer

# 2. Set up your local config + personal-notes scratchpad (both gitignored).
cd ~/.claude/skills/composer
cp config.example.json config.json
cp style.example.md style.md
$EDITOR config.json   # edit template_path and output_root
```

Restart Claude Code and the `composer` skill is discoverable. Try:

> *Compose a melodic instrumental rock piece in Bm — make the bridge a halftime breakdown.*

## Template setup

The script doesn't create instrument tracks — it inserts MIDI items into tracks **you have already set up** in a Reaper project template. That way your synths, FX chains, sends, and mixer balance are exactly the way you like them; the skill just supplies the notes.

In Reaper, create the tracks below with these **exact names**, save as a project template (`File → Project templates → Save project as template…`), and point `template_path` in `config.json` at the resulting `.RPP`.

| Track name | Role | What gets written |
|---|---|---|
| `BASS` | bass | Root-note bassline. Splits long chords in two for movement. |
| `DRUMS` | drums | GM kit (kick 36, snare 38, hat 42), crash at section starts. |
| `PIANO` | pad | Open chord voicings, sustained for the full chord duration. |
| `MIDI-RHY-GTR-L` | rhy_l | Root+5th power chords (or full voicings for jazz). Pattern from `feel`. |
| `MIDI-RHY-GTR-R` | rhy_r | Same as L, offset 1/8 beat for stereo width. |
| `MIDI-CLEAN` | clean | 8th-note fingerpicked arpeggios cycling chord tones. |
| `MIDI-STRUM` | strum | Staggered strum — chord tones offset ~40ms (pick rake). |
| `MIDI-LEAD` | lead | Composed melodic line per section (`melody` field). |
| `MIDI-CHUGG` | chugg | Palm-muted low-octave rhythm. Patterns: `gallop`, `straight-16ths`, `polyrhythm-3`, `syncopated`, `halftime`, `single-hit`, `open-8ths`. Drop a ReaPitch on this track to drop-tune. |
| `SURGE XT` | synth_pad | Soft sustained chord-tone bed. Long sustain blurs into next chord. |

Track names are matched exactly. **You don't need every track** — if your template has only `BASS`, `DRUMS`, and `PIANO`, the script writes those three and skips everything else. (The `.mid` files still contain every role as separate tracks, so you can drag-and-drop into any DAW.)

To use different track names, edit `TRACK_TARGETS` near the top of `composer.py`.

## Fill mode

You're working in a song. There's a gap — a section that needs something. Or maybe the bridge you wrote isn't landing and you want a second opinion. Fill mode is for that moment.

### Setup in Reaper

1. Find the empty bars. (Or clear existing MIDI items from a range.)
2. Press **R** to drop a region over those bars. Rename it `COMPOSER` (literal, all caps).
3. **Save and close the project.** The script rewrites the `.RPP` in place; Reaper would silently clobber the edits on its next auto-save if left open.

### Ask Claude

Three flavors of brief, all valid:

| Brief style | Example | What Claude does |
|---|---|---|
| **None** (Mode A) | *"fill the COMPOSER region"* | Reads prev/next 4 bars, picks a transition that fits — pre-chorus build, halftime breather, parallel-minor bridge, etc. |
| **Vibe-textural** | *"arpeggiated guitars, 65bpm feel"* · *"atmospheric"* · *"drop to silence"* | Keeps the surrounding harmonic frame; picks `feel` + `roles` to match the texture words. |
| **Harmonic** | *"do a key mod to F#m"* · *"Andalusian cadence"* · *"bVI-bVII-i lift"* · *"halftime breakdown"* | Composes the dictated progression; if a key changes, ends with a chord that lands cleanly into the next section. |

Reopen the `.RPP` in Reaper when it's done. The fill appears as items named `composer-fill-<role>` on the right tracks.

### Re-running for variations

If you don't love the result:

1. In Reaper, select the `composer-fill-*` items and delete them.
2. Save, close.
3. Ask again with a refined brief.

Each run replaces the `COMPOSER-FILL` entry in the project notes (so the description stays accurate). The MIDI items don't auto-replace though — that's the manual step.

### How it knows what's around the gap

When you run `analyze` on a project, the script tries four sources in priority order:

1. **EXTSTATE breadcrumb** inside the `.RPP` — embedded by `compose` (and updated by every `fill`). Invisible to you in Reaper's UI, perfect-fidelity record of the spec.
2. **Sidecar `spec.json`** in the project's output folder — written by `compose`, always.
3. **Project notes-block parsing** — every composer-authored `.RPP` has structured `chords:`, `move:`, `improv:`, and `roles:` lines per section.
4. **Raw MIDI parsing** — for projects you built by hand, the script falls back to extracting pitch sets from items in the surrounding bars and lets Claude infer chords.

This means fill mode works on **every song you've ever composed with this skill**, even ones predating the EXTSTATE breadcrumb feature — the sidecar and notes-block tiers carry the day. The first fill on a legacy project even upgrades its breadcrumb to tier 1, so future analyses are exact.

## Configuration

Everything user-specific lives in `config.json` (gitignored). Two keys:

```json
{
  "template_path": "~/Library/Application Support/REAPER/ProjectTemplates/claude-composer.RPP",
  "output_root": "~/Documents/MIDI-SONGS"
}
```

| Key | Purpose |
|---|---|
| `template_path` | Path (`~/...` OK) to your Reaper template `.RPP`. The script reads, patches, and writes to your output folder. |
| `output_root` | Where compositions land: `<output_root>/_<YEAR>/composer/<week-folder>/<key>-<bpm>-<slug>/`. Key is lowercase with `#`/`b` and an `m` suffix for minor (`f#m`, `ebm`); bpm is zero-padded to 3 digits so `ls` sorts numerically. See SKILL.md §3 for the full rule. |

Want a personal scratchpad for "what I've found works"? Copy `style.example.md` to `style.md` — Claude reads it at the start of every composition, so guidance you give it persists across sessions. Example entries:

> *Don't default to halftime-verse/driving-chorus arcs.*
> *For Plini/Satriani context, use 8 distinct chord changes per section.*
> *I keep landing on Em — rotate keys.*

## File layout

```
~/.claude/skills/composer/
├── README.md                  ← you are here
├── SKILL.md                   ← the prompt Claude reads — style packs, song forms,
│                                arrangement archetypes, transition idioms, spec reference
├── composer.py                ← the generator (stdlib only, single file)
├── config.example.json        ← checked-in template
├── config.json                ← YOUR local paths (gitignored)
├── style.example.md           ← checked-in template
├── style.md                   ← YOUR scratchpad — preferences, what's worked (gitignored)
└── references.md              ← curated bibliography for the moves in SKILL.md
```

Each generated song goes to:

```
<output_root>/_<YEAR>/composer/<week-folder>/<key>-<bpm>-<slug>/
├── <slug>.RPP                 ← open this in Reaper
├── full.mid                   ← full-song arrangement, any DAW
├── <section>.mid              ← per-section MIDI files
└── spec.json                  ← the JSON spec that produced this song
```

Folder names use `<key>-<bpm>-<slug>` (e.g. `em-128-iron-mile`) so `ls` groups the directory first by key, then by tempo. The `<week-folder>` is optional — for one-offs you can put the song directly under `composer/` — but weekly sessions keep things organized.

`spec.json` is the most useful archive artifact. It captures every musical decision the skill made — key, tempo, form, feel-arc, arrangement, every chord. If a song works, you can read the spec to see why. If it doesn't, hand-edit the spec and re-run the generator.

## Style packs

Each pack in [`SKILL.md`](SKILL.md) is a self-contained recipe: tempo range, default key, which roles to include, which feel-archetypes to reach for, which moves and voicings fit, and a "what to avoid" list. Packs can be combined (e.g. *"a Spanish bridge in a synthwave song"*).

| Pack | Words that select it |
|---|---|
| **Rock** *(default)* | rock, driving, epic, Satriani, Vai, Plini, Polyphia |
| **Cinematic / sad** | sad, emotional, cinematic, melancholy, ballad, Ólafur Arnalds, Sigur Rós, Zimmer |
| **Spanish / Phrygian** | Spanish, Phrygian, flamenco, Latin metal, Andalusian, Rodrigo y Gabriela |
| **Post-rock** | post-rock, Mogwai, Explosions in the Sky, Russian Circles, Caspian |
| **Djent / prog metal** | djent, Periphery, Animals as Leaders, Meshuggah, Tesseract |
| **Synthwave / 80s** | synthwave, retrowave, Carpenter Brut, Kavinsky, Stranger Things |
| **Jazz-funk / fusion** | Jack Thammarat, fusion, smooth jazz instrumental, Cory Henry, Snarky Puppy |
| **Math rock / Midwest emo** | math rock, midwest emo, American Football, TTNG, Toe, fingerpicked indie |

## Standalone usage

You can drive `composer.py` directly without Claude.

**Compose:**

```bash
python3 composer.py compose /path/to/spec.json /path/to/output_dir
```

A minimal spec:

```json
{
  "song_name": "iron-mile",
  "key": "Em",
  "tempo": 135,
  "time_sig": [4, 4],
  "sections": [
    {
      "name": "verse",
      "feel": "halftime",
      "chords": [
        {"name": "Em9",   "beats": 4},
        {"name": "D",     "beats": 4},
        {"name": "Cmaj7", "beats": 4},
        {"name": "B7",    "beats": 4}
      ]
    },
    {
      "name": "chorus",
      "feel": "driving",
      "chords": [
        {"name": "C",   "beats": 4},
        {"name": "G",   "beats": 4},
        {"name": "D",   "beats": 4},
        {"name": "Em",  "beats": 4}
      ]
    }
  ],
  "form": ["verse", "chorus", "verse", "chorus"]
}
```

**Analyze + fill:**

```bash
# Dump the context JSON for a project with a COMPOSER region:
python3 composer.py analyze /path/to/song.RPP

# Then write a fill spec (one section + roles, beats must match region length):
python3 composer.py fill /path/to/fill_spec.json /path/to/song.RPP
```

Full spec field reference is in [`SKILL.md`](SKILL.md) — `roles`, `feel`, `voicing`, `move`, `scales`, `melody`, `melody_loop_beats`, `chugg`, `skip_roles`, plus the supported chord vocabulary.

> **Always close the `.RPP` in Reaper before running `fill`.** The script rewrites the file in place; Reaper holds project state in memory while open and would clobber the changes on its next save.

## Philosophy

This is **an idea incubator, not a song finisher.** The output is rough on purpose. The point is to mine it for chord progressions you'd never have thought of on your own, drop yourself into an idiom you don't normally write in, and have something concrete enough to improvise over by the time you've poured a coffee.

Design choices that fall out of that:

- **Reach wider, not higher.** No drum fills. No walking basslines. No voice leading optimization. No per-note velocity ramping. The energy budget is spent on chord-choice and arrangement variety across genres, not on polishing one output.
- **Variety is enforced.** The skill scans recent outputs and deliberately rotates keys, forms, and arrangement archetypes. The `style.md` scratchpad lets you teach it your taste over time.
- **Musical decisions are Claude's job.** The Python script is dumb — it converts a JSON spec into MIDI and an `.RPP`. Every musical choice — what chords, what key, what feel-arc, what arrangement, what moves to reach for — happens inside Claude's reasoning, guided by the catalogs in [`SKILL.md`](SKILL.md).
- **The DAW is the destination.** The Reaper project is the artifact you actually live in. Per-section `.mid` files exist for cross-DAW portability; `spec.json` exists as the recipe you can hand-edit. Everything else is in service of the `.RPP`.

## Limitations

- No tempo or time-signature changes mid-song.
- Drum patterns are fixed bar-level — no fills, breakdowns, or builds.
- Chord parsing is strict — `C9sus4`, `Cmaj7#11`, and similar extended/altered chords will error. See the supported vocabulary in [`SKILL.md`](SKILL.md).
- No automation, no per-note velocity shaping beyond the built-in pattern defaults.
- The compose step is one-shot — re-running with the same spec overwrites the output `.RPP` / `.mid` / `spec.json`.

## License

[MIT](https://alco.mit-license.org) © Ricardo Alcocer
