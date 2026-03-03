# UMIP Week 4 Decision Document

**Date:** 2026-02-14
**Status:** Week 4 Complete — Architecture Validated, Ready for Direction

---

## Executive Summary

Over 4 weeks we built a working **hub-and-spoke vault system** (UMIP) that manages collateral across GMX and Vertex perpetual platforms through a unified adapter interface. The system is tested with **54 passing tests** covering vault operations, adapter mocks, and margin health tracking.

**The core question now:** What's the next phase — testnet deployment, real adapter integration, or feature expansion?

---

## What Was Built

### 1. UMIPVault (384 lines, 23 tests)
The central hub managing collateral flow and position lifecycle.

| Capability | Status |
|---|---|
| USDC deposit/withdraw | Working |
| Hub-and-spoke collateral routing (idle → adapter → platform) | Working |
| Position open/close with real IAdapter calls | Working |
| Collateral invariant enforcement (`idle + GMX + Vertex = total`) | Working |
| Per-platform allocation tracking | Working |
| Event emissions for all state changes | Working |

**Architecture Decision:** Vault transfers collateral TO adapter before calling `openMarketLong`. This matches the real GMX flow where collateral goes to OrderVault before order creation. The adapter then forwards to the platform.

### 2. IAdapter Interface
Unified interface both platforms implement:

```solidity
openMarketLong(market, collateralAmount, collateralToken, sizeDeltaUsd, acceptablePrice, executionFee)
closeMarketLong(market, collateralToken, sizeDeltaUsd, acceptablePrice, executionFee)
```

**Architecture Decision:** No `positionKey` parameter for closing — position identified by `market + collateralToken + isLong` (matches GMX V2 pattern). This simplifies the interface but limits to one position per market/collateral/direction per adapter.

### 3. GMXAdapter (4 tests)
Mock adapter validated against real GMX V2 architecture analysis.

| Aspect | Detail |
|---|---|
| Interface | Implements IAdapter exactly |
| Position key computation | `keccak256(account, market, collateral, isLong)` |
| Collateral flow | Receives from vault, tracks internally |
| Limitation | Mock execution (no real GMX keeper integration) |

**Known Blocker:** Fork tests against real GMX contracts fail due to ROUTER_PLUGIN permission issues and proxy-level reverts. The adapter is architecturally sound but unvalidated against live contracts. See [umip_week1_gmx_findings.md](umip_week1_gmx_findings.md) for full analysis.

### 4. VertexAdapter (7 tests)
Mock adapter implementing IAdapter with Vertex-specific concepts.

| Aspect | Detail |
|---|---|
| Interface | Implements IAdapter (same as GMX) |
| Vertex concepts | productId mapping, subaccount management |
| Short support | Negative `sizeDelta` for short positions |
| Limitation | Mock only — real Vertex requires off-chain sequencer API |

**Architecture Decision:** Vertex's hybrid on-chain/off-chain model means a pure smart contract adapter can only use "slow mode" (AMM execution, 1 USDC fee). Orderbook access requires an off-chain backend component.

### 5. MarginManager (271 lines, 18 tests)
Read-only health factor monitoring across all positions.

| Feature | Detail |
|---|---|
| `getHealthFactor(user)` | Aggregate health across all open positions |
| `getPositionMargin(user, id)` | Per-position: collateral, required margin, leverage, health |
| `getUserSummary(user)` | Full dashboard: idle, allocated, positions, health, available to withdraw |
| `checkHealth(user)` | Emits events with threshold alerts |
| `setPlatformMargin(platform, bps)` | Configurable per-platform margin (default 5%) |

**Threshold Alerts:**
- WARNING: health < 150%
- CRITICAL: health < 120%
- LIQUIDATABLE: health < 100%

**Limitation:** Health factor uses on-chain collateral amounts only. Does not reflect unrealized PnL (would require oracle integration).

---

## Test Coverage Summary

| Suite | Tests | Status |
|---|---|---|
| UMIPVault | 23 | All passing |
| MarginManager | 18 | All passing |
| VertexAdapterMock | 7 | All passing |
| GMXAdapterMock | 4 | All passing |
| Counter (template) | 2 | All passing |
| **Total (non-fork)** | **54** | **All passing** |
| Fork tests (GMX real) | 3 | Failing (expected — need RPC + permission fixes) |

---

## Architecture Decisions Made

### Decision 1: Hub-and-Spoke Over Direct Integration
**Chose:** Vault as central collateral hub, adapters as spokes
**Why:** Clean separation of concerns. Vault handles accounting, adapters handle platform-specific logic. Adding a new platform = writing one new adapter.
**Trade-off:** Extra gas for the routing hop. Collateral sits in vault contract (not earning yield while idle).

### Decision 2: Adapter Transfers Collateral (Not User)
**Chose:** Vault transfers collateral to adapter, adapter forwards to platform
**Why:** Matches real GMX V2 flow. User never needs to approve multiple contracts.
**Trade-off:** Adapter holds collateral briefly during the call. Must trust adapter code.

### Decision 3: Mock-First Development
**Chose:** Build and test with mock adapters, defer live integration
**Why:** Unblocked development while GMX fork testing has permission blockers. Validated architecture and accounting logic independently of platform quirks.
**Trade-off:** Real integration may surface issues the mocks don't capture (async keeper execution, PnL settlement, fee handling).

### Decision 4: Basis Points for Health Factor
**Chose:** All ratios in basis points (10000 = 100%)
**Why:** Avoids floating point entirely. Standard in DeFi. Sufficient precision for health monitoring.
**Trade-off:** None significant. Well-understood pattern.

### Decision 5: No Access Control Yet
**Chose:** All admin functions (setAdapters, setPlatformMargin) are unprotected
**Why:** Development phase. Adding OpenZeppelin Ownable/AccessControl is straightforward when needed.
**Risk:** Must add before any deployment, even testnet.

---

## Known Gaps & Risks

### Gap 1: No PnL Tracking
Health factor only considers deposited collateral, not unrealized profit/loss. A position could be deeply in profit (healthy) or deeply in loss (at risk) and the health factor wouldn't reflect it.

**To fix:** Integrate oracle price feeds to calculate mark-to-market PnL per position.

### Gap 2: No Async Order Handling
GMX V2 uses a two-step model: create order → keeper executes. Currently the vault assumes synchronous execution (open = immediate). In reality there's a pending state between order creation and execution.

**To fix:** Add order status tracking. Position should be "pending" until keeper confirms execution. Handle failed orders (collateral return).

### Gap 3: No Real Adapter Validation
Both adapters are mocks. The GMX fork test blocker (ROUTER_PLUGIN permission) is unresolved.

**To fix (options):**
1. Study existing GMX V2 integrations (SteadeFi, etc.) for working patterns
2. Deploy to Arbitrum Sepolia testnet for real validation
3. Deep dive into GMX permission system to fix fork tests

### Gap 4: Single Position Per Market Limitation
The close interface (`closeMarketLong(market, collateralToken, ...)`) identifies positions by market+collateral+direction. Can't have two concurrent long positions on the same market with the same collateral token through the same adapter.

**To fix:** Either accept this limitation (reasonable for v1) or add position key tracking.

### Gap 5: No Liquidation Automation
MarginManager detects unhealthy positions but doesn't act on them. It's read-only monitoring.

**To fix:** Add keeper/bot integration that calls `checkHealth()` periodically and triggers position closes when LIQUIDATABLE.

---

## Decision Points for Next Phase

### Decision A: What to build next?

| Option | Description | Effort | Value |
|---|---|---|---|
| **A1: Real GMX integration** | Fix fork tests or testnet deploy, validate adapter against live GMX | 1-2 weeks | High — proves the architecture works |
| **A2: Oracle + PnL integration** | Add Chainlink/GMX oracle feeds for real health factor | 1 week | High — makes MarginManager accurate |
| **A3: Async order handling** | Pending states, order callbacks, failed order recovery | 1-2 weeks | High — required for production |
| **A4: Access control + security** | Ownable, reentrancy guards, pause functionality | 2-3 days | Medium — required before deployment |
| **A5: Frontend/SDK** | TypeScript SDK or simple UI to interact with vault | 1-2 weeks | Medium — makes it usable |

### Decision B: Vertex strategy?

| Option | Description |
|---|---|
| **B1: Smart contract slow mode** | Accept Vertex limitations (AMM only, 1 USDC fee, no orderbook) |
| **B2: Hybrid backend** | Add off-chain service for Vertex orderbook execution |
| **B3: Skip Vertex for now** | Focus on GMX, add Vertex later when architecture is proven |

### Decision C: Testing strategy?

| Option | Description |
|---|---|
| **C1: Fix fork tests** | Solve the ROUTER_PLUGIN blocker, test against forked Arbitrum |
| **C2: Testnet deployment** | Deploy to Arbitrum Sepolia, test with real GMX testnet contracts |
| **C3: Study existing integrations** | Analyze SteadeFi or similar for proven patterns, then adapt |

---

## Recommendation

**Suggested next phase (Week 5-6):**

1. **A4 first (2-3 days):** Add access control and security basics. Quick win, required regardless of direction.
2. **A1 via C3 (1 week):** Study existing GMX V2 integrations to solve the fork test blocker, then validate the real adapter.
3. **A2 (1 week):** Oracle integration for accurate health factor. MarginManager becomes genuinely useful.
4. **B3 for now:** Park Vertex until GMX integration is proven end-to-end.

This path validates the architecture against real infrastructure before expanding scope.

---

## Appendix: File Inventory

```
contracts/src/
├── UMIPVault.sol              # Hub vault (384 lines)
├── MarginManager.sol          # Health monitoring (271 lines)
├── interfaces/
│   └── IAdapter.sol           # Unified adapter interface
└── adapters/
    ├── GMXAdapterMock.sol     # GMX mock (implements IAdapter)
    ├── GMXAdapterSimple.sol   # Real GMX V2 integration (partial)
    ├── GMXAdapterSepolia.sol  # Sepolia variant
    └── VertexAdapterMock.sol  # Vertex mock (implements IAdapter)

contracts/test/
├── UMIPVault.t.sol            # 23 tests
├── MarginManager.t.sol        # 18 tests
├── GMXAdapterMock.t.sol       # 4 tests
├── VertexAdapterMock.t.sol    # 7 tests
└── fork/
    ├── GMXAdapter.t.sol       # Fork test (blocked)
    ├── GMXAdapterSimple.t.sol # Fork test (blocked)
    └── GMXIntegration.t.sol   # Fork test (blocked)

workflows/
├── gmx_v2_integration.md
├── vertex_protocol_research.md
├── unified_interface_strategy.md
├── umip_week1_gmx_findings.md
└── umip_week4_decision.md     # This document
```

---

**Status:** Decision document complete. Awaiting direction on which path to take for Week 5+.
