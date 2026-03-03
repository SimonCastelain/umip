#!/usr/bin/env python3
"""
config.py — Central configuration for Agent V1 (No UMIP).

All addresses, thresholds, and tuning parameters in one place.
Loaded by rates.py, positions.py, and agent.py.
"""

# ─── Network ─────────────────────────────────────────────────────────────────

ARBITRUM_MAINNET_RPC  = "https://arb1.arbitrum.io/rpc"
ARBITRUM_SEPOLIA_RPC  = "https://sepolia-rollup.arbitrum.io/rpc"

# ─── GMX V2 Mainnet (rate signal) ────────────────────────────────────────────

GMX_DATASTORE_MAIN   = "0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8"
ETH_USDC_MKT_MAIN    = "0x70d95587d40A2caf56bd97485aB3Eec10Bee6336"
BTC_USDC_MKT_MAIN    = "0x47c031236e19d024b42f8AE6780E44A573170703"
WETH_MAIN            = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"
WBTC_B_MAIN          = "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f"

# ─── GMX V2 Sepolia (trade execution) ────────────────────────────────────────

GMX_ADAPTER_SEP      = "0x148B975C477bdf6196670Fa09F9AA12C86F1Fe00"
GMX_DATASTORE_SEP    = "0xCF4c2C4c53157BcC01A596e3788fFF69cBBCD201"
GMX_EXCHANGE_SEP     = "0xEd50B2A1eF0C35DAaF08Da6486971180237909c3"
GMX_ORDER_VAULT_SEP  = "0x1b8AC606de71686fd2a1AEDEcb6E0EFba28909a2"
ETH_USDC_MKT_SEP     = "0xb6fC4C9eB02C35A134044526C62bb15014Ac0Bcc"  # WETH-USDC.SG
SG_USDC_SEP          = "0x3253a335E7bFfB4790Aa4C25C4250d206E9b9773"  # Stargate USDC
WETH_SEP             = "0x980B62Da83eFf3D4576C647993b0c1D7faf17c73"

# ─── gTrade Mainnet (rate signal) ────────────────────────────────────────────

GTRADE_DIAMOND_MAIN  = "0xFF162c694eAA571f685030649814282eA457f169"
GTRADE_USDC_COLL_IDX = 3   # collateralIndex for USDC on mainnet
GTRADE_BTC_PAIR      = 0
GTRADE_ETH_PAIR      = 1

# ─── gTrade Sepolia (trade execution) ────────────────────────────────────────

GTRADE_DIAMOND_SEP   = "0xd659a15812064C79E189fd950A189b15c75d3186"
GNS_USDC_SEP         = "0x4cC7EbEeD5EA3adf3978F19833d2E1f3e8980cD6"  # gTrade test USDC
GTRADE_USDC_COLL_IDX_SEP = 3   # collateralIndex for GNS_USDC on Sepolia

# ─── Wallet ───────────────────────────────────────────────────────────────────

DEPLOYER_ADDRESS     = "0xb53d98C60f327a61aa34C29762efD4EfD47BA756"
# DEPLOYER_PRIVATE_KEY loaded from .env at runtime (never hardcode here)

# ─── Trading Parameters ───────────────────────────────────────────────────────

RATE_THRESHOLD       = 0.0005  # 0.05%/day — lowered from 0.1% to fire at current GMX rates (~0.058%/day)
PREFER_GTRADE_RATIO  = 2.0     # prefer gTrade when it's ≥2x cheaper than GMX
COLLATERAL_USD       = 10.0    # $10 collateral per position
LEVERAGE             = 5.0     # 5x leverage → $50 position
GMX_EXEC_FEE_WEI     = 1_000_000_000_000_000  # 0.001 ETH

# ─── Arbitrum Block Time ─────────────────────────────────────────────────────

ARB_BLOCKS_PER_DAY   = 345_600  # ~4 blocks/sec × 86400 sec

# ─── Log Paths ────────────────────────────────────────────────────────────────

import os
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
TMP_DIR      = _ROOT / ".tmp"
LOG_FILE     = TMP_DIR / "agent_v1_log.jsonl"
SUMMARY_FILE = TMP_DIR / "agent_v1_summary.txt"

TMP_DIR.mkdir(parents=True, exist_ok=True)
