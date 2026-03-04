#!/usr/bin/env python3
"""
logger.py — Structured event logging for Agent V2 (With UMIP).

Events:
  RATE_SNAPSHOT  — periodic rate captures
  OPPORTUNITY    — rate arbitrage signal detected
  VAULT_HEALTH   — vault state (idle/allocated/total)
  VAULT_OPEN     — position opened via vault
  ACTION         — trade executed
  ERROR          — error context
"""

import json
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR      = Path(__file__).parent.parent.parent / ".tmp"
LOG_FILE     = LOG_DIR / "agent_v2_log.jsonl"
SUMMARY_FILE = LOG_DIR / "agent_v2_summary.txt"

LOG_DIR.mkdir(parents=True, exist_ok=True)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(event: dict) -> None:
    event["ts"] = _ts()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


# ─── Event Loggers ────────────────────────────────────────────────────────────

def log_rate_snapshot(rates: list[dict]) -> None:
    gmx_eth = next((r for r in rates if r["platform"] == "GMX"    and r["market"] == "ETH/USD"), None)
    gt_eth  = next((r for r in rates if r["platform"] == "gTrade" and r["market"] == "ETH/USD"), None)

    _write({
        "event":              "RATE_SNAPSHOT",
        "gmx_eth_daily_pct":    round(gmx_eth["daily_rate"] * 100, 6) if gmx_eth else None,
        "gtrade_eth_daily_pct": round(gt_eth["daily_rate"]  * 100, 6) if gt_eth  else None,
        "gmx_direction":        gmx_eth["direction"] if gmx_eth else None,
        "rates": [
            {"platform": r["platform"], "market": r["market"],
             "daily_pct": round(r["daily_rate"] * 100, 6),
             "above_threshold": r["above_threshold"]}
            for r in rates
        ]
    })


def log_opportunity(rates: list[dict], preferred_platform: str, reason: str) -> None:
    gmx_eth = next((r for r in rates if r["platform"] == "GMX"    and r["market"] == "ETH/USD"), None)
    gt_eth  = next((r for r in rates if r["platform"] == "gTrade" and r["market"] == "ETH/USD"), None)

    if gmx_eth and gt_eth:
        ratio       = gmx_eth["daily_rate"] / max(gt_eth["daily_rate"], 1e-10)
        savings_pct = (gmx_eth["daily_rate"] - gt_eth["daily_rate"]) * 100
    else:
        ratio = 0; savings_pct = 0

    _write({
        "event":               "OPPORTUNITY",
        "preferred_platform":  preferred_platform,
        "reason":              reason,
        "rate_ratio":          round(ratio, 1),
        "savings_pct_per_day": round(savings_pct, 4),
    })


def log_vault_health(vault_state: dict) -> None:
    """Log vault state snapshot."""
    _write({
        "event":             "VAULT_HEALTH",
        "idle_usdc":         round(vault_state.get("idle_usdc",          0), 2),
        "allocated_gmx":     round(vault_state.get("allocated_gmx_usdc", 0), 2),
        "allocated_gtrade":  round(vault_state.get("allocated_gt_usdc",  0), 2),
        "total_usdc":        round(vault_state.get("total_usdc",         0), 2),
        "position_count":    vault_state.get("position_count", 0),
        "fragmentation_risk": False,
        "vault":             "UMIPVault",
    })


def log_vault_open(result: dict, rates: list[dict]) -> None:
    """Log a successful vault position open."""
    gmx_eth = next((r for r in rates if r["platform"] == "GMX"    and r["market"] == "ETH/USD"), None)
    gt_eth  = next((r for r in rates if r["platform"] == "gTrade" and r["market"] == "ETH/USD"), None)

    note = ""
    if gmx_eth and gt_eth:
        ratio = gmx_eth["daily_rate"] / max(gt_eth["daily_rate"], 1e-10)
        note  = (
            f"On mainnet, vault would route to gTrade ({ratio:.0f}x cheaper). "
            f"gTrade unavailable on testnet (GNS_USDC required vs SG_USDC in vault)."
        )

    _write({
        "event":          "VAULT_OPEN",
        "platform":       result.get("platform", "GMX"),
        "via":            result.get("via", "UMIPVault"),
        "vault":          result.get("vault", ""),
        "tx_hash":        result.get("tx_hash", ""),
        "collateral_usd": result.get("collateral_usd", 0),
        "size_usd":       result.get("size_usd", 0),
        "fragmentation":  False,
        "note":           note,
    })

    with open(SUMMARY_FILE, "a") as f:
        ts = _ts()
        f.write(
            f"[{ts}] VAULT_OPEN: Opened {result.get('size_usd', 0):.0f} USD long on "
            f"{result.get('platform', 'GMX')} via UMIPVault. No fragmentation.\n"
        )


def log_action(action: str, platform: str, details: dict) -> None:
    _write({
        "event":    "ACTION",
        "action":   action,
        "platform": platform,
        **{k: v for k, v in details.items() if isinstance(v, (str, int, float, bool))}
    })


def log_error(context: str, error: str) -> None:
    _write({"event": "ERROR", "context": context, "error": str(error)})


# ─── Summary Printer ──────────────────────────────────────────────────────────

def print_recent_log(n: int = 20) -> None:
    if not LOG_FILE.exists():
        print("No V2 log file yet.")
        return

    with open(LOG_FILE) as f:
        lines = f.readlines()

    print(f"\n{'='*62}")
    print(f"  AGENT V2 LOG  (last {min(n, len(lines))} entries)  →  {LOG_FILE}")
    print(f"{'='*62}")
    for line in lines[-n:]:
        try:
            e  = json.loads(line)
            ts = e.get("ts", "")[:19]
            ev = e.get("event", "?")
            if ev == "RATE_SNAPSHOT":
                print(f"[{ts}] RATE   GMX={e.get('gmx_eth_daily_pct','?')}%/day "
                      f"gTrade={e.get('gtrade_eth_daily_pct','?')}%/day")
            elif ev == "VAULT_HEALTH":
                print(f"[{ts}] VAULT  idle=${e['idle_usdc']} "
                      f"gmx=${e['allocated_gmx']} total=${e['total_usdc']} "
                      f"frag={e['fragmentation_risk']}")
            elif ev == "VAULT_OPEN":
                print(f"[{ts}] ✓ OPEN  {e['collateral_usd']} USDC → "
                      f"${e['size_usd']} {e['platform']} via {e['via']}")
            elif ev == "OPPORTUNITY":
                print(f"[{ts}] OPPTY  Prefer {e['preferred_platform']} "
                      f"({e['rate_ratio']:.0f}x cheaper, -{e['savings_pct_per_day']:.4f}%/day)")
            elif ev == "ACTION":
                print(f"[{ts}] ACT    {e['action'].upper()} on {e['platform']}")
            elif ev == "ERROR":
                print(f"[{ts}] ERROR  [{e['context']}] {e['error']}")
            else:
                print(f"[{ts}] {ev}")
        except Exception:
            print(line.rstrip())
    print(f"{'='*62}\n")


if __name__ == "__main__":
    print_recent_log()
