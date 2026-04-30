import { useEffect, useState, useCallback } from 'react'
import {
  fetchLeads, fetchLead, verifyLead, unverifyLead,
  type LeadListItem, type LeadDetail, type PriorityTier,
} from '../api/leads'
import { useAuth } from '../hooks/useAuth'
import TierPill from '../components/TierPill'

const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const pct = (v: number | null) => v == null ? '—' : `${(v * 100).toFixed(1)}%`
const TIERS: PriorityTier[] = ['A', 'B', 'C', 'D']

function conversionScore(lead: LeadListItem): number {
  return Math.round((lead.appealProbability ?? 0) * 100)
}

function scoreLabel(score: number): string {
  if (score >= 75) return 'High Potential'
  if (score >= 55) return 'Good Potential'
  if (score >= 35) return 'Moderate'
  return 'Low Potential'
}

function scoreColor(score: number): { bar: string; text: string; bg: string; border: string } {
  if (score >= 75) return { bar: 'bg-green-500', text: 'text-green-700', bg: 'bg-green-50', border: 'border-green-200' }
  if (score >= 55) return { bar: 'bg-blue-500', text: 'text-blue-700', bg: 'bg-blue-50', border: 'border-blue-200' }
  if (score >= 35) return { bar: 'bg-yellow-500', text: 'text-yellow-700', bg: 'bg-yellow-50', border: 'border-yellow-200' }
  return { bar: 'bg-red-400', text: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200' }
}

function ScoreGauge({ score }: { score: number }) {
  const c = scoreColor(score)
  return (
    <div className={`rounded-lg px-4 py-3 ${c.bg} border ${c.border}`}>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Conversion Score</p>
      <div className="flex items-end gap-2 mb-2">
        <span className={`text-3xl font-black ${c.text}`}>{score}%</span>
        <span className={`text-sm font-semibold mb-0.5 ${c.text}`}>{scoreLabel(score)}</span>
      </div>
      <div className="h-2 bg-white/60 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${c.bar}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

function VerificationBadge({ lead }: { lead: LeadListItem }) {
  if (!lead.isVerified) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
        ○ Pending Review
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
      ✓ Verified{lead.verifiedBy ? ` by ${lead.verifiedBy}` : ''}
    </span>
  )
}

interface ExpandedDetail {
  leadId: string
  data: LeadDetail | null
  loading: boolean
}

export default function VerificationPage() {
  const { user } = useAuth()
  const [leads, setLeads] = useState<LeadListItem[]>([])
  const [total, setTotal] = useState(0)
  const [pendingTotal, setPendingTotal] = useState(0)
  const [verifiedTotal, setVerifiedTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [selectedTiers, setSelectedTiers] = useState<PriorityTier[]>([])
  const [filterVerified, setFilterVerified] = useState<'all' | 'pending' | 'verified'>('all')
  const [dataSource, setDataSource] = useState<'live' | 'generated' | null>(null)
  const [expanded, setExpanded] = useState<ExpandedDetail | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const pageSize = 12

  const load = useCallback(async () => {
    const result = await fetchLeads({
      page, pageSize,
      tier: selectedTiers.length ? selectedTiers : undefined,
      sortBy: 'appeal_probability',
      sortDir: 'desc',
      dataSource: dataSource ?? undefined,
    })
    setLeads(result.items)
    setTotal(result.total)
    setPendingTotal(result.pendingCount)
    setVerifiedTotal(result.verifiedCount)
  }, [page, selectedTiers, dataSource])

  useEffect(() => { load() }, [load])

  const visibleLeads = leads.filter(l => {
    if (filterVerified === 'pending') return !l.isVerified
    if (filterVerified === 'verified') return l.isVerified
    return true
  })

  async function toggleExpand(lead: LeadListItem) {
    if (expanded?.leadId === lead.id) {
      setExpanded(null)
      return
    }
    setExpanded({ leadId: lead.id, data: null, loading: true })
    const detail = await fetchLead(lead.id)
    setExpanded({ leadId: lead.id, data: detail, loading: false })
  }

  async function handleVerify(lead: LeadListItem) {
    setActionLoading(lead.id)
    try {
      const by = user?.username ?? 'agent'
      if (lead.isVerified) {
        await unverifyLead(lead.id)
      } else {
        await verifyLead(lead.id, by)
      }
      await load()
      if (expanded?.leadId === lead.id && expanded.data) {
        const detail = await fetchLead(lead.id)
        setExpanded({ leadId: lead.id, data: detail, loading: false })
      }
    } finally {
      setActionLoading(null)
    }
  }

  const pendingCount = pendingTotal
  const verifiedCount = verifiedTotal

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Lead Verification</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Review each lead's history, valuation, and property data — then confirm conversion potential.
        </p>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Leads', value: total.toLocaleString(), color: 'text-gray-900' },
          { label: 'Pending Review', value: pendingCount.toString(), color: 'text-orange-600' },
          { label: 'Verified', value: verifiedCount.toString(), color: 'text-green-600' },
          { label: 'Avg Conversion Score', value: leads.length ? `${Math.round(leads.reduce((s, l) => s + conversionScore(l), 0) / leads.length)}%` : '—', color: 'text-blue-600' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-100 shadow-sm px-5 py-4">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <div className="flex gap-1 bg-white border border-gray-200 rounded-lg p-1">
          {(['all', 'pending', 'verified'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilterVerified(f)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${
                filterVerified === f ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              {f === 'all' ? 'All' : f === 'pending' ? 'Pending Review' : 'Verified'}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {TIERS.map(t => (
            <button
              key={t}
              onClick={() => { setSelectedTiers(p => p.includes(t) ? p.filter(x => x !== t) : [...p, t]); setPage(1) }}
              className={`px-3 py-1.5 rounded-md text-sm font-bold border transition-colors ${
                selectedTiers.includes(t)
                  ? 'border-blue-600 bg-blue-600 text-white'
                  : 'border-gray-200 text-gray-500 hover:border-blue-400 bg-white'
              }`}
            >
              Tier {t}
            </button>
          ))}
        </div>
        <div className="flex gap-1 border border-gray-200 rounded-lg p-1 bg-white">
          {([null, 'live', 'generated'] as const).map((src) => (
            <button
              key={String(src)}
              onClick={() => { setDataSource(src); setPage(1) }}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                dataSource === src
                  ? src === 'live' ? 'bg-green-600 text-white' : src === 'generated' ? 'bg-orange-500 text-white' : 'bg-blue-600 text-white'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              {src === null ? 'All Sources' : src === 'live' ? '🟢 Live' : '🟠 Generated'}
            </button>
          ))}
        </div>
        <span className="ml-auto text-sm text-gray-400">{visibleLeads.length} shown</span>
      </div>

      {/* Cards */}
      <div className="space-y-4">
        {visibleLeads.map(lead => {
          const score = conversionScore(lead)
          const isExpanded = expanded?.leadId === lead.id
          return (
            <div key={lead.id} className={`bg-white rounded-xl shadow-sm border transition-shadow ${
              isExpanded ? 'border-blue-300 shadow-md' : 'border-gray-100 hover:shadow-md'
            }`}>
              {/* Card top */}
              <div className="p-5">
                <div className="flex items-start gap-4">
                  {/* Left: identity */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <TierPill tier={lead.priorityTier} />
                      <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">{lead.propertyType}</span>
                      <VerificationBadge lead={lead} />
                    </div>
                    <h3 className="text-base font-bold text-gray-900 truncate">{lead.address}</h3>
                    <p className="text-sm text-gray-500">{lead.city}, {lead.state} · {lead.countyName} County</p>
                  </div>

                  {/* Right: score */}
                  <div className="w-56 flex-shrink-0">
                    <ScoreGauge score={score} />
                  </div>
                </div>

                {/* Data row */}
                <div className="grid grid-cols-4 gap-3 mt-4">
                  {[
                    ['Assessed', lead.assessedTotal ? fmt.format(Number(lead.assessedTotal)) : '—'],
                    ['Market Est.', lead.marketValueEst ? fmt.format(Number(lead.marketValueEst)) : '—'],
                    ['Gap', pct(lead.gapPct)],
                    ['Est. Savings / yr', lead.estimatedSavings ? fmt.format(Number(lead.estimatedSavings)) : '—'],
                  ].map(([label, value]) => (
                    <div key={label} className="bg-gray-50 rounded-lg px-3 py-2">
                      <p className="text-xs text-gray-400">{label}</p>
                      <p className="text-sm font-semibold text-gray-800 mt-0.5">{value}</p>
                    </div>
                  ))}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 mt-4">
                  <button
                    onClick={() => handleVerify(lead)}
                    disabled={actionLoading === lead.id}
                    className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors disabled:opacity-40 ${
                      lead.isVerified
                        ? 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        : 'bg-green-600 text-white hover:bg-green-700'
                    }`}
                  >
                    {actionLoading === lead.id ? '...' : lead.isVerified ? '✓ Verified — Undo' : 'Mark Verified'}
                  </button>
                  <button
                    onClick={() => toggleExpand(lead)}
                    className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-800 border border-blue-200 rounded-lg hover:bg-blue-50 transition-colors"
                  >
                    {isExpanded ? 'Hide Details ↑' : 'Full Details ↓'}
                  </button>
                  {lead.deadlineDate && (
                    <span className="ml-auto text-xs text-orange-600 font-medium bg-orange-50 px-2 py-1 rounded">
                      Deadline {new Date(lead.deadlineDate).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="border-t border-gray-100 px-5 pb-5">
                  {expanded?.loading ? (
                    <div className="py-8 text-center text-gray-400 text-sm">Loading details...</div>
                  ) : expanded?.data ? (
                    <div className="pt-4 grid grid-cols-3 gap-6">
                      {/* Owner + Property */}
                      <div className="space-y-4">
                        <div>
                          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Owner Contact</p>
                          <div className="space-y-1">
                            <p className="text-sm font-medium text-gray-900">
                              {expanded.data.ownerName || <span className="text-gray-400 italic font-normal">Name not in public records</span>}
                            </p>
                            {expanded.data.mailingAddress && (
                              <p className="text-sm text-gray-600">📬 {expanded.data.mailingAddress}</p>
                            )}
                            {expanded.data.ownerEmail ? (
                              <a href={`mailto:${expanded.data.ownerEmail}`} className="block text-sm text-blue-600 hover:underline truncate">
                                {expanded.data.ownerEmail}
                              </a>
                            ) : (
                              <p className="text-xs text-gray-400 italic">No email in public records</p>
                            )}
                            {expanded.data.ownerPhone ? (
                              <a href={`tel:${expanded.data.ownerPhone}`} className="block text-sm text-blue-600 hover:underline">
                                {expanded.data.ownerPhone}
                              </a>
                            ) : (
                              <p className="text-xs text-gray-400 italic">No phone in public records</p>
                            )}
                          </div>
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Property</p>
                          <div className="space-y-1 text-sm">
                            {expanded.data.apn && <p><span className="text-gray-400">APN: </span><span className="font-mono font-medium">{expanded.data.apn}</span></p>}
                            {expanded.data.zip && <p><span className="text-gray-400">ZIP: </span>{expanded.data.zip}</p>}
                            {expanded.data.yearBuilt && <p><span className="text-gray-400">Built: </span>{expanded.data.yearBuilt}</p>}
                            {expanded.data.buildingSqft && <p><span className="text-gray-400">Size: </span>{expanded.data.buildingSqft.toLocaleString()} sqft</p>}
                            {expanded.data.bedrooms != null && <p><span className="text-gray-400">Beds/Baths: </span>{expanded.data.bedrooms} / {expanded.data.bathrooms ?? '—'}</p>}
                          </div>
                        </div>
                      </div>

                      {/* Assessment History */}
                      <div>
                        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                          Assessment History
                        </p>
                        {expanded.data.assessmentHistory.length > 0 ? (
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="text-gray-400">
                                <th className="text-left py-1 font-medium">Year</th>
                                <th className="text-right py-1 font-medium">Assessed</th>
                                <th className="text-right py-1 font-medium">Tax</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50">
                              {expanded.data.assessmentHistory.map((a, i) => (
                                <tr key={a.id} className={i === 0 ? 'font-semibold' : ''}>
                                  <td className="py-1.5 text-gray-700">{a.taxYear}</td>
                                  <td className="py-1.5 text-right text-gray-800">{fmt.format(Number(a.assessedTotal))}</td>
                                  <td className="py-1.5 text-right text-orange-600">{a.taxAmount ? fmt.format(Number(a.taxAmount)) : '—'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <p className="text-xs text-gray-400">No history available</p>
                        )}

                        {/* YoY change */}
                        {expanded.data.assessmentHistory.length >= 2 && (() => {
                          const [latest, prev] = expanded.data!.assessmentHistory
                          const change = (Number(latest.assessedTotal) - Number(prev.assessedTotal)) / Number(prev.assessedTotal)
                          const up = change > 0
                          return (
                            <div className={`mt-3 text-xs font-medium px-2 py-1 rounded inline-flex items-center gap-1 ${up ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'}`}>
                              {up ? '▲' : '▼'} {Math.abs(change * 100).toFixed(1)}% vs prior year
                            </div>
                          )
                        })()}
                      </div>

                      {/* Comparable Sales */}
                      <div>
                        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                          Comparable Sales ({expanded.data.comparableSales.length})
                        </p>
                        {expanded.data.comparableSales.length > 0 ? (
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="text-gray-400">
                                <th className="text-left py-1 font-medium">Sale Price</th>
                                <th className="text-right py-1 font-medium">$/sqft</th>
                                <th className="text-right py-1 font-medium">Match</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50">
                              {expanded.data.comparableSales.slice(0, 5).map(c => (
                                <tr key={c.id}>
                                  <td className="py-1.5 text-gray-800">{fmt.format(Number(c.salePrice))}</td>
                                  <td className="py-1.5 text-right text-gray-600">{c.pricePerSqft ? `$${Number(c.pricePerSqft).toFixed(0)}` : '—'}</td>
                                  <td className="py-1.5 text-right">
                                    <span className={c.similarityScore && c.similarityScore > 0.7 ? 'text-green-600 font-bold' : 'text-gray-400'}>
                                      {c.similarityScore ? `${(c.similarityScore * 100).toFixed(0)}%` : '—'}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <p className="text-xs text-gray-400">No comps available</p>
                        )}

                        {/* SHAP if available */}
                        {expanded.data.shapExplanation && (
                          <div className="mt-3">
                            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Score Drivers</p>
                            <div className="space-y-1">
                              {Object.entries((expanded.data.shapExplanation as any).shapValues ?? {})
                                .sort(([, a], [, b]) => Math.abs(Number(b)) - Math.abs(Number(a)))
                                .slice(0, 4)
                                .map(([feat, val]) => {
                                  const v = Number(val)
                                  const w = Math.min(Math.abs(v) * 200, 100)
                                  return (
                                    <div key={feat} className="flex items-center gap-1.5 text-xs">
                                      <span className="w-24 text-gray-400 truncate">{feat}</span>
                                      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                        <div className={`h-full ${v > 0 ? 'bg-green-400' : 'bg-red-400'}`} style={{ width: `${w}%` }} />
                                      </div>
                                    </div>
                                  )
                                })}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          )
        })}

        {visibleLeads.length === 0 && (
          <div className="py-16 text-center text-gray-400">
            No leads match the current filters.
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-6">
        <span className="text-sm text-gray-500">Page {page} · {Math.ceil(total / pageSize) || 1} pages</span>
        <div className="flex gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="px-3 py-1.5 text-sm border rounded-md bg-white disabled:opacity-40 hover:bg-gray-100">
            ← Prev
          </button>
          <button onClick={() => setPage(p => p + 1)} disabled={page * pageSize >= total}
            className="px-3 py-1.5 text-sm border rounded-md bg-white disabled:opacity-40 hover:bg-gray-100">
            Next →
          </button>
        </div>
      </div>
    </div>
  )
}
