import api from './client'

export interface AppealPacket {
  id: string
  leadScoreId: string
  propertyId: string
  countyId: string
  s3Key: string | null
  generatedAt: string
  claimedValue: number | null
  evidenceComps: number | null
  status: 'DRAFT' | 'READY' | 'FILED'
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

export async function generatePacket(leadScoreId: string): Promise<AppealPacket> {
  const resp = await api.post(`/packets/generate/${leadScoreId}`)
  return toCamel(resp.data) as AppealPacket
}

export async function listPackets(leadScoreId?: string): Promise<AppealPacket[]> {
  const params: Record<string, string> = {}
  if (leadScoreId) params.lead_score_id = leadScoreId
  const resp = await api.get('/packets', { params })
  return toCamel(resp.data) as AppealPacket[]
}

export async function downloadPacket(packetId: string): Promise<void> {
  const resp = await api.get(`/packets/${packetId}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `appeal_packet_${packetId.slice(0, 8)}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}
