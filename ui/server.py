#!/usr/bin/env python3
"""Local bridge between the composer archive and the React UI.

Stdlib only, same as composer.py — no pip install, no venv. It does three things:

  1. Walks <output_root> and reports every folder that has a spec.json in it.
  2. Serves those spec.json / .mid files to the browser.
  3. Shells out to composer.py when the UI asks to regenerate a spec.

It is a localhost development tool. Every path that comes in from the browser is
resolved and checked against <output_root> before anything is opened, so a
crafted request can't read outside the archive.

    python3 ui/server.py                # serves ui/dist if built, API on :8722
    python3 ui/server.py --port 9000
    python3 ui/server.py --root ~/other-midi-songs
"""

import argparse
import json
import mimetypes
import re
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent  # noqa: E402
import transforms  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSER_PY = REPO_ROOT / "composer.py"
SKILL_MD = REPO_ROOT / "SKILL.md"
DIST_DIR = Path(__file__).resolve().parent / "dist"

# <key>-<bpm>-<slug>, e.g. "f#m-104-blue-meridian". Older folders that predate the
# convention simply don't match and fall back to the raw folder name.
SONG_DIR_RE = re.compile(r"^(?P<key>[A-Ga-g][#b]?m?)-(?P<bpm>\d{2,4})-(?P<slug>.+)$")

# Depth limit while walking the archive. output_root/_2026/composer/week-x/song is 4.
MAX_WALK_DEPTH = 6


# ---------- config ----------

def load_output_root(override=None):
    """Resolve the archive root: --root wins, then config.json, then the default."""
    if override:
        return Path(override).expanduser().resolve()
    cfg_path = REPO_ROOT / "config.json"
    if cfg_path.exists():
        try:
            with open(cfg_path) as f:
                cfg = json.load(f)
            root = cfg.get("output_root")
            if root:
                return Path(root).expanduser().resolve()
        except (json.JSONDecodeError, OSError):
            pass
    return (Path.home() / "Documents" / "MIDI-SONGS").resolve()


# ---------- archive walking ----------

def describe_song_dir(song_dir, root):
    """Build the library entry for one folder that contains a spec.json."""
    rel = song_dir.relative_to(root).as_posix()
    spec_path = song_dir / "spec.json"
    entry = {
        "rel": rel,
        "dir_name": song_dir.name,
        "group": song_dir.parent.relative_to(root).as_posix() if song_dir.parent != root else "",
        "key": None,
        "bpm": None,
        "slug": song_dir.name,
        "song_name": None,
        "sections": 0,
        "form_length": 0,
        "roles": [],
        "has_rpp": False,
        "has_full_mid": (song_dir / "full.mid").exists(),
        "mtime": spec_path.stat().st_mtime if spec_path.exists() else 0,
    }

    m = SONG_DIR_RE.match(song_dir.name)
    if m:
        entry["key"] = m.group("key")
        entry["bpm"] = int(m.group("bpm"))
        entry["slug"] = m.group("slug")

    try:
        with open(spec_path) as f:
            spec = json.load(f)
    except (json.JSONDecodeError, OSError):
        entry["broken"] = True
        return entry

    entry["song_name"] = spec.get("song_name")
    entry["sections"] = len(spec.get("sections", []))
    entry["form_length"] = len(spec.get("form", []))
    entry["roles"] = list(spec.get("roles", [])) or None
    # spec.json is the source of truth for key/tempo; folder name is only a hint.
    entry["key"] = spec.get("key") or entry["key"]
    entry["bpm"] = spec.get("tempo") or entry["bpm"]
    entry["has_rpp"] = any(song_dir.glob("*.RPP"))
    return entry


def walk_library(root):
    """Every directory under root holding a spec.json, newest first."""
    if not root.is_dir():
        return []
    found = []

    def rec(d, depth):
        if depth > MAX_WALK_DEPTH:
            return
        try:
            children = sorted(d.iterdir())
        except (PermissionError, OSError):
            return
        if (d / "spec.json").is_file() and d != root:
            found.append(describe_song_dir(d, root))
            return  # a song folder is a leaf — don't descend into it
        for c in children:
            if c.is_dir() and not c.name.startswith("."):
                rec(c, depth + 1)

    rec(root, 0)
    found.sort(key=lambda e: e["mtime"], reverse=True)
    return found


# ---------- SKILL.md catalog extraction ----------

_catalog_cache = {"mtime": None, "data": None}


def parse_catalogs():
    """Pull the browsable catalog headings out of SKILL.md.

    Purely for the reference panel — the UI shows you what vocabulary exists so
    you can name it in your next brief to Claude. We only read heading text, so
    this stays correct as the catalogs grow.
    """
    if not SKILL_MD.exists():
        return {}
    mtime = SKILL_MD.stat().st_mtime
    if _catalog_cache["mtime"] == mtime:
        return _catalog_cache["data"]

    try:
        text = SKILL_MD.read_text(encoding="utf-8")
    except OSError:
        return {}

    # Sections we want to surface, keyed by the "## " heading prefix in SKILL.md.
    wanted = {
        "Style packs": "style_packs",
        "Song forms catalog": "song_forms",
        "Arrangement archetypes catalog": "archetypes",
        "Moves library": "moves",
    }

    lines = text.splitlines()
    # Locate each top-level section's line range.
    tops = [(i, ln[3:].strip()) for i, ln in enumerate(lines) if ln.startswith("## ")]
    out = {}
    for idx, (line_no, title) in enumerate(tops):
        key = next((v for k, v in wanted.items() if title.startswith(k)), None)
        if not key:
            continue
        end = tops[idx + 1][0] if idx + 1 < len(tops) else len(lines)
        # Sub-headings (### / ####) inside the section are the catalog entries.
        entries = []
        for ln in lines[line_no + 1:end]:
            if ln.startswith("### ") or ln.startswith("#### "):
                name = ln.lstrip("#").strip()
                # Strip markdown emphasis and trailing parenthetical asides.
                name = re.sub(r"[*_`]", "", name).strip()
                if name:
                    entries.append(name)
        out[key] = {"title": title, "entries": entries}

    _catalog_cache["mtime"] = mtime
    _catalog_cache["data"] = out
    return out


# ---------- OS integration ----------

def _open_with_os(path):
    """Hand a file (or URL) to the OS default opener. Best-effort: a headless
    box has no opener, and that must not fail the API call that asked."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith("win"):
            import os
            os.startfile(str(path))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


# ---------- library change signal ----------
# Bumped whenever anything rewrites the archive (transform, generate, patch,
# promote, browser regenerate) so /api/events subscribers refresh instantly.
# A slow mtime poll backs it up for songs written by Claude in a terminal.

_library_version = 0
_library_cond = threading.Condition()


def bump_library():
    global _library_version
    with _library_cond:
        _library_version += 1
        _library_cond.notify_all()


def _mtime_fingerprint(root):
    """Cheap change detector for external writers (Claude in a terminal)."""
    if not root.is_dir():
        return 0
    newest = 0.0
    count = 0
    for p in root.rglob("spec.json"):
        count += 1
        try:
            newest = max(newest, p.stat().st_mtime)
        except OSError:
            pass
    return hash((count, newest))


def _watch_archive(root, interval=2.0):
    last = _mtime_fingerprint(root)
    while True:
        time.sleep(interval)
        cur = _mtime_fingerprint(root)
        if cur != last:
            last = cur
            bump_library()


# ---------- request handler ----------

class Handler(BaseHTTPRequestHandler):
    server_version = "ComposerUI/0.1"
    root = None           # set on the server instance at startup
    compose_lock = threading.Lock()

    # -- helpers --

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, status, message):
        self._json({"error": message}, status=status)

    def _safe_song_dir(self, rel):
        """Resolve a browser-supplied relative path, refusing anything outside root."""
        if rel is None:
            raise ValueError("missing 'rel' parameter")
        candidate = (self.root / rel).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise ValueError("path escapes the archive root")
        if not candidate.is_dir():
            raise ValueError(f"not a directory: {rel}")
        return candidate

    def log_message(self, fmt, *args):  # quieter than the default access log
        if "--verbose" in sys.argv:
            super().log_message(fmt, *args)

    # -- routing --

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path == "/api/config":
                return self.api_config()
            if path == "/api/library":
                return self.api_library()
            if path == "/api/song":
                return self.api_song(qs)
            if path == "/api/file":
                return self.api_file(qs)
            if path == "/api/catalog":
                return self._json(parse_catalogs())
            if path == "/api/jobs":
                return self._json({"jobs": agent.REGISTRY.snapshot()[1],
                                   "claude_available": agent.claude_available()})
            if path == "/api/events":
                return self.api_events()
            if path.startswith("/api/"):
                return self._err(404, f"no such endpoint: {path}")
            return self.serve_static(path)
        except ValueError as e:
            return self._err(400, str(e))
        except Exception as e:  # surface real errors to the UI instead of a blank 500
            traceback.print_exc()
            return self._err(500, f"{type(e).__name__}: {e}")

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/compose":
                return self.api_compose()
            if parsed.path == "/api/transform":
                return self.api_transform()
            if parsed.path == "/api/generate":
                return self.api_generate()
            if parsed.path == "/api/patch":
                return self.api_patch()
            if parsed.path == "/api/promote":
                return self.api_promote()
            if parsed.path == "/api/discard":
                return self.api_discard()
            return self._err(404, f"no such endpoint: {parsed.path}")
        except ValueError as e:
            return self._err(400, str(e))
        except Exception as e:
            traceback.print_exc()
            return self._err(500, f"{type(e).__name__}: {e}")

    # -- endpoints --

    def api_config(self):
        cfg_exists = (REPO_ROOT / "config.json").exists()
        return self._json({
            "output_root": str(self.root),
            "output_root_exists": self.root.is_dir(),
            "repo_root": str(REPO_ROOT),
            "has_config_json": cfg_exists,
            "composer_present": COMPOSER_PY.is_file(),
        })

    def api_library(self):
        return self._json({"root": str(self.root), "songs": walk_library(self.root)})

    def api_song(self, qs):
        song_dir = self._safe_song_dir((qs.get("rel") or [None])[0])
        spec_path = song_dir / "spec.json"
        if not spec_path.is_file():
            raise ValueError("no spec.json in that folder")
        with open(spec_path) as f:
            spec = json.load(f)
        return self._json({
            "rel": song_dir.relative_to(self.root).as_posix(),
            "spec": spec,
            "files": [{"name": p.name, "size": p.stat().st_size}
                      for p in sorted(song_dir.iterdir()) if p.is_file()],
        })

    def api_file(self, qs):
        song_dir = self._safe_song_dir((qs.get("rel") or [None])[0])
        name = (qs.get("name") or [None])[0]
        if not name:
            raise ValueError("missing 'name' parameter")
        # Reject any separator outright — files live flat inside a song folder.
        if "/" in name or "\\" in name or name in (".", ".."):
            raise ValueError("invalid file name")
        target = (song_dir / name).resolve()
        try:
            target.relative_to(self.root)
        except ValueError:
            raise ValueError("path escapes the archive root")
        if not target.is_file():
            raise ValueError(f"no such file: {name}")

        ctype = "audio/midi" if target.suffix.lower() == ".mid" else (
            mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def api_compose(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise ValueError("empty request body")
        payload = json.loads(self.rfile.read(length))

        spec = payload.get("spec")
        if not isinstance(spec, dict):
            raise ValueError("body must include a 'spec' object")
        for required in ("tempo", "sections", "form"):
            if required not in spec:
                raise ValueError(f"spec is missing required field '{required}'")

        rel = payload.get("rel")
        midi_only = bool(payload.get("midi_only", False))

        if rel:
            out_dir = self._safe_song_dir(rel)
        else:
            # New song: place it under <root>/_<year>/composer/<key>-<bpm>-<slug>,
            # matching the layout SKILL.md tells Claude to use.
            name = payload.get("dir_name")
            if not name:
                raise ValueError("provide 'rel' to regenerate, or 'dir_name' to create")
            if "/" in name or "\\" in name or name.startswith("."):
                raise ValueError("invalid dir_name")
            parent = payload.get("parent_rel") or ""
            base = (self.root / parent).resolve() if parent else self.root
            try:
                base.relative_to(self.root)
            except ValueError:
                raise ValueError("parent_rel escapes the archive root")
            out_dir = base / name
            out_dir.mkdir(parents=True, exist_ok=True)

        spec_file = out_dir / ".ui-spec.json"
        spec_file.write_text(json.dumps(spec, indent=2), encoding="utf-8")

        cmd = [sys.executable, str(COMPOSER_PY), "compose"]
        if midi_only:
            cmd.append("--midi-only")
        cmd += [str(spec_file), str(out_dir)]

        # composer.py rewrites a whole song folder; serialise so two browser tabs
        # can't interleave writes into the same directory.
        with self.compose_lock:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        spec_file.unlink(missing_ok=True)
        if proc.returncode == 0:
            bump_library()

        return self._json({
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "rel": out_dir.relative_to(self.root).as_posix(),
            "midi_only": midi_only,
        })

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise ValueError("empty request body")
        return json.loads(self.rfile.read(length))

    def _load_spec(self, rel):
        song_dir = self._safe_song_dir(rel)
        spec_path = song_dir / "spec.json"
        if not spec_path.is_file():
            raise ValueError("no spec.json in that folder")
        with open(spec_path) as f:
            return song_dir, json.load(f)

    @staticmethod
    def _unique_sibling(song_dir, suffix):
        base = f"{song_dir.name}-{suffix}"
        out = song_dir.parent / base
        n = 2
        while out.exists():
            out = song_dir.parent / f"{base}-{n}"
            n += 1
        return out

    def api_transform(self):
        """Tier 0: apply a deterministic transform, render a sibling variant."""
        body = self._read_body()
        rel, op, arg = body.get("rel"), body.get("op"), body.get("arg")
        song_dir, spec = self._load_spec(rel)
        try:
            out_spec = transforms.apply(spec, op, arg)
        except transforms.TransformError as e:
            raise ValueError(str(e))

        # Variant folder name mirrors the op: em-135-iron-mile-t+7, -96bpm, -7-8…
        def suffix_for(op, arg):
            if op == "transpose":
                return f"t{int(arg):+d}"
            if op == "tempo":
                return f"{int(float(arg))}bpm"
            if op == "rebar":
                return str(arg).replace("/", "-")
            if op == "thin":
                return "thin"
            return re.sub(r"[^a-z0-9+-]+", "-", f"{op}-{arg}".lower()).strip("-")

        out_dir = self._unique_sibling(song_dir, suffix_for(op, arg))

        t0 = time.perf_counter()
        out_dir.mkdir(parents=True)
        staged = out_dir / ".transform-spec.json"
        staged.write_text(json.dumps(out_spec, indent=2), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(COMPOSER_PY), "compose", "--midi-only",
             str(staged), str(out_dir)],
            capture_output=True, text=True, timeout=60)
        staged.unlink(missing_ok=True)
        if proc.returncode != 0:
            return self._json({"ok": False, "error": proc.stderr.strip()[:400]}, 500)
        bump_library()
        return self._json({
            "ok": True,
            "rel": out_dir.relative_to(self.root).as_posix(),
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        })

    def api_generate(self):
        """Tier 2: fan out N cold briefs. Returns job ids immediately."""
        body = self._read_body()
        brief = (body.get("brief") or "").strip()
        if not brief:
            raise ValueError("missing 'brief'")
        count = max(1, min(int(body.get("count") or 1), 8))
        parent_rel = body.get("parent_rel") or ""
        if parent_rel:
            self._safe_song_dir(parent_rel)  # validates containment
        if not agent.claude_available():
            raise ValueError("claude CLI not found on PATH — generation needs "
                             "Claude Code installed on this machine")
        jobs = []
        for i in range(count):
            variety = ("Make this take clearly different from other takes on the "
                       "same brief: vary form, archetype, and harmonic strategy. "
                       f"This is take {i + 1} of {count}.") if count > 1 else ""
            jobs.append(agent.run_brief(
                brief, self.root, parent_rel, variety,
                on_done=lambda j: bump_library()).to_dict())
        return self._json({"ok": True, "jobs": jobs})

    def api_patch(self):
        """Tier 1: scoped patch via the warm session. Returns job id."""
        body = self._read_body()
        rel, ask = body.get("rel"), (body.get("ask") or "").strip()
        if not ask:
            raise ValueError("missing 'ask'")
        self._load_spec(rel)  # validates rel + spec presence
        if not agent.claude_available():
            raise ValueError("claude CLI not found on PATH")
        job = agent.run_patch(ask, rel, self.root,
                              on_done=lambda j: bump_library())
        return self._json({"ok": True, "job": job.to_dict()})

    def api_promote(self):
        """Render the full REAPER project for a kept sketch (the keeper path).

        With open_in_reaper (default true) the .RPP is handed to the OS —
        which opens REAPER for a .RPP association — so "promote" IS "take it
        to REAPER", one click, not a render followed by a Finder hunt.
        """
        body = self._read_body()
        song_dir, spec = self._load_spec(body.get("rel"))
        staged = song_dir / ".promote-spec.json"
        staged.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(COMPOSER_PY), "compose", str(staged), str(song_dir)],
            capture_output=True, text=True, timeout=120)
        staged.unlink(missing_ok=True)
        if proc.returncode != 0:
            return self._json({"ok": False,
                               "error": proc.stderr.strip()[:400] or "compose failed"}, 500)
        bump_library()
        rpp = next(song_dir.glob("*.RPP"), None)
        opened = False
        if rpp and body.get("open_in_reaper", True):
            opened = _open_with_os(rpp)
        return self._json({"ok": True, "rpp": rpp.name if rpp else None,
                           "path": str(rpp) if rpp else None, "opened": opened})

    def api_discard(self):
        """Move a sketch to <root>/.bin — the "didn't inspire, next" action.

        A move, not a delete: dot-dirs are invisible to the library walk, so
        the sketch vanishes from the UI but survives on disk. Empty the .bin
        folder yourself whenever you like.
        """
        body = self._read_body()
        song_dir = self._safe_song_dir(body.get("rel"))
        if song_dir == self.root:
            raise ValueError("refusing to discard the archive root")
        bin_dir = self.root / ".bin"
        bin_dir.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = bin_dir / f"{stamp}-{song_dir.name}"
        n = 2
        while target.exists():
            target = bin_dir / f"{stamp}-{song_dir.name}-{n}"
            n += 1
        import shutil
        shutil.move(str(song_dir), str(target))
        bump_library()
        return self._json({"ok": True,
                           "binned_to": target.relative_to(self.root).as_posix()})

    def api_events(self):
        """SSE: pushes {library, jobs} versions so the UI refreshes live."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        lib_seen = -1
        jobs_seen = -1
        try:
            while True:
                with _library_cond:
                    lib_now = _library_version
                jobs_now = agent.REGISTRY.snapshot()[0]
                if lib_now != lib_seen or jobs_now != jobs_seen:
                    lib_seen, jobs_seen = lib_now, jobs_now
                    payload = json.dumps({"library": lib_now, "jobs": jobs_now})
                    self.wfile.write(f"data: {payload}\n\n".encode())
                    self.wfile.flush()
                else:
                    # Wait on job changes (they're the frequent ones); the
                    # timeout doubles as the library poll and keep-alive tick.
                    agent.REGISTRY.wait_change(jobs_seen, timeout=2.0)
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return  # client went away — normal

    # -- static files (production build) --

    def serve_static(self, path):
        if not DIST_DIR.is_dir():
            msg = (
                "<h1>UI not built</h1>"
                "<p>The API is running. For the interface, either:</p>"
                "<pre>cd ui &amp;&amp; npm install &amp;&amp; npm run dev</pre>"
                "<p>(dev server on :5173, proxies /api here)</p>"
                "<p>or build it once:</p>"
                "<pre>cd ui &amp;&amp; npm install &amp;&amp; npm run build</pre>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return

        rel = path.lstrip("/") or "index.html"
        target = (DIST_DIR / rel).resolve()
        try:
            target.relative_to(DIST_DIR)
        except ValueError:
            return self._err(400, "bad path")
        if not target.is_file():
            target = DIST_DIR / "index.html"  # SPA fallback
        data = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8722)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--root", default=None,
                    help="archive root (default: output_root from config.json)")
    ap.add_argument("--verbose", action="store_true", help="log every request")
    ap.add_argument("--open", action="store_true",
                    help="open the UI in the default browser once serving")
    args = ap.parse_args()

    root = load_output_root(args.root)
    Handler.root = root

    # Background watcher: notices songs written by Claude in a terminal (or
    # anything else) and pushes them to /api/events subscribers.
    threading.Thread(target=_watch_archive, args=(root,), daemon=True).start()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"composer-ui api  → http://{args.host}:{args.port}")
    print(f"archive root     → {root}" + ("" if root.is_dir() else "  (does not exist yet)"))
    print(f"claude CLI       → {'found — generation enabled' if agent.claude_available() else 'NOT FOUND — generation disabled, audition still works'}")
    if not DIST_DIR.is_dir():
        print("ui not built     → run `cd ui && npm install && npm run dev` in another terminal")
    if args.open:
        # Delay a beat so the first request hits a listening socket.
        threading.Timer(0.4, _open_with_os,
                        args=(f"http://{args.host}:{args.port}",)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
