import { LineChart, Line, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

interface AssessmentPoint {
  taxYear: number
  assessedTotal: number
}

interface Props {
  data: AssessmentPoint[]
  marketValue?: number | null
  width?: number
  height?: number
}

const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 0 })

export default function Sparkline({ data, marketValue, width = 160, height = 52 }: Props) {
  if (!data || data.length === 0) return null

  const sorted = [...data].sort((a, b) => a.taxYear - b.taxYear)
  const chartData = sorted.map(d => ({ year: d.taxYear, assessed: d.assessedTotal, market: marketValue ?? null }))

  return (
    <div title={`${sorted[0].taxYear}→${sorted[sorted.length - 1].taxYear}`}>
      <ResponsiveContainer width={width} height={height}>
        <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <Line
            type="monotone"
            dataKey="assessed"
            stroke="#ef4444"
            strokeWidth={2}
            dot={false}
            name="Assessed"
          />
          {marketValue != null && (
            <ReferenceLine y={marketValue} stroke="#16a34a" strokeDasharray="3 3" strokeWidth={1.5} />
          )}
          <Tooltip
            formatter={(v: number, name: string) => [fmt.format(v), name === 'assessed' ? 'Assessed' : 'Market']}
            labelFormatter={(l) => `Year ${l}`}
            contentStyle={{ fontSize: 11 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-xs text-center text-gray-400 mt-0.5">
        <span className="text-red-400">— assessed</span>
        {marketValue != null && <span className="text-green-600 ml-2">– – market</span>}
      </p>
    </div>
  )
}
