#!/usr/bin/env python3
"""Build a slim manifest of the Drumforge NuMetal Grooves Vol 1 library.

Parses filenames like 'Driving Groove 1 (115-140BPM).mid' into
{name, bpm_min, bpm_max, file}. Paths are relative to the source root
so the JSON stays portable; SKILL.md tells the assistant how to
expand to absolute path.
"""
import json
import os
import re

BASE = "/Users/music/Documents/_MIDI PACKS/Drumforge/Midi/NuMetal Grooves Vol 1/NuMetal Grooves Vol 1"
SECTIONS = ["Intro", "Verse", "Chorus", "Bridge", "Breakdown", "Fills", "Outro"]

RE_BPM = re.compile(r"^(.+?)\s*\((\d+)(?:-(\d+))?BPM\)\.mid$", re.IGNORECASE)


def parse(fname):
    m = RE_BPM.match(fname)
    if not m:
        return {"name": fname[:-4], "bpm_min": None, "bpm_max": None, "file": fname}
    name = m.group(1).strip()
    bpm_min = int(m.group(2))
    bpm_max = int(m.group(3)) if m.group(3) else bpm_min
    return {"name": name, "bpm_min": bpm_min, "bpm_max": bpm_max, "file": fname}


by_section = {}
for section in SECTIONS:
    sec_path = os.path.join(BASE, section)
    if not os.path.isdir(sec_path):
        continue
    entries = []
    for fname in sorted(os.listdir(sec_path)):
        if fname.endswith(".mid"):
            entries.append(parse(fname))
    by_section[section.lower()] = entries

manifest = {
    "source": "Drumforge — NuMetal Grooves Vol 1",
    "source_path": BASE,
    "format_note": "file paths are relative to source_path; combine to get absolute path. Filenames already encode BPM ranges (parsed into bpm_min/bpm_max).",
    "genre": "nu-metal / heavy modern rock — heavier than the user's preferred melodic-rock genres. Use for FILLS and SECTION TRANSITIONS even outside nu-metal contexts (a fill is a fill); skip the verses/choruses for non-metal pieces.",
    "by_section": by_section,
}

import sys
total = sum(len(v) for v in by_section.values())
print(f"Manifest: {total} files indexed across {len(by_section)} sections", file=sys.stderr)
print(json.dumps(manifest, indent=2))
