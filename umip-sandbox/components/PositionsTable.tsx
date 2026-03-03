'use client'

import { useReadContracts } from 'wagmi'
import { VAULT_ADDRESS, VAULT_ABI, PLATFORM_NAMES } from '@/lib/contracts'

interface Position {
  platform:         number
  market:           string
  collateralAmount: bigint
  sizeDeltaUsd:     bigint
  openTimestamp:    bigint
  isOpen:           boolean
}

function shortAddr(addr: string) {
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`
}

function timeAgo(ts: bigint) {
  const secs = Math.floor(Date.now() / 1000) - Number(ts)
  if (secs < 60)   return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  return `${Math.floor(secs / 3600)}h ago`
}

export function PositionsTable({ address, posCount }: { address: `0x${string}`; posCount: number }) {
  const contracts = Array.from({ length: posCount }, (_, i) => ({
    address:      VAULT_ADDRESS,
    abi:          VAULT_ABI,
    functionName: 'getPosition' as const,
    args:         [address, BigInt(i)] as const,
  }))

  const { data, isLoading } = useReadContracts({
    contracts,
    query: { refetchInterval: 15_000, enabled: posCount > 0 },
  })

  if (posCount === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <h2 className="text-lg font-semibold mb-3">Positions</h2>
        <p className="text-gray-500 text-sm">No positions opened yet.</p>
      </div>
    )
  }

  const positions = data
    ?.map((r) => r.result as Position | undefined)
    .filter((p): p is Position => !!p && p.isOpen)

  if (isLoading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 animate-pulse">
        <div className="h-4 bg-gray-800 rounded w-1/4 mb-4" />
        {[0, 1].map((i) => <div key={i} className="h-10 bg-gray-800 rounded mb-2" />)}
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Open Positions</h2>
        <span className="text-xs bg-emerald-900/40 text-emerald-400 px-2 py-1 rounded-full">
          {positions?.length ?? 0} open
        </span>
      </div>

      {(!positions || positions.length === 0) ? (
        <p className="text-gray-500 text-sm">All positions closed.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-800">
                <th className="pb-3 pr-4 font-medium">Platform</th>
                <th className="pb-3 pr-4 font-medium">Market</th>
                <th className="pb-3 pr-4 font-medium text-right">Collateral</th>
                <th className="pb-3 pr-4 font-medium text-right">Size</th>
                <th className="pb-3 font-medium text-right">Opened</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {positions.map((pos, i) => (
                <tr key={i} className="text-gray-300 hover:bg-gray-800/30 transition-colors">
                  <td className="py-3 pr-4">
                    <span className="bg-blue-900/40 text-blue-400 px-2 py-0.5 rounded text-xs font-medium">
                      {PLATFORM_NAMES[pos.platform] ?? `Platform ${pos.platform}`}
                    </span>
                  </td>
                  <td className="py-3 pr-4 font-mono text-xs text-gray-500">{shortAddr(pos.market)}</td>
                  <td className="py-3 pr-4 text-right font-mono">
                    ${(Number(pos.collateralAmount) / 1e6).toFixed(2)}
                  </td>
                  <td className="py-3 pr-4 text-right font-mono text-gray-400">
                    ${(Number(pos.sizeDeltaUsd) / 1e30).toFixed(2)}
                  </td>
                  <td className="py-3 text-right text-gray-500">{timeAgo(pos.openTimestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
