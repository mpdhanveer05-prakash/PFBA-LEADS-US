import api from './client'

export interface OutreachCampaign {
  id: string
  leadScoreId: string
  propertyId: string
  status: 'DRAFT' | 'SENT' | 'OPENED' | 'RESPONDED' | 'OPTED_OUT'
  channel: string
  recipientEmail: string | null
  recipientPhone: string | null
  subject: string | null
  body: string | null
  sentAt: string | null
  openedAt: string | null
  respondedAt: string | null
  createdAt: string
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

export async function generateCampaign(leadScoreId: string): Promise<OutreachCampaign> {
  const resp = await api.post(`/outreach/generate/${leadScoreId}`)
  return toCamel(resp.data) as OutreachCampaign
}

export async function listCampaigns(leadScoreId?: string, status?: string): Promise<OutreachCampaign[]> {
  const params: Record<string, string> = {}
  if (leadScoreId) params.lead_score_id = leadScoreId
  if (status) params.status = status
  const resp = await api.get('/outreach/campaigns', { params })
  return toCamel(resp.data) as OutreachCampaign[]
}

export async function sendCampaign(campaignId: string): Promise<OutreachCampaign> {
  const resp = await api.post(`/outreach/campaigns/${campaignId}/send`)
  return toCamel(resp.data) as OutreachCampaign
}

export async function updateCampaignStatus(campaignId: string, status: string): Promise<OutreachCampaign> {
  const resp = await api.patch(`/outreach/campaigns/${campaignId}/status`, { status })
  return toCamel(resp.data) as OutreachCampaign
}
