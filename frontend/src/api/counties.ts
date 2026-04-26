import api from './client'

export interface County {
  id: string
  name: string
  state: string
  portalUrl: string
  scraperAdapter: string
  appealDeadlineDays: number
  approvalRateHist: number | null
  lastScrapedAt: string | null
  leadCount: number
  propertyCount: number
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

export async function fetchCounties(): Promise<County[]> {
  const resp = await api.get('/counties')
  return toCamel(resp.data) as County[]
}
