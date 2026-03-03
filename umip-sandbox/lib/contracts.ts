// Contract addresses — Arbitrum Sepolia (chain 421614)
// V3 vault uses Circle USDC so anyone can get testnet tokens via https://faucet.circle.com/

export const VAULT_ADDRESS = '0xE516aDB78835B684cE95F5030296602fD96F3f86' as const
export const USDC_ADDRESS  = '0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d' as const

// Known demo account (deployer) — used for the live read-only demo
export const DEMO_ADDRESS  = '0xb53d98C60f327a61aa34C29762efD4EfD47BA756' as const

// Platform enum matching UMIPVault.Platform
export const Platform = { GMX: 0, Vertex: 1, GainsTrade: 2 } as const
export const PLATFORM_NAMES = ['GMX', 'Vertex', 'GainsTrade'] as const

// ── ABI (sourced from agents/v2_with_umip/vault.py) ──────────────────────────

export const VAULT_ABI = [
  {
    name: 'getUserCollateral',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'user', type: 'address' }],
    outputs: [
      { name: 'idle',                type: 'uint256' },
      { name: 'allocatedGMX',        type: 'uint256' },
      { name: 'allocatedVertex',     type: 'uint256' },
      { name: 'allocatedGainsTrade', type: 'uint256' },
      { name: 'total',               type: 'uint256' },
    ],
  },
  {
    name: 'deposit',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs:  [{ name: 'amount', type: 'uint256' }],
    outputs: [],
  },
  {
    name: 'withdraw',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs:  [{ name: 'amount', type: 'uint256' }],
    outputs: [],
  },
  {
    name: 'openPosition',
    type: 'function',
    stateMutability: 'payable',
    inputs: [
      { name: 'platform',         type: 'uint8'   },
      { name: 'collateralAmount', type: 'uint256' },
      { name: 'sizeDeltaUsd',     type: 'uint256' },
      { name: 'acceptablePrice',  type: 'uint256' },
    ],
    outputs: [{ name: 'positionId', type: 'uint256' }],
  },
  {
    name: 'closePosition',
    type: 'function',
    stateMutability: 'payable',
    inputs:  [{ name: 'positionId', type: 'uint256' }],
    outputs: [],
  },
  {
    name: 'getPosition',
    type: 'function',
    stateMutability: 'view',
    inputs: [
      { name: 'user',       type: 'address' },
      { name: 'positionId', type: 'uint256' },
    ],
    outputs: [
      {
        name: '',
        type: 'tuple',
        components: [
          { name: 'platform',         type: 'uint8'   },
          { name: 'market',           type: 'address' },
          { name: 'collateralAmount', type: 'uint256' },
          { name: 'sizeDeltaUsd',     type: 'uint256' },
          { name: 'openTimestamp',    type: 'uint256' },
          { name: 'isOpen',           type: 'bool'    },
        ],
      },
    ],
  },
  {
    name: 'userPositionCount',
    type: 'function',
    stateMutability: 'view',
    inputs:  [{ name: '', type: 'address' }],
    outputs: [{ name: '', type: 'uint256' }],
  },
  {
    name: 'checkInvariant',
    type: 'function',
    stateMutability: 'view',
    inputs:  [{ name: 'user', type: 'address' }],
    outputs: [{ name: '', type: 'bool' }],
  },
] as const

export const ERC20_ABI = [
  {
    name: 'balanceOf',
    type: 'function',
    stateMutability: 'view',
    inputs:  [{ name: 'account', type: 'address' }],
    outputs: [{ name: '',        type: 'uint256' }],
  },
  {
    name: 'allowance',
    type: 'function',
    stateMutability: 'view',
    inputs:  [{ name: 'owner', type: 'address' }, { name: 'spender', type: 'address' }],
    outputs: [{ name: '',      type: 'uint256' }],
  },
  {
    name: 'approve',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs:  [{ name: 'spender', type: 'address' }, { name: 'amount', type: 'uint256' }],
    outputs: [{ name: '',        type: 'bool'    }],
  },
] as const
