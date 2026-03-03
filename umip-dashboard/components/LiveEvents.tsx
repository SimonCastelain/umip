'use client'

import { LiveEvent } from '@/lib/data'

interface Props { events: LiveEvent[] }

function fmtTime(ts: string) {
  try { return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) }
  catch { return ts.slice(11, 16) }
}

export function LiveEventsFeed({ events }: Props) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-white">Live Event Feed</h3>
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Live
        </div>
      </div>

      <div className="space-y-2 max-h-72 overflow-y-auto">
        {events.map((e) => (
          <div
            key={e.id}
            className={`flex items-start gap-3 p-3 rounded-xl text-sm ${
              e.isNegative ? 'bg-red-950/40 border border-red-900/30' : 'bg-emerald-950/40 border border-emerald-900/30'
            }`}
          >
            <div className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${e.isNegative ? 'bg-red-500' : 'bg-emerald-500'}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                  e.agent === 'V1' ? 'bg-red-900/60 text-red-400' : 'bg-emerald-900/60 text-emerald-400'
                }`}>{e.agent}</span>
                <span className="text-xs text-gray-500 font-mono">{e.type}</span>
                <span className="text-xs text-gray-600 ml-auto">{fmtTime(e.ts)}</span>
              </div>
              <p className={`text-xs leading-relaxed ${e.isNegative ? 'text-red-300' : 'text-emerald-300'}`}>{e.message}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
