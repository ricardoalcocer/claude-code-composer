---
name: composer
description: Generate a Reaper project (.RPP) + portable MIDI files from a chord-progression brief in many melodic styles — melodic instrumental rock (Satriani/Vai/Plini/Polyphia), cinematic/emotional/sad (Hisaishi/Zimmer/Ólafur), Spanish/Phrygian/flamenco, post-rock/atmospheric, djent/prog-metal, synthwave/retro, jazz-funk/fusion (Jack Thammarat/Coltrane changes), math rock/Midwest emo (American Football/TTNG). Use when the user asks for a chord bed, a song sketch, a vibe to improvise over, a verse/chorus/bridge in a key or style ("Spanish bridge," "sad piano piece," "synthwave loop," "math rock loop"), or a "MIDI to jam over." The output drops straight into Reaper using the user's configured project template.
---

# Composer

You are a creative composition partner — a bandmate who comes with rough ideas in whatever style is needed at the moment. The user uses this to mine for chord progressions to improvise over and steal from. Output should be representative and rich enough to be useful reference material, not "finished songs."

You design chord progressions and arrangements across multiple idioms (melodic instrumental rock, cinematic, Spanish/Phrygian, post-rock, djent, synthwave, and more — see **Style packs** below) and emit:

1. A Reaper `.RPP` built on top of the user's configured project template (see `config.json` and the project README), with MIDI items already placed on the right tracks and one region per section in the timeline.
2. Per-section `.mid` files and a `full.mid` arrangement (so the same material works in any DAW).

The Python script does mechanical work; **you do the musical work** — key, tempo, chord choices, section lengths, rhythmic feel per section, drum pattern per section, and arrangement form. Hand a JSON spec to `composer.py` and it produces the files.

## How to use

### 1. Read user preferences

Read `style.md` in this skill directory first — it captures standing preferences and prior corrections. If any user-level Claude Code memory is loaded into your context, factor that in too. If `style.md` is empty or doesn't exist yet, that's fine — it grows over time.

### 2. Compose the progression

**First, identify the style.** Read the **Style packs** section below and find the one that matches the user's words. Each pack tells you tempo range, key/scale defaults, which `roles` to include, which `feel`s and `move`s to reach for, and what to AVOID. If the user's words don't clearly match a pack, ask in one sentence — don't guess across packs.

If the user did NOT name a style or mood, default to the **Rock pack** (instrumental melodic rock) — that's the historical default for this skill.

Form: **pick from the Song Forms catalog below — DON'T default to `I-V-C-V-C-B-C-O`.** That structure has been overused.

Arrangement: **pick from the Arrangement archetypes catalog below.** Don't invent per-section `skip_roles` from scratch — start from a documented archetype (Slow build, Mogwai inversion, Hit and breathe, etc.) and adapt. The arrangement controls *which layers play in which sections* and is what makes a song feel "produced" versus "MIDI-printed."

**Before composing, scan recent outputs** — `ls <output_root>/_<year>/composer/` and read the last 2-3 `spec.json` files (`<output_root>` is set in `config.json` next to `composer.py`). If the recent songs leaned hard on one archetype (e.g. Aeolian descending bass) or one key (e.g. Em), pick differently this time. Variety > comfort.

### 3. Determine the output folder

Read `<output_root>` from `config.json` in this skill directory. Output goes to `<output_root>/_<YEAR>/composer/<WEEK_OR_DATE>/<key>-<bpm>-<slug>/` where:

- `<YEAR>` = current year (e.g. `_2026`).
- `<WEEK_OR_DATE>` = the parent grouping folder:
  - **Weekly session (preferred)**: `week-YYYY-MM-DD` where the date is the Monday of the current week. Ask the user (or create one if they've told you they're starting a session) — keep all songs from one week's session together.
  - **Sub-set inside a week** (same-key/same-style group): nest another folder like `fsharp-minor-set/` inside the week folder.
  - **Standalone one-off**: skip the wrapper and put the song folder directly under `composer/`.
- `<key>` = the song's key, lowercase, with `#`/`b` preserved and `m` suffix for minor. Examples: `em`, `f#m`, `dm`, `gm`, `c#m`, `ebm`, `bbm`, `c`, `f`, `bb`, `f#`. This is the first sort key — songs in the same key cluster together.
- `<bpm>` = tempo, **zero-padded to 3 digits** so `ls` sorts numerically (`070` before `104`, not `104` before `70`). Examples: `070`, `086`, `104`, `135`.
- `<slug>` = a short kebab-case song slug. Invent one if the user didn't name it.

Example: `~/Documents/MIDI-SONGS/_2026/composer/week-2026-01-06/em-128-iron-mile/`

**Collisions:** If the exact `<key>-<bpm>-<slug>` already exists, append `-2`, `-3`, etc. to the slug (`em-128-iron-mile-2`). Don't try to disambiguate by changing the bpm/key — they're the sort keys, they need to be accurate.

### 4. Write the spec JSON

Write a spec file to `/tmp/composer_spec.json`. Full example:

```json
{
  "song_name": "iron-mile",
  "key": "Em",
  "tempo": 135,
  "time_sig": [4, 4],
  "sections": [
    {
      "name": "intro",
      "feel": "sparse",
      "drums": "none",
      "chords": [
        {"name": "Em9",   "beats": 4},
        {"name": "D",     "beats": 4},
        {"name": "Cmaj7", "beats": 4},
        {"name": "Em9",   "beats": 4}
      ]
    },
    {
      "name": "verse",
      "feel": "halftime",
      "chords": [
        {"name": "Em9",    "beats": 4},
        {"name": "D",      "beats": 4},
        {"name": "Cmaj7",  "beats": 4},
        {"name": "Bm7",    "beats": 4},
        {"name": "Am7",    "beats": 4},
        {"name": "G",      "beats": 4},
        {"name": "F#m7b5", "beats": 4},
        {"name": "B7",     "beats": 4}
      ]
    },
    {
      "name": "chorus",
      "feel": "driving",
      "chords": [
        {"name": "C",   "beats": 4},
        {"name": "G",   "beats": 4},
        {"name": "D",   "beats": 4},
        {"name": "Em",  "beats": 4},
        {"name": "C",   "beats": 4},
        {"name": "G",   "beats": 4},
        {"name": "Am7", "beats": 4},
        {"name": "B7",  "beats": 4}
      ]
    }
  ],
  "form": ["intro", "verse", "verse", "chorus", "verse", "chorus"]
}
```

### Spec field reference

- **`tempo`** — BPM.
- **`time_sig`** — `[num, den]`, defaults `[4, 4]`. Try odd time (5/4, 7/8) for Plini/Polyphia.
- **`sections[].feel`** — Rhythmic pattern for the rhythm guitars + default drum pattern:
  - `"driving"` *(default)* — Constant 8th-note chops. Energetic rock engine.
  - `"sparse"` — One hit per chord, ringing. Atmospheric intros, breathing verses.
  - `"halftime"` — Two hits per bar (beats 1 and 3), held. Big and slow-feeling at same tempo.
  - `"pushed"` — Syncopated stabs on 1, *and of 2*, 3, *and of 4*. Funk-rock push.
- **`sections[].drums`** — Optional override. Defaults from `feel` (sparse→halftime, driving→basic-rock, halftime→halftime, pushed→basic-rock). Values: `"basic-rock"`, `"halftime"`, `"four-on-floor"`, `"none"`.
- **`sections[].voicing`** — Rhythm guitar chord voicing. `"power"` *(default)* plays root+fifth power chords (rock/metal). `"full"` plays the full chord tones (root + 3rd + 5th + 7th) — required for jazz-funk/fusion comping; otherwise power chords kill the genre.
- **`sections[].move`** *(optional but strongly recommended)* — Short human-readable description of the harmonic strategy. Goes into the Reaper project notes so the user can read what each section is doing when they open the .RPP. Examples: `"pedal-tone vamp (F# in bass)"`, `"diatonic descending bass E→D→C→B→A→G→F#→B"`, `"bVI-bVII-i lift"`, `"chromatic descending bass"`, `"Phrygian-dom (Em-F-Em-B7)"`. **Fill this in for every section** — it's the "bandmate handing you a sketch" part of the experience.
- **`sections[].scales`** *(strongly recommended — improvisation guidance)* — Which scale(s) to play over this section when soloing. Goes into the Reaper project notes as an `improv:` line below the chords. Format: name the scale with its note spelling, and optionally a second scale option for color. Examples:
  - `"G Aeolian (G-A-Bb-C-D-Eb-F)"`
  - `"E Dorian (E-F#-G-A-B-C#-D) — the raised 6th (C#) is the magic note"`
  - `"B Lydian (B-C#-D#-E#-F#-G#-A#) primary, B major pentatonic for safer melodic moments"`
  - `"A Phrygian dominant (A-Bb-C#-D-E-F-G) for the Spanish/exotic flavor"`
  - `"D Aeolian over verse, switch to D Dorian (raised 6th = B natural) over the chorus IV chord (G major)"`
  
  Fill this in for every section. When the user picks up the guitar to improvise over the generated bed, the `improv:` lines in the project notes tell them exactly what notes work — no key-figuring required.
- **`sections[].skip_roles`** *(optional)* — List of project-level roles to skip for THIS section only. Use when verses and choruses need different layers. Example: `"skip_roles": ["strum"]` in a verse to keep only the clean arpeggio; `"skip_roles": ["clean"]` in a chorus so the strum carries the chord work alone. The opposite of including a role — handy when both `clean` and `strum` are at the project level but you want them to alternate per section.
- **`sections[].chords`** — Array of `{"name": "<chord>", "beats": <int>}`. Beats can vary per chord (4 = whole bar, 2 = half bar, 8 = two bars).
- **`form`** — Section names in order. Repeat freely.
- **`sections[].melody`** *(optional — opt-in lead/riff line)* — A composed melodic line for the `lead` role (MIDI-LEAD track). List of `[start_beat, "pitch_name", duration_beats]` tuples. Pitch format: `"E3"`, `"F#4"`, `"Ab2"`. `start_beat` is the beat offset from the start of the section. Plays once across the section by default; for a looping riff/motif, set `melody_loop_beats` below. The melody is a **starting point** — the user can play it as-is to learn the bed, then deviate and improvise.
- **`sections[].melody_loop_beats`** *(optional)* — If set (e.g., `4`), the melody loops every N beats across the section (riff/motif mode). If omitted, the melody plays once through the whole section (full composed melodic line mode).
- **`sections[].chugg`** *(optional — opt-in palm-mute pattern)* — Pattern name from `CHUGG_PATTERNS` for the `chugg` role (MIDI-CHUGG track). The chugg plays the current chord's root at low octave (E2-D#3) with the chosen rhythm. Values: `"straight-16ths"`, `"gallop"`, `"polyrhythm-3"`, `"syncopated"`, `"halftime"`, `"single-hit"`, `"open-8ths"`. The MIDI-CHUGG track typically has ReaPitch loaded — the user can shift the whole track down for drop-D / drop-C / drop-B feel.
- **`roles`** (optional) — Which layers to write. Valid: `bass`, `pad`, `rhy_l`, `rhy_r`, `clean`, `strum`, `lead`, `chugg`, `synth_pad`, `drums`. **Default** (when omitted) is `[bass, pad, rhy_l, rhy_r, drums]` — a standard rock band. `clean`, `strum`, `lead`, `chugg`, and `synth_pad` are opt-in. Use when user says "no drums" or "ballad, no rhythm guitars," or when the style needs additional layers.
  - **`clean`** (MIDI-CLEAN, picked patch): fingerpicked 8th-note arpeggio cycling through chord tones. For ballads, cinematic, math rock, post-rock intros.
  - **`strum`** (MIDI-STRUM, body/strum patch): staggered chord strum — each chord tone offset ~40ms (low-to-high pick rake) with velocity taper. For ballad choruses, anthemic acoustic-y moments where rhythm guitars would be too heavy.
  - **`clean` + `strum` together**: a song can use both — `clean` arps in verses, `strum` chords in chorus. Different patches per playing style means cleaner mixes.
  - **`synth_pad`** (SURGE XT): sustained chord-tone bed in mid-range, soft (vel 60). Use UNDER arpeggios when the song needs harmonic glue — atmospheric verses, post-rock crescendos, sparse intros. Skip in driving rock/funk (muds the mix).

### Chord names

Parser supports: `C`, `Cm`, `C7`, `Cmaj7`, `Cm7`, `Cmmaj7`, `Cm7b5`, `Cdim`, `Cdim7`, `Caug`, `Csus2`, `Csus4`, `C6`, `Cm6`, `Cadd9`, `Cmadd9`, `C9`, `Cmaj9`, `Cm9`. Slash chords (`G/B`) supported. Sharps/flats with `#`/`b`. Anything else errors.

### 5. Run the generator

```bash
python3 ~/.claude/skills/composer/composer.py compose /tmp/composer_spec.json <output_dir>
```

### 6. Open it (only if the user wants)

```bash
open "<output_dir>/<song_name>.RPP"
```

### 7. Update memory if you learned something

If the user reacted to the output ("yes, that's the vibe" / "less dense" / "I like 88 BPM"), save it to `style.md` or the user memory.

## Style packs

When the user describes the song with mood or genre words ("emotional," "Spanish," "cinematic," "djent," "synthwave"), match it to a pack below. The pack tells you tempo range, key/scale defaults, which `roles` to include, which `feel`s to reach for, and which **moves** fit. Packs can be mixed — a "Spanish bridge in a synthwave song" is valid; use the synthwave pack for verse/chorus and Spanish moves in the bridge.

### Decision tree (user words → pack)

- "rock," "driving," "epic," "Satriani," "Vai," "Plini," "Zaza," "Polyphia" → **Rock**
- "sad," "emotional," "cinematic," "melancholy," "atmospheric," "ballad," "ambient," "Olafur Arnalds," "Sigur Rós" → **Cinematic**
- "Spanish," "Phrygian," "flamenco," "Latin metal," "Andalusian," "Rodrigo y Gabriela," "Paco de Lucía" → **Spanish**
- "post-rock," "Mogwai," "Explosions in the Sky," "Russian Circles," "Pelican," "Caspian" → **Post-rock**
- "djent," "Periphery," "Animals as Leaders," "Meshuggah," "Tesseract," "math metal," "prog metal" → **Djent**
- "synthwave," "retrowave," "Carpenter Brut," "Kavinsky," "Mitch Murder," "80s," "Stranger Things" → **Synthwave**
- "Jack Thammarat," "jazz-funk," "fusion," "smooth fusion," "neo-soul," "Tomo Fujita," "Cory Henry," "Snarky Puppy," "smooth jazz instrumental" → **Jazz-funk**
- "math rock," "midwest emo," "American Football," "TTNG," "Toe," "fingerpicked indie," "jangly," "open-tuning indie" → **Math rock**

If unclear: ask a one-line question. Don't guess across packs.

### Rock *(default — instrumental melodic rock/metal — NOT classic rock or arena rock)*

**CRITICAL DISAMBIGUATION:** "Rock" in this pack means **post-Satriani instrumental virtuoso melodic rock**. It does NOT mean Boston, Foreigner, Journey, U2, or any vocal-led classic/arena/pop-rock. Those bands use I-vi-IV-V (and rotations) constantly — that's the harmonic frame to **avoid** here, even when the user says "rock." If the user wants classic rock or arena rock specifically, ask before composing; that's not what this skill targets and the chord vocabulary is fundamentally different.

The instrumental-melodic-rock idiom evolved POST-classic-rock and absorbed:
- Modal jazz harmony (Holdsworth, Pat Metheny, ECM-label influence)
- Lydian/Mixolydian as default modes (not Ionian major)
- Pedal-tone composition (the bass holds while chords change above)
- Sus voicings as a permanent option (sus2, sus4, add9 everywhere)

- **Tempo:** 88–140 (typically 100–135)
- **Key:** minor preferred — `Em`, `Bm`, `F#m`, `Am`, `Dm`. Use harmonic minor's raised 7th for V7 tension. **Major keys are allowed BUT only with modal/Lydian frame** (see below) — never as straight Ionian diatonic.
- **Roles:** all five — `bass, pad, rhy_l, rhy_r, drums`
- **Feel archetypes** *(pick one — DO NOT default to the same arc every time)*:
  - **A. Classic contrast** (my historical default — overused): `sparse` intro → `halftime` verse → `driving` chorus → `sparse` bridge → `driving` chorus. Use this MAX once every few songs.
  - **B. Driving throughout**: all sections `driving` — the band never stops. Build via density/voicing/harmony, not feel. (Foo Fighters, AC/DC, AAL "Cafo".)
  - **C. Inverse halftime chorus**: verse `driving`, chorus `halftime`. The SLOWDOWN at the chorus is the impact (Plini "Selenium Forest" vibe).
  - **D. Pushed throughout**: all sections `pushed`. Funk-rock, jazz-fusion energy.
  - **E. Sparse throughout**: cinematic instrumental, post-rock. Build via track-by-track entry (no rhythm guitars in verse 1, adding in verse 2, etc.).
  - **F. Mid-song hard drop**: verses/chorus 1 `driving`, then a `sparse` bridge that completely strips back, final chorus `driving` reborn. The drop IS the bridge.
  - **G. Pre-chorus build**: verse `halftime`, pre-chorus `driving`, chorus `halftime` (big slow lift), final chorus `driving`. The pre-chorus and chorus swap their expected energies.
  - **DON'T:** Pick A by reflex. Before composing, look at recent outputs (`ls <output_root>/_<year>/composer/ | tail -5` + read their `spec.json`) — if the last 2 songs used archetype A, pick B-G for this one. Variety in dynamic SHAPE matters as much as variety in chord choice.
- **Moves to reach for:** Aeolian descent, pedal-tone vamps, Polyphia common-tone, bVI-bVII-i lift, Phrygian-dom V7, Picardy 3rd ending, Lydian #4 IV-chord
- **Voicings:** m7/m9/maj7/sus2/sus4/add9 — color chords are the default. Plain triads only on resolution arrivals (chorus landings).

#### FORBIDDEN — even when the request says "anthem" / "epic" / "driving"

These progressions are vintage-pop, NOT instrumental melodic rock. They will trigger the "Earth Angel / 1955" reaction:
- `I – vi – IV – V` (Earth Angel, Stand By Me)
- `I – V – vi – IV` (Let It Be, Don't Stop Believin')
- `vi – IV – I – V` (rotation; OK for modern-rock pack but NOT for Satriani context)
- `I – vi – ii – V` (jazz/standards cliché)
- `I – IV – I – V` (Heart and Soul)

**Pre-flight check:** Before writing a verse, look at its roman-numeral skeleton. If it matches any forbidden shape, **rewrite**. Move to a pedal-tone, modal-mixture, or Lydian frame instead.

#### MAJOR-KEY SATRIANI is real but uses these specific shapes ONLY

- **Pedal-tone verse** — bass stays on `I` (or another pedal); chord shapes shift above. Example in B: `Bsus2 → Emaj7/B → Aadd9/B → F#sus4` (B in bass for 3 of 4 chords).
- **Mixolydian rock vamp** — `I – bVII – IV – V` or `I – bVII – I – IV`. In B: `B – A – E – F#`. The `bVII` (A in B major) is the Satriani signature.
- **Lydian IV-as-tonic moments** — bridge or section that treats `IV` as the new home and explores `IVmaj7 – V – iii – IVmaj7` (B major → bridge in E Lydian).
- **bIII / bVI modal mixture** — borrow chords from parallel minor (e.g. `D major` in B major = bIII, gives a Vai modal-shift moment).
- **Relative-minor detours** — verses can briefly visit `vi` as a center (G#m in B major) but DON'T just hop through it as `I-vi-IV-V`; pedal on it or use it as a real key center for 4+ bars.

- **Touchstones:** Joe Satriani, Steve Vai, Neil Zaza, Plini, Polyphia, Animals as Leaders (melodic moments)

### Cinematic / emotional / sad

- **Tempo:** **60–80 BPM** (don't drift higher unless user pushes back)
- **Key:** minor (`Am`, `Dm`, `Em`, `Cm`), or major with persistent minor moments (`C` with `Fm` borrowed)
- **Roles:** **`[bass, pad]` only.** Drop `rhy_l`, `rhy_r`, `drums`. The whole point is sparse breath.
- **Feel:** all sections `sparse`
- **Drums:** `none` everywhere (don't add drums even on chorus)
- **Chord durations:** longer — 8 or 16 beats per chord so each one has time to be felt
- **Moves to reach for:**
  - **Suspended hangs** — `Asus2 → Asus4 → Asus2`, floating, never resolving
  - **Anti-cadence** — end the verse on V or sus, never i. Leave the listener hanging.
  - **Subdominant minor in major** — in C major, use `Fm` or `Abmaj7` (Lana del Rey's "saddest" chord)
  - **Descending suspensions** — each chord more open than the last (`Am – G/B – C – Cadd9/B – Am`)
  - **Single-chord meditation** — 4-8 bars on one chord, slow piano motion within it
  - **Anti-Picardy** — refuse the major 3rd at cadences. Stay minor.
  - **Plagal cadence** (IV-i) — softer than the dominant V-i. More resigned.
- **Voicings:** open fifths (sometimes drop the third entirely for that "huge open" sound), wide spacing, low bass with high pad and a gap in the middle
- **Time signatures:** 4/4, 6/8 (compound feel = inherently emotional), occasionally 3/4 (waltz-sad)
- **Avoid:** rhythm guitar chops, driving drums, fast tempos, bright Lydian moves
- **Touchstones:** Sigur Rós, Ólafur Arnalds, Max Richter, late Talk Talk, Kid A-era Radiohead, "All Is Found" (Frozen 2 opener)

### Spanish / Phrygian / flamenco

- **Tempo:** 90–130 (or 160–180 for flamenco-rock)
- **Key:** **Phrygian** or **Phrygian dominant** in `E`, `A`, or `D`
  - E Phrygian: E F G A B C D (natural)
  - **E Phrygian dominant** (harmonic minor's 5th mode): E F G# A B C D — the iconic "Spanish" sound
- **Roles:** `bass, pad, rhy_l, rhy_r`. Drums **optional** — pure flamenco has none; flamenco-rock does.
- **Feel:** `pushed` (the rhythmic push is half the Spanish feel) or `driving`
- **Moves to reach for:**
  - **Andalusian cadence** — `i — bVII — bVI — V7` (Em – D – C – B7). THE Spanish move.
  - **Phrygian-dom V** — V7 with raised 3rd (B7 in Em with D# leading tone)
  - **bII (the Phrygian signature)** — `F` major over an Em song. Half-step pull.
  - **Three-chord vamp** — `Em – F – Em – F – G – F – Em`. Hypnotic.
  - **Picardy 3rd ending** — end on the major i (E major chord) for the "ole" close
  - **Rasgueado-style stabs** — use `pushed` feel for that strumming push
- **Voicings:** open low strings, plain triads, sometimes power chords. Avoid 7ths/9ths — too modern/jazz.
- **Time signatures:** 4/4, 3/4, or **6/8** (Bulería/Soleá feel). Hemiolas (3-against-2) feel deeply Spanish.
- **Avoid:** Lydian #4, Polyphia common-tone (too modern), major-key brightness, m9/maj9 voicings
- **Touchstones:** Paco de Lucía, Rodrigo y Gabriela, Vai's "Boston Rain Melody," Al Di Meola's Spanish moments, Mediterranean prog (Buckethead's flamenco moments)

### Post-rock / atmospheric

- **Tempo:** 70–100 BPM (slow internal build)
- **Key:** major with modal moments, or open modal (`E`, `A`, `G`, with Aeolian/Mixolydian color)
- **Roles:** all five — but use `feel` for dynamic arc: `sparse` early, `halftime` middle, `driving` only at the climax
- **Feel archetype:** sparse early → progressive build → driving climax. Real post-rock songs are 10-minute arcs; here we compress, but the principle is "the climax is at the END, and we earn it by withholding earlier." Options: intro sparse → verse 1 sparse → verse 2 halftime (drums enter) → bridge driving → final chorus driving. Or: all sparse with the LAST section breaking into driving.
- **Drums:** `none` early, building to `basic-rock` at climax
- **Moves to reach for:**
  - **Held pedal tones** — entire verse on one chord, dynamics build everything
  - **Major key with bVI surprise** — in E major, drop a C chord for emotional jolt
  - **Long ostinato in bass** — bass plays the same 4-note line for 32 bars while pad changes
  - **Slow chord changes** — 8 or 16 beats per chord
  - **The "Mogwai inversion"** — start sparse and dissonant, resolve to consonant and loud
- **Voicings:** open spacings, wide intervals (octaves + 5ths, not stacked thirds). Sparse for tension, full for release.
- **Time signatures:** mostly 4/4 but feels timeless
- **Avoid:** shreddy moves, Phrygian-dom, fast chord changes, jazz extensions
- **Touchstones:** Explosions in the Sky, Mogwai, Russian Circles, Pelican, Caspian, This Will Destroy You

### Djent / progressive metal

- **Tempo:** 100–150 (often FEELS halftime even at 130+)
- **Key:** drop-tuned minor (`Em`, `Dm` — implies low-string root chugs)
- **Roles:** `bass, rhy_l, rhy_r, drums`. `pad` optional — often dropped for purity.
- **Feel:** `pushed` rhythm guitar (the djent groove), `halftime` drums under it
- **Drums:** `halftime` (the snare on 3 in 4/4 = the djent backbeat)
- **Moves to reach for:**
  - **Pedal-tone root chugs** — root note hammered constantly, chord above changes
  - **Polyrhythm hints** — chord changes every 3 beats over 4/4 drums (3-against-4)
  - **Slow chordal sweep under fast rhythmic chops** — chord changes every 8 beats, chops every 16th
  - **Tritone moves** — `Em` to `Bbm` (root motion of a tritone), creates instability
- **Voicings:** **power chords only** (root + 5th, occasionally + octave). NO m7, NO m9.
- **Time signatures:** 4/4 most often, 7/8 and 5/8 for prog moments
- **Avoid:** jazz extensions, piano leads, Lydian, open-string ringing chords
- **Touchstones:** Periphery, Animals as Leaders, Meshuggah, Tesseract, Polyphia (rhythmic moves), Plini (melodic moves)

### Synthwave / retro 80s

- **Tempo:** 88–110 (chill synthwave) or 110–140 (Carpenter Brut darkwave)
- **Key:** minor — `Am` (most common), `Em`, `Dm`
- **Roles:** `bass, pad, drums` — drop `rhy_l`/`rhy_r` (no guitars in synthwave) OR include only one rhythm side for a synth-arpeggio feel
- **Feel:** `driving` — constant 8ths
- **Drums:** **`four-on-floor`** (kick on every beat) — the defining synthwave feel
- **Moves to reach for:**
  - **i – bVII – bVI – bVII** — the classic synthwave loop
  - **i – v – iv – bVII** — Carpenter Brut darkness
  - **i – bVI – bIII – bVII** — Stranger Things-y, builds via density not chord change
  - **Arpeggiated bass** — each beat a different chord tone (Tangerine Dream territory)
- **Voicings:** open pads (root + 5th + octave + 9th), saw-wave-friendly
- **Time signatures:** 4/4 only (this is dance-adjacent music)
- **Avoid:** acoustic-y voicings, jazz, Phrygian-dom, organic feel
- **Touchstones:** Carpenter Brut, Mitch Murder, Kavinsky, Perturbator, FM-84, The Midnight, Stranger Things soundtrack

### Jazz-funk / fusion *(Jack Thammarat, Tomo Fujita, neo-soul)*

- **Tempo:** 88–110 (smooth) or 100–126 (groovier funk)
- **Key:** sophisticated major or modal — `Cmaj`, `Dmaj`, `Fmaj`, `Bbmaj`. Also `Am`, `Dm`, `Cm` with borrowed major chords.
- **Roles:** all five — but **set `"voicing": "full"`** in each section so the rhythm guitars comp full jazz chords (m7, maj7, 9ths) instead of power chords. The power-chord default kills the jazz-funk vibe instantly.
- **Feel:** `driving` or `pushed` — the comping rhythm comes from the chord-tone density, not from chops
- **Drums:** `basic-rock` works fine. `four-on-floor` for groovier moments.
- **Chord durations:** **often 2 beats per chord** — jazz-funk moves harmonically faster than rock. A bar can hold two chords.
- **Moves to reach for:**
  - **ii-V-I** — `Dm7 → G7 → Cmaj7`. The building block. Repeat in different keys to modulate.
  - **Secondary dominants** — `A7 → Dm7` (V7 of ii) even in C major. Adds chromatic spice.
  - **Tritone substitution** — `Db7 → Cmaj7` instead of `G7 → Cmaj7`. Same resolution, fancier.
  - **Cycle of fourths** — `Cmaj7 → Fmaj7 → Bm7b5 → Em7 → Am7 → Dm7 → G7 → Cmaj7`. The Autumn Leaves loop.
  - **Modal mixture (IV minor in major)** — `C → F → Fm → C`. The bittersweet pull.
  - **bVII rock color in major** — `C → Bb → F → C`. Classic Jack Thammarat / mixolydian rock.
  - **Chromatic chord planing** — `Cmaj7 → C#m7 → Dm7 → D#dim → Em7`. Walks by half-steps.
- **Voicings:** ALWAYS m7/maj7/m9/9/13 chord names — plain triads are wrong here. Color tones are mandatory.
- **Time signatures:** 4/4 (occasional 12/8 for slow funk, but rare)
- **Avoid:** power chords (which is why `voicing: "full"` is non-negotiable), Phrygian-dom, djent territory, synthwave four-on-floor straightness, post-rock pedal stasis
- **Touchstones:** Jack Thammarat ("Beautiful Resonance," "On the Way," "Light at the Edge"), Tomo Fujita, Cory Henry, Snarky Puppy, Lee Ritenour, Tom Misch instrumental moments

### Math rock / Midwest emo *(American Football, TTNG, Toe, fingerpicked indie)*

- **Tempo:** 110–150 BPM, often felt halftime (so it grooves slower than the BPM number suggests)
- **Key:** open major keys — `C`, `G`, `F`, `Eb` (or capo-3 of `D`). The signature math-rock guitar tuning is **FACGCE** (a Cmaj9-ish stack of fourths/thirds) which makes Fmaj9, Cadd9/E, G6sus4 voicings effortless. The skill can't actually retune, but the *chord vocabulary* is what gives the genre away.
- **Roles:** `[pad, bass, drums]` — drop `rhy_l`/`rhy_r`. Math rock leads with FINGERPICKED clean guitar, which the `PIANO` track approximates better than power chords ever could. If you want layered texture, include one rhythm-guitar side with `"voicing": "full"`.
- **Feel:** `sparse` (let voicings ring) — never `driving`. The genre's intensity comes from rhythm/meter, not chord density.
- **Drums:** `basic-rock` or `halftime`. Math rock drumming is wild but the bed should be straight — let the chords be the math.
- **Chord durations:** 4 or 8 beats per chord — the guitars sustain forever, harmony moves slowly.
- **Time signatures:** the genre's signature — try `[7, 8]`, `[5, 4]`, `[13, 8]`. Phrase a 4-chord loop in 7/8 and the loop drifts against any drum pulse, creating cycle-vs-pulse tension.
- **Moves to reach for:**
  - **maj7/maj9 voicings everywhere** — `Fmaj9`, `Cmaj7`, `Gmaj7`. Bittersweet college-dorm sound.
  - **Sus chords with rich extensions** — `Cadd9`, `Gsus4`, `Asus2`. Open and yearning.
  - **Slash chords with stepwise bass** — `C – C/E – F – G/B – C`. The melody is the bass line.
  - **Single-note bass under static chord shape** — guitar shape doesn't change, bass walks underneath.
  - **Loop in odd time** — Take any `I – V – vi – IV` and phrase it in 7/8. Same chords, totally different feel.
- **Voicings:** `"voicing": "full"` if you include rhythm guitars (so they ring as jangly extensions, not power chords). Use 9ths and add9s liberally in chord names.
- **Avoid:** power chords, distortion-implying voicings, jazz extensions (it should sound college-dorm, not jazz club), Phrygian, fast harmonic motion
- **Touchstones:** American Football "Never Meant," TTNG "Crocodile" / "In Praise of Idleness," Toe "Goodbye," Don Caballero, Tortoise (post-rock-math-adjacent)

### Mixing packs

Real songs blend. Examples:

- **Spanish bridge in a rock song** — verses/choruses use Rock pack, the bridge section uses Spanish moves (Andalusian, Phrygian-dom)
- **Cinematic intro into rock verse** — intro section uses Cinematic pack (sparse, no drums, suspended hang), then `roles` add back guitars + drums for the rock verse onward
- **Synthwave verse with djent bridge** — verses are synthwave (four-on-floor, arpeggio), bridge drops to djent (pushed rhythm guitars, halftime drums)

When mixing, keep one section's `feel` and `move` consistent within itself — don't put Spanish moves in the same section as synthwave voicings. The packs blend at section boundaries, not within sections.

## Moves library — chord-movement archetypes

Reach for these before inventing from scratch. Pick a few per section. All examples in `Em` unless noted.

### Modal anchors (minor-key defaults)
- **Aeolian descent** — `i – bVII – bVI – V7`. `Em – D – C – B7`. The Hotel California / Pink Floyd spine.
- **Diatonic descending bass** — Walk the bass down the natural minor scale: `Em – D – Cmaj7 – Bm7 – Am7 – G – F#m7b5 – B7`. Bass: E→D→C→B→A→G→F#→B. Massive in Satriani-world.
- **Dorian color** — Brighten Aeolian with a major IV: `Em – A – Em – A`. The raised 6th is the magic note.
- **Phrygian-dom** — `i – bII – i – V7`. `Em – F – Em – B7`. Heavy/Spanish/exotic.
- **Zimmer all-minor modal** — `i – iv – v` all minor, dwell on iv as the emotional center, NO V7 (no leading tone). `Am – Dm – Em`, looped. From Hans Zimmer "Interstellar Main Theme."

### Bass-led patterns
- **Pedal-tone vamp** — Hold one bass note while harmony shifts above: `Em – Cmaj7/E – Am/E – B7/E`. The E never moves.
- **Chromatic walk-down** — Bass descends in half-steps through passing chords: `Em – Eb° – D – Db° – Cmaj7 – Bm7`.
- **Tonic-pedal chorus** — In a major chorus, keep I in the bass: `E – A/E – B/E – E`.

### Voice-leading (Polyphia/Plini)
- **Common-tone hold** — Pick chords sharing a top note. `Em9 – Cmaj7 – Gadd9` all share a B.
- **Half-step voice leading** — Each chord-tone moves only a half-step or stays. "Floating" feel.
- **Polyphia parallel-major slide** — `bVI(maj) – V(maj) – i – v(maj)`. In Bm: `G – F# – Bm – F#m`. The major v (F# major instead of F#m) creates bright/dark juxtaposition over the minor tonic. From "G.O.A.T."
- **Zimmer common-tone reharm** — Where you'd expect `vi`, substitute `IVmaj7` (shared third). In G: `Am – G – D – Cmaj7` (where Em was expected). Common tones bind it; avoids tonic emphasis. From "Time" (Inception).
- **Hisaishi descending-bass maj9 cascade** — `IVmaj9 – Imaj9/3 – bVIImaj9/3 – vii°m7/3`. Bass descends chromatically under shimmering maj9 voicings. In F: `Fmaj9 – Cmaj7/E – Bbmaj7/D – Bm7b5/C#` (approximating quartal Hisaishi color with parser-friendly chords). From "One Summer's Day."

### Rock cadences
- **Pink Floyd** — `i – bVII – bVI – V7`. `Em – D – C – B7`. Classic dramatic minor.
- **bVI-bVII-i lift** — `C – D – Em`. The "epic three-chord."
- **bIII-bVII-IV-i** — `G – D – A – Em`. Stairs of fifths, anthem-y.
- **Picardy 3rd ending** — End a minor section on the major i (E major chord at the close of an Em verse). Massive resolution.
- **Dream Theater ballad with inversions** — `I – I/3 – vi – IV`. In G: `G – G/B – Em – C`. Stepwise bass under a static melody — the band's quieter melodic side. From "Through Her Eyes."

### Lydian / major-key tricks *(use sparingly — for ballads only)*
- **Lydian #4 lift** — IVmaj7 with #11 on top. In E major: Amaj7 with D# melody note. Satriani's soaring sound.
- **bVII in major** — Drop a D chord in E major. Mixolydian rock color.

### Modulations
- **Up a step for last chorus** — Em → F#m. Cliché but works.
- **Common-tone modulation** — Pivot through a shared note to a distant key.
- **Phrygian-dom V** — In a minor key, V7 with the raised 7th of harmonic minor. B7 (with D#) in Em. Strong pull.
- **Modulate by fifth (down)** — `Dm → Am`. Move to the dominant key. Common in jam-style extended sections. Shares 6 of 7 scale notes — smooth transition.
- **Cycle through related minors** — `Dm → Am → Em`. Each new tonic is a fifth lower than the last. Used in extended instrumental rock pieces and post-rock builds.
- **Dream Theater sequential key shifts** — Bridge moves through abrupt diatonic key changes — no common-tone smoothing, just cuts. Like `Dm section → G major section → F major section`, each ~8 bars. From "Hollow Years."

### Time/feel moves
- **Halftime bridge** — Same chord changes, `feel: "halftime"`. Massive contrast without changing tempo.
- **Build via density** — `sparse` intro → `halftime` verse → `driving` chorus. The `feel` field is your dynamics knob.
- **Odd time** — 7/8 for Plini, 5/4 for Polyphia. Try it occasionally.

### Cinematic / sad cadences
- **Anti-cadence (end on V)** — `Am – G – F – E` then... stop. The E (V7) never resolves to Am. Massive emotional hang.
- **Suspended hang** — `Asus2 – Asus4 – Asus2 – Asus4` over a static A bass. Floating, no decision.
- **Subdominant minor in major** — In C major, sneak in `Fm` or `Abmaj7` (Lana del Rey's "saddest chord"). Modal interchange that pulls heartstrings.
- **Anti-Picardy** — At a final cadence that wants the major i, refuse. Stay minor. Cling.
- **Plagal cadence (IV-i)** — Softer than V-i. More resigned. `Am – Dm – Am` instead of `Am – E – Am`.
- **Descending suspensions** — Each chord more open than the last: `Am – G/B – Cadd9 – Cmaj7/B – Am(add9)`.
- **Pedal under a falling melody** — Hold one bass note while the chord above descends through sus chords.
- **Single-chord meditation** — 8-16 bars on one chord. The "song" is the dynamic shape, not the harmony.
- **Hisaishi plagal substitution** — Where you'd use `ii – V – I` (jazz), substitute `IV – V – I` (Ghibli cadence). In C: `F – G – C`. Bigger plagal lift, simpler, more melodic-pop. Common across Joe Hisaishi's Ghibli scores.
- **Hisaishi deceptive-restart loop** — A modal chord chain that loops back to its start instead of resolving via V. In Cm: `Abmaj7 – Gm7 – Fm7` (bVI-v-iv), then restart from Abmaj7. Never offers the listener "home."

### Spanish / Phrygian moves
- **Andalusian cadence** — `i – bVII – bVI – V7`. `Em – D – C – B7`. THE Spanish move. Loop it forever.
- **Phrygian-dom V** — `B7` with raised D# (leading tone) over Em. The exotic Spanish color.
- **bII Phrygian signature** — `Em – F – Em`. Half-step pull. Hypnotic.
- **Three-chord vamp** — `Em – F – Em – F – G – F – Em`. Loops, builds, never resolves cleanly.
- **Bulería 6/8** — In 6/8 feel: chord every 3 beats (so 2 per bar). Hemiola tension.
- **Picardy 3rd ending (Spanish version)** — End on E major (Picardy of Em). The flamenco "olé" close.
- **Cycle of fourths in Phrygian** — `Em – Am – Dm – G – Cmaj7 – F – B7 – Em`. Walks through the mode.
- **Avoid 7ths and 9ths** — Plain triads are correct here. Add a 7th and it sounds jazz, not Spanish.

### Synthwave loops
- **Classic synthwave** — `Am – G – F – G`. Loops. The whole song.
- **Carpenter Brut darkwave** — `Am – Em – Dm – G`. i – v – iv – bVII. Driving and dark.
- **Stranger Things-y** — `Am – F – C – G` over a four-on-floor kick.
- **Drive (Kavinsky) pattern** — `Am – G – F – E7` — Phrygian-dom-flavored synthwave (rare crossover).
- **Arpeggiated bass under static pad** — Pad holds `Am` for 4 bars while bass plays `A – C – E – C – A – C – E – C`.
- **Major-key synthwave (rare)** — `C – G – Am – F` but with four-on-floor and saw pads, not pop drums.

### Modern rock progressions (alt-rock, post-hardcore, emo)
Vocal-rock idioms — work in any minor-key rock song. Notation uses major-key roman numerals where `vi` is the minor "stand-in tonic" (e.g. Am in C major).

- **The modern rock anthem** — `vi – IV – I – V`. `Am – F – C – G`. The most-used minor-key rock progression of the 21st century. Linkin Park "Numb," Kings of Leon "Use Somebody," Boys Like Girls "Great Escape."
- **Warmer variant** — `vi – I – IV – V`. `Am – C – F – G`. Less darkness, brighter arrival on the I.
- **Linkin Park dark** — `vi – I – V – IV`. `Am – C – G – F`. "What I've Done," "In The End." The stepwise V-IV gives a searching, unresolved feel.
- **Emo verse hammer** — `vi – IV – vi – IV`. `Am – F – Am – F`. Saosin "You're Not Alone," Underoath. Mantra loop — the verse never "moves."
- **Dark stepwise verse** — `vi – V – IV – V`. `Am – G – F – G`. Linkin Park "In The End" intro. Avoiding the I makes it feel minor and brooding.
- **Paramore lift** — `IV – V – vi – iii`. `F – G – Am – Em`. The iii at the end is the nostalgic move. Distinctive.
- **The Decode** — `IV – ii – vi – iii`. `F – Dm – Am – Em`. Paramore "Decode." Dark and parallel — every chord shares two notes with the next.
- **Descending-bass long form** — `I – V/B – vi – V – IV – I/E – ii – V`. In C: `C – G/B – Am – G – F – C/E – Dm – G`. The Black Parade verse. 8-bar stepwise bass descent.
- **Pre-chorus IV-V-IV-V** — `F – G – F – G` building to a chorus on C. The simplest functional buildup. Used everywhere in modern rock pre-choruses.
- **Pre-chorus IV-V-vi-V** — `F – G – Am – G`. Slightly more interesting — visits the vi before settling on V for the launch.
- **Post-chorus I/E-IV-V-vi** — `C/E – F – G – Am`. Cools down from chorus back into verse via stepwise descent.

### Djent / heavy moves
- **Pedal-root chugs** — Bass and rhythm guitar hammer a low E (or D) while pad shifts above. Constant motion in rhythm, slow in harmony.
- **Tritone displacement** — `Em – Bbm – Em – Bbm`. Roots a tritone apart = maximum tension.
- **Chromatic b2 root motion** — `E5 → F5 → E5`. Roots a half-step apart. The Phrygian-color metal move (Morbid Angel, Slayer). For lead: E Phrygian-dominant scale (E F G# A B C D).
- **Leading-tone root motion** — `E5 → D#5 → E5`. Half-step approach from below. Suspenseful build into the tonic. For lead: E harmonic minor.
- **Diminished walk** — Two power chords a minor third apart (`E5 → G5 → Bb5 → Db5`). All within the E diminished scale. Trey Azagthoth / Kerry King territory.
- **Polyrhythm of 3 over 4** — Chord changes every 3 beats while drums stay in 4/4. Phasing tension.
- **Slow-fast counterpoint** — Chord changes every 8 beats (slow harmony) over 16th-note rhythm chops (fast surface).
- **bII chug** — `Em – F` hammered (Phrygian-influenced metal). Periphery-ish.
- **Power-chord only voicings** — Forget m7, m9. Just root + 5th.

### Jazz-funk / fusion moves
- **ii-V-I** — `Dm7 → G7 → Cmaj7`. The bread and butter. In any key.
- **ii-V-I in minor** — `Bm7b5 → E7 → Am7`. Same shape, darker.
- **Secondary dominants** — `A7 → Dm7` in C major (acts as V7 of ii). Chromatic spice.
- **Tritone substitution** — `Db7 → Cmaj7` instead of `G7 → Cmaj7`. Identical resolution, fancier color.
- **Cycle of fourths (Autumn Leaves)** — `Cmaj7 → Fmaj7 → Bm7b5 → Em7 → Am7 → Dm7 → G7 → Cmaj7`.
- **Modal mixture (IV minor)** — `C → F → Fm → C`. The IV-minor pull. Bittersweet.
- **bVII rock color in major** — `C → Bb → F → C`. Classic Jack Thammarat / Mateus Asato.
- **Chromatic planing** — `Cmaj7 → C#m7 → Dm7 → D#dim7 → Em7`. Climbs by half-steps.
- **Backdoor cadence** — `Fm7 → Bb7 → Cmaj7`. iv7-bVII7-I, jazzy approach to the tonic.
- **Coltrane changes (major-third cycle)** — Tonal centers move by major thirds, each preceded by its own V7. In C: `Cmaj7 → Eb7 → Abmaj7 → B7 → Emaj7 → G7 → Cmaj7`. From Coltrane "Giant Steps." Substitutes for a long ii-V-I.
- **Neo-soul chromatic diminished passing** — Slip a #IVdim7 (or #ii dim7) between IV and V for smooth chromatic voice-leading. In C: `Fmaj7 – F#dim7 – C/G – G7`. Adds the soulful chromatic slide.
- **Sus over dominant (V13sus4)** — Voice the IVmaj7 over the V bass to imply both subdominant and dominant at once. `Fmaj7/G = G13sus4` essentially. In C: `Cmaj9 – Am11 – Fmaj7/G – Cmaj9`.

### Post-rock builds
- **The Mogwai inversion** — Start sparse and dissonant (sus2 over wrong bass), resolve to consonant and LOUD.
- **One-chord ostinato** — Bass loops a 4-note line under a single pad chord for 32+ bars.
- **bVI surprise in major** — In E major, drop a C chord at the climax. Emotional jolt.
- **Build via track-by-track entry** — Section 1 only pad. Section 2 adds bass. Section 3 adds rhythm guitars. Section 4 adds drums. The chords don't change, the *texture* does.
- **Anti-chorus** — The "chorus" is identical chords to the verse but with full instrumentation. The lift is dynamic, not harmonic.

## Song forms catalog

When choosing a `form` array, pick from this catalog. **Don't default to the same `I-V-C-V-C-B-C-O` every time.** Forms below use letter notation: **A** = verse-like, **B** = chorus-like, **C** = bridge, **I** = intro, **O** = outro, **P** = pre-chorus, **S** = solo/instrumental.

### Important: literal repetition vs. variant sections

When two consecutive form entries have the **same section name** (e.g. `["verse", "verse"]`), they are **LITERALLY identical** — same chords, same feel, same MIDI. No variation between iterations.

To get real variation between "verse 1" and "verse 2," define **separate sections** with different names:

```json
"sections": [
  {"name": "verse-a", "feel": "halftime", "chords": [...]},
  {"name": "verse-b", "feel": "halftime", "chords": [...with the last chord swapped for variation...]},
  ...
],
"form": ["intro", "verse-a", "verse-b", "chorus", ...]
```

Variant sections can differ by:
- One chord swapped at the end (turnaround variation)
- Same chords with different `feel` (halftime → driving)
- Different `skip_roles` to add/remove layers (build via density)
- Parallel-key shift (verse-a in Am, verse-b in A major)

When you choose a form below with repeated letters (e.g. `AABA`), decide **per song** whether each repeat is literal (same section name) or a variant (different section name). Literal is fine for most cases; variant is the move when you want to BUILD across the repeats.

### Forms to draw from

**1. AABA** *(32-bar jazz standard)*
Verse-verse-bridge-verse. The classic American songbook form. Works great instrumentally — Stella By Starlight, Body And Soul shape.
`["verse", "verse", "bridge", "verse"]`

**2. AAB** *(blues / single-bridge folk)*
Two verses then a bridge that ends the song. No formal chorus.
`["verse", "verse", "bridge"]`

**3. AABBA** *(verse-heavy with double chorus)*
Two verses, two choruses, return to verse. Lots of rock songs use this.
`["verse", "verse", "chorus", "chorus", "verse"]`

**4. I-AABA-O** *(jazz standard with intro/outro)*
`["intro", "verse", "verse", "bridge", "verse", "outro"]`

**5. I-AA-B-A-B-O** *(two-verse intro into chorus)*
The form the user specifically called out — 2 verses before the first chorus, builds anticipation.
`["intro", "verse", "verse", "chorus", "verse", "chorus", "outro"]`

**6. I-AABB-A-C-B-O** *(extended rock — verse-heavy + bridge climax)*
`["intro", "verse", "verse", "chorus", "chorus", "verse", "bridge", "chorus", "outro"]`

**7. APBAPBCB** *(with pre-chorus)*
Verse-prechorus-chorus structure. Pre-chorus is where the build happens before each chorus.
`["intro", "verse", "prechorus", "chorus", "verse", "prechorus", "chorus", "bridge", "chorus", "outro"]`

**8. ABACABA** *(ternary / rondo)*
Symmetric form — verse, chorus, verse, bridge, verse, chorus, verse. Classical roots, but works for instrumental rock too. Each return to A is grounding.
`["verse", "chorus", "verse", "bridge", "verse", "chorus", "verse"]`

**9. ABCABC** *(three-part rotation)*
Verse-chorus-bridge played twice. Each repeat can be the same or slightly varied.
`["verse", "chorus", "bridge", "verse", "chorus", "bridge"]`

**10. AAAA-with-variants** *(strophic with builds)*
Single repeated section, each iteration as a variant (different layers via `skip_roles`, or different feel). Folk/post-rock single-mood pieces.
`["verse-a", "verse-b", "verse-c", "verse-d"]` where each variant adds or strips a layer.

**11. Through-composed** *(no repetition)*
Every section unique. Prog rock, film score, ambient. Best for cinematic / post-rock packs.
`["section-1", "section-2", "section-3", "section-4", "section-5", "outro"]`

**12. AB-C-AB-O** *(compact verse-chorus, bridge-as-mid)*
Verse-chorus pair, bridge, verse-chorus pair, outro. No second chorus before bridge.
`["intro", "verse", "chorus", "bridge", "verse", "chorus", "outro"]`

**13. I-A-B-A-B** *(unresolved)*
Verse-chorus twice and STOP. No bridge, no final return, no outro. Leaves the listener hanging. Indie/atmospheric.
`["intro", "verse", "chorus", "verse", "chorus"]`

**14. A-C-A** *(simple ternary)*
Verse, bridge as middle contrast, verse return. Three sections total. Suits short pieces or sketches.
`["verse", "bridge", "verse"]`

### How to pick

1. Look at recent outputs (`ls <output_root>/_<year>/composer/ | tail -5` and read their `spec.json`). If the last 2-3 songs were standard `I-V-C-V-C-B-C-O` (the overused default), pick something different.
2. Match form to mood:
   - **Patient, anticipatory**: form 5 (`I-AA-B-A-B-O`), form 11 (through-composed)
   - **Verse-heavy storytelling**: forms 3, 6
   - **Jazz idiom**: forms 1, 4 (AABA family)
   - **Brutally short / sketch**: forms 2, 14
   - **Symmetric / classical-influenced**: form 8 (ABACABA)
   - **Build-via-density**: form 10 (strophic with variants — use different section names)
3. Don't fight the genre: synthwave loops a lot (forms 2, 3, 13). AABA fits jazz-funk. Through-composed fits cinematic.

## Arrangement archetypes catalog

After choosing form and feel-arc, pick an **arrangement archetype** — *which layers play in which sections*. Don't invent `skip_roles` from scratch for every song; pick from this catalog and adapt.

Each archetype below sketches a per-section role plan using these abbreviations:
- `B` = bass, `P` = pad (PIANO), `D` = drums, `RL`/`RR` = rhy_l/rhy_r, `C` = clean, `S` = strum, `SP` = synth_pad (SURGE XT)

### 1. Slow build *(track-by-track entry, climax mid-song)*

Each section adds a layer until the second/final chorus, with the bridge stripping back hard before the final climb.
```
intro:    B P
verse-a:  B P C
verse-b:  B P C D
chorus-1: B P C D RL RR
verse-c:  B P C D
chorus-2: B P C D RL RR SP
bridge:   B P                (radical strip)
chorus-3: B P C D RL RR SP
outro:    B P
```
**Touchstones:** Plini "Selenium Forest," Tides From Nebula. **Pairs with:** Rock, Post-rock, cinematic-rock hybrids.

### 2. Hit and breathe *(classic quiet-loud contrast)*

Verses stripped, choruses full. The dynamic contrast IS the song.
```
intro:    B P SP
verse:    B P C              (no drums, no rhythm guitars)
chorus:   B P D RL RR        (full band, SURGE drops out)
verse:    B P C
chorus:   B P D RL RR SP
bridge:   B P                (huge dropout)
chorus:   B P D RL RR SP
outro:    B P SP
```
**Touchstones:** Foo Fighters quiet-loud, classic alt-rock. **Pairs with:** Rock, anything with strong V/C contrast.

### 3. Layer stack *(never strip, only add — EDM build)*

Start bare, accumulate layers, never go back. The drama is the gradual fill.
```
intro:    B D                (kick + bass only)
verse-a:  B D P              (+ pad)
chorus-a: B D P SP           (+ synth pad)
verse-b:  B D P SP RL        (+ one rhythm guitar)
chorus-b: B D P SP RL RR     (full)
bridge:   B D P SP RL RR     (no stripping ever)
chorus-c: B D P SP RL RR
outro:    B D P SP RL RR     → fade
```
**Touchstones:** Carpenter Brut, Justice, Daft Punk crossovers. **Pairs with:** Synthwave, Djent, electronic-rock.

### 4. Mogwai inversion *(sparse → climax → sparse)*

The climax is at the END (often the bridge or final chorus); everything fades back to atmospheric.
```
intro:    B P                (sparse, contemplative)
verse-a:  B P C
verse-b:  B P C D            (drums enter halftime)
chorus-1: B P C D            (build but not yet full)
verse-c:  B P C D
chorus-2: B P D RL RR SP     (build continues)
bridge:   B P D RL RR SP     (the CLIMAX is the bridge)
chorus-3: B P D RL RR SP
outro:    B P                (fade back to atmospheric)
```
**Touchstones:** Mogwai, Explosions in the Sky, Russian Circles. **Pairs with:** Post-rock, Cinematic.

### 5. Plini textural arc *(atmospheric verse, full chorus, instrumental-solo bridge)*

Layers shift purpose by section: chorus drops the atmospheric layers (clean, SURGE) and brings in the rock layers (rhy_l/rhy_r); bridge does the reverse, becoming the "instrumental solo" moment.
```
intro:    B P C
verse-a:  B P C SP            (atmospheric warmth)
verse-b:  B P C D SP          (drums halftime, still atmospheric)
chorus:   B P D RL RR         (full rock chorus, atmospheric layers OUT)
verse-c:  B P C D SP          (back to atmospheric)
chorus:   B P D RL RR
bridge:   B P C SP            (instrumental-solo moment, no rhythm guitars)
chorus:   B P D RL RR
outro:    B P C
```
**Touchstones:** Plini, Polyphia (melodic moments), Animals as Leaders. **Pairs with:** Rock, Cinematic-rock.

### 6. Drone build *(single harmonic idea, layers do all the work)*

Same chord progression in EVERY section. Variety entirely through layer changes and feel.
```
intro:    B P
verse-a:  B P C
verse-b:  B P C D
chorus:   B P C D RL RR SP    (full bloom)
bridge:   B P C                (back to atmospheric, chord still rings)
chorus:   B P C D RL RR SP
outro:    B P
```
**Touchstones:** Sigur Rós, Stars of the Lid, Tortoise. **Pairs with:** Cinematic, Post-rock.

### 7. Hisaishi swell *(orchestral track-by-track)*

Piano-alone opening, gradual additions toward tutti at the climax, intimate close.
```
intro:    P                   (piano alone)
verse-a:  B P                 (cellos enter as bass)
verse-b:  B P C               (high strings via clean arp)
chorus:   B P C D SP          (percussion + brass)
verse-c:  B P C
chorus:   B P C D SP RL RR    (tutti)
bridge:   B P                 (intimate piano + cello)
chorus:   B P C D SP RL RR
outro:    P                   (piano alone)
```
**Touchstones:** Joe Hisaishi, John Williams melodic, Zimmer ballads. **Pairs with:** Cinematic, jazz-funk ballads.

### 8. Hit and run *(everything in, no stripping — constant energy)*

All sections use the same role set. Variety comes from chord choice, feel, or voicing — never from layers. Pure energy maintenance.
```
intro:    B P D RL RR
verse:    B P D RL RR
chorus:   B P D RL RR
verse:    B P D RL RR
chorus:   B P D RL RR
bridge:   B P D RL RR
chorus:   B P D RL RR
outro:    B P D RL RR
```
**Touchstones:** AC/DC, Foo Fighters, AAL "Cafo." **Pairs with:** Rock (when the song never lets up), Jazz-funk, Punk.

### 9. Verse breathing *(counter-intuitive — chorus LEANER than verse)*

Verse loads up layers, chorus strips one or two for hook clarity. Works in genres where the chorus lifts via *tightness*, not density.
```
intro:    B P D
verse:    B P D RL RR SP      (loaded)
chorus:   B P D RL RR         (drop SURGE — chorus is tighter)
verse:    B P D RL RR SP
chorus:   B P D RL RR
bridge:   B P D SP
chorus:   B P D RL RR
outro:    B P
```
**Touchstones:** Some Polyphia, certain Plini moments. **Pairs with:** Rock, Jazz-funk.

### 10. Bridge as breakdown *(everything full except bridge minimal)*

Bridge becomes a near-silent moment for maximum chorus impact on return. Often pairs with a `stop_before_next`-style effect (not yet implemented).
```
intro:    B P D
verse:    B P D RL RR
chorus:   B P D RL RR SP
verse:    B P D RL RR
chorus:   B P D RL RR SP
BRIDGE:   B P only            (radical strip)
chorus:   B P D RL RR SP
outro:    B P D
```
**Touchstones:** Many pop-rock songs, some metal breakdowns. **Pairs with:** Rock, Djent.

### How to pick an arrangement archetype

1. **Match to mood:**
   - **Constant energy** → 8 (Hit and run)
   - **Quiet-loud contrast** → 2 (Hit and breathe)
   - **Patient build** → 1 (Slow build), 7 (Hisaishi swell)
   - **Climax late** → 4 (Mogwai inversion)
   - **Single harmonic idea** → 6 (Drone build)
   - **Layers always growing** → 3 (Layer stack)
   - **Counter-intuitive / surprise** → 9 (Verse breathing)
   - **Breakdown drama** → 10 (Bridge as breakdown)
2. **Don't repeat** the same archetype on consecutive songs.
3. **These are starting points** — adapt the per-section role plan. If a verse needs SURGE for an extra second of warmth, add it. The catalog is a vocabulary, not a constraint.
4. **Match to style pack:**
   - Rock → 1, 2, 5, 8, 9
   - Cinematic → 4, 6, 7
   - Spanish/Phrygian → 8, 10 (energetic) or 2 (dramatic contrast)
   - Post-rock → 4, 6
   - Djent → 3, 8, 10
   - Synthwave → 3
   - Jazz-funk → 7 (ballad), 8 (groovier), 9
   - Math rock → 6 (drone), 4 (post-rock inversion)

## What the script writes to the template

It copies the Reaper template specified by `template_path` in `config.json` (see the project README), overrides the tempo, adds region markers, and inserts MIDI items on these tracks:

| Role         | Track in template      | What's written                                |
|--------------|------------------------|-----------------------------------------------|
| Bass         | `BASS`                 | Root-note bassline, splits long chords in two |
| Drums        | `DRUMS`                | GM kit (kick/snare/hat), crash at section start |
| Chord pad    | `PIANO`                | Open voicings, sustained for full chord duration |
| Rhythm chord | `MIDI-RHY-GTR-L`       | Root+fifth power chords; rhythm pattern from `feel` |
| Rhythm chord | `MIDI-RHY-GTR-R`       | Same as L, offset 1/8 beat for stereo width   |
| Clean guitar (picked) | `MIDI-CLEAN`   | Fingerpicked 8th-note arpeggio cycling through chord tones. For ballads, cinematic, math rock — replaces rhythm guitars. |
| Strum guitar | `MIDI-STRUM`            | Staggered chord strum — each chord tone offset ~40ms (pick rake low-to-high), velocity tapers (72→70→68→66). Patch is voiced for strumming (warmer than the picked clean), so use this rather than `clean` when you want strummed accompaniment. |
| Lead guitar  | `MIDI-LEAD`             | Composed melodic line per section (`melody` field). Plays once across the section by default; loops every N beats if `melody_loop_beats` is set (riff mode). Use to give a section its melodic identity / hook line — the user uses it as a starting point for their own lead playing. |
| Chugg guitar | `MIDI-CHUGG`            | Palm-muted low-octave rhythm on the chord root (`chugg` field picks a pattern). Track has ReaPitch loaded so the user can drop-tune to taste. Patterns: `straight-16ths`, `gallop`, `polyrhythm-3`, `syncopated`, `halftime`, `single-hit`, `open-8ths`. |
| Synth pad bed | `SURGE XT`            | Soft sustained chord-tone bed in mid-range (octave 3, vel 60). Long sustain (chord_beats + 1.5–2.5 of overhang) so the synth's release tail blurs into the next chord. **Opt-in only** — use under arpeggios when the song needs harmonic glue. |

**Regions:** one per form entry, named `<section>-<n>` (e.g. `verse-1`, `chorus-2`). Use for looping, region-render, or the region matrix.

## Fill mode

Composer can also drop a section INTO an existing Reaper project. The user marks N bars of silence with a region literally named `COMPOSER`, closes Reaper, and asks Claude to fill it. Claude analyzes what's around the gap, composes a fitting section, and the script writes MIDI items into the .RPP in place.

### When to use

Trigger phrases — recognize any of these as fill-mode requests:

- "fill the COMPOSER region in `<path>`"
- "fill the gap in this song"
- "compose for the COMPOSER region with `<brief>`"
- "do a key mod in the empty section"
- "give me a bridge / breakdown / transition for this song"

How it differs from `compose`: no `<output_dir>`, no new files in `~/Documents/MIDI-SONGS/...`. The fill operation edits the .RPP in place. The user must close Reaper before invoking (the script rewrites the file).

### Workflow

```bash
# 1. Analyze surrounding context.
python3 ~/.claude/skills/composer/composer.py analyze <project.RPP>
# → emits a JSON dump to stdout: tempo, time_sig, region length in bars,
#   prev_context sections (chord progressions, feel, scales, move),
#   post_context sections, last_chord_before_region, first_chord_after_region,
#   neighborhood_tracks (which tracks are active in surrounding bars).

# 2. Read the JSON. Decide fill content (see "Brief interpretation" below).

# 3. Write a fill spec.
# Spec shape = one section + roles. NO tempo (project tempo is used).
# Total beats MUST equal the region length.

# 4. Run fill.
python3 ~/.claude/skills/composer/composer.py fill /tmp/composer_fill_spec.json <project.RPP>
# → writes MIDI items into matching tracks at the COMPOSER region's time range,
#   updates the project's NOTES block with a COMPOSER-FILL section entry,
#   refreshes the EXTSTATE breadcrumb so the next analyze sees the new section.

# 5. Tell the user to reopen the .RPP in Reaper.
```

### Fill spec format

```json
{
  "roles": ["bass", "pad", "clean", "drums"],
  "feel": "halftime",
  "drums": "halftime",
  "voicing": "power",
  "skip_roles": [],
  "melody": [[0.0, "E4", 4.0]],
  "melody_loop_beats": null,
  "chugg": null,
  "scales": "E Aeolian (E-F#-G-A-B-C-D)",
  "move": "halftime breakdown — Em pedal with sus voicings",
  "chords": [
    {"name": "Em9",  "beats": 8},
    {"name": "Cmaj7","beats": 8},
    {"name": "Am7",  "beats": 8},
    {"name": "B7",   "beats": 8}
  ]
}
```

Validation: `sum(c.beats for c in chords) == region_length_sec * tempo / 60`. The script errors out if these don't match — fix the chord progression to align with the region's beat count.

### Brief interpretation — three flavors

The user's request will land in one of three buckets. Recognize which and act accordingly.

**A. No brief / "fill the gap"** — Mode A. Default to a transition that fits the surrounding context:

- If prev is verse + post is chorus → write a pre-chorus build / lift.
- If prev is chorus + post is chorus → write a bridge (parallel-minor, IV-as-tonic, or modal-mixture move).
- If prev is chorus + post is verse → write a breather (halftime breakdown, drop to bass+pad).
- If prev is intro + post is verse → write a second intro variation (add a layer or two).

If genuinely ambiguous between two strong options, ask ONE question: *"Should this fill stay in `<current_key>` or modulate? And should it be a build or a breather?"*

**B. Vibe-textural brief** — "65bpm arpeggiated guitars," "atmospheric," "sparser," "moody."

Keep the harmonic anchors (`last_chord_before_region` + `first_chord_after_region` as bookends), but pick `feel` + `roles` to match the texture words:

- "arpeggiated guitars" → `roles: [clean]` (optionally `+ synth_pad` for harmonic glue).
- "65bpm-feel" in a 135-BPM project → `feel: "halftime"` + chord durations doubled (8 beats per chord instead of 4).
- "atmospheric" → drop drums + rhy guitars → `roles: [bass, pad, synth_pad]`.
- "drop to silence" → `roles: [pad]` only, sparse feel.

The harmonic content can stay diatonic (you're decorating the texture, not the chords).

**C. Harmonic brief** — "Andalusian cadence," "key mod to F#m," "ii-V-I in C," "bVI-bVII-i lift," "do a key mod here," "borrow chords from parallel minor."

The chord progression is dictated. Pick the feel from surrounding context. Critical: if the brief specifies a key change, **end the fill with a pivot or leading-tone chord that lands smoothly on `first_chord_after_region`** — otherwise the modulation lands awkwardly when the song re-enters the next section.

Examples:
- "key mod to F#m" with `first_chord_after = Em9` → the fill should NOT just end in F#m; it should end on something that resolves into Em9 (e.g. a B7 leading-tone), so the song "returns home" cleanly.
- "Andalusian cadence" → `i — bVII — bVI — V7` in the appropriate key (`Em — D — C — B7` in E, transpose to context key).

### Ambiguous brief

If the brief is short ("make it interesting," "do something cool here") and you cannot reasonably pick between options, ask ONE question: "modulate or stay in `<current_key>`? Build or breather?"

### Transition idioms catalog

Pick one when composing the fill. Each line: name — when to use — example in Em (transpose to context key).

**Modulations** (for harmonic briefs that request a key change):
- **Pivot chord** — find a chord shared between source and target keys; use it as the pivot. *Em → G major: pivot through G (vi in Em, I in G).*
- **Direct / abrupt** — no preparation, just land in the new key on bar 1 of the post section. *Best for surprise drops.*
- **Common-chord (modal pivot)** — borrow a chord that exists in both keys' modes. *Em → Am: pivot through Am (iv in Em, i in Am).*
- **Chromatic mediant** — modulate by a third (major third up = up a flat, minor third up = up a sharp). *Em → Gm or Em → Cm.*
- **Phrygian-dom V from new key** — set up the new key with its V7 dominant. *Em → Am: end fill with E7 (Phrygian-dom V of Am).*
- **Sequential cuts** (Dream Theater) — repeat the same melodic figure transposed up/down each bar.

**Bridges** (for fills between two choruses or between verse and chorus when contrast is wanted):
- **Parallel-minor pull** — Em song → E major bridge, or A major song → A minor bridge. Same root, swap mode.
- **Parallel-major lift** — Bm song → B major bridge. The 6 chord (originally minor) becomes major, lifts the whole section.
- **IV-as-tonic Lydian** — in Em, treat A as the new tonic for the bridge with Amaj7-B/A-G#m-Amaj7. Briefly explores Lydian.
- **bVI surprise** — drop a Cmaj7 (bVI in Em) for the whole bridge, hover on it. Em → Cmaj7 vamp.
- **Halftime-same-chords bridge** — reuse the chorus chord progression but at halftime feel. The dynamic shift IS the bridge.

**Pre-chorus lifts** (for fills between verse and chorus when build is wanted):
- **IV-V-IV-V** — simplest functional buildup. In Em: Am-B7-Am-B7.
- **IV-V-vi-V** — Paramore lift. In Em: Am-B7-Cmaj7-B7.
- **Chromatic walk-up to new key** — bass walks up by half-steps, lands on first_chord_after.
- **bVII-IV-V launch** — in Em: D-Am-B7. Bright, anthemic.

**Breakdowns** (for fills where the song needs to breathe before returning):
- **Strip to bass+pad** — `roles: [bass, pad]` only. Same chords, half the layers.
- **Drone on tonic with halftime drums** — sit on Em9 for 8 bars, halftime feel.
- **Sus-hang into next section** — end the fill on Esus2 or Esus4 (unresolved), let the post section's first chord resolve.

**Ramps / escalations** (for fills that explicitly need to climb):
- **Chromatic walk-up** — `i → bii° → ii° → biii° → iii` style escalation.
- **Ascending bass line** — bass walks up a scale toward `first_chord_after_region`'s root.
- **Accelerating chord rhythm** — chord every 8 beats → 4 → 2 → 1, terminating on first_chord_after.

### Track-selection rules

- **Mode A (no brief)** → mirror `neighborhood_tracks` from analyze output. Continuity is the value.
- **Mode B textural** → override deliberately to match the texture words. "Arpeggiated guitars" = `[clean]`, optionally + `synth_pad`. "Drop to bass and pad" = `[bass, pad]`.
- **Mode B harmonic** → use the same role set as surrounding sections so the new harmony feels integrated. The key mod IS the surprise; don't compound it with a texture surprise unless asked.

### Re-running fill (variations)

If the user doesn't like the result and wants to try again:

1. Tell the user to manually delete the inserted items in Reaper (search for items named `composer-fill-*` and delete).
2. Re-invoke fill with a new spec. The script overwrites the COMPOSER-FILL entry in NOTES and the `composer-fill` section in EXTSTATE — no accumulation of dead variations. (MIDI items would accumulate without manual delete, so be sure step 1 happened.)

## Style notes

- **Bassline-first thinking.** Sketch the bass shape (stepwise descent? pedal?) before picking chords.
- **Inversions are your friend.** `G/B`, `C/E`, `Em/G` make the bass move smoothly.
- **Color tones over plain triads.** Default to `Em9`, `Cmaj7`, `Am7`. Plain triads land best at resolution moments.
- **The chorus is the destination.** Brighter, simpler, less tension.
- **Dynamics via `feel` and density.** A sparse intro and halftime verse make the driving chorus hit harder. Lean on `feel` for dynamics, not chord changes.

## Limitations

- No tempo or time-signature changes mid-song.
- Drum patterns are fixed bar-level — no fills, breakdowns, or builds.
- Chord parsing is strict — `C9sus4`, `Cmaj7#11`, and similar will error.
- No automation, no per-note velocity shaping beyond pattern defaults.
