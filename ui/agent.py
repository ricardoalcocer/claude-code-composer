#!/usr/bin/env python3
"""Tier 1/2: drive `claude -p` headless for spec generation and scoped patches.

Two execution shapes, chosen by measurement (see ui/README-generation.md):

  Tier 2 (cold brief, ~2-3 min): a fresh `claude` process per brief. The work
    is dominated by emission, not startup, so process reuse buys little — and
    fresh processes parallelise trivially for fan-out.

  Tier 1 (scoped patch, ~13-25s): a WARM persistent session (stream-json in/out)
    primed once with SKILL.md + the current spec. Warmth matters here: the
    ~30s prime would otherwise dominate every small ask. The session keeps
    conversational context, so "darker" can follow "more Phrygian" naturally.

Everything runs through a Job registry the HTTP layer polls/streams. Claude
writes spec JSON to a private staging file; we validate it with transforms.py's
gate (composer.py's own parsers) before composer.py ever sees it, then render
--midi-only into the archive. Rendered output is the only thing the UI trusts.
"""

import json
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transforms  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_BIN = shutil.which("claude")

BRIEF_TIMEOUT_S = 420          # measured cold brief ~170s; headroom for hard ones
PATCH_TIMEOUT_S = 180
PRIME_TIMEOUT_S = 120

# The generation contract. Kept terse: every extra instruction token is paid on
# every brief, and SKILL.md already carries the musical doctrine.
BRIEF_PROMPT = """Read SKILL.md in this directory.

Compose a spec for this brief: {brief}

Requirements:
- Write ONLY the spec JSON to {out_path} (use the Write tool).
- Include `move` and `scales` on every section.
- Do NOT run composer.py. Do not explain anything.
{variety}"""

PRIME_PROMPT = """Read SKILL.md in full. Then read {spec_path} — this is the \
current working spec, named {song_name}. You will be asked for small scoped \
edits to it. Reply with exactly: primed"""

PATCH_PROMPT = """{ask}

Return ONLY the JSON for the requested change — the smallest object that \
covers it (one section object, or one chords array). Raw JSON only: no prose, \
no code fence, no file writes."""


def _now():
    return time.time()


class Job:
    """One unit of agent work, observable by the HTTP layer."""

    def __init__(self, kind, label):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind              # "brief" | "patch" | "prime"
        self.label = label
        self.status = "queued"        # queued | running | done | error
        self.detail = ""
        self.rel = None               # archive-relative song dir once rendered
        self.created = _now()
        self.started = None
        self.finished = None

    def to_dict(self):
        return {
            "id": self.id, "kind": self.kind, "label": self.label,
            "status": self.status, "detail": self.detail, "rel": self.rel,
            "created": self.created, "started": self.started,
            "finished": self.finished,
            "elapsed": round((self.finished or _now()) - (self.started or _now()), 1)
                       if self.started else 0,
        }


class JobRegistry:
    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()
        self._version = 0
        self._changed = threading.Condition(self._lock)

    def add(self, job):
        with self._lock:
            self._jobs[job.id] = job
            self._bump()
        return job

    def update(self, job, **fields):
        with self._lock:
            for k, v in fields.items():
                setattr(job, k, v)
            self._bump()

    def _bump(self):
        self._version += 1
        self._changed.notify_all()

    def snapshot(self):
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)
            return self._version, [j.to_dict() for j in jobs[:50]]

    def wait_change(self, seen_version, timeout):
        """Block until the registry moves past seen_version (or timeout)."""
        with self._changed:
            if self._version != seen_version:
                return self._version
            self._changed.wait(timeout)
            return self._version


REGISTRY = JobRegistry()


# ---------- shared helpers ----------

def claude_available():
    return CLAUDE_BIN is not None


def _staging_dir():
    d = REPO_ROOT / "ui" / ".staging"
    d.mkdir(exist_ok=True)
    return d


def _slug(text, fallback="sketch"):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:32].rstrip("-")) or fallback


def _render(spec, out_dir):
    """Validate then render --midi-only. Returns None or an error string."""
    try:
        transforms.validate(spec)
    except transforms.TransformError as e:
        return f"generated spec failed validation: {e}"
    out_dir.mkdir(parents=True, exist_ok=True)
    staged = out_dir / ".agent-spec.json"
    staged.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "composer.py"), "compose",
         "--midi-only", str(staged), str(out_dir)],
        capture_output=True, text=True, timeout=60)
    staged.unlink(missing_ok=True)
    if proc.returncode != 0:
        return f"composer.py failed: {proc.stderr.strip()[:400]}"
    return None


def _song_dir_name(spec, brief):
    key = (spec.get("key") or "x").lower()
    bpm = int(spec.get("tempo") or 0)
    slug = _slug(spec.get("song_name") or brief)
    return f"{key}-{bpm:03d}-{slug}"


def _unique_dir(parent, name):
    d = parent / name
    n = 2
    while d.exists():
        d = parent / f"{name}-{n}"
        n += 1
    return d


# ---------- Tier 2: cold briefs ----------

def run_brief(brief, archive_root, parent_rel="", variety_note="", on_done=None):
    """Spawn a cold `claude -p` for one brief. Returns the Job immediately."""
    job = REGISTRY.add(Job("brief", brief[:80]))

    def work():
        REGISTRY.update(job, status="running", started=_now())
        out_path = _staging_dir() / f"brief-{job.id}.json"
        prompt = BRIEF_PROMPT.format(
            brief=brief, out_path=out_path,
            variety=f"- {variety_note}" if variety_note else "")
        try:
            proc = subprocess.run(
                [CLAUDE_BIN, "-p", prompt,
                 "--permission-mode", "acceptEdits",
                 "--add-dir", str(_staging_dir()),
                 "--output-format", "text"],
                cwd=REPO_ROOT, capture_output=True, text=True,
                timeout=BRIEF_TIMEOUT_S)
            if not out_path.exists():
                tail = (proc.stdout or proc.stderr or "").strip()[-300:]
                REGISTRY.update(job, status="error", finished=_now(),
                                detail=f"agent wrote no spec. {tail}")
                return
            spec = json.loads(out_path.read_text(encoding="utf-8"))

            parent = archive_root / parent_rel if parent_rel else archive_root
            out_dir = _unique_dir(parent, _song_dir_name(spec, brief))
            err = _render(spec, out_dir)
            if err:
                REGISTRY.update(job, status="error", finished=_now(), detail=err)
                return
            rel = out_dir.relative_to(archive_root).as_posix()
            REGISTRY.update(job, status="done", finished=_now(), rel=rel,
                            detail=spec.get("song_name") or "")
            if on_done:
                on_done(job)
        except subprocess.TimeoutExpired:
            REGISTRY.update(job, status="error", finished=_now(),
                            detail=f"timed out after {BRIEF_TIMEOUT_S}s")
        except Exception as e:  # keep the worker thread from dying silently
            REGISTRY.update(job, status="error", finished=_now(),
                            detail=f"{type(e).__name__}: {e}")
        finally:
            out_path.unlink(missing_ok=True)

    threading.Thread(target=work, daemon=True).start()
    return job


# ---------- Tier 1: warm patch session ----------

class WarmSession:
    """One persistent claude stream-json process, primed on a spec.

    A session belongs to one song (the one it was primed on). Re-priming on a
    different song restarts the process — context from the old song would
    otherwise leak into patches for the new one.
    """

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()   # one patch at a time per session
        self.primed_rel = None

    def _alive(self):
        return self._proc is not None and self._proc.poll() is None

    def _start(self):
        self._proc = subprocess.Popen(
            [CLAUDE_BIN, "-p",
             "--input-format", "stream-json",
             "--output-format", "stream-json", "--verbose",
             "--permission-mode", "acceptEdits",
             "--add-dir", str(_staging_dir())],
            cwd=REPO_ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def close(self):
        with self._lock:
            if self._proc:
                try:
                    self._proc.stdin.close()
                    self._proc.terminate()
                except OSError:
                    pass
                self._proc = None
                self.primed_rel = None

    def _turn(self, text, timeout):
        """Send one user turn, return the result event's text (or raise)."""
        msg = {"type": "user",
               "message": {"role": "user",
                           "content": [{"type": "text", "text": text}]}}
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()
        deadline = _now() + timeout
        while _now() < deadline:
            line = self._proc.stdout.readline()
            if not line:
                raise RuntimeError("agent stream closed")
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                if ev.get("is_error"):
                    raise RuntimeError(str(ev.get("result"))[:300])
                return str(ev.get("result") or "")
        raise TimeoutError(f"no result within {timeout}s")

    def ensure_primed(self, rel, spec_path, song_name):
        with self._lock:
            if self._alive() and self.primed_rel == rel:
                return None  # already warm on this song
            job = REGISTRY.add(Job("prime", f"prime on {song_name}"))
            REGISTRY.update(job, status="running", started=_now())
            try:
                if self._alive():
                    self._proc.stdin.close()
                    self._proc.terminate()
                self._start()
                self._turn(PRIME_PROMPT.format(spec_path=spec_path,
                                               song_name=song_name),
                           PRIME_TIMEOUT_S)
                self.primed_rel = rel
                REGISTRY.update(job, status="done", finished=_now())
                return None
            except Exception as e:
                REGISTRY.update(job, status="error", finished=_now(),
                                detail=str(e)[:300])
                self.close()
                return str(e)

    def patch(self, ask, timeout=PATCH_TIMEOUT_S):
        """Run one scoped ask; returns parsed JSON (object or array)."""
        with self._lock:
            if not self._alive():
                raise RuntimeError("session not primed")
            raw = self._turn(PATCH_PROMPT.format(ask=ask), timeout).strip()
        # Defensive unwrap: the contract says no fence, but strip one anyway.
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"[\[{].*[\]}]", raw, re.S)  # salvage embedded JSON
            if m:
                return json.loads(m.group(0))
            raise RuntimeError(f"agent returned non-JSON: {raw[:200]}")


WARM = WarmSession()


def _splice(spec, fragment):
    """Merge a scoped patch fragment into a copy of the spec.

    Fragment shapes we accept, mirroring what PATCH_PROMPT elicits:
      {"name": <existing section>, ...}  -> replace that section
      {"name": <new section>, ...}       -> append to sections (form untouched)
      [{"name": ..., "beats": ...}, ...] -> replace chords of... ambiguous,
                                            so we require {"section": ..., "chords": [...]}
      {"section": <name>, "chords": [...]} -> replace that section's chords
      {full spec with sections+form}     -> take it whole
    """
    out = json.loads(json.dumps(spec))
    if isinstance(fragment, dict) and "sections" in fragment and "form" in fragment:
        return fragment
    if isinstance(fragment, dict) and "chords" in fragment and "section" in fragment:
        for sec in out["sections"]:
            if sec["name"] == fragment["section"]:
                sec["chords"] = fragment["chords"]
                return out
        raise transforms.TransformError(f"no section named {fragment['section']!r}")
    if isinstance(fragment, dict) and "name" in fragment and "chords" in fragment:
        for i, sec in enumerate(out["sections"]):
            if sec["name"] == fragment["name"]:
                out["sections"][i] = fragment
                return out
        out["sections"].append(fragment)
        return out
    raise transforms.TransformError(
        "unrecognised patch shape — expected a section object, "
        '{"section": name, "chords": [...]}, or a full spec')


def run_patch(ask, rel, archive_root, on_done=None):
    """Scoped Tier 1 patch against the song at `rel`. Returns Job immediately.

    The result is rendered as a NEW sibling folder (suffix -p2, -p3, …): a
    patch is a variant to audition next to the original, not an overwrite.
    """
    job = REGISTRY.add(Job("patch", ask[:80]))

    def work():
        REGISTRY.update(job, status="running", started=_now())
        try:
            song_dir = archive_root / rel
            spec = json.loads((song_dir / "spec.json").read_text(encoding="utf-8"))
            err = WARM.ensure_primed(rel, song_dir / "spec.json",
                                     spec.get("song_name") or rel)
            if err:
                REGISTRY.update(job, status="error", finished=_now(),
                                detail=f"prime failed: {err}")
                return
            fragment = WARM.patch(ask)
            patched = _splice(spec, fragment)

            base = song_dir.name
            m = re.match(r"^(.*)-p(\d+)$", base)
            stem = m.group(1) if m else base
            out_dir = _unique_dir(song_dir.parent, f"{stem}-p2")
            err = _render(patched, out_dir)
            if err:
                REGISTRY.update(job, status="error", finished=_now(), detail=err)
                return
            new_rel = out_dir.relative_to(archive_root).as_posix()
            REGISTRY.update(job, status="done", finished=_now(), rel=new_rel)
            if on_done:
                on_done(job)
        except Exception as e:
            REGISTRY.update(job, status="error", finished=_now(),
                            detail=f"{type(e).__name__}: {str(e)[:300]}")

    threading.Thread(target=work, daemon=True).start()
    return job
