#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${GREEN_CHECK_SCRAPER_DIR:-/opt/greencheck-facebook-scraper}"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
LOCK_FILE="$PROJECT_DIR/.runtime/scrape.lock"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$PROJECT_DIR/.runtime" "$LOG_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  printf '%s skipped: another scraper cycle is active\n' "$(date --iso-8601=seconds)" >> "$LOG_DIR/scraper.log"
  exit 0
fi

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
  printf '%s error: .env is missing\n' "$(date --iso-8601=seconds)" >> "$LOG_DIR/scraper.log"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$PROJECT_DIR/.env"
set +a
export GREENCHECK_API_BASE_URL="${GREENCHECK_API_BASE_URL:-http://127.0.0.1:18000}"
export GREENCHECK_API_CLIENT_ID="${GREENCHECK_API_CLIENT_ID:-roman-home-facebook-scraper}"
export GREENCHECK_API_SCHEMA_VERSION="${GREENCHECK_API_SCHEMA_VERSION:-1.0}"

cd "$PROJECT_DIR"
printf '%s starting scraper cycle\n' "$(date --iso-8601=seconds)" >> "$LOG_DIR/scraper.log"
api_health="${GREENCHECK_API_BASE_URL%/}/health"
for _ in $(seq 1 30); do
  if curl --fail --silent --show-error --max-time 3 "$api_health" >/dev/null 2>&1; then
    exec "$VENV_PYTHON" main3.py
  fi
  sleep 1
done
printf '%s error: Green Check API tunnel unavailable\n' "$(date --iso-8601=seconds)" >> "$LOG_DIR/scraper.log"
exit 1
