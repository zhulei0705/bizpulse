import type { ReactNode } from 'react'

export function StatCard({ icon, label, value = '—', hint, tone }: {
  icon: ReactNode
  label: string
  value?: string | number
  hint?: string
  tone?: 'blue' | 'cyan' | 'purple' | 'gold' | 'green' | 'danger'
}) {
  return (
    <div className={`stat-card pulse-border ${tone ? `tone-${tone}` : ''}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        {hint && <small>{hint}</small>}
      </div>
      <div className="mini-spark"><i/><i/><i/><i/><i/></div>
    </div>
  )
}
