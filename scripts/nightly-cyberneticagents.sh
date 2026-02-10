#!/usr/bin/env bash
set -euo pipefail

# Nightly runner for CyberneticAgents.
# - syncs to origin/main
# - bootstraps Python env using uv (no system pip/venv required)
# - runs usability tests
# - leaves logs under logs/nightly/

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPO_SSH="git@github.com:simonvanlaak/CyberneticAgents.git"
BRANCH_MAIN="main"

MAX_RUNTIME_SECONDS=$((2 * 60 * 60))

LOG_DIR="$ROOT_DIR/logs/nightly"
mkdir -p "$LOG_DIR"
RUN_TS="$(date -u +"%Y%m%dT%H%M%SZ")"
LOG_FILE="$LOG_DIR/nightly-${RUN_TS}.log"

# Ensure local toolchain
export PATH="$HOME/.local/bin:$PATH"

log() { echo "[$(date -u +"%F %T") UTC] $*"; }

{
  log "nightly start"
  log "root: $ROOT_DIR"

  if ! command -v git >/dev/null 2>&1; then
    echo "git not found" >&2
    exit 2
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found" >&2
    exit 2
  fi

  # Install uv locally if needed
  if ! command -v uv >/dev/null 2>&1; then
    log "uv not found; installing locally"
    mkdir -p "$HOME/.local/bin"
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT
    UV_VER="0.4.30"
    URL="https://github.com/astral-sh/uv/releases/download/${UV_VER}/uv-x86_64-unknown-linux-gnu.tar.gz"
    curl -fsSL "$URL" -o "$tmpdir/uv.tgz"
    tar -xzf "$tmpdir/uv.tgz" -C "$tmpdir"
    cp "$tmpdir/uv-x86_64-unknown-linux-gnu/uv" "$HOME/.local/bin/uv"
    chmod +x "$HOME/.local/bin/uv"
  fi

  log "uv: $(uv --version)"

  # Safety: ensure correct remote
  if [ ! -d .git ]; then
    echo "Not a git repo: $ROOT_DIR" >&2
    exit 2
  fi

  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "$REPO_SSH"
  fi

  # Sync to origin/main
  log "syncing to origin/${BRANCH_MAIN}"
  git fetch origin --prune
  git checkout "$BRANCH_MAIN"

  # If local main is ahead (e.g. you're running this script to validate a commit
  # before pushing), do not discard local commits.
  ahead_count="$(git rev-list --count "origin/${BRANCH_MAIN}..HEAD" 2>/dev/null || echo 0)"
  if [ "${ahead_count}" = "0" ]; then
    git reset --hard "origin/${BRANCH_MAIN}"
  else
    log "local ${BRANCH_MAIN} is ahead of origin/${BRANCH_MAIN} by ${ahead_count} commit(s); skipping hard reset"
  fi

  # Optional: if GitLab CI is failing, open a GitHub issue with details and
  # move it to the top of Project #1 (Ready).
  # Safe-by-default: script exits 0 when not configured.
  if [ -x ./scripts/gitlab_ci_failure_to_github_issue.sh ]; then
    log "checking GitLab CI (best-effort)"
    bash ./scripts/gitlab_ci_failure_to_github_issue.sh || true
  fi

  # Python env
  export UV_LINK_MODE=copy
  VENV_DIR="$ROOT_DIR/.venv"
  if [ ! -d "$VENV_DIR" ]; then
    log "creating venv at $VENV_DIR"
    uv venv "$VENV_DIR"
  fi

  # Install deps
  log "installing (editable)"
  uv pip install -U pip setuptools wheel
  uv pip install -e .

  # Activate venv for usability script convenience
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  log "running usability"
  if command -v timeout >/dev/null 2>&1; then
    timeout --preserve-status "${MAX_RUNTIME_SECONDS}" bash ./scripts/usability.sh
  else
    # Fallback: no timeout available
    bash ./scripts/usability.sh
  fi

  log "nightly OK"
} 2>&1 | tee "$LOG_FILE"
