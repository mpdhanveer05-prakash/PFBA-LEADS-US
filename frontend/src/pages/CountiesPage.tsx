import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchCounties, type County } from '../api/counties'
import { triggerScoring } from '../api/operations'
import { triggerSync, fetchSyncJobs, type SyncJob } from '../api/sync'
import AddCountyModal from '../components/AddCountyModal'

const REAL_SCRAPERS = new Set([
  // Texas
  'travis_tx', 'harris_tx', 'dallas_tx', 'tarrant_tx', 'bexar_tx',
  'collin_tx', 'denton_tx', 'williamson_tx', 'montgomery_tx',
  // Florida
  'miami_dade_fl', 'broward_fl', 'palm_beach_fl', 'hillsborough_fl', 'orange_fl', 'pinellas_fl',
  // California
  'san_diego_ca', 'los_angeles_ca', 'orange_ca', 'riverside_ca', 'santa_clara_ca',
  // Other states
  'cook_il', 'king_wa', 'maricopa_az', 'clark_nv', 'fulton_ga', 'mecklenburg_nc', 'wake_nc',
  // Socrata verified
  'ny_nyc', 'ca_sf', 'pa_philly',
])

const SEC_PER_RECORD: Record<string, number> = {
  travis_tx: 2.5, harris_tx: 3.0, miami_dade_fl: 2.0, san_diego_ca: 1.2,
}

// ── Circular SVG progress ring ─────────────────────────────────────────────
function ProgressRing({ pct, size = 48 }: { pct: number; size?: number }) {
  const r = (size - 8) / 2
  const circ = 2 * Math.PI * r
  const dash = Math.min(pct / 100, 1) * circ
  const color = pct >= 100 ? '#16a34a' : '#3b82f6'
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="flex-shrink-0">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#e5e7eb" strokeWidth="4" />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: 'stroke-dasharray 0.8s ease' }}
      />
      <text x={size/2} y={size/2+4} textAnchor="middle" fontSize="11" fontWeight="bold" fill={color}>
        {pct >= 100 ? '✓' : `${Math.round(pct)}%`}
      </text>
    </svg>
  )
}

// ── Progress card — only shown for jobs triggered in this page session ─────
function SyncProgressCard({ job, scraperAdapter, onDone }: {
  job: SyncJob; scraperAdapter: string; onDone: () => void
}) {
  const [elapsed, setElapsed] = useState(0)
  const startMs = useRef(new Date(job.startedAt).getTime())
  const firedRef = useRef(false)

  const secPerRecord = SEC_PER_RECORD[scraperAdapter] ?? 2.5
  const estimatedSecs = (job.leadCount || 200) * secPerRecord
  const isCompleted = job.status === 'COMPLETED' || job.status === 'FAILED'

  // Tick elapsed time every 500 ms while running
  useEffect(() => {
    if (isCompleted) return
    const t = setInterval(() => setElapsed(Date.now() - startMs.current), 500)
    return () => clearInterval(t)
  }, [isCompleted])

  // Call onDone exactly once when job finishes
  useEffect(() => {
    if (isCompleted && !firedRef.current) {
      firedRef.current = true
      setTimeout(onDone, 1200)
    }
  }, [isCompleted, onDone])

  const pct = isCompleted ? 100
    : job.recordsSeeded > 0 ? Math.min((job.recordsSeeded / job.leadCount) * 100, 98)
    : Math.min((elapsed / 1000 / estimatedSecs) * 100, 95)

  const remaining = Math.max(0, estimatedSecs - elapsed / 1000)
  const remainingStr = remaining > 60 ? `~${Math.ceil(remaining / 60)} min left`
    : remaining > 5 ? `~${Math.ceil(remaining)}s left`
    : 'Almost done…'

  const bg = job.status === 'FAILED' ? 'bg-red-50 border-red-200'
    : isCompleted ? 'bg-green-50 border-green-200'
    : 'bg-blue-50 border-blue-200'
  const barColor = job.status === 'FAILED' ? 'bg-red-500' : isCompleted ? 'bg-green-500' : 'bg-blue-500'

  return (
    <div className={`flex items-center gap-3 p-2.5 rounded-xl border mt-2 ${bg}`}>
      <ProgressRing pct={pct} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-xs font-semibold text-gray-800">
            {job.status === 'FAILED' ? 'Scraper failed'
              : isCompleted ? 'Complete'
              : job.status === 'PENDING' ? 'Queued…'
              : 'Scraping…'}
          </span>
          {!isCompleted && job.status === 'RUNNING' && (
            <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" />
          )}
        </div>
        <div className="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div className={`h-1.5 rounded-full ${barColor}`}
            style={{ width: `${pct}%`, transition: 'width 0.8s ease' }} />
        </div>
        <div className="flex justify-between mt-1 text-xs text-gray-500">
          <span>
            {job.recordsSeeded > 0
              ? `${job.recordsSeeded} / ${job.leadCount} records`
              : `Up to ${job.leadCount} records`}
          </span>
          <span>
            {job.status === 'FAILED' ? (job.errorMessage?.slice(0, 40) ?? 'Error')
              : isCompleted ? `${job.recordsScored} leads scored`
              : remainingStr}
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function CountiesPage() {
  const navigate = useNavigate()
  const [counties, setCounties] = useState<County[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)   // countyId or 'all' or 'score'
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)
  // Only track jobs triggered in this session (by job ID)
  const [sessionJobIds, setSessionJobIds] = useState<Set<string>>(new Set())
  // Latest sync job per county (from polling)
  const [syncJobs, setSyncJobs] = useState<Record<string, SyncJob>>({})

  // Initial load — shows spinner once
  useEffect(() => {
    fetchCounties()
      .then(setCounties)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  // Silent background refresh — no loading flash
  const silentRefresh = useCallback(() => {
    fetchCounties().then(setCounties).catch(console.error)
  }, [])

  // Poll sync jobs every 5s — only update state if something actually changed
  const prevJobsRef = useRef<string>('')
  useEffect(() => {
    const poll = async () => {
      try {
        const jobs = await fetchSyncJobs()
        const map: Record<string, SyncJob> = {}
        for (const j of jobs) {
          if (!map[j.countyId] || new Date(j.startedAt) > new Date(map[j.countyId].startedAt)) {
            map[j.countyId] = j
          }
        }
        // Only update state if something changed (avoids unnecessary re-renders)
        const fingerprint = JSON.stringify(
          Object.values(map).map(j => `${j.id}:${j.status}:${j.recordsSeeded}:${j.recordsScored}`)
        )
        if (fingerprint !== prevJobsRef.current) {
          prevJobsRef.current = fingerprint
          setSyncJobs(map)
        }
      } catch { /* ignore */ }
    }
    poll()
    const t = setInterval(poll, 5000)
    return () => clearInterval(t)
  }, [])

  function showToast(msg: string, ok = true) {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 6000)
  }

  async function handleScrape(county: County) {
    setBusy(county.id)
    try {
      const result = await triggerSync([county.id], 200)
      showToast(`Scraper started for ${county.name}.`)
      const jobId = result.jobs?.[0]?.jobId
      if (jobId) {
        setSessionJobIds(prev => new Set([...prev, jobId]))
        // Fetch the newly created job immediately so the card shows PENDING/RUNNING
        const jobs = await fetchSyncJobs()
        const newJob = jobs.find(j => j.id === jobId)
        if (newJob) setSyncJobs(prev => ({ ...prev, [county.id]: newJob }))
      }
    } catch {
      showToast(`Failed to start scraper for ${county.name}`, false)
    } finally {
      setBusy(null)
    }
  }

  async function handleSyncAll() {
    setBusy('all')
    try {
      const realCounties = counties.filter(c => REAL_SCRAPERS.has(c.scraperAdapter))
      if (!realCounties.length) { showToast('No live-scraper counties found', false); return }
      const result = await triggerSync(realCounties.map(c => c.id), 200)
      const jobList: { jobId?: string; id?: string; countyId?: string }[] =
        Array.isArray(result) ? result : (result as any).jobs ?? []
      const newIds = new Set(jobList.map(j => j.jobId ?? j.id ?? '').filter(Boolean))
      setSessionJobIds(prev => new Set([...prev, ...newIds]))
      showToast(`Sync started for ${realCounties.length} counties.`)
    } catch {
      showToast('Failed to start sync', false)
    } finally {
      setBusy(null)
    }
  }

  async function handleScoreAll() {
    setBusy('score')
    try {
      await triggerScoring(undefined, true)  // force=true re-scores all, including existing tier-D
      // Navigate to Leads page immediately; it will poll until scoring finishes
      navigate('/leads?scoring=1')
    } catch {
      showToast('Failed to queue scoring', false)
      setBusy(null)
    }
  }

  const realCount = counties.filter(c => REAL_SCRAPERS.has(c.scraperAdapter)).length

  return (
    <div className="p-6">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium text-white max-w-sm ${toast.ok ? 'bg-green-600' : 'bg-red-600'}`}>
          {toast.msg}
        </div>
      )}

      {showAddModal && (
        <AddCountyModal
          onClose={() => setShowAddModal(false)}
          onCreated={() => { setShowAddModal(false); fetchCounties().then(setCounties).catch(console.error) }}
        />
      )}

      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Counties</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {realCount} of {counties.length} counties have live scrapers
          </p>
        </div>
        <div className="flex gap-3">
          <button onClick={handleSyncAll} disabled={!!busy}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg disabled:opacity-50 flex items-center gap-2">
            {busy === 'all'
              ? <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Syncing…</>
              : '⬇ Sync All Counties'}
          </button>
          <button onClick={handleScoreAll} disabled={!!busy}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-semibold rounded-lg disabled:opacity-50 flex items-center gap-2">
            {busy === 'score'
              ? <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Queuing…</>
              : '⚡ Score All Leads'}
          </button>
          <button onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-800 text-white text-sm font-semibold rounded-lg">
            + Add County
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow border border-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['County', 'State', 'Scraper', 'Deadline', 'Approval Rate', 'Properties', 'Leads', 'Last Synced', 'Actions'].map(h => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={9} className="px-4 py-10 text-center text-gray-400">
                <span className="inline-flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                  Loading counties…
                </span>
              </td></tr>
            ) : counties.length === 0 ? (
              <tr><td colSpan={9} className="px-4 py-12 text-center">
                <p className="text-gray-400 mb-3">No counties configured yet</p>
                <button onClick={() => setShowAddModal(true)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg">
                  + Add your first county
                </button>
              </td></tr>
            ) : counties.map((c) => {
              const hasRealScraper = REAL_SCRAPERS.has(c.scraperAdapter)
              const job = syncJobs[c.id]
              // Only show progress for jobs triggered in this session
              const showProgress = job && sessionJobIds.has(job.id)
              const jobRunning = job && (job.status === 'PENDING' || job.status === 'RUNNING')

              return (
                <tr key={c.id} className="hover:bg-gray-50 transition-colors align-top">
                  <td className="px-4 py-3 font-semibold text-gray-900 max-w-xs">
                    {c.name}
                    {showProgress && (
                      <SyncProgressCard
                        key={job.id}
                        job={job}
                        scraperAdapter={c.scraperAdapter}
                        onDone={silentRefresh}
                      />
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="bg-gray-100 text-gray-700 text-xs font-bold px-2 py-0.5 rounded">{c.state}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${hasRealScraper ? 'bg-green-500' : 'bg-gray-300'}`} />
                      <code className={`text-xs px-2 py-0.5 rounded ${hasRealScraper ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                        {c.scraperAdapter}
                      </code>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{c.appealDeadlineDays}d</td>
                  <td className="px-4 py-3 text-gray-600">
                    {c.approvalRateHist != null ? `${(c.approvalRateHist * 100).toFixed(0)}%` : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{c.propertyCount.toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <span className={`font-semibold ${c.leadCount > 0 ? 'text-blue-700' : 'text-gray-400'}`}>
                      {c.leadCount.toLocaleString()}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                    {c.lastScrapedAt ? (
                      <span className="flex items-center gap-1">
                        <span className="w-2 h-2 bg-green-400 rounded-full" />
                        {new Date(c.lastScrapedAt).toLocaleString()}
                      </span>
                    ) : <span className="text-gray-400">Never</span>}
                  </td>
                  <td className="px-4 py-3">
                    {hasRealScraper ? (
                      showProgress && jobRunning ? (
                        <span className="flex items-center gap-1.5 text-xs text-blue-600 font-medium">
                          <span className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                          Running…
                        </span>
                      ) : (
                        <button
                          onClick={() => handleScrape(c)}
                          disabled={!!busy}
                          className="px-3 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-md disabled:opacity-40 whitespace-nowrap flex items-center gap-1"
                        >
                          {busy === c.id
                            ? <><span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />Starting…</>
                            : '▶ Run Scraper'}
                        </button>
                      )
                    ) : (
                      <span className="text-xs text-gray-400 italic">No scraper yet</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-blue-50 rounded-lg border border-blue-100 text-sm text-blue-800">
          <p className="font-semibold mb-1">How to get real leads</p>
          <ol className="list-decimal list-inside space-y-1 text-blue-700">
            <li>Click <strong>▶ Run Scraper</strong> on any green-dot county</li>
            <li>Watch the progress bar — 2–10 min depending on county</li>
            <li>Click <strong>⚡ Score All Leads</strong> to run the AI model</li>
            <li>Visit <strong>Leads</strong> to see real scored properties</li>
          </ol>
        </div>
        <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 text-sm text-gray-700">
          <p className="font-semibold mb-2">Scraper legend</p>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-green-500 rounded-full" />
              <span>Live — pulls real assessment data from county website</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-gray-300 rounded-full" />
              <span>Stub — scraper not yet built for this county</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
