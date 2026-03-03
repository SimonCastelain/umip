# UMIP Agent Template

A working autonomous funding rate arbitrage agent using UMIP for unified collateral across perpetual DEXes.

**No fragmentation. No capital locked on the wrong platform. One vault, every DEX.**

→ [Live sandbox](https://umip-sandbox.vercel.app) · [Live V1 vs V2 comparison](https://umip-dashboard.vercel.app)

---

## Quick Start (3 steps)

**1. Clone and install:**
```bash
git clone https://github.com/YOUR_USERNAME/umip-agent-template
cd umip-agent-template
pip install -r requirements.txt
```

**2. Configure:**
```bash
cp .env.example .env
# Edit .env: add your private key
```

**3. Get testnet USDC, deposit, run:**
```bash
# Get Circle USDC (select "Arbitrum Sepolia"): https://faucet.circle.com/
# Get testnet ETH: https://www.alchemy.com/faucets/arbitrum-sepolia

# Deposit into the public demo vault via the sandbox UI:
# https://umip-sandbox.vercel.app

# Run one cycle:
python agent.py

# Or run continuously (hourly):
python agent.py --loop
```

---

## What the Agent Does

Every cycle:
1. Fetches live ETH/USD funding rates from GMX and gTrade (mainnet signal)
2. Queries UMIPVault state (idle collateral, open positions)
3. If GMX funding rate > 0.05%/day → opens long (collects funding from shorts)
4. If rate drops below threshold → closes position
5. Logs every decision to `agent_log.jsonl`

**The UMIP advantage:** Capital lives in one vault. The vault routes to whatever platform
has the best rate. No wallet management, no fragmentation, no missed opportunities.

---

## Customize Your Strategy

Edit `agent.py` — the `decide()` function is where your strategy lives:

```python
def decide(rates: dict, vault_state: dict, open_positions: list) -> tuple[str, str]:
    # rates = {"gmx": 0.058238, "gtrade": 0.003456}  (daily % floats)
    # vault_state = {"idle_usdc": 90.0, "position_count": 0, "can_open": True}
    # open_positions = [{"id": 0, "collateral_usd": 10.0, "size_usd": 50.0}]
    #
    # Return: ("open" | "close_all" | "hold" | "skip", reason_string)
    ...
```

Edit `config.py` to change:
- `RATE_THRESHOLD` — when to open (default: 0.05%/day)
- `COLLATERAL_USD` — per-position size (default: $10)
- `LEVERAGE` — position leverage (default: 5x)
- `VAULT_ADDRESS` — point at your own vault (see deploy.sh)

---

## Deploy Your Own Vault

```bash
bash deploy.sh
```

This deploys a fresh UMIPVault using Circle USDC (so anyone can deposit via the public faucet)
and wires up the GMX adapter. Takes ~2 minutes.

---

## How UMIP Works

```
Your Agent
    │
    ▼
UMIPVault (single collateral pool)
    │
    ├──── GMX Adapter ────► GMX V2 (Sepolia)
    ├──── Vertex Adapter ──► Vertex Protocol
    └──── gTrade Adapter ──► GainsTrade
```

Without UMIP (V1): separate wallets for each platform → capital locked → fragmentation
With UMIP (V2): one vault → routes to best platform → zero fragmentation

**Live proof:** [comparison dashboard](https://umip-dashboard.vercel.app)
shows 4 fragmentation events eliminated and 0.2192% opportunity cost saved over 2 days.

---

## Contract Addresses (Arbitrum Sepolia)

| Contract | Address |
|----------|---------|
| UMIPVault (public demo) | `0xE516aDB78835B684cE95F5030296602fD96F3f86` |
| GMXAdapterSepolia | `0x148B975C477bdf6196670Fa09F9AA12C86F1Fe00` |
| Circle USDC | `0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d` |

---

## File Structure

```
umip-agent-template/
├── agent.py          # Main agent — strategy + execution (~200 lines, self-contained)
├── config.py         # All configuration (thresholds, addresses, leverage)
├── requirements.txt  # Python dependencies
├── deploy.sh         # One-command vault deployment
├── .env.example      # Environment variable template
└── README.md
```

---

## Common Patterns

### Pattern 1: Funding Rate Arb (this template)
Open longs when funding rate is high, collect from shorts, close when rate normalizes.

### Pattern 2: Cross-Venue Hedging
```python
# Long on GMX, short on gTrade simultaneously (delta-neutral)
# UMIP vault routes both positions from single collateral pool
```

### Pattern 3: Dynamic Rebalancing
```python
# Monitor PnL across platforms, rebalance collateral allocation
# Without UMIP: requires manual wallet management
# With UMIP: vault handles routing, agent just calls openPosition/closePosition
```

---

## Resources

- [Live sandbox](https://umip-sandbox.vercel.app) — test the vault in your browser
- [Comparison dashboard](https://umip-dashboard.vercel.app) — live V1 vs V2 metrics
- [Circle USDC faucet](https://faucet.circle.com/) — get testnet USDC
- [Arbitrum Sepolia ETH faucet](https://www.alchemy.com/faucets/arbitrum-sepolia) — get gas
