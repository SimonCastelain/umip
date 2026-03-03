#!/usr/bin/env bash
# run_agent_v2.sh — Cron wrapper for Agent V2 (With UMIP)
#
# Cron entry (hourly, same cadence as V1):
#   0 * * * * /Users/simoncastelain/Documents/PROJET\ CRYPTO/agents/v2_with_umip/run_agent_v2.sh >> /Users/simoncastelain/Documents/PROJET\ CRYPTO/.tmp/cron_v2.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
AGENT="$SCRIPT_DIR/agent.py"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

if [ -z "${DEPLOYER_PRIVATE_KEY:-}" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: DEPLOYER_PRIVATE_KEY not set. Abort." >&2
    exit 1
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] --- CRON V2 TICK START ---"
"$PYTHON" "$AGENT"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] --- CRON V2 TICK END ---"
