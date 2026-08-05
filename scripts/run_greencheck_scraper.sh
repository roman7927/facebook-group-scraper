#!/bin/zsh
# launchd entrypoint: source local secrets, prevent overlap, and retain logs.
set -eu

PROJECT_DIR="/Users/rrodichev/Projects/fbscraper/github-scraper"
VENV_PYTHON="$PROJECT_DIR/../.venv/bin/python"
LOCK_DIR="$PROJECT_DIR/.runtime/scrape.lock"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$PROJECT_DIR/.runtime" "$LOG_DIR"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  print -r -- "$(date '+%Y-%m-%dT%H:%M:%S%z') skipped: another scraper cycle is active" >> "$LOG_DIR/scraper.log"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT INT TERM

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
  print -r -- "$(date '+%Y-%m-%dT%H:%M:%S%z') error: .env is missing" >> "$LOG_DIR/scraper.log"
  exit 1
fi

set -a
source "$PROJECT_DIR/.env"
set +a
export GREENCHECK_API_BASE_URL="${GREENCHECK_API_BASE_URL:-http://127.0.0.1:18000}"
export GREENCHECK_API_CLIENT_ID="${GREENCHECK_API_CLIENT_ID:-roman-home-facebook-scraper}"
export GREENCHECK_API_SCHEMA_VERSION="${GREENCHECK_API_SCHEMA_VERSION:-1.0}"

cd "$PROJECT_DIR"
print -r -- "$(date '+%Y-%m-%dT%H:%M:%S%z') starting scraper cycle" >> "$LOG_DIR/scraper.log"
"$VENV_PYTHON" main3.py >> "$LOG_DIR/scraper.log" 2>> "$LOG_DIR/scraper-error.log"
