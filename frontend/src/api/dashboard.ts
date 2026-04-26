import api from './client'

export interface CountyComparison {
  county: string
  leadCount: number
  avgGapPct: number
  totalSavings: number
}

export interface DashboardStats {
  totalLeads: number
  totalEstimatedSavings: number
  avgAppealProbability: number
  urgentDeadlines: number
  tierDistribution: Record<string, number>
  appealStatusCounts: Record<string, number>
  agencyFeesEstimate: number
  avgSavingsPerLead: number
  tierACount: number
  countyComparison: CountyComparison[]
}

function toCamel(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(toCamel)
  if (obj && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [
        k.replace(/_([a-z])/g, (_, c) => c.toUpperCase()),
        toCamel(v),
      ])
    )
  }
  return obj
}

export async function fetchDashboardStats(dataSource?: 'live' | 'generated'): Promise<DashboardStats> {
  const params: Record<string, string> = {}
  if (dataSource) params.data_source = dataSource
  const resp = await api.get('/dashboard/stats', { params })
  return toCamel(resp.data) as DashboardStats
}
