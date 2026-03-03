'use client'

import { TimePoint } from '@/lib/data'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

interface Props { data: TimePoint[] }

export function UtilizationChart({ data }: Props) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
      <h3 className="font-semibold text-white mb-1">Cumulative Fragmentation Events Over Time</h3>
      <p className="text-xs text-gray-500 mb-6">V1 accumulates fragmentation; V2 stays at zero</p>

      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="label" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
          <Tooltip
            contentStyle={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '12px', color: '#f9fafb' }}
            itemStyle={{ color: '#d1d5db' }}
          />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 16 }} />
          <Line
            type="stepAfter"
            dataKey="v1Fragmentation"
            name="V1 — Fragmentation Events"
            stroke="#ef4444"
            strokeWidth={2}
            dot={{ fill: '#ef4444', r: 4 }}
            activeDot={{ r: 6 }}
          />
          <Line
            type="stepAfter"
            dataKey="v2VaultOpen"
            name="V2 — Vault Opens (UMIP)"
            stroke="#10b981"
            strokeWidth={2}
            dot={{ fill: '#10b981', r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
