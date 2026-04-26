import api from './client'

export type SyncStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
export type SyncType = 'MANUAL' | 'SCHEDULED'

export interface SyncJob {
  id: string
  countyId: string
  countyName: string
  syncType: SyncType
  status: SyncStatus
  triggeredBy: string | null
  leadCount: number
  recordsSeeded: number
  recordsScored: number
  errorMessage: string | null
  startedAt: string
  completedAt: string | null
}

export interface CountyWithSchedule {
  id: string
  name: string
  state: string
  lastScrapedAt: string | null
  syncIntervalHours: number
  autoSyncEnabled: boolean
  nextSyncAt: string | null
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

export async function triggerSync(
  countyIds: string[],
  count: number,
  triggeredBy?: string
): Promise<{ jobs: { jobId: string; countyName: string; countyId: string }[] }> {
  const resp = await api.post('/sync/trigger', {
    county_ids: countyIds,
    count,
    triggered_by: triggeredBy ?? null,
  })
  return toCamel(resp.data) as any
}

export async function fetchSyncJobs(countyId?: string, status?: SyncStatus): Promise<SyncJob[]> {
  const params: Record<string, unknown> = { limit: 100 }
  if (countyId) params.county_id = countyId
  if (status) params.status = status
  const resp = await api.get('/sync/jobs', { params })
  return toCamel(resp.data) as SyncJob[]
}

export async function fetchSyncJob(jobId: string): Promise<SyncJob> {
  const resp = await api.get(`/sync/jobs/${jobId}`)
  return toCamel(resp.data) as SyncJob
}

export async function updateCountySchedule(
  countyId: string,
  syncIntervalHours: number,
  autoSyncEnabled: boolean
): Promise<void> {
  await api.put(`/counties/${countyId}/schedule`, {
    sync_interval_hours: syncIntervalHours,
    auto_sync_enabled: autoSyncEnabled,
  })
}
