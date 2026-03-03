#!/usr/bin/env python3
"""
positions.py — Open/close/query positions on GMX Sepolia and gTrade Sepolia.

Agent V1: Demonstrates capital fragmentation problem.
  - GMX wallet:    900 SG USDC in adapter → CAN open GMX positions
  - gTrade wallet: 0 GNS_USDC            → CANNOT open gTrade positions
  - Result: Agent is FORCED onto GMX even when gTrade has 33x lower fees.

Position open is async on GMX V2 (keeper-fulfilled order, ~2-10 sec).
Positions on gTrade are also async (oracle callback, ~3-7 blocks).

Usage:
  from positions import open_gmx_long, close_gmx_long, get_gmx_position
  from positions import get_gtrade_positions, get_platform_balances
"""

import time
from web3 import Web3
from eth_abi import encode

# ─── Sepolia Network Config ────────────────────────────────────────────────────

SEPOLIA_RPC = "https://sepolia-rollup.arbitrum.io/rpc"

# GMX V2 Sepolia
GMX_ADAPTER    = "0x148B975C477bdf6196670Fa09F9AA12C86F1Fe00"
GMX_DATASTORE  = "0xCF4c2C4c53157BcC01A596e3788fFF69cBBCD201"
ETH_MKT_SEP    = "0xb6fC4C9eB02C35A134044526C62bb15014Ac0Bcc"  # WETH-USDC.SG market
SG_USDC        = "0x3253a335E7bFfB4790Aa4C25C4250d206E9b9773"  # Stargate USDC (GMX collateral)
WETH_SEP       = "0x980B62Da83eFf3D4576C647993b0c1D7faf17c73"

# gTrade Sepolia
GTRADE_DIAMOND  = "0xd659a15812064C79E189fd950A189b15c75d3186"
GNS_USDC        = "0x4cC7EbEeD5EA3adf3978F19833d2E1f3e8980cD6"  # gTrade test USDC
USDC_COLL_IDX   = 3     # collateralIndex for GNS_USDC on gTrade Sepolia
ETH_PAIR_IDX    = 1     # BTC=0, ETH=1 on gTrade

# Execution costs
GMX_EXEC_FEE    = 1_000_000_000_000_000   # 0.001 ETH (dominant cost on Sepolia)
BLOCKS_TO_WAIT  = 15                       # blocks to wait for order execution

# ─── ABIs ─────────────────────────────────────────────────────────────────────

GMX_ADAPTER_ABI = [
    {
        "name": "openMarketLong",
        "type": "function",
        "inputs": [
            {"name": "market",           "type": "address"},
            {"name": "collateralAmount", "type": "uint256"},
            {"name": "collateralToken",  "type": "address"},
            {"name": "sizeDeltaUsd",     "type": "uint256"},
            {"name": "acceptablePrice",  "type": "uint256"},
            {"name": "executionFee",     "type": "uint256"}
        ],
        "outputs": [{"name": "orderKey", "type": "bytes32"}]
    },
    {
        "name": "closeMarketLong",
        "type": "function",
        "inputs": [
            {"name": "market",          "type": "address"},
            {"name": "collateralToken", "type": "address"},
            {"name": "sizeDeltaUsd",    "type": "uint256"},
            {"name": "acceptablePrice", "type": "uint256"},
            {"name": "executionFee",    "type": "uint256"}
        ],
        "outputs": [{"name": "orderKey", "type": "bytes32"}]
    }
]

DATASTORE_ABI = [
    {"name": "getUint",    "type": "function",
     "inputs": [{"type": "bytes32"}], "outputs": [{"type": "uint256"}]},
    {"name": "getInt",     "type": "function",
     "inputs": [{"type": "bytes32"}], "outputs": [{"type": "int256"}]},
    {"name": "getAddress", "type": "function",
     "inputs": [{"type": "bytes32"}], "outputs": [{"type": "address"}]}
]

GTRADE_ABI = [
    {
        "name": "openTrade",
        "type": "function",
        "inputs": [
            {"name": "_trade", "type": "tuple", "components": [
                {"name": "user",               "type": "address"},
                {"name": "index",              "type": "uint32"},
                {"name": "pairIndex",          "type": "uint16"},
                {"name": "leverage",           "type": "uint24"},
                {"name": "long",               "type": "bool"},
                {"name": "isOpen",             "type": "bool"},
                {"name": "collateralIndex",    "type": "uint8"},
                {"name": "tradeType",          "type": "uint8"},
                {"name": "collateralAmount",   "type": "uint120"},
                {"name": "openPrice",          "type": "uint64"},
                {"name": "tp",                 "type": "uint64"},
                {"name": "sl",                 "type": "uint64"},
                {"name": "isCounterTrade",     "type": "bool"},
                {"name": "positionSizeToken",  "type": "uint160"},
                {"name": "__placeholder",      "type": "uint24"}
            ]},
            {"name": "_maxSlippageP", "type": "uint16"},
            {"name": "_referrer",     "type": "address"}
        ],
        "outputs": []
    },
    {
        "name": "closeTradeMarket",
        "type": "function",
        "inputs": [
            {"name": "_index",         "type": "uint32"},
            {"name": "_expectedPrice", "type": "uint64"}
        ],
        "outputs": []
    },
    {
        "name": "getTrades",
        "type": "function",
        "inputs": [{"name": "_trader", "type": "address"}],
        "outputs": [{"name": "", "type": "tuple[]", "components": [
            {"name": "user",               "type": "address"},
            {"name": "index",              "type": "uint32"},
            {"name": "pairIndex",          "type": "uint16"},
            {"name": "leverage",           "type": "uint24"},
            {"name": "long",               "type": "bool"},
            {"name": "isOpen",             "type": "bool"},
            {"name": "collateralIndex",    "type": "uint8"},
            {"name": "tradeType",          "type": "uint8"},
            {"name": "collateralAmount",   "type": "uint120"},
            {"name": "openPrice",          "type": "uint64"},
            {"name": "tp",                 "type": "uint64"},
            {"name": "sl",                 "type": "uint64"},
            {"name": "isCounterTrade",     "type": "bool"},
            {"name": "positionSizeToken",  "type": "uint160"},
            {"name": "__placeholder",      "type": "uint24"}
        ]}]
    }
]

ERC20_ABI = [
    {"name": "balanceOf", "type": "function",
     "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]},
    {"name": "approve",   "type": "function",
     "inputs": [{"type": "address"}, {"type": "uint256"}], "outputs": [{"type": "bool"}]}
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _connect() -> Web3:
    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to Sepolia RPC: {SEPOLIA_RPC}")
    return w3


def _send_tx(w3: Web3, tx: dict, private_key: str) -> str:
    """Sign, send, and wait for a transaction. Returns tx hash."""
    account = w3.eth.account.from_key(private_key)
    tx["from"]  = account.address
    tx["nonce"] = w3.eth.get_transaction_count(account.address, "pending")
    tx["gas"]   = w3.eth.estimate_gas(tx)
    # Arbitrum Sepolia uses EIP-1559 (Type 2) — use maxFeePerGas, not gasPrice
    base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
    tx["maxPriorityFeePerGas"] = w3.to_wei(0.1, "gwei")
    tx["maxFeePerGas"]         = base_fee * 2 + w3.to_wei(0.1, "gwei")
    tx.pop("gasPrice", None)

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status != 1:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
    return tx_hash.hex()


def _gmx_position_key(account: str, market: str, collateral: str, is_long: bool) -> bytes:
    """Compute GMX V2 position key: keccak(account, market, collateral, isLong)."""
    return Web3.keccak(encode(
        ['address', 'address', 'address', 'bool'],
        [Web3.to_checksum_address(account),
         Web3.to_checksum_address(market),
         Web3.to_checksum_address(collateral),
         is_long]
    ))

# ─── Platform Balances ────────────────────────────────────────────────────────

def get_platform_balances(account: str) -> dict:
    """
    Return available collateral balances for each platform.
    GMX uses SG USDC held in the adapter contract.
    gTrade uses GNS_USDC held directly by the account.
    """
    w3 = _connect()
    sg_usdc_tok = w3.eth.contract(address=Web3.to_checksum_address(SG_USDC),  abi=ERC20_ABI)
    gns_usdc_tok = w3.eth.contract(address=Web3.to_checksum_address(GNS_USDC), abi=ERC20_ABI)

    adapter_sg  = sg_usdc_tok.functions.balanceOf(Web3.to_checksum_address(GMX_ADAPTER)).call()
    account_gns = gns_usdc_tok.functions.balanceOf(Web3.to_checksum_address(account)).call()
    eth_bal     = w3.eth.get_balance(Web3.to_checksum_address(account))

    return {
        "gmx_usdc":    adapter_sg  / 1e6,   # SG USDC available in adapter
        "gtrade_usdc": account_gns / 1e6,   # GNS_USDC available in account
        "eth":         eth_bal     / 1e18,
        "can_open_gmx":    adapter_sg  >= 10_000_000 and eth_bal >= GMX_EXEC_FEE,
        "can_open_gtrade": account_gns >= 10_000_000,
    }

# ─── GMX Position Management ──────────────────────────────────────────────────

def open_gmx_long(
    private_key: str,
    collateral_usdc: float = 10.0,
    leverage_x: float = 5.0
) -> dict:
    """
    Open a market-long ETH/USD position on GMX Sepolia via the deployed adapter.
    Adapter already holds SG USDC — no pre-transfer needed.

    Returns: {order_key, tx_hash, collateral_usd, size_usd}
    """
    w3 = _connect()
    adapter = w3.eth.contract(
        address=Web3.to_checksum_address(GMX_ADAPTER),
        abi=GMX_ADAPTER_ABI
    )

    account_addr    = w3.eth.account.from_key(private_key).address
    collateral_raw  = int(collateral_usdc * 1e6)
    size_delta_raw  = int(collateral_usdc * leverage_x * 1e30)  # GMX V2: 1e30 USD
    acceptable_price = 2**256 - 1   # market order long: accept any price

    tx = adapter.functions.openMarketLong(
        Web3.to_checksum_address(ETH_MKT_SEP),
        collateral_raw,
        Web3.to_checksum_address(SG_USDC),
        size_delta_raw,
        acceptable_price,
        GMX_EXEC_FEE
    ).build_transaction({"value": GMX_EXEC_FEE, "from": account_addr})

    tx_hash = _send_tx(w3, tx, private_key)

    # Wait for keeper fulfillment (Sepolia: ~2-10 sec / 7 blocks)
    time.sleep(12)

    return {
        "platform":       "GMX",
        "market":         "ETH/USD",
        "tx_hash":        tx_hash,
        "collateral_usd": collateral_usdc,
        "size_usd":       collateral_usdc * leverage_x,
        "status":         "pending_execution",
    }


def close_gmx_long(private_key: str, size_usd: float) -> dict:
    """
    Close an existing GMX long position (full size).
    Returns: {tx_hash, status}
    """
    w3 = _connect()
    adapter = w3.eth.contract(
        address=Web3.to_checksum_address(GMX_ADAPTER),
        abi=GMX_ADAPTER_ABI
    )

    account_addr     = w3.eth.account.from_key(private_key).address
    size_delta_raw   = int(size_usd * 1e30)
    acceptable_price = 0   # market order close: accept any price

    tx = adapter.functions.closeMarketLong(
        Web3.to_checksum_address(ETH_MKT_SEP),
        Web3.to_checksum_address(SG_USDC),
        size_delta_raw,
        acceptable_price,
        GMX_EXEC_FEE
    ).build_transaction({"value": GMX_EXEC_FEE, "from": account_addr})

    tx_hash = _send_tx(w3, tx, private_key)
    time.sleep(12)

    return {"platform": "GMX", "tx_hash": tx_hash, "status": "close_pending"}


def get_gmx_position(account: str) -> dict | None:
    """
    Query GMX DataStore for an open long ETH/USD position.
    Returns position dict or None if no position.

    Position is stored under the ADAPTER address (since adapter opens the trade).
    """
    w3 = _connect()
    ds = w3.eth.contract(address=Web3.to_checksum_address(GMX_DATASTORE), abi=DATASTORE_ABI)

    pos_key = _gmx_position_key(GMX_ADAPTER, ETH_MKT_SEP, SG_USDC, True)

    size_hash  = Web3.keccak(encode(['string'], ['SIZE_IN_USD']))
    coll_hash  = Web3.keccak(encode(['string'], ['COLLATERAL_AMOUNT']))
    price_hash = Web3.keccak(encode(['string'], ['SIZE_IN_TOKENS']))

    size_key  = Web3.keccak(encode(['bytes32', 'bytes32'], [size_hash,  pos_key]))
    coll_key  = Web3.keccak(encode(['bytes32', 'bytes32'], [coll_hash,  pos_key]))
    price_key = Web3.keccak(encode(['bytes32', 'bytes32'], [price_hash, pos_key]))

    size_raw  = ds.functions.getUint(size_key).call()
    coll_raw  = ds.functions.getUint(coll_key).call()
    size_tok  = ds.functions.getUint(price_key).call()

    if size_raw == 0:
        return None

    size_usd  = size_raw / 1e30
    coll_usd  = coll_raw / 1e30

    # Approximate entry price: size_usd / (size_tokens / 1e18)
    entry_price = (size_usd / (size_tok / 1e18)) if size_tok > 0 else 0

    return {
        "platform":    "GMX",
        "market":      "ETH/USD",
        "size_usd":    size_usd,
        "collateral":  coll_usd,
        "leverage":    size_usd / coll_usd if coll_usd > 0 else 0,
        "entry_price": entry_price,
        "is_long":     True,
    }

# ─── gTrade Position Management ───────────────────────────────────────────────

def open_gtrade_long(
    private_key: str,
    collateral_usdc: float = 10.0,
    leverage_x: int = 5
) -> dict:
    """
    Attempt to open a market-long ETH/USD position on gTrade Sepolia.
    WILL FAIL if account has insufficient GNS_USDC — logs as fragmentation event.
    """
    w3       = _connect()
    account  = w3.eth.account.from_key(private_key).address
    gns_usdc = w3.eth.contract(address=Web3.to_checksum_address(GNS_USDC), abi=ERC20_ABI)
    balance  = gns_usdc.functions.balanceOf(Web3.to_checksum_address(account)).call()

    needed = int(collateral_usdc * 1e6)
    if balance < needed:
        return {
            "platform":     "gTrade",
            "market":       "ETH/USD",
            "status":       "FAILED_INSUFFICIENT_FUNDS",
            "balance_usdc": balance / 1e6,
            "needed_usdc":  collateral_usdc,
            "fragmentation": True,
            "message": (
                f"FRAGMENTATION: Cannot open gTrade position. "
                f"Need {collateral_usdc:.2f} GNS_USDC, have {balance/1e6:.2f}. "
                f"Capital is locked in GMX adapter (SG USDC form). "
                f"Cross-wallet transfer requires manual bridge."
            )
        }

    # Approve and open
    diamond = w3.eth.contract(address=Web3.to_checksum_address(GTRADE_DIAMOND), abi=GTRADE_ABI)

    # Approve collateral
    approve_tx = gns_usdc.functions.approve(
        Web3.to_checksum_address(GTRADE_DIAMOND), needed
    ).build_transaction({})
    _send_tx(w3, approve_tx, private_key)

    # Build trade struct
    trade = (
        Web3.to_checksum_address(account),  # user
        0,        # index (assigned by contract)
        ETH_PAIR_IDX,   # pairIndex (ETH=1)
        leverage_x * 1000,  # leverage (in 0.001x units, e.g. 5000 = 5x)
        True,     # long
        True,     # isOpen
        USDC_COLL_IDX,  # collateralIndex (3 = GNS_USDC)
        0,        # tradeType (0 = market)
        needed,   # collateralAmount
        0,        # openPrice (0 = current market price)
        0,        # tp (0 = no TP)
        0,        # sl (0 = no SL)
        False,    # isCounterTrade
        0,        # positionSizeToken (computed by contract)
        0         # __placeholder
    )

    open_tx = diamond.functions.openTrade(
        trade, 1000, Web3.to_checksum_address("0x0000000000000000000000000000000000000000")
    ).build_transaction({})
    tx_hash = _send_tx(w3, open_tx, private_key)

    return {
        "platform":       "gTrade",
        "market":         "ETH/USD",
        "tx_hash":        tx_hash,
        "collateral_usd": collateral_usdc,
        "size_usd":       collateral_usdc * leverage_x,
        "status":         "pending_oracle",
    }


def get_gtrade_positions(account: str) -> list[dict]:
    """Return all open gTrade positions for an account."""
    w3      = _connect()
    diamond = w3.eth.contract(address=Web3.to_checksum_address(GTRADE_DIAMOND), abi=GTRADE_ABI)
    trades  = diamond.functions.getTrades(Web3.to_checksum_address(account)).call()

    result = []
    for t in trades:
        collateral = t[8] / 1e6      # collateralAmount (GNS_USDC = 6 decimals)
        leverage   = t[3] / 1000.0   # leverage in 0.001x units
        result.append({
            "platform":    "gTrade",
            "market":      "ETH/USD" if t[2] == 1 else "BTC/USD",
            "index":       t[1],
            "pair_index":  t[2],
            "leverage":    leverage,
            "long":        t[4],
            "collateral":  collateral,
            "size_usd":    collateral * leverage,
            "open_price":  t[9] / 1e10,  # openPrice in 1e10 format
            "tp":          t[10] / 1e10,
            "sl":          t[11] / 1e10,
        })
    return result


def close_gtrade_long(private_key: str, trade_index: int) -> dict:
    """Close a gTrade position by trade index."""
    w3      = _connect()
    diamond = w3.eth.contract(address=Web3.to_checksum_address(GTRADE_DIAMOND), abi=GTRADE_ABI)

    tx = diamond.functions.closeTradeMarket(trade_index, 0).build_transaction({})
    tx_hash = _send_tx(w3, tx, private_key)

    return {"platform": "gTrade", "trade_index": trade_index,
            "tx_hash": tx_hash, "status": "close_submitted"}

# ─── Health Check ─────────────────────────────────────────────────────────────

def get_all_positions(account: str) -> dict:
    """
    Return a unified view of all open positions and platform balances.
    This is the main entry point for the agent's health monitoring loop.
    """
    balances   = get_platform_balances(account)
    gmx_pos    = get_gmx_position(account)  # uses adapter address internally
    gtrade_pos = get_gtrade_positions(account)

    total_collateral = 0
    if gmx_pos:
        total_collateral += gmx_pos["collateral"]
    for t in gtrade_pos:
        total_collateral += t["collateral"]

    return {
        "account":         account,
        "balances":        balances,
        "gmx_position":    gmx_pos,
        "gtrade_positions": gtrade_pos,
        "total_collateral": total_collateral,
        "has_gmx":         gmx_pos is not None,
        "has_gtrade":      len(gtrade_pos) > 0,
        "fragmentation_risk": (
            balances["can_open_gtrade"] is False and balances["can_open_gmx"] is True
        )
    }


if __name__ == "__main__":
    import os
    pk = os.getenv("DEPLOYER_PRIVATE_KEY")
    if not pk:
        print("Set DEPLOYER_PRIVATE_KEY in .env")
        raise SystemExit(1)

    w3 = _connect()
    account = w3.eth.account.from_key(pk).address
    print(f"\nAccount: {account}")

    state = get_all_positions(account)
    print(f"\nBalances:")
    print(f"  GMX (SG USDC in adapter): {state['balances']['gmx_usdc']:.2f}")
    print(f"  gTrade (GNS_USDC):        {state['balances']['gtrade_usdc']:.2f}")
    print(f"  ETH:                      {state['balances']['eth']:.4f}")
    print(f"  Can open GMX:             {state['balances']['can_open_gmx']}")
    print(f"  Can open gTrade:          {state['balances']['can_open_gtrade']}")

    print(f"\nGMX position:    {state['gmx_position']}")
    print(f"gTrade positions: {state['gtrade_positions']}")
    print(f"\nFragmentation risk: {state['fragmentation_risk']}")
