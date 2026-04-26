import { useEffect, useState, useCallback, useRef } from 'react'
import api from '../api/client'
import {
  triggerSync, fetchSyncJobs, updateCountySchedule,
  type SyncJob, type SyncStatus,
} from '../api/sync'
import { useAuth } from '../hooks/useAuth'

interface County {
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

const INTERVAL_OPTIONS = [
  { value: 1, label: 'Every hour' },
  { value: 6, label: 'Every 6 hours' },
  { value: 12, label: 'Every 12 hours' },
  { value: 24, label: 'Daily' },
  { value: 48, label: 'Every 2 days' },
  { value: 168, label: 'Weekly' },
]

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

function StatusBadge({ status }: { status: SyncStatus | 'NEVER' }) {
  const map: Record<string, { cls: string; label: string }> = {
    NEVER:     { cls: 'bg-gray-100 text-gray-500', label: 'Never synced' },
    PENDING:   { cls: 'bg-yellow-100 text-yellow-700', label: '⏳ Queued' },
    RUNNING:   { cls: 'bg-blue-100 text-blue-700 animate-pulse', label: '⟳ Running' },
    COMPLETED: { cls: 'bg-green-100 text-green-700', label: '✓ Done' },
    FAILED:    { cls: 'bg-red-100 text-red-700', label: '✕ Failed' },
  }
  const { cls, label } = map[status] ?? map.NEVER
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>{label}</span>
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function timeUntil(iso: string | null): string {
  if (!iso) return '—'
  const diff = new Date(iso).getTime() - Date.now()
  if (diff <= 0) return 'Overdue'
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `in ${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `in ${hrs}h`
  return `in ${Math.floor(hrs / 24)}d`
}

function duration(job: SyncJob): string {
  if (!job.completedAt) {
    const secs = Math.floor((Date.now() - new Date(job.startedAt).getTime()) / 1000)
    return `${secs}s`
  }
  const secs = Math.floor((new Date(job.completedAt).getTime() - new Date(job.startedAt).getTime()) / 1000)
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

export default function SyncCenterPage() {
  const { user } = useAuth()
  const [counties, setCounties] = useState<County[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [leadCount, setLeadCount] = useState(20)
  const [syncing, setSyncing] = useState(false)
  const [jobs, setJobs] = useState<SyncJob[]>([])
  const [scheduleUpdating, setScheduleUpdating] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadCounties = useCallback(async () => {
    const resp = await api.get('/counties', { params: { include_stats: true } })
    setCounties(toCamel(resp.data) as County[])
  }, [])

  const loadJobs = useCallback(async () => {
    const data = await fetchSyncJobs()
    setJobs(data)
  }, [])

  useEffect(() => {
    loadCounties()
    loadJobs()
  }, [loadCounties, loadJobs])

  // Poll every 3 seconds while any job is active
  useEffect(() => {
    const hasActive = jobs.some(j => j.status === 'PENDING' || j.status === 'RUNNING')
    if (hasActive && !pollingRef.current) {
      pollingRef.current = setInterval(async () => {
        const data = await fetchSyncJobs()
        setJobs(data)
        const stillActive = data.some(j => j.status === 'PENDING' || j.status === 'RUNNING')
        if (!stillActive) {
          clearInterval(pollingRef.current!)
          pollingRef.current = null
          loadCounties()
        }
      }, 3000)
    }
    return () => {
      if (!hasActive && pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }
  }, [jobs, loadCounties])

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleAll() {
    if (selected.size === counties.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(counties.map(c => c.id)))
    }
  }

  async function handleSyncNow() {
    if (!selected.size) return
    setSyncing(true)
    try {
      await triggerSync([...selected], leadCount, user?.username)
      await loadJobs()
    } finally {
      setSyncing(false)
    }
  }

  async function handleScheduleChange(county: County, field: 'interval' | 'auto', value: number | boolean) {
    setScheduleUpdating(county.id)
    try {
      const interval = field === 'interval' ? (value as number) : county.syncIntervalHours
      const auto = field === 'auto' ? (value as boolean) : county.autoSyncEnabled
      await updateCountySchedule(county.id, interval, auto)
      await loadCounties()
    } finally {
      setScheduleUpdating(null)
    }
  }

  // Map county id → latest job status
  const latestJobByCounty = jobs.reduce<Record<string, SyncJob>>((acc, j) => {
    if (!acc[j.countyId] || new Date(j.startedAt) > new Date(acc[j.countyId].startedAt)) {
      acc[j.countyId] = j
    }
    return acc
  }, {})

  const activeJobs = jobs.filter(j => j.status === 'PENDING' || j.status === 'RUNNING')
  const recentJobs = jobs.slice(0, 30)

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Sync Center</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Trigger real-time syncs for selected counties and manage automatic schedules.
        </p>
      </div>

      {/* Action bar */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm px-5 py-4 flex items-center gap-4 flex-wrap">
        <span className="text-sm font-medium text-gray-700">
          {selected.size > 0 ? `${selected.size} counti${selected.size > 1 ? 'es' : 'y'} selected` : 'Select counties to sync'}
        </span>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500">Leads per county:</label>
          <input
            type="number"
            min={1}
            max={10000}
            step={50}
            value={leadCount}
            onChange={e => setLeadCount(Math.max(1, Math.min(10000, Number(e.target.value))))}
            className="w-24 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-xs text-gray-400">(1 – 10,000, default 20)</span>
        </div>
        <button
          onClick={handleSyncNow}
          disabled={!selected.size || syncing}
          className="ml-auto px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg disabled:opacity-40 transition-colors flex items-center gap-2"
        >
          {syncing ? '⟳ Queuing...' : `⟳ Sync Now${selected.size ? ` (${selected.size})` : ''}`}
        </button>
        {activeJobs.length > 0 && (
          <span className="text-xs font-medium text-blue-600 bg-blue-50 px-3 py-1.5 rounded-lg animate-pulse">
            {activeJobs.length} sync{activeJobs.length > 1 ? 's' : ''} running
          </span>
        )}
      </div>

      <div className="grid grid-cols-5 gap-6">
        {/* Counties table — 3 cols */}
        <div className="col-span-3 bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-3">
            <h2 className="text-sm font-semibold text-gray-700 flex-1">Counties</h2>
            <button onClick={toggleAll} className="text-xs text-blue-600 hover:underline">
              {selected.size === counties.length ? 'Deselect all' : 'Select all'}
            </button>
          </div>
          <div className="overflow-auto max-h-[calc(100vh-280px)]">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="w-8 px-3 py-2"></th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">County</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Status</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Last Sync</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Next</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Schedule</th>
                  <th className="px-3 py-2 text-center text-xs font-semibold text-gray-500 uppercase">Auto</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {counties.map(county => {
                  const job = latestJobByCounty[county.id]
                  const statusVal: SyncStatus | 'NEVER' = job ? job.status : 'NEVER'
                  const isUpdating = scheduleUpdating === county.id
                  return (
                    <tr
                      key={county.id}
                      className={`hover:bg-gray-50 cursor-pointer ${selected.has(county.id) ? 'bg-blue-50' : ''}`}
                      onClick={() => toggleSelect(county.id)}
                    >
                      <td className="px-3 py-2.5" onClick={e => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selected.has(county.id)}
                          onChange={() => toggleSelect(county.id)}
                          className="rounded border-gray-300 text-blue-600"
                        />
                      </td>
                      <td className="px-3 py-2.5">
                        <p className="font-medium text-gray-900">{county.name}</p>
                        <p className="text-xs text-gray-400">{county.state} · {county.leadCount ?? 0} leads</p>
                      </td>
                      <td className="px-3 py-2.5">
                        <StatusBadge status={statusVal} />
                      </td>
                      <td className="px-3 py-2.5 text-xs text-gray-500">{timeAgo(county.lastScrapedAt)}</td>
                      <td className="px-3 py-2.5 text-xs text-gray-500">{county.autoSyncEnabled ? timeUntil(county.nextSyncAt) : '—'}</td>
                      <td className="px-3 py-2.5" onClick={e => e.stopPropagation()}>
                        <select
                          value={county.syncIntervalHours}
                          disabled={isUpdating}
                          onChange={e => handleScheduleChange(county, 'interval', Number(e.target.value))}
                          className="text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:opacity-40"
                        >
                          {INTERVAL_OPTIONS.map(o => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-2.5 text-center" onClick={e => e.stopPropagation()}>
                        <button
                          disabled={isUpdating}
                          onClick={() => handleScheduleChange(county, 'auto', !county.autoSyncEnabled)}
                          className={`w-10 h-5 rounded-full transition-colors ${county.autoSyncEnabled ? 'bg-blue-600' : 'bg-gray-200'} disabled:opacity-40 relative`}
                        >
                          <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${county.autoSyncEnabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Sync jobs feed — 2 cols */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden flex flex-col">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">Sync Feed</h2>
            {activeJobs.length > 0 && (
              <span className="text-xs text-blue-500 animate-pulse">● Live</span>
            )}
          </div>
          <div className="overflow-auto flex-1 max-h-[calc(100vh-280px)]">
            {recentJobs.length === 0 ? (
              <div className="px-5 py-10 text-center text-gray-400 text-sm">
                No sync jobs yet. Select counties and click Sync Now.
              </div>
            ) : (
              <div className="divide-y divide-gray-50">
                {recentJobs.map(job => (
                  <div key={job.id} className="px-5 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{job.countyName}</p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {job.syncType === 'SCHEDULED' ? '⏱ Scheduled' : '▶ Manual'}
                          {job.triggeredBy ? ` · by ${job.triggeredBy}` : ''}
                        </p>
                      </div>
                      <StatusBadge status={job.status} />
                    </div>

                    {(job.status === 'RUNNING' || job.status === 'COMPLETED') && (
                      <div className="mt-2 space-y-1">
                        <div className="flex justify-between text-xs text-gray-500">
                          <span>Seeded</span>
                          <span className="font-medium">{job.recordsSeeded.toLocaleString()} / {job.leadCount.toLocaleString()}</span>
                        </div>
                        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${job.status === 'COMPLETED' ? 'bg-green-500' : 'bg-blue-500'}`}
                            style={{ width: `${Math.min(100, (job.recordsSeeded / job.leadCount) * 100)}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-xs text-gray-400">
                          <span>{job.recordsScored.toLocaleString()} leads scored</span>
                          <span>{duration(job)}</span>
                        </div>
                      </div>
                    )}

                    {job.status === 'PENDING' && (
                      <p className="mt-1 text-xs text-yellow-600">Waiting to start...</p>
                    )}

                    {job.status === 'COMPLETED' && (
                      job.errorMessage?.includes('[seed]')
                        ? <span className="mt-1 inline-block text-xs bg-orange-100 text-orange-700 rounded px-2 py-0.5">⚠ Generated data (scraper unavailable)</span>
                        : <span className="mt-1 inline-block text-xs bg-green-100 text-green-700 rounded px-2 py-0.5">✓ Live county data</span>
                    )}
                    {job.status === 'FAILED' && job.errorMessage && (
                      <p className="mt-1 text-xs text-red-600 bg-red-50 rounded px-2 py-1 truncate">{job.errorMessage.replace('[seed] real scraper unavailable', '').replace(' | ', '')}</p>
                    )}

                    <p className="mt-1 text-xs text-gray-300">{timeAgo(job.startedAt)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
