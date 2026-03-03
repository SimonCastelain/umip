#!/usr/bin/env python3
"""
logger.py — Structured event logging for Agent V1.

Three log levels:
  RATE_SNAPSHOT  — periodic rate captures (every run)
  OPPORTUNITY    — rate arbitrage signal detected
  FRAGMENTATION  — capital stuck on wrong platform (the core demo event)
  ACTION         — actual trade executed
  HEALTH         — position health update

Logs are written to .tmp/agent_v1_log.jsonl (one JSON per line).
A human-readable summary is also maintained at .tmp/agent_v1_summary.txt.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR     = Path(__file__).parent.parent.parent / ".tmp"
LOG_FILE    = LOG_DIR / "agent_v1_log.jsonl"
SUMMARY_FILE = LOG_DIR / "agent_v1_summary.txt"

LOG_DIR.mkdir(parents=True, exist_ok=True)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(event: dict) -> None:
    event["ts"] = _ts()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


# ─── Event Loggers ────────────────────────────────────────────────────────────

def log_rate_snapshot(rates: list[dict]) -> None:
    """Log the current funding rates from both platforms."""
    gmx_eth  = next((r for r in rates if r["platform"] == "GMX"    and r["market"] == "ETH/USD"), None)
    gt_eth   = next((r for r in rates if r["platform"] == "gTrade" and r["market"] == "ETH/USD"), None)

    _write({
        "event": "RATE_SNAPSHOT",
        "gmx_eth_daily_pct":    round(gmx_eth["daily_rate"]  * 100, 6) if gmx_eth  else None,
        "gtrade_eth_daily_pct": round(gt_eth["daily_rate"]   * 100, 6) if gt_eth   else None,
        "gmx_direction":        gmx_eth["direction"]  if gmx_eth  else None,
        "rates": [
            {"platform": r["platform"], "market": r["market"],
             "daily_pct": round(r["daily_rate"] * 100, 6),
             "above_threshold": r["above_threshold"]}
            for r in rates
        ]
    })


def log_opportunity(rates: list[dict], preferred_platform: str, reason: str) -> None:
    """Log when rate arbitrage signal is strong enough to prefer one platform."""
    gmx_eth = next((r for r in rates if r["platform"] == "GMX"    and r["market"] == "ETH/USD"), None)
    gt_eth  = next((r for r in rates if r["platform"] == "gTrade" and r["market"] == "ETH/USD"), None)

    if gmx_eth and gt_eth:
        ratio = gmx_eth["daily_rate"] / max(gt_eth["daily_rate"], 1e-10)
        savings_pct = (gmx_eth["daily_rate"] - gt_eth["daily_rate"]) * 100
    else:
        ratio = 0; savings_pct = 0

    _write({
        "event":              "OPPORTUNITY",
        "preferred_platform": preferred_platform,
        "reason":             reason,
        "rate_ratio":         round(ratio, 1),
        "savings_pct_per_day": round(savings_pct, 4),
    })


def log_fragmentation(
    preferred_platform: str,
    forced_platform: str,
    balances: dict,
    opportunity_cost_pct_per_day: float,
    note: str = ""
) -> None:
    """
    Log the capital fragmentation failure — the core V1 demo event.
    Fires when: agent wants Platform A but capital is locked in Platform B.
    """
    _write({
        "event":               "FRAGMENTATION",
        "preferred_platform":  preferred_platform,
        "forced_platform":     forced_platform,
        "gmx_usdc":            round(balances.get("gmx_usdc", 0), 2),
        "gtrade_usdc":         round(balances.get("gtrade_usdc", 0), 2),
        "opportunity_cost_pct_per_day": round(opportunity_cost_pct_per_day, 4),
        "note": note,
    })
    # Also append to the human-readable summary
    with open(SUMMARY_FILE, "a") as f:
        ts = _ts()
        f.write(
            f"[{ts}] FRAGMENTATION: Wanted {preferred_platform}, stuck on {forced_platform}. "
            f"Lost {opportunity_cost_pct_per_day:.4f}%/day. "
            f"GMX={balances.get('gmx_usdc',0):.2f} gTrade={balances.get('gtrade_usdc',0):.2f} USDC\n"
        )


def log_action(action: str, platform: str, details: dict) -> None:
    """Log an actual trade action (open/close)."""
    _write({
        "event":    "ACTION",
        "action":   action,     # "open_long" | "close_long" | "skipped"
        "platform": platform,
        **{k: v for k, v in details.items() if isinstance(v, (str, int, float, bool))}
    })


def log_health(position_state: dict) -> None:
    """Log the current position health snapshot."""
    gmx = position_state.get("gmx_position")
    gt  = position_state.get("gtrade_positions", [])

    _write({
        "event":           "HEALTH",
        "has_gmx":         position_state.get("has_gmx", False),
        "has_gtrade":      position_state.get("has_gtrade", False),
        "fragmentation_risk": position_state.get("fragmentation_risk", False),
        "gmx_size_usd":    round(gmx["size_usd"],   2) if gmx else 0,
        "gmx_collateral":  round(gmx["collateral"], 2) if gmx else 0,
        "gtrade_count":    len(gt),
        "gtrade_size_usd": round(sum(t["size_usd"] for t in gt), 2),
        "total_collateral": round(position_state.get("total_collateral", 0), 2),
    })


def log_error(context: str, error: str) -> None:
    """Log an error without crashing the agent loop."""
    _write({"event": "ERROR", "context": context, "error": str(error)})


# ─── Summary Printer ──────────────────────────────────────────────────────────

def print_recent_log(n: int = 20) -> None:
    """Print the last n log entries to stdout."""
    if not LOG_FILE.exists():
        print("No log file yet.")
        return

    with open(LOG_FILE) as f:
        lines = f.readlines()

    print(f"\n{'='*62}")
    print(f"  AGENT V1 LOG  (last {min(n, len(lines))} entries)  →  {LOG_FILE}")
    print(f"{'='*62}")
    for line in lines[-n:]:
        try:
            e = json.loads(line)
            ts  = e.get("ts", "")[:19]
            ev  = e.get("event", "?")
            if ev == "RATE_SNAPSHOT":
                print(f"[{ts}] RATE   GMX={e.get('gmx_eth_daily_pct','?')}%/day "
                      f"gTrade={e.get('gtrade_eth_daily_pct','?')}%/day")
            elif ev == "FRAGMENTATION":
                print(f"[{ts}] ⚠ FRAG  Wanted {e['preferred_platform']}, "
                      f"got {e['forced_platform']}, "
                      f"cost={e['opportunity_cost_pct_per_day']:.4f}%/day")
            elif ev == "OPPORTUNITY":
                print(f"[{ts}] OPPTY  Prefer {e['preferred_platform']} "
                      f"({e['rate_ratio']:.0f}x cheaper, -{e['savings_pct_per_day']:.4f}%/day)")
            elif ev == "ACTION":
                print(f"[{ts}] ACT    {e['action'].upper()} on {e['platform']}")
            elif ev == "HEALTH":
                print(f"[{ts}] HEALTH GMX=${e['gmx_size_usd']} "
                      f"gTrade={e['gtrade_count']} positions  "
                      f"frag={e['fragmentation_risk']}")
            elif ev == "ERROR":
                print(f"[{ts}] ERROR  [{e['context']}] {e['error']}")
            else:
                print(f"[{ts}] {ev}")
        except Exception:
            print(line.rstrip())
    print(f"{'='*62}\n")


if __name__ == "__main__":
    print_recent_log()
