#!/usr/bin/env python3
"""
agent.py — UMIP Agent Template: Funding Rate Arbitrage

Strategy: Collects ETH/USD funding rates from GMX and gTrade. When rates are
above threshold, opens a long via UMIPVault. Zero fragmentation — vault routes
capital to whichever platform is cheapest automatically.

Quick Start:
  1. cp .env.example .env && edit .env (add your private key)
  2. Get Circle USDC: https://faucet.circle.com/
  3. Deposit USDC into vault via: https://umip-sandbox.vercel.app
  4. python agent.py            — run one cycle
     python agent.py --loop    — run every hour

Customize:
  - Edit config.py to change thresholds, collateral size, leverage
  - Edit decide() to change the strategy entirely
  - Swap fetch_rates() with your own data source
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()
from config import (
    ARB_SEPOLIA_RPC, VAULT_ADDRESS, USDC_ADDRESS,
    RATE_THRESHOLD, PREFER_GTRADE_IF, COLLATERAL_USD, LEVERAGE,
    GMX_EXEC_FEE_ETH, LOG_FILE,
)

# ── ABI (minimal subset needed) ───────────────────────────────────────────────

VAULT_ABI = [
    {"name": "getUserCollateral", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "user", "type": "address"}],
     "outputs": [
         {"name": "idle",                "type": "uint256"},
         {"name": "allocatedGMX",        "type": "uint256"},
         {"name": "allocatedVertex",     "type": "uint256"},
         {"name": "allocatedGainsTrade", "type": "uint256"},
         {"name": "total",               "type": "uint256"},
     ]},
    {"name": "openPosition", "type": "function", "stateMutability": "payable",
     "inputs": [
         {"name": "platform",         "type": "uint8"},
         {"name": "collateralAmount", "type": "uint256"},
         {"name": "sizeDeltaUsd",     "type": "uint256"},
         {"name": "acceptablePrice",  "type": "uint256"},
     ],
     "outputs": [{"name": "positionId", "type": "uint256"}]},
    {"name": "closePosition", "type": "function", "stateMutability": "payable",
     "inputs":  [{"name": "positionId", "type": "uint256"}],
     "outputs": []},
    {"name": "getPosition", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "user", "type": "address"}, {"name": "positionId", "type": "uint256"}],
     "outputs": [{"name": "", "type": "tuple", "components": [
         {"name": "platform",         "type": "uint8"},
         {"name": "market",           "type": "address"},
         {"name": "collateralAmount", "type": "uint256"},
         {"name": "sizeDeltaUsd",     "type": "uint256"},
         {"name": "openTimestamp",    "type": "uint256"},
         {"name": "isOpen",           "type": "bool"},
     ]}]},
    {"name": "userPositionCount", "type": "function", "stateMutability": "view",
     "inputs":  [{"name": "", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}]},
]

ERC20_ABI = [
    {"name": "approve", "type": "function", "stateMutability": "nonpayable",
     "inputs":  [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
     "outputs": [{"name": "", "type": "bool"}]},
]

PLATFORM_GMX = 0

# ── Logging ───────────────────────────────────────────────────────────────────

def _log(obj: dict) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(), **obj}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"  [{entry['event']}] {json.dumps({k: v for k, v in entry.items() if k not in ('ts', 'event')})[:120]}")

# ── Web3 Helpers ──────────────────────────────────────────────────────────────

def _w3() -> Web3:
    w3 = Web3(Web3.HTTPProvider(ARB_SEPOLIA_RPC))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to {ARB_SEPOLIA_RPC}")
    return w3

def _send(w3: Web3, tx: dict, private_key: str) -> str:
    """Sign, broadcast, and await a transaction. Returns tx hash."""
    acct  = w3.eth.account.from_key(private_key)
    tx["from"]  = acct.address
    tx["nonce"] = w3.eth.get_transaction_count(acct.address, "pending")
    tx["gas"]   = w3.eth.estimate_gas(tx)
    base_fee    = w3.eth.get_block("latest")["baseFeePerGas"]
    tx["maxPriorityFeePerGas"] = w3.to_wei(0.1, "gwei")
    tx["maxFeePerGas"]         = base_fee * 2 + w3.to_wei(0.1, "gwei")
    tx.pop("gasPrice", None)
    signed  = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status != 1:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
    return tx_hash.hex()

# ── Rate Fetching ─────────────────────────────────────────────────────────────

GMX_DATASTORE  = "0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8"
GMX_ETH_MARKET = "0x70d95587d40A2caf56bd97485aB3Eec10Bee6336"
GMX_WETH       = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"

GMX_DS_ABI = [
    {"name": "getUint", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "key", "type": "bytes32"}], "outputs": [{"name": "", "type": "uint256"}]},
]

def _keccak(*parts) -> bytes:
    from eth_abi import encode
    encoded = b"".join(
        Web3.keccak(text=p) if isinstance(p, str) else encode(["address"], [p])
        for p in parts
    )
    return Web3.keccak(encoded)

def fetch_gmx_rate() -> float:
    """Returns ETH/USD funding rate on GMX as a daily % (e.g. 0.058 = 0.058%/day)."""
    try:
        w3 = Web3(Web3.HTTPProvider("https://arb1.arbitrum.io/rpc"))
        ds = w3.eth.contract(address=Web3.to_checksum_address(GMX_DATASTORE), abi=GMX_DS_ABI)
        key = _keccak("FUNDING_FACTOR_PER_SECOND", GMX_ETH_MARKET, GMX_WETH, True)
        raw = ds.functions.getUint(key).call()
        return (raw / 1e30) * 86400 * 100   # per-second → daily %
    except Exception:
        return 0.0

def fetch_gtrade_rate() -> float:
    """Returns ETH/USD borrowing rate on gTrade as a daily % (proxy for funding cost)."""
    try:
        url = "https://backend-arbitrum.gains.trade/trading-variables"
        data = requests.get(url, timeout=5).json()
        # borrowing fee per block → daily
        fee_per_block = float(data.get("borrowingFees", [{}])[0].get("groups", [{}])[0].get("feePerBlock", 0))
        return fee_per_block * 7200 * 100  # ~7200 blocks/day on Arbitrum
    except Exception:
        return 0.0

def fetch_rates() -> dict:
    gmx = fetch_gmx_rate()
    gt  = fetch_gtrade_rate()
    _log({"event": "RATE_SNAPSHOT", "gmx_eth_daily_pct": round(gmx, 6), "gtrade_eth_daily_pct": round(gt, 6)})
    return {"gmx": gmx, "gtrade": gt}

# ── Vault Queries ─────────────────────────────────────────────────────────────

def get_vault_state(address: str) -> dict:
    w3    = _w3()
    vault = w3.eth.contract(address=Web3.to_checksum_address(VAULT_ADDRESS), abi=VAULT_ABI)
    idle, alloc_gmx, alloc_vtx, alloc_gt, total = \
        vault.functions.getUserCollateral(Web3.to_checksum_address(address)).call()
    count = vault.functions.userPositionCount(Web3.to_checksum_address(address)).call()
    return {
        "idle_usdc":           idle      / 1e6,
        "allocated_gmx_usdc":  alloc_gmx / 1e6,
        "total_usdc":          total     / 1e6,
        "position_count":      count,
        "can_open":            idle >= int(COLLATERAL_USD * 1e6),
    }

def get_open_positions(address: str) -> list:
    w3    = _w3()
    vault = w3.eth.contract(address=Web3.to_checksum_address(VAULT_ADDRESS), abi=VAULT_ABI)
    count = vault.functions.userPositionCount(Web3.to_checksum_address(address)).call()
    positions = []
    for i in range(count):
        pos = vault.functions.getPosition(Web3.to_checksum_address(address), i).call()
        platform, market, collateral, size, ts, is_open = pos
        if is_open:
            positions.append({"id": i, "platform": platform, "collateral_usd": collateral / 1e6,
                               "size_usd": size / 1e30, "open_ts": ts})
    return positions

# ── Trading ───────────────────────────────────────────────────────────────────

def open_position(private_key: str) -> dict:
    w3    = _w3()
    vault = w3.eth.contract(address=Web3.to_checksum_address(VAULT_ADDRESS), abi=VAULT_ABI)
    acct  = w3.eth.account.from_key(private_key).address

    collateral_raw   = int(COLLATERAL_USD * 1e6)
    size_raw         = int(COLLATERAL_USD * LEVERAGE * 1e30)
    acceptable_price = 2**256 - 1   # market order: accept any price
    exec_fee_wei     = w3.to_wei(GMX_EXEC_FEE_ETH, "ether")

    tx = vault.functions.openPosition(
        PLATFORM_GMX, collateral_raw, size_raw, acceptable_price
    ).build_transaction({"value": exec_fee_wei, "from": acct})

    tx_hash = _send(w3, tx, private_key)
    time.sleep(12)   # wait for keeper
    return {"tx_hash": tx_hash, "collateral_usd": COLLATERAL_USD, "size_usd": COLLATERAL_USD * LEVERAGE}

def close_position(private_key: str, position_id: int) -> dict:
    w3    = _w3()
    vault = w3.eth.contract(address=Web3.to_checksum_address(VAULT_ADDRESS), abi=VAULT_ABI)
    acct  = w3.eth.account.from_key(private_key).address
    exec_fee_wei = w3.to_wei(GMX_EXEC_FEE_ETH, "ether")
    tx = vault.functions.closePosition(position_id).build_transaction({"value": exec_fee_wei, "from": acct})
    tx_hash = _send(w3, tx, private_key)
    return {"tx_hash": tx_hash, "position_id": position_id}

# ── Strategy ──────────────────────────────────────────────────────────────────
# Edit decide() to implement your own strategy.
# Inputs:  rates dict, vault_state dict, open_positions list
# Returns: action string ("open", "close_all", "hold", "skip")

def decide(rates: dict, vault_state: dict, open_positions: list) -> tuple[str, str]:
    gmx_rate = rates["gmx"]
    gt_rate  = rates["gtrade"]
    ratio    = gmx_rate / max(gt_rate, 1e-10)

    has_positions = len(open_positions) > 0

    # Rate signal: is there a funding-rate arbitrage opportunity?
    above_threshold = gmx_rate > RATE_THRESHOLD

    if not above_threshold:
        if has_positions:
            return "close_all", "Rate dropped below threshold — closing"
        return "skip", f"Rate {gmx_rate*100:.4f}%/day below threshold"

    # Determine optimal venue (V2 vault routes automatically — zero fragmentation)
    if ratio >= PREFER_GTRADE_IF:
        venue = "gTrade (via vault)"
        reason = f"gTrade is {ratio:.1f}x cheaper than GMX"
    else:
        venue = "GMX (via vault)"
        reason = f"GMX rate {gmx_rate*100:.4f}%/day above threshold"

    if not has_positions and vault_state["can_open"]:
        return "open", f"{reason} → opening on {venue}"

    if not vault_state["can_open"]:
        return "skip", f"Vault has no idle collateral (${vault_state['idle_usdc']:.2f})"

    return "hold", "Position open, monitoring"

# ── Main Cycle ────────────────────────────────────────────────────────────────

def run_cycle(private_key: str) -> None:
    w3      = _w3()
    address = w3.eth.account.from_key(private_key).address

    print(f"\n{'─'*60}")
    print(f"  UMIP Agent  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Account: {address[:10]}...")
    print(f"  Vault:   {VAULT_ADDRESS[:10]}...")
    print(f"{'─'*60}")

    print("\n[1/4] Fetching rates...")
    rates = fetch_rates()
    print(f"  GMX:    {rates['gmx']*100:.4f}%/day")
    print(f"  gTrade: {rates['gtrade']*100:.4f}%/day")

    print("\n[2/4] Querying vault state...")
    state     = get_vault_state(address)
    positions = get_open_positions(address)
    print(f"  Idle:      ${state['idle_usdc']:.2f}")
    print(f"  GMX alloc: ${state['allocated_gmx_usdc']:.2f}")
    print(f"  Positions: {len(positions)} open")
    print(f"  Fragmentation: False (UMIP vault — always False)")

    print("\n[3/4] Deciding...")
    action, reason = decide(rates, state, positions)
    print(f"  Action: {action.upper()} — {reason}")
    _log({"event": "DECISION", "action": action, "reason": reason, "rates": rates})

    print("\n[4/4] Executing...")
    if action == "open":
        result = open_position(private_key)
        _log({"event": "VAULT_OPEN", "tx_hash": result["tx_hash"],
              "collateral_usd": result["collateral_usd"], "size_usd": result["size_usd"],
              "via": "UMIPVault", "note": "No fragmentation."})
        print(f"  ✓ Opened position | tx: {result['tx_hash'][:20]}...")

    elif action == "close_all":
        for pos in positions:
            result = close_position(private_key, pos["id"])
            _log({"event": "VAULT_CLOSE", "position_id": pos["id"], "tx_hash": result["tx_hash"]})
            print(f"  ✓ Closed position #{pos['id']} | tx: {result['tx_hash'][:20]}...")

    elif action in ("hold", "skip"):
        print(f"  → {reason}")

    print()


def main():
    parser = argparse.ArgumentParser(description="UMIP Agent — Funding Rate Arbitrage")
    parser.add_argument("--loop",     action="store_true", help="Run continuously (hourly)")
    parser.add_argument("--interval", type=int, default=3600, help="Loop interval in seconds")
    args = parser.parse_args()

    pk = os.getenv("DEPLOYER_PRIVATE_KEY")
    if not pk:
        print("Error: DEPLOYER_PRIVATE_KEY not set. Add it to .env")
        sys.exit(1)

    if args.loop:
        print(f"Starting loop (interval={args.interval}s). Ctrl+C to stop.")
        while True:
            try:
                run_cycle(pk)
            except KeyboardInterrupt:
                print("\nStopped.")
                break
            except Exception as e:
                _log({"event": "ERROR", "error": str(e)})
                traceback.print_exc()
            time.sleep(args.interval)
    else:
        run_cycle(pk)


if __name__ == "__main__":
    main()
