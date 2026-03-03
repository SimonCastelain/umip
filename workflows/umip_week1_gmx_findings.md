# UMIP Week 1: GMX Adapter Research - Findings & Status

**Date:** 2026-01-24
**Goal:** Validate GMX adapter viability for UMIP collateral management
**Status:** ⚠️ Technical blockers encountered - Alternative approaches required

## Executive Summary

We successfully mapped the complete GMX V2 architecture and interfaces, created comprehensive fork tests, and identified the integration pattern. However, we encountered **permission and execution issues** that prevent simple smart contract integration in our fork testing environment.

**Key Finding:** GMX V2 fork testing has complexities that require either:
1. More advanced permission manipulation
2. Testing with actual mainnet state/testnet
3. Alternative integration research (examining existing GMX integrations)

## What We Accomplished ✅

### 1. Complete GMX V2 Architecture Mapping

**Contract Addresses (Arbitrum, verified active 2026):**
```solidity
address GMX_EXCHANGE_ROUTER = 0x602b805EedddBbD9ddff44A7dcBD46cb07849685; // 692k+ transactions
address GMX_ROUTER = 0x7452c558d45f8afC8c83dAe62C3f8A5BE19c71f6;
address GMX_READER = 0xf60becbba223EEA9495Da3f606753867eC10d139;
address GMX_DATA_STORE = 0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8;
address GMX_ORDER_VAULT = 0x31eF83a530Fde1B38EE9A18093A333D8Bbbc40D5;
```

**Markets:**
```solidity
address ETH_USD_MARKET = 0x70d95587d40A2caf56bd97485aB3Eec10Bee6336;
```

### 2. Interface Specifications

**Complete `CreateOrderParams` structure documented:**
```solidity
struct CreateOrderParams {
    CreateOrderParamsAddresses addresses;  // receiver, market, collateral token
    CreateOrderParamsNumbers numbers;      // size, collateral, prices, fees
    OrderType orderType;                   // MarketIncrease, LimitIncrease, etc.
    DecreasePositionSwapType decreasePositionSwapType;
    bool isLong;
    bool shouldUnwrapNativeToken;
    bytes32 referralCode;
}
```

### 3. Integration Pattern Identified

**GMX V2 Order Creation Flow:**
1. Transfer collateral to OrderVault (or use multicall with sendTokens)
2. Call `ExchangeRouter.createOrder()` with execution fee
3. Keeper executes order off-chain with oracle prices
4. Position created and settled on-chain

### 4. Fork Test Infrastructure Created

File: [`contracts/test/fork/GMXIntegration.t.sol`](../contracts/test/fork/GMXIntegration.t.sol)

- Complete test setup with funded accounts
- Proper interface definitions
- Multiple test approaches attempted

## Technical Blockers Encountered ❌

### Blocker 1: ROUTER_PLUGIN Permission Issue

**Problem:**
When using `multicall([sendTokens(), createOrder()])` pattern:
```
Error: ROUTER_PLUGIN role missing
- ExchangeRouter lacks permission to call Router.pluginTransfer()
- Role hash: 0x97adf037b2472f4a6a9825eff7d2dd45e37f2dc308df2a260d6a72af4189a65b
```

**Attempted Solution:**
Used `vm.store()` to grant role in fork test - unsuccessful (storage slot calculation may be incorrect)

**Impact:**
Cannot use the documented multicall pattern in fork tests

### Blocker 2: Direct createOrder Revert

**Problem:**
When using simplified pattern (direct transfer + createOrder):
```solidity
USDC.transfer(OrderVault, amount);  // ✅ Succeeds
router.createOrder{value: executionFee}(params);  // ❌ Reverts at proxy level (894 gas)
```

**Analysis:**
- Transfer succeeds
- createOrder reverts immediately (proxy-level failure)
- Only 894 gas used → fails before reaching implementation logic

**Possible Causes:**
1. Router paused/disabled in fork state
2. Execution fee handling incorrect
3. Missing initialization or setup step
4. Proxy/implementation mismatch in fork

### Blocker 3: Execution Fee Handling Unclear

**Observation from Mainnet:**
- Successful transactions use `multicall` with **0 ETH value**
- Our tests send execution fee as msg.value
- Discrepancy suggests different fee payment mechanism

**Questions:**
- Is execution fee pre-deposited?
- Does it use `sendWnt()` separately?
- Is there a fee payment contract?

## Analysis of Real GMX Transactions

**Examined Transaction:** [0x8617bad8e189...](https://www.arbiscan.io/tx/0x8617bad8e189e7ce47d1283f3db0301c8089709bd6b60239f95a3d0d1436a48f)

**Findings:**
- ✅ Uses `multicall(bytes[] data)` - Method ID: `0xac9650d8`
- ✅ Sends **0 ETH** value
- ✅ Contains nested function calls
- ✅ Successful execution with order operations

**Implications:**
Our testing approach may be fundamentally different from production usage pattern.

## Alternative Approaches to Consider

### Approach A: Study Existing GMX Integrations 🔍

**Strategy:** Find and analyze projects already integrating with GMX V2

**Examples to examine:**
- SteadeFi ([GitHub](https://github.com/Cyfrin/2023-10-SteadeFi))
- Other DeFi protocols on Arbitrum using GMX
- GMX's own test suite

**Pros:**
- ✅ Learn from working implementations
- ✅ Discover edge cases and best practices
- ✅ May reveal simpler patterns

**Cons:**
- ⏱️ Time investment to find and study code
- ❌ May still have fork testing challenges

**Recommendation:** **Start here** - likely fastest path to working integration

### Approach B: Mainnet/Testnet Testing 🌐

**Strategy:** Deploy to Arbitrum testnet or use mainnet fork at specific block

**Steps:**
1. Find recent successful GMX transaction block
2. Fork at that specific block number
3. Or deploy to Arbitrum Sepolia testnet

**Pros:**
- ✅ Real environment, real permissions
- ✅ No vm cheatcode complexity
- ✅ Validates production behavior

**Cons:**
- ⏱️ Slower iteration cycle
- 💰 Requires testnet ETH/tokens
- ❌ Less control over test conditions

### Approach C: Deep Dive Into GMX Permissions 🔧

**Strategy:** Reverse engineer the permission system

**Steps:**
1. Find RoleStore admin address
2. Use `vm.prank()` to impersonate admin
3. Properly grant ROUTER_PLUGIN role
4. Test multicall pattern

**Pros:**
- ✅ Could unblock multicall approach
- ✅ Clean fork testing solution

**Cons:**
- ⏱️ Requires deep contract analysis
- ❌ May hit other blockers downstream
- ❌ Fragile (depends on internal implementation)

### Approach D: Simplified Integration Pattern 📝

**Strategy:** Skip fork tests, build adapter based on interface knowledge

**Approach:**
1. We know the interfaces (documented above)
2. Build `GMXAdapter` assuming working createOrder
3. Defer integration testing to testnet/mainnet
4. Focus on adapter architecture and UMIP vault logic

**Pros:**
- ✅ Unblocked for Week 2-3 development
- ✅ Can test adapter logic independently
- ✅ Move forward on UMIP architecture

**Cons:**
- ❌ No validation of actual GMX interaction
- ❌ May discover issues late in development
- ❌ Risky for production deployment

## Recommended Path Forward

### **Recommendation: Approach A + D (Parallel)**

**Week 1 Extension (2-3 days):**
1. **Study existing integrations** - Find working GMX adapter code
   - Search GitHub for recent GMX V2 integrations
   - Analyze SteadeFi's GMXWorker pattern
   - Extract working patterns

2. **Build UMIP GMXAdapter** - Based on learned patterns
   - Use discovered integration approach
   - Implement deposit/withdraw/openPosition/closePosition
   - Add safety checks and error handling

**Why This Approach:**
- ✅ Learns from battle-tested code
- ✅ Unblocks UMIP vault development
- ✅ Can validate on testnet when adapter ready
- ⏱️ Fastest path to working prototype

### Alternative If Time-Constrained

**Focus on Vertex first (Week 2):**
- Vertex slow mode might be simpler
- Return to GMX with more knowledge
- Compare both before finalizing architecture

## Technical Artifacts Created

### Files Created:
1. [gmx_v2_integration.md](gmx_v2_integration.md) - Complete research documentation
2. [GMXIntegration.t.sol](../contracts/test/fork/GMXIntegration.t.sol) - Fork test infrastructure
3. [unified_interface_strategy.md](unified_interface_strategy.md) - Architecture analysis (pre-UMIP clarity)

### Contract Interfaces Defined:
- `IExchangeRouter` - Complete with all enums and structs
- `IERC20` - Token operations
- Ready for adapter implementation

## Key Learnings for UMIP

### 1. GMX V2 is Adapter-Friendly
- Clear interfaces
- Well-documented contracts
- Active mainnet usage (692k+ transactions)

### 2. Fork Testing Has Limitations
- Permission systems are complex
- May need real environment for validation
- Consider testnet for integration tests

### 3. Integration Pattern is Manageable
```solidity
// Pseudo-code for UMIP GMXAdapter
contract GMXAdapter {
    function deposit(uint256 amount) external {
        // Transfer from vault to adapter
        // Approve GMX contracts
    }

    function openPosition(Market market, uint256 size, bool isLong) external {
        // Transfer collateral to OrderVault
        // Call createOrder with params
        // Return order key for tracking
    }

    function closePosition(bytes32 orderKey) external {
        // Create decrease order
        // Return to vault when executed
    }
}
```

### 4. Two-Step Execution Model
- User/contract creates order
- Keeper executes asynchronously
- **UMIP Implication:** Need to handle pending states

## Questions for Decision

1. **Should we invest more time in fork testing** or move to testnet validation?

2. **Should we study existing integrations first** or build from our current knowledge?

3. **Should we parallelize with Vertex** (might be simpler) while solving GMX?

4. **What's the priority:** Working prototype vs. perfect testing?

## Next Actions (Pending Direction)

**Option 1: Continue GMX (Recommended)**
- [ ] Search GitHub for working GMX V2 integrations
- [ ] Analyze found integrations
- [ ] Build UMIP GMXAdapter based on patterns
- [ ] Test on Arbitrum testnet

**Option 2: Pivot to Vertex**
- [ ] Start Vertex slow mode research
- [ ] Compare complexity vs. GMX
- [ ] Return to GMX with more context

**Option 3: Hybrid Development**
- [ ] Build adapter interfaces for both
- [ ] Implement adapter logic
- [ ] Defer integration testing to testnet

## Resources

- [GMX V2 Documentation](https://docs.gmx.io/docs/trading/v2/)
- [GMX Synthetics GitHub](https://github.com/gmx-io/gmx-synthetics)
- [Exchange Router (Arbiscan)](https://ww4.arbiscan.io/address/0x602b805EedddBbD9ddff44A7dcBD46cb07849685)
- [Successful Transaction Example](https://www.arbiscan.io/tx/0x8617bad8e189e7ce47d1283f3db0301c8089709bd6b60239f95a3d0d1436a48f)

---

**Status:** Week 1 research complete with blockers. Architecture understood, integration pattern identified. Awaiting direction on how to proceed with adapter implementation.
