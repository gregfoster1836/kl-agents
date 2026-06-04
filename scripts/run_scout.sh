#!/bin/bash
# ---------------------------------------------------------------------------
# run_scout.sh — launchd entry point for the Scout agent.
#
# launchd cannot run Python cleanly on its own (no PATH, no cwd, no shell
# init). This wrapper owns the bridge: set a sane PATH, cd to the repo so the
# in-repo .env + config.yaml resolve, run Scout via the project venv, and
# record the outcome. Secrets load the normal way — config.py calls
# load_dotenv() against the repo's .env; the wrapper does NOT source secrets.
#
# Scheduled by: ~/Library/LaunchAgents/com.knifeledger.scout.plist (daily 7am).
# Logs: ~/Library/Logs/kl-scout/{stdout,stderr}.log (launchd-captured)
#       ~/Library/Logs/kl-scout/runs.log           (one line per run, this script)
#
# Exit codes are Scout's own (agents/scout/main.py):
#   0 success · 1 partial (some source failed, some posts landed) · 2 fatal
# The wrapper preserves Scout's exit code so launchd + runs.log reflect truth.
# SOURCE: --source youtube while Reddit API approval is pending. Scout's config
# fatals (exit 2) on `--source all` when REDDIT_CLIENT_ID is absent — it refuses
# to start before any source runs. youtube-only runs clean today; flip the
# --source line below to `all` once Reddit creds work. No code change needed.
# ---------------------------------------------------------------------------
set -uo pipefail

REPO_DIR="$HOME/00-coding/active/03 KL Agents"
VENV_PY="$REPO_DIR/.venv/bin/python"
LOG_DIR="$HOME/Library/Logs/kl-scout"
RUNS_LOG="$LOG_DIR/runs.log"

mkdir -p "$LOG_DIR"

log_run() {
  # JSON line: timestamp, exit code, human status. Append-only audit trail.
  local code="$1" status="$2" ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  printf '{"ts":"%s","exit":%s,"status":"%s"}\n' "$ts" "$code" "$status" >> "$RUNS_LOG" || true
}

# A minimal, predictable PATH. launchd hands jobs an almost-empty environment.
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

if [[ ! -x "$VENV_PY" ]]; then
  log_run "127" "venv-python-missing"
  echo "run_scout.sh: venv python not found at $VENV_PY" >&2
  exit 127
fi

cd "$REPO_DIR" || { log_run "126" "cd-failed"; echo "run_scout.sh: cannot cd to $REPO_DIR" >&2; exit 126; }

# Run Scout. config.yaml + .env resolve from cwd. youtube-only while Reddit
# approval pends (see header) — change to `--source all` when Reddit lands.
"$VENV_PY" -m agents.scout.main --source youtube
code=$?

case "$code" in
  0) log_run "$code" "success" ;;
  1) log_run "$code" "partial" ;;
  2) log_run "$code" "fatal" ;;
  *) log_run "$code" "unknown" ;;
esac

exit "$code"
