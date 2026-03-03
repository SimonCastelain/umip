// Hardcoded fallback data from comparison/results.json (Feb 21-22 run)
// The API route will overlay this with live GitHub data if GITHUB_RAW_BASE_URL is set

export interface AgentStats {
  log_entries: number
  fragmentation_events: number
  executions?: number
  vault_opens?: number
  missed_opportunities: number
  opportunity_cost_pct_sum: number
  avg_capital_utilization: number
}

export interface Improvement {
  fragmentation_events_eliminated: number
  opportunity_cost_saved_pct: number
  missed_opportunities_eliminated: number
  summary: string
}

export interface ComparisonData {
  period: string
  agent_v1: AgentStats
  agent_v2: AgentStats
  improvement: Improvement
  timeSeries: TimePoint[]
  recentEvents: LiveEvent[]
}

export interface TimePoint {
  ts: string
  label: string
  v1Fragmentation: number
  v2VaultOpen: number
  v1RatePct: number
  v2RatePct: number
}

export interface LiveEvent {
  id: string
  ts: string
  agent: 'V1' | 'V2'
  type: string
  message: string
  isNegative: boolean
}

// Static fallback
export const FALLBACK: ComparisonData = {
  period: '2026-02-21 to 2026-02-22',
  agent_v1: {
    log_entries: 24,
    fragmentation_events: 4,
    executions: 2,
    missed_opportunities: 4,
    opportunity_cost_pct_sum: 0.2192,
    avg_capital_utilization: 0.0,
  },
  agent_v2: {
    log_entries: 5,
    fragmentation_events: 0,
    vault_opens: 1,
    missed_opportunities: 0,
    opportunity_cost_pct_sum: 0.0,
    avg_capital_utilization: 0.0,
  },
  improvement: {
    fragmentation_events_eliminated: 4,
    opportunity_cost_saved_pct: 0.2192,
    missed_opportunities_eliminated: 4,
    summary: 'V2 eliminated 4 fragmentation events and saved 0.2192% cumulative opportunity cost vs V1.',
  },
  timeSeries: [
    { ts: '2026-02-21T18:51', label: '18:51', v1Fragmentation: 0, v2VaultOpen: 0, v1RatePct: 5.8, v2RatePct: 5.8 },
    { ts: '2026-02-21T18:55', label: '18:55', v1Fragmentation: 1, v2VaultOpen: 0, v1RatePct: 5.8, v2RatePct: 5.8 },
    { ts: '2026-02-21T18:58', label: '18:58', v1Fragmentation: 2, v2VaultOpen: 0, v1RatePct: 5.8, v2RatePct: 5.8 },
    { ts: '2026-02-21T18:59', label: '18:59', v1Fragmentation: 3, v2VaultOpen: 0, v1RatePct: 5.8, v2RatePct: 5.8 },
    { ts: '2026-02-21T19:00', label: '19:00', v1Fragmentation: 4, v2VaultOpen: 0, v1RatePct: 5.8, v2RatePct: 5.8 },
    { ts: '2026-02-22T14:16', label: 'Next day', v1Fragmentation: 4, v2VaultOpen: 1, v1RatePct: 5.8, v2RatePct: 5.8 },
  ],
  recentEvents: [
    { id: 'e1', ts: '2026-02-22T14:16:10', agent: 'V2', type: 'VAULT_OPEN', message: 'Opened 50 USD long on GMX via UMIPVault. No fragmentation.', isNegative: false },
    { id: 'e2', ts: '2026-02-21T18:59:48', agent: 'V1', type: 'FRAGMENTATION', message: 'Wanted gTrade, stuck on GMX. Lost 0.0548%/day', isNegative: true },
    { id: 'e3', ts: '2026-02-21T18:58:27', agent: 'V1', type: 'FRAGMENTATION', message: 'Wanted gTrade, stuck on GMX. Lost 0.0548%/day', isNegative: true },
    { id: 'e4', ts: '2026-02-21T18:58:00', agent: 'V1', type: 'FRAGMENTATION', message: 'Wanted gTrade, stuck on GMX. Lost 0.0548%/day', isNegative: true },
    { id: 'e5', ts: '2026-02-21T18:55:11', agent: 'V1', type: 'FRAGMENTATION', message: 'Wanted gTrade, stuck on GMX. Lost 0.0548%/day', isNegative: true },
  ],
}
