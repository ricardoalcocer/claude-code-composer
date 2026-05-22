#!/usr/bin/env python3
"""Parse SHLD progression-MIDI filenames into a structured mood-indexed bank.

Filename format: `<KEY> - <roman_numerals_space_separated> - <mood_tags>.mid`
Examples:
  A - i VI III VII - Nostalgic Hopeful.mid
  Eb - im bVIIM bVIM V - Mysterious Triumphant.mid
  G - bVIIM V7 I - Cadence.mid
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/music/Documents/_MIDI PACKS/SHLD/progressions-20251006")
SCALES = {"Minor", "Modal"}  # skip Major

FNAME_RE = re.compile(r"^(.+?)\s+-\s+(.+?)\s+-\s+(.+?)\.mid$")


def parse_filename(stem: str):
    """Return (key, rn_seq_normalized, mood_tags_list) or None on bad format."""
    m = FNAME_RE.match(stem)
    if not m:
        return None
    key, rn_raw, mood_raw = m.group(1), m.group(2), m.group(3)
    # Normalize whitespace inside RN sequence
    rn = " ".join(rn_raw.split())
    moods = mood_raw.split()  # 1-2 words typically; "Cadence" is single
    return key.strip(), rn, moods


def main():
    # progression_rn -> {keys: Counter, moods: Counter, scale: set, count: int}
    bank = defaultdict(lambda: {
        "keys": Counter(),
        "moods": Counter(),
        "scales": set(),
        "styles": Counter(),
        "count": 0,
    })

    skipped = []
    for scale in SCALES:
        scale_root = ROOT / scale
        for path in scale_root.rglob("*.mid"):
            parsed = parse_filename(path.name)
            if parsed is None:
                skipped.append(str(path))
                continue
            key, rn, moods = parsed
            entry = bank[rn]
            entry["keys"][key] += 1
            for mood in moods:
                entry["moods"][mood] += 1
            entry["scales"].add(scale)
            # style is the parent folder name (pop / pop2 / soul / hiphop2)
            style = path.parent.name
            entry["styles"][style] += 1
            entry["count"] += 1

    # Build mood-indexed view
    mood_index = defaultdict(list)
    for rn, entry in bank.items():
        # primary mood label = top mood by frequency (combined)
        primary_mood = entry["moods"].most_common(1)[0][0]
        # all mood combos this RN appeared under
        record = {
            "rn": rn,
            "scales": sorted(entry["scales"]),
            "keys_seen": sorted(entry["keys"].keys()),
            "mood_tags": [m for m, _ in entry["moods"].most_common()],
            "total_files": entry["count"],
        }
        mood_index[primary_mood].append(record)

    # Sort each mood bucket by total_files descending (most common first)
    for mood in mood_index:
        mood_index[mood].sort(key=lambda r: -r["total_files"])

    # Summary stats
    total_files = sum(e["count"] for e in bank.values())
    unique_rn = len(bank)
    print(f"Parsed {total_files} files, {unique_rn} unique progressions", file=sys.stderr)
    print(f"Skipped: {len(skipped)}", file=sys.stderr)
    if skipped[:3]:
        print(f"First skipped: {skipped[:3]}", file=sys.stderr)
    print(f"Mood buckets: {sorted(mood_index.keys())}", file=sys.stderr)
    for mood in sorted(mood_index.keys()):
        print(f"  {mood}: {len(mood_index[mood])} unique progressions", file=sys.stderr)

    # Convert defaultdict to dict for JSON
    out = {
        "source": "Songwriter's Helpful Library Database (SHLD) — local MIDI pack",
        "source_path": str(ROOT),
        "scope": "Minor + Modal scales only (Major skipped — user genre preference)",
        "total_source_files": total_files,
        "unique_progressions": unique_rn,
        "by_mood": dict(mood_index),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
