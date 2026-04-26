interface Props {
  label: string
  value: string | number
  sub?: string
  urgent?: boolean
}

export default function StatCard({ label, value, sub, urgent }: Props) {
  return (
    <div className={`bg-white rounded-lg shadow p-5 ${urgent ? 'border-l-4 border-red-500' : ''}`}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${urgent ? 'text-red-600' : 'text-gray-900'}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}
