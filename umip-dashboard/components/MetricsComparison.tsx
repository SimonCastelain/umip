'use client'

import { AgentStats, Improvement } from '@/lib/data'

interface Props {
  v1: AgentStats
  v2: AgentStats
  improvement: Improvement
}

function StatRow({ label, v1, v2, v1Bad }: { label: string; v1: string; v2: string; v1Bad?: boolean }) {
  return (
    <div className="grid grid-cols-3 items-center gap-4 py-3 border-b border-gray-800 last:border-0">
      <span className="text-gray-400 text-sm">{label}</span>
      <span className={`font-mono font-semibold text-center ${v1Bad ? 'text-red-400' : 'text-gray-300'}`}>{v1}</span>
      <span className="font-mono font-semibold text-center text-emerald-400">{v2}</span>
    </div>
  )
}

export function MetricsComparison({ v1, v2, improvement }: Props) {
  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="grid grid-cols-3 gap-4 pb-3 border-b border-gray-700">
        <div />
        <div className="text-center">
          <div className="inline-flex items-center gap-1.5 bg-red-900/30 text-red-400 rounded-lg px-3 py-1.5">
            <div className="w-2 h-2 rounded-full bg-red-500" />
            <span className="text-sm font-semibold">Agent V1</span>
          </div>
          <p className="text-xs text-gray-500 mt-1">Fragmented wallets</p>
        </div>
        <div className="text-center">
          <div className="inline-flex items-center gap-1.5 bg-emerald-900/30 text-emerald-400 rounded-lg px-3 py-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-sm font-semibold">Agent V2</span>
          </div>
          <p className="text-xs text-gray-500 mt-1">UMIP vault</p>
        </div>
      </div>

      {/* Stats */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <StatRow
          label="Fragmentation Events"
          v1={v1.fragmentation_events.toString()}
          v2={v2.fragmentation_events.toString()}
          v1Bad={v1.fragmentation_events > 0}
        />
        <StatRow
          label="Missed Opportunities"
          v1={v1.missed_opportunities.toString()}
          v2="0"
          v1Bad={v1.missed_opportunities > 0}
        />
        <StatRow
          label="Opportunity Cost"
          v1={`${v1.opportunity_cost_pct_sum.toFixed(4)}%`}
          v2="0.0000%"
          v1Bad={v1.opportunity_cost_pct_sum > 0}
        />
        <StatRow
          label="Successful Executions"
          v1={(v1.executions ?? 0).toString()}
          v2={(v2.vault_opens ?? 0).toString()}
        />
        <StatRow
          label="Log Events"
          v1={v1.log_entries.toString()}
          v2={v2.log_entries.toString()}
        />
      </div>

      {/* Improvement callout */}
      <div className="bg-gradient-to-r from-emerald-900/40 to-blue-900/40 border border-emerald-800/40 rounded-2xl p-5">
        <p className="text-emerald-400 font-semibold mb-1">UMIP Advantage</p>
        <p className="text-gray-300 text-sm">{improvement.summary}</p>
        <div className="mt-3 grid grid-cols-2 gap-4">
          <div>
            <p className="text-2xl font-bold text-emerald-400">{improvement.fragmentation_events_eliminated}</p>
            <p className="text-xs text-gray-500">fragmentation events eliminated</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-emerald-400">{improvement.opportunity_cost_saved_pct.toFixed(4)}%</p>
            <p className="text-xs text-gray-500">opportunity cost saved</p>
          </div>
        </div>
      </div>
    </div>
  )
}
