#!/usr/bin/env bash
# One-command launch for the composer UI:
#
#   ./start-ui.sh                 # build if needed, serve, open browser
#   ./start-ui.sh --port 9000     # extra args pass through to ui/server.py
#   NO_OPEN=1 ./start-ui.sh       # don't pop the browser (e.g. over SSH)
#
# Builds the front end only when it's missing or stale, then runs the single
# stdlib Python server (API + built UI on one port). Ctrl-C stops everything —
# there is exactly one process.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "error: python3 not found" >&2; exit 1
fi

# --- build the front end if missing or stale -------------------------------
needs_build=0
if [ ! -d ui/dist ]; then
  needs_build=1
elif [ -n "$(find ui/src ui/index.html ui/package.json ui/vite.config.ts \
              -type f -newer ui/dist -print -quit 2>/dev/null)" ]; then
  needs_build=1
fi

if [ "$needs_build" = 1 ]; then
  if ! command -v npm >/dev/null; then
    echo "error: UI needs building but npm was not found." >&2
    echo "Install Node 18+ (https://nodejs.org) and re-run." >&2
    exit 1
  fi
  echo "building UI (first run or sources changed)…"
  ( cd ui
    [ -d node_modules ] || npm install --no-audit --no-fund
    npm run build )
  # Refresh dist's own mtime so the staleness probe is quiet next time.
  touch ui/dist
fi

# --- gentle preflight ------------------------------------------------------
command -v claude >/dev/null || \
  echo "note: claude CLI not on PATH — generation will be disabled; audition still works"
[ -f config.json ] || \
  echo "note: no config.json — archive defaults to ~/Documents/MIDI-SONGS (cp config.example.json config.json to change)"

# --- run -------------------------------------------------------------------
open_flag="--open"
[ "${NO_OPEN:-0}" = 1 ] && open_flag=""
exec python3 ui/server.py $open_flag "$@"
