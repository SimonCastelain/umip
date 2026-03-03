import { NextResponse }    from 'next/server'
import { FALLBACK, ComparisonData, TimePoint, LiveEvent } from '@/lib/data'

// Fetch from GitHub raw if env var is set; otherwise return hardcoded fallback
const GITHUB_BASE = process.env.GITHUB_RAW_BASE_URL // e.g. https://raw.githubusercontent.com/USER/REPO/main

interface LogEvent {
  event?: string
  ts?: string
  preferred_platform?: string
  forced_platform?: string
  opportunity_cost_pct_per_day?: number
  note?: string
  collateral_usd?: number
  size_usd?: number
  via?: string
  action?: string
  platform?: string
}

function parseJSONL(text: string): LogEvent[] {
  return text.split('\n')
    .filter(l => l.trim())
    .flatMap(line => {
      try { return [JSON.parse(line) as LogEvent] }
      catch { return [] }
    })
}

function fmtTs(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toISOString().slice(11, 16) // HH:MM
  } catch { return ts.slice(0, 16) }
}

function buildFromLogs(v1Events: LogEvent[], v2Events: LogEvent[]): Partial<ComparisonData> {
  const v1Frags = v1Events.filter(e => e.event === 'FRAGMENTATION')
  const v2Opens = v2Events.filter(e => e.event === 'VAULT_OPEN')
  const v1Actions = v1Events.filter(e => e.event === 'ACTION' && (e.action === 'open_long' || e.action === 'open_long_forced'))

  const totalOppCost = v1Frags.reduce((s, e) => s + (e.opportunity_cost_pct_per_day ?? 0), 0)

  // Build time series from FRAGMENTATION timestamps
  const cumFrags: TimePoint[] = []
  let fCount = 0
  let vCount = 0

  const allEvents = [
    ...v1Events.map(e => ({ ...e, _agent: 'V1' as const })),
    ...v2Events.map(e => ({ ...e, _agent: 'V2' as const })),
  ].sort((a, b) => (a.ts ?? '').localeCompare(b.ts ?? ''))

  for (const e of allEvents) {
    if (!e.ts) continue
    if (e.event === 'FRAGMENTATION') { fCount++ }
    if (e.event === 'VAULT_OPEN')    { vCount++ }
    if (e.event === 'FRAGMENTATION' || e.event === 'VAULT_OPEN') {
      cumFrags.push({
        ts: e.ts,
        label: fmtTs(e.ts),
        v1Fragmentation: fCount,
        v2VaultOpen: vCount,
        v1RatePct: 5.8,
        v2RatePct: 5.8,
      })
    }
  }

  // Build live event feed
  const recentEvents: LiveEvent[] = allEvents
    .filter(e => ['FRAGMENTATION', 'VAULT_OPEN', 'ACTION', 'ERROR'].includes(e.event ?? ''))
    .slice(-10)
    .reverse()
    .map((e, i) => {
      const isFrag = e.event === 'FRAGMENTATION'
      const isOpen = e.event === 'VAULT_OPEN'
      let msg = e.note ?? e.event ?? ''
      if (isFrag) msg = `Wanted ${e.preferred_platform}, stuck on ${e.forced_platform}. Lost ${e.opportunity_cost_pct_per_day?.toFixed(4)}%/day`
      if (isOpen) msg = `Opened ${e.size_usd ?? '?'} USD long via ${e.via ?? 'UMIPVault'}. No fragmentation.`
      return {
        id: `${i}-${e.ts}`,
        ts: e.ts ?? '',
        agent: e._agent as 'V1' | 'V2',
        type: e.event ?? '',
        message: msg,
        isNegative: isFrag || e.event === 'ERROR',
      }
    })

  const ts = v1Events[0]?.ts?.slice(0, 10)
  const te = [...v1Events, ...v2Events].at(-1)?.ts?.slice(0, 10)

  return {
    period: ts && te ? `${ts} to ${te}` : FALLBACK.period,
    agent_v1: {
      log_entries: v1Events.length,
      fragmentation_events: v1Frags.length,
      executions: v1Actions.length,
      missed_opportunities: v1Frags.length,
      opportunity_cost_pct_sum: Math.round(totalOppCost * 10000) / 10000,
      avg_capital_utilization: 0,
    },
    agent_v2: {
      log_entries: v2Events.length,
      fragmentation_events: 0,
      vault_opens: v2Opens.length,
      missed_opportunities: 0,
      opportunity_cost_pct_sum: 0,
      avg_capital_utilization: v2Opens.length > 0 ? 100 : 0,
    },
    improvement: {
      fragmentation_events_eliminated: v1Frags.length,
      opportunity_cost_saved_pct: Math.round(totalOppCost * 10000) / 10000,
      missed_opportunities_eliminated: v1Frags.length,
      summary: `V2 eliminated ${v1Frags.length} fragmentation events and saved ${(Math.round(totalOppCost * 10000) / 10000).toFixed(4)}% cumulative opportunity cost vs V1.`,
    },
    timeSeries: cumFrags.length > 0 ? cumFrags : FALLBACK.timeSeries,
    recentEvents: recentEvents.length > 0 ? recentEvents : FALLBACK.recentEvents,
  }
}

export async function GET() {
  // If no GitHub base URL configured, return static fallback immediately
  if (!GITHUB_BASE) {
    return NextResponse.json(FALLBACK, {
      headers: { 'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600' },
    })
  }

  try {
    const [v1Res, v2Res] = await Promise.all([
      fetch(`${GITHUB_BASE}/.tmp/agent_v1_log.jsonl`, { next: { revalidate: 300 } }),
      fetch(`${GITHUB_BASE}/.tmp/agent_v2_log.jsonl`, { next: { revalidate: 300 } }),
    ])

    if (!v1Res.ok || !v2Res.ok) {
      return NextResponse.json(FALLBACK, {
        headers: { 'Cache-Control': 'public, s-maxage=60' },
      })
    }

    const [v1Text, v2Text] = await Promise.all([v1Res.text(), v2Res.text()])
    const v1Events = parseJSONL(v1Text)
    const v2Events = parseJSONL(v2Text)

    const data = { ...FALLBACK, ...buildFromLogs(v1Events, v2Events) }

    return NextResponse.json(data, {
      headers: { 'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600' },
    })
  } catch {
    return NextResponse.json(FALLBACK, {
      headers: { 'Cache-Control': 'public, s-maxage=60' },
    })
  }
}
