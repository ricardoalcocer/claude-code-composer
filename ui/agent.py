#!/usr/bin/env python3
"""Tiers 1/2: drive a coding agent headless for spec generation and patches.

Two backends, selected at startup (see select_backend):

  claude    Claude Code. Cold `claude -p` per brief; a WARM persistent
            stream-json session per song for scoped patches. This is the
            measured reference path (see ui/README-generation.md).

  opencode  opencode (https://opencode.ai). Cold `opencode run --auto` per
            brief; patches reuse a session id (`-s`) scraped from the prime
            run's JSON events, which is opencode's equivalent of warmth.
            Content travels via a FILE contract — the prompt tells the agent
            to write JSON to a staging path — so we never parse the event
            stream for content, only for the session id. Model comes from
            opencode's own config, or `agent_model` in config.json / the
            COMPOSER_AGENT_MODEL env var (format: provider/model).

Both backends hit the same trust boundary: the agent writes to a staging
file; the JSON is parsed and run through transforms.validate() (composer.py's
own parsers) before composer.py renders it into the archive. Rendered output
is the only thing the UI trusts.

Execution shapes are measurement-driven: brief latency is dominated by token
emission, so cold processes fan out trivially; patch latency would be
dominated by re-reading the 151KB SKILL.md, so both backends prime once per
song and keep that context (process for claude, session for opencode).
"""

import json
import os
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

# Defaults sized from claude measurements (cold brief ~170s); a slower model
# behind opencode may need more — override with the env vars.
BRIEF_TIMEOUT_S = int(os.environ.get("COMPOSER_BRIEF_TIMEOUT_S", 420))
PATCH_TIMEOUT_S = int(os.environ.get("COMPOSER_PATCH_TIMEOUT_S", 180))
PRIME_TIMEOUT_S = int(os.environ.get("COMPOSER_PRIME_TIMEOUT_S", 150))

# The generation contract. Kept terse: every extra instruction token is paid
# on every brief, and SKILL.md already carries the musical doctrine.
BRIEF_PROMPT = """Read SKILL.md in this directory.

Compose a spec for this brief: {brief}

Requirements:
- Write ONLY the spec JSON to {out_path} (use your file-write tool).
- Include `move` and `scales` on every section.
- Do NOT run composer.py. Do not explain anything.
{variety}"""

PRIME_PROMPT = """Read SKILL.md in full. Then read {spec_path} — this is the \
current working spec, named {song_name}. You will be asked for small scoped \
edits to it. Reply with exactly: primed"""

# claude patches return the fragment as the reply (proven live); opencode
# patches write it to a file (robust against any event-stream format).
# The wrapper is mandatory even for chords-only changes — a bare chords array
# doesn't say which section it belongs to, so the splice would have to guess.
_PATCH_SHAPES = """Use exactly one of these JSON shapes:
- a complete section object: {{"name": "<section>", "feel": ..., "chords": [...], ...}}
- chords only: {{"section": "<section name>", "chords": [{{"name": "Em", "beats": 4}}, ...]}}
- insert a NEW section into the form: {{"insert_after_index": <form position>, "section": {{complete section object with a name not already used}}}}
Never a bare array."""

PATCH_PROMPT_REPLY = """{ask}

Return ONLY the JSON for the requested change — the smallest shape that \
covers it. """ + _PATCH_SHAPES + """
Raw JSON only: no prose, no code fence, no file writes."""

PATCH_PROMPT_FILE = """{ask}

Write ONLY the JSON for the requested change — the smallest shape that \
covers it — to {out_path} using your file-write tool. """ + _PATCH_SHAPES + """
Raw JSON in the file, nothing else. Do not reply with the JSON, do not explain."""

RESHAPE_PROMPT = """Your last JSON did not match the required shape ({error}). \
Resend the SAME musical content, reshaped. """ + _PATCH_SHAPES


def _now():
    return time.time()


# ---------- job registry ----------

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
        with self._changed:
            if self._version != seen_version:
                return self._version
            self._changed.wait(timeout)
            return self._version


REGISTRY = JobRegistry()


# ---------- shared helpers ----------

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


def _strip_ansi(text):
    """CLI error output arrives with colour codes; job details shouldn't."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _strip_fence(raw):
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())


def _parse_fragment(raw):
    raw = _strip_fence(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", raw, re.S)  # salvage embedded JSON
        if m:
            return json.loads(m.group(0))
        raise RuntimeError(f"agent returned non-JSON: {raw[:200]}")


# ---------- backend: claude ----------

class ClaudeWarmSession:
    """One persistent claude stream-json process, primed on a spec.

    A session belongs to one song. Re-priming on a different song restarts
    the process — context from the old song must not leak into the new one.
    """

    def __init__(self, binary):
        self.binary = binary
        self._proc = None
        self._lock = threading.Lock()
        self.primed_rel = None

    def _alive(self):
        return self._proc is not None and self._proc.poll() is None

    def _start(self):
        self._proc = subprocess.Popen(
            [self.binary, "-p",
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
                return None
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
        with self._lock:
            if not self._alive():
                raise RuntimeError("session not primed")
            raw = self._turn(PATCH_PROMPT_REPLY.format(ask=ask), timeout)
        return _parse_fragment(raw)


class ClaudeBackend:
    name = "claude"

    def __init__(self):
        self.binary = shutil.which("claude")
        self._session = ClaudeWarmSession(self.binary) if self.binary else None

    @property
    def available(self):
        return self.binary is not None

    def run_brief_blocking(self, prompt, out_path, timeout):
        proc = subprocess.run(
            [self.binary, "-p", prompt,
             "--permission-mode", "acceptEdits",
             "--add-dir", str(_staging_dir()),
             "--output-format", "text"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)
        if not out_path.exists():
            tail = (proc.stdout or proc.stderr or "").strip()[-300:]
            return f"agent wrote no spec. {tail}"
        return None

    def ensure_primed(self, rel, spec_path, song_name):
        return self._session.ensure_primed(rel, spec_path, song_name)

    def run_patch_blocking(self, ask, timeout):
        return self._session.patch(ask, timeout)


# ---------- backend: opencode ----------

def _find_session_id(obj):
    """Recursively find a session id in a JSON event (key name varies)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ("sessionid", "session_id") and isinstance(v, str) and v:
                return v
            found = _find_session_id(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_session_id(item)
            if found:
                return found
    return None


class OpencodeBackend:
    """opencode. Content via file contract; warmth via session-id reuse.

    --auto approves tool calls headless (opencode has no per-directory scope
    like --add-dir; restrict further with a repo-level opencode.json
    `permission` block if you want e.g. bash denied).
    """

    name = "opencode"

    def __init__(self, model=None):
        self.binary = shutil.which("opencode")
        self.model = model or os.environ.get("COMPOSER_AGENT_MODEL")
        self._lock = threading.Lock()   # one patch at a time, same as claude
        # opencode's local state is SQLite: two simultaneous `opencode run`
        # processes fail with "database is locked" (seen live on a 2-take
        # fan-out). Serialize every opencode invocation through this lock —
        # briefs queue instead of failing. claude has no such constraint and
        # keeps true parallel fan-out.
        self._exec_lock = threading.Lock()
        self.session_id = None
        self.primed_rel = None

    @property
    def available(self):
        return self.binary is not None

    def _base_cmd(self):
        cmd = [self.binary, "run", "--auto",
               "--dir", str(REPO_ROOT), "--format", "json"]
        if self.model:
            cmd += ["-m", self.model]
        return cmd

    def _exec(self, cmd, timeout):
        """Run one opencode invocation, serialized; retry once on a db lock.

        The serialization prevents our own runs from colliding; the retry
        covers an interactive opencode (the TUI) briefly holding the lock.
        """
        with self._exec_lock:
            proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True,
                                  text=True, timeout=timeout)
        if proc.returncode != 0 and \
                "database is locked" in ((proc.stderr or "") + (proc.stdout or "")):
            time.sleep(2)
            with self._exec_lock:
                proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True,
                                      text=True, timeout=timeout)
        return proc

    def run_brief_blocking(self, prompt, out_path, timeout):
        proc = self._exec(self._base_cmd() + [prompt], timeout)
        if not out_path.exists():
            tail = _strip_ansi((proc.stderr or proc.stdout or "").strip())[-300:]
            return f"agent wrote no spec (exit {proc.returncode}). {tail}"
        return None

    def ensure_primed(self, rel, spec_path, song_name):
        with self._lock:
            if self.session_id and self.primed_rel == rel:
                return None
            job = REGISTRY.add(Job("prime", f"prime on {song_name}"))
            REGISTRY.update(job, status="running", started=_now())
            try:
                proc = self._exec(
                    self._base_cmd() + ["--title", f"composer:{song_name}",
                                        PRIME_PROMPT.format(spec_path=spec_path,
                                                            song_name=song_name)],
                    PRIME_TIMEOUT_S)
                if proc.returncode != 0:
                    raise RuntimeError(
                        _strip_ansi((proc.stderr or proc.stdout or "").strip())[-300:]
                        or f"exit {proc.returncode}")
                sid = None
                for line in proc.stdout.splitlines():
                    try:
                        sid = _find_session_id(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                    if sid:
                        break
                # No id found → fall back to --continue (last session). Works
                # unless something else uses opencode in this repo meanwhile.
                self.session_id = sid
                self.primed_rel = rel
                REGISTRY.update(job, status="done", finished=_now(),
                                detail=sid or "via --continue")
                return None
            except Exception as e:
                REGISTRY.update(job, status="error", finished=_now(),
                                detail=str(e)[:300])
                self.session_id = None
                self.primed_rel = None
                return str(e)

    def run_patch_blocking(self, ask, timeout):
        with self._lock:
            if self.primed_rel is None:
                raise RuntimeError("session not primed")
            out_path = _staging_dir() / f"patch-{uuid.uuid4().hex[:8]}.json"
            cont = ["-s", self.session_id] if self.session_id else ["-c"]
            try:
                proc = self._exec(
                    self._base_cmd() + cont +
                    [PATCH_PROMPT_FILE.format(ask=ask, out_path=out_path)],
                    timeout)
                if not out_path.exists():
                    tail = _strip_ansi((proc.stderr or proc.stdout or "").strip())[-200:]
                    raise RuntimeError(f"agent wrote no fragment. {tail}")
                return _parse_fragment(out_path.read_text(encoding="utf-8"))
            finally:
                out_path.unlink(missing_ok=True)


# ---------- backend selection ----------

BACKEND = None


def select_backend(choice="auto", model=None, respect_env=True):
    """Pick the agent backend. choice: auto | claude | opencode.

    At startup, env overrides win (COMPOSER_AGENT_BACKEND,
    COMPOSER_AGENT_MODEL); a runtime switch from the UI passes
    respect_env=False so the user's explicit click beats a stale env var.
    Returns the backend (possibly unavailable — the HTTP layer reports that
    instead of failing at startup). Jobs already running keep the backend
    they started on; only new jobs see the switch.
    """
    global BACKEND
    if respect_env:
        choice = os.environ.get("COMPOSER_AGENT_BACKEND") or choice or "auto"
    if choice == "claude":
        BACKEND = ClaudeBackend()
    elif choice == "opencode":
        BACKEND = OpencodeBackend(model)
    else:  # auto: claude is the measured reference path; prefer it when present
        claude = ClaudeBackend()
        BACKEND = claude if claude.available else OpencodeBackend(model)
    return BACKEND


def backend_info():
    b = BACKEND or select_backend()
    return {
        "backend": b.name,
        "available": b.available,
        # What the UI's backend picker can offer, with per-CLI presence.
        "backends": {
            "claude": shutil.which("claude") is not None,
            "opencode": shutil.which("opencode") is not None,
        },
    }


def claude_available():
    """Back-compat shim: 'is generation possible at all'."""
    b = BACKEND or select_backend()
    return b.available


# ---------- Tier 2: cold briefs ----------

def run_brief(brief, archive_root, parent_rel="", variety_note="", on_done=None):
    """Spawn one cold brief on the selected backend. Returns Job immediately."""
    backend = BACKEND or select_backend()
    job = REGISTRY.add(Job("brief", brief[:80]))

    def work():
        REGISTRY.update(job, status="running", started=_now())
        out_path = _staging_dir() / f"brief-{job.id}.json"
        prompt = BRIEF_PROMPT.format(
            brief=brief, out_path=out_path,
            variety=f"- {variety_note}" if variety_note else "")
        try:
            err = backend.run_brief_blocking(prompt, out_path, BRIEF_TIMEOUT_S)
            if err:
                REGISTRY.update(job, status="error", finished=_now(), detail=err)
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


# ---------- Tier 1: scoped patches ----------

def _splice(spec, fragment):
    """Merge a scoped patch fragment into a copy of the spec.

    Accepted shapes, mirroring what the patch prompts elicit:
      {"name": <existing section>, ...}    -> replace that section
      {"name": <new section>, ...}         -> append (form untouched)
      {"section": <name>, "chords": [...]} -> replace that section's chords
      {full spec with sections+form}       -> take it whole
    """
    out = json.loads(json.dumps(spec))
    if isinstance(fragment, dict) and "sections" in fragment and "form" in fragment:
        return fragment
    if isinstance(fragment, dict) and "insert_after_index" in fragment \
            and isinstance(fragment.get("section"), dict):
        idx = int(fragment["insert_after_index"])
        sec = fragment["section"]
        if not sec.get("name"):
            raise transforms.TransformError("inserted section needs a name")
        if not 0 <= idx < len(out["form"]):
            raise transforms.TransformError(
                f"insert_after_index {idx} out of range for a form of "
                f"{len(out['form'])} entries")
        # Reusing an existing name would silently rewrite every occurrence of
        # that section in the form — an insert must be a genuinely new part.
        if any(s["name"] == sec["name"] for s in out["sections"]):
            raise transforms.TransformError(
                f"section name {sec['name']!r} already exists — "
                "an inserted section needs a new name")
        out["sections"].append(sec)
        out["form"].insert(idx + 1, sec["name"])
        return out
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

    The result renders as a NEW sibling folder (-p2, -p3, …): a patch is a
    variant to audition next to the original, not an overwrite.
    """
    backend = BACKEND or select_backend()
    job = REGISTRY.add(Job("patch", ask[:80]))

    def work():
        REGISTRY.update(job, status="running", started=_now())
        try:
            song_dir = archive_root / rel
            spec = json.loads((song_dir / "spec.json").read_text(encoding="utf-8"))
            err = backend.ensure_primed(rel, song_dir / "spec.json",
                                        spec.get("song_name") or rel)
            if err:
                REGISTRY.update(job, status="error", finished=_now(),
                                detail=f"prime failed: {err}")
                return
            fragment = backend.run_patch_blocking(ask, PATCH_TIMEOUT_S)
            try:
                patched = _splice(spec, fragment)
            except transforms.TransformError as e:
                # Wrong shape, right content is the common failure — one
                # corrective turn is cheap on a warm session, so ask the agent
                # to reshape what it already decided rather than erroring out.
                REGISTRY.update(job, detail="reshaping fragment…")
                fragment = backend.run_patch_blocking(
                    RESHAPE_PROMPT.format(error=str(e)[:120]), PATCH_TIMEOUT_S)
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
