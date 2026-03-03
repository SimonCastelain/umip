# gTrade v8/v10 Integration Plan

**Date:** 2026-02-14 (updated after gTrade integrator research)
**Purpose:** Plan GTradeAdapter implementation for UMIP multi-platform vault
**Status:** Research complete. GMX validated. Ready to build.

---

## Contract Addresses (Arbitrum Mainnet)

| Contract | Address |
|---|---|
| **GNSMultiCollatDiamond** | `0xFF162c694eAA571f685030649814282eA457f169` |
| gUSDC Vault | `0xd3443ee1e91aF28e5FB858Fbd0D72A63bA8046E0` |
| USDC | `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` |
| WETH | `0x82aF49447D8a07e3bd95BD0d56f35241523fBab1` |
| DAI | `0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1` |
| GNS Token | `0x18c11FD286C5EC11c3b683Caa813B77f5163A122` |
| GNS Staking | `0x7edDE7e5900633F698EaB0Dbc97DE640fC5dC015` |

**Testnet (Arbitrum Sepolia):**
| Contract | Address |
|---|---|
| GNSMultiCollatDiamond | `0xd659a15812064C79E189fd950A189b15c75d3186` |

Testnet UI: https://gains.trade (select "Sepolia - Practice")

---

## Key Architecture Differences: gTrade vs GMX

| Aspect | GMX V2.2+ | gTrade v10 |
|---|---|---|
| **Execution** | Async (keeper bots) | Async (Chainlink DON + trigger bots) |
| **Execution fee** | 0.001 ETH via sendWnt to OrderVault | **No ETH fee** — deducted from collateral |
| **Collateral flow** | Direct ERC20 transfer to OrderVault | **Standard approve → Diamond pulls via transferFrom** |
| **Position ID** | Implicit (account+market+collateral+isLong) | **Explicit (trader address, uint32 index)** |
| **Multiple positions** | One per market/direction/collateral | **Multiple per pair** (each gets unique index) |
| **Market ID** | Market token address | **uint16 pairIndex** (0=BTC, 1=ETH, etc.) |
| **Size spec** | `sizeDeltaUsd` (30 decimals) | `collateralAmount × leverage` |
| **Price decimals** | 30 decimals | **10 decimals** (uint64) |
| **Leverage** | Implicit (size/collateral) | **Explicit uint24** (3 decimals: 10000 = 10x) |
| **Permission** | None (direct transfer bypasses ROUTER_PLUGIN) | **None since v8** — fully permissionless |
| **Close function** | createOrder(MarketDecrease) via multicall | **closeTradeMarket(index, expectedPrice)** — simple |

**Critical insight:** gTrade is simpler to integrate than GMX. No OrderVault pattern, no multicall, standard approve+call, simpler close function.

---

## Real Transaction Analysis

### Real openTrade TX on Mainnet (Feb 14, 2026)

**TX:** `0xcd95ffacd7f99f4dc7d77c7a8719f95823fbef79459c3bc72d1acbd4becc08f4`
**Function selector:** `0x5bfcc4f8`

| Field | Value | Notes |
|---|---|---|
| user | `0xcBce5E22...` | The trader address |
| index | 0 | Auto-assigned on execution |
| pairIndex | 1 | ETH/USD |
| leverage | 63000 | 63x leverage |
| long | true | |
| isOpen | true | Must be true for new trades |
| collateralIndex | 3 | USDC |
| tradeType | 0 | MARKET |
| collateralAmount | 10,000,000 | 10 USDC (6 decimals) |
| openPrice | 82,197,710,045,183 | Ignored for market orders |
| tp | 0 | No take profit |
| sl | 0 | No stop loss |
| isCounterTrade | false | v10 field |
| positionSizeToken | 0 | Set to 0 for new trades |
| __placeholder | 0 | 48-bit reserved field |
| maxSlippageP | 1000 | 10% slippage tolerance |
| referrer | address(0) | No referral |

**Observation:** Token flow is `USDC.transferFrom(user → Diamond)` followed by 5 LINK transfers to Chainlink oracle nodes. No ETH execution fee.

### Key Corrections from Earlier Plan

1. **`isOpen` should be `true` for new trades** (plan incorrectly said `false`)
2. **`__placeholder` is `uint48`** not `uint24` (40 more bits than planned)
3. **`maxSlippageP` uses 2 decimal places**: 1000 = 10.00% (plan said "tenths of percent")
4. **Real trades use very high slippage tolerance** (10%) on mainnet

---

## Existing Integrators Analysis

### Finding: No Public Contract-to-Contract Integrators Exist

After extensive research across GitHub, Arbiscan, and documentation:

- **No open-source vault/strategy contract** calls `openTrade()` directly from another contract
- **Copin Protocol** (the main integrator) uses the **delegation pattern**: `setTradingDelegate()` + `delegatedTradingAction()`, not direct contract calls
- **Reason:** gTrade v6 blocked smart contracts (`notContract` modifier). v8 removed this restriction (May 2024), but the ecosystem hasn't built direct integrators yet

**Implication:** We'd be among the first contract-to-contract integrators. This means:
- No reference adapter code to study
- Must validate every assumption on testnet (applying GMX lesson)
- The delegation path is more battle-tested but doesn't fit our vault architecture

### Two Integration Paths

**Path A (Direct Call) — Our approach:**
```solidity
// Contract IS the trader, holds collateral, receives PnL
IERC20(usdc).approve(DIAMOND, collateralAmount);
diamond.openTrade(trade, maxSlippageP, referrer);
// trade.user = address(this)
```

**Path B (Delegation) — Copin's approach:**
```solidity
// User wallet is the trader, delegate just submits tx
diamond.delegatedTradingAction(traderWallet, encodedCalldata);
// Collateral pulled from traderWallet, not the delegate
```

**We use Path A** because our vault holds the collateral.

---

## How Position Opening Works

### Function (v10)
```solidity
function openTrade(
    ITradingStorage.Trade memory _trade,
    uint16 _maxSlippageP,    // 2 decimals: 1000 = 10.00%
    address _referrer         // address(0) for none
) external;
```

**Function selector:** `0x5bfcc4f8`

### Trade Struct (v10 — verified from real tx)
```solidity
struct Trade {
    address user;              // address(this) for contract integration
    uint32 index;              // 0 for new trades (auto-assigned on execution)
    uint16 pairIndex;          // 0=BTC/USD, 1=ETH/USD, 2=LINK/USD...
    uint24 leverage;           // 3 decimals: 10000 = 10x, 50000 = 50x, 63000 = 63x
    bool long;                 // true=long, false=short
    bool isOpen;               // TRUE for new trades (corrected from earlier)
    uint8 collateralIndex;     // 1=gDAI, 2=gETH, 3=USDC
    uint8 tradeType;           // 0=MARKET, 1=LIMIT, 2=STOP
    uint120 collateralAmount;  // Native decimals (6 for USDC, 18 for DAI/WETH)
    uint64 openPrice;          // 10 decimals (0 or ignored for market orders)
    uint64 tp;                 // Take profit (10 decimals, 0=none)
    uint64 sl;                 // Stop loss (10 decimals, 0=none)
    bool isCounterTrade;       // false for normal trades (v10 field)
    uint160 positionSizeToken; // 0 for new trades (v10 field) — CORRECTED: uint160 not uint120
    uint24 __placeholder;      // Must be 0 — CORRECTED: uint24 not uint48
}
```

### Collateral Pattern
```solidity
// Standard approve+transferFrom — Diamond pulls collateral
IERC20(USDC).approve(DIAMOND, type(uint256).max); // one-time infinite approval
diamond.openTrade(trade, 1000, address(0));
// Diamond calls transferFrom(adapter, diamond, collateralAmount) internally
```

### Execution Flow
1. Adapter calls `openTrade()` → Diamond validates, creates PendingOrder → emits `MarketOrderInitiated`
2. Chainlink DON oracle fetches price → trigger bot calls `triggerOrder()` → emits `MarketExecuted` with `trade.index`
3. If not fulfilled in ~60 seconds → call `cancelOrderAfterTimeout()` to reclaim collateral

---

## How Position Closing Works

### Function
```solidity
function closeTradeMarket(
    uint32 _index,           // Trade index from MarketExecuted event
    uint64 _expectedPrice    // For slippage protection (10 decimals)
) external;
```

**Function selector:** `0x36ce736b`

### Additional Operations
```solidity
function decreasePositionSize(uint32 _index, uint120 _collateralDelta, uint24 _leverageDelta, uint64 _expectedPrice) external;
function updateTp(uint32 _index, uint64 _newTp) external;  // Synchronous
function updateSl(uint32 _index, uint64 _newSl) external;  // Synchronous
function updateLeverage(uint32 _index, uint24 _newLeverage) external;
function increasePositionSize(uint32 _index, uint120 _collateralDelta, uint24 _leverageDelta, uint64 _expectedPrice, uint16 _maxSlippageP) external;
function cancelOrderAfterTimeout(uint32 _orderIndex) external;  // 60-second timeout safety
```

### PnL Settlement
Async (same as open). Close creates pending order → oracle fulfills → collateral ± PnL sent to `_trade.user` (our adapter contract).

---

## Adapter Implementation Plan

### IAdapter Compatibility — Parameter Mapping

| IAdapter param | gTrade equivalent | Conversion |
|---|---|---|
| `market` (address) | `pairIndex` (uint16) | `marketToPairIndex[market]` mapping |
| `collateralAmount` | `collateralAmount` (uint120) | Direct cast: `uint120(collateralAmount)` |
| `collateralToken` | `collateralIndex` (uint8) | `tokenToCollateralIndex[token]` mapping: USDC→3 |
| `sizeDeltaUsd` (30 dec) | `leverage` (uint24, 3 dec) | `leverage = sizeDeltaUsd * 1000 / (collateralAmount * 1e24)` |
| `acceptablePrice` (30 dec) | `maxSlippageP` (uint16, 2 dec) | Use fixed 1000 (10%) for v1, or derive from price |
| `executionFee` | **Ignored** | No ETH execution fee on gTrade |
| Return `bytes32` | Encode `uint32 index` | `bytes32(uint256(pendingOrderIndex))` |

**Close mapping:**

| IAdapter param | gTrade equivalent | Conversion |
|---|---|---|
| `market` | Look up trade index | Query `getTrades(address(this))` by pairIndex |
| `collateralToken` | Not needed for close | |
| `sizeDeltaUsd` | Full close only in v1 | Use `closeTradeMarket(index, price)` |
| `acceptablePrice` (30 dec) | `expectedPrice` (10 dec, uint64) | `uint64(acceptablePrice / 1e20)` |

### Proposed GTradeAdapter (Updated)

```solidity
contract GTradeAdapter is IAdapter {
    address constant DIAMOND = 0xFF162c694eAA571f685030649814282eA457f169;

    // Map "market address" to pairIndex (set by owner)
    mapping(address => uint16) public marketToPairIndex;

    // Map collateral token to gTrade collateralIndex
    mapping(address => uint8) public tokenToCollateralIndex;

    // No trade index tracking needed — resolved via on-chain getTrades() query

    function openMarketLong(
        address market,
        uint256 collateralAmount,
        address collateralToken,
        uint256 sizeDeltaUsd,
        uint256 acceptablePrice,
        uint256 executionFee
    ) external payable override returns (bytes32) {
        // 1. Approve Diamond to pull collateral
        IERC20(collateralToken).approve(DIAMOND, collateralAmount);

        // 2. Derive leverage: sizeDeltaUsd(30 dec) / collateralUsd
        // For USDC (6 dec): collateralUsd = collateralAmount * 1e24 (to get 30 dec)
        // leverage (3 dec) = sizeDeltaUsd * 1000 / (collateralAmount * 1e24)
        uint24 leverage = uint24((sizeDeltaUsd * 1000) / (uint256(collateralAmount) * 1e24));

        // 3. Build Trade struct (v10 — isOpen=true for new trades)
        ITradingStorage.Trade memory trade = ITradingStorage.Trade({
            user: address(this),
            index: 0,
            pairIndex: marketToPairIndex[market],
            leverage: leverage,
            long: true,
            isOpen: true,              // Must be true for new trades
            collateralIndex: tokenToCollateralIndex[collateralToken],
            tradeType: 0,              // MARKET
            collateralAmount: uint120(collateralAmount),
            openPrice: 0,              // Ignored for market orders
            tp: 0,
            sl: 0,
            isCounterTrade: false,
            positionSizeToken: 0,  // uint160
            __placeholder: 0      // uint24
        });

        // 4. Open trade (no msg.value needed!)
        IGNSDiamond(DIAMOND).openTrade(trade, 1000, address(0)); // 10% max slippage

        // 5. Return placeholder — real index assigned async via MarketExecuted event
        return bytes32(uint256(marketToPairIndex[market]));
    }

    function closeMarketLong(
        address market,
        address collateralToken,
        uint256 sizeDeltaUsd,
        uint256 acceptablePrice,
        uint256 executionFee
    ) external payable override returns (bytes32) {
        // On-chain trade index resolution — no off-chain relay needed
        uint16 targetPairIndex = marketToPairIndex[market];
        uint64 expectedPrice = uint64(acceptablePrice / 1e20);

        // Query all open trades for this adapter
        ITradingStorage.Trade[] memory trades = IGNSDiamond(DIAMOND).getTrades(address(this));
        for (uint i = 0; i < trades.length; i++) {
            if (trades[i].pairIndex == targetPairIndex) {
                uint32 tradeIndex = trades[i].index;
                IGNSDiamond(DIAMOND).closeTradeMarket(tradeIndex, expectedPrice);
                return bytes32(uint256(tradeIndex));
            }
        }
        revert("No active trade for market");
    }

    receive() external payable {}
}
```

### Trade Index Tracking — RESOLVED (Feb 14, 2026 Research)

**The trade index problem is solved. Direct integration is safe.**

#### How gTrade Assigns Trade Indices

Per-user monotonic counter stored on-chain:
```solidity
struct Counter {
    uint32 currentIndex;  // Next available index, increments per new trade stored
    uint32 openCount;     // Number of currently open trades
    uint192 __placeholder;
}
// Storage: mapping(address => mapping(CounterType => Counter)) userCounters
```

Index is assigned **at execution time** (oracle fulfillment), not at `openTrade()` call time.

#### MarketExecuted Event (confirmed from ITradingCallbacksUtils)
```solidity
event MarketExecuted(
    ITradingStorage.Id orderId,    // pending order ID
    address user,                   // trader address (our adapter)
    uint32 index,                   // THE TRADE INDEX
    ITradingStorage.Trade t,        // full trade object
    bool open,                      // true=open, false=close
    uint256 oraclePrice, uint256 marketPrice, uint256 liqPrice,
    uint256 priceImpactP, int256 percentProfit,
    uint256 amountSentToTrader, uint256 collateralPriceUsd
);
```

#### On-Chain View Functions Available
| Function | Returns |
|---|---|
| `getTrades(address _trader)` | All open trades for an address |
| `getTrade(address _trader, uint32 _index)` | Single trade by address+index |
| `getCounters(address _trader, CounterType _type)` | Counter with currentIndex + openCount |

#### Chosen Strategy: On-Chain Query at Close Time (Option 2)

```solidity
function closeMarketLong(...) external {
    ITradingStorage.Trade[] memory trades = diamond.getTrades(address(this));
    for (uint i = 0; i < trades.length; i++) {
        if (trades[i].pairIndex == marketToPairIndex[market]) {
            diamond.closeTradeMarket(trades[i].index, expectedPrice);
            return;
        }
    }
    revert("No active trade for market");
}
```

**Why this is best:**
- Fully on-chain, no backend dependency
- No `setTradeIndex()` function needed — simpler adapter
- Gas cost negligible for <10 open positions
- No fund-locking risk (query always works)

**Alternatives still available if needed:**
- Off-chain relay via `MarketExecuted` event (has user + index fields)
- Counter prediction: read `getCounters()` before open, safe since adapter is sole controller of its address

---

## Effort Estimate (Updated with Confidence)

| Task | Effort | Confidence | Notes |
|---|---|---|---|
| GTradeAdapter contract | 2 days | High | Simpler than GMX — no multicall, standard approve+call |
| Trade index tracking | 0.5 day | High | On-chain `getTrades()` query — no relay needed |
| GTradeAdapterMock | 1 day | High | Simpler struct, no multicall to simulate |
| Unit tests | 1-2 days | High | Follow GMX mock pattern |
| UMIPVault + Platform.GainsTrade | 0.5 day | High | Enum addition + adapter wiring |
| **Testnet validation** | **1-2 days** | **Medium** | Must verify: function selector, struct fields, collateral flow |
| **Total** | **5-7 days (~1 week)** | | |

### Confidence: **High (85%)**

Raised from 75% because:
1. Trade index problem is fully solved — on-chain query confirmed working
2. No off-chain relay dependency — simpler architecture
3. `MarketExecuted` event confirmed to emit trader address + index (backup tracking)
4. `getTrades(address)` confirmed as view function for on-chain resolution

Remaining risks:
1. No existing contract integrator to reference — we're first
2. Function selector `0x5bfcc4f8` still needs on-chain verification on Sepolia
3. `getTrades()` return format needs testnet verification (array of Trade structs)

---

## Blockers Assessment (Updated)

| Potential Blocker | Risk | Mitigation |
|---|---|---|
| No reference integrator code | **Medium** — can't copy proven patterns | Validate every assumption on Sepolia testnet |
| Trade struct v10 fields | **Low** — confirmed from real tx decode | Verify selector on Sepolia before building |
| Trade index tracking for close | **Low** — resolved via on-chain `getTrades()` query | Fully on-chain, no relay needed |
| Leverage derivation accuracy | **Medium** — `sizeDeltaUsd / collateralUsd` assumes $1 USDC | Acceptable for USDC collateral; needs oracle for non-stablecoin |
| Sepolia Diamond version | **Low-Medium** — may differ from mainnet v10 | Compare function selectors mainnet vs Sepolia |
| No ETH execution fee | **None** — actually simplifies our adapter | Less gas, simpler code |
| `isOpen` field semantics | **Low** — confirmed true for new trades from real tx | Unit test both paths |

---

## Applying GMX Lessons to gTrade Build

1. **Find a real successful tx first** — DONE (mainnet `0xcd95ff...`). Now need Sepolia equivalent.
2. **Verify function selector on target network** — Must check `0x5bfcc4f8` on Sepolia Diamond
3. **Test on testnet before declaring complete** — Mandatory. No mock-only cycle.
4. **Expect struct changes** — v10 has fields not in v8 docs. Always decode from real calldata.
5. **Map collateral flow exactly** — Diamond uses `transferFrom`, so adapter needs `approve` first. Different from GMX's direct `transfer` to OrderVault.

---

## Week 6 Build Sequence

1. **Day 1:** Verify Sepolia Diamond — check function selectors, try a manual openTrade via cast
2. **Day 2:** Build GTradeAdapter + GTradeAdapterMock
3. **Day 3:** Unit tests with mock, integrate into UMIPVault
4. **Day 4:** Deploy to Sepolia, validate open+close with real gTrade contracts
5. **Day 5:** Fix any bugs found on testnet, document results

**Non-negotiable:** Real testnet tx hashes for both open and close before Week 6 is declared complete.

---

**Status:** Ready to build. Trade index research complete (Feb 14). Direct integration is safe — on-chain `getTrades()` resolves trade index at close time. Next action: verify Sepolia Diamond function selector and begin coding.
