# GMX V2 Integration Research

**Status:** Day 2-3 Complete - Contract Interface Discovered, Permission Issues Identified
**Last Updated:** 2026-01-24

## Objective

Understand how to programmatically interact with GMX V2 on Arbitrum to create leveraged positions, specifically for building a unified interface abstraction.

## What We Learned

### ✅ Confirmed Working Knowledge

#### 1. GMX V2 Contract Addresses (Arbitrum Mainnet - Current as of Jan 2026)

```solidity
address GMX_EXCHANGE_ROUTER = 0x602b805EedddBbD9ddff44A7dcBD46cb07849685; // 692k+ transactions
address GMX_ROUTER = 0x7452c558d45f8afC8c83dAe62C3f8A5BE19c71f6;
address GMX_READER = 0xf60becbba223EEA9495Da3f606753867eC10d139;
address GMX_DATA_STORE = 0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8;
address GMX_ORDER_VAULT = 0x31eF83a530Fde1B38EE9A18093A333D8Bbbc40D5;
```

#### 2. Order Creation Interface

**Function Signature:**
```solidity
function createOrder(
    IBaseOrderUtils.CreateOrderParams calldata params
) external payable returns (bytes32 orderKey)
```

**Parameter Structure:**
```solidity
struct CreateOrderParams {
    CreateOrderParamsAddresses addresses;
    CreateOrderParamsNumbers numbers;
    OrderType orderType;
    DecreasePositionSwapType decreasePositionSwapType;
    bool isLong;
    bool shouldUnwrapNativeToken;
    bytes32 referralCode;
}

struct CreateOrderParamsAddresses {
    address receiver;              // Address to receive the position
    address callbackContract;      // Optional callback on execution
    address uiFeeReceiver;         // UI fee recipient
    address market;                // Market address (e.g., ETH/USD market)
    address initialCollateralToken; // Token for collateral (USDC, USDT, etc.)
    address[] swapPath;            // Markets to swap through
}

struct CreateOrderParamsNumbers {
    uint256 sizeDeltaUsd;                    // Position size in USD (30 decimals)
    uint256 initialCollateralDeltaAmount;    // Collateral amount
    uint256 triggerPrice;                    // 0 for market orders
    uint256 acceptablePrice;                 // Max slippage (type(uint256).max for market)
    uint256 executionFee;                    // Fee for keeper (in ETH)
    uint256 callbackGasLimit;                // Gas for callback
    uint256 minOutputAmount;                 // Min output for swaps
}
```

#### 3. Expected Order Creation Flow

Based on GMX V2 tests and documentation:

1. **Approve Router** to spend collateral tokens
   ```solidity
   IERC20(collateralToken).approve(GMX_ROUTER, amount);
   ```

2. **Use Multicall** to atomically:
   - Send tokens to OrderVault via `sendTokens()`
   - Create order via `createOrder()`

   ```solidity
   bytes[] memory multicallData = new bytes[](2);
   multicallData[0] = abi.encodeWithSelector(
       router.sendTokens.selector,
       collateralToken,
       GMX_ORDER_VAULT,
       collateralAmount
   );
   multicallData[1] = abi.encodeWithSelector(
       router.createOrder.selector,
       params
   );
   router.multicall{value: executionFee}(multicallData);
   ```

3. **Keeper Execution** (off-chain)
   - GMX keepers monitor for new orders
   - They execute orders with oracle price data
   - User's execution fee compensates the keeper

### ❌ Blockers Encountered

#### Permission Error: `ROUTER_PLUGIN` Role Missing

**Error:**
```
custom error 0xa35b150b: ROUTER_PLUGIN
```

**Root Cause:**
- When ExchangeRouter calls `sendTokens()` via multicall
- It delegates to `pluginTransfer()` on the Router contract
- Router checks if caller has `ROUTER_PLUGIN` role
- ExchangeRouter (0x602b...) doesn't have this role in current fork state

**Call Stack:**
```
GMXIntegrationTest
  → ExchangeRouter.multicall()
    → ExchangeRouter.sendTokens() [delegatecall]
      → Router.pluginTransfer()
        → RoleStore.hasRole(ExchangeRouter, "ROUTER_PLUGIN")
          → Returns false → REVERT
```

#### Implications

1. **Contract-to-Contract calls may be restricted** - GMX might require whitelisting/registration
2. **EOA calls might work differently** - Need to test with actual EOA transaction pattern
3. **Permissions may have been revoked** - Fork state might reflect paused/disabled features
4. **Alternative entry points may exist** - There might be a different router for smart contracts

### 📊 Test Results

**File:** `contracts/test/fork/GMXIntegration.t.sol`

**Tests Implemented:**
1. ✅ `test_ExploreExchangeRouterInterface()` - Interface discovery (permission error)
2. ⏸️ `test_QueryOrderDetails()` - Not yet run
3. ⏸️ `test_MonitorOrderEvents()` - Not yet run
4. ⏸️ `test_SimulateKeeperExecution()` - Not yet run
5. ⏸️ `test_QueryPositions()` - Not yet run

**Successful Steps:**
- ✅ Contract addresses are correct
- ✅ Token approvals work
- ✅ Interface definitions are valid
- ✅ Multicall data encoding works
- ❌ Order creation fails on permission check

## Next Steps

### Option A: Alternative GMX Integration Approaches

1. **Use GMX SDK/API** instead of direct contract calls
   - Query their subgraph for market data
   - Use their frontend SDK for order construction
   - Submit via their relayer

2. **Test with Actual EOA** (not forge test prank)
   - Deploy a test contract on Arbitrum testnet
   - Call from EOA to see if permissions differ
   - Trace successful mainnet transactions

3. **Contact GMX Team**
   - Ask about contract whitelisting process
   - Inquire about ROUTER_PLUGIN role requirements
   - Check if there's a developer API/access

### Option B: Build Abstraction Layer Assuming EOA Usage

If our unified interface is meant to be called by EOAs (not other smart contracts), we can:

1. Build the abstraction assuming direct user calls
2. Our contract would be a view/query layer, not execution layer
3. Users would call GMX directly through our interface helpers

### Option C: Pivot to Vertex Protocol First

Since GMX has permission complexities:

1. Start with Vertex Protocol integration (Day 4-5)
2. Build the abstraction layer for Vertex
3. Return to GMX once we understand Vertex's patterns
4. Compare architectures to design unified interface

## Recommendations

**Recommended Path: Option C**

**Reasoning:**
1. We've learned GMX's interface structure (valuable for later)
2. Vertex might have simpler contract access
3. Understanding both protocols will inform better abstraction design
4. We can return to GMX with more context

**Immediate Action:**
Create `contracts/test/fork/VertexIntegration.t.sol` and explore Vertex's:
- Contract addresses
- Order creation interface
- Permission requirements
- Position querying

## Resources

- [GMX V2 Documentation](https://docs.gmx.io/docs/trading/v2/)
- [GMX Synthetics GitHub](https://github.com/gmx-io/gmx-synthetics)
- [GMX V2 Exchange Router (Arbiscan)](https://ww4.arbiscan.io/address/0x602b805EedddBbD9ddff44A7dcBD46cb07849685)
- [Cyfrin GMX Course](https://updraft.cyfrin.io/courses/gmx-perpetuals-trading)
- [SteadeFi GMX Integration Example](https://github.com/Cyfrin/2023-10-SteadeFi/blob/main/contracts/strategy/gmx/GMXWorker.sol)

## Key Takeaways

1. **GMX V2 uses a multicall pattern** for atomic token transfer + order creation
2. **Two-step execution model**: User creates order → Keeper executes with oracle prices
3. **Permission architecture**: Contracts need ROUTER_PLUGIN role for certain operations
4. **Our interface definitions are correct** - when permissions work, this pattern should succeed
5. **Smart contract integration may require whitelisting** - not a self-service process

---

**Next Workflow:** `vertex_integration.md` (Day 4-5)
