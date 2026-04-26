import type { PriorityTier } from '../api/leads'

const COLORS: Record<PriorityTier, string> = {
  A: 'bg-green-100 text-green-800',
  B: 'bg-blue-100 text-blue-800',
  C: 'bg-yellow-100 text-yellow-800',
  D: 'bg-gray-100 text-gray-600',
}

export default function TierPill({ tier }: { tier: PriorityTier }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${COLORS[tier]}`}>
      {tier}
    </span>
  )
}
