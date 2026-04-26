interface Props { date: string | null }

export default function DeadlineBadge({ date }: Props) {
  if (!date) return <span className="text-gray-400 text-xs">—</span>
  const days = Math.ceil((new Date(date).getTime() - Date.now()) / 86400000)
  const urgent = days <= 30
  return (
    <span className={`text-xs font-medium ${urgent ? 'text-red-600 font-bold' : 'text-gray-600'}`}>
      {urgent && '⚠ '}
      {days > 0 ? `${days}d` : 'Overdue'}
    </span>
  )
}
