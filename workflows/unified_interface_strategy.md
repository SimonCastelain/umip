# Unified Perpetuals Interface - Strategy & Recommendations

**Status:** Day 2-5 Complete - Research Phase Finished
**Last Updated:** 2026-01-24
**Decision Required:** Choose implementation approach

## Executive Summary

After deep research into both GMX V2 and Vertex Protocol, we've discovered they use **fundamentally incompatible architectures** that make a pure smart contract unified interface challenging:

- **GMX V2**: Fully on-chain, smart contract composable, keeper-based execution
- **Vertex**: Hybrid off-chain/on-chain, requires API/SDK for optimal trading

## What We've Accomplished

### ✅ GMX V2 Research (Day 2-3)
- Complete interface mapping
- All contract addresses verified
- Multicall pattern understood
- Fork tests created
- **Blocker**: ROUTER_PLUGIN permission issue (solvable)

### ✅ Vertex Protocol Research (Day 4-5)
- Architecture fully understood
- Contract addresses documented
- SDK capabilities mapped
- **Finding**: Primary trading requires off-chain sequencer

## The Core Problem

```
┌────────────────────────────────────────────────────────────┐
│             Unified Interface Goal                          │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  IDEAL: Single Solidity interface for multiple protocols   │
│                                                             │
│  interface IUnifiedPerp {                                  │
│      function openLongPosition(...) external;              │
│      function closeLongPosition(...) external;             │
│      function getPosition(...) external view;              │
│  }                                                          │
│                                                             │
└────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────┴─────────┐
                    │                   │
            ┌───────▼──────┐    ┌──────▼────────┐
            │   GMX V2     │    │    Vertex     │
            ├──────────────┤    ├───────────────┤
            │ ✅ Works     │    │ ❌ Requires   │
            │ (on-chain)   │    │ off-chain API │
            └──────────────┘    └───────────────┘
```

**The Incompatibility:**
- GMX: Pure smart contract calls
- Vertex: Best execution requires off-chain orderbook API

## Four Implementation Strategies

### Strategy A: Smart Contract Only ⚠️

**Description**: Pure Solidity interface using slow mode for Vertex

```solidity
contract UnifiedPerp {
    function openPosition(
        Protocol protocol,
        Market market,
        bool isLong,
        uint256 size,
        uint256 collateral
    ) external {
        if (protocol == Protocol.GMX) {
            // Direct GMX createOrder call
            gmxRouter.multicall([sendTokens(), createOrder()]);
        } else if (protocol == Protocol.Vertex) {
            // Vertex slow mode (AMM only)
            vertexEndpoint.submitSlowModeTransaction(encodedTx);
        }
    }
}
```

**Pros:**
- ✅ Pure on-chain, composable with DeFi
- ✅ No backend infrastructure needed
- ✅ Trustless execution

**Cons:**
- ❌ Vertex slow mode: expensive (1 USDC fee + gas)
- ❌ No orderbook access for Vertex
- ❌ Poor execution quality on Vertex
- ❌ GMX permission issues to solve first

**Best For:** DeFi protocols that need composability and don't mind Vertex limitations

---

### Strategy B: Hybrid Architecture 🏗️

**Description**: Smart contracts + backend service

```
User
  ↓
Smart Contract (On-chain)
  ├→ GMX: Direct execution
  └→ Vertex: Emit event
         ↓
    Backend Service (Off-chain)
         ├→ Listen for events
         ├→ Call Vertex API
         └→ Post result on-chain
```

**Implementation:**
```solidity
contract UnifiedPerp {
    event VertexOrderRequested(
        address indexed user,
        uint256 indexed orderId,
        Market market,
        bool isLong,
        uint256 size
    );

    function openPosition(...) external {
        if (protocol == Protocol.GMX) {
            // Immediate execution
            gmxRouter.createOrder(...);
        } else if (protocol == Protocol.Vertex) {
            // Request via event
            emit VertexOrderRequested(...);
            // Backend fulfills later
        }
    }
}
```

**Pros:**
- ✅ Optimal execution for both protocols
- ✅ Orderbook access for Vertex
- ✅ Maintains on-chain settlement

**Cons:**
- ❌ Complex infrastructure
- ❌ Requires reliable backend
- ❌ Asynchronous Vertex execution
- ❌ Trust assumptions on backend

**Best For:** Products with existing backend infrastructure, can handle async

---

### Strategy C: Query/View Layer Only 📊

**Description**: Read-only unified interface, execution elsewhere

```solidity
interface IUnifiedPerpQuery {
    function getPosition(
        Protocol protocol,
        address account,
        Market market
    ) external view returns (Position memory);

    function getMarketInfo(
        Protocol protocol,
        Market market
    ) external view returns (MarketInfo memory);

    function getAccountMargin(
        Protocol protocol,
        address account
    ) external view returns (uint256);
}
```

**Pros:**
- ✅ Achievable purely on-chain
- ✅ No complex infrastructure
- ✅ Useful for dashboards/analytics
- ✅ Can query both protocols

**Cons:**
- ❌ Doesn't solve execution unification
- ❌ Users still need separate execution paths
- ❌ Limited value-add

**Best For:** Portfolio managers, analytics tools, risk monitoring

---

### Strategy D: SDK/Library Abstraction 📚

**Description**: TypeScript/Python library, not Solidity

```typescript
// Unified JavaScript/TypeScript SDK
class UnifiedPerpetuals {
    constructor(config: {
        gmxProvider: Provider,
        vertexClient: VertexClient,
        wallet: Wallet
    }) { ... }

    async openPosition(params: {
        protocol: Protocol,
        market: Market,
        isLong: boolean,
        size: BigNumber,
        collateral: BigNumber
    }): Promise<TransactionReceipt> {
        if (params.protocol === Protocol.GMX) {
            return this.gmxProvider.createOrder(...);
        } else if (params.protocol === Protocol.VERTEX) {
            return this.vertexClient.place_order(...);
        }
    }
}
```

**Pros:**
- ✅ Natural fit for both protocols
- ✅ Optimal execution paths
- ✅ No artificial limitations
- ✅ Can add more protocols easily

**Cons:**
- ❌ Not a smart contract solution
- ❌ Not composable with DeFi
- ❌ Requires frontend integration

**Best For:** Trading applications, bots, user-facing interfaces

---

## Decision Matrix

| Criteria | Strategy A | Strategy B | Strategy C | Strategy D |
|----------|------------|------------|------------|------------|
| **On-chain composable** | ✅ | ⚠️ (hybrid) | ✅ (read-only) | ❌ |
| **Optimal GMX execution** | ✅ | ✅ | N/A | ✅ |
| **Optimal Vertex execution** | ❌ | ✅ | N/A | ✅ |
| **Infrastructure complexity** | Low | High | Low | Medium |
| **Development time** | Medium | Long | Short | Short |
| **Trustless** | ✅ | ⚠️ (backend) | ✅ | ⚠️ (frontend) |
| **DeFi composability** | ✅ | ⚠️ | ✅ | ❌ |

## Recommendations by Use Case

### Use Case 1: Building a Trading Bot
→ **Strategy D** (SDK/Library)
- Optimal execution for both
- Easy to extend with more protocols
- Direct API access when needed

### Use Case 2: DeFi Protocol Integration
→ **Strategy A** (Smart Contract Only)
- Composable with other protocols
- Accept Vertex limitations (or skip it)
- Focus on GMX + others with on-chain execution

### Use Case 3: Portfolio Management Dashboard
→ **Strategy C** (Query Layer)
- Read positions across protocols
- Display unified portfolio view
- Users execute trades separately

### Use Case 4: Advanced Trading Platform
→ **Strategy B** (Hybrid Architecture)
- Best execution everywhere
- More complex but most capable
- Good for serious trading products

## Immediate Next Steps

### Before Proceeding, Answer These Questions:

1. **What is your primary objective?**
   - [ ] Build composable DeFi primitives
   - [ ] Create a trading application
   - [ ] Develop portfolio analytics
   - [ ] Build automated trading strategies

2. **Who are your end users?**
   - [ ] Other smart contracts
   - [ ] EOA wallet users
   - [ ] Trading bots/algorithms
   - [ ] DeFi protocols

3. **What's your complexity tolerance?**
   - [ ] Simple: Single protocol or limited functionality
   - [ ] Medium: Smart contracts + some limitations
   - [ ] Complex: Full hybrid architecture acceptable

4. **What's your timeline?**
   - [ ] Quick prototype: 1-2 weeks
   - [ ] MVP: 1-2 months
   - [ ] Production-ready: 3-6 months

### Based on Answers, Choose Path:

**Path 1**: Focus on GMX V2 only
- Fix permission issues
- Build complete GMX interface
- Add Vertex later if needed
- ⏱️ **Timeline**: 1-2 weeks

**Path 2**: Build query layer for both
- Read-only unified interface
- Useful immediately
- Add execution later
- ⏱️ **Timeline**: 1 week

**Path 3**: SDK-based unification
- TypeScript/Python library
- Supports both protocols optimally
- Not Solidity
- ⏱️ **Timeline**: 2-3 weeks

**Path 4**: Full hybrid architecture
- Smart contracts + backend
- Most complex but most capable
- Production-grade solution
- ⏱️ **Timeline**: 4-8 weeks

## Recommended Path: **Path 1 (GMX Focus)**

**Reasoning:**
1. GMX is fully on-chain and composable
2. You've already done the research
3. Once working, easy to evaluate if Vertex is needed
4. Can add Vertex slow mode later if DeFi composability required
5. Or switch to SDK approach if that fits better

**Next Actions:**
1. Solve GMX ROUTER_PLUGIN permission issue
2. Complete GMX fork tests
3. Build GMX adapter interface
4. Test end-to-end execution
5. Document and evaluate

**Then decide:**
- Add Vertex? (Slow mode or hybrid)
- Stay GMX-only? (Simplest)
- Pivot to SDK? (If composability not needed)

---

## Appendix: Contract Addresses Reference

### GMX V2 (Arbitrum)
```solidity
address GMX_EXCHANGE_ROUTER = 0x602b805EedddBbD9ddff44A7dcBD46cb07849685;
address GMX_ROUTER = 0x7452c558d45f8afC8c83dAe62C3f8A5BE19c71f6;
address GMX_READER = 0xf60becbba223EEA9495Da3f606753867eC10d139;
address GMX_DATA_STORE = 0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8;
address GMX_ORDER_VAULT = 0x31eF83a530Fde1B38EE9A18093A333D8Bbbc40D5;
```

### Vertex Protocol (Arbitrum)
```solidity
address VERTEX_ENDPOINT = 0xbbEE07B3e8121227AfCFe1E2B82772246226128e;
address VERTEX_CLEARINGHOUSE = 0xAE1ec28d6225dCE2ff787dcb8CE11cF6D3AE064f;
address VERTEX_PERP_ENGINE = 0xb74C78cca0FADAFBeE52B2f48A67eE8c834b5fd1;
address VERTEX_SPOT_ENGINE = 0x32d91Af2B17054D575A7bF1ACfa7615f41CCEfaB;
address VERTEX_QUERIER = 0x1693273B443699bee277eCbc60e2C8027E91995d;
```

---

**Status**: Research complete. Strategy document ready. **Awaiting direction from you on which path to take.**
