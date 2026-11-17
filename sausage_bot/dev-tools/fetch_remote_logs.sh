#!/usr/bin/env bash
# Download the bot's logs/ directory from the remote server via rsync
# into a timestamped folder under remote_logs/, next to this script.
# Optionally also fetch the per-guild db/ directory for a chosen guild.

set -euo pipefail

[[ -f ./.env ]] || {
  echo ".env missing in $PWD" >&2
  exit 1
}
set -a
source "$(dirname "$0")/.env"
set +a

: "${REMOTE_HOST:?Missing 'REMOTE_HOST'}"
: "${REMOTE_DATA_DIR:?Missing 'REMOTE_DATA_DIR'}"

# Make sure that these variables are correct
REMOTE_LOG_FILES="${REMOTE_DATA_DIR}/logs/bot.log*"
REMOTE_DB_DIR="${REMOTE_DATA_DIR}/db/"

GUILD_ID=""

usage() {
  echo "Usage: $0 [--guild GUILD_ID]" >&2
  echo "  --guild GUILD_ID   Also fetch db/guild_GUILD_ID/ from the server" >&2
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --guild)
    [[ $# -ge 2 ]] || usage
    GUILD_ID="$2"
    shift 2
    ;;
  -h | --help)
    usage
    ;;
  *)
    echo "Unknown argument: $1" >&2
    usage
    ;;
  esac
done

# SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR=$(dirname "$0")
TIMESTAMP="$(date +%Y-%m-%d_%H-%M)"
DEST_DIR="${SCRIPT_DIR}/remote_files/${TIMESTAMP}"
DEST_DIR_SHORT=".../remote_files/${TIMESTAMP}"

if ! command -v rsync >/dev/null 2>&1; then
  echo "Error: rsync is not installed." >&2
  exit 1
fi

mkdir -p "${DEST_DIR}"

echo "Fetching logs from ${REMOTE_HOST}:"
echo "${REMOTE_LOG_FILES} -> ${DEST_DIR_SHORT}"
rsync -e "ssh -i $SSH_KEY_FILE" -avzhq "${REMOTE_HOST}:${REMOTE_LOG_FILES}" "${DEST_DIR}/logs/"

if [[ -n "${GUILD_ID}" ]]; then
  REMOTE_DB_DIR="${REMOTE_DB_DIR}/guild_${GUILD_ID}/*.sqlite"
  DEST_DB_DIR="${DEST_DIR}/db/guild_${GUILD_ID}"
  DEST_DB_DIR_SHORT=".../db/guild_${GUILD_ID}"
  mkdir -p "${DEST_DB_DIR}"
  echo "Fetching db files for guild ${GUILD_ID} from ${REMOTE_HOST}:"
  echo "${REMOTE_DB_DIR} -> ${DEST_DB_DIR_SHORT}"
  rsync -e "ssh -i $SSH_KEY_FILE" -avzhq "${REMOTE_HOST}:${REMOTE_DB_DIR}" "${DEST_DB_DIR}/"
fi

FILE_COUNT=$(find "${DEST_DIR}" -type f | wc -l | tr -d ' ')
echo "Done. ${FILE_COUNT} file(s) saved to ${DEST_DIR}"
