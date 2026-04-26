import { useEffect, useState } from 'react'
import api from '../api/client'

interface Appeal {
  id: string
  leadScoreId: string
  status: string
  filingDate: string | null
  deadlineDate: string | null
  assignedAgent: string | null
  actualSavings: number | null
  createdAt: string
}

function toCamel(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(toCamel)
  if (obj && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [
        k.replace(/_([a-z])/g, (_, c) => c.toUpperCase()), toCamel(v),
      ])
    )
  }
  return obj
}

const STATUSES = ['NEW', 'ASSIGNED', 'FILED', 'WON', 'LOST', 'WITHDRAWN']
const STATUS_STYLES: Record<string, string> = {
  NEW: 'bg-gray-100 text-gray-700 border-gray-200',
  ASSIGNED: 'bg-blue-50 text-blue-800 border-blue-200',
  FILED: 'bg-yellow-50 text-yellow-800 border-yellow-200',
  WON: 'bg-green-50 text-green-800 border-green-200',
  LOST: 'bg-red-50 text-red-700 border-red-200',
  WITHDRAWN: 'bg-gray-50 text-gray-500 border-gray-200',
}
const STATUS_HEADER: Record<string, string> = {
  NEW: 'bg-gray-500', ASSIGNED: 'bg-blue-600', FILED: 'bg-yellow-500',
  WON: 'bg-green-600', LOST: 'bg-red-500', WITHDRAWN: 'bg-gray-400',
}

const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

export default function AppealsPage() {
  const [appeals, setAppeals] = useState<Appeal[]>([])
  const [updating, setUpdating] = useState<string | null>(null)

  useEffect(() => {
    api.get('/appeals').then((r) => setAppeals(toCamel(r.data) as Appeal[])).catch(console.error)
  }, [])

  async function moveStatus(appeal: Appeal, status: string) {
    setUpdating(appeal.id)
    try {
      await api.patch(`/appeals/${appeal.id}`, { status })
      setAppeals((prev) => prev.map(a => a.id === appeal.id ? { ...a, status } : a))
    } finally {
      setUpdating(null)
    }
  }

  const grouped = STATUSES.reduce<Record<string, Appeal[]>>((acc, s) => {
    acc[s] = appeals.filter((a) => a.status === s)
    return acc
  }, {})

  const totalWon = grouped['WON'].reduce((sum, a) => sum + (Number(a.actualSavings) || 0), 0)

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-gray-900">Appeal Pipeline</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {appeals.length} appeals · {totalWon > 0 ? `${fmt.format(totalWon)} saved` : 'Drag cards to update status'}
        </p>
      </div>

      <div className="flex gap-4 overflow-x-auto pb-4">
        {STATUSES.map((status) => (
          <div key={status} className="flex-shrink-0 w-60">
            <div className={`flex items-center justify-between px-3 py-2 rounded-t-lg text-white text-xs font-bold uppercase ${STATUS_HEADER[status]}`}>
              <span>{status}</span>
              <span className="bg-white/20 rounded-full px-2 py-0.5">{grouped[status].length}</span>
            </div>
            <div className={`rounded-b-lg p-2 space-y-2 min-h-32 border ${STATUS_STYLES[status]}`}>
              {grouped[status].map((a) => {
                const isUrgent = a.deadlineDate && Math.ceil((new Date(a.deadlineDate).getTime() - Date.now()) / 86400000) <= 30
                return (
                  <div key={a.id} className={`bg-white rounded-lg shadow-sm p-3 text-xs border ${isUrgent ? 'border-red-300' : 'border-transparent'}`}>
                    {isUrgent && <p className="text-red-600 font-bold mb-1">⚠ Urgent deadline</p>}
                    <p className="font-medium text-gray-800 truncate">{a.assignedAgent ?? 'Unassigned'}</p>
                    {a.deadlineDate && (
                      <p className="text-gray-400 mt-1">Due: {new Date(a.deadlineDate).toLocaleDateString()}</p>
                    )}
                    {a.actualSavings != null && (
                      <p className="text-green-700 font-bold mt-1">{fmt.format(Number(a.actualSavings))} saved</p>
                    )}
                    {/* Quick status buttons */}
                    <div className="flex gap-1 mt-2 flex-wrap">
                      {STATUSES.filter(s => s !== status).slice(0, 3).map(s => (
                        <button
                          key={s}
                          onClick={() => moveStatus(a, s)}
                          disabled={updating === a.id}
                          className="text-xs px-1.5 py-0.5 border rounded hover:bg-gray-100 disabled:opacity-40 text-gray-500"
                        >
                          → {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )
              })}
              {grouped[status].length === 0 && (
                <p className="text-center text-gray-400 text-xs py-6">Empty</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
