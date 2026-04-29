import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, PieChart, Pie,
} from 'recharts'
import { fetchDashboardStats, type DashboardStats } from '../api/dashboard'
import { triggerScoring } from '../api/operations'
import { triggerSync, fetchSyncJobs } from '../api/sync'
import { fetchCounties } from '../api/counties'
import StatCard from '../components/StatCard'
import { useToast } from '../components/Toast'

const TIER_COLORS: Record<string, string> = { A: '#16a34a', B: '#2563eb', C: '#d97706', D: '#9ca3af' }
const STATUS_COLORS: Record<string, string> = {
  NEW: '#9ca3af', ASSIGNED: '#2563eb', FILED: '#d97706',
  WON: '#16a34a', LOST: '#ef4444', WITHDRAWN: '#6b7280',
}

const DEMO_STEPS = [
  { label: 'Connect county portals', icon: '🔗', detail: 'Establishing connections to county assessor databases…' },
  { label: 'Sync property records', icon: '⬇️', detail: 'Downloading assessment records and comparable sales data…' },
  { label: 'Score leads with AI', icon: '🤖', detail: 'Running XGBoost model + SHAP explainability on each property…' },
  { label: 'Generate insights', icon: '📊', detail: 'Building ROI projections and prioritizing high-value appeals…' },
  { label: 'Ready to review!', icon: '✅', detail: 'All leads scored and ranked — navigating to your pipeline.' },
]

// How long to spend on each demo step (ms) — purely visual, independent of real sync
const STEP_DURATIONS = [1800, 5000, 5000, 3000, 1500]

function DemoModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [seeded, setSeeded] = useState(0)
  const [scored, setScored] = useState(0)
  const [done, setDone] = useState(false)
  const jobIdsRef = useRef<string[]>([])

  // Fire real sync in the background — demo animation never waits on it
  useEffect(() => {
    async function kick() {
      try {
        const counties = await fetchCounties()
        const ids = counties.slice(0, 3).map((c: { id: string }) => c.id)
        const result = await triggerSync(ids, 60)
        const jobList = Array.isArray(result) ? result : (result as { jobs?: { jobId: string }[] }).jobs ?? []
        jobIdsRef.current = jobList.map((j: { jobId?: string; id?: string }) => j.jobId ?? j.id ?? '')
      } catch { /* background — ignore errors */ }
    }
    kick()
  }, [])

  // Auto-advance through steps on fixed timers — always completes regardless of sync status
  useEffect(() => {
    if (done) return
    const duration = STEP_DURATIONS[step] ?? 2000
    const timer = setTimeout(() => {
      if (step < DEMO_STEPS.length - 1) {
        setStep(s => s + 1)
      } else {
        setDone(true)
      }
    }, duration)
    return () => clearTimeout(timer)
  }, [step, done])

  // Poll for real progress numbers to display in the counter (purely cosmetic)
  useEffect(() => {
    const interval = setInterval(async () => {
      if (jobIdsRef.current.length === 0) return
      try {
        const jobs = await fetchSyncJobs()
        const mine = jobs.filter((j) => jobIdsRef.current.includes(j.id))
        setSeeded(mine.reduce((s, j) => s + (j.recordsSeeded ?? 0), 0))
        setScored(mine.reduce((s, j) => s + (j.recordsScored ?? 0), 0))
      } catch { /* ignore */ }
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (done) setTimeout(() => { onClose(); navigate('/leads') }, 1500)
  }, [done, navigate, onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-gray-900 text-white rounded-2xl shadow-2xl w-full max-w-lg p-8 relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-500 hover:text-gray-300 text-xl">✕</button>
        <div className="text-center mb-6">
          <div className="text-4xl mb-2">🚀</div>
          <h2 className="text-2xl font-bold">Live Demo Mode</h2>
          <p className="text-gray-400 text-sm mt-1">Watch the AI pipeline run in real-time</p>
        </div>

        <div className="space-y-3 mb-6">
          {DEMO_STEPS.map((s, i) => (
            <div
              key={i}
              className={`flex items-start gap-3 p-3 rounded-xl transition-all duration-500 ${
                i === step ? 'bg-blue-600/30 border border-blue-500/50 scale-[1.01]' :
                i < step ? 'bg-green-600/20 border border-green-600/30' :
                'bg-white/5 border border-white/10 opacity-40'
              }`}
            >
              <span className="text-xl mt-0.5">{i < step ? '✅' : i === step ? s.icon : '○'}</span>
              <div>
                <div className="font-semibold text-sm">{s.label}</div>
                {i === step && <div className="text-xs text-gray-300 mt-0.5">{s.detail}</div>}
              </div>
              {i === step && !done && (
                <div className="ml-auto self-center w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
              )}
            </div>
          ))}
        </div>

        {(seeded > 0 || scored > 0) && (
          <div className="bg-white/10 rounded-xl p-4 mb-4 grid grid-cols-2 gap-4 text-center">
            <div>
              <div className="text-2xl font-black text-blue-300">{seeded.toLocaleString()}</div>
              <div className="text-xs text-gray-400">Properties synced</div>
            </div>
            <div>
              <div className="text-2xl font-black text-green-300">{scored.toLocaleString()}</div>
              <div className="text-xs text-gray-400">Leads scored</div>
            </div>
          </div>
        )}

        {done && (
          <div className="text-center text-green-400 font-semibold animate-pulse">
            Pipeline complete! Redirecting to leads…
          </div>
        )}
      </div>
    </div>
  )
}

const fmtCurrency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 })

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [error, setError] = useState('')
  const [scoring, setScoring] = useState(false)
  const [showDemo, setShowDemo] = useState(false)
  const [dataSource, setDataSource] = useState<'live' | 'generated' | null>(null)
  const { addToast } = useToast()

  useEffect(() => {
    setStats(null)
    fetchDashboardStats(dataSource ?? undefined).then(setStats).catch(() => setError('Failed to load stats'))
  }, [dataSource])

  async function handleScore() {
    setScoring(true)
    try {
      await triggerScoring(undefined, true)  // force=true re-scores existing tier-D leads
      addToast('Scoring queued — leads update in ~30s', 'success')
      setTimeout(() => fetchDashboardStats().then(setStats).catch(() => {}), 35000)
    } catch {
      addToast('Failed to queue scoring', 'error')
    } finally {
      setScoring(false)
    }
  }

  if (error) return (
    <div className="p-8 space-y-2">
      <p className="text-red-600 font-medium">Failed to load dashboard</p>
      <p className="text-sm text-gray-500">The backend may still be starting up. <button className="text-blue-600 underline" onClick={() => { setError(''); fetchDashboardStats().then(setStats).catch(() => setError('Failed to load stats')) }}>Retry</button></p>
    </div>
  )
  if (!stats) return (
    <div className="p-8 flex items-center gap-3 text-gray-500">
      <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      Loading dashboard…
    </div>
  )

  const tierData = Object.entries(stats.tierDistribution)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([tier, count]) => ({ tier, count }))

  const statusData = Object.entries(stats.appealStatusCounts).map(([status, value]) => ({ name: status, value }))

  const countyBarData = (stats.countyComparison ?? []).map((c) => ({
    county: c.county.length > 14 ? c.county.slice(0, 14) + '…' : c.county,
    avgGapPct: parseFloat(c.avgGapPct.toFixed(1)),
    totalSavings: c.totalSavings,
  }))

  return (
    <>
      {showDemo && <DemoModal onClose={() => setShowDemo(false)} />}
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-sm text-gray-500 mt-0.5">Overview of all leads and appeal activity</p>
          </div>
          <div className="flex items-center gap-3">
            {/* Data Source Filter */}
            <div className="flex gap-1 border border-gray-200 rounded-lg p-1 bg-white">
              {([null, 'live', 'generated'] as const).map((src) => (
                <button
                  key={String(src)}
                  onClick={() => setDataSource(src)}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                    dataSource === src
                      ? src === 'live' ? 'bg-green-600 text-white' : src === 'generated' ? 'bg-orange-500 text-white' : 'bg-blue-600 text-white'
                      : 'text-gray-500 hover:text-gray-800'
                  }`}
                >
                  {src === null ? 'All' : src === 'live' ? '🟢 Live' : '🟠 Generated'}
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowDemo(true)}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white flex items-center gap-2"
              style={{ background: 'linear-gradient(135deg, #6366f1 0%, #ec4899 100%)' }}
            >
              🚀 Live Demo
            </button>
            <button
              onClick={handleScore}
              disabled={scoring}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-semibold rounded-lg disabled:opacity-50 flex items-center gap-2"
            >
              {scoring
                ? <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Queuing…</>
                : '⚡ Score All Leads'}
            </button>
          </div>
        </div>

        {/* Primary Stat Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Leads" value={stats.totalLeads.toLocaleString()} sub="Scored properties" />
          <StatCard label="Total Est. Savings" value={fmtCurrency.format(stats.totalEstimatedSavings)} sub="Client savings potential" />
          <StatCard
            label="Avg. Probability"
            value={`${(stats.avgAppealProbability * 100).toFixed(1)}%`}
            sub="Appeal success rate"
          />
          <StatCard
            label="Urgent Deadlines"
            value={stats.urgentDeadlines}
            sub="Due in < 30 days"
            urgent={stats.urgentDeadlines > 0}
          />
        </div>

        {/* ROI Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="rounded-xl p-5 text-white" style={{ background: 'linear-gradient(135deg, #16a34a 0%, #15803d 100%)' }}>
            <div className="text-xs font-medium uppercase tracking-widest opacity-80 mb-1">Agency Revenue Est.</div>
            <div className="text-3xl font-black">{fmtCurrency.format(stats.agencyFeesEstimate ?? 0)}</div>
            <div className="text-sm opacity-75 mt-1">10% contingency on total savings</div>
          </div>
          <div className="rounded-xl p-5 text-white" style={{ background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)' }}>
            <div className="text-xs font-medium uppercase tracking-widest opacity-80 mb-1">Avg Savings / Lead</div>
            <div className="text-3xl font-black">{fmtCurrency.format(stats.avgSavingsPerLead ?? 0)}</div>
            <div className="text-sm opacity-75 mt-1">Per qualifying property</div>
          </div>
          <div className="rounded-xl p-5 text-white" style={{ background: 'linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%)' }}>
            <div className="text-xs font-medium uppercase tracking-widest opacity-80 mb-1">Tier A Leads</div>
            <div className="text-3xl font-black">{(stats.tierACount ?? 0).toLocaleString()}</div>
            <div className="text-sm opacity-75 mt-1">Highest priority — appeal now</div>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Tier Distribution */}
          <div className="bg-white rounded-xl shadow border border-gray-100 p-6">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Lead Tier Distribution</h2>
            {tierData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={tierData} barSize={48}>
                  <XAxis dataKey="tier" tick={{ fontSize: 13, fontWeight: 600 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => [v, 'Leads']} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {tierData.map((e) => <Cell key={e.tier} fill={TIER_COLORS[e.tier] ?? '#6b7280'} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-48 flex items-center justify-center text-gray-400 text-sm">No data yet</div>
            )}
          </div>

          {/* Appeal Pipeline */}
          <div className="bg-white rounded-xl shadow border border-gray-100 p-6">
            <h2 className="text-base font-semibold text-gray-800 mb-4">Appeal Pipeline Status</h2>
            {statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, value }) => `${name} (${value})`} labelLine={false} fontSize={11}>
                    {statusData.map((e) => <Cell key={e.name} fill={STATUS_COLORS[e.name] ?? '#6b7280'} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-48 flex items-center justify-center text-gray-400 text-sm">No appeals filed yet</div>
            )}
          </div>
        </div>

        {/* County Comparison Chart */}
        {countyBarData.length > 0 && (
          <div className="bg-white rounded-xl shadow border border-gray-100 p-6">
            <h2 className="text-base font-semibold text-gray-800 mb-1">County Comparison — Avg Assessment Gap %</h2>
            <p className="text-xs text-gray-500 mb-4">Top counties by average over-assessment percentage</p>
            <ResponsiveContainer width="100%" height={Math.max(220, countyBarData.length * 36)}>
              <BarChart data={countyBarData} layout="vertical" margin={{ left: 8, right: 32 }}>
                <XAxis type="number" tick={{ fontSize: 11 }} unit="%" />
                <YAxis type="category" dataKey="county" width={110} tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(v: number, name: string) => {
                    if (name === 'avgGapPct') return [`${v}%`, 'Avg Gap']
                    return [fmtCurrency.format(v), 'Total Savings']
                  }}
                />
                <Bar dataKey="avgGapPct" radius={[0, 4, 4, 0]} label={{ position: 'right', fontSize: 11, formatter: (v: number) => `${v}%` }}>
                  {countyBarData.map((_, i) => (
                    <Cell
                      key={i}
                      fill={`hsl(${220 - i * (180 / Math.max(countyBarData.length - 1, 1))}, 75%, 55%)`}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Tier Summary */}
        <div className="bg-white rounded-xl shadow border border-gray-100 p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Tier Summary</h2>
          <div className="grid grid-cols-4 gap-4">
            {['A', 'B', 'C', 'D'].map((tier) => {
              const count = stats.tierDistribution[tier] ?? 0
              const pct = stats.totalLeads > 0 ? ((count / stats.totalLeads) * 100).toFixed(0) : '0'
              const desc: Record<string, string> = {
                A: 'Prob ≥75% & Gap ≥15%',
                B: 'Prob ≥55% & Gap ≥10%',
                C: 'Prob ≥35% & Gap ≥5%',
                D: 'All others',
              }
              return (
                <div key={tier} className="text-center p-4 rounded-lg border" style={{ borderColor: TIER_COLORS[tier] + '44' }}>
                  <div className="text-3xl font-black" style={{ color: TIER_COLORS[tier] }}>{tier}</div>
                  <div className="text-2xl font-bold text-gray-900 mt-1">{count.toLocaleString()}</div>
                  <div className="text-xs text-gray-400">{pct}% of total</div>
                  <div className="text-xs text-gray-500 mt-1">{desc[tier]}</div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </>
  )
}
