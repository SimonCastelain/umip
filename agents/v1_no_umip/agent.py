#!/usr/bin/env python3
"""
agent.py — Agent V1 (No UMIP): Autonomous funding rate arbitrage on Sepolia.

Decision loop:
  1. Fetch live rates (GMX mainnet, gTrade mainnet) as signal
  2. Query Sepolia position state and balances
  3. Decide optimal platform based on rates
  4. Execute trade if: rate signal > threshold AND no existing position
  5. Log every decision — especially FRAGMENTATION events when capital
     is locked on the wrong platform

The fragmentation constraint surfaces naturally: the GMX adapter holds all capital
(SG USDC), so the agent cannot act on gTrade signals even when gTrade fees are lower.
Every missed opportunity is logged as a FRAGMENTATION event with the opportunity cost.

Usage:
  python3 agent.py              — run one cycle and exit
  python3 agent.py --loop       — run continuously (cron-friendly with --loop)
  python3 agent.py --open-gmx   — force open a GMX position this cycle
  python3 agent.py --close-gmx  — force close all GMX positions
"""

import argparse
import os
import sys
import traceback
from pathlib import Path

# Add parent dir so we can import from agents/
sys.path.insert(0, str(Path(__file__).parent))

from rates     import fetch_rates
from positions import (
    get_all_positions, open_gmx_long, close_gmx_long,
    open_gtrade_long, close_gtrade_long
)
from logger import (
    log_rate_snapshot, log_opportunity, log_fragmentation,
    log_action, log_health, log_error, print_recent_log
)

# ─── Config ───────────────────────────────────────────────────────────────────

RATE_THRESHOLD    = 0.0005  # 0.05%/day — lowered to fire at current GMX rates (~0.058%/day)
PREFER_GTRADE_IF  = 2.0     # open gTrade if it's ≥2x cheaper than GMX
POSITION_SIZE_USD = 50.0    # $50 position (5x leverage on $10 collateral)
LEVERAGE          = 5.0
COLLATERAL_USD    = 10.0

# ─── Decision Logic ───────────────────────────────────────────────────────────

def decide(rates: list[dict], position_state: dict) -> dict:
    """
    Core decision function.
    Returns: {action, platform, reason, opportunity_cost}
    """
    gmx_eth = next((r for r in rates if r["platform"] == "GMX"    and r["market"] == "ETH/USD"), None)
    gt_eth  = next((r for r in rates if r["platform"] == "gTrade" and r["market"] == "ETH/USD"), None)

    has_gmx    = position_state["has_gmx"]
    has_gtrade = position_state["has_gtrade"]
    balances   = position_state["balances"]

    # If no rates, skip
    if not gmx_eth or not gt_eth:
        return {"action": "skip", "reason": "rate fetch failed"}

    gmx_rate = gmx_eth["daily_rate"]
    gt_rate  = gt_eth["daily_rate"]
    ratio    = gmx_rate / max(gt_rate, 1e-10)
    opp_cost = (gmx_rate - gt_rate) * 100   # %/day wasted on wrong platform

    # Choose optimal platform
    if ratio >= PREFER_GTRADE_IF and gmx_rate > RATE_THRESHOLD:
        optimal = "gTrade"
        reason  = f"gTrade is {ratio:.0f}x cheaper ({opp_cost:.4f}%/day saving)"
    elif gmx_rate > RATE_THRESHOLD:
        optimal = "GMX"
        reason  = f"GMX rate {gmx_rate*100:.4f}%/day above threshold"
    else:
        optimal = None
        reason  = "rates below threshold, no position needed"

    # Decide action
    if optimal is None:
        if has_gmx:
            return {"action": "close", "platform": "GMX", "reason": "rate dropped below threshold",
                    "opportunity_cost": 0}
        if has_gtrade:
            return {"action": "close", "platform": "gTrade", "reason": "rate dropped below threshold",
                    "opportunity_cost": 0}
        return {"action": "skip", "reason": reason, "opportunity_cost": 0}

    # Rate is high — we want to be long
    if not has_gmx and not has_gtrade:
        # No position open: open on optimal platform
        can_open = balances[f"can_open_{optimal.lower().replace('/', '')}"]

        if optimal == "gTrade":
            can_open = balances["can_open_gtrade"]
        else:
            can_open = balances["can_open_gmx"]

        if can_open:
            return {"action": "open",   "platform": optimal, "reason": reason,
                    "opportunity_cost": 0}
        else:
            # FRAGMENTATION: can't open on optimal platform
            # Fall back to GMX if possible
            if optimal == "gTrade" and balances["can_open_gmx"]:
                return {
                    "action":           "open_forced",
                    "platform":         "GMX",
                    "reason":           f"FRAGMENTATION — wanted gTrade but no GNS_USDC. Fallback to GMX.",
                    "optimal":          "gTrade",
                    "opportunity_cost": opp_cost,
                }
            else:
                return {
                    "action":           "skip",
                    "reason":           f"FRAGMENTATION — no capital on any platform",
                    "opportunity_cost": opp_cost,
                }

    # Already have a position
    if has_gmx and optimal == "gTrade" and not has_gtrade:
        # Holding GMX but gTrade is better → missed savings, log fragmentation
        return {
            "action":           "hold_suboptimal",
            "platform":         "GMX",
            "reason":           f"Stuck on GMX ({gmx_rate*100:.4f}%/day), gTrade is {ratio:.0f}x cheaper",
            "opportunity_cost": opp_cost,
        }

    return {"action": "hold", "platform": "GMX" if has_gmx else "gTrade",
            "reason": "position healthy, no change needed", "opportunity_cost": 0}


# ─── Action Executor ──────────────────────────────────────────────────────────

def execute(decision: dict, position_state: dict, private_key: str) -> None:
    """Execute the agent's decision and log the outcome."""
    action    = decision["action"]
    platform  = decision.get("platform", "unknown")
    reason    = decision.get("reason", "")
    opp_cost  = decision.get("opportunity_cost", 0)
    balances  = position_state["balances"]

    print(f"  Decision: {action.upper()} on {platform} — {reason}")

    if action == "skip":
        log_action("skipped", platform, {"reason": reason})
        return

    if action == "hold":
        log_action("hold", platform, {"reason": reason})
        return

    if action == "hold_suboptimal":
        # Log the fragmentation event
        log_fragmentation(
            preferred_platform="gTrade",
            forced_platform="GMX",
            balances=balances,
            opportunity_cost_pct_per_day=opp_cost,
            note=reason
        )
        log_action("hold_suboptimal", platform, {"reason": reason, "opp_cost_pct": opp_cost})
        print(f"  ⚠ FRAGMENTATION logged: {opp_cost:.4f}%/day opportunity cost")
        return

    if action == "open" or action == "open_forced":
        if action == "open_forced":
            log_fragmentation(
                preferred_platform="gTrade",
                forced_platform="GMX",
                balances=balances,
                opportunity_cost_pct_per_day=opp_cost,
                note="No GNS_USDC for gTrade — forced onto GMX"
            )

        if platform == "GMX":
            print(f"  Opening {COLLATERAL_USD} USDC / {LEVERAGE}x long on GMX Sepolia...")
            result = open_gmx_long(private_key, COLLATERAL_USD, LEVERAGE)
            log_action("open_long", "GMX", result)
            print(f"  ✓ GMX order: {result.get('tx_hash', 'pending')[:20]}...")

        elif platform == "gTrade":
            print(f"  Opening {COLLATERAL_USD} USDC / {LEVERAGE}x long on gTrade Sepolia...")
            result = open_gtrade_long(private_key, COLLATERAL_USD, int(LEVERAGE))
            log_action("open_long", "gTrade", result)
            if result.get("fragmentation"):
                log_fragmentation(
                    preferred_platform="gTrade",
                    forced_platform="none",
                    balances=balances,
                    opportunity_cost_pct_per_day=opp_cost,
                    note=result.get("message", "")
                )
                print(f"  ⚠ {result['message']}")
            else:
                print(f"  ✓ gTrade order: {result.get('tx_hash','?')[:20]}...")

    elif action == "close":
        if platform == "GMX":
            pos = position_state.get("gmx_position")
            if pos:
                print(f"  Closing GMX position (${pos['size_usd']:.2f})...")
                result = close_gmx_long(private_key, pos["size_usd"])
                log_action("close_long", "GMX", result)
                print(f"  ✓ Close tx: {result['tx_hash'][:20]}...")

        elif platform == "gTrade":
            for trade in position_state.get("gtrade_positions", []):
                print(f"  Closing gTrade position index={trade['index']}...")
                result = close_gtrade_long(private_key, trade["index"])
                log_action("close_long", "gTrade", result)
                print(f"  ✓ Close tx: {result['tx_hash'][:20]}...")


# ─── Main Loop ────────────────────────────────────────────────────────────────

def run_cycle(private_key: str, force_open_gmx: bool = False, force_close_gmx: bool = False):
    """Run one complete agent cycle."""
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider("https://sepolia-rollup.arbitrum.io/rpc"))
    account = w3.eth.account.from_key(private_key).address

    print(f"\n{'─'*62}")
    print(f"  AGENT V1 CYCLE  |  account: {account[:10]}...")
    print(f"{'─'*62}")

    # 1. Fetch rates
    print("  [1/4] Fetching mainnet rates...")
    try:
        rates = fetch_rates()
        log_rate_snapshot(rates)
        gmx_eth = next(r for r in rates if r["platform"] == "GMX" and r["market"] == "ETH/USD")
        gt_eth  = next(r for r in rates if r["platform"] == "gTrade" and r["market"] == "ETH/USD")
        ratio   = gmx_eth["daily_rate"] / max(gt_eth["daily_rate"], 1e-10)
        print(f"  GMX: {gmx_eth['daily_rate']*100:.4f}%/day  "
              f"gTrade: {gt_eth['daily_rate']*100:.4f}%/day  "
              f"(GMX is {ratio:.0f}x costlier)")
    except Exception as e:
        log_error("fetch_rates", str(e))
        print(f"  ERROR fetching rates: {e}")
        return

    # 2. Query positions + balances
    print("  [2/4] Querying Sepolia positions...")
    try:
        state = get_all_positions(account)
        log_health(state)
        print(f"  GMX position: {'$'+str(round(state['gmx_position']['size_usd'],2)) if state['has_gmx'] else 'none'}")
        print(f"  gTrade trades: {len(state['gtrade_positions'])}")
        print(f"  GMX USDC (adapter): {state['balances']['gmx_usdc']:.2f}")
        print(f"  gTrade USDC (acct): {state['balances']['gtrade_usdc']:.2f}")
    except Exception as e:
        log_error("get_all_positions", str(e))
        print(f"  ERROR querying positions: {e}")
        return

    # 3. Handle CLI overrides
    if force_close_gmx:
        if state["has_gmx"]:
            print("  [3/4] Force-closing GMX position...")
            try:
                pos = state["gmx_position"]
                result = close_gmx_long(private_key, pos["size_usd"])
                log_action("close_long_forced", "GMX", result)
                print(f"  ✓ Closed: {result['tx_hash'][:20]}...")
            except Exception as e:
                log_error("close_gmx", str(e))
        else:
            print("  No GMX position to close.")
        return

    if force_open_gmx:
        print("  [3/4] Force-opening GMX position...")
        try:
            result = open_gmx_long(private_key, COLLATERAL_USD, LEVERAGE)
            log_action("open_long_forced", "GMX", result)
            print(f"  ✓ Opened: {result.get('tx_hash','?')[:20]}...")
        except Exception as e:
            log_error("open_gmx", str(e))
        return

    # 4. Decide and execute
    print("  [3/4] Deciding...")
    decision = decide(rates, state)
    log_opportunity(rates, decision.get("platform", "?"), decision.get("reason", ""))

    print("  [4/4] Executing...")
    try:
        execute(decision, state, private_key)
    except Exception as e:
        log_error("execute", str(e))
        print(f"  ERROR executing: {e}")
        traceback.print_exc()

    print()
    print_recent_log(n=5)


def main():
    parser = argparse.ArgumentParser(description="Agent V1 — No UMIP")
    parser.add_argument("--loop",       action="store_true", help="Run continuously")
    parser.add_argument("--open-gmx",   action="store_true", help="Force open GMX position")
    parser.add_argument("--close-gmx",  action="store_true", help="Force close GMX position")
    parser.add_argument("--interval",   type=int, default=3600, help="Loop interval seconds (default 3600)")
    args = parser.parse_args()

    pk = os.getenv("DEPLOYER_PRIVATE_KEY")
    if not pk:
        # Try loading from .env file
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
        print(f"Starting Agent V1 loop (interval={args.interval}s). Ctrl+C to stop.")
        while True:
            try:
                run_cycle(pk, args.open_gmx, args.close_gmx)
            except KeyboardInterrupt:
                print("\nAgent stopped.")
                break
            except Exception as e:
                log_error("main_loop", str(e))
                print(f"Cycle error: {e}")
            time.sleep(args.interval)
    else:
        run_cycle(pk, args.open_gmx, args.close_gmx)


if __name__ == "__main__":
    main()
