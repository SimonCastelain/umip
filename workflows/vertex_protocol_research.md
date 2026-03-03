# Vertex Protocol Research

**Status:** Day 4-5 Complete - Architecture Understood, Fundamental Difference Identified
**Last Updated:** 2026-01-24

## Objective

Understand how to programmatically interact with Vertex Protocol on Arbitrum to create leveraged positions, and compare with GMX V2 for building a unified interface.

## Vertex Protocol Architecture

### 🏗️ Hybrid Model: Off-Chain + On-Chain

Vertex uses a **fundamentally different architecture** from GMX:

```
┌─────────────────────────────────────────────────────────┐
│                    Vertex Protocol                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  PRIMARY PATH (Fast Mode):                              │
│  User → Sequencer (Off-chain) → On-chain Settlement     │
│  ├─ Centralized orderbook matching                      │
│  ├─ 5-15ms latency (CEX-grade)                         │
│  └─ SDK/API required                                    │
│                                                          │
│  FALLBACK PATH (Slow Mode):                            │
│  User → Endpoint Contract → AMM → Settlement            │
│  ├─ submitSlowModeTransaction()                         │
│  ├─ Direct smart contract calls                        │
│  └─ Used for withdrawals & maintenance mode             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Key Contracts (Arbitrum Mainnet)

```solidity
// Core Contracts
address VERTEX_ENDPOINT = 0xbbEE07B3e8121227AfCFe1E2B82772246226128e;
address VERTEX_CLEARINGHOUSE = 0xAE1ec28d6225dCE2ff787dcb8CE11cF6D3AE064f;
address VERTEX_PERP_ENGINE = 0xb74C78cca0FADAFBeE52B2f48A67eE8c834b5fd1;
address VERTEX_SPOT_ENGINE = 0x32d91Af2B17054D575A7bF1ACfa7615f41CCEfaB;
address VERTEX_QUERIER = 0x1693273B443699bee277eCbc60e2C8027E91995d;

// Sequencer (Off-chain)
address VERTEX_OFFCHAIN_EXCHANGE = 0xA4369d8E3dC847aEDf17F4125f1ABB1BC18FC060;

// VRTX Token
address VRTX_TOKEN = 0x95146881b86B3ee99e63705eC87AfE29Fcc044D9;
```

### Architecture Components

#### 1. Sequencer (Off-Chain Orderbook)
- **Purpose**: High-speed order matching
- **Implementation**: Custom parallelized EVM in Rust
- **Performance**: 5-15ms execution (comparable to CEXes)
- **Access**: Via SDK/API only
- **Trade-off**: Centralized component for speed

#### 2. Endpoint Contract
- **Purpose**: Entry point for on-chain interactions
- **Key Function**: `submitSlowModeTransaction(bytes transaction)`
- **Use Cases**:
  - Withdrawals
  - Collateral deposits
  - Fallback trading when sequencer is down
- **Cost**: 1 USDC slow-mode fee

#### 3. Clearinghouse
- **Purpose**: Risk management and settlement hub
- **Functions**:
  - Combines perpetual and spot markets
  - Cross-margin calculations
  - Liquidation engine

#### 4. AMM (On-Chain Backup)
- **Purpose**: "Slo-Mo Mode" liquidity backstop
- **Activation**: When sequencer unavailable
- **Mechanism**: Users trade against on-chain AMM
- **Design**: Hybrid orderbook-AMM model

## How Vertex Works

### Normal Trading Flow (Fast Mode)

1. **User submits order to Sequencer** (off-chain API call)
   ```python
   # Via Python SDK
   client.market.place_order(
       product_id=1,  # e.g., ETH-PERP
       order_type="limit",
       side="buy",
       price="3000.00",
       size="1.5"
   )
   ```

2. **Sequencer matches order** (5-15ms)
   - High-speed matching against orderbook
   - Price discovery happens off-chain

3. **Settlement posted on-chain**
   - Batch settlements to Clearinghouse
   - Final state stored in smart contracts

### Slow Mode Trading Flow (Backup)

1. **User calls Endpoint contract**
   ```solidity
   endpoint.submitSlowModeTransaction(encodedTx);
   ```

2. **Transaction executes against AMM**
   - No orderbook matching
   - Trade against on-chain liquidity
   - Higher gas costs

3. **Settlement via Clearinghouse**
   - Same final settlement as fast mode

## Smart Contract Integration

### ⚠️ Critical Limitation

**For programmatic trading from smart contracts:**
- Normal trading requires **off-chain API/SDK** (can't be done from Solidity)
- Slow mode is possible but:
  - Higher costs (gas + 1 USDC fee)
  - No orderbook access
  - Trade against AMM only
  - Limited to basic operations

### Available SDK Functions

From the Python/TypeScript SDKs:

**Order Management:**
- `place_order()` - Limit orders
- `place_market_order()` - Market orders
- `cancel_orders()` - Cancel orders
- `place_trigger_order()` - Conditional orders

**Collateral:**
- `deposit_collateral()` - Add collateral
- `withdraw_collateral()` - Remove collateral

**Liquidity:**
- `mint_lp()` - Provide liquidity
- `burn_lp()` - Remove liquidity

## Comparison: GMX vs Vertex

| Aspect | GMX V2 | Vertex Protocol |
|--------|--------|-----------------|
| **Architecture** | Fully on-chain | Hybrid (off-chain + on-chain) |
| **Order Matching** | Keeper-based execution with oracles | Off-chain sequencer (orderbook) |
| **Smart Contract Access** | Direct (with permissions) | Slow mode only (limited) |
| **Latency** | ~1-2 blocks for keeper execution | 5-15ms (sequencer) |
| **Orderbook** | No traditional orderbook | Yes (off-chain) |
| **Decentralization** | Fully decentralized | Hybrid (centralized sequencer) |
| **SDK Required** | No (direct contract calls) | Yes (for normal trading) |
| **Gas Costs** | Execution fee (~0.0001 ETH) | Lower (batch settlements) |
| **Integration Approach** | Smart contract multicalls | API/SDK primarily |

## Implications for Unified Interface

### The Challenge

Building a unified interface that abstracts both GMX and Vertex faces a fundamental issue:

**GMX**: Pure smart contract interactions
**Vertex**: Requires off-chain API calls for best execution

### Possible Approaches

#### Option A: Smart Contract Only (Limited)
```solidity
interface IUnifiedPerp {
    function openPosition(...) external;  // Works for GMX, limited for Vertex
}
```
- ✅ Works with GMX (when permissions fixed)
- ❌ Vertex slow mode only (expensive, no orderbook)
- ❌ Poor UX for Vertex users

#### Option B: Hybrid Interface (Complex)
```solidity
// On-chain component
contract UnifiedPerp {
    function openPositionGMX(...) external;      // Direct call
    function requestPositionVertex(...) external; // Emit event for backend
}

// Off-chain component
Backend → Listens for Vertex events
       → Calls Vertex API
       → Posts result on-chain
```
- ✅ Best execution for both protocols
- ✅ Maintains on-chain settlement guarantees
- ❌ Complex architecture
- ❌ Requires backend infrastructure

#### Option C: View/Query Layer Only
```solidity
// Read-only unified interface
interface IUnifiedPerpQuery {
    function getPosition(protocol, account) external view returns (Position);
    function getMarketInfo(protocol, market) external view returns (Market);
}
```
- ✅ Achievable purely on-chain
- ✅ Useful for portfolio management
- ❌ Doesn't solve execution unification

#### Option D: SDK-Based Abstraction (Non-Solidity)
```typescript
// TypeScript/Python unified SDK
class UnifiedPerp {
    async openPosition(protocol, params) {
        if (protocol === "GMX") {
            return gmxContract.createOrder(...);
        } else if (protocol === "VERTEX") {
            return vertexClient.place_order(...);
        }
    }
}
```
- ✅ Natural fit for both protocols
- ✅ Optimal execution paths
- ❌ Not a smart contract solution
- ❌ Not composable with other DeFi

## Recommendations

### Recommended Approach: Revisit Project Goals

Before proceeding, we need to clarify:

1. **What is the primary use case?**
   - Portfolio management dashboard? → Option C (query layer)
   - Trading bot/automation? → Option D (SDK)
   - DeFi composability? → Option B (hybrid)
   - Pure on-chain execution? → May not work for Vertex

2. **Who are the end users?**
   - Smart contracts? → GMX-focused, Vertex slow mode
   - EOA wallets? → Both protocols viable
   - Backend services? → SDK approach works

3. **What level of complexity is acceptable?**
   - Simple: Focus on one protocol
   - Medium: Query layer for both, execution for GMX
   - Complex: Full hybrid architecture

### Next Steps (Pending Clarification)

**If focusing on smart contract composability:**
- Build GMX integration first (solve permission issues)
- Document Vertex as "API-based, not composable"
- Create query-only interface for Vertex

**If building a trading application:**
- Use Option D (SDK-based abstraction)
- Create TypeScript/Python unified library
- Smart contracts only for settlement

**If building DeFi primitives:**
- Use Option B (hybrid architecture)
- Design event-driven backend
- Maintain on-chain finality

## Resources

- [Vertex Technical Architecture](https://docs.vertexprotocol.com/basics/technical-architecture)
- [Vertex Python SDK](https://vertex-protocol.github.io/vertex-python-sdk/)
- [Vertex Contracts GitHub](https://github.com/vertex-protocol/vertex-contracts)
- [Vertex on Arbiscan](https://arbiscan.io/address/0xbbEE07B3e8121227AfCFe1E2B82772246226128e)
- [Messari: Understanding Vertex](https://messari.io/report/understanding-vertex-a-comprehensive-overview)

## Key Takeaways

1. **Vertex is NOT a pure smart contract protocol** - primary path requires off-chain sequencer
2. **GMX and Vertex have fundamentally incompatible architectures** for unified on-chain interface
3. **Slow mode exists but defeats Vertex's purpose** - sacrifices speed, orderbook access, and cost efficiency
4. **The "right" abstraction depends on the use case** - no one-size-fits-all solution
5. **SDK-based unification is more natural** than smart contract unification for these protocols

---

**Status**: Research complete. Architecture fundamentally incompatible with pure on-chain unified interface. Awaiting project direction clarification.
