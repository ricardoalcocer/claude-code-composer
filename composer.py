#!/usr/bin/env python3
"""
composer.py — generates MIDI + a Reaper .RPP from a JSON spec.

Reads a spec on stdin or from argv[1], writes outputs to argv[2] (a directory).
No external dependencies.
"""

import base64
import json
import os
import re
import struct
import sys
import textwrap
import uuid
from pathlib import Path

PPQN = 960

SKILL_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SKILL_DIR / "config.json"
CONFIG_EXAMPLE_PATH = SKILL_DIR / "config.example.json"


def load_template_path():
    """Resolve the Reaper template path from config.json.

    config.json lives next to composer.py and is gitignored. If it's missing,
    print a clear setup hint and exit. The path supports `~` expansion.
    """
    if not CONFIG_PATH.exists():
        sys.stderr.write(
            f"composer: missing {CONFIG_PATH.name} next to composer.py.\n"
            f"  cp {CONFIG_EXAMPLE_PATH.name} {CONFIG_PATH.name}\n"
            f"  then edit {CONFIG_PATH.name} to point at your Reaper template.\n"
        )
        sys.exit(2)

    with open(CONFIG_PATH) as f:
        cfg = json.load(f)

    raw = cfg.get("template_path")
    if not raw:
        sys.stderr.write(
            f"composer: {CONFIG_PATH.name} is missing the 'template_path' key.\n"
        )
        sys.exit(2)

    template = Path(raw).expanduser()
    if not template.is_absolute():
        template = SKILL_DIR / template
    if not template.exists():
        sys.stderr.write(
            f"composer: template not found at {template}.\n"
            f"  Edit 'template_path' in {CONFIG_PATH} to point at your .RPP template.\n"
        )
        sys.exit(2)
    return template

ALL_ROLES = ("bass", "pad", "rhy_l", "rhy_r", "clean", "strum", "lead", "chugg", "synth_pad", "drums")
DEFAULT_ROLES = ("bass", "pad", "rhy_l", "rhy_r", "drums")  # rock default; clean, strum, lead, chugg, synth_pad are opt-in.

# Track NAME (as it appears in the .RPP) -> role in the composer.
TRACK_TARGETS = {
    "BASS": "bass",
    "DRUMS": "drums",
    "PIANO": "pad",
    "MIDI-RHY-GTR-L": "rhy_l",
    "MIDI-RHY-GTR-R": "rhy_r",
    "MIDI-CLEAN": "clean",
    "MIDI-STRUM": "strum",
    "MIDI-LEAD": "lead",
    "MIDI-CHUGG": "chugg",
    "SURGE XT": "synth_pad",
}

# Chugg rhythm patterns at the bar level: (offset_beats, duration_beats, vel_delta).
# Operates on the current chord's root pitch (low octave). Short durations = palm-mute feel.
CHUGG_PATTERNS = {
    "straight-16ths": [
        (0.0,  0.15,  +5), (0.25, 0.10, -10), (0.5,  0.15,   0), (0.75, 0.10, -10),
        (1.0,  0.15,  +3), (1.25, 0.10, -10), (1.5,  0.15,   0), (1.75, 0.10, -10),
        (2.0,  0.15,  +3), (2.25, 0.10, -10), (2.5,  0.15,   0), (2.75, 0.10, -10),
        (3.0,  0.15,  +3), (3.25, 0.10, -10), (3.5,  0.15,   0), (3.75, 0.10, -10),
    ],
    "gallop": [
        # Iron Maiden 16th-16th-8th gallop pattern
        (0.0,  0.10,  +5), (0.25, 0.10,  -5), (0.5,  0.20,   0),
        (1.0,  0.10,  +3), (1.25, 0.10,  -5), (1.5,  0.20,   0),
        (2.0,  0.10,  +5), (2.25, 0.10,  -5), (2.5,  0.20,   0),
        (3.0,  0.10,  +3), (3.25, 0.10,  -5), (3.5,  0.20,   0),
    ],
    "polyrhythm-3": [
        # Every 3rd 16th over 4/4 — Meshuggah-style phasing tension.
        (0.0,  0.15,  +5), (0.75, 0.15,   0), (1.5,  0.15,   0),
        (2.25, 0.15,  +3), (3.0,  0.15,   0), (3.75, 0.15,  -3),
    ],
    "syncopated": [
        # Periphery-style breakdown — hits on 1 and "and of 2" only.
        (0.0,  0.30,  +7),
        (1.5,  0.30,  +3),
    ],
    "halftime": [
        # Doom/sludge — beats 1 and 3 only, sustained.
        (0.0,  0.50,  +7),
        (2.0,  0.50,  +3),
    ],
    "single-hit": [
        # One chord-root hit per bar — for accents or punctuation.
        (0.0,  0.40,  +7),
    ],
    "open-8ths": [
        # Less aggressive — 8ths with more ring, useful in mid-tempo rock not pure metal.
        (0.0,  0.30,  +5), (0.5,  0.25,  -3),
        (1.0,  0.30,  +3), (1.5,  0.25,  -3),
        (2.0,  0.30,  +5), (2.5,  0.25,  -3),
        (3.0,  0.30,  +3), (3.5,  0.25,  -3),
    ],
    "clave-3-2": [
        # Son clave 3-2 — TWO-BAR pattern (the chugg loop adapts its period).
        # 3-side first: bar-1 beat 1, "and of 2", beat 4. Then 2-side: bar-2 beat 2, beat 3.
        # Fires the chord root at low octave like a wood-block clave under the band.
        (0.0,  0.20,  +5),   # bar 1, beat 1
        (1.5,  0.20,  +0),   # bar 1, "and of 2"
        (3.0,  0.20,  +3),   # bar 1, beat 4
        (5.0,  0.20,  +3),   # bar 2, beat 2  (4 + 1)
        (6.0,  0.20,  +0),   # bar 2, beat 3  (4 + 2)
    ],
    "clave-2-3": [
        # Son clave 2-3 — reversed: 2-side first, 3-side second. The "Cuban son" cousin.
        (1.0,  0.20,  +3),   # bar 1, beat 2
        (2.0,  0.20,  +0),   # bar 1, beat 3
        (4.0,  0.20,  +5),   # bar 2, beat 1  (4 + 0)
        (5.5,  0.20,  +0),   # bar 2, "and of 2"  (4 + 1.5)
        (7.0,  0.20,  +3),   # bar 2, beat 4  (4 + 3)
    ],
}

# Pitch-name → MIDI-number parser (e.g., "E3" → 52, "F#4" → 66, "Ab2" → 44).
_PITCH_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_PITCH_RE = re.compile(r"^([A-G])([#b]?)(-?\d+)$")


def parse_pitch(name):
    """Convert pitch name (e.g., 'E3', 'F#4', 'Ab2') to a MIDI note number."""
    m = _PITCH_RE.match(name.strip())
    if not m:
        raise ValueError(f"bad pitch name: {name!r}")
    pc = _PITCH_PC[m.group(1)]
    if m.group(2) == "#":
        pc += 1
    elif m.group(2) == "b":
        pc -= 1
    octave = int(m.group(3))
    return pc + 12 * (octave + 1)


def chugg_pitch(root_pc):
    """Choose the lowest natural octave for the chord root on a standard E-tuned 6-string.
    Returns MIDI note in the E2-D#3 range. Use ReaPitch on the track to retune down further."""
    base = 36 if root_pc >= 4 else 48
    return root_pc + base

# Rhythm-guitar patterns at the bar level: (offset_beats, duration_beats, vel_delta).
# Each pattern repeats every 4 beats; truncated against the current chord's span.
# vel_delta adds to base velocity (~84-88), range ~76 to ~95 — gives real dynamic shape.
FEEL_BAR_PATTERNS = {
    "driving": [
        # Stab-ring alternation: downbeats ring full, upbeats palm-mute chug.
        # Velocity gradient: beat 1 (loudest) > beat 3 > beat 2 > beat 4. Standard rock dynamics.
        (0.0,  0.45,  +7),   # beat 1: strongest accent, full ring
        (0.5,  0.20,  -8),   # 1-and: palm-mute chug
        (1.0,  0.45,  +3),   # beat 2: medium accent, ring
        (1.5,  0.20, -10),   # 2-and: chug
        (2.0,  0.45,  +5),   # beat 3: strong accent, ring
        (2.5,  0.20,  -8),   # 3-and: chug
        (3.0,  0.45,  +1),   # beat 4: medium accent, ring
        (3.5,  0.20, -12),   # 4-and: quietest chug (pickup tail)
    ],
    "sparse":   [(0.0, 3.8, -8)],
    "halftime": [
        (0.0, 1.8, +5),   # beat 1: full and proud
        (2.0, 1.8, +1),   # beat 3: slightly less
    ],
    "pushed": [
        # Syncopated push — the offbeats are LOUDER than the downbeats (where the lift lives).
        (0.0, 0.45, +3),
        (1.5, 0.40, +5),   # the push on 2-and
        (2.0, 0.45, +1),
        (3.5, 0.40, +5),   # the push on 4-and
    ],
    "skank": [
        # Reggae skank — chord chops ONLY on the upbeats (and-of-2, and-of-4).
        # The silent downbeats ARE the sound. Choked short duration (no ring) so it
        # reads as a chop, not a strum. Apply to clean/rhy guitars; swap to a clean
        # tone VST on those tracks if you want authentic reggae.
        (1.5, 0.20, +5),   # and-of-2
        (3.5, 0.20, +5),   # and-of-4
    ],
    "montuno": [
        # Salsa montuno — syncopated 8th-note rhythm guitar comp. The primary
        # placement for montuno is the `pad` (piano) role, which handles montuno
        # specially as a chord-tone arpeggio; this pattern is for rhy_l/rhy_r if
        # you want guitar chops doubling the figure (Steve Khan / "Eyewitness").
        (0.5, 0.25, +0),   # and-of-1
        (1.0, 0.25, +5),   # beat 2 (accent)
        (1.5, 0.25, -3),   # and-of-2
        (2.5, 0.25, +0),   # and-of-3
        (3.0, 0.25, +5),   # beat 4 (accent)
        (3.5, 0.25, -3),   # and-of-4
    ],
    "locked-16": [
        # J-fusion (Casiopea / T-Square / Naniwa Express) tight 8th-note pocket.
        # Choked short durations — percussive, not strummy. Upbeats (the "ands")
        # are LOUDER than downbeats — that's the Japanese fusion lift, and it
        # inverts the rock-default accent pattern (which puts the weight on 1 and 3).
        # Pairs with the j-fusion-kit drum pattern (16th hi-hat under it).
        (0.0, 0.20,  +0),   # beat 1: medium, choked
        (0.5, 0.22,  +5),   # and-of-1: ACCENT (the lift)
        (1.0, 0.20,  -2),   # beat 2: medium
        (1.5, 0.22,  +5),   # and-of-2: ACCENT
        (2.0, 0.20,  +0),   # beat 3: medium
        (2.5, 0.22,  +5),   # and-of-3: ACCENT
        (3.0, 0.20,  -2),   # beat 4: medium
        (3.5, 0.22,  +5),   # and-of-4: ACCENT
    ],
}

GM_DRUMS = {"kick": 36, "snare": 38, "chat": 42, "ohat": 46, "crash": 49, "ride": 51,
            # Latin / world percussion (GM standard pitches) — used by one-drop, latin-fusion.
            # Swap the drum-track plugin to a GM-compliant kit (BFD, AD2, MT Power Drum) to hear them.
            "cowbell": 56, "bongo_hi": 60, "bongo_lo": 61, "conga_mute": 62,
            "conga_open": 63, "conga_lo": 64, "timbale_hi": 65, "timbale_lo": 66,
            "claves": 75, "guiro_short": 73, "guiro_long": 74}

DRUM_BAR_PATTERNS = {
    "none": [],
    "basic-rock": [
        (0.0, "kick", 100), (2.0, "kick", 95),
        (1.0, "snare", 95), (3.0, "snare", 95),
        (0.0, "chat", 78), (0.5, "chat", 68), (1.0, "chat", 78), (1.5, "chat", 68),
        (2.0, "chat", 78), (2.5, "chat", 68), (3.0, "chat", 78), (3.5, "chat", 68),
    ],
    "halftime": [
        (0.0, "kick", 100),
        (2.0, "snare", 95),
        (0.0, "chat", 78), (0.5, "chat", 68), (1.0, "chat", 78), (1.5, "chat", 68),
        (2.0, "chat", 78), (2.5, "chat", 68), (3.0, "chat", 78), (3.5, "chat", 68),
    ],
    "four-on-floor": [
        (0.0, "kick", 95), (1.0, "kick", 95), (2.0, "kick", 95), (3.0, "kick", 95),
        (1.0, "snare", 90), (3.0, "snare", 90),
        (0.0, "chat", 78), (0.5, "chat", 68), (1.0, "chat", 78), (1.5, "chat", 68),
        (2.0, "chat", 78), (2.5, "chat", 68), (3.0, "chat", 78), (3.5, "chat", 68),
    ],
    "one-drop": [
        # Classic reggae one-drop: kick AND snare together on beat 3 (the "drop").
        # Beats 1, 2, 4 have no kick — the silence is the groove. Hi-hat 8ths ride underneath.
        (2.0, "kick", 95),
        (2.0, "snare", 100),
        (0.0, "chat", 68), (0.5, "chat", 58), (1.0, "chat", 68), (1.5, "chat", 58),
        (2.0, "chat", 68), (2.5, "chat", 58), (3.0, "chat", 68), (3.5, "chat", 58),
    ],
    "latin-fusion": [
        # Standard kit + cowbell + conga — bridges salsa percussion vocabulary into
        # a jazz-fusion drummer's frame (think Steve Gadd doing Latin, not a salsa charanga).
        (0.0, "kick", 100), (2.0, "kick", 90),
        (1.0, "snare", 92), (3.0, "snare", 92),
        (0.0, "chat", 70), (0.5, "chat", 60), (1.0, "chat", 70), (1.5, "chat", 60),
        (2.0, "chat", 70), (2.5, "chat", 60), (3.0, "chat", 70), (3.5, "chat", 60),
        # Cowbell on every beat — cáscara-style timekeeping
        (0.0, "cowbell", 85), (1.0, "cowbell", 78),
        (2.0, "cowbell", 85), (3.0, "cowbell", 78),
        # Open conga on the "ands" of 2 and 4 — Latin offbeat push
        (1.5, "conga_open", 80), (3.5, "conga_open", 80),
    ],
    "j-fusion-kit": [
        # J-fusion drum kit — Akira Jimbo (Casiopea) / Hiroyuki Noritake (T-Square) style.
        # Kick on 1, "and of 2," and 3 (slight syncopation, the kick lift). Snare 2 + 4.
        # Hi-hat 16ths underneath — the locked-16 feel needs this density.
        (0.0, "kick", 95), (1.5, "kick", 85), (2.0, "kick", 90),
        (1.0, "snare", 95), (3.0, "snare", 95),
        # 16th-note hi-hat — open enough to breathe, tight enough to drive
        (0.0, "chat", 72), (0.25, "chat", 60), (0.5, "chat", 68), (0.75, "chat", 60),
        (1.0, "chat", 72), (1.25, "chat", 60), (1.5, "chat", 68), (1.75, "chat", 60),
        (2.0, "chat", 72), (2.25, "chat", 60), (2.5, "chat", 68), (2.75, "chat", 60),
        (3.0, "chat", 72), (3.25, "chat", 60), (3.5, "chat", 68), (3.75, "chat", 60),
    ],
}

FEEL_TO_DRUMS = {
    "sparse":    "halftime",
    "driving":   "basic-rock",
    "halftime":  "halftime",
    "pushed":    "basic-rock",
    "skank":     "one-drop",
    "montuno":   "latin-fusion",
    "locked-16": "j-fusion-kit",
}

NOTE_NAMES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
              "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
              "A#": 10, "Bb": 10, "B": 11, "Cb": 11}

CHORD_QUALITIES = {
    "":      [0, 4, 7],
    "m":     [0, 3, 7],
    "dim":   [0, 3, 6],
    "aug":   [0, 4, 8],
    "sus2":  [0, 2, 7],
    "sus4":  [0, 5, 7],
    "7":     [0, 4, 7, 10],
    "maj7":  [0, 4, 7, 11],
    "m7":    [0, 3, 7, 10],
    "mmaj7": [0, 3, 7, 11],
    "m7b5":  [0, 3, 6, 10],
    "dim7":  [0, 3, 6, 9],
    "6":     [0, 4, 7, 9],
    "m6":    [0, 3, 7, 9],
    "add9":  [0, 4, 7, 14],
    "madd9": [0, 3, 7, 14],
    "9":     [0, 4, 7, 10, 14],
    "maj9":  [0, 4, 7, 11, 14],
    "m9":    [0, 3, 7, 10, 14],
}

CHORD_RE = re.compile(r"^([A-G][b#]?)(.*?)(?:/([A-G][b#]?))?$")


def parse_chord(name):
    """Returns (root_pc, intervals, bass_pc). bass_pc=None means use root."""
    m = CHORD_RE.match(name.strip())
    if not m:
        raise ValueError(f"can't parse chord: {name}")
    root, qual, bass = m.group(1), m.group(2), m.group(3)
    qual = qual.strip()
    if qual not in CHORD_QUALITIES:
        raise ValueError(f"unknown quality {qual!r} in {name}")
    root_pc = NOTE_NAMES[root]
    intervals = CHORD_QUALITIES[qual]
    bass_pc = NOTE_NAMES[bass] if bass else None
    return root_pc, intervals, bass_pc


# ---------- voicing generators ----------

def voice_pad(root_pc, intervals, bass_pc, octave=4):
    """Orchestral spread voicing — not a piano-stack. Wide range, with a 10th gap-filler
    between bass and the chord stack, creating soundscape rather than crystalline piano.
    Bass at octave 2 (or slash bass) → 10th at octave 3 → full chord at octave 4."""
    base = 12 * (octave + 1)  # 60 = C4
    notes = []
    # Bass note at octave 2 — slash bass or root, given depth so it doesn't crowd the chord stack
    if bass_pc is not None:
        notes.append(bass_pc + base - 24)
    else:
        notes.append(root_pc + base - 24)
    # 10th interval (the chord's second tone, an octave above bass) — the "warmth" voice
    # that bridges the gap between bass and the chord stack. The single most important
    # spread-voicing trick for making piano-driven pads sound orchestral, not piano-student.
    if len(intervals) > 1:
        notes.append(root_pc + base - 12 + intervals[1])
    # Full chord stack at octave 4 (closed position)
    for iv in intervals:
        notes.append(root_pc + base + iv)
    # Root doubled at octave 5 for top sparkle on richer chords (maj9/m9/9 etc.)
    if len(intervals) >= 5:
        notes.append(root_pc + base + 12)
    return sorted(set(notes))


def voice_bass(root_pc, intervals, bass_pc, octave=2):
    base = 12 * (octave + 1)
    pc = bass_pc if bass_pc is not None else root_pc
    return [pc + base]


def voice_synth_pad(root_pc, intervals, bass_pc, octave=3):
    """SURGE XT synth pad — wide modal voicing across two octaves. Chord stack at
    octave 3, with root and 5th doubled at octave 4 for synth-pad fullness. No bass
    (BASS track has it). Designed for soundscape thickness, not piano-style stack."""
    base = 12 * (octave + 1)  # 48 = C3
    notes = [root_pc + base + iv for iv in intervals]
    # Octave doublings — root and 5th up an octave for the synth-pad "bloom"
    notes.append(root_pc + base + 12)
    if 7 in intervals:
        notes.append(root_pc + base + 12 + 7)
    return sorted(set(notes))


def voice_clean(root_pc, intervals, bass_pc, octave=3):
    """Clean-guitar chord tones for arpeggiation/strumming.
    Ignores slash bass (the BASS track has it) and uses chord tones at guitar-clean range."""
    base = 12 * (octave + 1)
    return [root_pc + base + iv for iv in intervals[:4]]


def voice_rhythm(root_pc, intervals, bass_pc, octave=3, voicing="power"):
    """Rhythm guitar chord voicing.
    'power' (default): root + fifth (rock/metal — uses slash bass).
    'full': root + 3rd + 5th + 7th (jazz-fusion comping — ignores slash bass since bass track has it)."""
    base = 12 * (octave + 1)
    if voicing == "full":
        return sorted({root_pc + base + iv for iv in intervals[:4]})
    pc = bass_pc if bass_pc is not None else root_pc
    return [pc + base, pc + 7 + base]


def voice_melody_guide(root_pc, intervals, bass_pc, octave=5):
    """A single chord-tone-of-the-week, biased high. Used as a sparse outline."""
    base = 12 * (octave + 1)
    # Pick the third or seventh if available (most colorful), else the fifth.
    for iv in (intervals[1] if len(intervals) > 1 else 4,
               intervals[3] if len(intervals) > 3 else None,
               intervals[2] if len(intervals) > 2 else 7):
        if iv is not None:
            return [root_pc + base + iv]
    return [root_pc + base + 4]


# ---------- note event building ----------

def feel_hits(feel, chord_start_in_bar, chord_beats, side):
    """Returns (offset, duration, vel_delta) tuples for a rhythm-guitar voicing,
    sourced from FEEL_BAR_PATTERNS and clipped to the chord's span. `side` shifts
    the R guitar by a 1/8 of a beat for stereo width without phasing."""
    pattern = FEEL_BAR_PATTERNS.get(feel, FEEL_BAR_PATTERNS["driving"])
    hits = []
    bar_cursor = 0.0
    # ~20ms at 120 BPM — Haas-effect stereo width, not a perceptibly separate hit.
    # The old 0.125 (1/8 beat) was 62ms which sounded like two separate guitarists,
    # not a tight double-track.
    side_offset = 0.04 if side == "R" else 0.0
    while bar_cursor < chord_beats:
        for offset, dur, vd in pattern:
            t = bar_cursor + offset
            if t + side_offset >= chord_beats:
                continue
            d = min(dur, chord_beats - t - side_offset)
            hits.append((t + side_offset, d, vd))
        bar_cursor += 4.0
    return hits


def emit_drum_pattern(cursor_beats, sec_length, pattern_name, mark_section_start):
    """Drum notes for one section. mark_section_start=True drops a crash on beat 1."""
    pattern = DRUM_BAR_PATTERNS.get(pattern_name, [])
    out = []
    if mark_section_start and pattern:
        out.append((cursor_beats, 0.5, GM_DRUMS["crash"], 95))
    bar_cursor = 0.0
    while bar_cursor < sec_length:
        for offset, drum, vel in pattern:
            if bar_cursor + offset >= sec_length:
                continue
            out.append((cursor_beats + bar_cursor + offset, 0.1, GM_DRUMS[drum], vel))
        bar_cursor += 4.0
    return out


def build_track_notes(form, sections_by_name, role):
    """Returns (notes, total_beats) where notes is a list of (start_beat, dur_beats, pitch, vel)."""
    out = []
    cursor_beats = 0.0
    for sec_name in form:
        sec = sections_by_name[sec_name]
        feel = sec.get("feel", "driving")
        sec_length = sum(c["beats"] for c in sec["chords"])

        # Per-section role filter: skip this role for this section, but keep the cursor
        # in sync so other roles' notes still line up.
        if role in sec.get("skip_roles", []):
            cursor_beats += sec_length
            continue

        if role == "drums":
            pattern_name = sec.get("drums") or FEEL_TO_DRUMS.get(feel, "basic-rock")
            out.extend(emit_drum_pattern(cursor_beats, sec_length, pattern_name,
                                         mark_section_start=True))
            cursor_beats += sec_length
            continue

        if role == "lead":
            melody = sec.get("melody", [])
            if not melody:
                cursor_beats += sec_length
                continue
            loop_beats = sec.get("melody_loop_beats")
            if loop_beats is None:
                # Melody plays once across the section (full composed line).
                for start, pitch_name, dur in melody:
                    if start < sec_length:
                        out.append((cursor_beats + start, dur, parse_pitch(pitch_name), 88))
            else:
                # Riff/motif mode — loop the phrase across the section.
                phrase_start = 0.0
                while phrase_start < sec_length:
                    for start, pitch_name, dur in melody:
                        abs_start = phrase_start + start
                        if abs_start < sec_length:
                            out.append((cursor_beats + abs_start, dur, parse_pitch(pitch_name), 86))
                    phrase_start += loop_beats
            cursor_beats += sec_length
            continue

        if role == "chugg":
            pattern_name = sec.get("chugg", "single-hit")
            pattern = CHUGG_PATTERNS.get(pattern_name, CHUGG_PATTERNS["single-hit"])
            # Derive the pattern period from the max offset — supports both 1-bar
            # patterns (gallop, syncopated, etc.) and 2-bar patterns (clave-3-2, clave-2-3).
            if pattern:
                max_offset = max(o for o, _, _ in pattern)
                period = (int(max_offset) // 4 + 1) * 4.0
            else:
                period = 4.0
            chord_cursor = cursor_beats
            for chord_spec in sec["chords"]:
                beats = chord_spec["beats"]
                root_pc, intervals, bass_pc = parse_chord(chord_spec["name"])
                pitch = chugg_pitch(root_pc)
                bar_cursor = 0.0
                while bar_cursor < beats:
                    for offset, dur, vd in pattern:
                        t = bar_cursor + offset
                        if t >= beats:
                            continue
                        out.append((chord_cursor + t, dur, pitch, 95 + vd))
                    bar_cursor += period
                chord_cursor += beats
            cursor_beats = chord_cursor
            continue

        chord_cursor = cursor_beats
        for chord_spec in sec["chords"]:
            beats = chord_spec["beats"]
            root_pc, intervals, bass_pc = parse_chord(chord_spec["name"])
            if role == "bass":
                pitches = voice_bass(root_pc, intervals, bass_pc)
                if beats >= 4:
                    out.append((chord_cursor, beats / 2, pitches[0], 85))
                    out.append((chord_cursor + beats / 2, beats / 2, pitches[0] + 7, 80))
                else:
                    out.append((chord_cursor, beats, pitches[0], 85))
            elif role == "pad":
                if feel == "montuno":
                    # Salsa montuno on piano — a syncopated 8th-note arpeggio of chord
                    # tones (root / 3rd / 5th) in the mid-register. Replaces the held-
                    # chord pad emission. Per-bar pattern, looped across the chord's span.
                    # Pattern: (offset_in_bar, tone_index, dur, vel)
                    base = 60  # C4 — mid-register where montuno comping lives
                    tones = intervals[:3]
                    while len(tones) < 3:   # ensure index 2 access for triads/sus
                        tones = tones + tones
                    montuno_figure = [
                        (0.5, 1, 0.40, 70),   # and-of-1: 3rd (anticipation)
                        (1.0, 0, 0.40, 78),   # beat 2: root (accent)
                        (1.5, 2, 0.40, 66),   # and-of-2: 5th
                        (2.5, 1, 0.40, 70),   # and-of-3: 3rd (anticipation)
                        (3.0, 0, 0.40, 78),   # beat 4: root (accent)
                        (3.5, 2, 0.40, 66),   # and-of-4: 5th
                    ]
                    bar_cursor = 0.0
                    while bar_cursor < beats:
                        for offset, tone_idx, dur, vel in montuno_figure:
                            t = bar_cursor + offset
                            if t >= beats:
                                continue
                            pitch = root_pc + base + tones[tone_idx]
                            out.append((chord_cursor + t, dur, pitch, vel))
                        bar_cursor += 4.0
                else:
                    pitches = voice_pad(root_pc, intervals, bass_pc)
                    pad_vel = 65 if feel == "sparse" else 72
                    # Let chords ring into the next change — more pianistic, less choppy.
                    # Generous on sparse sections so atmospheric moments breathe.
                    overhang = 2.0 if feel == "sparse" else 1.25
                    note_len = beats + overhang
                    for p in pitches:
                        out.append((chord_cursor, note_len, p, pad_vel))
            elif role == "synth_pad":
                pitches = voice_synth_pad(root_pc, intervals, bass_pc, octave=3)
                # Long sustain — pad blurs into next chord, the synth's release tail handles fadeout.
                overhang = 2.5 if feel == "sparse" else 1.5
                for p in pitches:
                    out.append((chord_cursor, beats + overhang, p, 60))
            elif role == "clean":
                # Always 8th-note fingerpicked arpeggio. The MIDI-CLEAN patch is voiced for picking.
                pitches = voice_clean(root_pc, intervals, bass_pc, octave=3)
                n = len(pitches)
                t = 0.0
                idx = 0
                while t < beats - 1e-6:
                    out.append((chord_cursor + t, 1.0, pitches[idx % n], 75))
                    t += 0.5
                    idx += 1
            elif role == "strum":
                # Always staggered strum on the MIDI-STRUM track (a patch voiced for strumming).
                # Each chord tone starts ~40ms after the previous (pick rake low-to-high),
                # all notes ring until just past the next chord change.
                pitches = voice_clean(root_pc, intervals, bass_pc, octave=3)
                stagger = 0.04
                end_time = chord_cursor + beats + 1.0
                for i, p in enumerate(pitches):
                    start = chord_cursor + i * stagger
                    out.append((start, end_time - start, p, 72 - i * 2))
            elif role in ("rhy_l", "rhy_r"):
                voicing = sec.get("voicing", "power")
                # Power chords live LOW on a real guitar (rock register, oct 2).
                # Full jazz comping lives mid-range (oct 3). Different octaves per voicing
                # match where real players actually voice these on the fretboard.
                rhy_octave = 2 if voicing == "power" else 3
                pitches = voice_rhythm(root_pc, intervals, bass_pc, octave=rhy_octave, voicing=voicing)
                # R slightly quieter (mimics real double-tracking — R player is the supporting take)
                base_vel = 88 if role == "rhy_l" else 84
                side = "L" if role == "rhy_l" else "R"
                for offset, dur, vd in feel_hits(feel, 0, beats, side):
                    for p in pitches:
                        out.append((chord_cursor + offset, dur, p, base_vel + vd))
            chord_cursor += beats
        cursor_beats = chord_cursor
    return out, cursor_beats


# ---------- standard MIDI file writer ----------

def vlq(n):
    """Variable-length quantity encoding for SMF."""
    if n == 0:
        return b"\x00"
    out = []
    while n > 0:
        out.append(n & 0x7F)
        n >>= 7
    out.reverse()
    return bytes((b | 0x80) for b in out[:-1]) + bytes([out[-1]])


def smf_track(events):
    """events: list of (abs_tick, bytes_payload). Returns the track chunk bytes."""
    events = sorted(events, key=lambda e: e[0])
    body = b""
    last = 0
    for tick, payload in events:
        body += vlq(tick - last) + payload
        last = tick
    body += b"\x00\xff\x2f\x00"  # end of track
    return b"MTrk" + struct.pack(">I", len(body)) + body


def write_smf(path, tempo_bpm, time_sig, tracks_notes):
    """tracks_notes: list of (name, notes). Writes a type-1 SMF."""
    mthd = b"MThd" + struct.pack(">IHHH", 6, 1, 1 + len(tracks_notes), PPQN)

    micros = int(60_000_000 / tempo_bpm)
    tempo_payload = b"\xff\x51\x03" + micros.to_bytes(3, "big")
    num, den = time_sig
    # denom -> power of 2 exponent (4 -> 2)
    den_pow = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}[den]
    ts_payload = b"\xff\x58\x04" + bytes([num, den_pow, 24, 8])
    meta_events = [(0, tempo_payload), (0, ts_payload)]
    meta_chunk = smf_track(meta_events)

    track_chunks = b""
    for name, notes in tracks_notes:
        events = []
        name_bytes = name.encode("utf-8")
        events.append((0, b"\xff\x03" + vlq(len(name_bytes)) + name_bytes))
        for start_beat, dur_beats, pitch, vel in notes:
            start_tick = int(round(start_beat * PPQN))
            end_tick = int(round((start_beat + dur_beats) * PPQN))
            events.append((start_tick, bytes([0x90, pitch, vel])))
            events.append((end_tick, bytes([0x80, pitch, 0])))
        track_chunks += smf_track(events)

    with open(path, "wb") as f:
        f.write(mthd)
        f.write(meta_chunk)
        f.write(track_chunks)


# ---------- Reaper RPP injection ----------

def rpp_midi_events(notes):
    """Convert notes to Reaper's inline E-event lines (delta ticks, hex bytes)."""
    raw = []
    for start_beat, dur_beats, pitch, vel in notes:
        start_tick = int(round(start_beat * PPQN))
        end_tick = int(round((start_beat + dur_beats) * PPQN))
        raw.append((start_tick, 0x90, pitch, vel))
        raw.append((end_tick, 0x80, pitch, 0))
    raw.sort(key=lambda e: (e[0], 0 if e[1] == 0x80 else 1))
    lines = []
    last = 0
    for tick, status, d1, d2 in raw:
        delta = tick - last
        lines.append(f"      E {delta} {status:02x} {d1:02x} {d2:02x}")
        last = tick
    lines.append(f"      E 0 b0 7b 00")  # all notes off
    return lines


def new_guid():
    return "{" + str(uuid.uuid4()).upper() + "}"


def rpp_item_block(name, position_sec, length_sec, notes, indent="    "):
    ev_lines = rpp_midi_events(notes)
    lines = [
        f"{indent}<ITEM",
        f"{indent}  POSITION {position_sec:.10f}",
        f"{indent}  SNAPOFFS 0",
        f"{indent}  LENGTH {length_sec:.10f}",
        f"{indent}  LOOP 0",
        f"{indent}  ALLTAKES 0",
        f"{indent}  FADEIN 1 0 0 1 0 0 0",
        f"{indent}  FADEOUT 1 0 0 1 0 0 0",
        f"{indent}  MUTE 0 0",
        f"{indent}  SEL 0",
        f"{indent}  IGUID {new_guid()}",
        f"{indent}  IID 0",
        f"{indent}  NAME \"{name}\"",
        f"{indent}  VOLPAN 1 0 1 -1",
        f"{indent}  SOFFS 0",
        f"{indent}  PLAYRATE 1 1 0 -1 0 0.0025",
        f"{indent}  CHANMODE 0",
        f"{indent}  GUID {new_guid()}",
        f"{indent}  <SOURCE MIDI",
        f"{indent}    HASDATA 1 {PPQN} QN",
        f"{indent}    CCINTERP 32",
    ]
    lines.extend(ev_lines)
    lines.extend([
        f"{indent}    IGNTEMPO 0 120 4 4",
        f"{indent}    SRCCOLOR 24576",
        f"{indent}    VELLANE -1",
        f"{indent}    KEYSNAP 0",
        f"{indent}    TRACKSEL 0",
        f"{indent}  >",
        f"{indent}>",
    ])
    return lines


def find_track_block(rpp_lines, track_name):
    """Returns (start_idx, end_idx) of the <TRACK ... > block for the given NAME, or None."""
    n = len(rpp_lines)
    i = 0
    while i < n:
        line = rpp_lines[i].lstrip()
        if line.startswith("<TRACK"):
            # Look for a NAME line within this track block to identify it.
            depth = 1
            j = i + 1
            this_name = None
            while j < n and depth > 0:
                s = rpp_lines[j].lstrip()
                if depth == 1 and s.startswith("NAME "):
                    # Strip surrounding quotes if present.
                    val = s[5:].strip()
                    if val.startswith('"') and val.endswith('"'):
                        val = val[1:-1]
                    this_name = val
                if s.startswith("<"):
                    depth += 1
                elif s == ">" or s.startswith(">"):
                    depth -= 1
                    if depth == 0:
                        if this_name == track_name:
                            return (i, j)
                        break
                j += 1
            i = j + 1
            continue
        i += 1
    return None


def inject_items_into_track(rpp_lines, track_name, item_blocks):
    """Insert item blocks just before the closing '>' of the named track."""
    span = find_track_block(rpp_lines, track_name)
    if span is None:
        return rpp_lines
    _, end_idx = span
    flat = []
    for block in item_blocks:
        flat.extend(block)
    return rpp_lines[:end_idx] + flat + rpp_lines[end_idx:]


def patch_tempo(rpp_lines, tempo_bpm):
    out = []
    for line in rpp_lines:
        if line.lstrip().startswith("TEMPO "):
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}TEMPO {tempo_bpm} 4 4 0")
        else:
            out.append(line)
    return out


def make_region_markers(form, section_lengths_sec, indent="  "):
    """One region per form instance, named '<section>-<n>' (verse-1, verse-2, ...)."""
    lines = []
    pos = 0.0
    counters = {}
    for i, sec_name in enumerate(form):
        counters[sec_name] = counters.get(sec_name, 0) + 1
        label = f"{sec_name}-{counters[sec_name]}"
        length = section_lengths_sec[sec_name]
        guid = new_guid()
        # MARKER <num> <pos> "<name>" <isregion> <color> <show> R <guid>
        lines.append(f'{indent}MARKER {i+1} {pos:.10f} "{label}" 1 0 1 R {guid}')
        lines.append(f'{indent}MARKER {i+1} {pos + length:.10f} "" 1 0 1 R {guid}')
        pos += length
    return lines


def build_notes_block(spec, indent="  "):
    """Build the lines that go inside the <NOTES> block — a human summary of the song.

    Reaper's notes pane does not auto-wrap, so we hand-wrap every long line to ~68 chars
    and emit each visible row as its own `|`-prefixed line.
    """
    WRAP_WIDTH = 68
    song = spec.get("song_name", "untitled")
    key = spec.get("key", "?")
    tempo = spec["tempo"]
    ts = spec.get("time_sig", [4, 4])
    by_name = {s["name"]: s for s in spec["sections"]}
    form = spec["form"]
    project_roles = list(spec.get("roles", DEFAULT_ROLES))

    lines = []

    def L(s=""):
        lines.append(f"{indent}|{s}")

    def wrap_paragraph(text, first_prefix, cont_prefix):
        """Wrap text and emit as `|` lines. first_prefix on line 1, cont_prefix on continuations."""
        if not text:
            return
        # textwrap can't take separate first/cont prefixes when both have visible chars,
        # so we wrap the content (minus prefixes) then re-attach.
        body_width = WRAP_WIDTH - len(first_prefix)
        wrapped = textwrap.wrap(text, width=body_width) or [""]
        L(f"{first_prefix}{wrapped[0]}")
        for cont in wrapped[1:]:
            L(f"{cont_prefix}{cont}")

    # Header
    L(f"{song}  —  {key}  —  {tempo} BPM  —  {ts[0]}/{ts[1]}")
    L()
    wrap_paragraph(f"FORM: {' · '.join(form)}", first_prefix="", cont_prefix="      ")
    L()

    seen = set()
    for name in form:
        if name in seen:
            continue
        seen.add(name)
        sec = by_name[name]
        feel = sec.get("feel", "driving")
        drums = sec.get("drums") or FEEL_TO_DRUMS.get(feel, "basic-rock")
        drums_disp = "—" if drums == "none" else drums
        move = sec.get("move", "")
        chords = " · ".join(c["name"] for c in sec["chords"])
        scales = sec.get("scales")
        skip = set(sec.get("skip_roles", []))
        sec_roles = [r for r in project_roles if r not in skip]

        # Section header (always short — fits without wrapping)
        L(f"{name.upper():<10} feel={feel:<10} drums={drums_disp}")
        # Roles active in this section (breadcrumb for fill mode)
        if sec_roles:
            wrap_paragraph(f"roles: {' · '.join(sec_roles)}",
                           first_prefix="  ", cont_prefix="         ")
        # Move description (the harmonic strategy)
        wrap_paragraph(move, first_prefix="  ", cont_prefix="  ")
        # Chord list — continuation indent aligns under chord names
        wrap_paragraph(f"chords: {chords}", first_prefix="  ", cont_prefix="          ")
        # Improv scales — continuation indent aligns under scale text
        if scales:
            wrap_paragraph(f"improv: {scales}", first_prefix="  ", cont_prefix="          ")
        L()
    return lines


def inject_project_notes(rpp_lines, notes_block):
    """Replace the contents of the <NOTES ...> ... > block with notes_block."""
    out = []
    i = 0
    while i < len(rpp_lines):
        line = rpp_lines[i]
        if line.lstrip().startswith("<NOTES "):
            out.append(line)
            out.extend(notes_block)
            i += 1
            while i < len(rpp_lines) and rpp_lines[i].strip() != ">":
                i += 1
            if i < len(rpp_lines):
                out.append(rpp_lines[i])
                i += 1
            continue
        out.append(line)
        i += 1
    return out


def insert_after_tempo(rpp_lines, new_lines):
    out = []
    inserted = False
    for line in rpp_lines:
        out.append(line)
        if not inserted and line.lstrip().startswith("TEMPO "):
            out.extend(new_lines)
            inserted = True
    return out


# ---------- EXTSTATE breadcrumb (invisible-to-user spec snapshot) ----------
#
# Composer-authored .RPPs carry a base64-encoded JSON snapshot of the full spec
# inside an <EXTSTATE> block at the project level. Reaper preserves unknown
# EXTSTATE blocks across saves and never shows them in any UI panel, so the
# user's NOTES pane stays clean while fill-mode gets exact context.

EXTSTATE_KEY = "claude_composer_spec_b64"


def build_extstate_block(spec, indent="  "):
    """Build the <EXTSTATE>...</EXTSTATE> block carrying the base64-encoded spec."""
    payload = base64.b64encode(json.dumps(spec, separators=(",", ":")).encode("utf-8")).decode("ascii")
    return [
        f"{indent}<EXTSTATE",
        f"{indent}  {EXTSTATE_KEY} {payload}",
        f"{indent}>",
    ]


def inject_extstate_breadcrumb(rpp_lines, spec):
    """Inject (or replace) the claude_composer EXTSTATE block at the project level.

    If an existing EXTSTATE block already contains our key, rewrite that block.
    Otherwise insert a fresh block just after the <NOTES ...> block.
    """
    block = build_extstate_block(spec)
    out = []
    i = 0
    replaced = False
    while i < len(rpp_lines):
        line = rpp_lines[i]
        stripped = line.lstrip()
        if not replaced and stripped.startswith("<EXTSTATE"):
            # Walk to the matching '>'; check whether our key appears inside.
            depth = 1
            j = i + 1
            contains_key = False
            while j < len(rpp_lines) and depth > 0:
                s = rpp_lines[j].lstrip()
                if s.startswith(EXTSTATE_KEY + " ") or s == EXTSTATE_KEY:
                    contains_key = True
                if s.startswith("<"):
                    depth += 1
                elif s == ">" or s.startswith(">"):
                    depth -= 1
                j += 1
            if contains_key:
                out.extend(block)
                i = j
                replaced = True
                continue
        out.append(line)
        i += 1

    if replaced:
        return out

    # No existing block — insert after the NOTES block's closing '>'.
    out2 = []
    i = 0
    inserted = False
    while i < len(out):
        out2.append(out[i])
        if not inserted and out[i].lstrip().startswith("<NOTES "):
            # Find the matching '>' for this NOTES block, then insert after it.
            depth = 1
            j = i + 1
            while j < len(out) and depth > 0:
                s = out[j].lstrip()
                if s.startswith("<"):
                    depth += 1
                elif s == ">" or s.startswith(">"):
                    depth -= 1
                out2.append(out[j])
                j += 1
            out2.extend(block)
            inserted = True
            i = j
            continue
        i += 1
    return out2


# ---------- RPP parsers (read-side) ----------

_MARKER_RE = re.compile(
    r'^\s*MARKER\s+(\d+)\s+([\d.]+)\s+(?:"([^"]*)"|(\S+))\s+\d+(?:\s|$)'
)
_TEMPO_RE = re.compile(r"^\s*TEMPO\s+([\d.]+)(?:\s+(\d+)\s+(\d+))?")


def parse_rpp_tempo(rpp_lines, default=120.0):
    """Return (tempo_bpm, time_sig). Defaults if TEMPO line missing."""
    for line in rpp_lines:
        m = _TEMPO_RE.match(line)
        if m:
            tempo = float(m.group(1))
            if m.group(2) and m.group(3):
                return tempo, [int(m.group(2)), int(m.group(3))]
            return tempo, [4, 4]
    return default, [4, 4]


def parse_rpp_markers(rpp_lines):
    """Return ordered list of regions: [(name, start_sec, end_sec, region_id), ...].

    Regions appear as pairs of MARKER lines sharing an id: start has a name,
    end has empty quoted string. Non-region markers (no pair) are skipped.
    """
    by_id = {}
    order = []
    for line in rpp_lines:
        m = _MARKER_RE.match(line)
        if not m:
            continue
        mid = int(m.group(1))
        pos = float(m.group(2))
        name = m.group(3) if m.group(3) is not None else (m.group(4) or "")
        if mid not in by_id:
            by_id[mid] = {"start": pos, "name": name, "end": None}
            order.append(mid)
        else:
            by_id[mid]["end"] = pos
    regions = []
    for mid in order:
        entry = by_id[mid]
        if entry["end"] is None:
            continue
        regions.append((entry["name"], entry["start"], entry["end"], mid))
    regions.sort(key=lambda r: r[1])
    return regions


def find_composer_region(regions):
    """Return (start_sec, end_sec) of the single region named 'COMPOSER'.

    Errors to stderr + sys.exit(2) on zero or multiple matches.
    """
    hits = [r for r in regions if r[0] == "COMPOSER"]
    if not hits:
        sys.stderr.write(
            "composer: no region named 'COMPOSER' found. "
            "Add one in Reaper (R-key over the empty bars, rename to COMPOSER).\n"
        )
        sys.exit(2)
    if len(hits) > 1:
        sys.stderr.write(
            f"composer: found {len(hits)} regions named 'COMPOSER'. "
            "Rename or delete duplicates — fill mode requires exactly one.\n"
        )
        sys.exit(2)
    name, start, end, _ = hits[0]
    return start, end


def extract_extstate_breadcrumb(rpp_lines):
    """Return the decoded spec dict from the EXTSTATE breadcrumb, or None."""
    for line in rpp_lines:
        s = line.lstrip()
        if s.startswith(EXTSTATE_KEY + " "):
            payload = s[len(EXTSTATE_KEY) + 1:].strip()
            try:
                return json.loads(base64.b64decode(payload).decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                return None
    return None


def parse_notes_block(rpp_lines):
    """Return the list of `|`-prefixed body lines of the <NOTES ...> block, or [].

    The leading `|` and any indentation are stripped from each line.
    """
    out = []
    i = 0
    n = len(rpp_lines)
    while i < n:
        if rpp_lines[i].lstrip().startswith("<NOTES "):
            i += 1
            while i < n:
                stripped = rpp_lines[i].lstrip()
                if stripped == ">" or stripped.startswith(">"):
                    return out
                # Lines start with '|' after the indentation.
                idx = rpp_lines[i].find("|")
                if idx >= 0:
                    out.append(rpp_lines[i][idx + 1:])
                else:
                    out.append("")
                i += 1
            return out
        i += 1
    return out


def parse_notes_block_sections(rpp_lines):
    """Recover a spec snapshot from the human-readable NOTES block.

    Used as the third-priority context source (after EXTSTATE and sidecar
    spec.json). Returns a dict shaped roughly like a spec, or None if parsing
    finds nothing useful.
    """
    notes = parse_notes_block(rpp_lines)
    if not notes:
        return None

    form = []
    sections = []
    current = None
    in_form = False

    def commit():
        nonlocal current
        if current and current.get("chords"):
            sections.append(current)
        current = None

    section_header_re = re.compile(
        r"^([A-Z][A-Z0-9_-]*)\s+feel=(\S+)(?:\s+drums=(\S+))?"
    )
    for raw in notes:
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("FORM:"):
            payload = stripped[len("FORM:"):].strip()
            form = [x.strip() for x in payload.split("·") if x.strip()]
            in_form = True
            continue
        if in_form:
            # FORM lines wrap with extra indent; pick up continuation tokens.
            if line.startswith("      ") and stripped:
                more = [x.strip() for x in stripped.split("·") if x.strip()]
                form.extend(more)
                continue
            in_form = False
        m = section_header_re.match(stripped)
        if m:
            commit()
            name_upper, feel, drums = m.group(1), m.group(2), m.group(3) or ""
            current = {
                "name": name_upper.lower(),
                "feel": feel,
                "drums": drums if drums and drums != "—" else "none" if drums == "—" else None,
                "roles": [],
                "chords": [],
                "scales": "",
                "move": "",
            }
            continue
        if current is None:
            continue
        s = stripped
        if s.startswith("roles:"):
            tail = s[len("roles:"):].strip()
            current["roles"] = [x.strip() for x in tail.split("·") if x.strip()]
        elif s.startswith("chords:"):
            tail = s[len("chords:"):].strip()
            current["chords"] = [{"name": x.strip(), "beats": 4}
                                  for x in tail.split("·") if x.strip()]
        elif s.startswith("improv:"):
            current["scales"] = s[len("improv:"):].strip()
        elif s and not s.startswith("|"):
            # Continuation of move narrative
            current["move"] = (current["move"] + " " + s).strip() if current["move"] else s
    commit()

    if not sections:
        return None
    return {"sections": sections, "form": form}


def parse_rpp_track_names(rpp_lines):
    """Return ordered list of every track's NAME value."""
    names = []
    depth = 0
    inside_track_at = None
    for i, line in enumerate(rpp_lines):
        s = line.lstrip()
        if s.startswith("<TRACK"):
            depth = 1
            inside_track_at = i
            continue
        if inside_track_at is not None:
            if s.startswith("<"):
                depth += 1
            elif s == ">" or s.startswith(">"):
                depth -= 1
                if depth == 0:
                    inside_track_at = None
                    continue
            if depth == 1 and s.startswith("NAME "):
                val = s[5:].strip()
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                names.append(val)
                inside_track_at = "named"  # don't append twice for this track
    return names


def parse_items_in_range(rpp_lines, time_range, track_filter=None):
    """Return [(track_name, position_sec, length_sec, item_text_lines), ...]
    for items overlapping the given time range (lo_sec, hi_sec).
    If track_filter is set, only tracks whose NAME is in track_filter are scanned.
    """
    lo, hi = time_range
    out = []
    n = len(rpp_lines)
    i = 0
    while i < n:
        s = rpp_lines[i].lstrip()
        if not s.startswith("<TRACK"):
            i += 1
            continue
        # Determine track NAME and span
        depth = 1
        j = i + 1
        track_name = None
        while j < n and depth > 0:
            ss = rpp_lines[j].lstrip()
            if ss.startswith("<"):
                depth += 1
            elif ss == ">" or ss.startswith(">"):
                depth -= 1
                if depth == 0:
                    break
            if depth == 1 and ss.startswith("NAME "):
                v = ss[5:].strip()
                if v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                track_name = v
            j += 1
        track_end = j

        if track_filter is None or (track_name is not None and track_name in track_filter):
            # Scan items inside the track block
            k = i + 1
            while k < track_end:
                ss = rpp_lines[k].lstrip()
                if ss.startswith("<ITEM"):
                    item_start = k
                    idepth = 1
                    k2 = k + 1
                    pos = None
                    length = None
                    while k2 < track_end and idepth > 0:
                        ts = rpp_lines[k2].lstrip()
                        if ts.startswith("<"):
                            idepth += 1
                        elif ts == ">" or ts.startswith(">"):
                            idepth -= 1
                            if idepth == 0:
                                break
                        if idepth == 1 and ts.startswith("POSITION "):
                            pos = float(ts.split()[1])
                        elif idepth == 1 and ts.startswith("LENGTH "):
                            length = float(ts.split()[1])
                        k2 += 1
                    if pos is not None and length is not None:
                        item_end_sec = pos + length
                        if item_end_sec > lo and pos < hi:
                            out.append((track_name, pos, length, rpp_lines[item_start:k2 + 1]))
                    k = k2 + 1
                else:
                    k += 1
        i = track_end + 1
    return out


# ---------- compose subcommand ----------

def compose_main(spec_path, out_dir, midi_only=False):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(spec_path) as f:
        spec = json.load(f)

    tempo = spec["tempo"]
    time_sig = spec.get("time_sig", [4, 4])
    sections = {s["name"]: s for s in spec["sections"]}
    form = spec["form"]
    song_name = spec.get("song_name", "untitled")
    roles = tuple(r for r in ALL_ROLES if r in set(spec.get("roles", DEFAULT_ROLES)))

    # Per-section MIDI files for portability (each contains all roles as separate tracks).
    for sec_name, sec in sections.items():
        single_form = [sec_name]
        tracks_notes = []
        for role in roles:
            notes, _ = build_track_notes(single_form, {sec_name: sec}, role)
            tracks_notes.append((f"{sec_name}-{role}", notes))
        write_smf(out_dir / f"{sec_name}.mid", tempo, time_sig, tracks_notes)

    # Full arrangement MIDI (for drag-into-any-DAW).
    full_tracks = []
    for role in roles:
        notes, _ = build_track_notes(form, sections, role)
        full_tracks.append((f"full-{role}", notes))
    write_smf(out_dir / "full.mid", tempo, time_sig, full_tracks)

    # MIDI-only mode skips the Reaper .RPP entirely — for users on Logic, Ableton,
    # Cubase, FL Studio, etc. who just want the portable .mid files. No config.json
    # or REAPER template required.
    if midi_only:
        with open(out_dir / "spec.json", "w") as f:
            json.dump(spec, f, indent=2)
        print(str(out_dir / "full.mid"))
        return

    # Build the Reaper project from the template.
    template_path = load_template_path()
    with open(template_path) as f:
        rpp_lines = f.read().splitlines()
    rpp_lines = patch_tempo(rpp_lines, tempo)

    beats_per_sec = tempo / 60.0
    section_lengths_sec = {
        sec_name: sum(c["beats"] for c in sec["chords"]) / beats_per_sec
        for sec_name, sec in sections.items()
    }
    rpp_lines = insert_after_tempo(rpp_lines, make_region_markers(form, section_lengths_sec))
    rpp_lines = inject_project_notes(rpp_lines, build_notes_block(spec))
    rpp_lines = inject_extstate_breadcrumb(rpp_lines, spec)

    sec_to_per_section_notes = {}  # (sec_name, role) -> notes, length_beats
    for sec_name, sec in sections.items():
        for role in roles:
            notes, length_beats = build_track_notes([sec_name], {sec_name: sec}, role)
            sec_to_per_section_notes[(sec_name, role)] = (notes, length_beats)

    for track_name, role in TRACK_TARGETS.items():
        if role not in roles:
            continue
        item_blocks = []
        cursor_beats = 0.0
        idx_in_form = 0
        for sec_name in form:
            sec_notes, sec_len_beats = sec_to_per_section_notes[(sec_name, role)]
            position_sec = cursor_beats / beats_per_sec
            length_sec = sec_len_beats / beats_per_sec
            item_blocks.append(
                rpp_item_block(
                    f"{sec_name}-{idx_in_form+1}",
                    position_sec,
                    length_sec,
                    sec_notes,
                )
            )
            cursor_beats += sec_len_beats
            idx_in_form += 1
        rpp_lines = inject_items_into_track(rpp_lines, track_name, item_blocks)

    rpp_path = out_dir / f"{song_name}.RPP"
    with open(rpp_path, "w") as f:
        f.write("\n".join(rpp_lines) + "\n")

    # Save the spec next to the outputs so future-me can see what was generated.
    with open(out_dir / "spec.json", "w") as f:
        json.dump(spec, f, indent=2)

    print(str(rpp_path))


# ---------- MIDI parsing fallback ----------

_MIDI_E_RE = re.compile(r"^\s*E\s+(\d+)\s+([0-9a-fA-F]{2})\s+([0-9a-fA-F]{2})\s+([0-9a-fA-F]{2})")


def parse_item_note_ons(item_lines, ppqn=PPQN):
    """Yield (tick_within_item, pitch) for every note-on event inside an item.

    item_lines is the text block for one <ITEM>. We accumulate delta ticks
    through the embedded MIDI events and emit only note-on (status 0x90)
    with non-zero velocity.
    """
    cursor = 0
    out = []
    for line in item_lines:
        m = _MIDI_E_RE.match(line)
        if not m:
            continue
        delta = int(m.group(1))
        status = int(m.group(2), 16)
        d1 = int(m.group(3), 16)
        d2 = int(m.group(4), 16)
        cursor += delta
        if status == 0x90 and d2 > 0:
            out.append((cursor, d1))
    return out


def parse_midi_pitch_sets(rpp_lines, tempo, time_sig, comp_start_sec, comp_end_sec,
                          prev_range, post_range):
    """Fallback: extract pitch sets per bar in prev/post 4-bar ranges.

    Returns {"prev": [[bar_offset, [pitches...]], ...], "post": [...]}.
    bar_offset is in bars relative to COMPOSER region (negative for prev, ≥0 for post).
    """
    beats_per_sec = tempo / 60.0
    bar_beats = time_sig[0]
    bar_seconds = bar_beats * 60.0 / tempo

    items = parse_items_in_range(rpp_lines, (prev_range[0], post_range[1]),
                                 track_filter=set(TRACK_TARGETS))

    prev_buckets = {}  # bar_idx (negative) -> set(pitches)
    post_buckets = {}  # bar_idx (non-negative) -> set(pitches)

    for track_name, pos_sec, length_sec, item_lines in items:
        notes = parse_item_note_ons(item_lines)
        for tick, pitch in notes:
            beats_within_item = tick / PPQN
            sec_in_project = pos_sec + beats_within_item / beats_per_sec
            if prev_range[0] <= sec_in_project < prev_range[1]:
                # Bar offset: bar at [comp_start - 1*bar_seconds, comp_start) is -1, etc.
                bar_idx = int((sec_in_project - comp_start_sec) // bar_seconds)
                prev_buckets.setdefault(bar_idx, set()).add(pitch)
            elif post_range[0] <= sec_in_project < post_range[1]:
                bar_idx = int((sec_in_project - comp_end_sec) // bar_seconds)
                post_buckets.setdefault(bar_idx, set()).add(pitch)

    return {
        "prev": [[idx, sorted(prev_buckets[idx])] for idx in sorted(prev_buckets)],
        "post": [[idx, sorted(post_buckets[idx])] for idx in sorted(post_buckets)],
    }


# ---------- analyze subcommand ----------

def _strip_region_suffix(region_name):
    """`verse-a-2` → `verse-a`. Strip trailing `-<integer>`."""
    m = re.match(r"^(.*)-(\d+)$", region_name)
    return m.group(1) if m else region_name


def _resolve_spec_snapshot(rpp_lines, rpp_path):
    """Find the best-available spec snapshot. Returns (snapshot_dict_or_None, source_str)."""
    # (a) EXTSTATE breadcrumb
    snap = extract_extstate_breadcrumb(rpp_lines)
    if snap is not None:
        return snap, "extstate"
    # (b) Sidecar spec.json next to the .RPP
    sidecar = Path(rpp_path).parent / "spec.json"
    if sidecar.exists():
        try:
            with open(sidecar) as f:
                return json.load(f), "sidecar"
        except (OSError, json.JSONDecodeError):
            pass
    # (c) Notes-block parsing
    parsed = parse_notes_block_sections(rpp_lines)
    if parsed:
        return parsed, "notes_block"
    return None, "midi_parse"  # fallback flag — analyze_main will populate pitch sets


def _last_chord_before(section_spec, slice_end_within_section_beats):
    """Walk the chord list to find the chord covering the last beat before slice_end."""
    cursor = 0.0
    last = None
    for c in section_spec.get("chords", []):
        last = c
        cursor += c.get("beats", 0)
        if cursor >= slice_end_within_section_beats - 1e-6:
            return c
    return last


def _first_chord_after(section_spec, slice_start_within_section_beats):
    """Walk the chord list to find the chord covering the first beat after slice_start."""
    cursor = 0.0
    for c in section_spec.get("chords", []):
        cursor += c.get("beats", 0)
        if cursor > slice_start_within_section_beats + 1e-6:
            return c
    chords = section_spec.get("chords", [])
    return chords[0] if chords else None


def _overlapping_regions(regions, lo, hi):
    """Return regions intersecting [lo, hi] with their overlap_sec."""
    out = []
    for name, start, end, mid in regions:
        ov_lo = max(start, lo)
        ov_hi = min(end, hi)
        if ov_hi > ov_lo + 1e-9:
            out.append((name, start, end, mid, ov_lo, ov_hi))
    return out


def _context_side(regions, snapshot, side_range, side, tempo, time_sig, composer_start, composer_end):
    """Build the prev_context or post_context entry. `side` is 'prev' or 'post'."""
    beats_per_sec = tempo / 60.0
    bar_beats = time_sig[0]
    lo, hi = side_range
    overlaps = _overlapping_regions(regions, lo, hi)
    sections_by_name = {}
    if snapshot:
        sections_by_name = {s["name"]: s for s in snapshot.get("sections", [])}

    entries = []
    border_chord = None
    for name, start, end, mid, ov_lo, ov_hi in overlaps:
        sec_name = _strip_region_suffix(name)
        sec_spec = sections_by_name.get(sec_name, {})
        overlap_bars = (ov_hi - ov_lo) * beats_per_sec / bar_beats
        entry = {
            "region_name": name,
            "section_name": sec_name,
            "overlap_bars": round(overlap_bars, 3),
            "feel": sec_spec.get("feel"),
            "roles": sec_spec.get("roles"),
            "chords": sec_spec.get("chords"),
            "scales": sec_spec.get("scales"),
            "move": sec_spec.get("move"),
        }
        entries.append(entry)

    # Border chord — from the region directly touching the COMPOSER boundary.
    if overlaps:
        if side == "prev":
            adj = max(overlaps, key=lambda r: r[2])  # region ending closest to start
            adj_name, adj_start, adj_end, _, _, _ = adj
            sec_spec = sections_by_name.get(_strip_region_suffix(adj_name), {})
            # Position of composer_start within the section (in beats)
            offset_beats = (composer_start - adj_start) * beats_per_sec
            border_chord = _last_chord_before(sec_spec, offset_beats)
        else:
            adj = min(overlaps, key=lambda r: r[1])  # region starting closest to end
            adj_name, adj_start, adj_end, _, _, _ = adj
            sec_spec = sections_by_name.get(_strip_region_suffix(adj_name), {})
            offset_beats = (composer_end - adj_start) * beats_per_sec
            border_chord = _first_chord_after(sec_spec, offset_beats)

    return {
        "range_sec": [lo, hi],
        "sections": entries,
        ("last_chord_before_region" if side == "prev" else "first_chord_after_region"): border_chord,
    }


def analyze_main(rpp_path):
    rpp_path = Path(rpp_path).resolve()
    if not rpp_path.exists():
        sys.stderr.write(f"composer: file not found: {rpp_path}\n")
        sys.exit(2)

    rpp_lines = open(rpp_path).read().splitlines()

    tempo, time_sig = parse_rpp_tempo(rpp_lines)
    regions = parse_rpp_markers(rpp_lines)
    comp_start, comp_end = find_composer_region(regions)

    beats_per_sec = tempo / 60.0
    bar_beats = time_sig[0]
    bar_seconds = bar_beats * 60.0 / tempo

    length_sec = comp_end - comp_start
    length_beats = length_sec * beats_per_sec
    length_bars = length_beats / bar_beats

    snapshot, source = _resolve_spec_snapshot(rpp_lines, rpp_path)

    prev_range = [max(0.0, comp_start - 4 * bar_seconds), comp_start]
    post_range = [comp_end, comp_end + 4 * bar_seconds]

    prev_ctx = _context_side(regions, snapshot, prev_range, "prev", tempo, time_sig, comp_start, comp_end)
    post_ctx = _context_side(regions, snapshot, post_range, "post", tempo, time_sig, comp_start, comp_end)

    # Active tracks in the [prev_range.start, post_range.end] neighborhood
    neighborhood_range = (prev_range[0], post_range[1])
    items = parse_items_in_range(rpp_lines, neighborhood_range, track_filter=set(TRACK_TARGETS))
    neighborhood_tracks = []
    seen_tracks = set()
    for track_name, _, _, _ in items:
        if track_name and track_name not in seen_tracks:
            neighborhood_tracks.append(track_name)
            seen_tracks.add(track_name)

    all_template_tracks = [t for t in parse_rpp_track_names(rpp_lines) if t in TRACK_TARGETS]

    warnings = []
    if not snapshot:
        warnings.append("no spec snapshot recoverable (EXTSTATE / sidecar / notes-block all empty); falling back to MIDI parsing")

    midi_pitch_sets = None
    if source == "midi_parse":
        midi_pitch_sets = parse_midi_pitch_sets(rpp_lines, tempo, time_sig, comp_start, comp_end,
                                                prev_range, post_range)

    out = {
        "project": {
            "path": str(rpp_path),
            "tempo": tempo,
            "time_sig": time_sig,
            "key": (snapshot or {}).get("key"),
            "song_name": (snapshot or {}).get("song_name"),
        },
        "composer_region": {
            "start_sec": comp_start,
            "end_sec": comp_end,
            "length_sec": length_sec,
            "length_beats": round(length_beats, 6),
            "length_bars": round(length_bars, 6),
            "starts_on_bar_boundary": abs(length_bars - round(length_bars)) < 1e-3,
            "ends_on_bar_boundary": True,
        },
        "context_source": source,
        "prev_context": prev_ctx,
        "post_context": post_ctx,
        "neighborhood_tracks": neighborhood_tracks,
        "all_template_tracks": all_template_tracks,
        "spec_snapshot": snapshot,
        "midi_pitch_sets": midi_pitch_sets,
        "warnings": warnings,
    }

    print(json.dumps(out, indent=2))


# ---------- fill subcommand ----------

FILL_SECTION_NAME = "composer-fill"
FILL_NOTES_HEADER = "COMPOSER-FILL"


def _build_fill_section_notes_lines(fill_spec, indent="  "):
    """Build the human-readable notes block for the fill section.

    Returns a list of `|`-prefixed lines (in the same shape as build_notes_block).
    """
    feel = fill_spec.get("feel", "driving")
    drums = fill_spec.get("drums") or FEEL_TO_DRUMS.get(feel, "basic-rock")
    drums_disp = "—" if drums == "none" else drums
    move = fill_spec.get("move", "")
    chords = " · ".join(c["name"] for c in fill_spec["chords"])
    scales = fill_spec.get("scales")
    roles = fill_spec.get("roles", [])

    WRAP_WIDTH = 68
    out = []

    def L(s=""):
        out.append(f"{indent}|{s}")

    def wrap_paragraph(text, first_prefix, cont_prefix):
        if not text:
            return
        body_width = WRAP_WIDTH - len(first_prefix)
        wrapped = textwrap.wrap(text, width=body_width) or [""]
        L(f"{first_prefix}{wrapped[0]}")
        for cont in wrapped[1:]:
            L(f"{cont_prefix}{cont}")

    L(f"{FILL_NOTES_HEADER:<10} feel={feel:<10} drums={drums_disp}")
    if roles:
        wrap_paragraph(f"roles: {' · '.join(roles)}",
                       first_prefix="  ", cont_prefix="         ")
    wrap_paragraph(move, first_prefix="  ", cont_prefix="  ")
    wrap_paragraph(f"chords: {chords}", first_prefix="  ", cont_prefix="          ")
    if scales:
        wrap_paragraph(f"improv: {scales}", first_prefix="  ", cont_prefix="          ")
    L()
    return out


def _splice_or_append_notes_section(rpp_lines, new_section_lines):
    """Within the <NOTES ...> block, replace any existing COMPOSER-FILL block
    or append at the end. Section blocks are delimited by their header line
    and end at the next blank `|` line.
    """
    out = []
    n = len(rpp_lines)
    i = 0
    while i < n:
        if not rpp_lines[i].lstrip().startswith("<NOTES "):
            out.append(rpp_lines[i])
            i += 1
            continue
        # Inside <NOTES>: collect body lines until the closing '>'.
        out.append(rpp_lines[i])
        i += 1
        body = []
        while i < n and rpp_lines[i].strip() != ">":
            body.append(rpp_lines[i])
            i += 1
        # Look for an existing COMPOSER-FILL section block within body.
        # A section starts at the line whose payload begins with FILL_NOTES_HEADER,
        # and ends at the next blank `|` line.
        replaced = False
        new_body = []
        j = 0
        header_payload = FILL_NOTES_HEADER + " "
        while j < len(body):
            payload = body[j].lstrip()
            if payload.startswith("|") and payload[1:].lstrip().startswith(header_payload):
                # Skip until we hit the next blank `|` line (end of this section).
                k = j + 1
                while k < len(body):
                    p2 = body[k].lstrip()
                    if p2 == "|" or p2 == "|"[:1] and body[k].rstrip().endswith("|"):
                        # End of section — include the blank line and stop.
                        k += 1
                        break
                    k += 1
                new_body.extend(new_section_lines)
                replaced = True
                j = k
                continue
            new_body.append(body[j])
            j += 1
        if not replaced:
            # Append new section at the end of body (ensure exactly one trailing blank).
            # Strip trailing empty `|` lines, then add new section.
            while new_body and new_body[-1].rstrip().endswith("|"):
                new_body.pop()
            new_body.extend(new_section_lines)
        out.extend(new_body)
        if i < n:
            out.append(rpp_lines[i])  # the closing '>'
            i += 1
    return out


def _update_extstate_with_fill(rpp_lines, fill_spec, rpp_path):
    """Read the best-available spec snapshot (EXTSTATE → sidecar → notes-block),
    add/replace the composer-fill section, ensure form contains FILL_SECTION_NAME,
    write it back into the EXTSTATE block. This makes future analyze calls see
    the complete picture even for legacy projects.
    """
    snap, _ = _resolve_spec_snapshot(rpp_lines, rpp_path)
    if snap is None:
        snap = {"song_name": "untitled", "key": "?", "tempo": None,
                "time_sig": [4, 4], "sections": [], "form": []}
    fill_section = {
        "name": FILL_SECTION_NAME,
        "feel": fill_spec.get("feel", "driving"),
        "drums": fill_spec.get("drums"),
        "voicing": fill_spec.get("voicing", "power"),
        "skip_roles": fill_spec.get("skip_roles", []),
        "melody": fill_spec.get("melody"),
        "melody_loop_beats": fill_spec.get("melody_loop_beats"),
        "chugg": fill_spec.get("chugg"),
        "scales": fill_spec.get("scales"),
        "move": fill_spec.get("move"),
        "chords": fill_spec["chords"],
    }
    # Replace or append the composer-fill section.
    sections = snap.get("sections", [])
    sections = [s for s in sections if s.get("name") != FILL_SECTION_NAME]
    sections.append(fill_section)
    snap["sections"] = sections
    form = snap.get("form", [])
    if FILL_SECTION_NAME not in form:
        form.append(FILL_SECTION_NAME)
    snap["form"] = form
    return inject_extstate_breadcrumb(rpp_lines, snap), snap


def _update_sidecar_spec(rpp_path, fill_spec):
    """If a sidecar spec.json exists, update it in the same shape as the EXTSTATE.
    No-op if no sidecar."""
    sidecar = Path(rpp_path).parent / "spec.json"
    if not sidecar.exists():
        return
    try:
        with open(sidecar) as f:
            spec = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    fill_section = {
        "name": FILL_SECTION_NAME,
        "feel": fill_spec.get("feel", "driving"),
        "drums": fill_spec.get("drums"),
        "voicing": fill_spec.get("voicing", "power"),
        "skip_roles": fill_spec.get("skip_roles", []),
        "melody": fill_spec.get("melody"),
        "melody_loop_beats": fill_spec.get("melody_loop_beats"),
        "chugg": fill_spec.get("chugg"),
        "scales": fill_spec.get("scales"),
        "move": fill_spec.get("move"),
        "chords": fill_spec["chords"],
    }
    sections = spec.get("sections", [])
    sections = [s for s in sections if s.get("name") != FILL_SECTION_NAME]
    sections.append(fill_section)
    spec["sections"] = sections
    form = spec.get("form", [])
    if FILL_SECTION_NAME not in form:
        form.append(FILL_SECTION_NAME)
    spec["form"] = form
    with open(sidecar, "w") as f:
        json.dump(spec, f, indent=2)


def fill_main(fill_spec_path, rpp_path):
    rpp_path = Path(rpp_path).resolve()
    if not rpp_path.exists():
        sys.stderr.write(f"composer: file not found: {rpp_path}\n")
        sys.exit(2)

    with open(fill_spec_path) as f:
        fill_spec = json.load(f)

    if "chords" not in fill_spec or not fill_spec["chords"]:
        sys.stderr.write("composer: fill spec must include non-empty 'chords'.\n")
        sys.exit(2)

    rpp_lines = open(rpp_path).read().splitlines()
    tempo, time_sig = parse_rpp_tempo(rpp_lines)
    regions = parse_rpp_markers(rpp_lines)
    comp_start, comp_end = find_composer_region(regions)
    region_length_sec = comp_end - comp_start

    # Validate spec beats match region length.
    spec_beats = sum(c["beats"] for c in fill_spec["chords"])
    expected_beats = region_length_sec * tempo / 60.0
    if abs(spec_beats - expected_beats) > 1e-3:
        sys.stderr.write(
            f"composer: fill totals {spec_beats} beats; region is {expected_beats:.4f} beats "
            f"({region_length_sec:.4f}s at {tempo} BPM). Adjust the chord progression or "
            "resize the COMPOSER region in Reaper.\n"
        )
        sys.exit(2)

    # Build a one-section spec wrapper for build_track_notes.
    sec_spec = dict(fill_spec)  # shallow copy; we'll add `name`
    sec_spec["name"] = FILL_SECTION_NAME
    sections_by_name = {FILL_SECTION_NAME: sec_spec}
    form = [FILL_SECTION_NAME]
    roles = tuple(r for r in ALL_ROLES if r in set(fill_spec.get("roles", DEFAULT_ROLES)))

    available_tracks = set(parse_rpp_track_names(rpp_lines))
    written_tracks = []

    for track_name, role in TRACK_TARGETS.items():
        if role not in roles:
            continue
        if track_name not in available_tracks:
            sys.stderr.write(f"composer: track {track_name!r} not in project — skipping role {role!r}.\n")
            continue
        notes, _ = build_track_notes(form, sections_by_name, role)
        item = rpp_item_block(
            f"composer-fill-{role}",
            comp_start,
            region_length_sec,
            notes,
        )
        rpp_lines = inject_items_into_track(rpp_lines, track_name, [item])
        written_tracks.append(track_name)

    # Update breadcrumbs.
    rpp_lines, _ = _update_extstate_with_fill(rpp_lines, fill_spec, rpp_path)
    rpp_lines = _splice_or_append_notes_section(rpp_lines, _build_fill_section_notes_lines(fill_spec))
    _update_sidecar_spec(rpp_path, fill_spec)

    with open(rpp_path, "w") as f:
        f.write("\n".join(rpp_lines) + "\n")

    bars = round(region_length_sec * tempo / 60.0 / time_sig[0], 3)
    sys.stdout.write(
        f"composer: filled COMPOSER region ({bars} bars, {region_length_sec:.3f}s) on tracks "
        f"{', '.join(written_tracks) if written_tracks else '(none)'}. Reopen {rpp_path} in Reaper.\n"
    )


# ---------- main (CLI dispatcher) ----------

USAGE = (
    "usage:\n"
    "  composer.py compose [--midi-only] <spec.json> <output_dir>\n"
    "  composer.py analyze <project.RPP>\n"
    "  composer.py fill <fill_spec.json> <project.RPP>\n"
    "\n"
    "  --midi-only  skip the Reaper .RPP — only write per-section .mid + full.mid\n"
    "               (no config.json or REAPER template required; works for Logic,\n"
    "                Ableton, Cubase, FL Studio, etc.)\n"
)


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.stderr.write(USAGE)
        sys.exit(2)

    verb = argv[0]
    if verb == "compose":
        rest = argv[1:]
        midi_only = "--midi-only" in rest
        positional = [a for a in rest if a != "--midi-only"]
        if len(positional) != 2:
            sys.stderr.write("usage: composer.py compose [--midi-only] <spec.json> <output_dir>\n")
            sys.exit(2)
        compose_main(positional[0], positional[1], midi_only=midi_only)
    elif verb == "analyze":
        if len(argv) != 2:
            sys.stderr.write("usage: composer.py analyze <project.RPP>\n")
            sys.exit(2)
        analyze_main(argv[1])
    elif verb == "fill":
        if len(argv) != 3:
            sys.stderr.write("usage: composer.py fill <fill_spec.json> <project.RPP>\n")
            sys.exit(2)
        fill_main(argv[1], argv[2])
    else:
        sys.stderr.write(f"composer: unknown verb {verb!r}\n{USAGE}")
        sys.exit(2)


if __name__ == "__main__":
    main()
