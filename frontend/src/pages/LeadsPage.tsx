import { useEffect, useState, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  createColumnHelper, flexRender, getCoreRowModel,
  useReactTable, type SortingState,
} from '@tanstack/react-table'
import {
  fetchLeads, fetchLead, assignLead,
  type LeadListItem, type LeadDetail, type LeadFilters, type PriorityTier,
} from '../api/leads'
import { nlSearch, generateLetter, bulkLetters } from '../api/ai'
import api from '../api/client'
import TierPill from '../components/TierPill'
import ProbabilityBar from '../components/ProbabilityBar'
import DeadlineBadge from '../components/DeadlineBadge'
import Sparkline from '../components/Sparkline'
import { useToast } from '../components/Toast'

const TIERS: PriorityTier[] = ['A', 'B', 'C', 'D']
const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const pct = (v: number | null) => v == null ? '—' : `${(v * 100).toFixed(1)}%`

// Seed APNs look like "TR-123-4567-89" (2-letter prefix + 3 dashed digit groups)
const SEED_APN = /^[A-Z]{2}-\d{3}-\d{4}-\d{2}$/
function DataSourceTag({ apn }: { apn: string | null }) {
  if (!apn) return null
  const isSeed = SEED_APN.test(apn)
  return isSeed
    ? <span className="inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 ml-1 align-middle">Generated</span>
    : <span className="inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded bg-green-100 text-green-700 ml-1 align-middle">Live</span>
}

const col = createColumnHelper<LeadListItem>()

function buildColumns(
  selected: Set<string>,
  onToggle: (id: string) => void,
  onToggleAll: (ids: string[]) => void,
  pageIds: string[],
) {
  return [
    col.display({
      id: 'select',
      header: () => (
        <input
          type="checkbox"
          checked={pageIds.length > 0 && pageIds.every(id => selected.has(id))}
          onChange={() => {
            const allSelected = pageIds.every(id => selected.has(id))
            onToggleAll(allSelected ? [] : pageIds)
          }}
          className="rounded"
        />
      ),
      cell: (i) => (
        <input
          type="checkbox"
          checked={selected.has(i.row.original.id)}
          onChange={(e) => { e.stopPropagation(); onToggle(i.row.original.id) }}
          onClick={(e) => e.stopPropagation()}
          className="rounded"
        />
      ),
    }),
    col.accessor('priorityTier', { header: 'Tier', cell: (i) => <TierPill tier={i.getValue()} /> }),
    col.accessor('address', {
      header: 'Address',
      cell: (i) => (
        <div>
          <p className="font-medium text-gray-900">
            {i.getValue()}
            <DataSourceTag apn={i.row.original.apn} />
          </p>
          <p className="text-xs text-gray-400">{i.row.original.city}, {i.row.original.state}</p>
        </div>
      ),
    }),
    col.accessor('countyName', { header: 'County' }),
    col.accessor('propertyType', { header: 'Type', cell: (i) => <span className="text-xs">{i.getValue()}</span> }),
    col.accessor('assessedTotal', { header: 'Assessed', cell: (i) => fmt.format(Number(i.getValue())) }),
    col.accessor('marketValueEst', { header: 'Market Est.', cell: (i) => i.getValue() ? fmt.format(Number(i.getValue())) : '—' }),
    col.accessor('gapPct', {
      header: 'Gap %',
      cell: (i) => {
        const v = i.getValue()
        if (v == null) return '—'
        const color = v >= 0.15 ? 'text-green-700 font-bold' : v >= 0.05 ? 'text-yellow-700' : 'text-gray-500'
        return <span className={color}>{pct(v)}</span>
      },
    }),
    col.accessor('appealProbability', {
      header: 'Probability',
      cell: (i) => <ProbabilityBar value={i.getValue()} />,
    }),
    col.accessor('estimatedSavings', {
      header: 'Est. Savings',
      cell: (i) => i.getValue() ? <span className="text-green-700 font-medium">{fmt.format(Number(i.getValue()))}</span> : '—',
    }),
    col.accessor('deadlineDate', { header: 'Deadline', cell: (i) => <DeadlineBadge date={i.getValue()} /> }),
  ]
}

export default function LeadsPage() {
  const [, setSearchParams] = useSearchParams()
  const [data, setData] = useState<LeadListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [selectedTiers, setSelectedTiers] = useState<PriorityTier[]>([])
  const [dataSource, setDataSource] = useState<'live' | 'generated' | null>(null)
  const [sorting, setSorting] = useState<SortingState>([])
  const [selectedLead, setSelectedLead] = useState<LeadDetail | null>(null)
  const [assignAgent, setAssignAgent] = useState('')
  const [assigning, setAssigning] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [nlQuery, setNlQuery] = useState('')
  const [nlLoading, setNlLoading] = useState(false)
  const [nlHint, setNlHint] = useState('')
  const [extraFilters, setExtraFilters] = useState<Partial<LeadFilters>>({})
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)
  const [letterLoading, setLetterLoading] = useState(false)
  const [letterText, setLetterText] = useState<string | null>(null)
  const [scoringBanner, setScoringBanner] = useState<{ unscored: number; total: number; done: boolean } | null>(null)
  const scoringPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { addToast } = useToast()
  const pageSize = 25

  const load = useCallback(async () => {
    const sort = sorting[0]
    const result = await fetchLeads({
      page, pageSize,
      tier: selectedTiers.length ? selectedTiers : undefined,
      sortBy: sort?.id,
      sortDir: sort ? (sort.desc ? 'desc' : 'asc') : undefined,
      dataSource: dataSource ?? undefined,
      ...extraFilters,
    })
    setData(result.items)
    setTotal(result.total)
  }, [page, selectedTiers, dataSource, sorting, extraFilters])

  useEffect(() => { load() }, [load])

  // ── Scoring-completion polling (activated by ?scoring=1 URL param) ──────────
  // Read param once at mount via ref so the effect only fires once
  const startScoringPoll = useRef(new URLSearchParams(window.location.search).get('scoring') === '1')
  useEffect(() => {
    if (!startScoringPoll.current) return

    // Remove the param so a page refresh / back-nav doesn't re-trigger
    setSearchParams({}, { replace: true })
    setScoringBanner({ unscored: 1, total: 0, done: false })

    const poll = async () => {
      try {
        const resp = await api.get('/scoring/status')
        const { unscored, total } = resp.data as { unscored: number; total: number; scored: number }
        if (unscored === 0) {
          setScoringBanner({ unscored: 0, total, done: true })
          if (scoringPollRef.current) clearInterval(scoringPollRef.current)
          load()
          setTimeout(() => setScoringBanner(null), 6000)
        } else {
          setScoringBanner({ unscored, total, done: false })
        }
      } catch { /* ignore poll errors */ }
    }

    poll()
    scoringPollRef.current = setInterval(poll, 3000)
    const timeout = setTimeout(() => {
      if (scoringPollRef.current) clearInterval(scoringPollRef.current)
      setScoringBanner(null)
    }, 120_000)

    return () => {
      if (scoringPollRef.current) clearInterval(scoringPollRef.current)
      clearTimeout(timeout)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleNlSearch() {
    if (!nlQuery.trim()) return
    setNlLoading(true)
    setNlHint('')
    try {
      const result = await nlSearch(nlQuery)
      const filters: Partial<LeadFilters> = {}
      if (result.tier?.length) setSelectedTiers(result.tier as PriorityTier[])
      if (result.countyId) filters.countyId = result.countyId
      if (result.propertyType) filters.propertyType = result.propertyType
      if (result.minGapPct != null) filters.minGapPct = result.minGapPct
      if (result.minEstimatedSavings != null) filters.minEstimatedSavings = result.minEstimatedSavings
      if (result.minAppealProbability != null) filters.minAppealProbability = result.minAppealProbability
      if (result.sortBy) setSorting([{ id: result.sortBy, desc: result.sortDir === 'desc' }])
      setExtraFilters(filters)
      setPage(1)
      if (result.interpretation) setNlHint(result.interpretation)
      addToast('Search applied', 'info')
    } catch {
      addToast('NL search failed', 'error')
    } finally {
      setNlLoading(false)
    }
  }

  function clearNlSearch() {
    setNlQuery('')
    setNlHint('')
    setExtraFilters({})
    setSelectedTiers([])
    setDataSource(null)
    setSorting([])
    setPage(1)
  }

  async function openLead(id: string) {
    const detail = await fetchLead(id)
    setSelectedLead(detail)
    setAssignAgent('')
    setLetterText(null)
  }

  async function handleAssign() {
    if (!selectedLead || !assignAgent.trim()) return
    setAssigning(true)
    try {
      await assignLead(selectedLead.id, assignAgent.trim())
      addToast(`Lead assigned to ${assignAgent}`, 'success')
      await load()
    } catch {
      addToast('Assignment failed', 'error')
    } finally {
      setAssigning(false)
    }
  }

  async function handleExport() {
    if (!selectedLead) return
    setExporting(true)
    try {
      const resp = await api.post(`/leads/${selectedLead.id}/export`, {}, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a')
      a.href = url; a.download = `lead_${selectedLead.id}.csv`; a.click()
      URL.revokeObjectURL(url)
      addToast('Export downloaded', 'success')
    } catch {
      addToast('Export failed', 'error')
    } finally {
      setExporting(false)
    }
  }

  async function handleGenerateLetter() {
    if (!selectedLead) return
    setLetterLoading(true)
    setLetterText(null)
    try {
      const text = await generateLetter(selectedLead.id)
      setLetterText(text)
      addToast('AI appeal letter generated', 'success')
    } catch {
      addToast('Letter generation failed', 'error')
    } finally {
      setLetterLoading(false)
    }
  }

  function downloadLetter() {
    if (!letterText || !selectedLead) return
    const blob = new Blob([letterText], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `appeal_letter_${selectedLead.id}.txt`; a.click()
    URL.revokeObjectURL(url)
  }

  async function handleBulkLetters() {
    if (selected.size === 0) return
    setBulkLoading(true)
    try {
      const blob = await bulkLetters(Array.from(selected))
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `appeal_letters_bulk.zip`; a.click()
      URL.revokeObjectURL(url)
      addToast(`${selected.size} letters exported`, 'success')
    } catch {
      addToast('Bulk export failed', 'error')
    } finally {
      setBulkLoading(false)
    }
  }

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleSelectAll(ids: string[]) {
    if (ids.length === 0) {
      setSelected(prev => {
        const next = new Set(prev)
        data.forEach(d => next.delete(d.id))
        return next
      })
    } else {
      setSelected(prev => new Set([...prev, ...ids]))
    }
  }

  const pageIds = data.map(d => d.id)
  const columns = buildColumns(selected, toggleSelect, toggleSelectAll, pageIds)

  const table = useReactTable({
    data,
    columns,
    pageCount: Math.ceil(total / pageSize),
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
  })

  return (
    <div className="p-6">
      {/* Scoring-completion banner */}
      {scoringBanner && (
        <div className={`mb-4 flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium ${
          scoringBanner.done
            ? scoringBanner.total === 0
              ? 'bg-yellow-50 border border-yellow-200 text-yellow-800'
              : 'bg-green-50 border border-green-200 text-green-800'
            : 'bg-blue-50 border border-blue-200 text-blue-800'
        }`}>
          {scoringBanner.done ? (
            scoringBanner.total === 0 ? (
              <>⚠ No assessments found to score. Go to <a href="/sync" className="underline font-semibold">Sync Center</a> → select counties → click Sync Now to generate leads first.</>
            ) : (
              <>✅ Scoring complete — {scoringBanner.total.toLocaleString()} leads ready.</>
            )
          ) : (
            <>
              <span className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
              Scoring in progress… {scoringBanner.unscored} assessment{scoringBanner.unscored !== 1 ? 's' : ''} left. Page will refresh automatically.
            </>
          )}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Leads</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total.toLocaleString()} total leads</p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {TIERS.map((t) => (
            <button
              key={t}
              onClick={() => { setSelectedTiers((p) => p.includes(t) ? p.filter(x => x !== t) : [...p, t]); setPage(1) }}
              className={`px-3 py-1.5 rounded-md text-sm font-bold border transition-colors ${
                selectedTiers.includes(t)
                  ? 'border-blue-600 bg-blue-600 text-white shadow'
                  : 'border-gray-300 text-gray-600 hover:border-blue-400 bg-white'
              }`}
            >
              Tier {t}
            </button>
          ))}
          <span className="h-5 w-px bg-gray-200 mx-1" />
          {([null, 'live', 'generated'] as const).map((src) => (
            <button
              key={src ?? 'all'}
              onClick={() => { setDataSource(src); setPage(1) }}
              className={`px-3 py-1.5 rounded-md text-sm font-semibold border transition-colors ${
                dataSource === src
                  ? src === 'live'
                    ? 'border-green-600 bg-green-600 text-white shadow'
                    : src === 'generated'
                      ? 'border-orange-500 bg-orange-500 text-white shadow'
                      : 'border-blue-600 bg-blue-600 text-white shadow'
                  : 'border-gray-300 text-gray-600 hover:border-gray-400 bg-white'
              }`}
            >
              {src === null ? 'All Sources' : src === 'live' ? '🟢 Live' : '🟠 Generated'}
            </button>
          ))}
        </div>
      </div>

      {/* NL Search */}
      <div className="mb-4 space-y-2">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-lg">✦</span>
            <input
              value={nlQuery}
              onChange={(e) => setNlQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleNlSearch()}
              placeholder='Ask in plain English: "Show Tier A leads in Travis County with savings over $5k"'
              className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-purple-400 bg-purple-50 placeholder-gray-400"
            />
          </div>
          <button
            onClick={handleNlSearch}
            disabled={nlLoading || !nlQuery.trim()}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm rounded-xl font-semibold disabled:opacity-40 flex items-center gap-2"
          >
            {nlLoading ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : '🔍'}
            {nlLoading ? 'Thinking…' : 'AI Search'}
          </button>
          {(nlHint || Object.keys(extraFilters).length > 0) && (
            <button onClick={clearNlSearch} className="px-3 py-2 text-sm text-gray-500 hover:text-gray-800 border rounded-xl bg-white">
              ✕ Clear
            </button>
          )}
        </div>
        {nlHint && (
          <p className="text-xs text-purple-600 bg-purple-50 border border-purple-200 px-3 py-1.5 rounded-lg">
            <span className="font-semibold">AI interpreted:</span> {nlHint}
          </p>
        )}
      </div>

      {/* Bulk Actions Bar */}
      {selected.size > 0 && (
        <div className="mb-3 flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-xl px-4 py-2.5">
          <span className="text-sm font-semibold text-blue-800">{selected.size} lead{selected.size > 1 ? 's' : ''} selected</span>
          <button
            onClick={handleBulkLetters}
            disabled={bulkLoading}
            className="ml-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 flex items-center gap-1.5"
          >
            {bulkLoading ? <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" /> : '📦'}
            {bulkLoading ? 'Generating…' : 'Export AI Letters (.zip)'}
          </button>
          <button onClick={() => setSelected(new Set())} className="ml-auto text-xs text-gray-500 hover:text-gray-700">
            Clear selection
          </button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl shadow overflow-hidden border border-gray-100">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => (
                    <th
                      key={h.id}
                      onClick={h.column.id !== 'select' ? h.column.getToggleSortingHandler() : undefined}
                      className={`px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap ${
                        h.column.id !== 'select' ? 'cursor-pointer select-none hover:text-gray-800' : ''
                      }`}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {h.column.getIsSorted() === 'asc' && ' ↑'}
                      {h.column.getIsSorted() === 'desc' && ' ↓'}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-gray-50">
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => openLead(row.original.id)}
                  className={`hover:bg-blue-50 cursor-pointer transition-colors ${
                    selectedLead?.id === row.original.id ? 'bg-blue-50' : ''
                  }`}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3 text-gray-700 whitespace-nowrap">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
              {data.length === 0 && (
                <tr>
                  <td colSpan={columns.length} className="px-4 py-16 text-center text-gray-400">
                    No leads found. Run a sync to populate data.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50">
          <span className="text-sm text-gray-500">
            Page {page} · {Math.ceil(total / pageSize) || 1} pages
          </span>
          <div className="flex gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="px-3 py-1 text-sm border rounded-md bg-white disabled:opacity-40 hover:bg-gray-100">
              ← Prev
            </button>
            <button onClick={() => setPage(p => p + 1)} disabled={page * pageSize >= total}
              className="px-3 py-1 text-sm border rounded-md bg-white disabled:opacity-40 hover:bg-gray-100">
              Next →
            </button>
          </div>
        </div>
      </div>

      {/* Detail Drawer */}
      {selectedLead && (
        <div className="fixed inset-0 z-40 flex pointer-events-none">
          <div className="flex-1 pointer-events-auto" onClick={() => setSelectedLead(null)} />
          <div className="w-full max-w-xl bg-white shadow-2xl overflow-y-auto pointer-events-auto border-l border-gray-200">
            <div className="sticky top-0 bg-white px-6 py-4 border-b border-gray-100 z-10">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <TierPill tier={selectedLead.priorityTier} />
                    <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">{selectedLead.propertyType}</span>
                    {selectedLead.modelVersion && (
                      <span className="text-xs text-gray-400">{selectedLead.modelVersion}</span>
                    )}
                  </div>
                  <h2 className="text-lg font-bold text-gray-900">{selectedLead.address}</h2>
                  <p className="text-sm text-gray-500">{selectedLead.city}, {selectedLead.state} · {selectedLead.countyName}</p>
                </div>
                <button onClick={() => setSelectedLead(null)} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">×</button>
              </div>
            </div>

            <div className="px-6 py-5 space-y-6">

              {/* Owner Contact */}
              <div className="bg-blue-50 rounded-lg px-4 py-3 space-y-1">
                <p className="text-xs font-semibold text-blue-700 uppercase tracking-wider mb-2">Owner Contact</p>
                {selectedLead.ownerName ? (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-gray-400 w-5">👤</span>
                    <span className="font-medium text-gray-900">{selectedLead.ownerName}</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-gray-400 w-5">👤</span>
                    <span className="text-gray-400 italic">Name not in public records</span>
                  </div>
                )}
                {selectedLead.mailingAddress && (
                  <div className="flex items-start gap-2 text-sm">
                    <span className="text-gray-400 w-5 mt-0.5">🏠</span>
                    <span className="text-gray-700">{selectedLead.mailingAddress}</span>
                  </div>
                )}
                {selectedLead.ownerEmail ? (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-gray-400 w-5">✉</span>
                    <a href={`mailto:${selectedLead.ownerEmail}`} className="text-blue-600 hover:underline">
                      {selectedLead.ownerEmail}
                    </a>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-gray-400 w-5">✉</span>
                    <span className="text-gray-400 italic text-xs">Email not available in public records</span>
                  </div>
                )}
                {selectedLead.ownerPhone ? (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-gray-400 w-5">📞</span>
                    <a href={`tel:${selectedLead.ownerPhone}`} className="text-blue-600 hover:underline">
                      {selectedLead.ownerPhone}
                    </a>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-gray-400 w-5">📞</span>
                    <span className="text-gray-400 italic text-xs">Phone not available in public records</span>
                  </div>
                )}
              </div>

              {/* Property Details */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Property Details</p>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {selectedLead.apn && (
                    <div className="col-span-2">
                      <span className="text-gray-500">APN: </span>
                      <span className="font-mono font-medium text-gray-800">{selectedLead.apn}</span>
                    </div>
                  )}
                  {selectedLead.zip && <div><span className="text-gray-500">ZIP: </span><span className="text-gray-800">{selectedLead.zip}</span></div>}
                  {selectedLead.yearBuilt && <div><span className="text-gray-500">Built: </span><span className="text-gray-800">{selectedLead.yearBuilt}</span></div>}
                  {selectedLead.buildingSqft && <div><span className="text-gray-500">Building: </span><span className="text-gray-800">{selectedLead.buildingSqft.toLocaleString()} sqft</span></div>}
                  {selectedLead.lotSizeSqft && <div><span className="text-gray-500">Lot: </span><span className="text-gray-800">{selectedLead.lotSizeSqft.toLocaleString()} sqft</span></div>}
                  {selectedLead.bedrooms != null && <div><span className="text-gray-500">Beds/Baths: </span><span className="text-gray-800">{selectedLead.bedrooms} / {selectedLead.bathrooms ?? '—'}</span></div>}
                </div>
              </div>

              {/* Assessment Sparkline */}
              {selectedLead.assessmentHistory.length > 1 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Assessment Trend</p>
                  <Sparkline
                    data={selectedLead.assessmentHistory}
                    marketValue={selectedLead.marketValueEst ? Number(selectedLead.marketValueEst) : null}
                    width={320}
                    height={80}
                  />
                </div>
              )}

              {/* Key Metrics */}
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Valuation</p>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    ['Assessed Total', fmt.format(Number(selectedLead.assessedTotal))],
                    ['Market Estimate', selectedLead.marketValueEst ? fmt.format(Number(selectedLead.marketValueEst)) : '—'],
                    ['Assessment Gap', selectedLead.assessmentGap ? fmt.format(Number(selectedLead.assessmentGap)) : '—'],
                    ['Gap %', pct(selectedLead.gapPct)],
                    ['Est. Annual Savings', selectedLead.estimatedSavings ? fmt.format(Number(selectedLead.estimatedSavings)) : '—'],
                    ['Deadline', selectedLead.deadlineDate ? new Date(selectedLead.deadlineDate).toLocaleDateString() : '—'],
                  ].map(([label, value]) => (
                    <div key={label} className="bg-gray-50 rounded-lg px-4 py-3">
                      <p className="text-xs text-gray-500">{label}</p>
                      <p className="font-semibold text-gray-900 mt-0.5">{value}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Probability */}
              <div>
                <p className="text-xs text-gray-500 mb-1">Appeal Probability</p>
                <ProbabilityBar value={selectedLead.appealProbability} />
              </div>

              {/* Assessment History Table */}
              {selectedLead.assessmentHistory.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">
                    Assessment History ({selectedLead.assessmentHistory.length} year{selectedLead.assessmentHistory.length > 1 ? 's' : ''})
                  </h3>
                  <div className="border border-gray-100 rounded-lg overflow-hidden">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50">
                        <tr>
                          {['Year', 'Assessed Total', 'Tax Amount', 'Land', 'Improvement'].map(h => (
                            <th key={h} className="px-3 py-2 text-left text-gray-500 font-medium">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {selectedLead.assessmentHistory.map(a => (
                          <tr key={a.id} className="hover:bg-gray-50">
                            <td className="px-3 py-2 font-semibold text-gray-800">{a.taxYear}</td>
                            <td className="px-3 py-2 font-medium">{fmt.format(Number(a.assessedTotal))}</td>
                            <td className="px-3 py-2 text-orange-600">{a.taxAmount ? fmt.format(Number(a.taxAmount)) : '—'}</td>
                            <td className="px-3 py-2 text-gray-600">{a.assessedLand ? fmt.format(Number(a.assessedLand)) : '—'}</td>
                            <td className="px-3 py-2 text-gray-600">{a.assessedImprovement ? fmt.format(Number(a.assessedImprovement)) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* SHAP */}
              {selectedLead.shapExplanation && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Top Model Features</h3>
                  <div className="space-y-1.5">
                    {Object.entries((selectedLead.shapExplanation as { shapValues?: Record<string, number> }).shapValues ?? {})
                      .sort(([, a], [, b]) => Math.abs(Number(b)) - Math.abs(Number(a)))
                      .slice(0, 6)
                      .map(([feat, val]) => {
                        const v = Number(val)
                        const w = Math.min(Math.abs(v) * 200, 100)
                        return (
                          <div key={feat} className="flex items-center gap-2 text-xs">
                            <span className="w-36 text-gray-500 truncate">{feat}</span>
                            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${v > 0 ? 'bg-green-400' : 'bg-red-400'}`} style={{ width: `${w}%` }} />
                            </div>
                            <span className={`w-12 text-right ${v > 0 ? 'text-green-600' : 'text-red-600'}`}>{v.toFixed(3)}</span>
                          </div>
                        )
                      })}
                  </div>
                </div>
              )}

              {/* Comparable Sales */}
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">
                  Comparable Sales ({selectedLead.comparableSales.length})
                </h3>
                {selectedLead.comparableSales.length > 0 ? (
                  <div className="border border-gray-100 rounded-lg overflow-hidden">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50">
                        <tr>
                          {['APN', 'Sale Price', '$/sqft', 'Distance', 'Match'].map(h => (
                            <th key={h} className="px-3 py-2 text-left text-gray-500 font-medium">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {selectedLead.comparableSales.map(c => (
                          <tr key={c.id} className="hover:bg-gray-50">
                            <td className="px-3 py-2 font-mono text-gray-600">{c.compApn}</td>
                            <td className="px-3 py-2">{fmt.format(Number(c.salePrice))}</td>
                            <td className="px-3 py-2">{c.pricePerSqft ? `$${Number(c.pricePerSqft).toFixed(0)}` : '—'}</td>
                            <td className="px-3 py-2">{c.distanceMiles != null ? `${Number(c.distanceMiles).toFixed(2)}mi` : '—'}</td>
                            <td className="px-3 py-2">
                              <span className={c.similarityScore && c.similarityScore > 0.7 ? 'text-green-600 font-bold' : 'text-gray-500'}>
                                {c.similarityScore ? `${(Number(c.similarityScore) * 100).toFixed(0)}%` : '—'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 py-2">No comparable sales available</p>
                )}
              </div>

              {/* AI Letter */}
              {letterText && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-gray-700">AI Appeal Letter</h3>
                    <button onClick={downloadLetter} className="text-xs text-blue-600 hover:underline">⬇ Download</button>
                  </div>
                  <pre className="text-xs bg-gray-50 border rounded-lg p-4 whitespace-pre-wrap font-sans max-h-72 overflow-y-auto text-gray-700">
                    {letterText}
                  </pre>
                </div>
              )}

              {/* Actions */}
              <div className="border-t pt-5 space-y-3">
                <h3 className="text-sm font-semibold text-gray-700">Actions</h3>

                <div className="flex gap-2">
                  <input
                    value={assignAgent}
                    onChange={(e) => setAssignAgent(e.target.value)}
                    placeholder="Assign to agent (name or email)"
                    className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    onClick={handleAssign}
                    disabled={assigning || !assignAgent.trim()}
                    className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-40 font-medium"
                  >
                    {assigning ? '...' : 'Assign'}
                  </button>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={handleExport}
                    disabled={exporting}
                    className="px-3 py-2 border border-gray-200 text-gray-700 text-xs rounded-lg hover:bg-gray-50 font-medium"
                  >
                    {exporting ? 'Exporting...' : '⬇ Export CSV'}
                  </button>
                  <button
                    onClick={handleGenerateLetter}
                    disabled={letterLoading}
                    className="px-3 py-2 bg-purple-600 text-white text-xs rounded-lg hover:bg-purple-700 font-medium flex items-center justify-center gap-1 disabled:opacity-50"
                  >
                    {letterLoading
                      ? <><span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" /> Generating…</>
                      : '✦ AI Letter'}
                  </button>
                  <button
                    onClick={() => setSelected(prev => { const next = new Set(prev); next.add(selectedLead.id); return next })}
                    className="px-3 py-2 border border-gray-200 text-gray-700 text-xs rounded-lg hover:bg-gray-50 font-medium"
                  >
                    ☑ Select
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
