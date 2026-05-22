# Composer skill — external references

This file is a curated bibliography for the moves in SKILL.md. When you want to dig deeper on a specific move, follow the URL here.

## Plini
- "Plini Shows You How to Solo Over Prog Chord Progressions" — Guitar World — https://www.guitarworld.com/lessons/plini-shows-you-how-to-solo-over-prog-chord-progressions

## Polyphia
- "Playing God" — Hooktheory analysis — https://www.hooktheory.com/theorytab/view/polyphia/playing-god
- "G.O.A.T." — Hooktheory — https://www.hooktheory.com/theorytab/view/polyphia/goat

## Animals as Leaders
- "A Different Breed" — Premier Guitar — https://www.premierguitar.com/artists/animals-as-leaders-a-different-breed
- AAL theory discussion — Sevenstring forum — https://sevenstring.org/threads/animals-as-leaders-theory.188901/

## Dream Theater
- "Through Her Eyes" — Ultimate Guitar — https://tabs.ultimate-guitar.com/tab/dream-theater/through-her-eyes-chords-1130472
- "Hollow Years" — Hooktheory — https://www.hooktheory.com/theorytab/view/dream-theater/hollow-years

## Hans Zimmer
- "Interstellar Main Theme" analysis — Electric Guitar Composing — https://www.electricguitarcomposing.com/blog/interstellar-by-hans-zimmer-why-it-has-an-emotional-and-addictive-chord-progression
- "Time" (Inception) — Hooktheory — https://www.hooktheory.com/theorytab/view/hans-zimmer/time

## Joe Hisaishi
- Honors thesis on Hisaishi harmonic language — SUNY — https://soar.suny.edu/bitstream/handle/20.500.12648/1506/Laaninen_Honors.pdf
- "Studio Ghibli Music Explained by a Jazz Pianist" — YesChat — https://www.yeschat.ai/blog-studio-ghibli-music-explained-by-a-jazz-pianist-54136

## Math rock / Midwest emo
- FACGCE tuning guide — Ragajunglism — https://ragajunglism.org/tunings/menu/math-rock-f/
- FACGCE comprehensive guide — Background Animal — https://www.backgroundanimal.com/articles/facgce-guitar-tuning-comprehensive-guide
- Math rock guitar tunings — GTDB — https://gtdb.org/egdbad
- Odd time signatures explained — Chromelodeon — https://chromelodeon.com/guides/odd-time-signatures-explained/

## Jazz / fusion
- Kenny Barron chord voicing — Jazz Tutorial — https://jazztutorial.com/articles/the-kenny-barron-chord-voicing
- Backdoor progression — Learn Jazz Standards — https://www.learnjazzstandards.com/blog/learning-jazz/jazz-theory/backdoor-progression/
- Coltrane changes — The Jazz Piano Site — https://www.thejazzpianosite.com/jazz-piano-lessons/jazz-chord-progressions/coltrane-changes/

## Neo-soul / R&B
- 10 distinctive R&B chord progressions — Orange Candy Music — https://orangecandymusic.com/10-distinctive-rnb-chord-progressions-every-producer-should-know/

## Power metal / neoclassical
- Power Metal Soloing (Timo Tolkki) — Guitar MasterClass — https://www.guitarmasterclass.net/ls/Power-Metal-Soloing-Timo-Tolkki/

## Djent / Periphery
- Periphery / Misha Mansoor lesson — Premier Guitar — https://www.premierguitar.com/lessons/obsessive-progressive-periphery

## Frank Zappa / Lydian theory
- "A New Lydian Theory for Frank Zappa's Modal Music" — Music Theory Spectrum — https://academic.oup.com/mts/article-abstract/36/1/146/2748318

## General chord progressions
- GMC Forum article — "Chord Progressions Explained (modern Rock, metal, etc)" (shared by user 2026-05-14)

## Local MIDI corpora *(on disk, not baked into the skill — available for future mining)*

User has a curated `_MIDI PACKS` directory at `~/Documents/_MIDI PACKS/` with ~144k MIDI files. Only the SHLD Minor + Modal labeled progressions are baked into the skill (see `data/shld_mood_bank.json`). The rest are reference material that future iterations could mine if a gap appears:

- **`SHLD/progressions-20251006/Major/`** — 4,380 major-key progressions, same naming scheme. Skipped for now (genre mismatch with melodic-rock/cinematic/fusion preference) but mineable if a Major-key project pack ever opens up.
- **`Chords/Queen_The_Beatles/`** — Real-song transcriptions of Queen & Beatles in 12 transposed keys + Original_Key. Filenames carry song/section/chord-sequence/BPM/key. **Not baked in** because the harmonic vocabulary (I-vi-IV-V, I-V-vi-IV) directly conflicts with the Rock pack's FORBIDDEN list. Useful as a reference for verified pop-rock SECTION-FORM data (intro/verse/chorus structure of well-known songs) if that ever becomes a need.
- **`Niko 2024/Niko_Essentials_2024_/`** — 12 keys × `Chord Expansion` / `Chord Rhythms` / `Genre_Based_Chords` / `Melodies_Piano_Intros`. Pop/EDM-oriented voicings. Skip for melodic-rock/fusion work; consider if a pop-leaning project appears.
- **`Niko 2024/Bonuses/Top 100 Progressions/`** — Curated 100 progressions across keys, pop/EDM-oriented. Same caveat as above.
- **`Chords/SOUND7-Free-Midi-Chords/`** + **`Chords/Unison Free Mini MIDI Pack/`** — Smaller free packs, 12 keys each, pop-leaning. Reference quality.
- **`Niko 2024/Bonuses/Piano Intros/`** + **`Gorgeous/`** — Ambient/cinematic piano material. Mineable for the Cinematic pack if subschool B (Yiruma-style) needs more reference patterns.

If you mine any of these into the skill, follow the same pattern as `data/shld_mood_bank.json`: parse filenames, dedupe, write a JSON sidecar, add a SKILL.md section pointing at it, screen against the FORBIDDEN list.

## Composition quality framework
- Hooktheory "Chord and Melody Metrics" — https://www.hooktheory.com/song-metrics/about — the 5-axis quality framework documented in SKILL.md's "Composition quality metrics" section: Chord Complexity, Melodic Complexity, Chord-Melody Tension, Chord Progression Novelty, Chord Bass Melody. Each metric links to a curated list of exemplar songs from their TheoryTab database.
- Hooktheory stable/unstable scale degrees — https://www.hooktheory.com/support/musicreference?concept=music-concepts-stable-unstable-scale-degree — the canonical "is this melody note IN the current chord?" reference. Backs the chord-melody tension axis.
- Hooktheory TheoryTab — https://www.hooktheory.com/theorytab — searchable database of chord+melody breakdowns for thousands of popular songs. Browse the Bass Melody / Chord Complexity exemplar lists for new moves worth absorbing.
