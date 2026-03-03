#!/usr/bin/env python3
"""
config.py — Central configuration for Agent V2 (With UMIP).

Same trading thresholds as V1. Different architecture: all collateral
flows through UMIPVault instead of separate wallets.
"""

# ─── Network ─────────────────────────────────────────────────────────────────

ARBITRUM_MAINNET_RPC = "https://arb1.arbitrum.io/rpc"
ARBITRUM_SEPOLIA_RPC = "https://sepolia-rollup.arbitrum.io/rpc"

# ─── UMIPVault V3 (deployed 2026-03-02, Circle USDC for public faucet access) ──

UMIP_VAULT_SEP       = "0xE516aDB78835B684cE95F5030296602fD96F3f86"
SG_USDC_SEP          = "0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d"  # Circle USDC (faucet.circle.com)
ETH_USD_MKT_SEP      = "0xb6fC4C9eB02C35A134044526C62bb15014Ac0Bcc"
GMX_ADAPTER_SEP      = "0x148B975C477bdf6196670Fa09F9AA12C86F1Fe00"
DEPLOYER_ADDRESS     = "0xb53d98C60f327a61aa34C29762efD4EfD47BA756"

# Platform enum values matching UMIPVault.Platform
PLATFORM_GMX         = 0
PLATFORM_VERTEX      = 1
PLATFORM_GAINS_TRADE = 2

# ─── GMX Mainnet (rate signal — same as V1) ──────────────────────────────────

GMX_DATASTORE_MAIN   = "0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8"
ETH_USDC_MKT_MAIN    = "0x70d95587d40A2caf56bd97485aB3Eec10Bee6336"
BTC_USDC_MKT_MAIN    = "0x47c031236e19d024b42f8AE6780E44A573170703"
WETH_MAIN            = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"
WBTC_B_MAIN          = "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f"

# ─── gTrade Mainnet (rate signal — same as V1) ───────────────────────────────

GTRADE_DIAMOND_MAIN  = "0xFF162c694eAA571f685030649814282eA457f169"
GTRADE_USDC_COLL_IDX = 3
GTRADE_BTC_PAIR      = 0
GTRADE_ETH_PAIR      = 1

# ─── Trading Parameters (identical to V1 for fair comparison) ────────────────

RATE_THRESHOLD       = 0.0005  # 0.05%/day — same as V1
COLLATERAL_USD       = 10.0    # $10 collateral per position (same as V1)
LEVERAGE             = 5.0     # 5x leverage → $50 position (same as V1)
GMX_EXEC_FEE_WEI     = 1_000_000_000_000_000  # 0.001 ETH

# ─── Arbitrum Block Time ─────────────────────────────────────────────────────

ARB_BLOCKS_PER_DAY   = 345_600

# ─── Log Paths ────────────────────────────────────────────────────────────────

import os
from pathlib import Path

_ROOT        = Path(__file__).parent.parent.parent
TMP_DIR      = _ROOT / ".tmp"
LOG_FILE     = TMP_DIR / "agent_v2_log.jsonl"
SUMMARY_FILE = TMP_DIR / "agent_v2_summary.txt"

TMP_DIR.mkdir(parents=True, exist_ok=True)
