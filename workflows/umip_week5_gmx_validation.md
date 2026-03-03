# Week 5: GMX V2 On-Chain Validation Report

**Date:** 2026-02-14
**Network:** Arbitrum Sepolia (Chain ID: 421614)
**Status:** COMPLETE — Full open/close lifecycle validated

---

## Summary

Successfully deployed GMXAdapterSepolia, opened a 5x leveraged long ETH/USD position, and closed it — all on-chain on Arbitrum Sepolia. This validates the adapter's integration with GMX V2.2+ contracts.

---

## Transaction Log

| Step | Tx Hash | Block | Gas Used |
|---|---|---|---|
| **1. Deploy Adapter** | `0x313fbb15...bdd04d` | 242,571,188 | 1,022,607 |
| **2. Mint 1000 USDC** | `0xc3f76e7f...2be0c2` | 242,571,199 | 74,511 |
| **3. Open Long** | `0x7145653705bccbac996104780ce30832054893969ebe49cec95307d42d5ed7f9` | 242,571,210 | 960,047 |
| **4. Close Long** | `0x76a6d23287a591ac9017db372744054365def78676ef387761bf8c8a475bcba2` | 242,572,192 | 888,986 |

### Key Addresses

| Item | Address |
|---|---|
| **Adapter** | `0x148B975C477bdf6196670Fa09F9AA12C86F1Fe00` |
| **Deployer** | `0xb53d98C60f327a61aa34C29762efD4EfD47BA756` |
| **ETH/USD Market** | `0xb6fC4C9eB02C35A134044526C62bb15014Ac0Bcc` (WETH-USDC.SG) |
| **USDC (Stargate)** | `0x3253a335E7bFfB4790Aa4C25C4250d206E9b9773` |
| **ExchangeRouter** | `0xEd50B2A1eF0C35DAaF08Da6486971180237909c3` |
| **OrderVault** | `0x1b8AC606de71686fd2a1AEDEcb6E0EFba28909a2` |

---

## Position Details

### Open
- **Order Key:** `0x92f03c26c895002d35d38e6deeff29dd4c1c7e6bf0612e389f544436991d30f6`
- **Collateral:** 100 USDC → 99.80 USDC after fees ($0.20 position fee)
- **Position Size:** $500 (5x leverage)
- **Size in Tokens:** 0.241042 ETH
- **Execution Price:** $2,073.82 ETH/USD
- **Keeper Latency:** ~2 seconds (7 blocks: 242,571,210 → 242,571,217)

### Close
- **Order Key:** `0xb10982ee7715917e71ea1d2ed86ce7ec2f7b704aca01933e2522a415fbcead12`
- **USDC Returned to Deployer:** 99.49 USDC
- **Net Loss:** ~$0.51 (fees: position open fee + close fee)
- **Keeper Latency:** ~2 seconds (similar to open)

### Fee Breakdown
- Position open fee: ~$0.20 (deducted from collateral: 100 → 99.80 USDC)
- Position close fee: ~$0.31 (deducted from returned amount: 99.80 → 99.49 USDC)
- Total protocol fees: ~$0.51 on a $500 position = 0.10%

---

## Gas Costs

| Transaction | Gas Used | Gas Price (gwei) | ETH Cost | L1 Gas |
|---|---|---|---|---|
| Deploy adapter | 1,022,607 | 0.020 | 0.000020 ETH | 285,205 |
| Mint USDC | 74,511 | 0.020 | 0.000001 ETH | 23,310 |
| Open position | 960,047 | 0.020 | 0.000019 ETH | 38,423 |
| Close position | 888,986 | 0.020 | 0.000018 ETH | 36,630 |
| **Total gas** | **2,946,151** | | **0.000058 ETH** | |
| **Execution fees** | | | **0.002000 ETH** | (2 × 0.001 ETH) |
| **Grand total** | | | **0.002058 ETH** | |

**Key insight:** Execution fees (0.001 ETH per order) dominate costs — 97% of total ETH spent. Gas is negligible on Arbitrum Sepolia.

---

## Critical Learnings (Bugs Fixed)

### 1. Execution Fee Pattern (NOT direct msg.value)
**Wrong:** `createOrder{value: fee}(params)`
**Right:** `multicall([sendWnt(OrderVault, fee), createOrder(params)])`

GMX V2 requires execution fees to be sent via `sendWnt` which wraps ETH to WETH and transfers to the OrderVault. Direct `msg.value` on `createOrder` is silently ignored, causing "revert at 850 gas" errors.

### 2. GMX V2.2+ Interface Changes
`CreateOrderParams` struct gained two new fields in V2.2+:
```solidity
bool autoCancel;       // NEW — auto-cancel unfilled orders
bytes32[] dataList;    // NEW — additional order data
```
This changes the function selector entirely. Our old selector `0xd343f3da` did not match the deployed contract's `0xf59c48eb`. Always verify selectors against deployed bytecode.

### 3. Market Token Addresses
The "standard" ETH/USD market (`0x482Df3D3...`) is not registered on Sepolia. The active market uses Stargate USDC variant:
- Market: `0xb6fC4C9eB02C35A134044526C62bb15014Ac0Bcc`
- Collateral: `0x3253a335E7bFfB4790Aa4C25C4250d206E9b9773` (Stargate USDC)

### 4. Collateral Transfer Pattern
Collateral goes directly to OrderVault via ERC20 transfer — **no ROUTER_PLUGIN permission needed**. This was the Week 1 fork test blocker, now resolved.

### 5. Close Order Type
Close uses `orderType: 4` (MarketDecrease), not a separate function. Same `multicall` pattern, same `createOrder` call, just different order type and parameters.

---

## Adapter Architecture (Final Working Pattern)

```
openMarketLong:
  1. IERC20(collateral).transfer(OrderVault, amount)     // Direct transfer
  2. multicall([
       sendWnt(OrderVault, executionFee),                // Wrap ETH → WETH
       createOrder(MarketIncrease params)                 // Create order
     ])

closeMarketLong:
  1. multicall([
       sendWnt(OrderVault, executionFee),                // Wrap ETH → WETH
       createOrder(MarketDecrease params)                 // Create close order
     ])
```

No collateral transfer needed for close — the collateral is already in the position.

---

## Validation Verdict

**GMX V2 integration is VALIDATED.** The adapter correctly:
- Opens market long positions via the IAdapter interface
- Closes market long positions via the IAdapter interface
- Handles execution fees via the multicall/sendWnt pattern
- Receives collateral back to the specified receiver address
- Works with GMX V2.2+ contract interfaces (autoCancel, dataList)

**Ready to proceed to gTrade adapter implementation.**

---

## Files Modified

| File | Change |
|---|---|
| `contracts/src/adapters/GMXAdapterSepolia.sol` | Major rewrite: multicall pattern, V2.2+ interface |
| `contracts/script/DeploySepoliaGMX.s.sol` | Updated market + USDC addresses |
| `contracts/script/CloseSepoliaGMX.s.sol` | Updated market + USDC addresses |
| `contracts/foundry.toml` | Added Sepolia RPC |
| `.env` | Added deployer wallet, adapter address, RPC URL |
