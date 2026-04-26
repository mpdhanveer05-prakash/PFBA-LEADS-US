import { useEffect, useRef, useState } from 'react'
import { fetchMapLeads, type MapLead } from '../api/ai'
import { fetchCounties, type County } from '../api/counties'
import type { PriorityTier } from '../api/leads'

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    L: any
  }
}

const TIER_COLORS: Record<string, string> = { A: '#16a34a', B: '#2563eb', C: '#d97706', D: '#9ca3af' }
const TIERS: PriorityTier[] = ['A', 'B', 'C', 'D']

const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

function leafletLoaded(): boolean {
  return typeof window !== 'undefined' && !!window.L
}

function ensureLeaflet(): Promise<void> {
  if (leafletLoaded()) return Promise.resolve()
  return new Promise((resolve) => {
    const cssId = 'leaflet-css'
    if (!document.getElementById(cssId)) {
      const link = document.createElement('link')
      link.id = cssId
      link.rel = 'stylesheet'
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
      document.head.appendChild(link)
    }
    const script = document.createElement('script')
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    script.onload = () => resolve()
    document.head.appendChild(script)
  })
}

export default function MapPage() {
  const mapRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const leafletMap = useRef<any>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markersRef = useRef<any>(null)
  const [leads, setLeads] = useState<MapLead[]>([])
  const [counties, setCounties] = useState<County[]>([])
  const [selectedTiers, setSelectedTiers] = useState<PriorityTier[]>([])
  const [selectedCounty, setSelectedCounty] = useState('')
  const [dataSource, setDataSource] = useState<'live' | 'generated' | null>(null)
  const [loading, setLoading] = useState(true)
  const [mapReady, setMapReady] = useState(false)

  useEffect(() => {
    ensureLeaflet().then(() => setMapReady(true))
    fetchCounties().then(setCounties).catch(() => {})
  }, [])

  useEffect(() => {
    if (!mapReady || !mapRef.current || leafletMap.current) return
    const L = window.L
    leafletMap.current = L.map(mapRef.current).setView([31.5, -99], 6)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(leafletMap.current)
    markersRef.current = L.layerGroup().addTo(leafletMap.current)
  }, [mapReady])

  useEffect(() => {
    if (!mapReady) return
    setLoading(true)
    fetchMapLeads(
      selectedTiers.length ? selectedTiers : undefined,
      selectedCounty || undefined,
      dataSource ?? undefined,
    ).then((data) => {
      setLeads(data)
      renderMarkers(data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [mapReady, selectedTiers, selectedCounty, dataSource])

  function renderMarkers(data: MapLead[]) {
    if (!mapReady || !leafletMap.current || !markersRef.current) return
    const L = window.L
    markersRef.current.clearLayers()
    data.forEach((lead) => {
      if (!lead.lat || !lead.lng) return
      const color = TIER_COLORS[lead.tier] ?? '#6b7280'
      const svgIcon = `
        <svg xmlns="http://www.w3.org/2000/svg" width="22" height="28" viewBox="0 0 22 28">
          <ellipse cx="11" cy="26" rx="5" ry="2" fill="rgba(0,0,0,0.18)"/>
          <path d="M11 1C6.03 1 2 5.03 2 10c0 6.5 9 17 9 17S20 16.5 20 10c0-4.97-4.03-9-9-9z"
            fill="${color}" stroke="white" stroke-width="1.5"/>
          <text x="11" y="13" text-anchor="middle" font-size="7" font-weight="bold" fill="white">${lead.tier}</text>
        </svg>
      `
      const icon = L.divIcon({
        html: svgIcon,
        className: '',
        iconSize: [22, 28],
        iconAnchor: [11, 28],
        popupAnchor: [0, -28],
      })

      const popupContent = `
        <div style="min-width:200px;font-family:sans-serif">
          <div style="font-weight:700;font-size:13px;margin-bottom:4px">${lead.address}</div>
          <div style="font-size:11px;color:#6b7280;margin-bottom:6px">${lead.city}, ${lead.countyName}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px">
            <div><span style="color:#9ca3af">Tier</span><br/><b style="color:${color}">${lead.tier}</b></div>
            <div><span style="color:#9ca3af">Gap</span><br/><b>${lead.gapPct != null ? (lead.gapPct * 100).toFixed(1) + '%' : '—'}</b></div>
            <div><span style="color:#9ca3af">Probability</span><br/><b>${lead.probability != null ? (lead.probability * 100).toFixed(0) + '%' : '—'}</b></div>
            <div><span style="color:#9ca3af">Est. Savings</span><br/><b style="color:#16a34a">${fmt.format(lead.savings)}</b></div>
          </div>
        </div>
      `
      const marker = L.marker([lead.lat, lead.lng], { icon })
      marker.bindPopup(popupContent, { maxWidth: 260 })
      markersRef.current!.addLayer(marker)
    })
  }

  const tierCounts: Record<string, number> = {}
  leads.forEach(l => { tierCounts[l.tier] = (tierCounts[l.tier] ?? 0) + 1 })

  return (
    <div className="flex flex-col h-full" style={{ height: 'calc(100vh - 0px)' }}>
      {/* Toolbar */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4 flex-shrink-0">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Property Map</h1>
          <p className="text-xs text-gray-500">
            {loading ? 'Loading…' : `${leads.length.toLocaleString()} leads`}
          </p>
        </div>

        <div className="flex gap-1.5 ml-4">
          {TIERS.map(t => (
            <button
              key={t}
              onClick={() => setSelectedTiers(p => p.includes(t) ? p.filter(x => x !== t) : [...p, t])}
              className={`px-2.5 py-1 rounded-md text-xs font-bold border transition-colors ${
                selectedTiers.includes(t)
                  ? 'text-white shadow'
                  : 'border-gray-300 text-gray-600 hover:border-blue-400 bg-white'
              }`}
              style={selectedTiers.includes(t) ? { background: TIER_COLORS[t], borderColor: TIER_COLORS[t] } : {}}
            >
              Tier {t} {tierCounts[t] ? `(${tierCounts[t]})` : ''}
            </button>
          ))}
        </div>

        <select
          value={selectedCounty}
          onChange={(e) => setSelectedCounty(e.target.value)}
          className="ml-2 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
        >
          <option value="">All Counties</option>
          {counties.map(c => (
            <option key={c.id} value={c.id}>{c.name}, {c.state}</option>
          ))}
        </select>

        <div className="flex gap-1 border border-gray-200 rounded-lg p-1 bg-white ml-2">
          {([null, 'live', 'generated'] as const).map((src) => (
            <button
              key={String(src)}
              onClick={() => setDataSource(src)}
              className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-colors ${
                dataSource === src
                  ? src === 'live' ? 'bg-green-600 text-white' : src === 'generated' ? 'bg-orange-500 text-white' : 'bg-blue-600 text-white'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              {src === null ? 'All' : src === 'live' ? '🟢 Live' : '🟠 Gen'}
            </button>
          ))}
        </div>

        {loading && (
          <div className="ml-2 w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        )}

        <div className="ml-auto flex items-center gap-4 text-xs text-gray-500">
          {Object.entries(TIER_COLORS).map(([tier, color]) => (
            <span key={tier} className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: color }} />
              Tier {tier}
            </span>
          ))}
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 relative">
        {!mapReady && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100 z-10">
            <div className="text-center text-gray-500">
              <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              Loading map…
            </div>
          </div>
        )}
        <div ref={mapRef} className="w-full h-full" />
      </div>
    </div>
  )
}
