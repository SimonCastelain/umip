# UMIP Integration Guide

Integrate UMIPVault into your agent in 5 steps. Works from Solidity, Python, or TypeScript.

**Live demo:** https://umip-sandbox.vercel.app
**Proof of concept:** https://umip-dashboard.vercel.app

---

## Contract Addresses (Arbitrum Sepolia)

| Contract | Address | Purpose |
|----------|---------|---------|
| UMIPVault | `0xE516aDB78835B684cE95F5030296602fD96F3f86` | Hub vault — deposit once, trade everywhere |
| GMXAdapterSepolia | `0x148B975C477bdf6196670Fa09F9AA12C86F1Fe00` | Routes to GMX V2 on Sepolia |
| Circle USDC | `0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d` | Collateral token (faucet: faucet.circle.com) |

---

## Solidity Integration (5 steps)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IUMIPVault {
    function deposit(uint256 amount) external;
    function withdraw(uint256 amount) external;
    function openPosition(uint8 platform, uint256 collateral, uint256 size, uint256 price)
        external payable returns (uint256 positionId);
    function closePosition(uint256 positionId) external payable;
    function getUserCollateral(address user) external view
        returns (uint256 idle, uint256 gmx, uint256 vertex, uint256 gainsTrade, uint256 total);
}

contract MyAgent {
    IUMIPVault constant vault = IUMIPVault(0xE516aDB78835B684cE95F5030296602fD96F3f86);
    IERC20     constant usdc  = IERC20(0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d);

    uint8 constant GMX_PLATFORM = 0;

    // Step 1: Deposit once (call once, then use openPosition forever)
    function depositCollateral(uint256 usdcAmount) external {
        usdc.transferFrom(msg.sender, address(this), usdcAmount);
        usdc.approve(address(vault), usdcAmount);
        vault.deposit(usdcAmount);
    }

    // Step 2: Open a position on GMX via vault (zero fragmentation)
    function executeStrategy() external payable {
        (uint256 idle,,,,) = vault.getUserCollateral(address(this));
        uint256 collateral = idle / 2;               // use half of idle
        uint256 size       = collateral * 5 * 1e24;  // 5x leverage, GMX 30-decimal

        // One call — vault routes to GMX automatically
        vault.openPosition{value: 0.001 ether}(
            GMX_PLATFORM,
            collateral,
            size,
            type(uint256).max  // market order: accept any price
        );
    }

    // Step 3: Close when done
    function closeAll(uint256 positionId) external payable {
        vault.closePosition{value: 0.001 ether}(positionId);
    }
}
```

---

## Python Integration

```python
from agent import get_vault_state, open_position, close_position, get_open_positions
from config import VAULT_ADDRESS, USDC_ADDRESS

PRIVATE_KEY = "0x..."  # from .env

# Check vault state
state = get_vault_state("0xYourAddress")
print(f"Idle: ${state['idle_usdc']:.2f} | Positions: {state['position_count']}")

# Open a position
result = open_position(PRIVATE_KEY)
print(f"Opened: {result['tx_hash']}")

# Query open positions
positions = get_open_positions("0xYourAddress")
for pos in positions:
    print(f"  #{pos['id']}: ${pos['collateral_usd']} collateral, ${pos['size_usd']} size")

# Close a position
result = close_position(PRIVATE_KEY, position_id=0)
print(f"Closed: {result['tx_hash']}")
```

Full working example: `umip-agent-template/agent.py`

---

## TypeScript / Viem Integration

```typescript
import { createPublicClient, createWalletClient, http, parseUnits, maxUint256 } from 'viem'
import { arbitrumSepolia } from 'viem/chains'

const VAULT_ADDRESS = '0xE516aDB78835B684cE95F5030296602fD96F3f86'
const USDC_ADDRESS  = '0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d'

const publicClient = createPublicClient({ chain: arbitrumSepolia, transport: http() })

// Read vault state
const [idle, allocGMX, allocVtx, allocGT, total] = await publicClient.readContract({
  address: VAULT_ADDRESS,
  abi: VAULT_ABI,
  functionName: 'getUserCollateral',
  args: ['0xYourAddress'],
})
console.log(`Idle: ${Number(idle) / 1e6} USDC`)

// Deposit USDC
await walletClient.writeContract({
  address: USDC_ADDRESS,
  abi: ERC20_ABI,
  functionName: 'approve',
  args: [VAULT_ADDRESS, maxUint256],
})

await walletClient.writeContract({
  address: VAULT_ADDRESS,
  abi: VAULT_ABI,
  functionName: 'deposit',
  args: [parseUnits('100', 6)],  // 100 USDC
})

// Open a position
const positionId = await walletClient.writeContract({
  address: VAULT_ADDRESS,
  abi: VAULT_ABI,
  functionName: 'openPosition',
  args: [
    0,                           // Platform.GMX
    parseUnits('10', 6),         // $10 collateral
    BigInt('50000000000000000000000000000000'),  // $50 size (5x, 30 decimals)
    BigInt(2 ** 256 - 1),        // any price (market order)
  ],
  value: BigInt('1000000000000000'),  // 0.001 ETH execution fee
})
```

Full working example: `umip-sandbox/lib/contracts.ts` + `umip-sandbox/components/DepositButton.tsx`

---

## Common Patterns

### Pattern 1: Funding Rate Arbitrage
Open longs when GMX funding rate is high (shorts pay longs). Close when rate normalizes.
Capital flows from vault → GMX automatically. No pre-funding of GMX wallet required.

```python
# See umip-agent-template/agent.py for complete implementation
if gmx_rate > RATE_THRESHOLD and not has_positions:
    open_position(private_key)
elif gmx_rate < RATE_THRESHOLD and has_positions:
    close_position(private_key, position_id=0)
```

### Pattern 2: Cross-Venue Hedging (delta-neutral)
Long on GMX + short on gTrade simultaneously from same collateral pool.

```python
# Without UMIP: need GMX_USDC wallet AND GNS_USDC wallet → capital fragmented
# With UMIP: one vault → open on GMX, open on gTrade, both from idle collateral
long_id  = vault.openPosition(Platform.GMX, collateral, size, MAX_PRICE)
short_id = vault.openPosition(Platform.GainsTrade, collateral, size, 0)
```

### Pattern 3: Dynamic Rebalancing
Monitor rates continuously and shift capital to whichever platform offers the best rate.

```python
while True:
    rates = fetch_rates()
    state = get_vault_state(address)
    best  = max(rates, key=lambda k: rates[k])

    if best == "gmx" and state["allocated_gt_usdc"] > 0:
        close_gtrade_positions()   # frees idle collateral
        open_gmx_position()        # vault routes idle → GMX

    time.sleep(3600)
```

---

## Vault Architecture

```
User deposits USDC once
        │
        ▼
┌─────────────────────────────┐
│       UMIPVault             │
│                             │
│  userIdleCollateral: $900   │
│  userAllocatedGMX:   $100   │
│  userAllocatedGT:    $0     │
│  userTotal:          $1000  │
└─────────┬───────────────────┘
          │ openPosition(Platform.GMX, ...)
          │ transfers collateral to adapter
          ▼
┌─────────────────────┐
│  GMXAdapterSepolia  │
│  → GMX V2 Router   │
│  → OrderVault       │
│  → Position opened  │
└─────────────────────┘
```

The invariant always holds: `idle + allocatedGMX + allocatedVertex + allocatedGainsTrade = total`

---

## Key Contract Functions

| Function | Args | Description |
|----------|------|-------------|
| `deposit(amount)` | amount: uint256 | Deposit USDC. Approve first. |
| `withdraw(amount)` | amount: uint256 | Withdraw idle collateral |
| `openPosition(platform, collateral, size, price)` | payable | Open position. Needs 0.001 ETH fee. |
| `closePosition(positionId)` | payable | Close open position |
| `getUserCollateral(user)` | address | Returns (idle, gmx, vertex, gainsTrade, total) |
| `getPosition(user, id)` | address, uint256 | Returns position struct |
| `userPositionCount(user)` | address | Total positions for user |
