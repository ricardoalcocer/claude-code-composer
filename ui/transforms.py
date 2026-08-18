#!/usr/bin/env python3
"""Tier 0: deterministic spec transforms. No model, no network, ~0.3ms.

Every function takes a spec dict and returns a NEW spec dict (input is never
mutated). Each result passes through validate(), which re-parses every chord
and melody pitch with composer.py's own parsers — if composer.py would reject
it, the transform refuses to return it. That gate is what makes these safe to
bind to single keypresses in the UI.

Measured context (see ui/README-generation.md): asking the model to transpose
a 7-section spec took 171.6s because it re-emitted every section. transpose()
below is the same edit in ~0.3ms, and it cannot fumble an enharmonic.

Importable (`from transforms import apply`) — the bridge server uses it that
way — and runnable standalone:

    python3 ui/transforms.py transpose+7 spec.json          # writes to stdout
    python3 ui/transforms.py tempo=96 form=intro,verse,verse spec.json
"""

import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import composer  # noqa: E402  (path bootstrap must run first)

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
# Keys whose conventional spelling is flat-side; used to pick sharps vs flats
# after a transpose so "Bm +1" comes out Cm, not B#m.
FLAT_PCS = {1, 3, 5, 8, 10}

_ROOT_RE = re.compile(r"^([A-G][#b]?)(.*)$")
_KEY_RE = re.compile(r"^([A-G][#b]?)(m?)$")

FEELS = sorted(composer.FEEL_TO_DRUMS)
VALID_ROLES = list(composer.ALL_ROLES)


class TransformError(ValueError):
    """A transform that cannot produce a valid spec."""


# ---------- validation gate ----------

def validate(spec):
    """Re-parse everything composer.py would parse. Raises TransformError."""
    try:
        if not spec.get("sections"):
            raise ValueError("spec has no sections")
        if not spec.get("form"):
            raise ValueError("spec has an empty form")
        names = {s["name"] for s in spec["sections"]}
        missing = [n for n in spec["form"] if n not in names]
        if missing:
            raise ValueError(f"form references undefined sections: {missing}")
        tempo = spec.get("tempo")
        if not isinstance(tempo, (int, float)) or not 20 <= tempo <= 400:
            raise ValueError(f"tempo out of range: {tempo!r}")
        for sec in spec["sections"]:
            if not sec.get("chords"):
                raise ValueError(f"section {sec['name']!r} has no chords")
            for c in sec["chords"]:
                composer.parse_chord(c["name"])  # raises on anything bad
                if not isinstance(c["beats"], (int, float)) or c["beats"] <= 0:
                    raise ValueError(f"bad beats on {c['name']!r}: {c['beats']!r}")
            for note in sec.get("melody") or []:
                composer.parse_pitch(note[1])
            for role in sec.get("skip_roles") or []:
                if role not in VALID_ROLES:
                    raise ValueError(f"unknown role in skip_roles: {role!r}")
        for role in spec.get("roles") or []:
            if role not in VALID_ROLES:
                raise ValueError(f"unknown role: {role!r}")
    except TransformError:
        raise
    except Exception as e:
        raise TransformError(str(e))
    return spec


# ---------- pitch helpers ----------

def _shift_root(root, semis, flats):
    pc = (composer.NOTE_NAMES[root] + semis) % 12
    return (FLAT_NAMES if flats else SHARP_NAMES)[pc]


def _transpose_chord(name, semis, flats):
    base, _, slash = name.partition("/")
    m = _ROOT_RE.match(base)
    if not m:
        raise TransformError(f"cannot parse chord root: {name!r}")
    out = _shift_root(m.group(1), semis, flats) + m.group(2)
    if slash:
        ms = _ROOT_RE.match(slash)
        if not ms:
            raise TransformError(f"cannot parse slash bass: {name!r}")
        out += "/" + _shift_root(ms.group(1), semis, flats) + ms.group(2)
    return out


def _transpose_pitch(name, semis):
    midi = composer.parse_pitch(name) + semis
    if not 0 <= midi <= 127:
        raise TransformError(f"melody pitch {name!r} leaves MIDI range")
    return SHARP_NAMES[midi % 12] + str(midi // 12 - 1)


# ---------- transforms ----------

def transpose(spec, semis):
    """Shift every chord, melody pitch, and the key by `semis` semitones."""
    semis = int(semis)
    if semis == 0:
        return copy.deepcopy(spec)
    out = copy.deepcopy(spec)

    flats = False
    key = out.get("key")
    if key:
        m = _KEY_RE.match(key.strip())
        if m:
            new_pc = (composer.NOTE_NAMES[m.group(1)] + semis) % 12
            flats = new_pc in FLAT_PCS
            out["key"] = (FLAT_NAMES if flats else SHARP_NAMES)[new_pc] + m.group(2)

    for sec in out["sections"]:
        for c in sec["chords"]:
            c["name"] = _transpose_chord(c["name"], semis, flats)
        if sec.get("melody"):
            sec["melody"] = [[st, _transpose_pitch(p, semis), d]
                             for st, p, d in sec["melody"]]
        # scales text is prose about the OLD key — stale guidance is worse
        # than none, so drop it and let a Tier 1 patch restore it if wanted.
        if sec.get("scales"):
            sec.pop("scales")
    return validate(out)


def set_tempo(spec, bpm):
    bpm = float(bpm)
    out = copy.deepcopy(spec)
    out["tempo"] = int(bpm) if bpm == int(bpm) else bpm
    return validate(out)


def rebar(spec, num, den=8):
    """Change the time signature and rescale each chord's length so every
    section spans the same number of BARS it did before.

    4/4→7/8: a 4-beat (1-bar) chord becomes 3.5 beats (one 7/8 bar). Rhythmic
    feel patterns still articulate inside the new bar; this is a sketch-level
    re-bar, not a beat-map.
    """
    num, den = int(num), int(den)
    if den not in (2, 4, 8, 16):
        raise TransformError(f"unsupported denominator: {den}")
    out = copy.deepcopy(spec)
    old_num, old_den = out.get("time_sig", [4, 4])
    old_bar = old_num * 4 / old_den   # bar length in quarter-note beats
    new_bar = num * 4 / den
    if old_bar <= 0:
        raise TransformError("existing time_sig is degenerate")
    ratio = new_bar / old_bar
    out["time_sig"] = [num, den]
    for sec in out["sections"]:
        for c in sec["chords"]:
            scaled = c["beats"] * ratio
            # Round to a quarter of a beat to keep the grid playable; refuse
            # rebars that would zero a chord out.
            c["beats"] = max(round(scaled * 4) / 4, 0.25)
        if sec.get("melody"):
            sec["melody"] = [[round(st * ratio * 4) / 4, p, max(round(d * ratio * 4) / 4, 0.25)]
                             for st, p, d in sec["melody"]]
        if sec.get("melody_loop_beats"):
            sec["melody_loop_beats"] = max(round(sec["melody_loop_beats"] * ratio * 4) / 4, 0.25)
    return validate(out)


def set_roles(spec, roles):
    roles = [r for r in roles if r]
    bad = [r for r in roles if r not in VALID_ROLES]
    if bad:
        raise TransformError(f"unknown roles: {bad}")
    if not roles:
        raise TransformError("cannot remove every role")
    out = copy.deepcopy(spec)
    out["roles"] = [r for r in VALID_ROLES if r in set(roles)]
    return validate(out)


def drop_role(spec, role):
    current = spec.get("roles") or list(composer.DEFAULT_ROLES)
    return set_roles(spec, [r for r in current if r != role])


def add_role(spec, role):
    current = spec.get("roles") or list(composer.DEFAULT_ROLES)
    return set_roles(spec, current + [role])


def set_form(spec, form):
    if not form:
        raise TransformError("form cannot be empty")
    out = copy.deepcopy(spec)
    out["form"] = list(form)
    return validate(out)


def repeat_section(spec, index):
    """Duplicate the form entry at `index` (repeat a section in place)."""
    form = list(spec["form"])
    if not 0 <= index < len(form):
        raise TransformError(f"form index out of range: {index}")
    form.insert(index, form[index])
    return set_form(spec, form)


def remove_form_entry(spec, index):
    form = list(spec["form"])
    if not 0 <= index < len(form):
        raise TransformError(f"form index out of range: {index}")
    del form[index]
    return set_form(spec, form)


def set_feel(spec, section_name, feel):
    if feel not in composer.FEEL_TO_DRUMS:
        raise TransformError(f"unknown feel {feel!r}; valid: {FEELS}")
    out = copy.deepcopy(spec)
    for sec in out["sections"]:
        if sec["name"] == section_name:
            sec["feel"] = feel
            # A stale drum override would silently defeat the new feel.
            sec.pop("drums", None)
            return validate(out)
    raise TransformError(f"no section named {section_name!r}")


def thin(spec):
    """Halve the arrangement: keep bass + one harmony layer + drums.

    The "would it survive stripped down?" audition — a cheap variant that tells
    you whether the writing carries without the wall of guitars.
    """
    current = spec.get("roles") or list(composer.DEFAULT_ROLES)
    keep = [r for r in ("bass", "drums") if r in current]
    for harmony in ("clean", "pad", "rhy_l", "strum", "synth_pad"):
        if harmony in current:
            keep.append(harmony)
            break
    if not keep:
        raise TransformError("nothing left to keep")
    return set_roles(spec, keep)


# ---------- dispatch ----------

# name -> (fn, arg parser). Arg strings come from the CLI or the HTTP API.
def _parse_roles_arg(a):
    return [a] if isinstance(a, str) and "," not in a else (
        a.split(",") if isinstance(a, str) else list(a))


TRANSFORMS = {
    "transpose": lambda spec, a: transpose(spec, a),
    "tempo": lambda spec, a: set_tempo(spec, a),
    "rebar": lambda spec, a: rebar(spec, *(int(x) for x in str(a).split("/"))),
    "roles": lambda spec, a: set_roles(spec, _parse_roles_arg(a)),
    "drop_role": lambda spec, a: drop_role(spec, a),
    "add_role": lambda spec, a: add_role(spec, a),
    "form": lambda spec, a: set_form(spec, _parse_roles_arg(a)),
    "repeat": lambda spec, a: repeat_section(spec, int(a)),
    "remove_entry": lambda spec, a: remove_form_entry(spec, int(a)),
    "feel": lambda spec, a: set_feel(spec, *_parse_roles_arg(a)),
    "thin": lambda spec, a: thin(spec),
}


def apply(spec, op, arg=None):
    """Apply one named transform. This is the API the server calls."""
    fn = TRANSFORMS.get(op)
    if fn is None:
        raise TransformError(f"unknown transform {op!r}; valid: {sorted(TRANSFORMS)}")
    return fn(spec, arg)


# ---------- CLI ----------

def _main(argv):
    if len(argv) < 2:
        sys.stderr.write(__doc__ + "\n")
        return 2
    *ops, spec_path = argv
    with open(spec_path) as f:
        spec = json.load(f)
    for op_str in ops:
        # transpose+7 / transpose-2 / tempo=96 / rebar=7/8 / thin
        m = re.match(r"^([a-z_]+)(?:([+=-])(.*))?$", op_str)
        if not m:
            sys.stderr.write(f"bad op: {op_str!r}\n")
            return 2
        name, sep, arg = m.group(1), m.group(2), m.group(3)
        if name == "transpose" and sep in ("+", "-"):
            arg = sep + arg
        spec = apply(spec, name, arg)
    json.dump(spec, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
