import { useState } from 'react'
import { createCounty, type CountyCreatePayload } from '../api/operations'

interface Props {
  onClose: () => void
  onCreated: () => void
}

const ADAPTERS = [
  { value: 'travis_tx',      label: 'Travis, TX' },
  { value: 'harris_tx',      label: 'Harris, TX' },
  { value: 'dallas_tx',      label: 'Dallas, TX' },
  { value: 'tarrant_tx',     label: 'Tarrant, TX' },
  { value: 'bexar_tx',       label: 'Bexar, TX' },
  { value: 'collin_tx',      label: 'Collin, TX' },
  { value: 'denton_tx',      label: 'Denton, TX' },
  { value: 'williamson_tx',  label: 'Williamson, TX' },
  { value: 'montgomery_tx',  label: 'Montgomery, TX' },
  { value: 'miami_dade_fl',  label: 'Miami-Dade, FL' },
  { value: 'broward_fl',     label: 'Broward, FL' },
  { value: 'palm_beach_fl',  label: 'Palm Beach, FL' },
  { value: 'hillsborough_fl',label: 'Hillsborough, FL' },
  { value: 'orange_fl',      label: 'Orange, FL' },
  { value: 'pinellas_fl',    label: 'Pinellas, FL' },
  { value: 'san_diego_ca',   label: 'San Diego, CA' },
  { value: 'los_angeles_ca', label: 'Los Angeles, CA' },
  { value: 'orange_ca',      label: 'Orange, CA' },
  { value: 'riverside_ca',   label: 'Riverside, CA' },
  { value: 'santa_clara_ca', label: 'Santa Clara, CA' },
  { value: 'cook_il',        label: 'Cook, IL' },
  { value: 'king_wa',        label: 'King, WA' },
  { value: 'maricopa_az',    label: 'Maricopa, AZ' },
  { value: 'clark_nv',       label: 'Clark, NV' },
  { value: 'fulton_ga',      label: 'Fulton, GA' },
  { value: 'mecklenburg_nc', label: 'Mecklenburg, NC' },
  { value: 'wake_nc',        label: 'Wake, NC' },
]

export default function AddCountyModal({ onClose, onCreated }: Props) {
  const [form, setForm] = useState<CountyCreatePayload>({
    name: '',
    state: '',
    portal_url: '',
    scraper_adapter: 'travis_tx',
    appeal_deadline_days: 45,
    approval_rate_hist: 0.35,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function set(field: keyof CountyCreatePayload, value: string | number | null) {
    setForm(f => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await createCounty(form)
      onCreated()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create county')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Add County</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">County Name</label>
              <input
                required
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Travis"
                value={form.name}
                onChange={e => set('name', e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">State (2-letter)</label>
              <input
                required
                maxLength={2}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 uppercase"
                placeholder="TX"
                value={form.state}
                onChange={e => set('state', e.target.value.toUpperCase())}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Portal URL</label>
            <input
              required
              type="url"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="https://www.traviscad.org"
              value={form.portal_url}
              onChange={e => set('portal_url', e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Scraper Adapter</label>
            <select
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={form.scraper_adapter}
              onChange={e => set('scraper_adapter', e.target.value)}
            >
              {ADAPTERS.map(a => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Deadline Days</label>
              <input
                required
                type="number"
                min={1}
                max={365}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={form.appeal_deadline_days}
                onChange={e => set('appeal_deadline_days', Number(e.target.value))}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Historical Approval %</label>
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="35"
                value={form.approval_rate_hist != null ? Math.round(form.approval_rate_hist * 100) : ''}
                onChange={e => set('approval_rate_hist', e.target.value ? Number(e.target.value) / 100 : null)}
              />
            </div>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg disabled:opacity-50"
            >
              {loading ? 'Adding...' : 'Add County'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
