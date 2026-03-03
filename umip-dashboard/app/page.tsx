'use client'

import { useEffect, useState, useCallback } from 'react'
import { ComparisonData, FALLBACK }          from '@/lib/data'
import { MetricsComparison }                 from '@/components/MetricsComparison'
import { UtilizationChart }                  from '@/components/UtilizationChart'
import { LiveEventsFeed }                    from '@/components/LiveEvents'
import { OpportunityCostCalculator }         from '@/components/OpportunityCostCalculator'

const POLL_MS = 60_000 // refresh every 60s

export default function Dashboard() {
  const [data, setData]         = useState<ComparisonData>(FALLBACK)
  const [lastUpdated, setLast]  = useState<Date | null>(null)
  const [loading, setLoading]   = useState(true)

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/metrics')
      if (res.ok) {
        setData(await res.json())
        setLast(new Date())
      }
    } catch { /* keep stale data */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, POLL_MS)
    return () => clearInterval(id)
  }, [refresh])

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Nav */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center text-black font-bold text-sm">U</div>
          <span className="font-semibold text-white">UMIP Dashboard</span>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">Live · Arbitrum Sepolia</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          {loading && <span className="animate-pulse">Loading...</span>}
          {lastUpdated && (
            <span>Updated {lastUpdated.toLocaleTimeString()}</span>
          )}
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            Agent V1 vs V2 · Live Results
          </h1>
          <p className="text-gray-400">
            Two agents. Same strategy. Same thresholds. Only V2 uses UMIP.{' '}
            <span className="text-emerald-400">Period: {data.period}</span>
          </p>
        </div>

        {/* Metrics comparison */}
        <MetricsComparison v1={data.agent_v1} v2={data.agent_v2} improvement={data.improvement} />

        {/* Chart */}
        <UtilizationChart data={data.timeSeries} />

        {/* Lower grid: events + calculator */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <LiveEventsFeed events={data.recentEvents} />
          <OpportunityCostCalculator opportunityCostPct={data.improvement.opportunity_cost_saved_pct} />
        </div>

        {/* Architecture note */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <h3 className="text-red-400 font-semibold mb-3">Agent V1 — Fragmented</h3>
            <div className="space-y-2 text-sm text-gray-400">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                Separate wallets: GMX_USDC + GNS_USDC
              </div>
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                Capital locked on wrong platform
              </div>
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                Forced to trade suboptimal venue
              </div>
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                Loses {data.agent_v1.opportunity_cost_pct_sum.toFixed(4)}% to fragmentation
              </div>
            </div>
          </div>
          <div>
            <h3 className="text-emerald-400 font-semibold mb-3">Agent V2 — UMIP</h3>
            <div className="space-y-2 text-sm text-gray-400">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
                Single UMIPVault holds all collateral
              </div>
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
                Routes to any platform in one call
              </div>
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
                Always targets the best rate
              </div>
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
                0.0000% opportunity cost
              </div>
            </div>
          </div>
        </div>

        {/* CTA footer */}
        <div className="text-center space-y-4 pt-4">
          <p className="text-gray-400">Want to run your own agent on UMIP?</p>
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <a
              href="https://umip-sandbox-64jpcm1r7-simoncastelain-8080s-projects.vercel.app"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-semibold transition-colors text-sm"
            >
              Try the Sandbox →
            </a>
          </div>
          <p className="text-xs text-gray-600">Data from Arbitrum Sepolia · Updates every 60s</p>
        </div>
      </div>
    </div>
  )
}
