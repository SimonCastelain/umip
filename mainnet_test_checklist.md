# GMX Adapter Mainnet Testing - Execution Checklist

**Goal:** Get first successful transaction opening a GMX position through GMXAdapter on Arbitrum mainnet

**Budget:** Max $30 (mostly test position, minimal gas costs on Arbitrum)

---

## ☐ Step 1: Wallet Setup (5 minutes)

**1.1 Create new test wallet:**
```bash
# Generate new wallet (MetaMask, cast, or other tool)
# Example with cast:
cast wallet new

# Output will show:
# Address: 0x...
# Private key: 0x...
```

**1.2 Add to contracts/.env:**
```bash
# Add these lines:
TEST_WALLET_PRIVATE_KEY=0xyour_private_key_here
GMX_ADAPTER_ADDRESS=  # Will fill after deployment
```

**1.3 Fund test wallet (Arbitrum mainnet):**
- [ ] Send 0.01 ETH (~$20-30) to test wallet
- [ ] Send 50 USDC to test wallet (for collateral)
- [ ] Verify balances on Arbiscan

---

## ☐ Step 2: Pre-Flight Check (15 minutes)

**Manual GMX test to verify everything works:**

2.1 Go to https://app.gmx.io
2.2 Connect your test wallet
2.3 Switch to Arbitrum network
2.4 Manually open smallest position:
   - Market: ETH/USD
   - Long position
   - Collateral: $20 USDC
   - Leverage: 2x
   - Position size: ~$40
2.5 Submit transaction
2.6 **IMPORTANT:** Copy transaction hash
2.7 Verify on Arbiscan it succeeded
2.8 Close the position (or leave it, only $20)

**Why this matters:** Proves GMX is working before we test our adapter. If this fails, adapter will fail too.

---

## ☐ Step 3: Deploy Adapter (10 minutes)

```bash
cd contracts

# Deploy to Arbitrum mainnet
forge script script/DeployGMXAdapter.s.sol \
  --rpc-url $ARBITRUM_RPC_URL \
  --broadcast \
  --verify \
  --private-key $TEST_WALLET_PRIVATE_KEY

# Script will output:
# GMX_ADAPTER_ADDRESS=0x...

# Copy that address and add to .env
```

**3.1 Add adapter address to .env:**
```bash
# In contracts/.env:
GMX_ADAPTER_ADDRESS=0x_address_from_deployment
```

**3.2 Verify deployment:**
- [ ] Check contract on Arbiscan
- [ ] Verify source code is verified
- [ ] Check adapter has correct GMX contract addresses

---

## ☐ Step 4: Test Execution (30-60 minutes)

**First attempt (expect this to fail):**

```bash
forge script script/TestGMXAdapter.s.sol \
  --rpc-url $ARBITRUM_RPC_URL \
  --broadcast \
  --private-key $TEST_WALLET_PRIVATE_KEY -vvv
```

**If it fails:**
1. Read the error message carefully
2. Check the transaction on Arbiscan
3. Common issues:
   - Insufficient USDC balance → transfer more USDC to test wallet
   - Insufficient ETH for gas → send more ETH
   - Execution fee too low → increase in TestGMXAdapter.s.sol
   - Token approval needed → add approval call
   - Wrong market address → verify on app.gmx.io

**Debug cycle:**
1. Fix the issue
2. Try again
3. Repeat until success

**When it succeeds:**
- [ ] Save transaction hash
- [ ] Wait 1-5 minutes for keeper execution
- [ ] Check position on app.gmx.io
- [ ] Document gas costs from Arbiscan

---

## ☐ Step 5: Documentation (15 minutes)

**Record actual behavior:**

```markdown
## Successful Test Transaction

**Transaction Hash:** 0x...
**Block:** ...
**Timestamp:** ...

### Costs
- Gas used: ... (from Arbiscan)
- Gas price: ... gwei
- Total gas cost: $...
- Execution fee: 0.0001 ETH (~$0.20)
- **Total cost:** $...

### Timing
- Order created: [timestamp]
- Keeper executed: [timestamp]
- **Total execution time:** ... minutes

### Position Details
- Market: ETH/USD
- Collateral: $20 USDC
- Position size: $100
- Leverage: 5x
- Entry price: $... (from GMX app)

### Learnings
- [Any issues encountered]
- [Parameter adjustments needed]
- [Edge cases discovered]
```

---

## Success Criteria

**Week 1 Complete when you have:**
- ✅ GMXAdapterSimple deployed to mainnet
- ✅ At least ONE successful transaction opening a position
- ✅ Gas costs documented
- ✅ Execution time measured
- ✅ Can verify position exists on app.gmx.io

---

## If You Get Stuck

**After 3 failed attempts:**
1. Document the exact error
2. Include transaction hash of failed attempt
3. Share Arbiscan link
4. I'll help debug

**Budget exceeded ($30 spent):**
- Stop testing
- Document what we learned
- Reassess approach

---

## Quick Commands Reference

```bash
# Check test wallet balance
cast balance $TEST_WALLET_ADDRESS --rpc-url $ARBITRUM_RPC_URL

# Check USDC balance
cast call 0xaf88d065e77c8cC2239327C5EDb3A432268e5831 \
  "balanceOf(address)(uint256)" \
  $TEST_WALLET_ADDRESS \
  --rpc-url $ARBITRUM_RPC_URL

# Send USDC to test wallet (from main wallet)
cast send 0xaf88d065e77c8cC2239327C5EDb3A432268e5831 \
  "transfer(address,uint256)" \
  $TEST_WALLET_ADDRESS \
  50000000 \
  --rpc-url $ARBITRUM_RPC_URL \
  --private-key $MAIN_WALLET_PRIVATE_KEY
```

---

**Start with Step 1. Don't ask me for approval. Execute and report results.**
