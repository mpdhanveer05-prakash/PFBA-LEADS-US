import api from './client'

export interface DncMatchPreview {
  entryId: string
  rawName: string | null
  rawEmail: string | null
  rawPhone: string | null
  rawAddress: string | null
  rawApn: string | null
  matchedApn: string
  matchedAddress: string
  matchedCity: string
  matchedState: string
  matchedOwner: string | null
  matchReason: string
  propertyId: string
}

export interface DncUploadResult {
  listId: string
  filename: string
  fileType: string
  totalRecords: number
  matchedCount: number
  status: string
  matches: DncMatchPreview[]
}

export interface DncList {
  id: string
  filename: string
  fileType: string
  status: string
  uploadedBy: string
  totalRecords: number
  matchedCount: number
  uploadedAt: string
}

export interface DncEntry {
  id: string
  rawName: string | null
  rawEmail: string | null
  rawPhone: string | null
  rawAddress: string | null
  rawApn: string | null
  matchedPropertyId: string | null
  matchReason: string | null
  matchedAddress: string | null
  matchedCity: string | null
  matchedState: string | null
  isDncApplied: boolean
}

export interface DncProperty {
  id: string
  apn: string
  address: string
  city: string
  state: string
  ownerName: string | null
  dncAt: string | null
  dncListId: string | null
  dncSource: string | null
}

export interface DncStats {
  totalDncProperties: number
  totalLists: number
  appliedLists: number
}

function snakeToCamel(obj: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(obj)) {
    const camel = k.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
    out[camel] = v
  }
  return out
}

export async function uploadDncFile(file: File): Promise<DncUploadResult> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/dnc/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return {
    listId: data.list_id,
    filename: data.filename,
    fileType: data.file_type,
    totalRecords: data.total_records,
    matchedCount: data.matched_count,
    status: data.status,
    matches: (data.matches ?? []).map((m: Record<string, unknown>) =>
      snakeToCamel(m) as unknown as DncMatchPreview
    ),
  }
}

export async function applyDncList(listId: string): Promise<{ applied: number }> {
  const { data } = await api.post(`/dnc/lists/${listId}/apply`)
  return data
}

export async function fetchDncLists(): Promise<DncList[]> {
  const { data } = await api.get('/dnc/lists')
  return (data as Record<string, unknown>[]).map(
    (r) => snakeToCamel(r) as unknown as DncList
  )
}

export async function fetchDncEntries(listId: string): Promise<DncEntry[]> {
  const { data } = await api.get(`/dnc/lists/${listId}/entries`)
  return (data as Record<string, unknown>[]).map(
    (r) => snakeToCamel(r) as unknown as DncEntry
  )
}

export async function fetchDncProperties(): Promise<DncProperty[]> {
  const { data } = await api.get('/dnc/properties')
  return (data as Record<string, unknown>[]).map(
    (r) => snakeToCamel(r) as unknown as DncProperty
  )
}

export async function removeDncProperty(propertyId: string): Promise<void> {
  await api.delete(`/dnc/properties/${propertyId}`)
}

export async function deleteDncList(listId: string, unapply = true): Promise<void> {
  await api.delete(`/dnc/lists/${listId}`, { params: { unapply } })
}

export async function fetchDncStats(): Promise<DncStats> {
  const { data } = await api.get('/dnc/stats')
  return snakeToCamel(data) as unknown as DncStats
}
