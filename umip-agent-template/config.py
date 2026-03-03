"""
config.py — Edit this to customize your UMIP agent.

All you need to get started:
  1. Add your private key to .env (DEPLOYER_PRIVATE_KEY=0x...)
  2. Get Circle USDC at https://faucet.circle.com/ (select Arbitrum Sepolia)
  3. Set your vault address after deploying with deploy.sh

Strategy defaults: funding rate arbitrage on ETH/USD
  - Opens a long when GMX funding rate > threshold (shorts paying longs)
  - Closes when rate drops below threshold
  - All collateral in one UMIP vault — routes to GMX or gTrade automatically
"""

# ── Network ──────────────────────────────────────────────────────────────────

ARB_SEPOLIA_RPC = "https://sepolia-rollup.arbitrum.io/rpc"

# ── UMIP Vault (Arbitrum Sepolia) ─────────────────────────────────────────────
# Default: public demo vault using Circle USDC (anyone can deposit)
# Run deploy.sh to get your own vault address

VAULT_ADDRESS = "0xE516aDB78835B684cE95F5030296602fD96F3f86"
USDC_ADDRESS  = "0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d"  # Circle USDC (faucet.circle.com)

# ── Trading Parameters ────────────────────────────────────────────────────────

RATE_THRESHOLD   = 0.0005   # Open when daily funding rate > 0.05%/day
PREFER_GTRADE_IF = 2.0      # Route to gTrade when it's ≥2x cheaper than GMX
COLLATERAL_USD   = 10.0     # $ collateral per position
LEVERAGE         = 5.0      # Leverage multiplier (position size = collateral × leverage)
GMX_EXEC_FEE_ETH = 0.001   # ETH paid to GMX keeper (required for order execution)

# ── Log output ────────────────────────────────────────────────────────────────

LOG_FILE = "agent_log.jsonl"   # JSONL log — one JSON object per line
