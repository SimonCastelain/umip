'use client'

import { ConnectButton }     from '@rainbow-me/rainbowkit'
import { useAccount }        from 'wagmi'
import { useReadContract }   from 'wagmi'
import { VaultState }        from '@/components/VaultState'
import { DepositButton }     from '@/components/DepositButton'
import { PositionsTable }    from '@/components/PositionsTable'
import { VAULT_ADDRESS, VAULT_ABI, DEMO_ADDRESS } from '@/lib/contracts'

// The deployer address has real vault history — used as fallback demo
const DEMO: `0x${string}` = DEMO_ADDRESS

export default function Home() {
  const { address, isConnected } = useAccount()
  const viewAddress = isConnected && address ? address : DEMO

  const { data: posCount } = useReadContract({
    address:      VAULT_ADDRESS,
    abi:          VAULT_ABI,
    functionName: 'userPositionCount',
    args:         [viewAddress],
    query:        { refetchInterval: 15_000 },
  })

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Nav */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center text-black font-bold text-sm">U</div>
          <span className="font-semibold text-white">UMIP Sandbox</span>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">Arbitrum Sepolia</span>
        </div>
        <ConnectButton />
      </nav>

      {/* Hero */}
      <div className="max-w-4xl mx-auto px-6 pt-16 pb-8 text-center">
        <h1 className="text-4xl font-bold text-white mb-4">
          One vault.{' '}
          <span className="text-emerald-400">Every perp DEX.</span>
        </h1>
        <p className="text-gray-400 text-lg max-w-2xl mx-auto">
          UMIP lets your agent deposit once and trade across GMX, Vertex, and GainsTrade
          without fragmenting capital across wallets. Zero fragmentation by design.
        </p>

        {!isConnected && (
          <div className="mt-8 p-4 bg-gray-900 border border-gray-800 rounded-2xl text-sm text-gray-400 inline-block">
            Viewing demo account data · Connect your wallet to use your own vault
          </div>
        )}
      </div>

      {/* Main content */}
      <div className="max-w-4xl mx-auto px-6 pb-16 space-y-6">
        {/* 2-col layout on md+ */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <VaultState address={viewAddress} />
          {isConnected && <DepositButton />}
          {!isConnected && (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 flex flex-col items-center justify-center gap-4 text-center">
              <div className="text-4xl">🔒</div>
              <p className="text-gray-400 text-sm">Connect your wallet to deposit USDC and interact with the vault</p>
              <ConnectButton />
              <a
                href="https://faucet.circle.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-emerald-400 hover:underline"
              >
                Need testnet USDC? → faucet.circle.com
              </a>
            </div>
          )}
        </div>

        {/* Positions table */}
        <PositionsTable address={viewAddress} posCount={Number(posCount ?? 0n)} />

        {/* Architecture explainer */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
          <h3 className="font-semibold text-white mb-4">How UMIP Works</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { step: '1', title: 'Deposit Once', desc: 'USDC lands in UMIPVault as idle collateral. One approval, one transaction.' },
              { step: '2', title: 'Agent Decides', desc: 'Your agent monitors rates across GMX, Vertex, GainsTrade and picks the best opportunity.' },
              { step: '3', title: 'Vault Routes', desc: 'One call routes capital to the right platform. No wallet switching, no fragmentation.' },
            ].map(({ step, title, desc }) => (
              <div key={step} className="bg-gray-800/50 rounded-xl p-4">
                <div className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-bold flex items-center justify-center mb-3">{step}</div>
                <h4 className="font-medium text-white text-sm mb-1">{title}</h4>
                <p className="text-gray-500 text-xs">{desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Footer links */}
        <div className="flex items-center justify-center gap-6 text-sm text-gray-500">
          <a href="https://faucet.circle.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Circle Faucet</a>
          <span>·</span>
          <a href="https://sepolia.arbiscan.io/address/0xE516aDB78835B684cE95F5030296602fD96F3f86" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Vault Contract</a>
          <span>·</span>
          <span>Arbitrum Sepolia · Chain 421614</span>
        </div>
      </div>
    </div>
  )
}
