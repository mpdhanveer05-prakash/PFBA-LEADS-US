import { useState, useEffect, useRef } from 'react'
import {
  uploadDncFile,
  applyDncList,
  fetchDncLists,
  fetchDncProperties,
  removeDncProperty,
  deleteDncList,
  fetchDncStats,
  type DncMatchPreview,
  type DncUploadResult,
  type DncList,
  type DncProperty,
  type DncStats,
} from '../api/dnc'

type Tab = 'upload' | 'properties' | 'history'

const REASON_LABEL: Record<string, string> = {
  email: 'Email',
  phone: 'Phone',
  apn: 'APN',
  address: 'Address',
  name: 'Name',
}

const REASON_COLOR: Record<string, string> = {
  email: 'bg-purple-100 text-purple-700',
  phone: 'bg-blue-100 text-blue-700',
  apn: 'bg-orange-100 text-orange-700',
  address: 'bg-green-100 text-green-700',
  name: 'bg-pink-100 text-pink-700',
}

export default function DNCPage() {
  const [tab, setTab] = useState<Tab>('upload')
  const [stats, setStats] = useState<DncStats | null>(null)

  useEffect(() => {
    fetchDncStats().then(setStats).catch(() => null)
  }, [tab])

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Do Not Call (DNC)</h1>
          <p className="text-sm text-gray-500 mt-1">
            Upload lists, match against leads, and manage DNC-flagged properties
          </p>
        </div>
        {stats && (
          <div className="flex gap-4">
            <StatCard label="DNC Properties" value={stats.totalDncProperties} color="text-red-600" />
            <StatCard label="Lists Uploaded" value={stats.totalLists} color="text-gray-700" />
            <StatCard label="Applied" value={stats.appliedLists} color="text-green-700" />
          </div>
        )}
      </div>

      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          {(['upload', 'properties', 'history'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t === 'upload' ? 'Upload & Analyse' : t === 'properties' ? 'Active DNC Records' : 'Upload History'}
            </button>
          ))}
        </nav>
      </div>

      {tab === 'upload' && <UploadTab onApplied={() => setTab('properties')} />}
      {tab === 'properties' && <PropertiesTab />}
      {tab === 'history' && <HistoryTab />}
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 text-center min-w-[110px]">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  )
}

// ── Upload & Analyse Tab ──────────────────────────────────────────────────────

function UploadTab({ onApplied }: { onApplied: () => void }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<DncUploadResult | null>(null)
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    setError(null)
    setResult(null)
    setUploading(true)
    try {
      const res = await uploadDncFile(file)
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const handleApply = async () => {
    if (!result) return
    setApplying(true)
    setError(null)
    try {
      await applyDncList(result.listId)
      onApplied()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Apply failed')
    } finally {
      setApplying(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
          dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls,.pdf"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        />
        {uploading ? (
          <div className="space-y-2">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-gray-600">Analysing file…</p>
          </div>
        ) : (
          <>
            <div className="text-4xl mb-3">⬆</div>
            <p className="text-base font-medium text-gray-700">Drop a DNC file here or click to browse</p>
            <p className="text-xs text-gray-400 mt-1">Supported: CSV, Excel (.xlsx/.xls), PDF — max 10 MB</p>
            <p className="text-xs text-gray-400 mt-1">
              Required columns (any order): <span className="font-medium">name / email / phone / address / apn</span>
            </p>
          </>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-gray-900">{result.filename}</h3>
                <p className="text-sm text-gray-500 mt-0.5">
                  {result.totalRecords} records · {result.matchedCount} matched to properties
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => { setResult(null); if (inputRef.current) inputRef.current.value = '' }}
                  className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50"
                >
                  Discard
                </button>
                <button
                  onClick={handleApply}
                  disabled={applying || result.matchedCount === 0}
                  className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  {applying ? 'Applying…' : `Apply DNC to ${result.matchedCount} properties`}
                </button>
              </div>
            </div>

            {result.matchedCount === 0 ? (
              <div className="text-center py-8 text-gray-400 text-sm">
                No matches found. No existing leads will be affected.
              </div>
            ) : (
              <MatchPreviewTable matches={result.matches} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function MatchPreviewTable({ matches }: { matches: DncMatchPreview[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            {['Match via', 'DNC Entry', 'Matched Property', 'APN', 'Owner'].map((h) => (
              <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {matches.map((m) => (
            <tr key={m.entryId} className="hover:bg-gray-50">
              <td className="px-4 py-3">
                <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${REASON_COLOR[m.matchReason] ?? 'bg-gray-100 text-gray-600'}`}>
                  {REASON_LABEL[m.matchReason] ?? m.matchReason}
                </span>
              </td>
              <td className="px-4 py-3">
                <p className="text-gray-900 font-medium">{m.rawName ?? '—'}</p>
                <p className="text-gray-400 text-xs">{m.rawEmail ?? m.rawPhone ?? m.rawAddress ?? m.rawApn ?? ''}</p>
              </td>
              <td className="px-4 py-3">
                <p className="text-gray-900">{m.matchedAddress}</p>
                <p className="text-gray-400 text-xs">{m.matchedCity}, {m.matchedState}</p>
              </td>
              <td className="px-4 py-3 text-gray-600 font-mono text-xs">{m.matchedApn}</td>
              <td className="px-4 py-3 text-gray-600">{m.matchedOwner ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Active DNC Properties Tab ─────────────────────────────────────────────────

function PropertiesTab() {
  const [properties, setProperties] = useState<DncProperty[]>([])
  const [loading, setLoading] = useState(true)
  const [removing, setRemoving] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    fetchDncProperties()
      .then(setProperties)
      .catch(() => setError('Failed to load'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleRemove = async (id: string) => {
    setRemoving(id)
    setError(null)
    try {
      await removeDncProperty(id)
      setProperties((prev) => prev.filter((p) => p.id !== id))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Remove failed')
    } finally {
      setRemoving(null)
    }
  }

  if (loading) return <LoadingSpinner />
  if (error) return <ErrorBanner message={error} />

  if (properties.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p className="text-lg font-medium">No DNC properties</p>
        <p className="text-sm mt-1">Upload and apply a DNC list to see results here</p>
      </div>
    )
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <p className="text-sm font-medium text-gray-700">{properties.length} DNC-flagged properties</p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['Address', 'APN', 'Owner', 'Flagged On', 'Source', ''].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {properties.map((p) => (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-900">{p.address}</p>
                  <p className="text-xs text-gray-400">{p.city}, {p.state}</p>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-600">{p.apn}</td>
                <td className="px-4 py-3 text-gray-600">{p.ownerName ?? '—'}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {p.dncAt ? new Date(p.dncAt).toLocaleDateString() : '—'}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">{p.dncSource ?? '—'}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleRemove(p.id)}
                    disabled={removing === p.id}
                    className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50 font-medium"
                  >
                    {removing === p.id ? 'Removing…' : 'Remove DNC'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Upload History Tab ────────────────────────────────────────────────────────

function HistoryTab() {
  const [lists, setLists] = useState<DncList[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    fetchDncLists()
      .then(setLists)
      .catch(() => setError('Failed to load history'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this upload? Matched properties will have DNC removed.')) return
    setDeleting(id)
    setError(null)
    try {
      await deleteDncList(id, true)
      setLists((prev) => prev.filter((l) => l.id !== id))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setDeleting(null)
    }
  }

  if (loading) return <LoadingSpinner />
  if (error) return <ErrorBanner message={error} />

  if (lists.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p className="text-lg font-medium">No uploads yet</p>
        <p className="text-sm mt-1">Upload a DNC file to get started</p>
      </div>
    )
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['Filename', 'Type', 'Status', 'Records', 'Matched', 'Uploaded By', 'Date', ''].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {lists.map((l) => (
              <tr key={l.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{l.filename}</td>
                <td className="px-4 py-3">
                  <span className="text-xs font-medium uppercase text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                    {l.fileType}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    l.status === 'applied'
                      ? 'bg-red-100 text-red-700'
                      : 'bg-yellow-100 text-yellow-700'
                  }`}>
                    {l.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-600">{l.totalRecords}</td>
                <td className="px-4 py-3 text-gray-600">{l.matchedCount}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">{l.uploadedBy}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {new Date(l.uploadedAt).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleDelete(l.id)}
                    disabled={deleting === l.id}
                    className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50 font-medium"
                  >
                    {deleting === l.id ? 'Deleting…' : 'Delete'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function LoadingSpinner() {
  return (
    <div className="flex justify-center py-16">
      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
      {message}
    </div>
  )
}
