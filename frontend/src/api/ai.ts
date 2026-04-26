import api from './client'

export interface NLSearchResult {
  tier?: string[]
  countyId?: string
  propertyType?: string
  minGapPct?: number
  minEstimatedSavings?: number
  minAppealProbability?: number
  sortBy?: string
  sortDir?: 'asc' | 'desc'
  interpretation?: string
}

export interface MapLead {
  id: string
  address: string
  city: string
  state: string
  lat: number
  lng: number
  tier: string
  probability: number | null
  savings: number
  gapPct: number | null
  countyName: string
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

export async function generateLetter(leadId: string): Promise<string> {
  const resp = await api.post(`/ai/generate-letter/${leadId}`)
  return resp.data.letter as string
}

export async function nlSearch(query: string): Promise<NLSearchResult> {
  const resp = await api.post('/ai/nl-search', { query })
  return toCamel(resp.data) as NLSearchResult
}

export async function bulkLetters(leadIds: string[]): Promise<Blob> {
  const resp = await api.post('/ai/bulk-letters', { lead_ids: leadIds }, { responseType: 'blob' })
  return resp.data as Blob
}

export async function fetchMapLeads(tier?: string[], countyId?: string, dataSource?: 'live' | 'generated'): Promise<MapLead[]> {
  const params: Record<string, unknown> = {}
  if (tier?.length) params.tier = tier
  if (countyId) params.county_id = countyId
  if (dataSource) params.data_source = dataSource
  const resp = await api.get('/leads/map', { params })
  return toCamel(resp.data) as MapLead[]
}
