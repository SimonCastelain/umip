# GMX V2 Integration: Lessons Learned

**Date:** 2026-02-14
**Context:** 4 weeks of mock-based development, then 1 day of real testnet validation
**Result:** 3 critical bugs found and fixed in the first real on-chain test

---

## The 3 Bugs

### Bug 1: Execution Fee Pattern
**Symptom:** `revert at 850 gas` — a proxy-level revert before any function logic executes.

**Wrong approach:**
```solidity
// BROKEN: Direct msg.value on createOrder
orderKey = IExchangeRouter(EXCHANGE_ROUTER).createOrder{value: msg.value}(params);
```

**Correct approach:**
```solidity
// WORKING: multicall wraps ETH→WETH via sendWnt, then createOrder
bytes[] memory multicallData = new bytes[](2);
multicallData[0] = abi.encodeWithSelector(sendWnt.selector, ORDER_VAULT, executionFee);
multicallData[1] = abi.encodeWithSelector(createOrder.selector, params);
IGMXExchangeRouter(EXCHANGE_ROUTER).multicall{value: msg.value}(multicallData);
```

**Why:** GMX V2's ExchangeRouter expects execution fees as WETH in the OrderVault, not as raw ETH on the function call. `sendWnt` wraps ETH→WETH and transfers it. Direct `msg.value` on `createOrder` is silently ignored.

**How we found it:** Decoded a real successful Sepolia transaction (`0xf5433a2...`), saw the multicall pattern with sendWnt as first call.

**Time to fix:** ~2 hours

---

### Bug 2: V2.2+ Struct Changes (Function Selector Mismatch)
**Symptom:** Still `revert at 850 gas` even after fixing the multicall pattern.

**Root cause:** GMX V2.2+ added two fields to `CreateOrderParams`:
```solidity
// Old V2 struct (7 fields):
struct CreateOrderParams {
    addresses, numbers, orderType, decreasePositionSwapType,
    isLong, shouldUnwrapNativeToken, referralCode
}
// Selector: 0xd343f3da

// New V2.2+ struct (9 fields):
struct CreateOrderParams {
    addresses, numbers, orderType, decreasePositionSwapType,
    isLong, shouldUnwrapNativeToken,
    bool autoCancel,          // NEW
    bytes32 referralCode,
    bytes32[] dataList        // NEW
}
// Selector: 0xf59c48eb
```

Adding fields to a struct changes the ABI encoding, which changes the function selector. Our old selector didn't match the deployed contract's function, causing a fallback/revert.

**How we found it:** Compared our computed selector against the real tx's calldata. The first 4 bytes didn't match.

**Lesson for gTrade:** Always verify function selectors against deployed bytecode. Don't trust documentation — trust on-chain data.

**Time to fix:** ~1 hour

---

### Bug 3: Market Address Not Registered
**Symptom:** `EmptyMarket()` custom error (0x05fbc1ae) after fixing both above bugs.

**Root cause:** The "standard" ETH/USD market address (`0x482Df3D3...`) from GMX docs is not registered in the DataStore on Sepolia. The active market uses a Stargate USDC variant:
- Active market: `0xb6fC4C9eB02C35A134044526C62bb15014Ac0Bcc` (WETH-USDC.SG)
- Active collateral: `0x3253a335E7bFfB4790Aa4C25C4250d206E9b9773` (Stargate USDC)

**How we found it:** Decoded a real successful Sepolia tx to extract the market and collateral addresses used.

**Lesson:** Market addresses vary by network. Always verify by finding a successful transaction on the target network and extracting the addresses from its calldata.

**Time to fix:** ~30 minutes

---

## Gas Costs (Real On-Chain)

| Transaction | Gas Used | ETH Cost | Notes |
|---|---|---|---|
| Deploy adapter | 1,022,607 | 0.000020 | One-time cost |
| Mint test USDC | 74,511 | 0.000001 | Testnet only |
| Open position | 960,047 | 0.000019 | + 0.001 ETH execution fee |
| Close position | 888,986 | 0.000018 | + 0.001 ETH execution fee |

**Key insight:** Gas costs on Arbitrum are negligible (~$0.05 per tx). Execution fees dominate at 0.001 ETH (~$2-3) per order. This is a fixed cost per order, not proportional to position size.

## Execution Times

| Event | Latency |
|---|---|
| Order creation → Keeper execution | ~2 seconds (7 blocks on Sepolia) |
| Open → Close (full round-trip) | ~4.5 minutes (manual — could be automated) |

Keepers are fast. The async execution model works well for our vault pattern — the delay between order creation and execution is negligible for position management.

## Protocol Fees

| Fee Type | Amount | Notes |
|---|---|---|
| Open position fee | ~$0.20 | Deducted from collateral (100 → 99.80 USDC) |
| Close position fee | ~$0.31 | Deducted from returned collateral |
| Total fees | ~$0.51 | On a $500 position = 0.10% |

---

## What the Mock Got Right

1. **Position tracking by account+market+collateral+isLong** — matches real GMX V2
2. **IAdapter interface** — openMarketLong/closeMarketLong signatures work
3. **Collateral flow direction** — tokens sent to adapter, adapter forwards to protocol
4. **Async execution model** — mock executes instantly, but the interface handles async correctly
5. **Close without positionKey** — GMX identifies positions implicitly, mock mirrors this

## What the Mock Got Wrong

1. **Execution fee handling** — mock just accepts msg.value, real GMX needs sendWnt wrapping
2. **Event signature** — mock had `OrderCreated(bytes32, address, uint256)`, real adapter has `OrderCreated(bytes32, address, uint256, bool)` — fixed
3. **No multicall simulation** — acceptable for mock, but meant we never tested the actual call pattern
4. **Instant execution** — mock skips the pending order → keeper execution flow. This is fine for unit tests but means we can't test cancellation/timeout paths

## What the Mock Cannot Test

These scenarios require real testnet or fork testing:
- Order cancellation after timeout
- Keeper execution failure
- Insufficient execution fee (keeper won't pick up)
- Market suspension / circuit breaker
- Price impact on large positions
- Funding rate accumulation over time

---

## Recommendations for gTrade Adapter

Based on GMX lessons:

1. **Find a real successful transaction first.** Decode the calldata to understand the exact function signatures, struct layouts, and parameter values. Don't trust docs alone.

2. **Verify function selectors.** Compute the selector from your interface and compare against the deployed contract. One extra field = completely different selector.

3. **Test on testnet before declaring complete.** The mock-only approach worked for 4 weeks of unit testing but hid 3 critical integration bugs.

4. **Expect async execution.** gTrade also uses async (Chainlink DON oracles). Same pattern as GMX — create order, wait for keeper.

5. **Map collateral flow carefully.** gTrade uses standard approve+call (simpler than GMX's OrderVault pattern). This is actually easier, but verify the exact approve target and collateral handling.

6. **Check testnet contract addresses independently.** Don't assume mainnet addresses work on testnet. Find a real testnet tx to confirm.

---

## Files Changed

| File | Change | Why |
|---|---|---|
| `GMXAdapterSimple.sol` | Full rewrite | multicall pattern, V2.2+ interface, IAdapter impl |
| `GMXAdapterMock.sol` | Event signature | Added `bool isIncrease` to match real adapter |
| `GMXAdapterSepolia.sol` | Created + iterated 3x | Testnet validation — the source of all 3 bug fixes |
| `fork/GMXAdapterSimple.t.sol` | Updated | Matches new adapter structure |
| `IAdapter.sol` | Unchanged | Interface held up — good design |

---

**Bottom line:** 4 weeks of mock-only development was useful for architecture but insufficient for integration correctness. One day of real testnet testing found and fixed bugs that would have blocked mainnet deployment. Always validate against real contracts before moving on.
