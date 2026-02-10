#!/usr/bin/env bash
set -euo pipefail

# Basic CLI usability smoke tests.
# Meant to run in CI/nightly automation.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Expect to run inside an activated venv (.venv) with deps installed.

fail() {
  echo "[usability] ERROR: $*" >&2
  exit 2
}

command -v python >/dev/null 2>&1 || fail "python not found (activate venv first)"
command -v cyberagent >/dev/null 2>&1 || fail "cyberagent entrypoint not found (is package installed?)"

echo "[usability] python: $(python -V)"
echo "[usability] cyberagent: $(command -v cyberagent)"

echo "[usability] cyberagent --help"
cyberagent --help >/dev/null

# A couple of commands that should not crash the CLI. Some may exit non-zero if
# not configured; that's ok as long as output is sane and there's no traceback.
# We treat Python tracebacks as failures.

tmp_out="$(mktemp)"
trap 'rm -f "$tmp_out"' EXIT

echo "[usability] cyberagent status (allow non-zero; forbid traceback)"
set +e
cyberagent status >"$tmp_out" 2>&1
code=$?
set -e
if grep -q "Traceback (most recent call last)" "$tmp_out"; then
  echo "[usability] status produced traceback:" >&2
  sed -n '1,200p' "$tmp_out" >&2
  exit 1
fi

echo "[usability] status exit code: $code"

# Run fast CLI-focused tests if present.
if [ -d tests/cli ]; then
  echo "[usability] pytest tests/cli"
  python -m pytest -q tests/cli
fi

echo "[usability] OK"
