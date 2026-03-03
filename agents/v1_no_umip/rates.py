#!/usr/bin/env python3
"""
rates.py — Fetch and compare GMX V2 and gTrade funding/borrowing rates on Arbitrum mainnet.

Agent V1: No UMIP — two separate wallets, demonstrates collateral fragmentation problem.
Day 1: Rate fetching from mainnet as signal for trading decisions.

Key findings (2026-02-19):
- GMX ETH/USD: funding rate driven by OI imbalance (longs >> shorts = 0.13%/day)
- gTrade ETH/USD: borrowing fee per block = 1 unit/1e10, group fee = 0 → ~0.003%/day
- Rate difference: GMX charges ~37x more for ETH/USD longs at this moment

gTrade struct layouts confirmed via selector decode + on-chain verification:
  BorrowingPair: (uint16 groupIndex, uint48 accFeeLong, uint48 accFeeShort,
                  uint48 accLastUpdatedBlock, uint32 feePerBlock)
  BorrowingGroup: (uint32 feePerBlock, uint48 accFeeLong, uint48 accFeeShort,
                   uint48 accLastUpdatedBlock, uint32 placeholder)

Usage:
  python3 rates.py               — print rates and exit
  from rates import fetch_rates  — returns list of rate dicts
"""

from datetime import datetime, timezone
from web3 import Web3
from eth_abi import encode

# ─── Config ───────────────────────────────────────────────────────────────────

ARBITRUM_RPC = "https://arb1.arbitrum.io/rpc"

# Flag positions for logging when rate exceeds this threshold
RATE_THRESHOLD = 0.0005  # 0.05%/day — lowered to fire at current GMX rates

# GMX V2 Addresses (Arbitrum Mainnet)
GMX_DATASTORE        = "0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8"
ETH_USDC_MARKET      = "0x70d95587d40A2caf56bd97485aB3Eec10Bee6336"
BTC_USDC_MARKET      = "0x47c031236e19d024b42f8AE6780E44A573170703"
WETH                 = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"
WBTC_B               = "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f"  # WBTC.b on Arbitrum

# gTrade Addresses (Arbitrum Mainnet)
GTRADE_DIAMOND       = "0xFF162c694eAA571f685030649814282eA457f169"
USDC_COLLATERAL_IDX  = 3   # 1=gDAI, 2=gETH, 3=USDC
BTC_PAIR_IDX         = 0   # gTrade pair 0 = BTC/USD
ETH_PAIR_IDX         = 1   # gTrade pair 1 = ETH/USD

# Arbitrum block time: current block ~433M / ~3.3 years ≈ 4 blocks/sec
# 4 * 86400 = 345,600 blocks/day
BLOCKS_PER_DAY = 345_600

# ─── ABIs ─────────────────────────────────────────────────────────────────────

DATASTORE_ABI = [
    {
        "name": "getUint",
        "type": "function",
        "inputs":  [{"name": "key",  "type": "bytes32"}],
        "outputs": [{"name": "",     "type": "uint256"}]
    }
]

GTRADE_ABI = [
    {
        "name": "getBorrowingPair",
        "type": "function",
        "inputs": [
            {"name": "_collateralIndex", "type": "uint8"},
            {"name": "_pairIndex",       "type": "uint16"}
        ],
        "outputs": [
            {"name": "groupIndex",           "type": "uint16"},
            {"name": "accFeeLong",           "type": "uint48"},
            {"name": "accFeeShort",          "type": "uint48"},
            {"name": "accLastUpdatedBlock",  "type": "uint48"},
            {"name": "feePerBlock",          "type": "uint32"}
        ]
    },
    {
        "name": "getBorrowingGroup",
        "type": "function",
        "inputs": [
            {"name": "_collateralIndex", "type": "uint8"},
            {"name": "_groupIndex",      "type": "uint16"}
        ],
        "outputs": [
            {"name": "feePerBlock",         "type": "uint32"},
            {"name": "accFeeLong",          "type": "uint48"},
            {"name": "accFeeShort",         "type": "uint48"},
            {"name": "accLastUpdatedBlock", "type": "uint48"},
            {"name": "placeholder",         "type": "uint32"}
        ]
    }
]

# ─── Rate Fetchers ─────────────────────────────────────────────────────────────

def get_gmx_rate(datastore, market_addr: str, long_token_addr: str, market_name: str) -> dict:
    """
    Compute daily funding rate for a GMX V2 market.

    GMX funding = (fundingFactor / 1e30) * (imbalance / totalOI) * 86400

    The funding factor is stored as 2e22 raw = 2e-8 per second per unit of OI ratio.
    OI ratio = abs(longOI - shortOI) / (longOI + shortOI)  — dimensionless 0..1

    Key derivation (must match Solidity's keccak256(abi.encode(...))):
      oi_key   = keccak256(abi.encode(keccak256("OPEN_INTEREST"), market, token, isLong))
      ff_key   = keccak256(abi.encode(keccak256("FUNDING_FACTOR"), market))
    """
    market     = Web3.to_checksum_address(market_addr)
    long_token = Web3.to_checksum_address(long_token_addr)

    oi_hash = Web3.keccak(encode(['string'], ['OPEN_INTEREST']))
    ff_hash = Web3.keccak(encode(['string'], ['FUNDING_FACTOR']))

    long_oi_key  = Web3.keccak(encode(['bytes32','address','address','bool'],
                                      [oi_hash, market, long_token, True]))
    short_oi_key = Web3.keccak(encode(['bytes32','address','address','bool'],
                                      [oi_hash, market, long_token, False]))
    ff_key       = Web3.keccak(encode(['bytes32','address'],
                                      [ff_hash, market]))

    long_oi        = datastore.functions.getUint(long_oi_key).call()
    short_oi       = datastore.functions.getUint(short_oi_key).call()
    funding_factor = datastore.functions.getUint(ff_key).call()

    long_oi_usd  = long_oi  / 1e30
    short_oi_usd = short_oi / 1e30
    total_oi     = long_oi + short_oi
    oi_imbalance = abs(long_oi - short_oi)
    oi_ratio     = oi_imbalance / total_oi if total_oi > 0 else 0.0

    # Rate: fundingFactor is 2e-8/s per unit of OI ratio (dimensionless)
    daily_rate = (funding_factor / 1e30) * oi_ratio * 86400
    direction  = "longs pay" if long_oi > short_oi else "shorts pay"

    return {
        "market":          market_name,
        "platform":        "GMX",
        "long_oi_usd":     long_oi_usd,
        "short_oi_usd":    short_oi_usd,
        "oi_ratio":        oi_ratio,
        "funding_factor":  funding_factor,
        "daily_rate":      daily_rate,
        "direction":       direction,
        "above_threshold": daily_rate > RATE_THRESHOLD,
    }


def get_gtrade_rate(diamond, pair_index: int, market_name: str) -> dict:
    """
    Compute daily borrowing rate for a gTrade pair.

    total_fee_per_block = pair.feePerBlock + group.feePerBlock
    daily_rate = total_fee_per_block / 1e10 * BLOCKS_PER_DAY

    Units: feePerBlock is in 1e10 format (e.g. 1 = 0.0000000001 per block)
    """
    pair_data  = diamond.functions.getBorrowingPair(USDC_COLLATERAL_IDX, pair_index).call()
    group_idx  = pair_data[0]   # groupIndex
    pair_fee   = pair_data[4]   # feePerBlock (slot 4 of struct)

    group_data = diamond.functions.getBorrowingGroup(USDC_COLLATERAL_IDX, group_idx).call()
    group_fee  = group_data[0]  # feePerBlock (slot 0 of group struct)

    total_fee  = pair_fee + group_fee
    daily_rate = total_fee / 1e10 * BLOCKS_PER_DAY

    return {
        "market":              market_name,
        "platform":            "gTrade",
        "pair_fee_per_block":  pair_fee,
        "group_fee_per_block": group_fee,
        "group_index":         group_idx,
        "total_fee_per_block": total_fee,
        "daily_rate":          daily_rate,
        "direction":           "all positions pay (borrowing fee)",
        "above_threshold":     daily_rate > RATE_THRESHOLD,
    }


# ─── Main Interface ────────────────────────────────────────────────────────────

def fetch_rates() -> list[dict]:
    """
    Fetch live funding/borrowing rates from both platforms.
    Returns a list of rate dicts, one per (platform, market) pair.
    """
    w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to {ARBITRUM_RPC}")

    datastore = w3.eth.contract(
        address=Web3.to_checksum_address(GMX_DATASTORE),
        abi=DATASTORE_ABI
    )
    diamond = w3.eth.contract(
        address=Web3.to_checksum_address(GTRADE_DIAMOND),
        abi=GTRADE_ABI
    )

    rates = [
        get_gmx_rate(datastore, ETH_USDC_MARKET, WETH,   "ETH/USD"),
        get_gmx_rate(datastore, BTC_USDC_MARKET, WBTC_B, "BTC/USD"),
        get_gtrade_rate(diamond, ETH_PAIR_IDX, "ETH/USD"),
        get_gtrade_rate(diamond, BTC_PAIR_IDX, "BTC/USD"),
    ]
    return rates


def print_rates(rates: list[dict]) -> None:
    """Print a formatted rate comparison table."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'='*62}")
    print(f"  FUNDING / BORROWING RATE COMPARISON  |  {ts}")
    print(f"{'='*62}")

    for r in rates:
        flag = "⚠ HIGH" if r["above_threshold"] else "✓"
        print(f"\n{r['platform']:8} {r['market']:10}  {r['daily_rate']*100:7.4f}%/day  [{flag}]")
        print(f"          Direction: {r['direction']}")
        if r["platform"] == "GMX":
            print(f"          Long OI : ${r['long_oi_usd']:>12,.0f}   "
                  f"Short OI: ${r['short_oi_usd']:>12,.0f}   "
                  f"ratio={r['oi_ratio']:.3f}")
        else:
            print(f"          Fee/blk : {r['total_fee_per_block']} "
                  f"(pair={r['pair_fee_per_block']}, group={r['group_fee_per_block']}, "
                  f"group_idx={r['group_index']})")

    # Arbitrage signals
    gmx_eth = next(r for r in rates if r["platform"] == "GMX"    and r["market"] == "ETH/USD")
    gt_eth  = next(r for r in rates if r["platform"] == "gTrade" and r["market"] == "ETH/USD")
    gmx_btc = next(r for r in rates if r["platform"] == "GMX"    and r["market"] == "BTC/USD")
    gt_btc  = next(r for r in rates if r["platform"] == "gTrade" and r["market"] == "BTC/USD")

    eth_ratio = gmx_eth["daily_rate"] / max(gt_eth["daily_rate"], 1e-10)
    btc_ratio = gmx_btc["daily_rate"] / max(gt_btc["daily_rate"], 1e-10)
    eth_diff  = (gmx_eth["daily_rate"] - gt_eth["daily_rate"]) * 100
    btc_diff  = (gmx_btc["daily_rate"] - gt_btc["daily_rate"]) * 100

    print(f"\n{'─'*62}")
    print("  ARBITRAGE SIGNAL (Agent V1 — no UMIP):")
    print(f"  ETH/USD: GMX is {eth_ratio:.0f}x more expensive  "
          f"(+{eth_diff:.4f}%/day on longs)")
    print(f"  BTC/USD: GMX is {btc_ratio:.0f}x more expensive  "
          f"(+{btc_diff:.4f}%/day)")
    print()
    print("  → Rational action: open all positions on gTrade (lower fees)")
    print("  → Problem WITHOUT UMIP: two separate wallets means capital")
    print("    is trapped. If one wallet runs low, cannot borrow from")
    print("    the other. Fragmentation = missed trades + liquidation risk.")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    rates = fetch_rates()
    print_rates(rates)
