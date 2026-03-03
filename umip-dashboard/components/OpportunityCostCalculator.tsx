'use client'

import { useState } from 'react'

interface Props { opportunityCostPct: number }

export function OpportunityCostCalculator({ opportunityCostPct }: Props) {
  const [aum, setAum] = useState('100000')

  const aumNum = parseFloat(aum.replace(/[^0-9.]/g, '')) || 0
  const costPerPeriod = (aumNum * opportunityCostPct) / 100
  const annualized    = costPerPeriod * 365

  return (
    <div className="bg-gradient-to-br from-red-950/60 to-orange-950/40 border border-red-900/30 rounded-2xl p-6 space-y-4">
      <div>
        <h3 className="font-semibold text-white mb-1">Opportunity Cost Calculator</h3>
        <p className="text-xs text-gray-400">Based on observed {opportunityCostPct.toFixed(4)}% cumulative loss rate on Agent V1</p>
      </div>

      <div>
        <label className="text-xs text-gray-400 mb-1 block">Your agent's AUM</label>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
          <input
            type="text"
            value={aum}
            onChange={(e) => setAum(e.target.value)}
            className="w-full bg-gray-900/60 border border-gray-700 rounded-xl pl-8 pr-4 py-3 text-white focus:outline-none focus:border-red-500 transition-colors"
            placeholder="100000"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 pt-2">
        <div className="bg-red-900/30 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-1">Lost to fragmentation</p>
          <p className="text-2xl font-bold text-red-400">
            ${costPerPeriod.toLocaleString('en-US', { maximumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-gray-500 mt-1">this period (V1)</p>
        </div>
        <div className="bg-emerald-900/30 rounded-xl p-4">
          <p className="text-xs text-gray-400 mb-1">With UMIP (V2)</p>
          <p className="text-2xl font-bold text-emerald-400">$0.00</p>
          <p className="text-xs text-gray-500 mt-1">zero fragmentation</p>
        </div>
      </div>

      <div className="border-t border-gray-800 pt-4">
        <p className="text-xs text-gray-500">Annualized projection at current rate:</p>
        <p className="text-lg font-bold text-red-300">
          ${annualized.toLocaleString('en-US', { maximumFractionDigits: 0 })} lost/year without UMIP
        </p>
      </div>
    </div>
  )
}
