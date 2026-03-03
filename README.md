# UMIP — Unified Margin Infrastructure Protocol

One vault. Any perpetual DEX. No capital fragmentation.

**Live sandbox (Arbitrum Sepolia):** https://umip-sandbox.vercel.app
**V1 vs V2 dashboard:** https://umip-dashboard.vercel.app

---

## The Problem

Onchain perpetual DEXes require collateral locked per-platform. An agent holding capital on GMX cannot use it on gTrade — even when gTrade has a better rate. This is capital fragmentation: your agent knows the optimal venue but cannot act on it.

## The Solution

UMIPVault is an onchain hub-and-spoke vault. Deposit USDC once. The vault routes collateral to whichever adapter you call — GMX, gTrade, Vertex — without requiring a separate deposit per platform.

**Result:** 4 fragmentation events on V1 (no UMIP) vs 0 on V2 (with UMIP) in the same period. See the [live dashboard](https://umip-dashboard.vercel.app) for current data.

---

## Contract Addresses (Arbitrum Sepolia, chain 421614)

| Contract | Address |
|----------|---------|
| UMIPVault V3 | `0xE516aDB78835B684cE95F5030296602fD96F3f86` |
| GMXAdapterSepolia | `0x148B975C477bdf6196670Fa09F9AA12C86F1Fe00` |
| Collateral (Circle USDC) | `0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d` |

Get testnet USDC at https://faucet.circle.com/

---

## Quick Start

```bash
# 1. Clone and install
pip install -r umip-agent-template/requirements.txt

# 2. Set your key
cp umip-agent-template/.env.example umip-agent-template/.env
# Edit .env → add DEPLOYER_PRIVATE_KEY

# 3. Deposit USDC into the vault
# → https://umip-sandbox.vercel.app

# 4. Run the agent
python umip-agent-template/agent.py          # one cycle
python umip-agent-template/agent.py --loop   # hourly loop
```

---

## Repository Layout

```
agents/
  v1_no_umip/       — reference agent: fragments capital across platforms
  v2_with_umip/     — production agent: uses UMIPVault, zero fragmentation
umip-agent-template/ — fork this to build your own strategy
umip-sandbox/        — Next.js deposit/withdraw UI
umip-dashboard/      — Next.js V1 vs V2 comparison dashboard
docs/
  integration_guide.md — step-by-step integration (Solidity + Python + TS)
comparison/
  UMIP_DEMO.md        — proof of concept write-up with live log evidence
  compare_agents.py   — generates results.json from agent logs
```

**Separate repositories:**
- [umip-contracts](https://github.com/SimonCastelain/umip-contracts) — Solidity source (Foundry), GMX/Vertex/gTrade adapters, deployment scripts
- [umip-demo-data](https://github.com/SimonCastelain/umip-demo-data) — agent run logs powering the comparison dashboard

---

## Integration

Five lines to add UMIP to any agent. See [docs/integration_guide.md](docs/integration_guide.md) for the full guide (Solidity, Python, TypeScript).

```python
from vault import get_vault_state, open_gmx_position

state = get_vault_state(account)
if state["can_open_gmx"] and rate_above_threshold:
    result = open_gmx_position(private_key, collateral=10.0, leverage=5.0)
    # Done. No per-platform wallet management. No fragmentation handling.
```

---

## Status

Proof of concept live on Arbitrum Sepolia. Mainnet deployment requires a professional security audit. Seeking funding to conduct the audit and validate multi-venue routing (GMX ↔ gTrade ↔ Vertex) with real capital.
