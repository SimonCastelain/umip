#!/usr/bin/env bash
# run_agent_v1.sh — Cron wrapper for Agent V1 (No UMIP)
#
# Designed to be called by cron every hour:
#   0 * * * * /Users/simoncastelain/Documents/PROJET\ CRYPTO/agents/v1_no_umip/run_agent_v1.sh >> /Users/simoncastelain/Documents/PROJET\ CRYPTO/.tmp/cron_v1.log 2>&1
#
# Loads .env, activates the right Python, runs one agent cycle.

set -euo pipefail

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
AGENT="$SCRIPT_DIR/agent.py"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
LOG="$PROJECT_ROOT/.tmp/cron_v1.log"

# ─── Load .env ────────────────────────────────────────────────────────────────
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

# ─── Guard: ensure private key is set ─────────────────────────────────────────
if [ -z "${DEPLOYER_PRIVATE_KEY:-}" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: DEPLOYER_PRIVATE_KEY not set. Abort." >&2
    exit 1
fi

# ─── Run one agent cycle ───────────────────────────────────────────────────────
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] --- CRON TICK START ---"
"$PYTHON" "$AGENT"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] --- CRON TICK END ---"
