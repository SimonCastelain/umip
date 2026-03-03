#!/bin/bash
# deploy.sh — Deploy your own UMIPVault on Arbitrum Sepolia
#
# Prerequisites:
#   1. Install Foundry: https://book.getfoundry.sh/getting-started/installation
#   2. Add DEPLOYER_PRIVATE_KEY to .env
#   3. Get Circle USDC from https://faucet.circle.com/ (select Arbitrum Sepolia)
#   4. Get testnet ETH from https://www.alchemy.com/faucets/arbitrum-sepolia
#
# Usage: bash deploy.sh

set -e
source .env

echo "🚀 Deploying UMIP Vault on Arbitrum Sepolia..."

# Check foundry
command -v forge >/dev/null 2>&1 || {
    echo "❌ Foundry not found. Install it: curl -L https://foundry.paradigm.xyz | bash"
    exit 1
}

# Check private key
[ -z "$DEPLOYER_PRIVATE_KEY" ] && { echo "❌ DEPLOYER_PRIVATE_KEY not set in .env"; exit 1; }

ARB_SEP_RPC="https://sepolia-rollup.arbitrum.io/rpc"
CIRCLE_USDC="0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d"
GMX_ADAPTER="0x148B975C477bdf6196670Fa09F9AA12C86F1Fe00"

# Clone contracts
if [ ! -d "contracts" ]; then
    echo "📦 Cloning UMIP contracts..."
    git clone https://github.com/YOUR_GITHUB_USERNAME/umip-contracts contracts
fi

cd contracts

# Deploy
echo "📝 Deploying UMIPVault..."
forge create \
    src/UMIPVault.sol:UMIPVault \
    --constructor-args "$CIRCLE_USDC" \
    --rpc-url "$ARB_SEP_RPC" \
    --private-key "$DEPLOYER_PRIVATE_KEY" \
    --json > /tmp/vault_deploy.json

VAULT_ADDR=$(cat /tmp/vault_deploy.json | python3 -c "import sys,json; print(json.load(sys.stdin)['deployedTo'])")
echo "✅ Vault deployed at: $VAULT_ADDR"

# Set GMX adapter
cast send "$VAULT_ADDR" \
    "setAdapters(address,address,address)" \
    "$GMX_ADAPTER" "0x0000000000000000000000000000000000000000" "0x0000000000000000000000000000000000000000" \
    --rpc-url "$ARB_SEP_RPC" \
    --private-key "$DEPLOYER_PRIVATE_KEY"
echo "✅ GMX adapter configured"

cd ..

# Update config
sed -i.bak "s|VAULT_ADDRESS = \"0x.*\"|VAULT_ADDRESS = \"$VAULT_ADDR\"|" config.py
echo "✅ config.py updated with new vault address: $VAULT_ADDR"

echo ""
echo "✅ Done! Next steps:"
echo "  1. Get Circle USDC: https://faucet.circle.com/"
echo "  2. Deposit USDC into your vault:"
echo "     python3 -c \"from agent import *; load_dotenv(); deposit_usdc(os.getenv('DEPLOYER_PRIVATE_KEY'), 100)\""
echo "  3. Run agent: python agent.py"
