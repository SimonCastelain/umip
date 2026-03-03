# UMIP Demo: Capital Fragmentation — Proof of Concept

## Try It Live

| Resource | Link |
|----------|------|
| Interactive Sandbox (Arbitrum Sepolia) | https://umip-sandbox.vercel.app |
| Live V1 vs V2 Dashboard | https://umip-dashboard.vercel.app |
| Agent Template (fork & customize) | `umip-agent-template/` in this repo |
| Integration Guide | `docs/integration_guide.md` |

---

**Two agents. Same strategy. Radically different results.**

Agent V1 and Agent V2 run the identical funding rate arbitrage strategy on Arbitrum Sepolia.
The only difference is how they manage collateral. This document captures the live proof.

---

## The Problem: Capital Fragmentation

Onchain perpetual DEXes require collateral to be pre-deposited per platform.
When an agent holds capital on GMX, it cannot access that capital to trade on gTrade — and vice versa.

This is **capital fragmentation**: the agent knows which platform has the better rate,
but cannot act on it because its capital is locked on the wrong venue.

### Live Evidence — Agent V1 (No UMIP)

Agent V1 runs hourly. Every cycle it checks rates on GMX and gTrade, then tries to trade on the cheaper platform.
The logs tell the story:

```
[2026-02-21T18:55:11] FRAGMENTATION: Wanted gTrade, stuck on GMX. Lost 0.0548%/day. GMX=900.00 gTrade=0.00 USDC
[2026-02-21T18:58:00] FRAGMENTATION: Wanted gTrade, stuck on GMX. Lost 0.0548%/day. GMX=900.00 gTrade=0.00 USDC
[2026-02-21T18:58:27] FRAGMENTATION: Wanted gTrade, stuck on GMX. Lost 0.0548%/day. GMX=900.00 gTrade=0.00 USDC
[2026-02-21T18:59:48] FRAGMENTATION: Wanted gTrade, stuck on GMX. Lost 0.0548%/day. GMX=890.00 gTrade=0.00 USDC
```

**Rate context (2026-02-22):** GMX ETH/USD = 0.148%/day | gTrade ETH/USD = 0.003%/day
→ GMX is **43x more expensive**. V1 cannot capture the better rate.

---

## The Solution: UMIPVault

UMIPVault is an onchain hub-and-spoke vault that manages collateral across platforms from a single deposit.
Instead of locking capital per platform, the vault routes collateral to the adapter with the best rate — automatically.

### Live Evidence — Agent V2 (With UMIP)

Same hourly schedule. Same thresholds. Same position sizes. Different result:

```
[2026-02-22T14:15:55] RATE   GMX=0.148532%/day gTrade=0.003456%/day
[2026-02-22T14:15:55] VAULT  idle=$1000.0 gmx=$0.0 total=$1000.0 frag=False
[2026-02-22T14:16:10] ✓ OPEN  10.0 USDC → $50.0 GMX via UMIPVault
```

**Zero fragmentation events. Every signal → execution.**

---

## Code Comparison

### V1 — 15 lines to handle what should be impossible

```python
# agents/v1_no_umip/agent.py — fragmentation detection in decide()
if optimal == "gTrade" and balances["can_open_gmx"]:
    return {
        "action":           "open_forced",
        "platform":         "GMX",
        "reason":           "FRAGMENTATION — wanted gTrade but no GNS_USDC. Fallback to GMX.",
        "optimal":          "gTrade",
        "opportunity_cost": opp_cost,   # %/day wasted on wrong platform
    }

if has_gmx and optimal == "gTrade" and not has_gtrade:
    return {
        "action":           "hold_suboptimal",
        "platform":         "GMX",
        "reason":           f"Stuck on GMX, gTrade is {ratio:.0f}x cheaper",
        "opportunity_cost": opp_cost,
    }
```

### V2 — 3 lines via UMIPVault

```python
# agents/v2_with_umip/agent.py — execute() with vault
result = open_gmx_position(private_key, COLLATERAL_USD, LEVERAGE)
log_vault_open(result, rates)   # logs VAULT_OPEN — never FRAGMENTATION
log_action("open_long", platform, {...})
```

No fragmentation logic. No platform-specific wallet management. One deposit, any platform.

---

## Architecture

```
V1 (No UMIP)                          V2 (With UMIP)
────────────────────────────          ─────────────────────────────────────
Wallet A (SG_USDC) ──► GMX           Deployer ──► UMIPVault (1000 SG_USDC)
Wallet B (GNS_USDC) ─► gTrade                          │
                                                ┌───────┴──────────┐
Agent wants gTrade?                         GMX Adapter      gTrade Adapter
→ FRAGMENTATION (Wallet B = $0)           (vault routes,    (mainnet only)
                                           no fragmentation)
```

**Deployed contracts (Arbitrum Sepolia, chain ID 421614):**

| Contract | Address |
|---|---|
| UMIPVault V3 | `0xE516aDB78835B684cE95F5030296602fD96F3f86` |
| GMXAdapterSepolia | `0x148B975C477bdf6196670Fa09F9AA12C86F1Fe00` |
| Collateral (Circle USDC) | `0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d` |

---

## Testnet Scope & Limitations

**What this demo proves:**
On Arbitrum Sepolia, both agents run the same strategy using GMX. Agent V1 demonstrates collateral fragmentation: when its GMX-specific wallet is depleted, it cannot act on opportunities even though the vault (V2) has idle collateral ready. This proves the architectural problem and its solution.

**What this demo does not prove:**
On testnet, GMX uses SG_USDC and gTrade uses GNS_USDC — they cannot share collateral regardless of architecture. True cross-venue routing (GMX ↔ gTrade ↔ Vertex from a single USDC deposit) requires mainnet where all venues accept standard USDC. The testnet run validates the vault architecture and fragmentation mechanics, not the full capital efficiency gain across competing venues.

**Mainnet validation is the next step.** Both GMX and gTrade use standard USDC on mainnet, enabling real multi-venue routing. We're seeking funding to conduct mainnet validation with a professional security audit before managing significant capital.

---

## Quantitative Results (2026-02-21, 1 day of data)

Run the comparison script to see the latest metrics:

```bash
python3 comparison/compare_agents.py --save
```

| Metric | Agent V1 (No UMIP) | Agent V2 (UMIP) |
|---|---|---|
| Observation period | 2026-02-21 | 2026-02-22 |
| Fragmentation events | **4** | **0** |
| Missed opportunities | **4** | **0** |
| Cumulative opportunity cost | **0.2192%** | **0%** |
| Executions | 2 (suboptimal venue) | 1 (via vault) |

These are the actual results from one day of live runs on Arbitrum Sepolia. The agents continue to accumulate data — see the [live dashboard](https://umip-dashboard.vercel.app) for current numbers.

---

## Integration Guide

Add UMIP to any agent in 5 steps (Solidity):

```solidity
// 1. Deploy once
UMIPVault vault = new UMIPVault(USDC_ADDRESS);

// 2. Configure platform adapters
vault.setAdapters(gmxAdapter, address(0), gTradeAdapter);
vault.setMarket(Platform.GMX, ETH_USD_MARKET);

// 3. Deposit capital (from any source — no per-platform split)
USDC.approve(address(vault), 1000e6);
vault.deposit(1000e6);

// 4. Open on optimal platform — vault routes internally
uint256 posId = vault.openPosition{value: execFee}(
    Platform.GMX, 10e6, 50e30, type(uint256).max
);

// 5. Close when signal expires
vault.closePosition{value: execFee}(posId);
```

Python integration (using [vault.py](../agents/v2_with_umip/vault.py)):

```python
from vault import get_vault_state, open_gmx_position

state = get_vault_state(account)
if state["can_open_gmx"] and rate_above_threshold:
    result = open_gmx_position(private_key, collateral=10.0, leverage=5.0)
    # Done. No fragmentation handling needed.
```

---

## Log Files

> These files are generated locally when you run the agents — they are gitignored and not included in the repository. To see the results without running the agents, visit the [live dashboard](https://umip-dashboard.vercel.app).

| File | Contents |
|---|---|
| `.tmp/agent_v1_log.jsonl` | V1 live JSONL log (FRAGMENTATION events accumulating) |
| `.tmp/agent_v2_log.jsonl` | V2 live JSONL log (VAULT_OPEN events, zero fragmentation) |
| `.tmp/agent_v1_summary.txt` | V1 human-readable fragmentation summary |
| `.tmp/agent_v2_summary.txt` | V2 human-readable execution summary |
| `comparison/results.json` | Latest comparison output |

---

## Running the Agents

```bash
# One-shot cycle
python3 agents/v1_no_umip/agent.py
python3 agents/v2_with_umip/agent.py

# Comparison
python3 comparison/compare_agents.py

# Both agents run hourly via cron automatically
crontab -l
```
