#!/usr/bin/env python3
"""
agent.py — Agent V2 (With UMIP): Funding rate arbitrage via UMIPVault on Sepolia.

Decision loop:
  1. Fetch live rates (GMX mainnet, gTrade mainnet) as signal
  2. Query UMIPVault state (unified collateral pool)
  3. Decide optimal platform
  4. Execute via vault.openPosition() — no fragmentation possible
  5. Log VAULT_OPEN event

On testnet, routes to GMX only (gTrade requires GNS_USDC, vault holds SG_USDC).
On mainnet, vault routes to gTrade automatically when it offers a better rate.

Usage:
  python3 agent.py              — run one cycle and exit
  python3 agent.py --loop       — run continuously (cron-friendly)
  python3 agent.py --close-all  — close all open vault positions
"""

import argparse
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vault  import get_vault_state, get_open_positions, open_gmx_position, close_gmx_position
from logger import (
    log_rate_snapshot, log_opportunity, log_vault_health,
    log_vault_open, log_action, log_error, print_recent_log
)

sys.path.insert(0, str(Path(__file__).parent.parent / "v1_no_umip"))
from rates import fetch_rates

# ─── Config ───────────────────────────────────────────────────────────────────

RATE_THRESHOLD   = 0.0005  # 0.05%/day — same as V1
PREFER_GTRADE_IF = 2.0     # prefer gTrade if ≥2x cheaper (same as V1)
COLLATERAL_USD   = 10.0    # $10 per position (same as V1)
LEVERAGE         = 5.0     # 5x leverage (same as V1)
UMIP_VAULT       = "0x555f5Ea52732aDeF6D92DB42274be8144b8A3cf4"

# ─── Decision Logic ───────────────────────────────────────────────────────────

def decide(rates: list[dict], vault_state: dict) -> dict:
    """
    Decide trading action based on rates and vault state.
    Returns action dict with action, platform, reason.
    """
    gmx_eth = next((r for r in rates if r["platform"] == "GMX"    and r["market"] == "ETH/USD"), None)
    gt_eth  = next((r for r in rates if r["platform"] == "gTrade" and r["market"] == "ETH/USD"), None)

    if not gmx_eth or not gt_eth:
        return {"action": "skip", "reason": "rate fetch failed"}

    gmx_rate = gmx_eth["daily_rate"]
    gt_rate  = gt_eth["daily_rate"]
    ratio    = gmx_rate / max(gt_rate, 1e-10)
    opp_cost = (gmx_rate - gt_rate) * 100   # %/day saved by using gTrade

    has_positions = len(get_open_positions(vault_state.get("_account", ""))) > 0 \
                    if vault_state.get("_account") else vault_state["position_count"] > 0

    # Choose optimal platform (same logic as V1)
    if ratio >= PREFER_GTRADE_IF and gmx_rate > RATE_THRESHOLD:
        optimal = "gTrade"
        reason  = (
            f"gTrade is {ratio:.0f}x cheaper ({opp_cost:.4f}%/day saving). "
            f"Testnet: routing to GMX (vault holds SG_USDC, gTrade requires GNS_USDC)."
        )
    elif gmx_rate > RATE_THRESHOLD:
        optimal = "GMX"
        reason  = f"GMX rate {gmx_rate*100:.4f}%/day above threshold"
    else:
        optimal = None
        reason  = "rates below threshold, no position needed"

    # ── No action needed ──────────────────────────────────────────────────────
    if optimal is None:
        if has_positions:
            return {"action": "close_all", "platform": "GMX",
                    "reason": "rate dropped below threshold"}
        return {"action": "skip", "reason": reason, "opportunity_cost": 0}

    # ── Rate is above threshold — open if no position ─────────────────────────
    if not has_positions:
        can_open = vault_state["can_open_gmx"]

        if can_open:
            executed_platform = "GMX"   # testnet: only GMX available in vault
            return {
                "action":           "open",
                "platform":         executed_platform,
                "optimal_platform": optimal,
                "reason":           reason,
                "opportunity_cost": 0,
                "via_vault":        True,
            }
        else:
            # Vault has no idle collateral at all — unusual state
            return {
                "action": "skip",
                "reason": f"Vault has no idle collateral (idle={vault_state['idle_usdc']:.2f})",
                "opportunity_cost": 0,
            }

    # Already have a position
    return {"action": "hold", "platform": "GMX",
            "reason": "position open, vault managing collateral", "opportunity_cost": 0}


# ─── Action Executor ──────────────────────────────────────────────────────────

def execute(decision: dict, vault_state: dict, private_key: str, rates: list[dict]) -> None:
    action   = decision["action"]
    platform = decision.get("platform", "GMX")
    reason   = decision.get("reason", "")

    print(f"  Decision: {action.upper()} on {platform} — {reason[:80]}")

    if action == "skip":
        log_action("skipped", platform, {"reason": reason})
        return

    if action == "hold":
        log_action("hold", platform, {"reason": reason})
        return

    if action == "open":
        print(f"  Opening {COLLATERAL_USD} USDC / {LEVERAGE}x long via UMIPVault → {platform}...")
        result = open_gmx_position(private_key, COLLATERAL_USD, LEVERAGE)
        log_vault_open(result, rates)
        log_action("open_long", platform, {
            "via": "UMIPVault",
            "vault": UMIP_VAULT,
            "tx_hash": result.get("tx_hash", ""),
            "optimal_platform": decision.get("optimal_platform", platform),
        })
        print(f"  ✓ Vault order tx: {result.get('tx_hash','?')[:20]}...")

    if action == "close_all":
        positions = get_open_positions(vault_state.get("_account", ""))
        for pos in positions:
            print(f"  Closing vault position #{pos['position_id']} (${pos['size_usd']:.2f})...")
            result = close_gmx_position(private_key, pos["position_id"])
            log_action("close_long", platform, result)
            print(f"  ✓ Close tx: {result['tx_hash'][:20]}...")


# ─── Main Loop ────────────────────────────────────────────────────────────────

def run_cycle(private_key: str, force_close: bool = False):
    from web3 import Web3
    w3      = Web3(Web3.HTTPProvider("https://sepolia-rollup.arbitrum.io/rpc"))
    account = w3.eth.account.from_key(private_key).address

    print(f"\n{'─'*62}")
    print(f"  AGENT V2 CYCLE  |  vault: {UMIP_VAULT[:10]}...")
    print(f"  account: {account[:10]}...")
    print(f"{'─'*62}")

    # 1. Fetch rates (same as V1)
    print("  [1/4] Fetching mainnet rates...")
    try:
        rates   = fetch_rates()
        log_rate_snapshot(rates)
        gmx_eth = next(r for r in rates if r["platform"] == "GMX"    and r["market"] == "ETH/USD")
        gt_eth  = next(r for r in rates if r["platform"] == "gTrade" and r["market"] == "ETH/USD")
        ratio   = gmx_eth["daily_rate"] / max(gt_eth["daily_rate"], 1e-10)
        print(f"  GMX: {gmx_eth['daily_rate']*100:.4f}%/day  "
              f"gTrade: {gt_eth['daily_rate']*100:.4f}%/day  "
              f"(GMX is {ratio:.0f}x costlier)")
    except Exception as e:
        log_error("fetch_rates", str(e))
        print(f"  ERROR fetching rates: {e}")
        return

    # 2. Query vault state
    print("  [2/4] Querying UMIPVault state...")
    try:
        state = get_vault_state(account)
        state["_account"] = account
        log_vault_health(state)
        print(f"  Vault idle:     ${state['idle_usdc']:.2f}")
        print(f"  Vault GMX alloc:${state['allocated_gmx_usdc']:.2f}")
        print(f"  Vault total:    ${state['total_usdc']:.2f}")
        print(f"  Open positions: {state['position_count']}")
        print(f"  Fragmentation:  {state['fragmentation_risk']}")
    except Exception as e:
        log_error("get_vault_state", str(e))
        print(f"  ERROR querying vault: {e}")
        return

    # 3. Handle force-close
    if force_close:
        print("  [3/4] Force-closing all vault positions...")
        try:
            positions = get_open_positions(account)
            if not positions:
                print("  No open vault positions.")
            for pos in positions:
                result = close_gmx_position(private_key, pos["position_id"])
                log_action("close_long_forced", "GMX", result)
                print(f"  ✓ Closed: {result['tx_hash'][:20]}...")
        except Exception as e:
            log_error("close_all", str(e))
        return

    # 4. Decide and execute
    print("  [3/4] Deciding...")
    decision = decide(rates, state)
    log_opportunity(rates, decision.get("platform", "?"), decision.get("reason", ""))

    print("  [4/4] Executing...")
    try:
        execute(decision, state, private_key, rates)
    except Exception as e:
        log_error("execute", str(e))
        print(f"  ERROR executing: {e}")
        traceback.print_exc()

    print()
    print_recent_log(n=5)


def main():
    parser = argparse.ArgumentParser(description="Agent V2 — With UMIP")
    parser.add_argument("--loop",       action="store_true", help="Run continuously")
    parser.add_argument("--close-all",  action="store_true", help="Force close all vault positions")
    parser.add_argument("--interval",   type=int, default=3600, help="Loop interval seconds")
    args = parser.parse_args()

    pk = os.getenv("DEPLOYER_PRIVATE_KEY")
    if not pk:
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DEPLOYER_PRIVATE_KEY="):
                    pk = line.split("=", 1)[1].strip()
                    break
    if not pk:
        print("Error: DEPLOYER_PRIVATE_KEY not found in environment or .env")
        sys.exit(1)

    if args.loop:
        import time
        print(f"Starting Agent V2 loop (interval={args.interval}s). Ctrl+C to stop.")
        while True:
            try:
                run_cycle(pk, args.close_all)
            except KeyboardInterrupt:
                print("\nAgent stopped.")
                break
            except Exception as e:
                log_error("main_loop", str(e))
                print(f"Cycle error: {e}")
            time.sleep(args.interval)
    else:
        run_cycle(pk, args.close_all)


if __name__ == "__main__":
    main()
