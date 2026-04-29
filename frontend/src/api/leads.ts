import api from './client'

export type PriorityTier = 'A' | 'B' | 'C' | 'D'

export interface LeadListItem {
  id: string
  propertyId: string
  assessmentId: string
  apn: string | null
  address: string
  city: string
  state: string
  countyName: string
  propertyType: string
  assessedTotal: number
  marketValueEst: number | null
  gapPct: number | null
  appealProbability: number | null
  estimatedSavings: number | null
  priorityTier: PriorityTier
  deadlineDate: string | null
  scoredAt: string
  isVerified: boolean
  verifiedBy: string | null
  verifiedAt: string | null
  hasContact: boolean
}

export interface LeadDetail extends LeadListItem {
  // Property details
  apn: string | null
  zip: string | null
  buildingSqft: number | null
  lotSizeSqft: number | null
  yearBuilt: number | null
  bedrooms: number | null
  bathrooms: number | null

  // Owner contact
  ownerName: string | null
  ownerEmail: string | null
  ownerPhone: string | null
  mailingAddress: string | null

  // Scoring details
  assessmentGap: number | null
  shapExplanation: Record<string, unknown> | null
  modelVersion: string | null

  // Related records
  comparableSales: ComparableSale[]
  assessmentHistory: AssessmentHistoryItem[]
}

export interface ComparableSale {
  id: string
  compApn: string
  salePrice: number
  saleDate: string
  sqft: number | null
  pricePerSqft: number | null
  distanceMiles: number | null
  similarityScore: number | null
}

export interface AssessmentHistoryItem {
  id: string
  taxYear: number
  assessedLand: number | null
  assessedImprovement: number | null
  assessedTotal: number
  taxAmount: number | null
  fetchedAt: string
}

export interface PaginatedLeads {
  total: number
  page: number
  pageSize: number
  items: LeadListItem[]
}

export interface LeadFilters {
  page?: number
  pageSize?: number
  tier?: PriorityTier[]
  countyId?: string
  propertyType?: string
  minGapPct?: number
  minEstimatedSavings?: number
  minAppealProbability?: number
  sortBy?: string
  sortDir?: 'asc' | 'desc'
  dataSource?: 'live' | 'generated'
}

function toSnake(key: string): string {
  return key.replace(/([A-Z])/g, '_$1').toLowerCase()
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

export async function fetchLeads(filters: LeadFilters = {}): Promise<PaginatedLeads> {
  const params: Record<string, unknown> = {}
  if (filters.page) params.page = filters.page
  if (filters.pageSize) params.page_size = filters.pageSize
  if (filters.tier?.length) params.tier = filters.tier
  if (filters.countyId) params.county_id = filters.countyId
  if (filters.propertyType) params.property_type = filters.propertyType
  if (filters.minGapPct != null) params.min_gap_pct = filters.minGapPct
  if (filters.minEstimatedSavings != null) params.min_estimated_savings = filters.minEstimatedSavings
  if (filters.minAppealProbability != null) params.min_appeal_probability = filters.minAppealProbability
  if (filters.sortBy) params.sort_by = toSnake(filters.sortBy)
  if (filters.sortDir) params.sort_dir = filters.sortDir
  if (filters.dataSource) params.data_source = filters.dataSource

  const resp = await api.get('/leads', { params })
  return toCamel(resp.data) as PaginatedLeads
}

export async function fetchLead(id: string): Promise<LeadDetail> {
  const resp = await api.get(`/leads/${id}`)
  return toCamel(resp.data) as LeadDetail
}

export async function assignLead(id: string, agent: string): Promise<void> {
  await api.post(`/leads/${id}/assign`, { assigned_agent: agent })
}

export async function verifyLead(id: string, verifiedBy: string): Promise<void> {
  await api.post(`/leads/${id}/verify`, { verified_by: verifiedBy })
}

export async function unverifyLead(id: string): Promise<void> {
  await api.post(`/leads/${id}/unverify`)
}
