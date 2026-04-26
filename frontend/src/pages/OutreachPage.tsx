import { useEffect, useState, useCallback } from 'react'
import { fetchLeads, type LeadListItem } from '../api/leads'
import {
  listCampaigns, generateCampaign, sendCampaign, updateCampaignStatus,
  type OutreachCampaign,
} from '../api/outreach'
import { useToast } from '../components/Toast'
import TierPill from '../components/TierPill'

const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

const STATUS_STYLE: Record<string, string> = {
  DRAFT:     'bg-gray-100 text-gray-600',
  SENT:      'bg-blue-100 text-blue-700',
  OPENED:    'bg-purple-100 text-purple-700',
  RESPONDED: 'bg-green-100 text-green-700',
  OPTED_OUT: 'bg-red-100 text-red-600',
}

const STATUS_ICON: Record<string, string> = {
  DRAFT: '✏️', SENT: '📤', OPENED: '👁', RESPONDED: '💬', OPTED_OUT: '🚫',
}

type Tab = 'leads' | 'campaigns'

export default function OutreachPage() {
  const [tab, setTab] = useState<Tab>('leads')
  const [leads, setLeads] = useState<LeadListItem[]>([])
  const [campaigns, setCampaigns] = useState<OutreachCampaign[]>([])
  const [selectedLead, setSelectedLead] = useState<LeadListItem | null>(null)
  const [previewCampaign, setPreviewCampaign] = useState<OutreachCampaign | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const { addToast } = useToast()

  const loadLeads = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchLeads({ pageSize: 50, sortBy: 'estimated_savings', sortDir: 'desc' })
      setLeads(res.items)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadCampaigns = useCallback(async () => {
    setLoading(true)
    try {
      const res = await listCampaigns(undefined, statusFilter === 'ALL' ? undefined : statusFilter)
      setCampaigns(res)
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => { if (tab === 'leads') loadLeads(); else loadCampaigns() }, [tab, loadLeads, loadCampaigns])

  async function handleGenerate(lead: LeadListItem) {
    setActionLoading(lead.id)
    try {
      const c = await generateCampaign(lead.id)
      setPreviewCampaign(c)
      addToast('Draft campaign generated', 'success')
    } catch {
      addToast('Failed to generate campaign', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleSend(campaignId: string) {
    setActionLoading(campaignId)
    try {
      await sendCampaign(campaignId)
      addToast('Email sent successfully', 'success')
      setPreviewCampaign(null)
      loadCampaigns()
      setTab('campaigns')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to send — check SMTP settings in backend .env'
      addToast(msg, 'error')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleStatusUpdate(campaignId: string, newStatus: string) {
    try {
      await updateCampaignStatus(campaignId, newStatus)
      addToast(`Marked as ${newStatus}`, 'success')
      loadCampaigns()
    } catch {
      addToast('Failed to update status', 'error')
    }
  }

  const statusCounts = campaigns.reduce<Record<string, number>>((acc, c) => {
    acc[c.status] = (acc[c.status] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Owner Outreach</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Generate personalised pitch emails for over-assessed property owners and track responses.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        {[
          { label: 'Total Campaigns', value: campaigns.length, color: 'text-gray-900' },
          { label: 'Draft', value: statusCounts.DRAFT ?? 0, color: 'text-gray-600' },
          { label: 'Sent', value: statusCounts.SENT ?? 0, color: 'text-blue-600' },
          { label: 'Responded', value: statusCounts.RESPONDED ?? 0, color: 'text-green-600' },
          { label: 'Opted Out', value: statusCounts.OPTED_OUT ?? 0, color: 'text-red-500' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-100 shadow-sm px-5 py-4">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border border-gray-200 rounded-lg p-1 bg-white w-fit mb-5">
        {(['leads', 'campaigns'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === t ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-800'
            }`}>
            {t === 'leads' ? '📋 Select Leads' : '📤 Campaign Tracker'}
          </button>
        ))}
      </div>

      {/* ── LEADS TAB ── */}
      {tab === 'leads' && (
        <div className="space-y-3">
          {loading && (
            <div className="flex items-center gap-2 text-gray-400 text-sm py-8 justify-center">
              <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              Loading leads…
            </div>
          )}
          {leads.map(lead => (
            <div key={lead.id}
              onClick={() => setSelectedLead(lead)}
              className={`bg-white rounded-xl border shadow-sm p-5 transition-all cursor-pointer ${
                selectedLead?.id === lead.id ? 'border-blue-400 shadow-md' : 'border-gray-100 hover:shadow-md'
              }`}>
              <div className="flex items-start gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <TierPill tier={lead.priorityTier} />
                    <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">{lead.propertyType}</span>
                    {lead.apn && (
                      <span className={`text-xs px-2 py-0.5 rounded font-mono ${
                        /^[A-Z]{2}-\d{3}-\d{4}-\d{2}$/.test(lead.apn)
                          ? 'bg-orange-100 text-orange-700'
                          : 'bg-green-100 text-green-700'
                      }`}>
                        {/^[A-Z]{2}-\d{3}-\d{4}-\d{2}$/.test(lead.apn) ? '🟠 Generated' : '🟢 Live'}
                      </span>
                    )}
                  </div>
                  <h3 className="text-base font-bold text-gray-900 truncate">{lead.address}</h3>
                  <p className="text-sm text-gray-500">{lead.city}, {lead.state} · {lead.countyName} County</p>
                </div>
                <div className="flex items-center gap-6 text-sm flex-shrink-0">
                  <div className="text-right">
                    <p className="text-xs text-gray-400">Assessed</p>
                    <p className="font-semibold text-gray-800">{fmt.format(Number(lead.assessedTotal))}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-400">Est. Savings</p>
                    <p className="font-semibold text-green-600">
                      {lead.estimatedSavings ? fmt.format(Number(lead.estimatedSavings)) : '—'}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-400">Probability</p>
                    <p className="font-semibold text-blue-600">
                      {lead.appealProbability ? `${(lead.appealProbability * 100).toFixed(0)}%` : '—'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleGenerate(lead)}
                    disabled={actionLoading === lead.id}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg disabled:opacity-50 flex items-center gap-2 transition-colors"
                  >
                    {actionLoading === lead.id
                      ? <><span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />Generating…</>
                      : '✉️ Generate Pitch'}
                  </button>
                </div>
              </div>
            </div>
          ))}
          {!loading && leads.length === 0 && (
            <div className="py-16 text-center text-gray-400">No leads found. Run a sync first.</div>
          )}
        </div>
      )}

      {/* ── CAMPAIGNS TAB ── */}
      {tab === 'campaigns' && (
        <>
          {/* Status filter */}
          <div className="flex gap-2 mb-4">
            {['ALL', 'DRAFT', 'SENT', 'OPENED', 'RESPONDED', 'OPTED_OUT'].map(s => (
              <button key={s} onClick={() => setStatusFilter(s)}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold border transition-colors ${
                  statusFilter === s
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'border-gray-200 text-gray-500 hover:border-blue-400 bg-white'
                }`}>
                {STATUS_ICON[s] ?? '📋'} {s}
              </button>
            ))}
          </div>

          {loading && (
            <div className="flex items-center gap-2 text-gray-400 text-sm py-8 justify-center">
              <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              Loading campaigns…
            </div>
          )}
          <div className="space-y-3">
            {campaigns.map(c => (
              <div key={c.id} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${STATUS_STYLE[c.status] ?? 'bg-gray-100 text-gray-600'}`}>
                        {STATUS_ICON[c.status]} {c.status}
                      </span>
                      <span className="text-xs text-gray-400">
                        Created {new Date(c.createdAt).toLocaleDateString()}
                      </span>
                      {c.sentAt && (
                        <span className="text-xs text-gray-400">
                          · Sent {new Date(c.sentAt).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <p className="font-semibold text-gray-900 text-sm truncate">{c.subject ?? '(No subject)'}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      To: {c.recipientEmail ?? <span className="text-orange-500">No email set</span>}
                    </p>
                    {c.body && (
                      <p className="text-xs text-gray-400 mt-2 line-clamp-2 font-mono bg-gray-50 rounded p-2">
                        {c.body.slice(0, 200)}…
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col gap-2 flex-shrink-0">
                    {c.status === 'DRAFT' && (
                      <button
                        onClick={() => handleSend(c.id)}
                        disabled={actionLoading === c.id}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors"
                      >
                        {actionLoading === c.id ? 'Sending…' : '📤 Send Email'}
                      </button>
                    )}
                    {c.status === 'SENT' && (
                      <button
                        onClick={() => handleStatusUpdate(c.id, 'RESPONDED')}
                        className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-semibold rounded-lg transition-colors"
                      >
                        💬 Mark Responded
                      </button>
                    )}
                    {(c.status === 'SENT' || c.status === 'OPENED') && (
                      <button
                        onClick={() => handleStatusUpdate(c.id, 'OPTED_OUT')}
                        className="px-3 py-1.5 border border-red-200 text-red-600 text-xs font-semibold rounded-lg hover:bg-red-50 transition-colors"
                      >
                        🚫 Opt Out
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {!loading && campaigns.length === 0 && (
              <div className="py-16 text-center text-gray-400">
                No campaigns yet. Go to "Select Leads" to generate your first pitch.
              </div>
            )}
          </div>
        </>
      )}

      {/* ── PREVIEW MODAL ── */}
      {previewCampaign && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-900">Preview & Send</h2>
              <button onClick={() => setPreviewCampaign(null)} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
            </div>
            <div className="flex-1 overflow-auto px-6 py-4">
              <div className="mb-4">
                <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Subject</label>
                <p className="text-sm font-medium text-gray-900 mt-1 bg-gray-50 rounded-lg px-3 py-2">
                  {previewCampaign.subject}
                </p>
              </div>
              <div className="mb-4">
                <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">To</label>
                <p className={`text-sm mt-1 px-3 py-2 rounded-lg ${
                  previewCampaign.recipientEmail
                    ? 'bg-gray-50 text-gray-900'
                    : 'bg-orange-50 text-orange-600 font-medium'
                }`}>
                  {previewCampaign.recipientEmail ?? '⚠️ No email address — update owner email in property record first'}
                </p>
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Body</label>
                <pre className="text-xs text-gray-700 mt-1 bg-gray-50 rounded-lg px-3 py-3 whitespace-pre-wrap font-mono leading-relaxed max-h-72 overflow-auto">
                  {previewCampaign.body}
                </pre>
              </div>
            </div>
            <div className="flex items-center gap-3 px-6 py-4 border-t border-gray-100">
              <button
                onClick={() => handleSend(previewCampaign.id)}
                disabled={!previewCampaign.recipientEmail || actionLoading === previewCampaign.id}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                {actionLoading === previewCampaign.id
                  ? <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Sending…</>
                  : '📤 Send Email Now'}
              </button>
              <button
                onClick={() => { setPreviewCampaign(null); setTab('campaigns'); loadCampaigns() }}
                className="px-5 py-2.5 border border-gray-200 text-gray-600 font-semibold rounded-lg hover:bg-gray-50 transition-colors"
              >
                Save as Draft
              </button>
              <button onClick={() => setPreviewCampaign(null)}
                className="ml-auto text-sm text-gray-400 hover:text-gray-600">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
