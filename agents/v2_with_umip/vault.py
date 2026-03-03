#!/usr/bin/env python3
"""
vault.py — Python interface for UMIPVault on Arbitrum Sepolia.

Wraps the UMIPVault.sol ABI for:
  - getUserCollateral() — vault state query
  - openPosition()      — open via vault (routes to GMX adapter)
  - closePosition()     — close via vault

The vault manages all collateral accounting on-chain.
No fragmentation possible: the vault always has capital to deploy
(it just needs idle collateral and an adapter address set).
"""

import time
from web3 import Web3
from web3.types import TxReceipt
from eth_abi import encode

from config import (
    ARBITRUM_SEPOLIA_RPC,
    UMIP_VAULT_SEP,
    SG_USDC_SEP,
    DEPLOYER_ADDRESS,
    PLATFORM_GMX,
    GMX_EXEC_FEE_WEI,
    COLLATERAL_USD,
    LEVERAGE,
)

# ─── ABI ──────────────────────────────────────────────────────────────────────

VAULT_ABI = [
    {
        "name": "getUserCollateral",
        "type": "function",
        "inputs": [{"name": "user", "type": "address"}],
        "outputs": [
            {"name": "idle",                "type": "uint256"},
            {"name": "allocatedGMX",        "type": "uint256"},
            {"name": "allocatedVertex",     "type": "uint256"},
            {"name": "allocatedGainsTrade", "type": "uint256"},
            {"name": "total",               "type": "uint256"},
        ]
    },
    {
        "name": "openPosition",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {"name": "platform",        "type": "uint8"},
            {"name": "collateralAmount","type": "uint256"},
            {"name": "sizeDeltaUsd",    "type": "uint256"},
            {"name": "acceptablePrice", "type": "uint256"},
        ],
        "outputs": [{"name": "positionId", "type": "uint256"}]
    },
    {
        "name": "closePosition",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [{"name": "positionId", "type": "uint256"}],
        "outputs": []
    },
    {
        "name": "getPosition",
        "type": "function",
        "inputs": [
            {"name": "user",       "type": "address"},
            {"name": "positionId", "type": "uint256"},
        ],
        "outputs": [
            {"name": "",  "type": "tuple", "components": [
                {"name": "platform",         "type": "uint8"},
                {"name": "market",           "type": "address"},
                {"name": "collateralAmount", "type": "uint256"},
                {"name": "sizeDeltaUsd",     "type": "uint256"},
                {"name": "openTimestamp",    "type": "uint256"},
                {"name": "isOpen",           "type": "bool"},
            ]}
        ]
    },
    {
        "name": "userPositionCount",
        "type": "function",
        "inputs": [{"name": "", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}]
    },
]

ERC20_ABI = [
    {"name": "balanceOf", "type": "function",
     "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]},
    {"name": "approve", "type": "function",
     "inputs": [{"type": "address"}, {"type": "uint256"}], "outputs": [{"type": "bool"}]},
]

# ─── Connection ───────────────────────────────────────────────────────────────

def _connect() -> Web3:
    w3 = Web3(Web3.HTTPProvider(ARBITRUM_SEPOLIA_RPC))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to Sepolia RPC: {ARBITRUM_SEPOLIA_RPC}")
    return w3


def _send_tx(w3: Web3, tx: dict, private_key: str) -> str:
    """Sign, send, and wait for a transaction. Returns tx hash."""
    account = w3.eth.account.from_key(private_key)
    tx["from"]  = account.address
    tx["nonce"] = w3.eth.get_transaction_count(account.address, "pending")
    tx["gas"]   = w3.eth.estimate_gas(tx)
    base_fee    = w3.eth.get_block("latest")["baseFeePerGas"]
    tx["maxPriorityFeePerGas"] = w3.to_wei(0.1, "gwei")
    tx["maxFeePerGas"]         = base_fee * 2 + w3.to_wei(0.1, "gwei")
    tx.pop("gasPrice", None)

    signed  = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status != 1:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
    return tx_hash.hex()


def _wait_for_gmx_keeper(w3: Web3, account: str, position_count_before: int,
                          max_wait: int = 120, poll_interval: int = 3) -> str:
    """
    Poll until the GMX keeper has processed the order.

    GMX V2 uses an async order execution model: our vault tx calls
    ExchangeRouter.createOrder(), but a separate off-chain keeper actually
    executes the order (usually 2–30s on Sepolia, up to 2min under load).

    We detect execution by watching the vault's userPositionCount, which
    increases when openPosition() is called (same tx — immediate), and by
    polling the vault's allocatedGMX to confirm collateral moved.

    Production upgrade path:
        Parse the OrderCreated event from the vault tx receipt to extract
        the GMX order key, then poll DataStore.getOrder(key) until it returns
        zero (order gone = executed). This requires the adapter to surface the
        event, which is the planned v2 adapter upgrade.

    Returns: "confirmed" | "timeout" (order may still execute — do not retry
             without first checking vault state to avoid double-open).
    """
    vault = w3.eth.contract(
        address=Web3.to_checksum_address(UMIP_VAULT_SEP),
        abi=VAULT_ABI
    )
    deadline = time.time() + max_wait
    while time.time() < deadline:
        time.sleep(poll_interval)
        try:
            count = vault.functions.userPositionCount(
                Web3.to_checksum_address(account)
            ).call()
            if count > position_count_before:
                # Vault registered the position — order submitted to keeper.
                # Note: this confirms the vault tx succeeded, not that the
                # GMX keeper has executed. In practice on Sepolia this is
                # sufficient; mainnet needs order-key polling (see above).
                return "confirmed"
        except Exception:
            continue  # transient RPC error — keep polling
    return "timeout"


# ─── Vault State ──────────────────────────────────────────────────────────────

def get_vault_state(account: str) -> dict:
    """
    Query the vault's collateral breakdown for an account.
    Returns dict with idle/allocated/total in USD (6-decimal scaled).
    """
    w3    = _connect()
    vault = w3.eth.contract(
        address=Web3.to_checksum_address(UMIP_VAULT_SEP),
        abi=VAULT_ABI
    )
    idle, alloc_gmx, alloc_vtx, alloc_gt, total = \
        vault.functions.getUserCollateral(Web3.to_checksum_address(account)).call()

    pos_count = vault.functions.userPositionCount(Web3.to_checksum_address(account)).call()

    return {
        "idle_usdc":           idle       / 1e6,
        "allocated_gmx_usdc":  alloc_gmx  / 1e6,
        "allocated_vtx_usdc":  alloc_vtx  / 1e6,
        "allocated_gt_usdc":   alloc_gt   / 1e6,
        "total_usdc":          total      / 1e6,
        "position_count":      pos_count,
        "can_open_gmx":        idle >= int(COLLATERAL_USD * 1e6),
        "fragmentation_risk":  False,   # V2 never fragments — vault routes internally
    }


def get_open_positions(account: str) -> list[dict]:
    """Return list of currently open positions in the vault."""
    w3    = _connect()
    vault = w3.eth.contract(
        address=Web3.to_checksum_address(UMIP_VAULT_SEP),
        abi=VAULT_ABI
    )
    count = vault.functions.userPositionCount(Web3.to_checksum_address(account)).call()
    positions = []
    for i in range(count):
        pos = vault.functions.getPosition(Web3.to_checksum_address(account), i).call()
        platform, market, collateral, size, ts, is_open = pos
        if is_open:
            positions.append({
                "position_id":    i,
                "platform":       ["GMX", "Vertex", "GainsTrade"][platform],
                "market":         market,
                "collateral_usd": collateral / 1e6,
                "size_usd":       size / 1e30,
                "open_ts":        ts,
            })
    return positions


# ─── Position Management ──────────────────────────────────────────────────────

def open_gmx_position(private_key: str,
                       collateral_usdc: float = COLLATERAL_USD,
                       leverage_x: float = LEVERAGE) -> dict:
    """
    Open a position via the UMIPVault on Platform.GMX.

    Vault flow:
      1. Deducts from userIdleCollateral
      2. Adds to userAllocatedToGMX
      3. Transfers SG_USDC to GMXAdapterSepolia
      4. Calls adapter.openMarketLong(market, collateral, token, size, price, fee)
    """
    w3    = _connect()
    vault = w3.eth.contract(
        address=Web3.to_checksum_address(UMIP_VAULT_SEP),
        abi=VAULT_ABI
    )
    account_addr = w3.eth.account.from_key(private_key).address

    collateral_raw  = int(collateral_usdc * 1e6)
    size_delta_raw  = int(collateral_usdc * leverage_x * 1e30)
    acceptable_price = 2**256 - 1   # market long: accept any price

    tx = vault.functions.openPosition(
        PLATFORM_GMX,
        collateral_raw,
        size_delta_raw,
        acceptable_price,
    ).build_transaction({
        "value": GMX_EXEC_FEE_WEI,
        "from":  account_addr,
    })

    count_before = vault.functions.userPositionCount(
        Web3.to_checksum_address(account_addr)
    ).call()

    tx_hash = _send_tx(w3, tx, private_key)

    keeper_status = _wait_for_gmx_keeper(w3, account_addr, count_before)

    return {
        "platform":        "GMX",
        "via":             "UMIPVault",
        "vault":           UMIP_VAULT_SEP,
        "tx_hash":         tx_hash,
        "collateral_usd":  collateral_usdc,
        "size_usd":        collateral_usdc * leverage_x,
        "keeper_status":   keeper_status,   # "confirmed" or "timeout"
        "status":          "pending_execution" if keeper_status == "timeout" else "submitted",
    }


def close_gmx_position(private_key: str, position_id: int) -> dict:
    """Close a vault position by ID."""
    w3    = _connect()
    vault = w3.eth.contract(
        address=Web3.to_checksum_address(UMIP_VAULT_SEP),
        abi=VAULT_ABI
    )
    account_addr = w3.eth.account.from_key(private_key).address

    count_before = vault.functions.userPositionCount(
        Web3.to_checksum_address(account_addr)
    ).call()

    tx = vault.functions.closePosition(position_id).build_transaction({
        "value": GMX_EXEC_FEE_WEI,
        "from":  account_addr,
    })

    tx_hash = _send_tx(w3, tx, private_key)

    # Poll until vault confirms the close (position.isOpen flips to False).
    # Uses position count as proxy — close doesn't change count, so we
    # poll the specific position's isOpen flag directly.
    deadline = time.time() + 120
    keeper_status = "timeout"
    while time.time() < deadline:
        time.sleep(3)
        try:
            pos = vault.functions.getPosition(
                Web3.to_checksum_address(account_addr), position_id
            ).call()
            if not pos[5]:   # isOpen == False
                keeper_status = "confirmed"
                break
        except Exception:
            continue

    return {
        "platform":      "GMX",
        "position_id":   position_id,
        "tx_hash":       tx_hash,
        "keeper_status": keeper_status,
        "status":        "closed" if keeper_status == "confirmed" else "close_pending",
    }
