# GMX Reference Transaction Pattern

**Source:** [GMX Synthetics Test Suite](https://github.com/gmx-io/gmx-synthetics/blob/main/test/router/ExchangeRouter.ts)

## The Pattern (from Working Tests)

GMX V2 uses a **multicall pattern** to atomically transfer collateral and create orders:

```typescript
exchangeRouter.multicall([
  // Step 1: Transfer collateral to OrderVault
  encodeFunctionData("sendWnt", [orderVault, amount]),

  // Step 2: Create order
  encodeFunctionData("createOrder", [params])
],
{ value: executionFee })  // ETH for keeper execution
```

## Key Contracts (Arbitrum Mainnet)

- **ExchangeRouter:** `0x7C68C7866A64FA2160F78EEaE12217FFbf871fa8`
- **OrderVault:** `0x31eF83a530Fde1B38EE9A18093A333D8Bbbc40D5`
- **DataStore:** `0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8`

## CreateOrderParams Structure

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
    address receiver;
    address cancellationReceiver;
    address callbackContract;
    address uiFeeReceiver;
    address market;
    address initialCollateralToken;
    address[] swapPath;
}

struct CreateOrderParamsNumbers {
    uint256 sizeDeltaUsd;
    uint256 initialCollateralDeltaAmount;
    uint256 triggerPrice;
    uint256 acceptablePrice;
    uint256 executionFee;
    uint256 callbackGasLimit;
    uint256 minOutputAmount;
    uint256 validFromTime;
}
```

## Example Values (from tests)

**Market Increase (Open Long Position):**
```typescript
{
  addresses: {
    receiver: user,
    cancellationReceiver: user,
    callbackContract: address(0),
    uiFeeReceiver: address(0),
    market: ethUsdMarket,              // e.g., ETH-USD market token
    initialCollateralToken: weth,      // Using WETH as collateral
    swapPath: [ethUsdMarket],
  },
  numbers: {
    sizeDeltaUsd: 1000e30,             // $1000 position size (30 decimals)
    initialCollateralDeltaAmount: 0,   // 0 when using sendWnt
    triggerPrice: 0,                   // 0 for market orders
    acceptablePrice: 4900e30,          // Max price willing to pay
    executionFee: 1e18,                // 1 WNT (~0.0003 ETH on Arbitrum)
    callbackGasLimit: 200000,
    minOutputAmount: 0,
    validFromTime: 0,                  // Valid immediately
  },
  orderType: 2,                        // OrderType.MarketIncrease
  decreasePositionSwapType: 0,         // Not used for increase
  isLong: true,
  shouldUnwrapNativeToken: false,
  referralCode: 0x0,
}
```

## Order Types (enum values)

```solidity
enum OrderType {
    MarketSwap,        // 0
    LimitSwap,         // 1
    MarketIncrease,    // 2
    LimitIncrease,     // 3
    MarketDecrease,    // 4
    LimitDecrease,     // 5
    StopLossDecrease,  // 6
    Liquidation        // 7
}
```

## Critical Details

1. **Execution Fee:** ~1 WNT (wrapped native token) = 0.0003 ETH on Arbitrum
2. **Atomic Execution:** Collateral transfer + createOrder MUST be in same tx (via multicall)
3. **Price Decimals:** GMX uses 30 decimals for USD values
4. **Async Execution:** Orders are executed by keepers after creation (not immediate)
5. **Native Token:** Use `sendWnt` for ETH/WETH, `sendTokens` for other ERC20s

## Next Steps

Build `GMXAdapter.sol` that:
1. Implements multicall pattern
2. Handles token approvals to OrderVault
3. Encodes createOrder params correctly
4. Manages execution fees
5. Provides simple interface: `openMarketLong(market, collateral, size, leverage)`
