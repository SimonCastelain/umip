'use client'

import { useReadContract } from 'wagmi'
import { VAULT_ADDRESS, VAULT_ABI, ERC20_ABI, USDC_ADDRESS } from '@/lib/contracts'

function fmt(raw: bigint | undefined): string {
  if (raw === undefined) return '—'
  return (Number(raw) / 1e6).toFixed(2)
}

function Bar({ value, total, color }: { value: bigint; total: bigint; color: string }) {
  const pct = total > 0n ? Number((value * 10000n) / total) / 100 : 0
  return (
    <div className="w-full bg-gray-800 rounded-full h-2">
      <div className={`h-2 rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

export function VaultState({ address }: { address: `0x${string}` }) {
  const { data: collateral, isLoading } = useReadContract({
    address: VAULT_ADDRESS,
    abi:     VAULT_ABI,
    functionName: 'getUserCollateral',
    args:    [address],
    query:   { refetchInterval: 10_000 },
  })

  const { data: usdcBalance } = useReadContract({
    address: USDC_ADDRESS,
    abi:     ERC20_ABI,
    functionName: 'balanceOf',
    args:    [address],
    query:   { refetchInterval: 10_000 },
  })

  const { data: posCount } = useReadContract({
    address: VAULT_ADDRESS,
    abi:     VAULT_ABI,
    functionName: 'userPositionCount',
    args:    [address],
    query:   { refetchInterval: 10_000 },
  })

  if (isLoading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 animate-pulse">
        <div className="h-4 bg-gray-800 rounded w-1/3 mb-4" />
        <div className="h-8 bg-gray-800 rounded w-1/2" />
      </div>
    )
  }

  const [idle, allocGMX, allocVtx, allocGT, total] = collateral ?? [0n, 0n, 0n, 0n, 0n]
  const utilizationPct = total > 0n
    ? Math.round(Number(((total - idle) * 100n) / total))
    : 0

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Vault State</h2>
        <span className="text-xs text-gray-500 font-mono truncate max-w-[160px]">{address}</span>
      </div>

      {/* Wallet USDC balance */}
      <div className="bg-gray-800/50 rounded-xl p-4 flex justify-between items-center">
        <span className="text-sm text-gray-400">Wallet USDC</span>
        <span className="font-mono font-semibold text-white">${fmt(usdcBalance)}</span>
      </div>

      {/* Total deposited */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-800/50 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-1">Total Deposited</p>
          <p className="text-2xl font-bold text-emerald-400">${fmt(total)}</p>
        </div>
        <div className="bg-gray-800/50 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-1">Utilization</p>
          <p className="text-2xl font-bold text-blue-400">{utilizationPct}%</p>
        </div>
      </div>

      {/* Collateral breakdown */}
      <div className="space-y-3">
        <p className="text-xs text-gray-500 uppercase tracking-widest">Collateral Breakdown</p>

        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Idle</span>
            <span className="font-mono text-white">${fmt(idle)}</span>
          </div>
          <Bar value={idle} total={total || 1n} color="bg-gray-500" />
        </div>

        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Allocated → GMX</span>
            <span className="font-mono text-blue-400">${fmt(allocGMX)}</span>
          </div>
          <Bar value={allocGMX} total={total || 1n} color="bg-blue-500" />
        </div>

        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Allocated → Vertex</span>
            <span className="font-mono text-purple-400">${fmt(allocVtx)}</span>
          </div>
          <Bar value={allocVtx} total={total || 1n} color="bg-purple-500" />
        </div>

        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Allocated → GainsTrade</span>
            <span className="font-mono text-orange-400">${fmt(allocGT)}</span>
          </div>
          <Bar value={allocGT} total={total || 1n} color="bg-orange-500" />
        </div>
      </div>

      {/* Zero fragmentation badge */}
      <div className="flex items-center gap-2 pt-1">
        <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <span className="text-xs text-emerald-400">Zero fragmentation — vault routes capital to any platform</span>
      </div>

      {posCount !== undefined && (
        <p className="text-xs text-gray-500">{posCount.toString()} position(s) tracked on-chain</p>
      )}
    </div>
  )
}
