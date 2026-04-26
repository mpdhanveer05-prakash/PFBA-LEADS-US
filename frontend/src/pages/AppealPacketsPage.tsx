import { useState, useEffect, useCallback } from 'react'
import { generatePacket, listPackets, downloadPacket, AppealPacket } from '../api/appeal_packets'
import { fetchLeads as fetchLeadsApi } from '../api/leads'

interface LeadItem {
  id: string
  address: string
  city: string
  state: string
  priorityTier: string
  estimatedSavings: number
  appealProbability: number
  assessedTotal: number
  marketValueEst: number
}

const TIER_COLORS: Record<string, string> = {
  A: 'bg-emerald-100 text-emerald-800',
  B: 'bg-blue-100 text-blue-800',
  C: 'bg-yellow-100 text-yellow-800',
  D: 'bg-gray-100 text-gray-600',
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: 'bg-gray-100 text-gray-700',
  READY: 'bg-blue-100 text-blue-700',
  FILED: 'bg-emerald-100 text-emerald-700',
}

export default function AppealPacketsPage() {
  const [activeTab, setActiveTab] = useState<'generate' | 'packets'>('generate')
  const [leads, setLeads] = useState<LeadItem[]>([])
  const [packets, setPackets] = useState<AppealPacket[]>([])
  const [loadingLeads, setLoadingLeads] = useState(false)
  const [loadingPackets, setLoadingPackets] = useState(false)
  const [generatingId, setGeneratingId] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const fetchLeads = useCallback(async () => {
    setLoadingLeads(true)
    setError(null)
    try {
      const data = await fetchLeadsApi({ pageSize: 50 })
      setLeads(
        (data.items ?? []).map((l: any) => ({
          id: l.id,
          address: l.address,
          city: l.city,
          state: l.state,
          priorityTier: l.priorityTier,
          estimatedSavings: l.estimatedSavings ?? 0,
          appealProbability: l.appealProbability ?? 0,
          assessedTotal: l.assessedTotal ?? 0,
          marketValueEst: l.marketValueEst ?? 0,
        }))
      )
    } catch {
      setError('Failed to load leads.')
    } finally {
      setLoadingLeads(false)
    }
  }, [])

  const fetchPackets = useCallback(async () => {
    setLoadingPackets(true)
    setError(null)
    try {
      const data = await listPackets()
      setPackets(data)
    } catch {
      setError('Failed to load appeal packets.')
    } finally {
      setLoadingPackets(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'generate') fetchLeads()
    else fetchPackets()
  }, [activeTab, fetchLeads, fetchPackets])

  const handleGenerate = async (leadId: string) => {
    setGeneratingId(leadId)
    setError(null)
    setSuccessMsg(null)
    try {
      await generatePacket(leadId)
      setSuccessMsg('Appeal packet generated successfully.')
      setActiveTab('packets')
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Failed to generate packet.')
    } finally {
      setGeneratingId(null)
    }
  }

  const handleDownload = async (packetId: string) => {
    setDownloadingId(packetId)
    try {
      await downloadPacket(packetId)
    } catch {
      setError('Failed to download packet.')
    } finally {
      setDownloadingId(null)
    }
  }

  const filteredPackets =
    statusFilter === 'ALL' ? packets : packets.filter((p) => p.status === statusFilter)

  const statuses = ['ALL', 'DRAFT', 'READY', 'FILED']

  const draftCount = packets.filter((p) => p.status === 'DRAFT').length
  const readyCount = packets.filter((p) => p.status === 'READY').length
  const filedCount = packets.filter((p) => p.status === 'FILED').length

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Appeal Packets</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Generate and manage property tax appeal PDF packets
          </p>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Packets', value: packets.length, color: 'text-gray-900' },
          { label: 'Draft', value: draftCount, color: 'text-gray-600' },
          { label: 'Ready', value: readyCount, color: 'text-blue-600' },
          { label: 'Filed', value: filedCount, color: 'text-emerald-600' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}
      {successMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-lg px-4 py-3 text-sm">
          {successMsg}
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="border-b border-gray-200 px-6">
          <div className="flex gap-6">
            {(['generate', 'packets'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-3 text-sm font-medium border-b-2 transition-colors capitalize ${
                  activeTab === tab
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-800'
                }`}
              >
                {tab === 'generate' ? 'Generate Packets' : 'My Packets'}
              </button>
            ))}
          </div>
        </div>

        {/* Generate tab */}
        {activeTab === 'generate' && (
          <div>
            <div className="px-6 py-4 border-b border-gray-100 bg-blue-50">
              <p className="text-sm text-blue-700">
                Select a lead below to generate a professional 4-page PDF appeal packet with
                assessment analysis, comparable sales evidence, and certification page.
              </p>
            </div>
            {loadingLeads ? (
              <div className="flex items-center justify-center py-16 text-gray-400">Loading leads…</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 text-xs text-gray-500 uppercase">
                    <th className="px-6 py-3 text-left font-medium">Tier</th>
                    <th className="px-6 py-3 text-left font-medium">Property</th>
                    <th className="px-6 py-3 text-right font-medium">Assessed</th>
                    <th className="px-6 py-3 text-right font-medium">Market Est.</th>
                    <th className="px-6 py-3 text-right font-medium">Est. Savings</th>
                    <th className="px-6 py-3 text-right font-medium">Probability</th>
                    <th className="px-6 py-3 text-center font-medium">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {leads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-gray-50">
                      <td className="px-6 py-3">
                        <span
                          className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                            TIER_COLORS[lead.priorityTier] ?? 'bg-gray-100 text-gray-600'
                          }`}
                        >
                          {lead.priorityTier}
                        </span>
                      </td>
                      <td className="px-6 py-3">
                        <p className="font-medium text-gray-900">{lead.address}</p>
                        <p className="text-xs text-gray-400">
                          {lead.city}, {lead.state}
                        </p>
                      </td>
                      <td className="px-6 py-3 text-right text-gray-700">
                        ${lead.assessedTotal.toLocaleString()}
                      </td>
                      <td className="px-6 py-3 text-right text-gray-700">
                        ${lead.marketValueEst.toLocaleString()}
                      </td>
                      <td className="px-6 py-3 text-right font-semibold text-emerald-600">
                        ${lead.estimatedSavings.toLocaleString()}
                      </td>
                      <td className="px-6 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 bg-gray-200 rounded-full h-1.5">
                            <div
                              className="bg-blue-500 h-1.5 rounded-full"
                              style={{ width: `${Math.round(lead.appealProbability * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-600">
                            {Math.round(lead.appealProbability * 100)}%
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-3 text-center">
                        <button
                          onClick={() => handleGenerate(lead.id)}
                          disabled={generatingId === lead.id}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          {generatingId === lead.id ? (
                            <>
                              <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                                <circle
                                  className="opacity-25"
                                  cx="12"
                                  cy="12"
                                  r="10"
                                  stroke="currentColor"
                                  strokeWidth="4"
                                />
                                <path
                                  className="opacity-75"
                                  fill="currentColor"
                                  d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                                />
                              </svg>
                              Generating…
                            </>
                          ) : (
                            'Generate PDF'
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {leads.length === 0 && !loadingLeads && (
                    <tr>
                      <td colSpan={7} className="px-6 py-12 text-center text-gray-400">
                        No leads found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Packets tab */}
        {activeTab === 'packets' && (
          <div>
            {/* Status filter */}
            <div className="px-6 py-3 border-b border-gray-100 flex items-center gap-2">
              <span className="text-xs text-gray-500 font-medium mr-1">Status:</span>
              {statuses.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    statusFilter === s
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {s}
                </button>
              ))}
              <button
                onClick={fetchPackets}
                className="ml-auto text-xs text-blue-600 hover:underline"
              >
                Refresh
              </button>
            </div>

            {loadingPackets ? (
              <div className="flex items-center justify-center py-16 text-gray-400">
                Loading packets…
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 text-xs text-gray-500 uppercase">
                    <th className="px-6 py-3 text-left font-medium">Packet ID</th>
                    <th className="px-6 py-3 text-left font-medium">Generated</th>
                    <th className="px-6 py-3 text-right font-medium">Claimed Value</th>
                    <th className="px-6 py-3 text-right font-medium">Comps</th>
                    <th className="px-6 py-3 text-center font-medium">Status</th>
                    <th className="px-6 py-3 text-center font-medium">Download</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {filteredPackets.map((pkt) => (
                    <tr key={pkt.id} className="hover:bg-gray-50">
                      <td className="px-6 py-3 font-mono text-xs text-gray-500">
                        {pkt.id.slice(0, 8)}…
                      </td>
                      <td className="px-6 py-3 text-gray-600">
                        {new Date(pkt.generatedAt).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      <td className="px-6 py-3 text-right text-gray-700">
                        {pkt.claimedValue != null ? `$${pkt.claimedValue.toLocaleString()}` : '—'}
                      </td>
                      <td className="px-6 py-3 text-right text-gray-600">
                        {pkt.evidenceComps ?? '—'}
                      </td>
                      <td className="px-6 py-3 text-center">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            STATUS_COLORS[pkt.status] ?? 'bg-gray-100 text-gray-600'
                          }`}
                        >
                          {pkt.status}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-center">
                        {pkt.s3Key ? (
                          <button
                            onClick={() => handleDownload(pkt.id)}
                            disabled={downloadingId === pkt.id}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            {downloadingId === pkt.id ? 'Downloading…' : 'Download PDF'}
                          </button>
                        ) : (
                          <span className="text-xs text-gray-400">Not available</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {filteredPackets.length === 0 && !loadingPackets && (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center text-gray-400">
                        No packets found. Generate one from the "Generate Packets" tab.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
